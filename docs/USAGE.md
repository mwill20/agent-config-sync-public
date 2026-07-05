# Usage

## Read-only health checks

```bash
agent-config-sync status
agent-config-sync check
agent-config-sync doctor
```

`check` is read-only. Exit `0` means generated files match the source. Exit `1`
means at least one runtime is stale or edited.

## Project source to runtimes

```bash
agent-config-sync project
agent-config-sync project claude
agent-config-sync project claude --force
```

`project` refuses to overwrite out-of-band runtime edits unless the operator
scopes `--force` to one runtime. Existing files are backed up before overwrite
and consequential writes are audit-logged.

## Enroll a skill

Enroll a reviewed neutral body:

```bash
agent-config-sync enroll my-skill --body-file ./SKILL.md
agent-config-sync project
agent-config-sync check
```

Or select Claude's runtime-local body as the starting canonical variant:

```bash
agent-config-sync enroll my-skill --from claude
agent-config-sync project
agent-config-sync check
```

Enrollment is intentionally one skill at a time. The secret and neutral-language
lints run before the canonical write. Skill names must use lowercase letters,
numbers, and single hyphens; path segments, dots, underscores, spaces, and
Windows reserved device names are rejected.

The managed payload is `SKILL.md`, the runtime adapter generated under
`references/`, and any reviewed text companion files (`.md .txt .json .yaml
.yml .toml`) placed under `skills/<name>/` in the source repository. To add a
companion, review it, copy it into `skills/<name>/` (mirroring the relative
path the body references), and run `project` — the neutral-language and secret
gates run on every companion at projection time and refuse the whole plan on a
hit. Scripts, local virtual environments, browser profiles, caches, and runtime
state are never enrolled or projected; never bulk-copy a runtime skill
directory into the source repository.

## Capture a rule or skill

```bash
agent-config-sync capture standard --target core --text-file ./rule.md
agent-config-sync capture standard --target core --text-file ./rule.md --confirm
agent-config-sync capture skill --name my-skill --body-file ./SKILL.md --confirm
```

Capture is dry-run by default and prints a diff. With `--confirm`, source writes
are backed up and audit-logged, then the tool projects the updated source.

## Promote a runtime edit

```bash
agent-config-sync promote
agent-config-sync promote gemini --target core
agent-config-sync promote gemini --target core --confirm
```

Promote distinguishes clean, source-behind, live-only, missing-baseline, and true
conflict states. Append-only edits are appended through the capture engine.
Deletions and replacements are applied only when the changed block maps exactly
once to the selected source target.

## Sense what changed

```bash
agent-config-sync sense
agent-config-sync sense --json
```

Read-only. Reports, per finding: source-ahead files (apply with `project`),
runtime-side edits (keep via `promote`/re-enroll, or discard via a scoped
`--force`), unmanaged skills that are enrollment candidates, and source gate
failures. Exit 0 means nothing to do; exit 1 means findings exist. The brief
output is written for the AI that reads it at session start and instructs it
to ask the operator before running any command. Skills that should never be
flagged (deliberate exclusions) go under `sense_ignore_skills` in
`config/targets.yaml`.

## Check a candidate skill for redundancy

```bash
agent-config-sync overlap my-skill --from claude
agent-config-sync overlap my-skill --body-file ./body.md
```

Read-only similarity report against every managed skill (body and description
ratios). `REVIEW` flags mean inspect before enrolling; exit 1 when anything is
flagged. The report never decides — whether two skills are redundant, and how
to merge the useful parts of both, is an operator judgment executed through
the normal enroll gates.

## Serve status over MCP (read-only)

```bash
agent-config-sync mcp-serve
```

Speaks MCP (protocol 2024-11-05 subset) over stdio and exposes exactly three
read-only tools: `sense`, `check`, `status`. Point any MCP client at the
command above (stdio transport). Mutating commands are not tools on this
surface by construction. Example client config entry:

```json
{"agent-config-sync": {"command": "agent-config-sync", "args": ["mcp-serve"]}}
```

## Install startup hooks

```bash
agent-config-sync install-hooks --dry-run
agent-config-sync install-hooks
```

The dry run reports hook targets and the Gemini migration command without
writing runtime configuration. The apply command returns nonzero if a resolvable
hook step fails. The installed hook command is `agent-config-sync sense`; a
previously installed `agent-config-sync check` hook is replaced when its entry
is exactly what this tool wrote (operator-edited entries are left in place).

## Prune backups

```bash
agent-config-sync prune-backups
agent-config-sync prune-backups --confirm
```

Pruning is dry-run by default. The confirmed command deletes only eligible
snapshot directories under `repo_root/.backups`, keeps the newest 10 snapshots
per backup category, preserves snapshots newer than 30 days, and writes a prune
event to `.sync-audit.log`.

## Repo lock behavior

Mutating commands acquire `repo_root/.sync-state.lock/` before writing. If another
mutating command is active, the command exits with code `5` and prints the lock
owner metadata location. Read-only commands and dry-runs do not require the lock.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 1 | `check` found drift |
| 2 | Operator/action issue such as drift refusal, unknown runtime, promote conflict, or missing baseline |
| 3 | Config, secret, non-neutral body, hook, projection, or pruning failure |
| 4 | Unsafe blanket force request |
| 5 | Repo mutation lock is already held |