import json
import tomllib
from pathlib import Path

import pytest

from agent_config_sync.settingsedit import (
    HookInstallError,
    install_claude_hook,
    install_codex_hook,
)

CMD = "agent-config-sync check"

CODEX_TOML = (
    'model = "gpt-5.5"\n\n'
    'notify = ["existing-notify.exe", "turn-ended"]\n\n'
    '[plugins."github@openai-curated"]\n'
    "enabled = true\n"
)


def _codex_cmds(path):
    data = tomllib.loads(path.read_text("utf-8"))
    return [
        h.get("command")
        for e in data.get("hooks", {}).get("SessionStart", [])
        for h in e.get("hooks", [])
    ]


def test_codex_hook_appends_preserving_existing(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(CODEX_TOML, encoding="utf-8")
    added = install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1")
    assert added is True
    data = tomllib.loads(p.read_text("utf-8"))
    assert data["notify"] == ["existing-notify.exe", "turn-ended"]  # preserved
    assert data["plugins"]["github@openai-curated"]["enabled"] is True  # preserved
    assert data["model"] == "gpt-5.5"
    assert CMD in _codex_cmds(p)  # our hook added


def test_codex_hook_idempotent(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(CODEX_TOML, encoding="utf-8")
    assert install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1") is True
    assert install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T2") is False
    assert _codex_cmds(p).count(CMD) == 1


def test_codex_hook_creates_when_absent(tmp_path):
    p = tmp_path / "config.toml"
    install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1")
    assert CMD in _codex_cmds(p)


def test_codex_hook_backup_written(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(CODEX_TOML, encoding="utf-8")
    install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1")
    assert (tmp_path / "b" / "codex-config" / "T1" / "config.toml").exists()


def test_codex_hook_parse_error_aborts(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("this = = invalid toml", encoding="utf-8")
    with pytest.raises(HookInstallError):
        install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1")
    assert p.read_text("utf-8") == "this = = invalid toml"  # untouched


def test_codex_hook_rejects_unsafe_command(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(CODEX_TOML, encoding="utf-8")
    with pytest.raises(HookInstallError):
        install_codex_hook(p, 'bad" injected', backup_root=tmp_path / "b", stamp="T1")


def _write(p, obj):
    p.write_text(json.dumps(obj), encoding="utf-8")


def test_appends_without_clobbering_existing(tmp_path):
    s = tmp_path / "settings.json"
    _write(s, {
        "model": "opus",
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "python existing.py"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "python stop.py"}]}],
        },
    })
    added = install_claude_hook(s, CMD, backup_root=tmp_path / "b", stamp="T1")
    assert added is True
    data = json.loads(s.read_text("utf-8"))
    cmds = [h["command"] for e in data["hooks"]["SessionStart"] for h in e["hooks"]]
    assert "python existing.py" in cmds and CMD in cmds
    assert data["hooks"]["Stop"][0]["hooks"][0]["command"] == "python stop.py"
    assert data["model"] == "opus"


def test_idempotent(tmp_path):
    s = tmp_path / "settings.json"
    _write(s, {"hooks": {"SessionStart": []}})
    assert install_claude_hook(s, CMD, backup_root=tmp_path / "b", stamp="T1") is True
    assert install_claude_hook(s, CMD, backup_root=tmp_path / "b", stamp="T2") is False
    data = json.loads(s.read_text("utf-8"))
    cmds = [h["command"] for e in data["hooks"]["SessionStart"] for h in e["hooks"]]
    assert cmds.count(CMD) == 1


def test_creates_hooks_key_when_absent(tmp_path):
    s = tmp_path / "settings.json"
    _write(s, {"model": "opus"})
    install_claude_hook(s, CMD, backup_root=tmp_path / "b", stamp="T1")
    data = json.loads(s.read_text("utf-8"))
    assert data["hooks"]["SessionStart"][0]["hooks"][0]["command"] == CMD


def test_backup_written(tmp_path):
    s = tmp_path / "settings.json"
    _write(s, {"hooks": {"SessionStart": []}})
    install_claude_hook(s, CMD, backup_root=tmp_path / "b", stamp="T1")
    assert (tmp_path / "b" / "settings" / "T1" / "settings.json").exists()


