# Project Audit & Analysis: `agent-config-sync`

> **SUPERSEDED (2026-07-03):** This is a point-in-time audit kept for history.
> Its findings have since been remediated: backup pruning exists
> (`prune-backups`, dry-run default), state writes are serialized by a
> repo-scoped mutation lock (`lock.py`), and hook installation validates
> structure and supports `--dry-run`. See
> `docs/AUDIT_REMEDIATION_CHECKLIST.md` for the finding-by-finding disposition.

**Date:** 2026-06-29
**Role:** Auditor / Assessor
**Scope:** Review goals, code structure, specifications, gaps, and surface potential issues. No code execution was performed.

---

## 1. Project Goal & Purpose
`agent-config-sync` is a Python-based CLI tool acting as a **single source of truth** for managing and synchronizing AI assistant configurations across multiple runtimes (Claude Code, Codex, and Gemini/AntiGravity). 

It solves the problem of "configuration drift" where instructions or skills taught to one AI assistant do not propagate to the others. 

**Core capabilities:**
- **Forward Projection:** Merges neutral core standards (`_shared/core.md`) with vendor-specific overlays (`overlays/<vendor>.md`) and projects them out to the respective runtimes.
- **Skill Synchronization:** Distributes vendor-neutral skills to all assistants.
- **Capture:** Safely ingests new rules or skills from chat sessions after running deterministic security lints.
- **Reverse Promote:** Lifts modifications made inside a specific assistant's config file back into the global source of truth.
- **Startup Hooks:** Installs hooks (`SessionStart`) in the AI assistants to automatically check for configuration drift on startup.

---

## 2. Codebase & Architecture
The project is built in Python (>=3.11) with a strict focus on safety, atomic operations, and deterministic validation over probabilistic AI judgement.

### Key Components:
- `cli.py`: Command routing and exit-code contract management.
- `config.py` & `validation.py`: Handles `targets.yaml` allowlists and strict path resolution (anti-path-traversal).
- `project.py` & `skills.py`: Forward projection logic with drift detection and `.sync-state.json` hashing.
- `promote.py` & `capture.py` & `enroll.py`: Ingestion pipelines for runtime edits or chat-provided rules.
- `neutralize.py` & `secrets.py`: Binding deterministic lints to block vendor-specific terms and exposed credentials.
- `fsutil.py`: Handles atomic writes, backups (to `.backups/`), and file hashing.
- `settingsedit.py`: Merge-safe hook installation for `~/.claude/settings.json` and `~/.codex/config.toml`.

**Design Ethos:**
The code heavily reflects a security-engineering background. It employs "dry-run by default", requires human `--confirm` for consequential writes, backs up files prior to modification, and maintains a strict append-only audit log (`.sync-audit.log`).

---

## 3. Specifications & Current State
- **Status:** Marked as **v1 feature-complete**. All planned phases (Plan 1: Forward Projection, Plan 2: Skills & Discovery, Plan 3: Reverse Promote) have been built.
- **Testing:** Comprehensive test suite with **148 passing tests**. Testing includes specific "should-fail" paths for every consequential action (e.g., drift refusal, secret linting aborts, and 3-way conflicts).
- **Execution Environment:** Local operation. Interacts directly with the filesystem `~/.claude`, `~/.codex`, and `~/.gemini`.

---

## 4. Gaps & Documented Limitations
As identified in `LIMITATIONS.md` and `HANDOFF.md`, the tool deliberately accepts certain boundaries:
1. **Local Only:** Has no native remote sync logic. Off-machine durability relies entirely on the user setting up a private git remote.
2. **Promote Complexity:** The `promote` command handles exact matches for replace/delete operations. It is not a generalized 3-way merge engine. Ambiguous maps result in refusals.
3. **Pattern-Based Linting:** The secret lint and neutral-language lint are heuristic/denylist-based. They are guardrails, not impenetrable shields.
4. **Skill Naming:** Strictly enforces a portable `lowercase-hyphen` grammar, breaking any legacy skills with dots, spaces, or underscores.

---

## 5. Surfaced Issues & Audit Findings
Based on the code structure and documentation review, I have identified the following potential issues that warrant attention:

> [!WARNING]
> **1. Unbounded Backup Accumulation**
> Every projection or settings overwrite creates a copy in `.backups/`. There is no mechanism to prune or rotate these backups. Over time, this will lead to unbounded disk space usage and could silently hoard sensitive information if a secret was accidentally written and backed up before being removed.

> [!CAUTION]
> **2. Hook Installer Fragility (`settingsedit.py`)**
> The `install-hooks` command directly manipulates JSON and TOML config files managed by third-party tools (Claude Code, Codex). If these tools change their config schema or enforce strict property ordering, the merge-safe writer could corrupt the settings or cause the AI runtime to fail on launch. Furthermore, Gemini hook migration relies entirely on an external command (`gemini hooks migrate --from-claude`). If Gemini deprecates this undocumented/internal command, the integration breaks.

> [!NOTE]
> **3. State File Concurrency Risks**
> The `.sync-state.json` tracks hashes. While `fsutil.py` uses atomic file writes, it is unclear if there is a global file lock around the state read/write cycle. If multiple assistants run `agent-config-sync` concurrently (e.g., via startup hooks firing simultaneously), race conditions could corrupt the state ledger.

> [!TIP]
> **4. Cross-Platform Path Hazards**
> The tool is heavily tested by the author on Windows. The allowlist parser handles `;` vs `:` environment variable splitting. However, runtime hook paths and shell executions (like `cmd /c` usage mentioned in `EVALUATION.md`) can introduce subtle breakages on macOS or Linux environments if someone else clones this repository.

> [!IMPORTANT]
> **5. Lack of Live E2E CI Testing**
> The 148 tests are unit and integration tests against a mocked sandbox file system. The CI pipeline does not execute against live `claude`, `codex`, or `gemini` binaries. Drift in how those tools expect `SKILL.md` or `.settings.json` formatted will bypass CI entirely until it breaks on a user's machine.
