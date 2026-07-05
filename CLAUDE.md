# CLAUDE.md — agent-config-sync

Project context for AI assistant sessions in this repository. Read HANDOFF.md
next for current status; verify live state before trusting either file.

## What this repository is

The single source of truth for AI assistant configuration across three
runtimes. `_shared/core.md` + `overlays/<runtime>.md` generate the global
instruction files (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`,
`~/.gemini/GEMINI.md`); `skills/<name>/` holds neutral skill bodies plus text
companions that project to each runtime's skills directory. The Python CLI
(`src/agent_config_sync/`) does the projection, drift detection, enrollment,
capture, and reverse promotion.

## Hard rules

- Never hand-edit generated runtime files. Edit the source here, then run
  `agent-config-sync project`. Runtime-side edits come back via
  `agent-config-sync promote <runtime>`.
- Security gates are binding: secret scan, neutral-language lint (bodies and
  companions, at enrollment and projection), path containment, drift refusal,
  text-only companion allowlist. Fix content to pass a gate; never weaken the
  gate.
- Only user-GLOBAL skills and standards belong in this repo. Project-local and
  plugin skills are never enrolled.
- `managed_skills` must remain the last top-level key in `config/targets.yaml`.
- A blanket `--force` is refused when more than one target drifted; scope it
  to one runtime (`project claude --force`).
- Commit and push only when the operator asks. This is the sanitized public
  mirror; the operator's full standards live in a private original.

## Validation

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
agent-config-sync check          # exit 0 = all runtimes in sync
```

Plain `pytest` fails here: a globally installed plugin poisons collection.
A git pre-commit hook runs `agent-config-sync check` on every commit.

## Key paths

| Path | Role |
|---|---|
| `_shared/core.md`, `overlays/` | instruction-file source |
| `skills/<name>/` | skill bodies + text companions (source of truth) |
| `config/targets.yaml` | runtime destinations + managed-skill allowlist |
| `references/` | per-runtime tool adapters (only vendor-specific payload) |
| `src/agent_config_sync/` | CLI implementation |
| `docs/EVALUATION.md` | append-only validation log; update after suites |
| `docs/threat-models/` | STRIDE models; update when a surface changes |
| `.backups/` (gitignored) | automatic pre-overwrite snapshots |

## Working conventions

- Every consequential change lands with tests including at least one
  should-fail case, and updates the relevant docs (README, docs/, HANDOFF.md,
  threat models, EVALUATION log) in the same commit.
- Docs describe the current state; superseded audits get a banner, not a
  rewrite. Test counts in docs are baselines that grow; EVALUATION.md is the
  running log.
- Keep README free of em dashes; prefer plain punctuation there.

