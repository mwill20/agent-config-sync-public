# agent-config-sync — Plan 2 / Slice B (part 2 / "B3"): Startup-hook installation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** BUILT. ⚠️ **CORRECTION (2026-06-29):** this plan's premise that "Codex has
no hook mechanism" was **WRONG**. `codex_hooks` is a stable, default-on feature,
config-driven via `[[hooks.SessionStart]]` in `~/.codex/config.toml`. The shipped
`install-hooks` wires **all three** runtimes (Claude `settings.json`, Gemini via
`migrate`, Codex `config.toml`) — see `settingsedit.install_codex_hook`, the updated
threat model, and HANDOFF §8. The Codex-as-instructed-fallback text below is superseded.

**Goal:** Give every runtime an automatic, deterministic startup drift check — by installing a `SessionStart` hook into Claude (`~/.claude/settings.json`, merge-safe), propagating it to Gemini via `gemini hooks migrate --from-claude`, and printing an instructed fallback for Codex (which has no hook mechanism).

**Architecture:** A new, narrowly-scoped writer (`settingsedit.py`) performs an idempotent read-modify-write of `~/.claude/settings.json` that appends ONE `SessionStart` command hook and never touches any other key or existing hook. A new CLI command `install-hooks` orchestrates: Claude (writer) → Gemini (`migrate` shell-out) → Codex (printed instructions). This is the project's **first write outside the `targets.yaml` allowlist** — a deliberate, owner-approved exception, kept separate from the generic `project()` path on purpose.

**Tech Stack:** Python 3.11+, stdlib (`json`, `subprocess`, `shutil`, `pathlib`); reuses `fsutil.backup`/`default_stamp`. No new deps.

## Global Constraints

- Python floor **3.11**; deps pinned; no new deps.
- Test command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`.
- **Idempotent:** running `install-hooks` twice adds the hook once. Detection is by exact command-string match against existing `SessionStart` entries.
- **Non-destructive merge:** load the FULL settings JSON, mutate ONLY `hooks.SessionStart`, preserve every other key and every existing hook (the live file already has a `skill_compass.py` SessionStart hook + a `Stop` hook — both must survive).
- **Backup first:** copy `settings.json` to `.backups/settings/<stamp>/settings.json` before writing; atomic write.
- **Injectable paths:** `install_claude_hook(settings_path, …)` takes the path as a parameter so tests are hermetic; the CLI resolves the real `~/.claude/settings.json`.
- **No secrets, no traceback:** wrap failures; a missing/oversized/parse-failing settings file produces a one-line message + non-zero exit, never a stack trace (reuse the F1 pattern).

## Verified runtime facts (on-machine 2026-06-28 — do NOT re-derive)

- **Claude `settings.json` SessionStart schema:**
  ```json
  "hooks": { "SessionStart": [ { "hooks": [ { "type": "command", "command": "<cmd>" } ] } ] }
  ```
  Live file already contains a `SessionStart` (`python …/skill_compass.py`) and a `Stop` hook → **merge, never overwrite**.
- **Gemini:** only `gemini hooks migrate --from-claude` exists (no `list`/`add`). It converts Claude Code hooks into `~/.gemini/settings.json`. Use it; do not hand-write Gemini's schema. **Verify at build time** that after `migrate`, the hook is present (inspect `~/.gemini/settings.json`).
- **Codex:** no `hooks`/`skills` subcommand → instructed fallback only.
- **Hook command:** `agent-config-sync check` works with no env (the editable install resolves the repo via `_repo_root()` = `parents[2]` of `cli.py`). A thin wrapper (`hooks/sessionstart-check`) gives a friendlier message for non-devs.

## Trust boundary (security — read before building)

Writing `~/.claude/settings.json` is the FIRST write outside the `config/targets.yaml`
allowlist. `settings.json` holds `enabledPlugins`, `permissions`, and existing hooks —
corrupting it could disable security controls or execute an attacker-chosen command at
every session start. Controls for this plan:

1. **Append-only to `hooks.SessionStart`**, by key, via parsed JSON — never string-splice.
2. **Idempotent** (exact command match) so repeated runs can't stack duplicates.
3. **Backup + atomic write**; on any parse error, abort without writing.
4. **The command we install is fixed** (`agent-config-sync check` / the wrapper) — never
   derived from untrusted input.
5. **`docs/threat-models/` entry** (Task 4) before this is considered hardened.

---

## File Structure

```
src/agent_config_sync/settingsedit.py   CREATE: install_claude_hook(), HookInstallError
src/agent_config_sync/cli.py             MODIFY: add `install-hooks` command
hooks/sessionstart-check                 CREATE: wrapper that runs `agent-config-sync check`
tests/test_settingsedit.py               CREATE: merge/idempotency/backup/preserve tests
tests/test_cli.py                        MODIFY: install-hooks Claude path (hermetic)
docs/threat-models/2026-06-28-settings-write-surface.md   CREATE
README.md / AGENTS.md / docs/LIMITATIONS.md / HANDOFF.md  MODIFY
```

---

### Task 1: `settingsedit.py` — merge-safe Claude hook writer

**Files:**
- Create: `src/agent_config_sync/settingsedit.py`
- Test: `tests/test_settingsedit.py`

**Interfaces:**
- Produces: `install_claude_hook(settings_path: Path, command: str, *, backup_root: Path, stamp: str) -> bool` — returns `True` if the hook was added, `False` if an identical command was already present. Raises `HookInstallError` on parse failure.
- Produces: `class HookInstallError(Exception)`.

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path

import pytest

from agent_config_sync.settingsedit import HookInstallError, install_claude_hook

CMD = "agent-config-sync check"


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
    assert "python existing.py" in cmds and CMD in cmds      # existing preserved + ours added
    assert data["hooks"]["Stop"][0]["hooks"][0]["command"] == "python stop.py"  # untouched
    assert data["model"] == "opus"                            # other keys untouched


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
    assert s.read_text("utf-8") == "{not json"  # unchanged
```

