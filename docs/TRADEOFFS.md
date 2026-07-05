# Tradeoffs

This document records operational-hardening tradeoffs so future agents do not
reopen settled decisions without new evidence.

## Backup pruning: explicit command over automatic cleanup

Chosen: `agent-config-sync prune-backups` is dry-run by default and requires
`--confirm` to delete snapshots.

Reason: backups are recovery evidence. Deleting them automatically during normal
write paths could remove the only rollback copy for a failed or partially
completed operation.

Downside: `.backups/` can still grow until the operator intentionally prunes it.

## Backup retention: newest 10 plus 30-day preservation

Chosen: keep at least the newest 10 snapshots per category and preserve snapshots
newer than 30 days.

Reason: this balances disk hygiene with recovery depth. It is similar to keeping
a recent incident timeline in a SIEM while aging out old low-value events.

Downside: high-volume local use can still accumulate backups for 30 days.

## Locking: standard-library directory lock over third-party `filelock`

Chosen: use atomic directory creation at `.sync-state.lock/` with owner metadata.

Reason: this avoids adding a supply-chain dependency for a local single-user CLI.
The lock protects the whole mutating command path, not just state-file writes.

Downside: stale locks require manual inspection and removal. The tool does not
auto-delete stale-looking locks because doing so can create split-brain writers.

## Hook installation: validate local writers, delegate Gemini

Chosen: validate Claude/Codex config shape before writing; keep Gemini delegated
to `gemini hooks migrate --from-claude`.

Reason: Claude and Codex have known local config shapes used by this tool. Gemini
migration behavior is owned by Gemini CLI. Hand-writing Gemini settings would
expand the write surface and increase corruption risk.

Downside: if Gemini changes or removes the migration command, the operator must
resolve that runtime-specific issue manually.

## Skill payload: gated source companions over recursive directory copies

Chosen: project the canonical `SKILL.md`, one runtime adapter reference, and
reviewed text companion files stored in the source tree (`.md .txt .json .yaml
.yml .toml`), each passing the neutral-language and secret gates at projection.
Live runtime directories are never mirrored.

Reason: live runtime skill directories can contain virtual environments, browser
profiles, authentication state, caches, backups, or generated artifacts. A
recursive copy would turn local machine state into source-controlled agent input.
Companions enter only by reviewed copy into `skills/<name>/`.

Downside: skills that depend on executable scripts remain unsupported by design,
and deleting a companion from the source does not remove the projected copy at
the runtimes.

## Supply-chain inputs: exact pins over floating versions

Chosen: pin the Python build backend and declared direct dependencies to exact versions, and pin
GitHub Actions to immutable commit SHAs.

Reason: a floating build backend or mutable action tag can change executable code
without a reviewed repository diff.

Downside: dependency updates are manual and require a deliberate compatibility
and security validation pass.

## CI E2E: mock runtime CLI over live CLI installation

Chosen: CI creates a mock `gemini` executable and verifies subprocess wiring
across Windows, Linux, and macOS.

Reason: live Claude/Codex/Gemini CLIs can require auth, user profiles, or
interactive setup. A mock keeps CI deterministic and safe.

Downside: CI does not prove live runtime compatibility. Live hook verification
remains a manual/local validation step.

## Sensing: report-only with AI-mediated confirmation

Chosen: the session-start hook runs read-only `sense`; the AI reading its
output must ask the operator before running the named resolution command.
Nothing auto-applies, even for source-ahead changes.

Reason: writes at session open would happen inside a hook timeout with nobody
watching; a wrong auto-apply is exactly the silent clobber the drift guard
exists to prevent. The operator stays the trigger for every write.

Downside: one extra confirmation step when the source is legitimately ahead.

## Tier 2 pending.json retention: Human-in-the-Loop over auto-expiration

Chosen: `pending.json` is not automatically deleted by a staleness timer. It
persists until naturally superseded by the next `sense` run.

Reason: the operator may not open an AI for days or weeks. A finding from days
ago is still a valid finding that needs human awareness. Auto-deleting it would
hide drift. Keeping a human in the loop ensures drift resolution is intentional.

Downside: if a drift event resolves itself naturally, the operator still sees
a notification of the old resolved state until they start a session and run
a fresh check.

## Tier 2 pending.json integrity: advisory-only over cryptographic signing

Chosen: `pending.json` carries no signature or HMAC. It is advisory-only by
design: the AI always re-runs `sense` live at session start, and no
consequential decision may use `pending.json` as its sole input.

Reason: a signature was considered and rejected. Any process able to tamper
with `pending.json` already has same-user access — it could equally edit the
repo, PATH, or the hooks themselves, and any locally derivable HMAC key would
be readable by that same attacker (forgeable at zero cost). A DPAPI-protected
key would add real key-management complexity to protect a notification hint
whose forgery, at worst, prompts the operator to open a session where live
`sense` reports the truth.

Downside: a forged or corrupted `pending.json` can produce a misleading
desktop notification. Accepted: the live re-run bounds the impact to one
unnecessary look.

## Future enhancements (specced, not scheduled)

- **Fourth runtime / any-AI support:** placeholder spec at
  `superpowers/specs/2026-07-04-fourth-runtime-support-spec.md`. Gate: the
  operator actually adopts a fourth AI tool. Not built speculatively.
- **Unattended Tier 3 trigger:** the proposal drafter shipped as an
  operator-invoked skill (`draft-proposals`, eval 12/12). Running it
  unattended (watcher-triggered or scheduled) remains future work behind the
  original gate: watcher >=2 weeks clean + one real drift resolved + a
  deterministic write sandbox; LLM runs are paid - operator authorizes.
