# 🎓 Lesson 12: The Control Tower — Operating agent-config-sync Day to Day

## 🛡️ Welcome Back, Security Analyst!

You have spent eleven lessons inside the engine. But how do you actually *fly*
this thing? 🔍 Today we're exploring the **operator workflow** (the
`agent-config-sync` CLI as a whole) — the "control tower" from which one person
keeps three AI runtimes on the same reviewed configuration without ever
hand-editing a generated file.

This lesson is the one to read if you only read one: it is the "how to use this
tool" guide. Lessons 01–11 explain how each part works inside.

---

## 🎯 Learning Objectives

By the end of this lesson you will be able to:

- Run the daily health loop (`check`, `status`, `doctor`) and read its results
- Change a shared standard or a single runtime's overlay and fan it out safely
- Add a new skill (body plus text companions) through the enrollment gates
- Resolve drift deliberately, choosing between `promote` and a scoped `--force`
- Recognize a gate refusal as a control working, and fix content instead of bypassing

**Time estimate:** 30 minutes | **Prerequisites:** none (Lesson 00 recommended)

---

## 🧠 What This Component Does — Plain English

You run three AI coding assistants (Claude Code, Codex, Gemini/AntiGravity).
Each reads its own global instruction file and its own skills directory. Without
this tool, a rule you teach one assistant silently never reaches the other two,
and three copies of every skill slowly diverge.

This repository is the single reviewed source. The CLI projects that source into
every runtime, detects when a runtime copy was edited out-of-band (drift), and
gives you two deliberate resolutions: lift the edit back into the source
(`promote`) or discard it with an explicitly scoped overwrite (`--force`).
Deterministic gates screen everything that moves: no secrets, no
runtime-specific language in shared bodies, no writes outside the allowlist.

**Real-world analogy:** golden-image management for endpoints. You never patch
one laptop by hand and hope the others catch up; you update the image, redeploy,
and your integrity monitoring flags any box that no longer matches.

---

## 🔵🟡🔴 Career Lens — Three Perspectives on This Component

### 🔵 Analyst Lens — What a SOC Analyst Sees Here

This is detection-content management. The source repo is your rule repository,
`project` is the push to every sensor, and `check` is the integrity monitor that
alerts when a deployed copy no longer matches the approved baseline. Drift
refusal is the same discipline as refusing to hot-patch a correlation rule on
one SIEM node: either the change is promoted into the rule repo, or it is
reverted. The audit log (`.sync-audit.log`) gives you the forensic
reconstruction you would expect from any consequential-action trail.

**SOC parallel:** one FortiSIEM rule set pushed to every collector, with
file-integrity alerts on local tampering and a change-control path back.

---

### 🟡 Engineer Lens — What a Cybersecurity Engineer Builds Here

The operator surface is a thin CLI over deterministic modules: render, project,
skills, capture, promote, settingsedit. Every mutating command takes a
repo-scoped lock, backs up before overwriting, writes atomically, records state
hashes, and appends to an audit log. The design decision to own: dry-run is the
default for anything consequential (`capture`, `promote`, `prune-backups`), and
destructive intent must always be scoped (`project claude --force`, never a
blanket force across drifted targets). Exit codes are a contract (0 in sync,
1 drift, 2 operator issue, 3 gate/config failure, 4 unsafe force, 5 lock held),
which makes the tool safe to wire into hooks and CI.

**Engineering decision to own:** refuse-by-default with explicit, scoped
override. You should be able to defend why a blanket `--force` across two
drifted targets exits 4 instead of "just working."

---

### 🔴 AI Security Engineer Lens — What an AI/ML Security Engineer Watches For

The projected files become **system-prompt-adjacent input** for three different
LLM agents. That makes this pipeline an indirect prompt-injection distribution
channel: poison the source once and three agents ingest it forever. The
controls that matter here are the binding gates (secret scan and
neutral-language lint at enrollment AND at projection), human confirmation on
capture/promote, and the fact that the AI proposing a change never holds the
pen — the deterministic CLI decides. When you operate the tool, treat every
body and companion as untrusted input until the gates pass it.

**AI security surface:** a single malicious skill companion fanning out to all
three runtimes; mitigated by projection-time lints, the text-only allowlist,
and the human `--confirm` checkpoint.

---

## 🗺️ Where This Fits in the System

```
you (operator) ──edit──▶ 📁 source repo ──project──▶ 🤖 ~/.claude  🤖 ~/.codex  🤖 ~/.gemini
      ▲                        │                          │
      └──── promote ◀── drift detected ◀───── check ◀─────┘
```

If the operator loop stops, nothing breaks immediately — the runtimes keep
their last projection. What degrades is trust: runtime edits accumulate as
unreviewed drift, and the three assistants slowly stop following the same rules.

