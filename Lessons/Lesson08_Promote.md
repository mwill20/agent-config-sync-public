# 🎓 Lesson 08: The Return Path — promote.py & 3-Way Conflicts

## 🛡️ Welcome Back, Security Analyst!

Forward sync is easy; the hard, valuable part is **reverse** — "I learned something
inside Gemini, get it into Claude too." 🔍 Today: **`promote.py`** — detect a runtime's
out-of-band edit, route it back into the source, and re-project so everyone converges —
refusing to silently merge when the source *also* moved.

---

## 🎯 Learning Objectives
- Trace `detect_divergence` and the 3-way conflict check
- Explain how promote reuses the capture engine + force-reproject
- Define a 3-way conflict and why it's flagged, not merged
- Run the reverse-goal round trip

**Time estimate:** 22 min | **Prerequisites:** Lessons 04, 05, 07

---

## 🧠 What This Does — Plain English

You hand-edit `~/.gemini/GEMINI.md`. `promote gemini --target core` finds the lines you
added (live vs. projection), routes them into `_shared/core.md` via the capture engine
(so the secret lint still applies), and force-reprojects — now Claude and Codex have it
too. If the *source* also changed since the last project (both sides moved), that's a
**3-way conflict**: promote refuses to auto-merge and tells you to resolve it.

**Real-world analogy:** merging a field hotfix back into the master playbook. If master
also changed meanwhile, you don't blind-merge — you flag it for a human to reconcile.

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
This is promoting a sensor-local hotfix back to the central content repo, then
redeploying everywhere — with a conflict check so you never overwrite a master change
you didn't see. Detection-engineering hygiene: local improvements flow back, but
conflicts get human eyes.
**SOC parallel:** lifting a locally-tuned rule into the shared library and redeploying, with a "the master also changed" safety stop.

### 🟡 Engineer Lens
`detect_divergence` compares live vs. `projected_for(runtime)`; equal → nothing to do.
The 3-way check: if `sha256(projected) != .sync-state` hash for that target, the *source*
moved too → conflict. Otherwise it extracts added lines (`difflib.ndiff` "+ " lines),
hands them to `capture_standard`, then reprojects in two passes: a `force=True, only=runtime`
pass for the intentionally-drifted promoted runtime, then a plain `project(config)` for the
rest. Scoping the force matters — a *bare* `project(force=True)` here would trip
`ForceScopeError` (and abort *after* the source was already written) if any other runtime
also happened to be drifted. The scoped version instead lets that second pass raise
`DriftError` naming the real offender, so an unrelated un-promoted edit is refused, not clobbered.
**Engineering decision to own:** detection-only front layer delegating writes to the shared capture engine — no duplicate write/commit logic, one security path.

### 🔴 AI Security Engineer Lens
Reverse flow is the **highest-risk surface**: a promoted edit to `core.md` fans out to
three agents, and the content originated as a hand-edit (possibly attacker-influenced).
Same controls as capture (secret lint + human confirm), plus no-silent-merge on
conflict — you never auto-resolve competing changes to agent instructions.
**AI security surface:** attacker-influenced runtime edit amplified to all agents; mitigated by capture-engine gates + conflict refusal + human review.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/promote.py
def detect_divergence(config, runtime):
    projected = projected_for(config.repo_root, config.runtimes[runtime])
    live = rt.instruction_dest.read_text("utf-8") if exists else ""
    if live == projected:
        return None                                  # nothing to promote
    last = load_state(...).get("instructions", {}).get(runtime)
    source_moved = last is not None and sha256_text(projected) != last
    return {"added": _added_lines(projected, live), "conflict": source_moved, ...}

def promote_instruction(config, runtime, target, *, confirm=False):
    d = detect_divergence(config, runtime)
    if d is None: return None
    if d["conflict"]: raise PromoteConflict(runtime)         # never auto-merge
    result = capture_standard(config, target, d["added"], confirm=confirm)
    if confirm:
        project(config, force=True, only=runtime)   # force ONLY the promoted runtime
        project(config)                             # update the rest, refuse others' drift
    return result
