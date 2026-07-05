# HANDOFF — agent-config-sync

> **Read this first.** Then verify live repository and runtime state before
> trusting this snapshot. Last verified: 2026-07-04.

## Current status

- `main` tracks `origin/main`.
- v1 is feature-complete: forward projection, managed skills, capture, promote,
  startup hooks, backup pruning, mutation locking, drift protection, and audit
  logging are implemented.
- The full local suite passed on 2026-07-03: **181 passed**.
- A Codex-run repo-standards + critique audit (2026-07-03) independently
  reproduced the suite and found two enforcement gaps, both now fixed: managed
  bodies are neutral-linted at projection (not only at enrollment), and
  wrapped slash-commands naming managed skills (e.g. backticked) are detected.
- Claude, Codex, and Gemini instructions are generated from this repository.
- Startup drift-check hooks are installed for all three runtimes.
- 23 global skills are enrolled under `managed_skills` (2026-07-03 sweep of
  `~/.claude/skills`): 17 verbatim (lint-clean, including `config-sync`) and 6
  after neutralization of slash-command references (`feature-factory`,
  `overseer`, `test-design`, `threat-model`, `threat-model-treatment`,
  `workflow-lesson-gen`). Only user-global skills are canonical; project-local
  and plugin skills are never enrolled.
- `notebooklm` is deliberately NOT enrolled: its runtime directory is a cloned
  repository with a virtual environment and browser/auth state, and its body
  depends on companion scripts the projector cannot carry. It needs a clean
  source package before enrollment.
- The divergent Codex variant of `repo-standards` was replaced by the canonical
  Claude body via a scoped `project codex --force`; the prior variant is
  recoverable from `.backups/`.
- Live pickup verified in all three runtimes: Codex ran `critique` and a full
  `repo-standards` + companion-file audit (2026-07-03, cycle 2 clean);
  Gemini/AntiGravity validated promote, fixed its skills path
  (`~/.gemini/config/skills`), and installed hooks incl. a git pre-commit
  `check`.
- Publication cleanup pass (2026-07-04): project CLAUDE.md added, logo in
  README, REPO_AUDIT.md scorecard, examples/, Lesson12 operator guide,
  stale-claim sweep across lessons/TRADEOFFS/implementation plan.
- Fourth-runtime support is specced with placeholders, PROPOSED / NOT
  SCHEDULED (`docs/superpowers/specs/2026-07-04-fourth-runtime-support-spec.md`);
  no code was changed for it.
- V2 FULLY COMPLETE 2026-07-04 incl. S7 (eval dataset) and S8 (Tier 3 as the
  operator-invoked draft-proposals skill; eval 12/12; unattended variant
  stays gated by operator decision).
- Earlier same-day status: every buildable slice done (S1-S6, S9 overlap
  detector, S3 live drills documented in EVALUATION with method and proof
  rationale; Lesson13 ambient-watcher lesson added). Remaining work is
  ONLY the time-gated Tier 3 (S7 eval dataset, S8 agent) - gate: watcher
  stable >=2 weeks + one real drift resolved via notification workflow.
- Tier 2 ambient watcher LIVE 2026-07-04: `watch-once` CLI + balloon wrapper,
  scheduled task `agent-config-sync-sense` (daily 09:00, verified Ready);
  Tier 2->3 gate clock started.
- V2 MERGED to main 2026-07-04; sense hooks are LIVE in all three runtimes
  (Gemini needed the manual settings.json fallback — migrate would not update
  an existing entry). All 12 unmanaged skills enrolled; managed set is 35;
  `sense` exits 0. See docs/WORKING_CHECKLIST.md for slice statuses (S3 awaits
  operator live verification; S6 watcher build is fully unblocked; S9
  overlap-detector added).
- Branch `v2-sense-automation` (now merged): Tier 1 session-start sensing —
  read-only `sense` command (per-file drift direction, exact resolution
  commands, unmanaged-skill discovery, `sense_ignore_skills` exclusions),
  hooks now install `sense` replacing the old `check` command, AI-mediated
  confirm instruction added to `_shared/core.md`. Tiers 2-3 (ambient watcher,
  proposal agent) specced only:
  `docs/superpowers/specs/2026-07-04-ambient-automation-spec.md`. Live
  runtime instruction files were re-projected from this branch's core.md; if
  the branch is abandoned, check out main and run `agent-config-sync project`
  to revert them.
- Companion-file projection shipped 2026-07-03: text companions under
  `skills/<name>/` fan out to every runtime through the neutral-language and
  secret gates (`skills.companion_files`). `repo-standards` lessons and all 23
  `building-an-exo` companions are enrolled and projected.
