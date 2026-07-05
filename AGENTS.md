# AGENTS.md — agent-config-sync

This repo is the source of truth for AI runtime config. Rules for any agent
working here:

- Never hand-edit `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, or
  `~/.gemini/GEMINI.md` directly — they are generated. Edit `_shared/core.md`
  or `overlays/<vendor>.md`, then run `python -m agent_config_sync project`.
- **Skills are managed artifacts too.** Edit the canonical body at
  `skills/<name>/SKILL.md` (vendor-neutral action language only — no `Skill
  tool`, `apply_patch`, `activate_skill`, or `/slash-commands`), then `project`.
  Bring a new skill under management with `enroll <name> --body-file <path>`;
  enrollment is gated by a deterministic neutral-language lint and the secret
  lint. `managed_skills` must stay the last key in `config/targets.yaml`.
  The current managed payload is `SKILL.md` plus one runtime adapter; never
  recursively import live skill directories, virtual environments, browser
  profiles, caches, authentication state, backups, or generated artifacts.
- **Discovery:** every generated instruction file carries a "## Keeping configs
  in sync" section pointing back here, and a neutral `config-sync` skill is
  projected into every runtime — that skill is the canonical "how to check/apply
  sync" reference for any AI operating this tool.
- Never add credentials to any source file; the secret lint will abort the run.
- Only paths in `config/targets.yaml` may be written, with **one** exception:
  `install-hooks` appends a single `SessionStart` entry to
  `~/.claude/settings.json` (append-only, idempotent, backed up — see
  `settingsedit.install_claude_hook` and the settings-write threat model). Do not
  add other settings.json writes or broaden the allowlist without human review.
- Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` before committing
  (plain `pytest` is broken in this env); the pre-commit hook runs `check`.