---

## 🔑 Key Concepts

### The Source-of-Truth Loop
Edit source, `project`, `check`. Never edit `~/.claude/CLAUDE.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`, or any managed skill copy directly.
Generated files carry a banner saying exactly this.

### Drift Is a Signal, Not an Error
`check` exiting 1 means a runtime copy differs from what the tool last wrote.
That is information: either the edit is valuable (promote it into the source)
or it is not (discard with a runtime-scoped force). The tool refuses to make
that call for you.

### Gates Are Binding
Secret scan, neutral-language lint, path containment, extension allowlist.
A refusal (exit 3) means fix the content. Weakening a gate to land a change is
the one move this project treats as a defect in the operator, not the tool.

---

## 📝 Code Walkthrough

This lesson is workflow-focused; the deep dives live in earlier lessons. The
one contract worth reading here is the exit-code table the whole workflow
hangs off (see `src/agent_config_sync/cli.py`, and Lesson 10 for the full
walkthrough):

| Exit | Meaning | Operator response |
|---:|---|---|
| 0 | Success / in sync | Nothing to do |
| 1 | `check` found drift | Decide: promote or scoped force |
| 2 | Drift refusal, unknown runtime, promote conflict | Read the message; it names the file |
| 3 | Gate or config failure (secret, non-neutral, hooks, pruning) | Fix the content or config |
| 4 | Unsafe blanket force | Rescope to one runtime |
| 5 | Mutation lock held | Another invocation is running; investigate before deleting the lock |

> ⚠️ **Common pitfall:** treating exit 2's drift refusal as a bug and reaching
> for `--force` reflexively. The refusal names the exact file; look at it first.
> The overwritten version goes to `.backups/`, but reviewing beats recovering.

---

## 🧪 Hands-On Exercises

> Run these from `C:\Projects\agent-config-sync` with the package installed
> (`python -m pip install -e ".[dev]"`).

### 🔬 Exercise 1: The Daily Health Loop

Proves you can read the tool's health surface.

```powershell
agent-config-sync check
agent-config-sync status
agent-config-sync doctor
```

📊 **Expected output:**
```
All runtimes in sync.
(status: one block per runtime, every file listed as in sync)
(doctor: plain-language environment and sync health, all ok)
```

✅ **You succeeded if:** `check` exits 0 and doctor reports no problems.

---

### 🔬 Exercise 2: Preview a Projection Without Writing

Proves you can read a projection plan before trusting it.

```powershell
agent-config-sync project --dry-run
```

📊 **Expected output:**
```
unchanged  claude -> C:\Users\<you>\.claude\CLAUDE.md
unchanged  codex -> C:\Users\<you>\.codex\AGENTS.md
unchanged  gemini -> C:\Users\<you>\.gemini\GEMINI.md
...one line per managed instruction file, skill body, adapter, and companion
```

✅ **You succeeded if:** every line reads `unchanged` on a clean tree, and no
file was modified (run `check` again to confirm).

---

### 🔬 Exercise 3: Intentional Failure — Watch a Gate Refuse

Proves the neutral-language gate blocks a non-neutral skill body before
anything is written.

```powershell
Set-Content -Encoding utf8 bad-body.md "---`nname: demo-bad`ndescription: demo`n---`n`nUse the Bash tool to run this.`n"
agent-config-sync enroll demo-bad --body-file bad-body.md
Remove-Item bad-body.md
```

📊 **Expected output:**
```
Aborted: skill 'demo-bad' contains vendor-specific terms: Bash tool. Neutralize the body and retry.
```

✅ **You succeeded if:** the command exits 3, the message names the offending
term, and `config/targets.yaml` does not contain `demo-bad` (nothing was
enrolled or written).

---

### 🔬 Exercise 4 (Optional): Capture a Standard, Dry-Run First

Proves the capture path shows you the exact source diff before anything lands.

```powershell
agent-config-sync capture standard --target core --text-file examples/sample_rule.md
```

📊 **Expected output:**
```
(unified diff of the proposed _shared/core.md change)
DRY-RUN - nothing written. Re-run with --confirm to apply + project.
```

✅ **You succeeded if:** you can read the exact diff that would land, and
nothing changed (`git status` is clean).

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering Interview

**Q:** Your config-distribution tool detects that a deployed file was edited
out-of-band. Walk me through why "refuse and make the operator choose" beats
both "silently overwrite" and "silently keep the local edit."