- [ ] **Step 2: Run to verify it fails** — `… pytest tests/test_settingsedit.py -q` → ModuleNotFound.

- [ ] **Step 3: Implement `settingsedit.py`**

```python
import json
import shutil
from pathlib import Path


class HookInstallError(Exception):
    pass


def install_claude_hook(
    settings_path: Path, command: str, *, backup_root: Path, stamp: str
) -> bool:
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            raise HookInstallError(f"settings.json is not valid JSON: {exc}") from exc
    else:
        data = {}
    if not isinstance(data, dict):
        raise HookInstallError("settings.json top level is not an object")

    hooks = data.setdefault("hooks", {})
    sessionstart = hooks.setdefault("SessionStart", [])
    existing = [
        h.get("command")
        for entry in sessionstart
        for h in entry.get("hooks", [])
    ]
    if command in existing:
        return False

    # Back up before the first real write.
    if settings_path.exists():
        dest = backup_root / "settings" / stamp / settings_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(settings_path, dest)

    sessionstart.append({"hooks": [{"type": "command", "command": command}]})
    tmp = settings_path.with_name(settings_path.name + ".tmp")
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    import os
    os.replace(tmp, settings_path)
    return True
```

- [ ] **Step 4: Run to verify it passes** — all 5 tests green.

- [ ] **Step 5: Commit** — `git commit -m "feat(hooks): merge-safe idempotent Claude settings.json hook writer"`

---

### Task 2: `sessionstart-check` wrapper

**Files:**
- Create: `hooks/sessionstart-check`
- Test: covered by manual/live verification (a 3-line shell wrapper; no unit logic).

- [ ] **Step 1: Create `hooks/sessionstart-check`**

```sh
#!/bin/sh
# Startup drift check for agent-config-sync. Surfaces drift; never blocks the session.
agent-config-sync check || echo "⚠️  AI config drifted — run 'agent-config-sync project' (or use the config-sync skill)."
```

- [ ] **Step 2: Commit** — `git commit -m "feat(hooks): sessionstart-check wrapper"`

---

### Task 3: CLI `install-hooks` command

**Files:**
- Modify: `src/agent_config_sync/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `install_claude_hook`, `HookInstallError`.
- Produces: `agent-config-sync install-hooks [--claude-settings <path>]` — installs the Claude hook (default path `~/.claude/settings.json`, overridable for tests), runs `gemini hooks migrate --from-claude` if `gemini` is on PATH, and prints Codex instructions. Exit `0` on success, `3` on `HookInstallError`.

- [ ] **Step 1: Write the failing test** (hermetic — point at a temp settings file)

```python
import json


