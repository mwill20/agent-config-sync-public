# 🎓 Lesson 09: The One Exception — settingsedit.py & install-hooks

## 🛡️ Welcome Back, Security Analyst!

Every rule has exactly one documented exception here — and it's the riskiest write in
the tool. 🔍 Today: **`settingsedit.py`** and the **`install-hooks`** command, which
write `~/.claude/settings.json` (a file that runs commands at startup) to add an
automatic drift check. This is the *only* write outside the `targets.yaml` allowlist.

---

## 🎯 Learning Objectives
- Explain why writing `settings.json` is a distinct trust boundary
- Trace `install_claude_hook`: parse → idempotency → backup → atomic merge
- Explain the cross-platform Gemini propagation (`cmd /c`, `cwd=$HOME`)
- Connect this to its STRIDE threat model

**Time estimate:** 20 min | **Prerequisites:** Lessons 02, 04

---

## 🧠 What This Does — Plain English

`install-hooks` appends one `SessionStart` hook — `agent-config-sync sense` since V2 (previously `check`; superseded entries are replaced on exact match) — to
`~/.claude/settings.json` so every Claude session auto-checks sync. It **merges**: it
parses the full JSON, adds only to `hooks.SessionStart`, preserves every other key and
existing hook, backs up first, and is idempotent (running twice adds it once). Then it
runs `gemini hooks migrate --from-claude` to propagate the hook to Gemini, and appends a
`[[hooks.SessionStart]]` block to `~/.codex/config.toml` for Codex (its `codex_hooks`
feature is config-driven, no CLI). All three runtimes get the same `agent-config-sync
check` at session start.

**Real-world analogy:** editing one firewall rule in a shared policy file by hand. You
parse the whole policy, change exactly one entry, keep a backup, and never blindly
overwrite the file — because everything else in it matters.

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
A startup hook that runs a command on every session is, in EDR terms, a persistence
mechanism — the same shape attackers abuse (Run keys, scheduled tasks). That's why this
write is special-cased, fixed-command, idempotent, and backed up: legitimate persistence
done with the discipline you'd demand when auditing a suspicious one.
**SOC parallel:** reviewing a new autostart/persistence entry — you verify it's a known, fixed command and that nothing else in the config was tampered.

### 🟡 Engineer Lens
`install_claude_hook` parses JSON and mutates only `hooks.SessionStart` (key-addressed,
never string-splice); aborts on a parse error before any write; backs up; writes atomically.
Idempotency is an exact command-string match. The Gemini call uses `cmd /c <path> …` with
**list args** (no `shell=True`) to run the `.cmd` shim safely, and `cwd=$HOME` so `migrate`
reads the *global* `~/.claude/settings.json` (from a project dir it would read a local one).
**Engineering decision to own:** parsed, key-addressed merge + the two Windows fixes (`.cmd` via `cmd /c` list-args; `cwd` for global discovery) — both found by a live run, not unit tests.

### 🔴 AI Security Engineer Lens
This file controls code that runs at agent startup. A careless overwrite could drop
`enabledPlugins`/`permissions` (disabling security controls) or inject an arbitrary
startup command (code execution every session). Mitigations: fixed literal command (never
from input), append-only to one key, parse-or-abort, backup, idempotent — all mapped in
`docs/threat-models/2026-06-28-settings-write-surface.md`.
**AI security surface:** the startup-persistence write — the one place the tool can affect agent execution, hardened and threat-modeled accordingly.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/settingsedit.py
def install_claude_hook(settings_path, command, *, backup_root, stamp) -> bool:
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            raise HookInstallError(f"settings.json is not valid JSON: {exc}") from exc
    else:
        data = {}
    hooks = data.setdefault("hooks", {})
    sessionstart = hooks.setdefault("SessionStart", [])
    existing = [h.get("command") for e in sessionstart for h in e.get("hooks", [])]
    if command in existing:
        return False                          # idempotent: already there
    # backup, then append only our entry, then atomic write
    ...
    sessionstart.append({"hooks": [{"type": "command", "command": command}]})