**A:** Overwriting destroys potentially valuable unreviewed work and hides that
tampering ever happened; keeping the local edit silently forks the fleet from
its baseline. Refusing converts an ambiguous state into an explicit decision
with an audit trail: promote lifts the edit through review into the source so
every node gets it; a scoped force discards it deliberately, with a backup and
an audit entry. The key design detail is scoping — a blanket force across
multiple drifted targets is refused outright, so one intentional overwrite can
never collateral-damage an unrelated file.

*Why this answer works:* it reasons about failure modes and blast radius, not
just the happy path.

---

### 🔴 AI Security Engineering Interview

**Q:** This tool writes files that three different LLM agents load as standing
instructions. What is the attack surface, and where would you put the controls?

**A:** The pipeline is an indirect prompt-injection distribution channel: any
content that passes into the source fans out to every agent's
instruction-adjacent context. Controls belong at the last chokepoint before
fan-out, not just the entry paths — this tool runs its secret scan and
neutral-language lint at projection time as well as enrollment, so even a
direct edit to the canonical source cannot ship ungated. Text-only companion
allowlists keep executables out, human confirmation gates capture/promote, and
the deterministic CLI (never the AI) holds write authority. I would monitor the
audit log for unexpected source writes the same way I would watch a detection
rule repo.

*Why this answer works:* it applies trust-boundary thinking to the AI
instruction supply chain, and names the projection-time chokepoint rather than
only the front door.

---

## ✅ Key Takeaways

- Daily loop: `check` → (edit source → `project` → `check`) → done
- Never hand-edit generated files; `promote` brings runtime edits home
- Dry-run is the default for consequential commands; read plans before writing
- A gate refusal (exit 3) is the system working — fix content, never the gate
- Drift resolution is always a deliberate, scoped, audited choice

---

## 📋 Quick Reference Card

| Item | Value |
|------|-------|
| Health | `agent-config-sync check` (0 = in sync), `sense` (what changed + fix command), `status`, `doctor` |
| Change a shared rule | edit `_shared/core.md` → `project` → `check` |
| Change one runtime | edit `overlays/<runtime>.md` → `project` → `check` |
| New skill | `enroll <name> --body-file <path>` → `project` |
| Skill companions | copy reviewed text files into `skills/<name>/` → `project` |
| Runtime edit worth keeping | `promote <runtime>` (dry-run first) |
| Runtime edit to discard | `project <runtime> --force` (scoped, backed up) |
| Validate | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` |
| Recover a file | snapshots under `.backups/`, actions in `.sync-audit.log` |

---

## 📌 Implemented vs. Recommended

### What This Project Implements ✅
- Refuse-by-default drift handling with scoped force (`project.py`, `skills.py`)
- Gates at enrollment and projection (`enroll.py`, `skills.py`, `neutralize.py`, `secrets.py`)
- Dry-run defaults on capture, promote, prune (`cli.py`)
- Startup drift hooks in all three runtimes plus a git pre-commit check

### General Best Practices — Recommended but Not Implemented Here
- Scheduled (e.g., daily) automated `check` with alerting beyond session start — `Recommended (not implemented here)`
- Signed commits or provenance attestation on source changes — `Recommended (not implemented here)`

---

## ⚖️ Decisions & Trade-offs

### Decisions Touched
| Decision | Statement | Why It Matters Here |
|----------|-----------|---------------------|
| Refuse-by-default | Drift blocks projection until resolved | The operator loop stays honest; nothing is silently lost |
| Dry-run defaults | capture/promote/prune preview first | Consequential writes always get a human read |
| Text-only companions | No executable payloads project | Keeps the fan-out reviewable input, not code |

### What We Explicitly Rejected
- **Automatic bidirectional sync (last-writer-wins):** silently merging runtime
  edits back would turn unreviewed agent output into fleet-wide instructions.

### Trade-off Log
| Choice Made | What We Gained | What We Gave Up |
|-------------|----------------|-----------------|
| Manual promote step | Review checkpoint on every reverse flow | Runtime edits wait for an operator |
| Scoped force only | No collateral overwrites | Two-step resolution when multiple targets drift |

### Future Gate Conditions
- Adding a fourth runtime → revisit the adapter set and hook installer
- Publishing the repo → license selection and a fresh REPO_AUDIT pass

---

## 🚀 You Have Completed the Curriculum

This is the final lesson. If you started at Lesson 00 you have now seen the
system twice: once from inside the modules, once from the operator's chair.

**Optional deeper dive:** read `docs/threat-models/` end to end and trace each
mitigation pointer to its function — the fastest honest review of the whole
security posture.

**Modification challenge:** enroll a small skill of your own with one text
companion, verify it appears in all three runtimes, then delete your local
copies and re-project to restore them. Total time: under 20 minutes.

*Remember: the tool never decides; it refuses, previews, and records — deciding is your job.* 🛡️
