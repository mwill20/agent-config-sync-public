# Design Spec — agent-config-sync Plan 2 (Skills + Discovery + Capture)

**Status:** Approved design (pre-implementation)
**Date:** 2026-06-28
**Author:** Brainstormed collaboratively (owner + Claude), critiqued (cycle 1) and hardened
**Builds on:** Plan 1 (forward projection of instruction files) — `docs/superpowers/plans/2026-06-27-agent-config-sync-forward.md`
**Parent design:** `docs/superpowers/specs/2026-06-27-cross-runtime-sync-design.md`
**Next step:** writing-plans → implementation slices

---

## 1. Problem & goal

Plan 1 made the **instruction files** (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`) a projection of one neutral source. This plan extends the same source-of-truth model to **skills**, and closes the loop so the system is usable by a non-developer from inside *any* AI:

- **A — Skills sync (forward):** author a skill once, project it into each runtime in that runtime's expected location/format.
- **B — Discovery + startup check:** every AI can *find* the source and *verify it is in sync* at startup.
- **C — Capture-from-chat:** working in any AI, the user says "add this skill" / "add this rule"; the change is written to the source, shown as a diff, AI-reviewed (advisory), human-approved, then committed and projected.

**Overarching goal:** simple and safe for a non-dev. Author/capture in chat; see a diff; approve; it fans out everywhere — with deterministic guardrails, never a probabilistic gate.

## 2. Build order (dependency-driven)

**A → B → C.** B *ships as* a managed skill (depends on A's skill machinery). C *produces* skills and standards (depends on A's projector and Plan 1's instruction projector). Each is an independent implementation slice.

## 3. Verified runtime facts (research, 2026-06-28)

These were empirically verified on the owner's machine, not assumed:

| Runtime | Skill location | Discovery mechanism | Hooks |
|---------|---------------|---------------------|-------|
| **Claude Code** | `~/.claude/skills/<name>/SKILL.md` | Skill tool; surfaced at session start | Yes — `SessionStart` (used in this very session) |
| **Codex** | `~/.codex/skills/<name>/SKILL.md` | file-based; `config.toml`-driven runtime | Not surfaced via CLI — **verify during build**; instructed fallback |
| **Gemini / AntiGravity** | `~/.gemini/skills/<name>/SKILL.md` | **file-copy auto-discovered** (`gemini skills list` confirms an Enabled skill from a hand-copied file); AntiGravity loads a skill by *reading* its `SKILL.md` (`view_file IsSkillFile:true`), **no `activate_skill` tool** | Yes — `gemini hooks` (Claude-compatible, `gemini hooks migrate`) |

**Key correction:** an earlier assumption that Gemini needs a `plugins/<name>/` folder + `plugin.json` manifest is **wrong**. A `SKILL.md` hand-copied to `~/.gemini/skills/<name>/` is auto-discovered and enabled. All three runtimes therefore use the **same file-copy model**, differing only in destination directory. (The current `overlays/gemini.md` "activate_skill" line is incorrect and is fixed in slice A.)

**All three SKILL.md formats are identical:** YAML frontmatter (`name`, `description`) + markdown body, optional `references/` and `agents/` subdirs.

## 4. Locked decisions (this plan)

| # | Decision | Choice |
|---|----------|--------|
| D2-1 | Skill translation model | **Neutral action-language body + per-vendor tool adapter** (`references/<vendor>-tools.md`), as superpowers authors skills. Body copied verbatim; nuance lives in the adapter, authored once per vendor. |
| D2-2 | Existing non-neutral skills | **Neutralize-on-enrollment** with AI assistance + human review. `managed_skills` is explicit opt-in (starts empty). Inherently vendor-specific skills are *not enrolled*. No bulk rewrite. |
| D2-3 | Gemini skill destination | `~/.gemini/skills/<name>/SKILL.md`, **file-copy** (verified). No plugin manifest, no CLI shell-out, no `--consent` security bypass. |
| D2-4 | Discovery | Discovery section projected into every instruction file + a dog-fooded `config-sync` managed skill in every runtime. |
| D2-5 | Startup check | Deterministic via hooks on **Claude + Gemini**; **instructed + last-synced stamp** fallback on Codex until its hook support is verified. |
| D2-6 | Capture safety | Dry-run by default → diff → **deterministic lints are the binding gate** → AI advisory review (non-binding) → human confirm → commit + (push if remote) + project. |
| D2-7 | Durability | Recommend a private git remote at setup; push on capture/project when configured; document "no remote = no off-machine backup" as a hard limitation otherwise. |

## 5. Architecture

### 5.1 Source layout (additions to the repo)

```
skills/<name>/SKILL.md           # canonical neutral skill bodies (action-language)
references/
  claude-code-tools.md           # per-vendor tool adapters (seeded from superpowers)
  codex-tools.md
  gemini-tools.md
config/targets.yaml              # add managed_skills: []; fix gemini skills_dest -> ~/.gemini/skills
src/agent_config_sync/
  skills.py                      # skill projection (A): enumerate, classify, project dir-trees
  discovery.py                   # discovery section render + config-sync skill body (B)
  capture.py                     # capture flow (C): classify, lint, diff, review hook, commit, project
  doctor.py                      # environment + sync health check (F5)
  neutralize.py                  # neutral-language lint + enrollment reconciliation (F1, F6)
hooks/sessionstart-check         # startup check command for Claude/Gemini hooks (B)
```

### 5.2 Capability A — skills projection

A managed skill is projected to each enrolled runtime as a directory tree:
`<skills_dest>/<name>/SKILL.md` (verbatim neutral body) **+** the runtime's
`references/<vendor>-tools.md` bundled alongside, so the AI resolves neutral
actions to its own tools. Reuses Plan 1's machinery extended from single files to
directory trees: allowlist validation, per-skill backup to `.backups/`, per-file
drift guard via `.sync-state.json`, secret-lint, atomic writes, audit log.

**Enrollment (D2-2, F1, F6):** `managed_skills` is empty initially. To enroll a
skill, the tool:
1. Reads the candidate from each runtime where it exists.
2. **Reconciliation (F6):** if the skill body differs across runtimes, refuses to
   enroll until the user picks the canonical source (drift-guard pattern).
3. **Neutral-language lint (F1):** scans for hard-coded vendor tool names / slash
   commands. If found, the AI proposes a neutralized body; the user reviews the
   diff and approves. The approved neutral body is committed under `skills/<name>/`.
4. Adds `<name>` to `managed_skills`. From then on it projects like any managed file.

### 5.3 Capability B — discovery + startup

1. **Discovery section in `_shared/core.md`** — projects into all three instruction
   files: where the source repo is, that global config/skills are *generated*, the
   one command to check/update, and a **last-synced stamp** (cheap drift signal,
   F7).
2. **`config-sync` managed skill** (dog-foods A; authored neutral from the start) —
   any AI invokes it to run `check` / `status` / `project` / `capture` / `doctor`,
   with the workflow documented in plain language.
3. **Startup hook** (`hooks/sessionstart-check`) runs `agent-config-sync check` and
   surfaces drift. Installed into Claude (`SessionStart` in `settings.json`) and
   Gemini (`gemini hooks`). **Scope note:** writing one hook entry into
   `~/.claude/settings.json` is a deliberate, narrow exception to the parent spec's
   "no settings sync" non-goal, owner-approved. Codex uses the instructed
   discovery section + last-synced stamp until its hook support is verified.

### 5.4 Capability C — capture-from-chat

`agent-config-sync capture` (and a phrase pattern the `config-sync` skill
recognizes). Flow when the user says "capture this as a skill" / "add this rule":

1. **Classify & route** — skill → `skills/<name>/SKILL.md`; standard → `_shared/core.md`
   (shared) or `overlays/<vendor>.md` (vendor-specific). The AI proposes routing;
   the diff makes it visible.
2. **Dry-run by default (F3):** nothing is written to source yet.
3. **Deterministic pre-checks — the binding gate:** secret-lint, allowlist,
   neutral-language lint (for skills). A failure aborts regardless of any AI opinion.
4. **Show the diff** of the proposed source change.
5. **AI advisory review (non-binding):** an automatic mini-critique prints an
   APPROVE/DENY recommendation with reasons, rendered *separately* from the diff.
   It reads attacker-influenceable captured content, so it never auto-advances the
   confirm — it only advises.
6. **Human confirm** — one word/click. This is the gate.
7. **On approval:** write to source → `git commit` → `git push` (if a remote is
   configured) → `project` to all runtimes.

### 5.5 `doctor` (F5)

One command prints plain-language health: is the CLI reachable from this runtime,
is the repo present at the expected path, is git healthy, is a remote configured,
and is each runtime in sync. Every other command shares a **failure layer** that
catches known errors and prints one next-step sentence, always pointing at
`.backups/` for recovery.

## 6. Security & safety

- **Deterministic gates only (owner standard).** Secret-lint, allowlist, and
  neutral-language lint are the binding controls on every write. The AI review is
  advisory enrichment — it can never authorize a write (a probabilistic model must
  not gate a security decision).
- **Indirect prompt injection (F3).** Capture and the AI reviewer consume
  untrusted, possibly attacker-authored content that fans out to three agents. The
  human approval checkpoint + deterministic lints are the mitigation; the AI
  verdict is visually segregated and non-advancing. A dedicated entry lands in
  `docs/threat-models/` for the capture surface before C is considered hardened.
- **Least privilege.** Writes remain confined to the `targets.yaml` allowlist;
  skills are opt-in via `managed_skills`; the Gemini path uses plain file-copy
  (no `--consent` suppression of Gemini's native skill-install warning).
- **Auditability.** Every project/capture write is appended to `.sync-audit.log`
  (runtime, kind, force, dest, content hash, stamp) — extended to skill files.
- **Durability (F4).** Single-machine source is a documented risk until a private
  remote is configured; capture/project push when one exists.

## 7. Testing (tied to goals; includes should-fail)

- **A goal test:** enroll + project a neutral skill into a fake 3-runtime tree →
  each runtime gets `SKILL.md` + the correct `references/<vendor>-tools.md`.
- **A reconciliation (should-fail):** enrolling a skill that differs across
  runtimes raises until a canonical source is chosen.
- **A neutral-language lint (should-fail):** a skill body hard-coding a vendor tool
  name is flagged.
- **B test:** discovery section renders into all three instruction files; the
  startup-check command exits non-zero on drift, zero when in sync.
- **C goal test:** capture a skill in a fake repo → diff produced, source unwritten
  pre-approval (dry-run), then on approval committed + projected to all runtimes.
- **C should-fail:** a capture containing a secret aborts at the deterministic gate
  *before* any source write, regardless of AI review.
- **Idempotency / safety:** re-projecting a skill is a no-op; `project` refuses to
  overwrite an out-of-band edited skill file without per-runtime `--force`
  (inherits Plan 1's drift guard).

## 8. Deliverables

- `skills.py`, `discovery.py`, `capture.py`, `doctor.py`, `neutralize.py` with the
  behaviors above and tests tied to goals.
- `references/<vendor>-tools.md` adapters (seeded from superpowers).
- `config-sync` managed skill (the first dog-fooded neutral skill).
- `hooks/sessionstart-check`; Claude `settings.json` + Gemini hook wiring.
- `config/targets.yaml`: `managed_skills` enrollment + corrected `gemini skills_dest`.
- Corrected `overlays/gemini.md` (skill-loading mechanism).
- `docs/threat-models/` entry for the capture surface.
- README/AGENTS/LIMITATIONS updates for skills, discovery, capture, and the
  no-remote durability limitation.

## 9. Out of scope / future

- Codex deterministic startup hook (pending hook-support verification).
- `git push` automation requires a remote the owner has not yet created.
- Bidirectional/auto-merge of skills (still rejected — human gate at capture).
- Additional runtimes (Copilot, pi) — adapters exist in superpowers; additive via
  `targets.yaml` + `managed_skills`.