```

| Control | Threat addressed |
|---------|------------------|
| parse full JSON, mutate one key | clobbering `permissions`/`enabledPlugins`/other hooks |
| fixed literal command | injected/attacker-chosen startup command |
| idempotent (exact match) | duplicate/stacked hooks |
| parse-or-abort + backup | corrupt file / unrecoverable overwrite |

> ⚠️ **Common pitfall (real, found live):** `subprocess.run(["gemini", …])` fails on
> Windows (`gemini` is a `.cmd`). Fix: `["cmd", "/c", gemini, …]` (list args, no
> `shell=True`). And run with `cwd=$HOME` or `migrate` reads a project-local settings file.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Writer tests (merge / idempotent / backup / parse-abort)
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_settingsedit.py -q
```
✅ **Success if:** green — incl. "append without clobbering" and "parse error aborts without write".

### 🔬 Exercise 2: Idempotency live
```bash
agent-config-sync install-hooks
agent-config-sync install-hooks     # second run
```
📊 **Expected:** second run says "Claude hook already present." (no duplicate).
✅ **Success if:** only one `agent-config-sync sense` entry exists (the V2 command; older docs said `check`):
```bash
python -c "import json,os;d=json.load(open(os.path.expanduser('~/.claude/settings.json')));print(sum(h['command']=='agent-config-sync check' for e in d['hooks']['SessionStart'] for h in e['hooks']))"
```
(expect `1`).

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** You must add one entry to a shared JSON config without damaging it. How?
**A:** Parse the whole file to an object, mutate only the target key (`hooks.SessionStart`), and serialize back — never string-splice. Guard with: abort if it doesn't parse (don't overwrite a file you can't read), back up before writing, write atomically, and make it idempotent via an exact-match check so re-runs don't stack entries. Every other key is preserved untouched.
*Why it works:* the canonical safe config-merge recipe, with failure handling.

### 🔴 AI Security Engineering
**Q:** A startup hook is persistence. Why is this acceptable here and how is it bounded?
**A:** It's owner-invoked, installs a *fixed* command (`agent-config-sync sense`, never derived from input), touches only one key append-only, backs up, and is threat-modeled (STRIDE) with each threat mapped to `settingsedit.install_claude_hook`. The residual — the command runs at every startup with user privileges — is the same trust you place in any installed console script, and it's documented. Bounded persistence done with audit-grade discipline.
*Why it works:* treats the feature as the persistence mechanism it is and shows the controls + honest residual.

---

## ✅ Key Takeaways
- The one allowlist exception: writing `~/.claude/settings.json`
- Parsed, key-addressed, append-only merge — preserves everything else
- Idempotent, backed up, parse-or-abort; fixed command (no injection surface)
- Gemini via `cmd /c` list-args + `cwd=$HOME`; Codex via a merge-safe `config.toml` writer (`tomllib` parse/validate, append-only) — Windows quirks found by live testing

## 📋 Quick Reference
| Item | Value |
|------|-------|
| Files | `src/agent_config_sync/settingsedit.py`, `hooks/sessionstart-check` |
| Entry | `install_claude_hook(settings_path, command, *, backup_root, stamp) -> bool` |
| CLI | `install-hooks [--claude-settings <path>]` |
| Error | `HookInstallError` (exit 3) |
| Threat model | `docs/threat-models/2026-06-28-settings-write-surface.md` |
| Test | `tests/test_settingsedit.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** one narrow, owner-approved settings.json write for the startup check.
- **Rejected:** broad settings sync (parent spec non-goal) — too much blast radius.
- **Trade-off:** auto startup check gains deterministic drift detection; costs one documented allowlist exception (threat-modeled).

## 🚀 Next: Lesson 10 — the CLI surface & `doctor` (`cli.py`, `doctor.py`).
*Remember: the one exception to a security rule must be the most carefully guarded code you write.* 🛡️
