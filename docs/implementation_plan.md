# Implementation Plan: Resolving Agent-Config-Sync Operational Findings

> **STATUS: COMPLETED (2026-06-30).** All items below shipped in the
> operational-hardening pass; see `docs/EVALUATION.md` (161-test entry),
> `CHANGELOG.md`, and `docs/TRADEOFFS.md`. Kept for history.

This plan addresses follow-on operational-readiness and reliability findings surfaced after ACS-001 through ACS-010 were implemented and verified. These items do not replace the ACS remediation work; they harden backup retention, concurrent CLI execution, hook validation, and cross-platform verification.

**Execution rule:** keep this work narrowly scoped to the items below. Do not add new runtime sync capabilities, change the private-repo license decision, or broaden the settings-write surface beyond the existing `install-hooks` command.

---

## Proposed Changes

### 1. File System Utilities & Backups

#### Backup Naming (Collision Safety)

- **File:** `src/agent_config_sync/fsutil.py`
- **Change:** Update backup stamp/path creation so rapid repeated writes cannot overwrite a backup created in the same second.
- **Implementation guidance:**
  - Prefer a UTC timestamp with microseconds for deterministic ordering.
  - If the computed destination already exists, add a short deterministic counter suffix instead of overwriting.
  - Preserve readable timestamp prefixes so backup folders remain easy to audit.
- **Acceptance criteria:**
  - Two backups for the same source file/category in the same second create two distinct backup paths.
  - Existing backup files are never overwritten.

#### Explicit Backup Pruning Command

- **File:** `src/agent_config_sync/fsutil.py`, `src/agent_config_sync/cli.py`
- **Change:**
  - Add a dedicated command `agent-config-sync prune-backups`.
  - The command will be **dry-run by default** and requires `--confirm` to delete anything.
  - **Retention policy:** keep at least the newest 10 backup snapshots per category and preserve any backups newer than 30 days.
- **Definitions:**
  - Backup root: `repo_root/.backups`.
  - Category: first-level directory under `.backups`, for example `claude`, `codex`, `gemini`, `source`, `settings`, or `codex-config`.
  - Snapshot: timestamp/collision-safe child directory under a category.
- **Safety requirements:**
  - Never delete anything outside `repo_root/.backups`.
  - Refuse path traversal and symlink-style escape attempts where feasible.
  - Do not run pruning automatically inside `backup()`.
  - Dry-run output must list the snapshots that would be removed.
  - Confirmed deletion must append a `.sync-audit.log` event with timestamp, policy, deleted count, and affected category summary.

---

### 2. Concurrency Controls (Repo-Scoped Locking)

#### Mutating Operation Lock

- **File:** `src/agent_config_sync/lock.py`, `src/agent_config_sync/cli.py`
- **Change:**
  - Implement a standard-library repo-scoped lock using atomic directory creation at `repo_root/.sync-state.lock`.
  - Put lock mechanics in a dedicated module because the lock protects repo-wide mutation, not only `.sync-state.json`.
  - Wrap the *entire* mutating command path, not just state read/write helpers.
- **Commands that must acquire the lock:**
  - `project` when not `--dry-run`
  - `capture --confirm`
  - `promote --confirm`
  - `enroll --body-file`
  - `install-hooks`
  - `prune-backups --confirm`
- **Commands that do not need the lock:**
  - `check`
  - `status`
  - `doctor`
  - dry-run commands
- **Lock behavior:**
  - Store lock owner metadata: PID, hostname, creation timestamp, and command.
  - Use a bounded timeout and return a clean CLI error if the lock cannot be acquired.
  - On apparent stale locks, fail closed with inspection/removal guidance. Do not silently delete stale lock directories.
  - Always release the lock in `finally`.
- **Acceptance criteria:**
  - A second mutating command fails cleanly while the lock is held.
  - No target/runtime/source files are written when lock acquisition fails.
  - Lock metadata is present and readable for troubleshooting.

---

### 3. Hook Installer Fragility & Validation

#### Schema Validation & Bad-Shape Tests

- **File:** `src/agent_config_sync/settingsedit.py`, `tests/test_settingsedit.py`
- **Change:**
  - Add explicit schema and type validation in `install_claude_hook` and `install_codex_hook`.
  - Ensure `AttributeError` cannot be thrown if `hooks`, `SessionStart`, or nested `hooks` entries exist but have the wrong type.
  - Throw a clear `HookInstallError` instead of crashing.
  - Add explicit bad-shape test cases to `test_settingsedit.py`.
