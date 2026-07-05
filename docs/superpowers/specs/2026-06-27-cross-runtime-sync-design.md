# Design Spec — agent-config-sync

**Status:** Approved design (pre-implementation) — superseded in part by shipped scope; see "Scope evolution" below
**Date:** 2026-06-27
**Author:** Brainstormed collaboratively (owner + Claude)
**Next step:** writing-plans → implementation slices

---

## Scope evolution since this spec (added 2026-07-01)

This is the original pre-implementation design. Two things below no longer match
what shipped — recorded here so the spec is not read as current truth:

- **Hook/settings sync moved INTO scope.** §3 Non-Goals and §11 list "syncing of
  MCP config, settings.json, hooks, permissions" as out of scope for v1. The
  shipped `install-hooks` command *does* write startup drift-check hooks into
  Claude `settings.json` (merge-safe JSON writer), Codex `config.toml` (merge-safe
  TOML writer), and Gemini (delegated to `gemini hooks migrate --from-claude`).
  MCP config and permissions remain out of scope. The dedicated threat model is
  `docs/threat-models/2026-06-28-settings-write-surface.md`.
- **Command name.** §6 uses `sync project` / `sync check` / `sync promote`. The
  shipped console script is `agent-config-sync <subcommand>`. The command surface
  also grew beyond the four here to include `status`, `doctor`, `enroll`,
  `capture`, `install-hooks`, and `prune-backups`. See `README.md` for the
  authoritative command list and exit codes.

Everything else in this spec still reflects the design intent.

---

## 1. Problem

Three AI coding runtimes run side-by-side in VS Code on this machine:

- **Claude Code** — instruction file `~/.claude/CLAUDE.md`; skills in `~/.claude/skills/`
- **Codex** — instruction file `~/.codex/AGENTS.md`; skills in `~/.codex/skills/`
- **Gemini / AntiGravity** — instruction file `~/.gemini/GEMINI.md`; skills under `~/.gemini/`

Their instruction files and skills have drifted: `CLAUDE.md` is rich (~21 KB), `GEMINI.md` is empty, `AGENTS.md` is a stub. Each runtime also exposes a **different tool API** (`Skill` tool vs `apply_patch`/`shell` vs `activate_skill`), so a skill authored for one cannot be copied verbatim to another.

The owner wants a single source of truth that keeps the "like" content equalized across all three, and — critically — a way for a learning made *inside any runtime* to flow back to that source and then out to the others ("learn something in Gemini, get it in Claude").

## 2. Goals

- One **vendor-neutral source of truth** that even Claude derives from.
- **Forward projection:** generate each runtime's instruction file and managed skills from the source, on demand.
- **Reverse promotion:** lift a change made in any runtime back into the source, with a human diff review deciding what is shared vs vendor-specific.
- **No silent drift:** a read-only check fails a commit when a derived file is stale.
- **No clobbering:** projection never overwrites an un-promoted runtime change.
- Deterministic, auditable, least-privilege; aligned with the owner's security standards.

## 3. Non-Goals

- No automatic bidirectional merge (explicitly rejected — no source of truth at conflict time).
- No live file-watcher / background daemon in v1.
- No syncing of MCP config, `settings.json`, hooks, or permissions in v1 (instruction files + skills only).
- No management of skills the tool does not explicitly own (the 23 personal Claude skills and 26 Azure skills in `~/.agents/` are left untouched unless enrolled).

## 4. Locked decisions

| # | Decision | Choice |
|---|----------|--------|
| D-1 | Sync scope | Instruction files **+ skills** |
| D-2 | Reverse flow | **Explicit `promote` with diff review** (no auto-merge) |
| D-3 | Forward trigger | **Manual `sync` command + read-only stale-check pre-commit hook** |
| D-4 | Content model | **Neutral core + per-vendor overlays** |
| D-5 | Source of truth home | Dedicated git repo `agent-config-sync`; runtimes are derived targets |
| D-6 | Language/stack | Python 3 stdlib + `pyyaml==6.0.2`; tests `pytest==8.3.4` |

## 5. Architecture & repo layout

```
agent-config-sync/
├── _shared/core.md                     # neutral, vendor-agnostic standards
├── overlays/
│   ├── claude.md                       # Skill tool, slash commands
│   ├── codex.md                        # AGENTS.md extras, apply_patch notes
│   └── gemini.md                       # activate_skill, GEMINI.md extras
├── skills/<name>/SKILL.md              # neutral skill bodies (canonical copies)
├── references/
│   ├── claude-tools.md                 # tool-API adapters (sourced from superpowers)
│   ├── codex-tools.md
│   └── gemini-tools.md
├── config/targets.yaml                 # allowlist: managed files + skills + destination paths
├── src/agent_config_sync/              # the CLI package
├── hooks/pre-commit                    # runs `sync check`
├── tests/
├── docs/
│   ├── superpowers/specs/              # this spec
│   ├── threat-models/                  # poisoned-core threat model (later)
│   ├── ARCHITECTURE.md  LIMITATIONS.md
├── Lessons/00_Index.md                 # educational track (generated via lesson-gen post-build)
├── SECURITY.md  README.md  .env.example  AGENTS.md
```

