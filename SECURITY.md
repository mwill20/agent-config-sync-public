# Security Policy

## What this tool does to your system

`agent-config-sync` writes generated AI runtime instruction files and managed
skills under configured Claude, Codex, and Gemini roots. Projection destinations
must be declared in `config/targets.yaml` and resolve under allowed runtime
roots. The `install-hooks` command has narrow documented exceptions for Claude
settings, Codex config, and Gemini CLI hook migration.

## Controls

- **Allowlist and containment:** runtime destinations are validated against
  allowed roots, source paths stay under the repository, and skill names pass a
  portable lowercase/hyphen grammar before they can become paths.
- **No secrets:** source and projected content are scanned for high-confidence
  credential patterns before consequential writes.
- **Neutral skills:** managed skill bodies — and every companion file projected
  with them — are blocked when they contain known runtime-specific tool names
  or slash-command forms. Only the per-runtime adapter is exempt.
- **Runtime-skill import boundary:** enrollment accepts one reviewed `SKILL.md`
  body, not a recursive runtime directory. Companion files enter only by
  reviewed copy into the source tree and are restricted to a text-only
  extension allowlist (no scripts or executables); hidden paths are never
  projected and adapter filenames cannot be shadowed. Virtual environments,
  browser profiles, authentication state, caches, backups, and generated files
  must never be copied into the canonical repository.
- **Supply-chain pinning:** the Python build backend and declared direct dependencies use exact
  versions, and CI actions are referenced by immutable commit SHA.
- **No clobbering:** `project` refuses out-of-band runtime edits — instruction
  files *and* managed skill files — unless the operator scopes `--force` to a
  runtime. A blanket `--force` that would overwrite more than one drifted target
  (across instructions and skills combined) is refused; name a single runtime.
- **Read-only sensing:** `sense`, `overlap`, and the ambient watcher
  (`watch-once` + the scheduled wrapper) hold no write authority over source
  or runtime files; the watcher's only write is its own advisory pending file,
  and a should-fail test proves no mutating path is reachable from a cycle.
  Session-start sense output instructs the consuming AI to ask the operator
  before running any resolution command.
- **Promote safety:** source-only movement, missing baselines, true conflicts,
  and ambiguous delete/replace mappings are refused instead of guessed. The
  post-promote reproject uses a runtime-scoped force, so an unrelated runtime's
  own un-promoted edit is refused (not silently overwritten) during fan-out.
- **Backups:** existing source and runtime files are copied under `.backups/`
  before overwrites.
- **Audit:** source and runtime writes are appended to `.sync-audit.log` with
  timestamp, kind, destination, and content hash.
- **Human approval:** capture and promote are dry-run by default and require
  `--confirm` before writing.

## Threat note

These files steer AI agents. A poisoned standard or skill can become an indirect
prompt-injection vector across multiple runtimes. A recursive copy from a live
runtime can also leak session data or executable dependencies that were never
reviewed as skill source. The binding controls are the deterministic validation
gates, the narrow managed payload, and human confirmation; any AI review is
advisory only. Detailed threat models live under `docs/threat-models/`.

## Reporting

Open a private issue or contact the maintainer. Do not include secrets in
reports, logs, screenshots, or reproduction artifacts.