- Fixed: files byte-identical at first projection now get a baseline hash, so
  a later source edit is a clean update instead of false drift
  (`skills.project_skills`). Fixed: `lesson-gen` had a UTF-8 BOM that broke
  frontmatter parsing in skill listings; the source body is now BOM-free.

## V2 build state and continuation checklist

V2 = ambient automation, built in tiers on branch `v2-sense-automation`.
Specs: `docs/superpowers/specs/2026-07-04-ambient-automation-spec.md`
(Tiers 2-3) and `2026-07-04-fourth-runtime-support-spec.md` (related, separate).

**V2 is COMPLETE (2026-07-04).** All slices S1-S6 and S9 are done and merged
to main; S3 live drills are documented with method and proof rationale in
`docs/EVALUATION.md`. The authoritative per-slice record (statuses, acceptance,
what shipped) is **`docs/WORKING_CHECKLIST.md`** — do not re-derive from the
historical steps that used to live here.

**All slices are DONE (2026-07-04), including S7/S8.** Tier 3 shipped as the
operator-invoked `draft-proposals` skill after passing its eval 12/12; the
operator scoped (did not remove) the 2-week gate - it still governs any
future UNATTENDED trigger variant. Nothing remains open in V2.

## Current operating workflow

```powershell
agent-config-sync doctor
agent-config-sync status
agent-config-sync check
agent-config-sync project --dry-run
```

After an intentional source edit, run `agent-config-sync project`, then
`agent-config-sync check`.

Enroll runtime-local skills one at a time:

```powershell
agent-config-sync enroll <name> --from claude
agent-config-sync project
agent-config-sync check
```

Do not bulk-copy `~/.claude/skills` into the repository. Secret detection and
the vendor-neutral language lint are binding gates; resolve failures in the
canonical body instead of bypassing them.

---

## Legacy implementation history

The remaining sections are retained as historical implementation context. Their
task lists and test counts are not current status; the block above is canonical.

## 1. What this project is

A vendor-neutral **source of truth** that projects AI-runtime config (instruction
files, and — once Plan 2 lands — skills) into Claude Code, Codex, and
Gemini/AntiGravity, safely and idempotently.

- **Source** lives in this repo: `_shared/core.md` (neutral standards) +
  `overlays/{claude,codex,gemini}.md` (per-vendor).
- **`project`** renders `header + core + overlay` and writes each runtime's global
  instruction file. Guardrails: allowlist, secret-lint, drift guard, atomic writes,
  per-file backups, `.sync-state.json` hashes, append-only `.sync-audit.log`.
- Design docs: `docs/superpowers/specs/`. Implementation plans:
  `docs/superpowers/plans/`.

## 2. Durable anchors (source-of-truth files)

| File | What it is |
|------|-----------|
| `HANDOFF.md` (this file) | Start here |
| `docs/superpowers/specs/2026-06-27-cross-runtime-sync-design.md` | Parent design (Plan 1+2+3 vision) |
| `docs/superpowers/specs/2026-06-28-skills-discovery-capture-design.md` | **Plan 2 design — awaiting owner review** |
| `docs/superpowers/specs/2026-06-28-reverse-promote-design.md` | **Plan 3 design — awaiting owner review** |
| `docs/superpowers/plans/2026-06-27-agent-config-sync-forward.md` | Plan 1 implementation plan (DONE) |
| `config/targets.yaml` | Security allowlist: what may be written, where |
| `README.md` / `SECURITY.md` / `docs/ARCHITECTURE.md` / `docs/LIMITATIONS.md` | Repo standards |

## 3. ⚠️ Critical live-state facts (do not skip)

1. **The owner's REAL global config is now GENERATED by this tool.**
   `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md` each carry a
   `GENERATED — DO NOT EDIT HERE` header and were projected on 2026-06-28.
   - **Edit the source, not the live files.** Change `_shared/core.md` or an
     overlay, then `project`. A hand-edit to a live file is refused by the drift
     guard (needs per-runtime `--force`, which backs up first).
   - **Originals are backed up** at `.backups/<runtime>/20260628T114805/`.
