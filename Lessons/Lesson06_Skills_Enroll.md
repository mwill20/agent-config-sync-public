# 🎓 Lesson 06: The Universal Adapter — skills.py & enroll.py

## 🛡️ Welcome Back, Security Analyst!

How do you ship *one* skill to three assistants that each speak a different tool
language? 🔍 Today: **`skills.py`** (project a managed skill to every runtime as a
directory tree) and **`enroll.py`** (bring a skill under management, gated). This is
Lesson 05's projection generalized from one file to a *set* of files.

---

## 🎯 Learning Objectives
- Explain how a skill projects as `SKILL.md` + the runtime's tool adapter
- Trace `project_skills` and its per-file drift state
- Explain enrollment: reconcile → neutral-lint → write source → update allowlist
- Explain the comment-safe `managed_skills` rewrite and its guard
- State why enrollment is not a recursive copy of a live runtime skill directory

**Time estimate:** 22 min | **Prerequisites:** Lessons 03, 05

---

## 🧠 What This Does — Plain English

A managed skill has one neutral body in `skills/<name>/SKILL.md`. `project_skills`
copies that body into every runtime *plus* that runtime's `references/<vendor>-tools.md`
adapter — so each assistant resolves the neutral actions ("dispatch a subagent") to its
own real tools. `enroll` is how a skill becomes managed: read its variants across
runtimes, reconcile to one canonical body, require it to pass the neutral-language and
secret lints, write it to source, and add its name to `managed_skills`.

The managed payload is deliberately narrow: `SKILL.md` plus one runtime adapter.
Scripts, templates, virtual environments, browser profiles, caches, and other
runtime-local files are not recursively copied. That boundary prevents an
apparently simple skill import from becoming a session-data or executable
dependency import.

**Real-world analogy:** a universal power adapter. One device (the neutral skill body)
plus the right plug per country (the per-vendor adapter) = it works everywhere.

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
Enrollment is onboarding a detection into a managed library with a review gate — you
don't add content to the shared ruleset until it passes policy checks and conflicts are
resolved. Projection is distributing that library to every sensor in its native format.
**SOC parallel:** promoting a vetted rule into the central content repo, then deploying it to each platform's dialect.

### 🟡 Engineer Lens
`project_skills` is `project()` generalized over a `{relpath: content}` map: `SKILL.md`
+ `references/<vendor>-tools.md`, each drift-classified by a `"<name>/<relpath>"` key in
`state["skills"][runtime]`. Same guard/backup/secret/audit machinery. `enroll` separates
*deriving* a starting body (`propose_enrollment` → reconcile) from *committing* it
(`enroll_skill` → binding lints → write). `update_managed_skills` rewrites only the
trailing `managed_skills` block textually to preserve the file's security comments.
**Engineering decision to own:** generalizing a single-file projector to a file-set without duplicating the guard logic — and the comment-preserving config edit with its last-key invariant guard.

### 🔴 AI Security Engineer Lens
Skills are *executable instructions* for agents; a poisoned skill fans out to three.
Enrollment is the gate: cross-runtime reconciliation prevents silently adopting a drifted
(possibly tampered) variant, and the neutral-language lint keeps a body from smuggling a
runtime-specific instruction. Projection bundles only the trusted adapter alongside.
**AI security surface:** the skill supply chain — controlled onboarding + neutral-only bodies prevent injection via "add this skill." Refusing recursive directory copies also prevents browser state, cached credentials, virtual environments, or generated executables from entering the canonical source unnoticed.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/skills.py
def skill_files(config, runtime, name) -> dict[str, str]:
    body = (config.repo_root / "skills" / name / "SKILL.md").read_text("utf-8")
    adapter_name = REFERENCE_FILENAMES[runtime]            # claude->claude-code-tools.md ...
    adapter = (config.repo_root / "references" / adapter_name).read_text("utf-8")
    return {"SKILL.md": body, f"references/{adapter_name}": adapter}
```

```python
# src/agent_config_sync/enroll.py
def enroll_skill(config, name, body):
    if find_vendor_terms(body): raise NeutralLanguageError(name, find_vendor_terms(body))
    if find_secrets(body):      raise SecretFoundError(name, find_secrets(body))
    atomic_write(config.repo_root / "skills" / name / "SKILL.md", body)
    update_managed_skills(config.repo_root / "config" / "targets.yaml",
                          [*config.managed_skills, name])