- **Bad-shape cases to test:**
  - Claude top-level JSON is valid but `hooks` is not an object.
  - Claude `hooks.SessionStart` is not a list.
  - Claude SessionStart entries are not objects.
  - Claude nested `hooks` is not a list.
  - Codex TOML `hooks` or `hooks.SessionStart` exists with an unexpected type.
- **Gemini handling:**
  - Continue using `gemini hooks migrate --from-claude`.
  - Do not hand-write Gemini settings.
  - Improve failure reporting for nonzero exit, launch failure, and missing CLI.
  - If feasible, add a best-effort postcondition diagnostic after successful migration. If the Gemini settings file is readable and clearly lacks the hook command, report that as a manual verification warning or failure based on the confidence of the check. Unknown schema should remain an accepted limitation, not a reason to invent a direct writer.

---

### 4. CI/CD Hermetic CLI E2E Testing

#### Mock CLI E2E in CI

- **File:** `.github/workflows/ci.yml` and a focused test/helper under `tests/`
- **Change:**
  - Add a "Hermetic CLI E2E" test step to the CI matrix.
  - Create a mock `gemini` executable/script that mimics `gemini hooks migrate --from-claude`.
  - Add the mock directory to `PATH` and run `agent-config-sync install-hooks` against temp Claude settings and temp Codex config paths.
  - Do not add fake `claude` or `codex` CLI mocks unless future code starts shelling out to those binaries. Current Claude and Codex hook paths are direct file writes, not subprocess calls.
- **Environment requirements:**
  - Use temp directories for `AGENT_CONFIG_SYNC_REPO`, `AGENT_CONFIG_SYNC_ALLOWED_ROOTS`, Claude settings, and Codex config.
  - Ensure the E2E test never touches the user's real `~/.claude`, `~/.codex`, or `~/.gemini`.
  - Include Windows and POSIX mock executable forms where needed.
- **Acceptance criteria:**
  - CI proves subprocess wiring for Gemini on Windows, Linux, and macOS.
  - CI does not claim to prove real Claude/Codex/Gemini runtime compatibility.

---

### 5. Documentation & Checklists

#### Distinguish Accepted Limitations

- **File:** `docs/LIMITATIONS.md`, `docs/AUDIT_REMEDIATION_CHECKLIST.md`, `docs/EVALUATION.md`, and the relevant threat model if pruning/locking changes the write surface.
- **Change:** Update docs to clearly distinguish between:
  - accepted limitations, such as Gemini's reliance on a CLI-owned migration command;
  - remediated reliability issues, such as hook bad-shape handling and backup collision safety;
  - newly introduced operator commands, especially `prune-backups`.
- **Documentation requirements:**
  - Document `prune-backups` dry-run and confirm behavior.
  - Document lock failure troubleshooting.
  - Record validation commands and final test counts in `docs/EVALUATION.md`.
  - Keep the private-repo no-license decision unchanged.

---

## Verification Plan

### Automated Tests

Run `python -m pytest -q -p no:cacheprovider` to verify:

- Backup naming collision tests that force same-second backups.
- Pruning dry-run tests proving no files are deleted without `--confirm`.
- Pruning retention tests proving the 10-item/30-day policy.
- Pruning containment tests proving paths outside `.backups/` are never deleted.
- Repo-scoped lock tests covering acquisition, release, metadata, timeout failure, and no-write-on-lock-failure.
- Hook installer bad-shape tests proving `HookInstallError` on corrupted types.
- Hermetic CLI E2E tests with a mock Gemini executable.

### Manual / Integration Verification

- Run `agent-config-sync prune-backups` without `--confirm` and verify it only lists intended deletions.
- Run `agent-config-sync prune-backups --confirm` and verify the `.backups/` directory respects the 10-item/30-day policy.
- Run a lock contention check with two local mutating commands and verify the second command fails cleanly without writes.
- Check CI runs to confirm the Hermetic CLI E2E tests pass across all OS runners.

## Out of Scope

- Installing or authenticating real Claude, Codex, or Gemini CLIs in CI.
- Directly writing Gemini settings.
- Adding third-party locking dependencies.
- Changing runtime instruction projection semantics.
- Adding or changing a repository license while the repo remains private.

## Implementation status

Completed on 2026-06-30 in five slices:

1. Backup collision safety and explicit `prune-backups`.
2. Repo-scoped mutating-operation lock.
3. Hook schema validation and bad-shape tests.
4. Hermetic Gemini CLI E2E coverage and CI workflow step.
5. README/docs/lessons/tradeoffs/checklist/evaluation/threat-model updates.

Final regression: `161 passed in 8.77s` with the isolated pytest command recorded
in `docs/EVALUATION.md`.

