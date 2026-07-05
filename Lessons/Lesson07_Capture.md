# 🎓 Lesson 07: The Intake Window — capture.py, Untrusted Input → Source

## 🛡️ Welcome Back, Security Analyst!

The most dangerous door in any system is the one that lets *outside content in*. 🔍
Today: **`capture.py`** — "add this rule / skill" from a chat. It writes into the
source of truth, which fans out to three agents — so it is the highest-risk ingress,
and it is deliberately gated: dry-run by default, binding lints, a visible diff, and a
human `--confirm`.

---

## 🎯 Learning Objectives
- Trace `capture_standard` and `capture_skill`
- Explain why the lints run **before any write, even in dry-run**
- Explain the dry-run → diff → confirm → project flow
- Articulate why the AI's review is advisory, never the tool's gate

**Time estimate:** 20 min | **Prerequisites:** Lessons 03, 05, 06

---

## 🧠 What This Does — Plain English

`capture` routes a proposed change: a *standard* to `_shared/core.md` (shared) or an
overlay (vendor), or a *skill* to `skills/<name>`. By default it's a **dry-run** — it
runs the deterministic lints, builds a diff, and writes nothing. Add `--confirm` and it
applies to the source and projects to every runtime. A secret (or a non-neutral skill)
aborts *before* anything is written, even in dry-run.

**Real-world analogy:** a secure intake/reception window. Visitors are screened
(lints), you see exactly who's entering (diff), and a human badges them in (confirm)
before they reach the building (the three agents).

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
This is a SOAR intake with mandatory enrichment + human approval before action. Untrusted
input is screened by deterministic rules; an analyst sees the normalized case (the diff)
and approves before the playbook executes (project). Dry-run-by-default = "investigate
before you act."
**SOC parallel:** a SOAR playbook that screens and previews an artifact, then waits for analyst approval before taking a consequential action.

### 🟡 Engineer Lens
The tool owns only the *deterministic* half: routing, lints, diff (via `difflib`), and a
hard `confirm` boolean. The "AI advisory review" lives in the chat agent, not the tool —
keeping `capture` pure-Python and unit-testable. Lints run before the write branch, so
dry-run and confirm share the exact same gate.
**Engineering decision to own:** putting the binding gate before the `if confirm:` branch — the security check can't be skipped by the dry-run path.

### 🔴 AI Security Engineer Lens
This is the indirect-prompt-injection front door with a 3× blast radius. Controls:
dry-run default (no accidental writes), deterministic lints (secret/neutral) that
attacker text can't talk past, a visible diff, and a human `--confirm`. The AI may
propose routing or opine on safety, but a probabilistic model — manipulable by the very
text it reviews — never authorizes the write.
**AI security surface:** untrusted-content ingestion into agent prompts; mitigated by deterministic gates + human-in-the-loop, never by AI judgment.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/capture.py
def capture_standard(config, target, text, *, confirm=False):
    secrets = find_secrets(text)
    if secrets:
        raise SecretFoundError(target, secrets)      # binding gate, BEFORE any write
    path = _standard_path(config, target)            # 'core' or a runtime overlay
    before = path.read_text("utf-8") if path.exists() else ""
    after = before + sep + text.strip("\n") + "\n"
    diff = _unified(before, after, path)
    if confirm:
        atomic_write(path, after)                    # only now do we write
    return CaptureResult("standard", target, diff, confirm)
```

| Element | Why |
|---------|-----|
| lint before `if confirm` | dry-run and confirm share the gate; a secret can't sneak through dry-run |
| `_unified` diff | the human sees exactly what changes before approving |
| `confirm` boolean | the binding human gate; CLI requires `--confirm` |

The CLI handler prints the diff; without `--confirm` it stops at "DRY-RUN"; with it,
applies then runs `project` + `project_skills` to fan out, and prints a `git commit` hint.

> ⚠️ **Common pitfall:** assuming the chat AI's "looks safe" advances the write. It
> doesn't — only a human passing `--confirm` does. The AI verdict is decoration.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Capture tests
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_capture.py -q
```
✅ **Success if:** green — incl. dry-run-writes-nothing and secret-aborts-before-write.

### 🔬 Exercise 2: Dry-run shows a diff, writes nothing
```bash
printf '## Always log auth events\n' > /tmp/rule.md
agent-config-sync capture standard --target core --text-file /tmp/rule.md
```
📊 **Expected:** a unified diff, then "DRY-RUN — nothing written…". `core.md` unchanged.
✅ **Success if:** no change to `_shared/core.md`.

### 🔬 Exercise 3: Secret blocked before write (intentional failure)
```bash
printf 'token = "abcd1234efgh5678"\n' > /tmp/leak.md
agent-config-sync capture standard --target core --text-file /tmp/leak.md --confirm; echo "exit=$?"
```
📊 **Expected:** `Aborted: secret-like content in 'core'. Nothing written.` `exit=3`.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** Why run the secret lint before the dry-run/confirm branch instead of only on confirm?
**A:** So the gate is unconditional — dry-run and apply share the exact same check, and a secret aborts before any code path could write. It also means the preview a human reviews is already known-clean of the deterministic failures, so confirmation is about *content judgment*, not re-checking for secrets.
*Why it works:* shows the gate is structurally unskippable, not just present.

### 🔴 AI Security Engineering
**Q:** This feature ingests possibly-attacker-authored text into three agents' prompts. Defend the design.
**A:** Defense in depth: dry-run by default (no accidental propagation), deterministic lints that untrusted text can't manipulate, a visible diff, and a binding human `--confirm`. The AI's role is advisory only — never authorizing — because a model reviewing attacker content is itself an injection target. The blast radius (3 agents) is exactly why the human gate is mandatory, not optional.
*Why it works:* names the injection-of-the-reviewer risk and the layered human-in-the-loop control.

---

## ✅ Key Takeaways
- Capture is the highest-risk ingress; gated accordingly
- Dry-run by default; lints bind before any write; human `--confirm` applies
- Tool owns deterministic half; AI review lives in chat, advisory only
- On confirm: write source → project to all runtimes → git-commit hint

## 📋 Quick Reference
| Item | Value |
|------|-------|
| File | `src/agent_config_sync/capture.py` |
| Entries | `capture_standard(config, target, text, *, confirm)`, `capture_skill(config, name, body, *, confirm)` |
| CLI | `capture {standard\|skill} … [--confirm]` (dry-run default) |
| Errors | `SecretFoundError`/`NeutralLanguageError` (exit 3), `ValueError` (exit 2) |
| Test | `tests/test_capture.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** dry-run default + human confirm; deterministic gates bind.
- **Rejected:** auto-apply or AI-gated apply — both unsafe for a 3-agent fan-out.
- **Trade-off:** confirm step gains injection resistance; costs one extra deliberate action.

## 🚀 Next: Lesson 08 — reverse promote & 3-way conflicts (`promote.py`).
*Remember: screen at the window, show the badge, and let a human open the door.* 🛡️