def test_cli_install_hooks_claude(monkeypatch, fake_env, tmp_path):
    _env(monkeypatch, fake_env)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), "utf-8")
    rc = main(["install-hooks", "--claude-settings", str(settings)])
    assert rc == 0
    data = json.loads(settings.read_text("utf-8"))
    cmds = [h["command"] for e in data["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("check" in c for c in cmds)
```

- [ ] **Step 2: Run to verify it fails** — unknown command `install-hooks`.

- [ ] **Step 3: Implement the command** in `cli.py`

Add an `install-hooks` subparser with `--claude-settings` (default `None` → resolve `Path.home()/".claude"/"settings.json"`). Handler:
```python
if args.cmd == "install-hooks":
    from .settingsedit import HookInstallError, install_claude_hook
    settings = Path(args.claude_settings) if args.claude_settings else Path.home() / ".claude" / "settings.json"
    cmd = "agent-config-sync check"
    try:
        added = install_claude_hook(
            settings, cmd, backup_root=config.repo_root / ".backups", stamp=default_stamp()
        )
    except HookInstallError as exc:
        print(f"Hook install failed: {exc}. No changes written.")
        return 3
    print(f"Claude hook {'installed' if added else 'already present'}.")
    # Gemini: convert the Claude hook into Gemini's own format.
    import shutil as _sh
    if _sh.which("gemini"):
        import subprocess
        subprocess.run(["gemini", "hooks", "migrate", "--from-claude"], check=False)
        print("Ran `gemini hooks migrate --from-claude`.")
    else:
        print("Gemini CLI not found — skipped; run `gemini hooks migrate --from-claude` later.")
    print("Codex has no hook mechanism — its discovery section + the config-sync "
          "skill cover startup; run `agent-config-sync check` manually there.")
    return 0
```
(Import `default_stamp` from `.fsutil` at the top with the other imports.)

- [ ] **Step 4: Run to verify it passes** — full suite green.

- [ ] **Step 5: Commit** — `git commit -m "feat(cli): install-hooks (Claude merge + gemini migrate + codex fallback)"`

---

### Task 4: Threat model + docs

**Files:**
- Create: `docs/threat-models/2026-06-28-settings-write-surface.md`
- Modify: `README.md`, `AGENTS.md`, `docs/LIMITATIONS.md`, `HANDOFF.md`, `docs/EVALUATION.md`

- [ ] **Step 1: Threat model** — assets (`settings.json`: plugins/permissions/hooks), trust boundary (first write outside allowlist), threats (T1 clobbered security keys → mitigated by parsed append-only; T2 duplicate/poisoned hook → idempotent + fixed command; T3 corrupt file → backup + abort-on-parse-error), residual risk, `file:function` pointers (`settingsedit.install_claude_hook`).
- [ ] **Step 2: Docs** — README: document `install-hooks`; AGENTS: note settings.json is written only by `install-hooks`, append-only; LIMITATIONS: Gemini hook relies on `gemini hooks migrate`, Codex manual; HANDOFF: mark B3 done; EVALUATION: add suite count + the live `install-hooks` verification (inspect `~/.claude/settings.json` shows both hooks; `~/.gemini/settings.json` shows the migrated hook).
- [ ] **Step 3: Commit** — `git commit -m "docs(hooks): settings-write threat model + B3 docs"`

- [ ] **Step 4 (owner-run apply):** `agent-config-sync install-hooks`, then confirm `~/.claude/settings.json` still has `skill_compass` + the new check hook, and `gemini hooks migrate` registered it in `~/.gemini/settings.json`.

---

## Self-Review

**Spec coverage (Plan 2 §5.3 startup hook + D2-5):** Claude SessionStart (Task 1+3), Gemini via migrate (Task 3), Codex instructed fallback (Task 3) — all covered. Wrapper for friendly non-dev message (Task 2). Threat model for the new write surface (Task 4).

**Placeholder scan:** none — full code for the writer and tests; the CLI handler is shown in full; threat-model contents enumerated.

**Type consistency:** `install_claude_hook(settings_path, command, *, backup_root, stamp) -> bool` and `HookInstallError` are used identically in Tasks 1 and 3. `default_stamp` from `fsutil` (existing).

**Security note:** this is the one allowlist exception in the project; it is append-only, idempotent, backed up, parse-guarded, and threat-modeled. It does not route through `project()` and does not widen the `targets.yaml` allowlist.

**Out of scope:** `doctor` health command (Plan 2 §5.5); Slice C capture; Plan 3 promote.
```

