import json
import os
import shutil
import tomllib
from pathlib import Path


class HookInstallError(Exception):
    pass


_CODEX_HOOK_BLOCK = """
[[hooks.SessionStart]]
matcher = "startup|resume"

[[hooks.SessionStart.hooks]]
type = "command"
command = "{command}"
timeout = 30
statusMessage = "agent-config-sync: checking config sync"
"""


def _validate_command(command: str) -> None:
    if any(ch in command for ch in '"\\\n'):
        raise HookInstallError("hook command must be a simple literal (no quotes/backslashes)")


def _existing_hook_commands(data: dict, *, format_name: str, create_missing: bool) -> list[str]:
    if create_missing:
        hooks = data.setdefault("hooks", {})
    else:
        hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        raise HookInstallError(f"{format_name} hooks must be an object/table")

    if create_missing:
        sessionstart = hooks.setdefault("SessionStart", [])
    else:
        sessionstart = hooks.get("SessionStart", [])
    if not isinstance(sessionstart, list):
        raise HookInstallError(f"{format_name} hooks.SessionStart must be a list")

    commands: list[str] = []
    for entry in sessionstart:
        if not isinstance(entry, dict):
            raise HookInstallError(f"{format_name} SessionStart entries must be objects/tables")
        nested = entry.get("hooks", [])
        if not isinstance(nested, list):
            raise HookInstallError(f"{format_name} SessionStart entry hooks must be a list")
        for hook in nested:
            if not isinstance(hook, dict):
                raise HookInstallError(f"{format_name} nested hook entries must be objects/tables")
            command_value = hook.get("command")
            if isinstance(command_value, str):
                commands.append(command_value)
    return commands


def install_codex_hook(
    config_path: Path,
    command: str,
    *,
    backup_root: Path,
    stamp: str,
    replace_commands: tuple[str, ...] = (),
) -> bool:
    """Append one SessionStart command hook to a Codex config.toml.

    Codex hooks are config-driven via ``[[hooks.SessionStart]]`` array-of-tables.
    This appends one top-level array-of-tables block, preserving existing keys and
    validating both the old and new TOML before writing. A superseded command in
    ``replace_commands`` is removed only when its block is byte-identical to what
    this installer originally wrote; an operator-edited block is left in place.
    """
    _validate_command(command)
    for old in replace_commands:
        _validate_command(old)

    if config_path.exists():
        text = config_path.read_text("utf-8")
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise HookInstallError(f"config.toml is not valid TOML: {exc}") from exc
    else:
        text = ""
        data = {}

    removed = False
    for old in replace_commands:
        old_block = _CODEX_HOOK_BLOCK.format(command=old)
        if old_block in text:
            text = text.replace(old_block, "", 1)
            removed = True
    if removed:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise HookInstallError(
                f"refusing: removing superseded hook left invalid TOML: {exc}"
            ) from exc

    existing = _existing_hook_commands(data, format_name="config.toml", create_missing=False)
    if command in existing and not removed:
        return False

    if command in existing:
        new_text = text
    else:
        block = _CODEX_HOOK_BLOCK.format(command=command)
        sep = "" if (not text or text.endswith("\n")) else "\n"
        new_text = text + sep + block
    try:
        new_data = tomllib.loads(new_text)
        _existing_hook_commands(new_data, format_name="config.toml", create_missing=False)
    except tomllib.TOMLDecodeError as exc:
        raise HookInstallError(f"refusing to write invalid TOML: {exc}") from exc

    if config_path.exists():
        dest = backup_root / "codex-config" / stamp / config_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_path, dest)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_name(config_path.name + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, config_path)
    return True


def install_claude_hook(
    settings_path: Path,
    command: str,
    *,
    backup_root: Path,
    stamp: str,
    replace_commands: tuple[str, ...] = (),
) -> bool:
    """Append one SessionStart command hook to a Claude settings.json.

    The writer parses the full JSON object, validates the hook subtree shape,
    mutates only ``hooks.SessionStart``, backs up first, and writes atomically.
    A SessionStart entry is removed as superseded only when every command it
    carries is in ``replace_commands`` — entries with unrelated hooks are kept.
    """
    _validate_command(command)
    for old in replace_commands:
        _validate_command(old)

    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            raise HookInstallError(f"settings.json is not valid JSON: {exc}") from exc
    else:
        data = {}
    if not isinstance(data, dict):
        raise HookInstallError("settings.json top level is not an object")

    _existing_hook_commands(data, format_name="settings.json", create_missing=True)

    removed = False
    if replace_commands:
        kept = []
        for entry in data["hooks"]["SessionStart"]:
            cmds = [
                h.get("command")
                for h in entry.get("hooks", [])
                if isinstance(h, dict) and isinstance(h.get("command"), str)
            ]
            if cmds and all(c in replace_commands for c in cmds):
                removed = True
                continue
            kept.append(entry)
        data["hooks"]["SessionStart"] = kept

    existing = _existing_hook_commands(data, format_name="settings.json", create_missing=True)
    if command in existing and not removed:
        return False

    if settings_path.exists():
        dest = backup_root / "settings" / stamp / settings_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(settings_path, dest)

    if command not in existing:
        data["hooks"]["SessionStart"].append({"hooks": [{"type": "command", "command": command}]})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = settings_path.with_name(settings_path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, settings_path)
    return True