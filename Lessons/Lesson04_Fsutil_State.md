# 🎓 Lesson 04: The Notary & the Ledger — fsutil.py & state.py

## 🛡️ Welcome Back, Security Analyst!

How do you change a file *without* risking a half-written, corrupt result — and how
do you remember what you wrote so you can detect tampering later? 🔍 Today:
**`fsutil.py`** (atomic writes, backups, hashing) and **`state.py`** (the
`.sync-state.json` ledger that powers drift detection).

---

## 🎯 Learning Objectives
- Explain **atomic write** (temp + `os.replace`) and why it prevents corruption
- Describe the backup-before-overwrite discipline
- Explain how `sha256` + `.sync-state.json` enable drift classification
- Connect this to forensic reconstruction

**Time estimate:** 18 min | **Prerequisites:** Lesson 00

---

## 🧠 What This Does — Plain English

`atomic_write` writes to a temporary file then atomically renames it over the target,
so a crash mid-write never leaves a partial file. `backup` copies the existing file
into `.backups/<runtime>/<timestamp>/` before any overwrite. `sha256_text` hashes
content. `state.py` stores those hashes in `.sync-state.json` — the record of *what
the tool last wrote* to each target, which is how it later tells "I wrote this" from
"a human edited this."

**Real-world analogy:** a notary (atomic, all-or-nothing stamping) plus a ledger
(the hash record) plus a filing cabinet of carbon copies (backups) for recovery.

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
`.sync-audit.log` + `.sync-state.json` + `.backups/` are your evidence trail: who/what/
when was written, the integrity hash, and a recoverable prior version. This is exactly
the artifact set an IR analyst wants — change record, integrity baseline, rollback.
**SOC parallel:** the hash ledger is a file-integrity-monitoring (FIM) baseline; backups are your restore point.

### 🟡 Engineer Lens
`atomic_write` = `tmp.write_text` then `os.replace(tmp, path)` — `os.replace` is atomic
on a single filesystem. Backups use a UTC timestamp folder so concurrent runtimes don't
collide. State is plain JSON, sorted keys, written deterministically.
**Engineering decision to own:** temp-then-rename is the standard crash-safe write; explain why writing in place is unsafe (a crash leaves a truncated file).

### 🔴 AI Security Engineer Lens
The hash ledger is an **integrity baseline for agent instructions**: if the on-disk
prompt no longer matches the hash the tool recorded, something changed it out of band —
a tamper signal for content that steers an autonomous agent. Backups give you a known-good
state to restore after a poisoning incident.
**AI security surface:** tamper-evidence + rollback for prompt/skill files (detect & recover from an unauthorized change to what an agent reads).

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/fsutil.py
def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)                  # atomic swap

def backup(path: Path, backup_root: Path, runtime: str, stamp: str) -> Path | None:
    if not path.exists():
        return None
    dest = backup_root / runtime / stamp / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)               # preserves mtime
    return dest

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

```python
# src/agent_config_sync/state.py
def save_state(repo_root, state):
    path = repo_root / ".sync-state.json"
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
```

| Piece | Why designed this way |
|-------|------------------------|
| temp + `os.replace` | Crash-safe: target is either old or new, never half |
| backup before overwrite | `~/.codex` / `~/.gemini` aren't git repos — this is their undo |
| `sort_keys=True` | Deterministic state file (stable diffs) |

> ⚠️ **Common pitfall:** on Windows, text-mode writes emit CRLF; `read_text` and git both
> normalize to LF, so comparisons stay correct — but the on-disk bytes differ. The tool
> compares normalized text, which is why drift detection still works.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: fsutil + state tests
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_fsutil.py tests/test_state.py -q
```
✅ **Success if:** green.

### 🔬 Exercise 2: See a backup get made
```bash
agent-config-sync project        # writes (and backs up if pre-existing)
ls .backups/*/ 2>/dev/null | head
```
📊 **Expected:** timestamped backup folders per runtime (after a real projection over existing files).
✅ **Success if:** you see `<runtime>/<timestamp>/` entries.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** Walk me through why temp-file + rename is safer than writing in place.
**A:** `os.replace` is atomic on one filesystem: at any instant the target is either the complete old file or the complete new one — never a partially written file. Writing in place risks a crash leaving a truncated/corrupt file (here, a broken agent instruction). We also persist state *inside* the write loop so a mid-run failure can't leave a written file unrecorded and get misclassified as drift next run.
*Why it works:* shows failure-mode reasoning and awareness of partial-write corruption.

### 🔴 AI Security Engineering
**Q:** How would you detect that an agent's instruction file was tampered with?
**A:** Keep a recorded hash of what you last wrote (`.sync-state.json`). On the next check, re-hash the on-disk file: a mismatch that doesn't equal the freshly rendered projection means out-of-band modification. Pair it with timestamped backups for rollback. That's file-integrity monitoring applied to prompt content.
*Why it works:* maps a classic FIM control onto the AI supply chain.

---

## ✅ Key Takeaways
- Atomic write = temp + `os.replace`; never a half-written agent prompt
- Backup before every overwrite (the non-git runtimes' undo)
- `sha256` in `.sync-state.json` is the integrity baseline / drift oracle
- State saved inside the loop so recorded hashes never lag disk

## 📋 Quick Reference
| Item | Value |
|------|-------|
| Files | `src/agent_config_sync/fsutil.py`, `state.py` |
| Entry points | `atomic_write`, `backup`, `sha256_text`, `default_stamp`; `load_state`/`save_state` |
| Artifacts | `.sync-state.json` (hashes), `.backups/<rt>/<stamp>/` |
| Tests | `tests/test_fsutil.py`, `tests/test_state.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** hash ledger drives drift; backups for recovery.
- **Rejected:** relying on git alone — `~/.codex`/`~/.gemini` aren't repos.
- **Trade-off:** `.backups/` gains recoverability; costs disk (prune manually — LIMITATIONS).

## 🚀 Next: Lesson 05 — forward projection & the drift guard (`project.py`).
*Remember: write all-or-nothing, keep the receipt, and always leave a carbon copy.* 🛡️
