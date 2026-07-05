# 🎓 Lesson 00: The Universal Translator — System Overview of agent-config-sync

## 🛡️ Welcome, Security Analyst!

Ever maintained the same correlation rule in two SIEMs and watched them quietly
drift apart? 🔍 Today we explore **agent-config-sync** — the "universal translator
and notary" that keeps three AI coding assistants (Claude Code, Codex,
Gemini/AntiGravity) steering from **one source of truth**, and lets a lesson learned
inside any one of them flow back out to the others — safely, with a preview and a
human confirm before anything is written.

---

## 🎯 Learning Objectives

By the end of this lesson you will be able to:

- Describe the **projector architecture**: one neutral source → many vendor outputs
- Trace the **forward** path (`project`) and the **reverse** path (`promote`)
- Identify the **deterministic security gates** and where each sits
- Name the **trust boundaries** and the one deliberate exception to them
- Run the test suite and the CLI end-to-end against a safe sandbox

**Time estimate:** 25 minutes | **Prerequisites:** none — this is the anchor lesson

---

## 🧠 What This System Does — Plain English

You run several AI assistants. Each reads its own "rules" file (`~/.claude/CLAUDE.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) and its own folder of "skills." Edit one
by hand and the others never find out — they drift. And each assistant speaks a
different *tool language*, so a skill written for one can't be copy-pasted to another.

`agent-config-sync` solves this like a compiler. There is **one neutral source** in a
git repo: `_shared/core.md` (shared standards) plus `overlays/<vendor>.md` (per-vendor
extras). The `project` command *renders* that source into each runtime's real file and
copies managed skills out. Only skills explicitly enrolled in `managed_skills` are
canonical, and each projected payload is limited to `SKILL.md` plus one runtime
adapter. The tool does not recursively mirror live skill directories or their scripts,
environments, browser profiles, caches, or session state. Nothing in `~/.claude`
etc. is hand-edited — it is all **generated**. When you do change something inside one
runtime, `promote` lifts it back into the source and re-projects so everyone
converges.

**Real-world analogy:** a SOAR platform where one master playbook compiles down to
vendor-specific actions. You edit the master, not the per-integration scripts; and
when an analyst improves a step in one integration, you promote it back to the master
so every integration inherits it — after a review, never silently.

---

## 🔵🟡🔴 Career Lens — Three Perspectives

### 🔵 Analyst Lens — What a SOC Analyst Sees Here

This is **config drift management with an audit trail** — the discipline you already
apply to detection content. `check` is your "are my rules deployed and unmodified?"
sweep; `status` is the per-source detail view; `.sync-audit.log` is the change record
you'd hand to IR. The drift guard refusing to overwrite a hand-edited file is the same
instinct as a SIEM warning "this rule was changed out-of-band — review before redeploy."

**SOC parallel:** `project` is pushing a vetted content pack to every sensor; `check`
is the deployment-state verification that flags any sensor whose local copy was tampered.

### 🟡 Engineer Lens — What a Cybersecurity Engineer Builds Here

The architecture is a **pure-render core + thin command layer**. `render(core, overlay)`
is a deterministic pure function (same input → identical output). Everything stateful
(`project`, `capture`, `promote`) reads source, computes the projection, and writes only
to allowlisted destinations via atomic writes + backups. State lives in
`.sync-state.json` (a hash of the last content written per target) so the tool can tell
"source moved ahead" (safe to overwrite) from "someone hand-edited the output" (refuse).
That hash is the whole drift-detection engine.

**Engineering decision to own:** determinism is injectable — timestamps and allowed
roots are parameters, so tests are hermetic and the render is reproducible. You should
be able to explain why a wall-clock value must never appear in projected content (it
would break idempotency and make `check` always report drift).

### 🔴 AI Security Engineer Lens — What an AI/ML Security Engineer Watches For

These files are **system prompts for three agents**. A poisoned `_shared/core.md` is an
**indirect prompt-injection amplifier** — one edit fans out to three autonomous coding
agents at once. That is why the reverse/capture paths are dry-run-by-default, gated by
deterministic lints (secret + neutral-language), and require an explicit human
`--confirm` after showing a diff. The AI's role (proposing routing/review) is advisory
only and lives in the chat agent — **a probabilistic model never authorizes a write**.

**AI security surface:** the capture/promote ingress (untrusted text → source → 3
agents). Controls: `secrets.find_secrets`, `neutralize.find_vendor_terms`, the human
confirm, and 3-way-conflict detection — see `docs/threat-models/`.

---

## 🗺️ Where Everything Fits

```
        ┌─────────────────── SOURCE OF TRUTH (git repo) ───────────────────┐
        │  _shared/core.md   overlays/{claude,codex,gemini}.md              │
        │  skills/<name>/SKILL.md   references/<vendor>-tools.md            │
        │  config/targets.yaml  (the write allowlist)                       │
        └──────────────────────────────┬───────────────────────────────────┘
                                        │
   render() ── project / project_skills │ (forward)        promote ▲ (reverse)
                                        ▼                          │
   ~/.claude/CLAUDE.md   ~/.codex/AGENTS.md   ~/.gemini/GEMINI.md   │
   + skills/<name>/SKILL.md + references in each runtime ───────────┘
                                        ▲
              capture (chat) ───────────┘  (untrusted text → source, gated)

   Gates on every write:  secret-lint · allowlist · neutral-language(skills) · drift-guard
   Durability: atomic writes · per-file backups (.backups/) · .sync-audit.log
```

If `render`/`project` breaks, runtimes stop receiving updates (fail-safe — old config
stays). If a gate breaks open, poisoned content could reach three agents — gates are
the security-critical path.

---

## 🔑 Key Concepts

### Projection
Rendering the neutral source into a runtime-specific artifact: `header + core + overlay`.
Forward = source → runtimes (`project`). Reverse = runtime edit → source (`promote`).

### Deterministic gate vs. advisory review
A *gate* is rule-based code that can block a write (`find_secrets`, `find_vendor_terms`,
the allowlist, the drift guard). *Advisory review* is an AI opinion that informs a human
but can never authorize the write. Security decisions ride only on gates.

### Drift guard
`.sync-state.json` stores `sha256` of the last content the tool wrote per target. On the
next run: output == projection → unchanged; output hash == stored hash but != projection
→ source moved (safe `update`); output != projection and hash != stored → hand-edited
(`drift`, refused without per-runtime `--force`).

---

## 📝 Code Walkthrough — the deterministic heart

```python
# src/agent_config_sync/render.py
def render(core_text: str, overlay_text: str) -> str:
    parts = [GENERATED_HEADER.rstrip("\n"), core_text.strip("\n")]
    if overlay_text.strip():
        parts.append(overlay_text.strip("\n"))
    return "\n\n".join(parts) + "\n"
```

| Lines | What it does | Why designed this way |
|-------|-------------|------------------------|
| `GENERATED_HEADER` | Stamps "DO NOT EDIT HERE" on every output | Tells humans + the tool these files are derived |
| `core + overlay` | Concatenates shared then vendor content | Shared flows everywhere; overlay stays local |
| pure function | No I/O, no clock | Same input → identical output = idempotent, testable |

**Design pattern:** a *pure transformation* core wrapped by an imperative shell — the
functional-core/imperative-shell pattern. The risky stuff (file writes) is isolated; the
logic is trivially testable.

> ⚠️ **Common pitfall:** putting a timestamp in the discovery section would make every
> `project` produce different bytes → `check` always reports drift. Drift signals must be
> deterministic (content hash) or come from the `check` command itself.

---

## 🧪 Hands-On Exercises

> Activate the project venv / install: `python -m pip install -e ".[dev]"`.

### 🔬 Exercise 1: Run the test suite

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
```

📊 **Expected output:**
```
208 passed
```

✅ **You succeeded if:** the suite passes with zero failures (the count grows as
features land; `docs/EVALUATION.md` logs each baseline — 208 as of 2026-07-04).

### 🔬 Exercise 2: See the projection without writing

```bash
agent-config-sync status
agent-config-sync project --dry-run
```

📊 **Expected output:** `status` lists each runtime/skill; `--dry-run` prints
`unchanged`/`update`/`create` lines and writes nothing.

✅ **You succeeded if:** `--dry-run` printed a plan and changed no files.

### 🔬 Exercise 3: Watch a gate fire (intentional failure)

Create a file with a fake secret and try to capture it:

```bash
printf 'api_key = "abcd1234efgh5678"\n' > /tmp/leak.md
agent-config-sync capture standard --target core --text-file /tmp/leak.md --confirm
echo "exit=$?"
```

📊 **Expected output:**
```
Aborted: secret-like content in 'core'. Nothing written.
exit=3
```

✅ **You succeeded if:** exit code is `3` and nothing was written to `_shared/core.md`.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering Interview

**Q:** How does this tool distinguish a legitimate source update from a user's
out-of-band edit when deciding whether to overwrite a generated file?

**A:** It stores a `sha256` of the last content it wrote per target in
`.sync-state.json`. On the next run it compares three things: the current file, the
freshly rendered projection, and the stored hash. If the file matches the stored hash
but not the projection, the *source* moved — safe to overwrite (`update`). If the file
matches neither, a human edited it — refuse (`drift`) unless a scoped `--force` is given,
and back up before overwriting. State is saved *inside* the write loop so a mid-run crash
never leaves a written file unrecorded.

*Why this answer works:* shows you reason about state reconciliation and failure modes,
not just happy-path file copying.

### 🔴 AI Security Engineering Interview

**Q:** These files are effectively system prompts for three agents. What's the attack
surface when you let a user "capture this rule from chat," and how is it controlled?

**A:** It's indirect prompt injection with a 3× blast radius — captured text may be
attacker-influenced and fans out to three agents on the next project. Controls:
capture/promote are dry-run by default and print a diff; deterministic lints
(`find_secrets`, `find_vendor_terms`) run *before any write, even in dry-run*; a human
must pass `--confirm`; and the AI's routing/review is advisory only — never authorizes
the write. Reverse `promote` also detects a "source-also-moved" 3-way conflict via the
state hash and refuses to auto-merge.

*Why this answer works:* applies threat modeling to the data path into the model's
context, and shows the deterministic-gate-over-probabilistic-judgment principle.

---

## ✅ Key Takeaways

- One neutral source projects to many vendor outputs; runtimes are derived, never authored
- `render` is a pure function; stateful commands are a thin shell around it
- `.sync-state.json` hashes power the drift guard (update vs. drift vs. unchanged)
- Security rides on deterministic gates; AI review is advisory only
- Writes are allowlisted, atomic, backed up, and audited — with one documented exception (`install-hooks`)

---

## 📋 Quick Reference Card

| Item | Value |
|------|-------|
| Source of truth | `_shared/core.md` + `overlays/<vendor>.md` + `skills/<name>/SKILL.md` |
| Allowlist | `config/targets.yaml` |
| Forward command | `agent-config-sync project` |
| Reverse command | `agent-config-sync promote <runtime> --target core|<runtime>` |
| Capture command | `agent-config-sync capture {standard|skill} … [--confirm]` |
| Health | `agent-config-sync doctor` |
| State / audit | `.sync-state.json` · `.sync-audit.log` (gitignored) |
| Tests | `tests/` — `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider` |

---

## 📌 Implemented vs. Recommended

### What This Project Implements ✅
- Forward projection, skills, discovery, capture, reverse promote, install-hooks
- Deterministic secret + neutral-language lints; allowlist; drift guard; backups; audit log
- Exact Python build/direct-dependency pins and immutable GitHub Action SHAs

### Recommended but Not Implemented Here
- Signing/verification of the source repo (e.g., signed commits enforced) — `Recommended (not implemented here)`
- Recursive companion-asset projection for managed skills — `Recommended only after an explicit allowlist, containment, lint, drift, backup, and audit design`
- True guided 3-way merge on promote conflicts — `Recommended (not implemented here)`

---

## ⚖️ Decisions & Trade-offs

### Decisions Touched
| Decision | Statement | Why It Matters Here |
|----------|-----------|---------------------|
| Neutral core + per-vendor overlays | Content model | Lets one source serve three tool languages |
| Explicit `promote` with review | No auto-merge | Human is the security gate for the fan-out |

### What We Explicitly Rejected
- **Automatic bidirectional merge:** no single source of truth at conflict time → 3-way conflicts are flagged, not merged.
- **A wall-clock "last-synced" stamp in output:** breaks idempotency; `check` is the drift signal instead.

### Trade-off Log
| Choice Made | What We Gained | What We Gave Up |
|-------------|----------------|-----------------|
| Curated denylist for neutral-language lint | No false positives on ordinary prose | Completeness (must add new tool names over time) |
| capture/promote print git hint, don't auto-commit | Deterministic, testable, no surprise git ops | One-command durability (user commits manually) |

### Future Gate Conditions
- Adding a 4th runtime → extend `references/` adapters + `targets.yaml` (additive).
- Real guided merge needed → store last-projected *content* (not just hash) in `state.py`.

---

## 🚀 Ready for Lesson 01?

Next up: **The Render Core — Deterministic Projection** — a close read of `render.py`
and why purity is a security property. Get ready to trace a single function that the
entire system depends on!

**Modification challenge (<30 min):** add a managed skill of your own — write a neutral
`SKILL.md`, `agent-config-sync enroll my-skill --body-file <path>`, then `project --dry-run`
and watch it appear for all three runtimes. Confirm the plan holds `SKILL.md` plus
the runtime adapter (plus any text companions you placed under `skills/my-skill/`
in the source; runtime-side files are never imported). Try sneaking in "use the
Bash tool" and watch the neutral-language gate reject it.

*Remember: the source is the truth; everything the AIs see is just a projection of it.* 🛡️
