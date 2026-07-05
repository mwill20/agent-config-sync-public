# Limitations

- **Local runtime state is not backed up by Git.** The canonical source has a
  private remote, but `.sync-state.json`, `.sync-audit.log`, `.backups/`, and
  generated runtime files remain machine-local by design.
- **No automatic bidirectional sync.** Runtime edits must be reviewed with
  `promote`; source changes flow out with `project`.
- **Promote is exact, not a general merge engine.** Append-only edits are
  supported. Deletions and replacements are supported only when the changed text
  maps exactly once to the selected source target. Ambiguous mappings are refused
  before source mutation.
- **Missing promote baseline is refused.** If `.sync-state.json` lacks the last
  generated hash for a divergent runtime, establish a baseline first instead of
  guessing.
- **Neutral-language lint is a curated denylist.** It catches known runtime tool
  names and slash-command forms, but it is not a proof that a skill is fully
  vendor-neutral. Human review remains required.
- **Secret lint is pattern-based.** It catches high-confidence key/token formats
  and assignments, but it is not a replacement for review or a dedicated secret
  scanner in CI.
- **Skill-name grammar is intentionally narrow.** Names must be portable
  lowercase/hyphen identifiers. Existing skills with dots, spaces, underscores,
  or path-like names must be renamed before management.
- **Managed skill payloads are text-only.** Projection copies the canonical
  `SKILL.md`, one runtime adapter reference, and reviewed text companions
  (`.md .txt .json .yaml .yml .toml`) stored in the source tree. Scripts,
  binaries, images, and nested repositories are refused. Removing a companion
  from the source does not delete the projected copy at the runtimes.
- **No bulk runtime-skill import.** Runtime skill directories may contain
  virtual environments, browser profiles, authentication state, caches, backups,
  or generated artifacts. Each skill must be reviewed and enrolled individually;
  directory-level copying is outside the supported trust boundary.
- **Three runtimes only.** The write allowlist, adapter set, lint vocabulary,
  and hook installers cover Claude Code, Codex, and Gemini/AntiGravity.
  Supporting a fourth AI is specced with placeholders but not scheduled: see
  `superpowers/specs/2026-07-04-fourth-runtime-support-spec.md`. Tools that
  read the `AGENTS.md` convention may already consume the generated Codex
  output with no changes.
- **Hook installation depends on runtime behavior.** Claude and Codex hooks are
  written directly by merge-safe writers. Gemini hook migration is delegated to
  `gemini hooks migrate --from-claude`; a resolvable Gemini failure makes the
  command fail, but migration behavior itself is owned by Gemini CLI.
- **Backup pruning is explicit, not automatic.** `.backups/` can still grow until
  the operator runs `prune-backups`. This is intentional so recovery evidence is
  not deleted during normal write paths.
- **Repo locks fail closed.** A stale-looking `.sync-state.lock/` is not removed
  automatically. The operator must inspect owner metadata and remove it manually
  if safe.
- **CI is hermetic, not live-runtime proof.** CI runs unit/integration tests plus
  a mock-Gemini subprocess E2E across hosted OS runners. It does not install or
  authenticate real Claude, Codex, or Gemini CLIs.
- **No license for current private use.** The owner has decided this private
  repository does not need a license file. If the repo becomes public or shared
  for third-party reuse, select and add a license before publication.