2. **Private git remote EXISTS** (added 2026-06-28): `origin` →
   `https://github.com/mwill20/agent-config-sync-public` (this mirror; the
   source carries the owner's full standards, so it must never be made public).
   `main` and `feat/forward-projection` are pushed. Off-machine backup is in place.
3. **Git author** is `Claude (agent-config-sync)`. **Commit/push only when asked.**
4. **`.gitignore`d runtime artifacts:** `.sync-state.json`, `.sync-audit.log`,
   `.backups/` (backups may contain real config — never commit).

## 4. How to work here

- **Validation command (use this — plain `pytest` is broken in this env):**
  ```
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
  ```
  A broken *global* `web3` pytest plugin poisons collection otherwise. Expect
  **57 passing**.
- **Run the CLI:** `python -m agent_config_sync {project|check|status} [...]`
  (console script `agent-config-sync` is installed editable, resolving to the
  main checkout's `src/`).
- **This is a background-job repo: isolate edits in a git worktree.** File edits
  in the shared checkout are rejected. Use `EnterWorktree`, work, commit, then
  `ExitWorktree` + `git merge --ff-only <worktree-branch>` onto
  `feat/forward-projection`, then remove the worktree. The worktree branches from
  HEAD (no remote), so it carries existing commits.
  - **Inside a worktree, `python -m agent_config_sync` needs `PYTHONPATH=src`**
    (the editable install points at the main checkout, not the worktree).
- **Per-task TDD** (Plan 1 style): write the failing test → confirm red → minimal
  impl → green → commit. Every consequential path gets a should-fail test.

## 5. Status checklist

### ✅ Done (Plan 1 — forward projection of instruction files, fully built & verified)
- [x] Scaffold, hermetic `fake_env` fixture, pytest config
- [x] `render()` — header + core + overlay (deterministic)
- [x] `secrets.py` — credential lint (hardened: unquoted markdown + slack/github_pat/stripe prefixes)
- [x] `fsutil.py` — atomic_write, backup, sha256, stamp
- [x] `state.py` — `.sync-state.json` last-projected hashes
- [x] `config.py` — allowlist validation (dests AND overlay source paths contained)
- [x] `project.py` — forward projection: drift guard, per-runtime `--force` + multi-drift guard (exit 4), secret abort, idempotency, incremental state save, audit log
- [x] `check.py` / `status.py` / `cli.py` / `__main__.py` — exit codes 0/1/2/3/4
- [x] `audit.py` — append-only `.sync-audit.log`
- [x] `hooks/pre-commit` (NOT installed into `.git/hooks` — see below)
- [x] Repo standards: README, SECURITY, AGENTS, ARCHITECTURE, LIMITATIONS, .env.example, .gitattributes
- [x] Source seeded from the owner's real CLAUDE.md (neutral core + overlays); **projected live** to all three runtimes; in-sync, backed up, audited
- [x] All critique findings from Plan 1 review resolved (audit log, secret lint, incremental state, per-runtime force, overlay containment)
- [x] 57 tests passing

### ✅ Done (Plan 2 — Slice A: skills projection + enrollment, built & merged 2026-06-28)
- [x] `neutralize.py` — vendor-term lint (`find_vendor_terms`) + cross-runtime reconciliation (`read_skill_variants`/`reconcile_skill`)
- [x] `skills.py` — `project_skills()` fans each managed skill (`SKILL.md` + per-runtime adapter) to all runtimes; drift guard, backups, secret-lint, audit
- [x] `enroll.py` — neutral+secret-gated enrollment; comment-safe `managed_skills` rewrite (must stay last key)
- [x] CLI `enroll`; `project`/`check`/`status` now cover skills (exit map drift→2/secret→3/force→4)
- [x] Fixed wrong `activate_skill` line in `overlays/gemini.md`; seeded `references/<vendor>-tools.md` from superpowers
- [x] Docs (README/AGENTS/LIMITATIONS), capture/promote threat-model **stub** (`docs/threat-models/2026-06-28-capture-promote-surface.md`)
- [x] **79 tests passing**; merged to `feat/forward-projection`; pushed; PR #1 open
- [x] Private remote created (durability) — see §3.2

### ✅ Done (Slice A critique — fixed 2026-06-28, cycle 2)
- [x] **F1** `cli.py` now catches `ConfigError` → clean **exit 3** (was a raw traceback)
- [x] **F2** neutral-language lint broadened — `<Name> tool` set, `mcp__*`, `TodoWrite`/`subagent_type`, etc.; ordinary prose not flagged
- [x] **F3** `enroll.update_managed_skills` refuses to rewrite if `managed_skills` isn't the last key (prevents silent data loss)
- [x] **86 tests passing**; all fixes re-verified via live CLI run (see `docs/EVALUATION.md`)
- [x] `docs/EVALUATION.md` — durable test/run log (suite history + live runs)
- [ ] `/lesson-gen` — **deferred until project feature-complete** (after Slices B/C + Plan 3)

### ✅ Done (Plan 2 — Slice B part 1: discovery + config-sync skill, 2026-06-28)
- [x] **B-1** "## Keeping configs in sync" discovery section in `_shared/core.md` → projects into all 3 instruction files
- [x] **B-2** neutral dog-fooded `config-sync` skill (`skills/config-sync/SKILL.md`); body passes the neutral-language lint
- [x] **B-3** `config-sync` enrolled in real `targets.yaml`; HANDOFF §8 hook facts corrected; docs updated
- [x] **90 tests passing**
- [x] Owner-run apply DONE: discovery section + `config-sync` skill projected to live runtimes (verified `check` clean; config-sync visible in-session)

### ✅ Done (Plan 2 — Slice B3: startup-hook installation, 2026-06-28)
- [x] `settingsedit.install_claude_hook` — merge-safe, idempotent, backup, parse-guarded Claude `settings.json` writer (the one allowlist exception)
- [x] `hooks/sessionstart-check` wrapper; CLI `install-hooks` (Claude `settings.json` merge + `gemini hooks migrate` + **Codex `config.toml` `[[hooks.SessionStart]]` merge**) — all three runtimes wired & verified live
- [x] `docs/threat-models/2026-06-28-settings-write-surface.md` (STRIDE; threats→code pointers)
- [x] **96 tests passing**
- [x] Owner-run apply: `agent-config-sync install-hooks` (writes live `settings.json`; backs up first) — NOT yet run on live config

### 🟡 In progress / awaiting owner
- [ ] **Plan 2 design spec — written, AWAITING OWNER REVIEW** before the implementation plan is generated. (`docs/superpowers/specs/2026-06-28-skills-discovery-capture-design.md`)
- [x] **Plan 3 design spec — APPROVED** (`docs/superpowers/specs/2026-06-28-reverse-promote-design.md`).
- [ ] Open owner decisions (see §7)

### ❌ Not started
- [x] **Plan 2 / Slice A implementation plan — WRITTEN 2026-06-28** (`docs/superpowers/plans/2026-06-28-plan2-skills-slice-a.md`). 7 tasks, TDD, grounded in the live engine. Ready to execute.
- [ ] **Plan 2 / Slice B & C implementation plans** — write after Slice A lands and the Gemini `hooks` / Claude `settings.json` SessionStart formats are verified on-machine (HANDOFF §8 flags these as verify-during-build; don't pre-fabricate schemas).
- [x] **Plan 2 build — Slice A DONE** (see Done section above); B (discovery/startup) → C (capture) follow
- [x] **Plan 3 implementation plan** — COMPLETED.
- [x] **Plan 3 build** (reverse `promote`) — COMPLETED; `promote` command is fully functional.
- [ ] Install `hooks/pre-commit` into `.git/hooks/` (deferred; do after merge so the package is importable)
- [ ] Merge PR #1 `feat/forward-projection` → `main` (owner's call)
- [x] Create a private git remote (durability) — DONE 2026-06-28 (§3.2)
- [ ] Complete the `docs/threat-models/` capture/promote entry (stub exists — finish before Slice C)
- [ ] `Lessons/` educational track (parent spec deliverable, post-build)

### ➡️ Immediate next action
**Slice A is built/merged/pushed (PR #1).** Next: verify the Gemini `hooks` and
Claude `settings.json` SessionStart formats on-machine (HANDOFF §8), then invoke
`writing-plans` for **Slice B** (discovery + startup check), then Slice C
(capture). Owner still to review Plan 2/3 specs for B/C scope and merge PR #1.
Original `writing-plans` note retained below for reference:
plan (Plan 1 format), built A → B → C; then the Plan 3 plan (promote, on top of
capture). Execute slices TDD.

## 6. "Are all specs written?" — precise answer

| Item | Design spec | Impl plan | Built |
|------|:-----------:|:---------:|:-----:|
| Plan 1 — instruction-file forward projection | ✅ | ✅ | ✅ |
| Plan 2 — skills + discovery + capture | ✅ (awaiting review) | ❌ (next step) | ❌ |
| Plan 3 — reverse `promote` | ✅ | ✅ | ✅ |

So: **design specs are now written for all three plans.** Plans 1, 2, and 3 are fully
specced and built. The `promote` command (Plan 3) is fully operational.

## 7. Owner decisions — RESOLVED 2026-06-28 (Plan 2 design finalized)

1. **Incremental enrollment** — ✅ CONFIRMED. `managed_skills` starts empty; skills
   are enrolled one at a time with AI-proposed neutralization + human review. No
   bulk rewrite of the existing skills.
2. **`settings.json` hook** — ✅ APPROVED. Capability B writes one `SessionStart`
   hook entry into `~/.claude/settings.json` (deliberate, narrow exception to "no
   settings sync"). Gemini gets the equivalent via `gemini hooks`.
3. **Capture friction** — ✅ AS SPECIFIED. Dry-run by default → deterministic lints
   bind (secret/allowlist/neutral) → AI review advisory only → human confirm before
   commit + project.
4. **Durability** — ✅ FOLD INTO PLAN 2 BUILD. A setup step creates/configures a
   private git remote; capture/project push when one is configured.

With these resolved, Plan 2's design is final → proceed to `writing-plans`.

## 8. Plan 2 verified runtime facts (research done 2026-06-28 — do NOT re-derive)

Empirically tested on this machine; saves the next agent the investigation:

- **Skill format is identical** across all three: `<name>/SKILL.md` with YAML
  frontmatter (`name`, `description`) + body, optional `references/` & `agents/`.
- **Destinations (all file-copy, same model):**
  - Claude: `~/.claude/skills/<name>/SKILL.md`
  - Codex: `~/.codex/skills/<name>/SKILL.md`
  - Gemini: `~/.gemini/skills/<name>/SKILL.md` — **VERIFIED** a hand-copied
    `SKILL.md` is auto-discovered & enabled (`gemini skills list` confirmed).
    The earlier "Gemini needs a `plugins/<name>/` + `plugin.json` manifest"
    assumption is **WRONG** — do not use it.
- **Gemini CLI** (`gemini` on PATH): `gemini skills {list|install|enable|disable|uninstall}`,
  `gemini extensions`. AntiGravity (`agy`) loads a skill by **reading its `SKILL.md`** —
  there is **no `activate_skill` tool**.
- **`overlays/gemini.md` WRONG line** ("Load skills with `activate_skill`") —
  ✅ FIXED in Slice A.
- **Startup hooks (VERIFIED on-machine 2026-06-28 — corrects earlier wording):**
  - **Claude** ✅ `~/.claude/settings.json` →
    `hooks.SessionStart[].hooks[] = {type:"command", command:"…"}`. A SessionStart
    hook (`skill_compass.py`) + a `Stop` hook ALREADY EXIST — a writer must
    **merge/append**, never overwrite.
  - **Gemini** ⚠️ there is **NO** `gemini hooks list/add` — the only subcommand is
    `gemini hooks migrate --from-claude`, which converts Claude Code hooks into
    Gemini's own `~/.gemini/settings.json` format. Use `migrate`; do not hand-write
    Gemini's hook schema. (Earlier "`gemini hooks` Claude-compatible" wording was
    misleading.)
  - **Codex** ✅ DOES support hooks — `codex_hooks` is a **stable, default-on**
    feature (`codex features list`). It is **config-driven** (no `hooks` CLI
    subcommand, which is why the earlier "no hooks" note was WRONG): add a
    `[[hooks.SessionStart]]` array-of-tables to `~/.codex/config.toml`
    (`matcher`, then `[[hooks.SessionStart.hooks]]` with `type="command"`,
    `command`, `timeout`, `statusMessage`). Verified against the official docs
    (developers.openai.com/codex/hooks) and applied live. `install_codex_hook`
    appends merge-safely (preserves `notify` + `[plugins.*]`).
  - These facts also live in `docs/superpowers/plans/2026-06-28-plan2-sliceB-discovery.md`
    for the upcoming **B3 (hook installation)** plan — writing `settings.json` is the
    first write outside the `targets.yaml` allowlist (new trust boundary → needs a
    threat-model touch).
- **Per-vendor tool adapters already exist** to seed `references/`:
  superpowers `using-superpowers/references/{claude-code,codex,gemini,antigravity}-tools.md`.
- **Existing skills are NOT neutral** (e.g. `architect`, `critique` reference the
  Skill tool / slash commands) and the same skill has **drifted** across runtimes
  (`repo-standards` differs Claude vs Codex) — hence neutralize-on-enrollment + the
  reconciliation gate (Plan 2 D2-2 / F1 / F6).

## 9. Memory & conventions

- Project memory: machine-local assistant memory (not part of this mirror)
  (`global-config-is-generated.md`, `pytest-plugin-autoload-workaround.md`, `MEMORY.md` index).
- Owner is a Cybersecurity Analyst II → Engineer II; security-first, deterministic
  gates over probabilistic ones, TDD with should-fail cases, explain the "why".
  Their full standards are now in `_shared/core.md`.
