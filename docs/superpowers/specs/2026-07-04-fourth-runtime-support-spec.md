# Spec: Fourth Runtime / Any-AI Support

**Status:** PROPOSED / NOT SCHEDULED — nothing in this document is implemented.
**Date:** 2026-07-04
**Trigger to schedule:** the operator adopts a fourth AI coding tool and wants
it under managed configuration. Do not build speculatively.

---

## 1. Goal

Extend agent-config-sync so an arbitrary new runtime `<vendor>` receives the
same projected instruction file, managed skills, and text companions as the
three current runtimes (Claude Code, Codex, Gemini/AntiGravity), behind the
same deterministic gates, with no weakening of the write allowlist.

`<vendor>` is a placeholder throughout. Candidate examples (named, not chosen):
Cursor, Copilot CLI, Windsurf.

## 2. Qualification checklist — does the candidate even need this?

A candidate runtime qualifies for a full runtime entry only if ALL of:

- [ ] It reads a global instruction file from a predictable per-user path
      (e.g. `~/.<vendor>/<FILE>.md`). `TODO: confirm exact path from vendor docs.`
- [ ] The operator wants managed skills there, and the tool has a skills-like
      directory it actually loads. `TODO: confirm skills mechanism and path.`
- [ ] (Optional) It exposes a startup-hook or session-start mechanism for the
      drift check. Hooks are NOT required; `check` can run manually or via the
      git pre-commit hook.

**Free-riding on `AGENTS.md` first.** Many tools read the `AGENTS.md`
convention. If the candidate reads `~/.codex/AGENTS.md` or a project-level
`AGENTS.md`, it may need ZERO changes to this tool: it already consumes the
generated Codex output. A full runtime entry is justified only when the
candidate needs its own destination path, its own overlay content, or managed
skills in its own directory. Check this before anything below.

## 3. Touchpoints (verified against code, 2026-07-04)

| # | Touchpoint | File | Placeholder change |
|---|---|---|---|
| 1 | Write-allowlist root | `src/agent_config_sync/config.py` (default allowed roots, lines 8–10) | add `Path.home() / ".<vendor>"` |
| 2 | Runtime block | `config/targets.yaml` | `<vendor>: instruction_dest: "~/.<vendor>/<FILE>.md"`, `overlay: "overlays/<vendor>.md"`, `skills_dest: "~/.<vendor>/<SKILLS_DIR>"` — `TODO: real paths from vendor docs` |
| 3 | Overlay source | `overlays/<vendor>.md` | new file; `TODO:` runtime-specific instructions (skill invocation, tool notes) |
| 4 | Tool adapter | `references/<vendor>-tools.md` + `REFERENCE_FILENAMES` in `src/agent_config_sync/skills.py` (lines 13–17) | new map entry + adapter file translating neutral actions to `<vendor>` tools — `TODO: enumerate from vendor docs` |
| 5 | Neutral-language lint | `src/agent_config_sync/neutralize.py` (`_VENDOR_TERMS`) | add `<vendor>`-specific tool names / invocation forms so its vocabulary is caught in shared bodies — `TODO: enumerate from vendor docs` |
| 6 | Hook installer (optional) | `src/agent_config_sync/settingsedit.py` | `TODO: per-vendor config shape (JSON/TOML/other) and merge-safety rules; MAY ship without hooks` |
| 7 | Docs | README runtime mentions, `docs/ARCHITECTURE.md`, `docs/USAGE.md`, Lessons 00/12 | extend runtime lists; note hook status for `<vendor>` |

Gemini precedent: a runtime's skills path can differ from the obvious guess
(`~/.gemini/config/skills`, not `~/.gemini/skills`). Verify `<SKILLS_DIR>`
against the tool's actual discovery behavior, live, before first projection.

## 4. Security requirements (blocking, not optional)

- **Threat-model delta before first projection.** Each new allowlisted root
  widens the write surface. Extend the existing models in `docs/threat-models/`
  (settings-write surface if hooks are added; companion-projection model for
  the new fan-out target). Every new threat needs a code-mapped mitigation.
- **Lint coverage first.** Touchpoint 5 lands BEFORE any body or companion is
  projected to `<vendor>`, so non-neutral content referencing `<vendor>` tools
  cannot enter shared bodies unflagged in the interim.
- **Guard behavior at N=4.** Force-scope guard, drift refusal, and blanket-force
  refusal must be re-verified with four runtimes (the guards are counted, not
  hardcoded to three — confirm with tests, not by reading).
- **No allowlist shortcuts.** `AGENT_CONFIG_SYNC_ALLOWED_ROOTS` stays a
  testing-only override; the new root lands in code review, not env config.

## 5. Test plan skeleton (`TODO` — categories only, no test code yet)

Mirror the existing per-runtime coverage:

- `tests/test_config.py`: `<vendor>` root accepted; destinations outside it refused (should-fail).
- `tests/test_project.py`: instruction projection to 4 runtimes; drift refusal on `<vendor>` copy (should-fail); scoped `project <vendor> --force`.
- `tests/test_skills.py`: body + adapter + companion fan-out to `<vendor>`; adapter-collision refusal includes `<vendor>-tools.md` (should-fail).
- `tests/test_neutralize.py`: `<vendor>` tool names flagged in bodies/companions (should-fail).
- `tests/test_settingsedit.py` (only if hooks ship): merge-safe write, malformed-shape refusal (should-fail), dry-run.
- `tests/test_cli_e2e.py`: hermetic end-to-end with a mock `<vendor>` layout.

## 6. Acceptance criteria (placeholders)

- [ ] `agent-config-sync check` exits 0 across all four runtimes.
- [ ] `<vendor>` receives the generated instruction file, all managed skill
      bodies, its adapter, and all text companions.
- [ ] All gates verified with should-fail tests against the new runtime.
- [ ] Live verification: `<vendor>` actually loads the projected instruction
      file and (if applicable) at least one skill — recorded in
      `docs/EVALUATION.md`, mirroring the Codex/AntiGravity verification.
- [ ] Threat-model delta merged in the same change set.

## 7. Out of scope

- Implementing any of the above now.
- Choosing which vendor to add.
- Auto-discovery of installed runtimes (runtime entries stay a reviewed,
  deliberate trust decision).
- Executable skill companions (separate boundary; see `docs/TRADEOFFS.md`).