```

| Step | Why |
|------|-----|
| live vs. projection | finds the out-of-band addition |
| hash vs. `.sync-state` | detects "source also moved" → 3-way conflict |
| delegate to `capture_standard` | reuses the secret gate + diff |
| `project(force=True, only=runtime)` | overwrites just the (intentionally) drifted promoted runtime |
| `project(config)` (no force) | updates the rest as safe `update`s; refuses (doesn't clobber) any *other* runtime's own un-promoted edit |

> ⚠️ **Common pitfall:** `promote` extracts *added lines* — great for append-style edits.
> A mid-file rewrite may capture extra context; always review the diff before `--confirm`.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Promote tests (incl. the reverse goal)
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_promote.py -q
```
✅ **Success if:** green — incl. `test_promote_reverse_goal_shared` and the 3-way conflict should-fail.

### 🔬 Exercise 2: Scan for divergence
```bash
agent-config-sync project          # baseline
agent-config-sync promote          # scan all (no runtime arg)
```
📊 **Expected:** "Nothing to promote — all runtimes match the source."
✅ **Success if:** clean scan after a fresh project.

### 🔬 Exercise 3: Reverse round trip (modification challenge)
```bash
printf '\nPREFER SQLITE FOR LOCAL CACHES.\n' >> ~/.gemini/GEMINI.md
agent-config-sync promote gemini --target core            # dry-run preview
agent-config-sync promote gemini --target core --confirm  # apply + reproject
grep -c "PREFER SQLITE" ~/.claude/CLAUDE.md ~/.codex/AGENTS.md
```
📊 **Expected:** dry-run shows the diff; after `--confirm`, the line appears in Claude and Codex.
✅ **Success if:** the gemini-born line is now in the other runtimes. *(Commit the source per the printed hint.)*

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** What is a 3-way conflict here and why refuse instead of merge?
**A:** Both sides moved: the live runtime file was hand-edited AND the source changed since the last project (detected by comparing the fresh projection's hash to the recorded `.sync-state` hash). There's no single source of truth at that moment, so auto-merging could silently drop or mangle one side's change to an agent's instructions. v1 flags it for manual resolution — correctness over convenience.
*Why it works:* precise definition + a principled "don't guess" stance.

### 🔴 AI Security Engineering
**Q:** Reverse promote is called the highest-risk path. Why, and how is it contained?
**A:** The promoted content originated as a runtime hand-edit (possibly attacker-influenced) and, routed to `core.md`, fans out to all three agents. It's contained by reusing the capture engine's gates (secret lint, visible diff, human `--confirm`), by refusing 3-way merges, and by backing up every overwritten file. The AI's per-section routing suggestion is advisory; a human approves each destination.
*Why it works:* identifies the amplification + provenance risk and the layered containment.

---

## ✅ Key Takeaways
- `promote` lifts a runtime edit back to source, then reprojects to converge
- Detection front layer delegates writes to the capture engine (one security path)
- 3-way conflicts are flagged, never auto-merged
- Reproject force is scoped to the promoted runtime, so another runtime's own
  un-promoted edit is refused (`DriftError`), not clobbered, during fan-out
- Reverse is highest-risk: same gates as capture + conflict refusal + backups

## 📋 Quick Reference
| Item | Value |
|------|-------|
| File | `src/agent_config_sync/promote.py` |
| Entries | `detect_divergence(config, runtime)`, `promote_instruction(config, runtime, target, *, confirm)` |
| CLI | `promote [<runtime> --target core\|<rt>] [--confirm]` (bare = scan all) |
| Error | `PromoteConflict` (exit 2); secret → exit 3 |
| Test | `tests/test_promote.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** explicit promote with review; flag (not merge) 3-way conflicts (D-2 / D3-2).
- **Rejected:** automatic bidirectional merge — no source of truth at conflict time.
- **Trade-off:** detect-and-flag gains safety + simplicity; gives up a guided merge (future: store last-projected content, not just its hash).

## 🚀 Next: Lesson 09 — the allowlist exception (`settingsedit.py` + `install-hooks`).
*Remember: bring the field fix home — but if home moved too, stop and let a human reconcile.* 🛡️
