---
name: config-sync
description: Keep this AI's global instructions and skills in sync with the shared source of truth, and add new ones safely.
---

# Keeping your AI config in sync

This runtime's global instruction file and skills are generated from one shared
source (the `agent-config-sync` repository). Use this skill to check sync, apply
updates, and add new skills or standards — the same way in every AI.

## Check whether you are in sync

Run `agent-config-sync check`. Exit 0 means everything matches the source.
A non-zero result means something drifted; run `agent-config-sync status` to see
which runtime and which file.

## Apply the latest source

Run `agent-config-sync project` to regenerate this runtime's instruction file and
managed skills from the source. It refuses to overwrite a file you hand-edited
(to avoid losing your change) unless you scope it to one runtime with `--force`.

## Add or update a skill

1. Write the skill body as a neutral `SKILL.md` (describe actions, not a specific
   runtime's tools — for example "dispatch a subagent" or "open a file").
2. Run `agent-config-sync enroll <name> --body-file <path>`. This refuses bodies
   that contain runtime-specific tool names or secrets.
3. Run `agent-config-sync project` to copy it into every runtime.

## Add or change a standard

Edit the shared source (`_shared/core.md` for something every AI should follow,
or `overlays/<runtime>.md` for one runtime), then run `agent-config-sync project`.

## If something looks wrong

Every overwrite is backed up under the repo's `.backups/` folder, and every
action is recorded in the audit log. Recover a previous version from there.
