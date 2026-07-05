# Architecture

## System overview

`agent-config-sync` is a local CLI that keeps AI runtime instruction files and
managed skills synchronized from one repository-owned source of truth.

```text
                    SOURCE OF TRUTH (this repo)
   _shared/core.md + overlays/<runtime>.md + skills/<name>/SKILL.md
                            |         ^
              project / project_skills   promote / capture --confirm
                            v         |
      ~/.claude, ~/.codex, ~/.gemini instruction files + skill directories
                            |
        +-------------------+-------------------+-------------------+
        |                   |                   |                   |
  session start        daily (no AI       on demand, any        on demand,
  hook: sense           session open):     MCP client:            operator-
  (read-only) ->        watcher.watch_once mcp-serve exposes      invoked skill:
  AI names findings,    -> pending.json    sense/check/status     draft-proposals
  asks operator ->      (advisory) +       tools (read-only)      -> proposal
  approved command      notification                              artifacts
  writes back to                                                   (scratch only;
  source (loop above)                                              operator applies)
```

Managed skill projection is not a recursive runtime mirror. The payload is
`SKILL.md`, the selected runtime adapter under `references/`, and reviewed
text companion files stored under `skills/<name>/` in the source (allowlist:
`.md .txt .json .yaml .yml .toml`). Companions pass the same neutral-language
gate as bodies plus the secret scan at projection time; hidden paths are
skipped; a companion may not shadow a runtime adapter filename. Scripts and
other executable content remain outside the source-to-runtime contract, as do
runtime-side environments, caches, and state.

## Components

| Component | Responsibility |
|---|---|
| `config.py` | Load `config/targets.yaml`, validate runtime allowlists, validate `managed_skills` and `sense_ignore_skills` names |
| `sense.py` | Read-only session-start sensing: classify per-file drift direction from dry-run plans, discover unmanaged skills, emit findings with exact resolution commands (brief for AI/human, `--json` for automation); converts gate errors into findings so the session hook never crashes |
| `watcher.py` | One daily ambient cycle: run the sense scan, persist advisory `pending.json` (HITL retention with `resolved` block), return notification text; read-only by construction, never raises |
| `mcp_server.py` | Read-only MCP stdio server (sense/check/status tools); no mutating function is importable from it, enforced by test |
| `overlap.py` | Read-only similarity report (body/description ratios) between a candidate skill and the managed set; triage signal only — redundancy judgment stays with the operator |
| `validation.py` | Central skill-name grammar and final resolved-path containment checks |
| `render.py` | Deterministically compose generated instruction content |
| `project.py` | Project instruction files with drift guard, backups, state, and audit logging |
| `skills.py` | Project the allowlisted skill payload: canonical `SKILL.md` plus one runtime adapter reference |
| `capture.py` / `enroll.py` | Bring reviewed standards or skills into the source, with secret/neutral lint, backups, and source audit records |
| `promote.py` | Classify runtime divergence and lift append/delete/replace edits back to a selected source target |
| `settingsedit.py` | Merge-safe hook writers for Claude and Codex config files, including bad-shape validation |
| `fsutil.py` | Atomic writes, collision-safe backups, explicit backup-prune planning/execution |
| `lock.py` | Repo-scoped mutation lock with owner metadata and fail-closed stale-lock behavior |
| `cli.py` | Operator interface, exit-code mapping, Windows-safe stdout, lock orchestration, hooks, and pruning |

## Data flow and state

`.sync-state.json` stores hashes of the last content written per runtime and per
managed skill file. This lets the tool distinguish source movement from
out-of-band runtime edits. State writes are atomic.

`.sync-audit.log` is JSONL. It records consequential source/runtime writes and
confirmed backup pruning. Runtime writes live outside the repository, so git
alone is not a sufficient audit trail.

`.sync-state.lock/` is a repo-scoped mutation lock. Mutating commands acquire it
before writes and release it in `finally`. The lock stores owner metadata in
`owner.json`. Stale-looking locks fail closed and require manual inspection.

`.backups/` contains recovery snapshots for source, runtime, and settings writes.
Backup snapshot names are collision-safe. Pruning is explicit via
`prune-backups`; it is dry-run by default.

## Trust boundaries

1. User/chat or runtime-local skill text to source (`capture`, `enroll`,
   `promote`). Controls: dry-run where supported, explicit one-skill
   enrollment, human review, secret lint, neutral-language lint for skills,
   exact source mapping for non-append promote changes. Recursive runtime
   directories are not accepted as managed payloads.
2. Source to runtime files (`project`, `project_skills`). Controls: allowlisted
   roots, resolved-path containment, drift guard, backups, state, audit logging,
   and repo-scoped lock.
3. Hook installation to runtime settings (`install-hooks`). Controls: narrow
   merge-safe writers, schema/type validation, backups, idempotency,
   per-runtime failure reporting, and repo-scoped lock.
4. Backup deletion (`prune-backups --confirm`). Controls: dry-run default,
   `.backups/` containment, retention policy, symlink escape avoidance where
   feasible, audit event, and repo-scoped lock.

## Design decisions

| Decision | Chosen approach | Rationale | Trade-off |
|---|---|---|---|
| Source of truth | Repo-owned `_shared`, `overlays`, and `skills` files | Keeps generated runtime files reproducible and reviewable | Operators must not hand-edit generated files without promoting |
| Drift handling | Refuse by default, scoped `--force` only | Prevents clobbering useful runtime learnings | Extra promote/force step for intentional overwrites |
| Promote changes | Append through capture; delete/replace only on unique source match | Prevents silent lossy reverse merges | Ambiguous edits require manual source editing |
| Skill names | Portable lowercase/hyphen grammar | Blocks path traversal and cross-platform filesystem surprises | Some existing names may need renaming |
| Skill payload | `SKILL.md`, one runtime adapter, and gated text companions from the source tree | Keeps fan-out reviewable and excludes runtime caches/session state | Executable companions stay unsupported; companion deletion does not propagate |
| Supply-chain inputs | Exact Python build/direct-dependency versions and immutable CI action SHAs | Reduces unreviewed version drift | Updates require deliberate review |
| Locks | Standard-library directory lock | No new dependency; works across supported OSes | Stale locks require manual inspection/removal |
| Backup pruning | Explicit dry-run command | Avoids deleting recovery evidence during normal writes | Operators must run cleanup intentionally |
| Hooks | Optional startup drift checks | Surfaces stale generated files early | Depends on each runtime's hook mechanism |
| CI E2E | Mock Gemini subprocess | Proves local subprocess wiring across OSes without auth | Does not prove live runtime behavior |