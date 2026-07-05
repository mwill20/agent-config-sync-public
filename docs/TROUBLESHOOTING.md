# Troubleshooting

## `pytest` fails before collecting tests

Use the isolated test command:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider
```

In this local environment, the default temp directory and global pytest plugins
can fail before project code is reached. When needed, use an explicit writable
basetemp such as `.pytest_cache/acs-pytest`.

## `project` refuses to overwrite a runtime

The runtime file was edited outside the source of truth. Run:

```bash
agent-config-sync promote
```

If the edit is intentional, promote it back into `core` or the relevant overlay.
If it should be discarded, run a scoped force such as:

```bash
agent-config-sync project claude --force
```

## `promote` reports `source-behind`

The source changed, but the runtime still matches the last generated version.
There is no live edit to promote. Run:

```bash
agent-config-sync project
```

## `promote` reports `missing last-projected baseline`

The runtime file does not match the current projection and there is no recorded
baseline hash. Establish a baseline with `project`, then make the runtime edit
again or resolve manually.

## A projected skill is missing scripts, templates, or other files

This is expected for the current managed payload. Projection copies only
`SKILL.md` and one runtime adapter reference; it is not a recursive directory
sync. Do not copy a live runtime skill directory wholesale because it may contain
virtual environments, browser profiles, authentication state, caches, or
generated files. Either make the skill self-contained or design and review an
explicit companion-file allowlist before extending the projector.

## `capture skill --confirm` returns nonzero after writing source

The source was updated, but projection failed because of drift, config, or lint
state. The command prints the recovery state. Resolve the reported issue, then
run:

```bash
agent-config-sync project
```

## A command returns `Lock error` or exit code `5`

Another mutating command is active or a previous command left
`.sync-state.lock/` behind. Inspect:

```bash
cat .sync-state.lock/owner.json
```

If the PID/host is no longer active, remove the lock directory manually. The tool
intentionally does not auto-delete stale-looking locks because doing so could let
two writers run at once.

## `install-hooks` returns `3`

At least one resolvable hook step failed. Claude/Codex files are written only by
their merge-safe writers; Gemini uses `gemini hooks migrate --from-claude` and is
owned by the Gemini CLI. Re-run after fixing the reported runtime issue.

## `prune-backups --confirm` refuses or fails

The command deletes only snapshot directories contained under `repo_root/.backups`.
If a symlink, permission issue, or containment issue is reported, inspect that
backup path manually. Do not broaden deletion rules without review; backups may
contain real runtime configuration.