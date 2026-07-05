# Threat Model - Operational Hardening Surface

**Date:** 2026-06-30  
**Scope:** backup pruning, repo-scoped mutation locking, and hermetic CLI E2E.

## Assets

- Runtime/source backup snapshots under `.backups/`
- State ledger `.sync-state.json`
- Audit log `.sync-audit.log`
- Runtime instruction files and hook settings modified by mutating commands
- CI trust signal for cross-platform subprocess wiring

## Trust boundaries

1. Operator command to local filesystem deletion (`prune-backups --confirm`).
2. Concurrent process boundary between multiple local CLI invocations.
3. CI mock executable boundary for `gemini` subprocess behavior.

## Threats and controls

| ID | Threat | Control | Code pointer |
|---|---|---|---|
| O1 | Backup path collision overwrites recovery evidence | Collision-safe backup destination suffixing | `fsutil.backup` |
| O2 | Cleanup deletes recovery evidence without review | `prune-backups` is dry-run by default and requires `--confirm` | `cli.main`, `fsutil.prune_backups` |
| O3 | Cleanup escapes `.backups/` via traversal or symlink-like path | Resolved containment checks and symlink directory exclusion | `fsutil.plan_backup_prune`, `fsutil.prune_backups` |
| O4 | Two mutating commands race and corrupt state/audit/runtime writes | Repo-scoped atomic directory lock | `lock.repo_lock`, `cli._mutation_lock` |
| O5 | Stale lock is removed unsafely while another writer is active | Stale-looking locks fail closed; operator must inspect metadata | `lock.repo_lock` |
| O6 | Malformed hook config causes traceback or partial corruption | Pre-write schema/type validation and `HookInstallError` | `settingsedit.install_claude_hook`, `settingsedit.install_codex_hook` |
| O7 | CI claims live runtime compatibility it did not verify | Hermetic E2E documented as mock-subprocess coverage only | `.github/workflows/ci.yml`, `tests/test_cli_e2e.py` |

## Residual risk

- The directory lock is local-filesystem based. It is appropriate for this local
  CLI, but it is not a distributed lock.
- Real Gemini CLI migration behavior can still drift outside CI coverage.
- Backup pruning can still fail on filesystem permission issues; failures should
  be treated as manual inspection events, not bypassed.