def test_parse_error_aborts_without_write(tmp_path):
    s = tmp_path / "settings.json"
    s.write_text("{not json", encoding="utf-8")
    with pytest.raises(HookInstallError):
        install_claude_hook(s, CMD, backup_root=tmp_path / "b", stamp="T1")
    assert s.read_text("utf-8") == "{not json"


def test_claude_hook_bad_shapes_abort_without_write(tmp_path):
    cases = [
        {"hooks": "bad"},
        {"hooks": {"SessionStart": {}}},
        {"hooks": {"SessionStart": ["bad"]}},
        {"hooks": {"SessionStart": [{"hooks": {}}]}},
        {"hooks": {"SessionStart": [{"hooks": ["bad"]}]}},
    ]
    for idx, obj in enumerate(cases):
        s = tmp_path / f"settings-{idx}.json"
        _write(s, obj)
        before = s.read_text("utf-8")
        with pytest.raises(HookInstallError):
            install_claude_hook(s, CMD, backup_root=tmp_path / "b", stamp=f"T{idx}")
        assert s.read_text("utf-8") == before


def test_codex_hook_bad_shapes_abort_without_write(tmp_path):
    cases = [
        'hooks = "bad"\n',
        '[hooks]\nSessionStart = "bad"\n',
        '[hooks]\nSessionStart = ["bad"]\n',
        '[[hooks.SessionStart]]\nhooks = "bad"\n',
        '[[hooks.SessionStart]]\nhooks = ["bad"]\n',
    ]
    for idx, text in enumerate(cases):
        p = tmp_path / f"config-{idx}.toml"
        p.write_text(text, encoding="utf-8")
        with pytest.raises(HookInstallError):
            install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp=f"T{idx}")
        assert p.read_text("utf-8") == text


SENSE_CMD = "agent-config-sync sense"


def test_claude_hook_replaces_superseded_command(tmp_path):
    p = tmp_path / "settings.json"
    assert install_claude_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1") is True
    data = json.loads(p.read_text("utf-8"))
    data["hooks"]["SessionStart"].append(
        {"hooks": [{"type": "command", "command": "unrelated-tool doit"}]}
    )
    p.write_text(json.dumps(data), encoding="utf-8")
    added = install_claude_hook(
        p, SENSE_CMD, backup_root=tmp_path / "b", stamp="T2",
        replace_commands=(CMD,),
    )
    assert added is True
    data = json.loads(p.read_text("utf-8"))
    cmds = [
        h["command"]
        for e in data["hooks"]["SessionStart"]
        for h in e["hooks"]
    ]
    assert SENSE_CMD in cmds
    assert CMD not in cmds
    assert "unrelated-tool doit" in cmds  # unrelated entry preserved


def test_claude_hook_replace_is_idempotent(tmp_path):
    p = tmp_path / "settings.json"
    install_claude_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1")
    install_claude_hook(
        p, SENSE_CMD, backup_root=tmp_path / "b", stamp="T2", replace_commands=(CMD,)
    )
    assert install_claude_hook(
        p, SENSE_CMD, backup_root=tmp_path / "b", stamp="T3", replace_commands=(CMD,)
    ) is False


def test_codex_hook_replaces_exact_superseded_block(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(CODEX_TOML, encoding="utf-8")
    install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1")
    added = install_codex_hook(
        p, SENSE_CMD, backup_root=tmp_path / "b", stamp="T2", replace_commands=(CMD,)
    )
    assert added is True
    cmds = _codex_cmds(p)
    assert SENSE_CMD in cmds
    assert CMD not in cmds
    data = tomllib.loads(p.read_text("utf-8"))
    assert data["model"] == "gpt-5.5"  # unrelated keys preserved


def test_codex_hook_leaves_operator_edited_block_in_place(tmp_path):
    # should-fail path for removal: an edited block no longer matches what we
    # wrote, so it is preserved and the new hook is appended alongside it
    p = tmp_path / "config.toml"
    p.write_text(CODEX_TOML, encoding="utf-8")
    install_codex_hook(p, CMD, backup_root=tmp_path / "b", stamp="T1")
    text = p.read_text("utf-8").replace("timeout = 30", "timeout = 45")
    p.write_text(text, encoding="utf-8")
    added = install_codex_hook(
        p, SENSE_CMD, backup_root=tmp_path / "b", stamp="T2", replace_commands=(CMD,)
    )
    assert added is True
    cmds = _codex_cmds(p)
    assert SENSE_CMD in cmds
    assert CMD in cmds  # edited block untouched