```

| Step | Why |
|------|-----|
| reconcile variants | refuse to enroll a skill that differs across runtimes until you pick canonical |
| neutral + secret lint | binding gates before the source write |
| `update_managed_skills` | comment-safe; refuses if `managed_skills` isn't last key |

> ⚠️ **Common pitfall:** writing a body that says "use the Edit tool" — enrollment will
> reject it. Describe the *action* ("edit the file"), not the runtime's tool.

### Managed payload boundary

`agent-config-sync enroll my-skill --from claude` chooses Claude's
`SKILL.md` as the canonical body. It does not import the rest of
`~/.claude/skills/my-skill/`. Before enrollment, inspect that directory and
separate authored source assets from machine-local state. Companion files ARE
projected (since 2026-07-03) but only from the source tree: place reviewed text
files (`.md .txt .json .yaml .yml .toml`) under `skills/my-skill/` in the repo
and they fan out through the neutral-language gate, secret scan, extension
allowlist, hidden-path exclusion, adapter-collision refusal, and symlink
containment, with the same drift state, backup, and audit coverage as bodies
(`skills.companion_files`).

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Skills + enroll tests
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_skills.py tests/test_enroll.py -q
```
✅ **Success if:** green — incl. reconciliation + non-neutral + secret should-fails.

### 🔬 Exercise 2: Enroll a neutral skill (modification challenge)
```bash
printf -- '---\nname: hello\ndescription: demo\n---\n\nDispatch a subagent to greet the user.\n' > /tmp/hello.md
agent-config-sync enroll hello --body-file /tmp/hello.md
agent-config-sync project --dry-run | grep hello
```
📊 **Expected:** enrolled; dry-run shows `hello` SKILL.md + adapter for all three runtimes.
✅ **Success if:** the skill appears for claude, codex, and gemini.

### 🔬 Exercise 3: Non-neutral rejected (intentional failure)
```bash
printf -- '---\nname: bad\ndescription: x\n---\n\nUse the Bash tool.\n' > /tmp/bad.md
agent-config-sync enroll bad --body-file /tmp/bad.md; echo "exit=$?"
```
📊 **Expected:** `Aborted: skill 'bad' contains vendor-specific terms: Bash tool …` `exit=3`.

### 🔬 Exercise 4: Enroll from Claude without copying companions

Choose an existing Claude skill that you have reviewed and that is not already
managed, then set its name below:

```bash
REVIEWED_SKILL=architect  # replace with your reviewed, unmanaged Claude skill
agent-config-sync enroll "$REVIEWED_SKILL" --from claude
agent-config-sync project --dry-run
```

📊 **Expected:** `SKILL.md` and the per-runtime adapter appear in the projection
plan. Files beside Claude's `SKILL.md` are NOT imported by enroll; companions
join the payload only when you copy reviewed text files into `skills/<name>/`
in the source repository. If the neutral or secret lint blocks enrollment, fix
the canonical body instead of bypassing the gate.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** How did you reuse the instruction-file projector for skills without duplicating the drift/backup logic?
**A:** I modeled a skill as a `{relpath: content}` map (`SKILL.md` + adapter) and ran the same classify/backup/secret/audit loop over each file, keyed by `"<name>/<relpath>"` in a parallel `state["skills"]` namespace. The drift semantics (create/unchanged/update/drift/forced) are identical; only the iteration unit changed from one file to a set.
*Why it works:* shows abstraction reuse and a clean state-model extension.

### 🔴 AI Security Engineering
**Q:** "Add this skill" is a powerful, dangerous capability. How is it controlled?
**A:** Opt-in enrollment (managed_skills starts empty), cross-runtime reconciliation so a tampered/drifted variant can't be silently adopted, a binding neutral-language lint so a body can't smuggle a runtime instruction, a secret lint, and a human review of the diff before it's committed and projected to three agents.
*Why it works:* treats skills as an attacker-relevant supply chain with layered gates.

---

## ✅ Key Takeaways
- A skill projects as neutral `SKILL.md` + per-runtime adapter
- `project_skills` = the projector generalized to a file set
- Enrollment: reconcile → bind lints → write source → update allowlist
- `managed_skills` rewrite is comment-safe and guards the last-key invariant
- Text companion files under `skills/<name>/` in the source are part of the
  managed payload (since 2026-07-03): they project through the neutral-language
  and secret gates with an extension allowlist; scripts and runtime-local state
  remain outside

## 📋 Quick Reference
| Item | Value |
|------|-------|
| Files | `src/agent_config_sync/skills.py`, `enroll.py` |
| Entries | `project_skills(...)`, `enroll_skill(config, name, body)`, `propose_enrollment(...)`, `update_managed_skills(...)` |
| Errors | `SkillDriftError`, `NeutralLanguageError`, `ReconciliationError`, `SecretFoundError` |
| Tests | `tests/test_skills.py`, `tests/test_enroll.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** neutral body + per-vendor adapter (D2-1); opt-in enrollment (D2-2).
- **Rejected:** bulk auto-enrolling existing skills — large unreviewed surface.
- **Rejected:** recursively copying runtime skill directories — they can contain
  session state, caches, environments, and generated executables.
- **Trade-off:** incremental enroll gains safety + small diffs; costs one-at-a-time effort.
- **Trade-off:** the narrow payload protects the source boundary but does not yet
  support skills that require companion scripts or templates.

## 🚀 Next: Lesson 07 — capture-from-chat (`capture.py`), untrusted input → source.
*Remember: one neutral body, the right adapter per runtime — write once, run everywhere.* 🛡️
