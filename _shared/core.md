# Shared Engineering Standards (example)

This is the neutral source of truth that agent-config-sync projects into every
AI runtime's instruction file. In this public mirror it is a compact example;
in a real deployment it carries the operator's full engineering and security
standards. Edit THIS file, never the generated runtime files.

## Engineering defaults

- Simple, clean, correct; no over-engineering.
- Pin dependency versions exactly; unpinned dependencies are supply-chain risk.
- Every consequential change lands with tests, including at least one case
  that should fail (bad input, wrong permissions, missing authorization).
- Explain the why alongside the what.

## Security defaults

- Least privilege everywhere; input validation on every external boundary.
- No hardcoded secrets; audit logging on consequential actions.
- Deterministic checks gate security decisions; a probabilistic model may
  propose, never authorize.

## Keeping configs in sync

Your global instruction file and your skills are **generated** from one source
of truth: the agent-config-sync repository. Do not hand-edit the generated
files; edits are overwritten and may be refused as drift.

- **To change a shared standard:** edit `_shared/core.md` in that repo, then
  run `agent-config-sync project`.
- **To change one runtime only:** edit that runtime's `overlays/<vendor>.md`,
  then `agent-config-sync project`.
- **To check whether everything is in sync:** run `agent-config-sync check`
  (exit 0 = in sync). `agent-config-sync status` shows per-runtime detail.
- **To add or update a skill:** run
  `agent-config-sync enroll <name> --body-file <path>` then `project`.
- **At session start** the installed hook runs `agent-config-sync sense`, which
  names what changed and the exact resolution command. If it reports findings,
  tell the user what changed and ask before acting; on approval, run exactly
  the command the finding names. Never promote, force, or enroll without
  explicit user approval.
