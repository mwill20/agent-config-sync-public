# Lesson 11 - Operational Hardening: Locks, Backup Pruning, Supply-Chain Pins, and Hermetic E2E

## Goal

This lesson explains the operational-readiness layer added after the main sync
capabilities were complete. The focus is preventing avoidable local failures:
backup collisions, unbounded backup growth, concurrent writers, malformed hook
config shapes, dependency drift, and CI gaps.

## Why this matters

Think of `agent-config-sync` like a local SOAR playbook that writes to several
sensitive runtime files. A SOAR workflow needs guardrails so two runs do not
fight each other, cleanup does not delete evidence, and external tool drift is
caught before it breaks the operator.

## What changed

| Capability | File | Security outcome |
|---|---|---|
| Collision-safe backup paths | `fsutil.py` | Two rapid writes cannot overwrite the same recovery snapshot |
| Explicit `prune-backups` | `fsutil.py`, `cli.py` | Cleanup is intentional, dry-run first, and audit-logged |
| Repo-scoped lock | `lock.py`, `cli.py` | Mutating commands do not race each other |
| Hook shape validation | `settingsedit.py` | Malformed config trees fail safely before writes |
| Exact Python build/direct-dependency pins | `pyproject.toml` | Builds cannot silently resolve a different backend or library version |
| Immutable GitHub Action pin | `.github/workflows/ci.yml` | CI executable code changes only through a reviewed SHA update |
| Hermetic Gemini CLI E2E | `tests/test_cli_e2e.py`, CI | Subprocess wiring is tested without real runtime auth |

## Key design choices

- Backup pruning is not automatic. Recovery evidence should not disappear during
  normal write paths.
- The lock is a standard-library directory lock, not a third-party dependency.
- Stale-looking locks fail closed and require manual inspection.
- Gemini remains delegated to `gemini hooks migrate --from-claude`; the tool does
  not hand-write Gemini settings.
- The build backend and declared direct Python dependencies use exact versions. GitHub Actions
  use immutable commit SHAs rather than mutable major-version tags.
- CI proves mock subprocess wiring, not live runtime compatibility.

## Exercise

Run focused tests for the operational layer:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_fsutil.py tests/test_lock.py tests/test_settingsedit.py tests/test_cli_e2e.py -q -p no:cacheprovider
```

Then inspect the pins and operator docs:

```bash
python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['build-system']['requires'])"
git grep "actions/setup-python@" .github/workflows/ci.yml
agent-config-sync prune-backups
```

The focused tests should pass. The pin checks should show an exact setuptools
version and a full GitHub Action commit SHA. `prune-backups` should be a dry-run
and should not delete backup snapshots.

## Interview framing

If asked why this was added after feature-complete status, say:

> The core functionality worked, but operational readiness needed a second pass.
> We added deterministic controls around cleanup, concurrency, config-shape
> validation, dependency resolution, CI action identity, and cross-platform
> subprocess behavior so the tool fails safely under realistic local conditions.
