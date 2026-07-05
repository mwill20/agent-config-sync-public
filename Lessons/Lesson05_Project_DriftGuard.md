# 🎓 Lesson 05: Air Traffic Control — project.py & the Drift Guard

## 🛡️ Welcome Back, Security Analyst!

How do you push updates to many endpoints *without* silently overwriting a change
someone made locally on purpose? 🔍 Today: **`project.py`** — the forward-projection
engine and its **drift guard**, the control that refuses to clobber an un-promoted edit.

---

## 🎯 Learning Objectives
- Trace `project()` end to end: plan → guard → write
- Explain the five classifications: create / unchanged / update / drift / forced
- Explain the blanket-`--force` guard (exit 4) and why it exists
- See how secret-lint, backups, state, and audit compose here

**Time estimate:** 22 min | **Prerequisites:** Lessons 01–04

---

## 🧠 What This Does — Plain English

`project()` renders each runtime's instruction file, decides what *kind* of write each
is, and writes only the safe ones. If a target was hand-edited out of band (its content
matches neither the new projection nor the last-recorded hash), it's **drift** — refused
unless you pass a per-runtime `--force` (which backs up first). A blanket `--force`
across more than one drifted runtime is refused (exit 4): you must name the one you mean.

**Real-world analogy:** air traffic control. Planes (writes) only land when cleared;
a runway with an unexpected obstacle (a hand-edit) is held, not bulldozed.

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
This is safe content deployment with change-control: push the vetted version everywhere,
but *hold and alert* on any endpoint whose local copy was modified — don't silently
overwrite evidence. The `--force` scoping is a deliberate "are you sure, and exactly
where?" guardrail.
**SOC parallel:** a content-deployment job that refuses to overwrite a sensor someone hotfixed, flagging it for review instead.

### 🟡 Engineer Lens
`_classify` compares three things — current file, fresh projection, last-recorded hash —
to pick create/unchanged/update/drift/forced. `project` builds the full *plan* first,
raises `DriftError`/`ForceScopeError` *before* any write (no partial state), then writes,
saving state and appending audit **inside** the loop so a crash can't desync the ledger.
**Engineering decision to own:** plan-then-act with pre-write validation — errors are raised before side effects, so a rejected run changes nothing.

### 🔴 AI Security Engineer Lens
The drift guard is what prevents the forward path from *erasing* a learning made inside a
runtime before it's been reviewed and promoted — and prevents a source push from silently
overwriting a locally-injected change without anyone noticing. Force is scoped so you
can't blanket-overwrite multiple agents' instruction files in one careless sweep.
**AI security surface:** change-control on agent instructions — no silent clobber, scoped override, full audit.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/project.py
def _classify(projected, dest, last_hash, force):
    if not dest.exists():            return "create"
    current = dest.read_text("utf-8")
    if current == projected:         return "unchanged"
    if last_hash is not None and sha256_text(current) == last_hash:
        return "update"              # source moved; our last output is intact -> safe
    return "forced" if force else "drift"   # someone edited it out of band
```

```python
    drifted = [a.runtime for a in plan if a.kind == "drift"]
    if drifted and not dry_run:
        raise DriftError(drifted)                 # refuse before writing
    forced = [a.runtime for a in plan if a.kind == "forced"]
    if force and only is None and len(forced) > 1 and not dry_run:
        raise ForceScopeError(forced)             # no blanket multi-force
```

`skills.py::project_skills` carries the *same* `ForceScopeError` guard for
managed skill files. And because a blanket `--force` spans instructions *and*
skills — two plans that never see each other — the CLI runs a combined pre-flight
that counts forced targets across both and refuses if the total exceeds one. So
you can't slip past the guard by drifting one instruction and one skill at once.

```python
# src/agent_config_sync/cli.py — combined blanket-force pre-flight
if args.force and args.runtime is None and not args.dry_run:
    forced = [a.runtime for a in project(config, dry_run=True, force=True)
              if a.kind == "forced"] + \
             [f"{a.runtime}:{a.name}/{a.relpath}"
              for a in project_skills(config, dry_run=True, force=True)
              if a.kind == "forced"]
    if len(forced) > 1:
        return 4   # name one runtime instead
```

| Classification | Meaning | Action |
|----------------|---------|--------|
| create | target missing | write |
| unchanged | matches projection | skip |
| update | source moved, our last write intact | write (safe) |
| drift | hand-edited out of band | **refuse** (or `forced` with scoped `--force`) |

> ⚠️ **Common pitfall:** thinking `--force` is global. A bare `--force` with 2+ drifted
> targets — counting instruction files **and** managed skills together — raises
> `ForceScopeError` (exit 4). You must scope it: `project claude --force`.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Projection tests
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_project.py -q
```
✅ **Success if:** green — incl. idempotency, drift refusal, force-scope.

### 🔬 Exercise 2: Idempotency live
```bash
agent-config-sync project        # writes / updates
agent-config-sync project        # second run
```
📊 **Expected:** the second run shows `unchanged` for everything.
✅ **Success if:** no `update`/`create` the second time.

### 🔬 Exercise 3: Drift refusal (intentional failure)
Hand-edit a live instruction file, then project:
```bash
printf '\nHAND EDIT\n' >> ~/.gemini/GEMINI.md
agent-config-sync project; echo "exit=$?"
```
📊 **Expected:** `Refusing to overwrite un-promoted changes in: gemini …` and `exit=2`.
✅ **Success if:** exit 2 and the edit is preserved (not clobbered). *(Then recover with `promote` — Lesson 08 — or `project gemini --force`.)*

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** How does the tool distinguish "source moved" (safe overwrite) from "user edited the output" (refuse)?
**A:** Three-way compare. If the file equals the fresh projection → unchanged. If it equals the *last recorded hash* but not the projection → the source advanced and our previous output is intact → safe `update`. If it equals neither → out-of-band edit → `drift`, refused unless a per-runtime `--force` (which backs up first). The plan is built and validated before any write, so a rejected run is side-effect-free.
*Why it works:* precise state reconciliation + fail-before-write discipline.

### 🔴 AI Security Engineering
**Q:** Why scope `--force` to a single runtime?
**A:** A blanket force could overwrite *every* agent's instruction file in one command — if one was maliciously or accidentally edited, you'd erase the evidence everywhere at once. Forcing one named runtime keeps the override deliberate and bounded, and every overwrite is backed up. It's least-surprise + blast-radius control for prompt content.
*Why it works:* connects an ergonomics guard to blast-radius reasoning.

---

## ✅ Key Takeaways
- Five classifications; only safe ones are written
- Drift (out-of-band edit) is refused, not clobbered — for instructions *and* skills
- Blanket `--force` across >1 drift is refused (exit 4) — instructions and skills
  counted together — scope it to one runtime
- Plan-then-act: errors raise before writes; audit/state saved in-loop

## 📋 Quick Reference
| Item | Value |
|------|-------|
| File | `src/agent_config_sync/project.py` |
| Entry | `project(config, *, dry_run, force, only, stamp)` |
| Errors | `DriftError` (exit 2), `ForceScopeError` (exit 4), `SecretFoundError` (exit 3) |
| Test | `tests/test_project.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** refuse-on-drift; scoped force only.
- **Rejected:** auto-overwrite (would silently destroy un-promoted learnings).
- **Trade-off:** safety gains no-silent-clobber; costs an occasional manual `promote`/`--force` step.

## 🚀 Next: Lesson 06 — skills projection & enrollment (`skills.py` + `enroll.py`).
*Remember: clear the runway before you land — never bulldoze an obstacle you didn't expect.* 🛡️
