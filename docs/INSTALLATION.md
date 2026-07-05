# Installation

## Requirements

| Requirement | Version / Notes |
|---|---|
| Python | 3.11 or newer |
| Package manager | `pip` |
| Build backend | `setuptools==81.0.0` |
| Runtime dependency | `pyyaml==6.0.2` |
| Development dependency | `pytest==8.3.4` |
| OS | Tested locally on Windows; CI covers Windows, Linux, and macOS best-effort |
| External services | None for normal CLI use |

## Install for local development

```bash
python -m pip install -e ".[dev]"
```

Build isolation resolves the exact `setuptools==81.0.0` requirement declared in
`pyproject.toml`. CI runs at the declared Python floor (3.11) and pins
`actions/setup-python` to the immutable v5.6.0 commit SHA.

## First projection

```bash
python -m agent_config_sync project
```

The installed console command is also available as `agent-config-sync` when the
editable install's scripts directory is on `PATH`.

## Validation command

Plain `pytest` is not reliable in this local environment because a global plugin
breaks collection. Use the isolated command below:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
```

Windows PowerShell equivalent:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; $env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -p no:cacheprovider
```

## Optional hooks

```bash
agent-config-sync install-hooks --dry-run
agent-config-sync install-hooks
```

`--dry-run` reports planned hook targets without writing files. The apply command installs startup drift checks for Claude, Gemini, and Codex. It writes only
the documented hook locations and reports a nonzero exit if a resolvable runtime
hook step fails.

## Optional backup maintenance

```bash
agent-config-sync prune-backups
agent-config-sync prune-backups --confirm
```

The first command is a dry-run. The confirmed command prunes only eligible
`.backups/` snapshots and records the operation in `.sync-audit.log`.