A derived instruction file is rendered as: `generated-header + core.md + overlays/<vendor>.md`.

### Trust boundary

`config/targets.yaml` is the security-critical allowlist. The tool may write **only** to paths declared there. It enumerates, per runtime: the destination instruction-file path, the destination skills directory, and the explicit list of skill names under management.

## 6. Components — CLI surface

Single entry point with four subcommands:

- **`sync project [--dry-run] [--force]`** — render each derived instruction file and copy managed skills into each runtime. Writes a `GENERATED — do not edit here` header into every derived file. Refuses to overwrite a target with un-promoted drift unless `--force`.
- **`sync check`** — read-only. Exits non-zero if any managed target differs from what `project` would produce. Used by the pre-commit hook and CI.
- **`sync promote <runtime> [path]`** — diffs the live runtime file/skill against the projected version; for each divergence, the user assigns it to **core** (flows everywhere), **that vendor's overlay** (stays local), or **a neutralized skill** under `skills/`.
- **`sync status`** — drift report across all three runtimes.

### Skill neutralization

A canonical skill body in `skills/<name>/SKILL.md` is written in platform-neutral action language and never hard-codes a runtime tool name. Each runtime resolves actions through its own `references/<vendor>-tools.md` adapter (reused from the superpowers plugin). This is how one skill body remains valid across three tool APIs.

## 7. Data flow

**Forward:** edit `core.md` / an overlay / a skill → `sync project` → derived files re-rendered, managed skills copied out → `git commit` (pre-commit `check` passes because content was just synced).

**Reverse (key use case):** edit `~/.gemini/GEMINI.md` or add a skill while working in Gemini → `sync promote gemini` → tool shows the divergence → user tags it **shared** → it lands in `core.md` → `sync project` propagates it into `CLAUDE.md` and `AGENTS.md`. A vendor-specific tweak instead lands in `overlays/gemini.md` and stays put.

## 8. Safety, security & error handling

- **No clobbering learnings:** `project` refuses to overwrite a target with un-promoted drift; instructs the user to `promote` or pass `--force`. Primary guardrail for the reverse-flow scenario.
- **Allowlist writes only:** the tool writes solely to paths declared in `targets.yaml`. Atomic writes (temp file + rename).
- **Backups:** because `~/.codex` and `~/.gemini` are not git repos, every overwrite is first copied to `.backups/<runtime>/<timestamp>/` inside the repo.
- **Secret lint:** before writing, content is scanned for credential/key patterns and rejected. Instruction files must never carry secrets.
- **Audit log:** every `project`/`promote` appends actor / timestamp / files-changed to `sync.log`, on top of git history.
- **Input validation:** `targets.yaml` paths are validated (must resolve under known runtime roots) before any write.

### Security framing

These files steer three AI agents. A poisoned `core.md` is an **indirect prompt-injection vector that fans out to all three runtimes simultaneously**. The explicit promote-with-review gate (D-2) is therefore a security control, not only a UX choice. A dedicated threat model lands in `docs/threat-models/` before the promote path is considered hardened.

## 9. Testing (tied to goals; includes should-fail cases)

- **Forward goal test:** project into a temp fake-runtime tree → files exactly match expected render.
- **Reverse goal test:** simulate a new skill/edit in a fake Gemini dir → `promote` lifts it to core → re-project → assert it now appears in the **Claude** and **Codex** outputs (proves the literal requirement).
- **Idempotency:** running `project` twice yields no second-run changes; `check` passes after `project`.
- **Should-fail / safety:**
  - `project` refuses to overwrite un-promoted drift.
  - `check` exits non-zero when a target is stale.
  - secret-laden content is rejected before write.
  - a write targeting a path outside the allowlist is refused.

## 10. Deliverables

- Working CLI (`project`, `check`, `promote`, `status`) with the safety behaviors above.
- `config/targets.yaml` enrolling the three runtimes with an initial managed set.
- Pre-commit hook running `sync check`.
- Repo standard files: `README.md` (easy-to-follow, design-stage until built), `SECURITY.md`, `docs/ARCHITECTURE.md`, `docs/LIMITATIONS.md`, `AGENTS.md`, `.env.example`.
- `docs/threat-models/` entry for the poisoned-core surface.
- `Lessons/` educational track generated via `lesson-gen` **after the first implementation slice exists** (cannot be generated against an empty repo).

## 11. Out of scope / future

- MCP config, settings, hooks, permissions sync.
- Live file-watcher trigger.
- Additional runtimes (Copilot, pi) — adapters exist in superpowers; enrollment is additive via `targets.yaml`.
- A `git pre-commit` mode that auto-regenerates instead of only checking.
