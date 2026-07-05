# Contributing

This is a single-operator repository; these notes keep changes consistent for
the operator and any AI assistant working in it.

## Workflow

1. Edit the source of truth — `_shared/core.md`, `overlays/<runtime>.md`, or
   `skills/<name>/` — never the generated files under `~/.claude`, `~/.codex`,
   or `~/.gemini`. If a runtime copy was edited out-of-band, run
   `agent-config-sync promote <runtime>` instead of copying by hand.
2. Fan out with `agent-config-sync project`, then verify with
   `agent-config-sync check` (exit 0 = in sync).
3. Validate:

   ```bash
   PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
   ```

   (Plain `pytest` fails in some environments — a globally installed plugin
   poisons collection.)

## Rules

- Security gates (secret scan, neutral-language lint, path containment, drift
  refusal) are binding. Fix the content; never bypass or weaken a gate to make
  a change land.
- Every consequential change lands with tests, including at least one
  should-fail case, and updates the relevant docs (`README`, `docs/`,
  `HANDOFF.md`, threat models, `docs/EVALUATION.md` log).
- Commit and push only with the operator's approval. Keep this repository
  private.
