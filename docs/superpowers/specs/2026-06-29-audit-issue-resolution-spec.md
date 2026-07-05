# Audit Issue Resolution Specification

**Status:** Proposed remediation specification — no implementation started  
**Date:** 2026-06-29  
**Source:** Independent read-only audit of `agent-config-sync`  
**Validation baseline:** 123 automated tests pass with
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`  
**Tracking checklist:** `docs/AUDIT_REMEDIATION_CHECKLIST.md`

## 1. Purpose

This specification converts the audit findings into testable engineering
requirements. It is the source of truth for the remediation work. The plans in
`docs/superpowers/plans/` sequence the work; they do not change the requirements
defined here.

No finding is resolved merely because the current 123 tests pass. Each issue
requires a regression test tied to the expected security or functional outcome.

## 2. System outcome

After remediation, `agent-config-sync` must:

1. write only to validated source and runtime paths;
2. report success only when the requested operation reached its documented
   postcondition;
3. preserve or explicitly recover from partial failures;
4. promote additions, deletions, and replacements safely, or refuse before any
   write when a change cannot be mapped unambiguously;
5. project runtime instructions that match the installed runtime capability;
6. maintain documentation and tests that describe the same behavior.

## 3. Severity model

| Severity | Meaning |
|---|---|
| High | Allows a write outside the intended boundary, misreports a consequential operation as successful, or breaks a primary workflow. |
| Medium | Weakens recovery, auditability, runtime compatibility, or reviewer trust. |
| Low | Defense-in-depth, publication, or maintainability gap without a demonstrated primary-path failure. |

## 4. Issue register

### ACS-001 — Skill names can escape source and runtime allowlists

**Severity:** High  
**Affected code:** `enroll.py:enroll_skill`, `enroll.py:update_managed_skills`,
`skills.py:skill_files`, `skills.py:project_skills`, `neutralize.py:read_skill_variants`

**Observed behavior:** A skill name containing `..` path segments was accepted.
Enrollment wrote `SKILL.md` outside the repository skill directory. A later
projection wrote outside each configured `skills_dest`, despite the command
returning success.

**Security outcome:** This is equivalent to a SOAR playbook accepting an
unvalidated response-action path: the base destination is approved, but attacker-
controlled path components redirect the action outside the approved target.

**Required resolution:**

- Introduce one canonical skill-name validator used at every entry point.
- Reject absolute paths, drive-qualified paths, path separators, dot segments,
  control characters, empty names, and names outside the verified portable
  runtime naming grammar.
- After joining a name to a source or destination directory, resolve the complete
  path and verify containment under the expected canonical root.
- Validate `managed_skills` during config load so hand-edited YAML cannot bypass
  CLI validation.
- Quote or structurally serialize skill names when updating YAML; do not construct
  YAML list entries from unchecked strings.

**Acceptance criteria:**

- Traversal and absolute-name tests fail before any file or directory is created.
- Valid names enroll and project on Windows and POSIX paths.
- A malicious `managed_skills` entry causes a controlled configuration error.
- Source and runtime containment are tested independently.

### ACS-002 — Confirmed skill capture does not immediately project the skill

**Severity:** High  
**Affected code:** `capture.py:capture_skill`, `enroll.py:enroll_skill`, CLI
`capture` handler

**Observed behavior:** `capture skill --confirm` wrote the canonical skill and
updated `targets.yaml`, then projected with the stale in-memory configuration.
The command returned success and claimed fan-out, but the new skill appeared only
after a second `project` command reloaded configuration.

**Required resolution:**

- Reload and validate configuration after enrollment changes `managed_skills`, or
  update the in-memory plan through a single explicit transaction object.
- Define success as: canonical source exists, `managed_skills` contains the name,
  every selected runtime contains the expected body and adapter, state hashes are
  current, and audit events exist.
- Do not print “projected” unless those postconditions are verified.
- On incomplete fan-out, return nonzero and state separately whether the source
  change was retained or rolled back.

**Acceptance criteria:** One confirmed command projects the new skill to all three
runtimes, and a simulated projection failure cannot return exit 0.

### ACS-003 — Promote misclassifies source-only movement and loses non-additive edits

**Severity:** High  
**Affected code:** `promote.py:_added_lines`, `promote.py:detect_divergence`,
`promote.py:promote_instruction`

**Observed behavior:**

- A source-only change was labeled a three-way conflict even though the live file
  still matched the last projection.
- A confirmed deletion returned success but restored the deleted content.
- Replacement behavior is based on extracting added lines rather than preserving
  the complete change operation.

**Required resolution:**

- Store enough last-projected information to distinguish four states:
  clean, source-behind, live-only edit, and true source-plus-live conflict.
- A missing baseline must produce a controlled “establish baseline first” result;
  it must not guess.
- Represent promote changes as additions, deletions, and replacements, not only
  added lines.
- Apply a deletion or replacement only when its source location is uniquely
  attributable to the human-selected target. Ambiguous mapping must refuse before
  source mutation and provide a manual-resolution path.
- Keep the human confirmation gate and deterministic lints before mutation.

**Acceptance criteria:** Goal tests cover append, delete, replace, source-only
movement, live-only movement, true conflict, ambiguous mapping, and missing state.

### ACS-004 — Gemini instructions contradict the installed skill mechanism

**Severity:** High  
**Affected files:** `overlays/gemini.md`, `references/gemini-tools.md`,
`docs/AUDIT_BRIEF.md`, Gemini lesson material

**Observed behavior:** The overlay and audit brief state that `activate_skill`
does not exist, while installed Gemini CLI 0.26.0 defines that tool and the Gemini
adapter lists it.

**Required resolution:**

- Reconcile the overlay, adapter, audit brief, and lessons against one verified
  Gemini CLI version.
- Record the verified version and verification date in the runtime adapter.
- Keep file auto-discovery and model-time skill activation as separate concepts.
- Add a deterministic consistency test that fails when the overlay denies a tool
  the adapter requires.

**Acceptance criteria:** Generated Gemini instructions contain no contradictory
skill-loading guidance, and the documented manual check works on the supported
Gemini version.

### ACS-005 — Hook installation can partially fail and still return success

**Severity:** Medium  
**Affected code:** CLI `install-hooks` handler, `settingsedit.py`

**Observed behavior:** The Gemini migration subprocess return code is ignored.
Codex hook errors are reported as skipped, but the overall command still exits 0.

**Required resolution:**

- Model Claude, Gemini, and Codex installation as independent results with
  `installed`, `already-present`, `skipped`, or `failed` status.
- Treat a nonzero migration return code as failure and capture a safe diagnostic
  without exposing configuration contents.
- Verify the expected hook after each installation step.
- Return nonzero if any requested runtime fails.
- Add a read-only `--dry-run` that parses, validates, and shows intended changes.
- Preserve idempotency, backup-first behavior, and existing settings.

**Acceptance criteria:** Partial failure cannot return 0 or print an unqualified
success message; each runtime result is machine-testable.

### ACS-006 — Write safety is not uniformly atomic, backed up, audited, or transactional

**Severity:** Medium  
**Affected code:** `state.py:save_state`, capture and enrollment write paths,
project/capture orchestration, audit handling

**Observed behavior:** State uses direct replacement-prone writes; source capture
and enrollment changes lack the advertised backup and audit events; multi-step
commands can mutate source before a later projection error.

**Required resolution:**

- Use atomic state writes and validate state before replacement.
- Back up existing source files before capture or enrollment overwrites them.
- Audit source mutations separately from runtime projection mutations.
- Preflight all deterministic validations and destination plans before the first
  consequential write.
- Define explicit partial-failure semantics. If full rollback is not safe, retain
  recoverable state, return nonzero, and print the exact incomplete stage.
- Correct documentation so “audit log” is not described as tamper-evident or as a
  record of events that are not actually logged.

**Acceptance criteria:** Fault-injection tests at every write boundary prove that
no command reports full success after partial completion and that recovery data is
available.

### ACS-007 — Windows console encoding can fail after writes complete

**Severity:** Medium  
**Affected code:** CLI output and diff rendering

**Observed behavior:** UTF-8 content containing a BOM produced a
`UnicodeEncodeError` while printing a promote diff under a CP-1252 console. The
source and runtime writes had already completed, but the process exited 1.

**Required resolution:**

- Establish a documented UTF-8 CLI output strategy for Windows.
- Sanitize or safely encode arbitrary diff content without hiding the changed
  bytes from the reviewer.
- Print the reviewed diff before committing where the workflow permits.
- Ensure any post-write output failure is caught and cannot obscure completion
  state.

**Acceptance criteria:** Tests cover BOM, emoji, non-Latin text, invalid console
encoding, and redirected output without changing the semantic diff.

### ACS-008 — Secret and neutral-language lints have material coverage gaps

**Severity:** Low, defense-in-depth  
**Affected code:** `secrets.py`, `neutralize.py`

**Observed behavior:** Synthetic raw OpenAI-style keys, JWTs, and PEM headers were
not detected. Lowercase or current tool names bypassed neutral-language lint,
while harmless quoted prose produced a secret false positive.

**Required resolution:**

- Add synthetic positive and negative corpora for current credential and tool
  formats; never use real credentials in tests.
- Make appropriate neutral-language matching case-insensitive and include the
  supported runtime adapters' current tool identifiers.
- Separate high-confidence blocking matches from advisory low-confidence matches.
- Document that repository scanning and human review remain required; pattern
  matching must not be represented as complete secret detection.
- Evaluate a pinned, free/open-source repository secret scanner for CI rather than
  expanding the runtime denylist without limit. Dependency adoption requires a
  separate owner decision.

**Acceptance criteria:** The documented corpus has expected blocking/advisory
results and the false-positive set remains explicit.

### ACS-009 — Documentation and safety claims contradict the live implementation

**Severity:** Medium  
**Affected files:** `README.md`, `SECURITY.md`, `docs/ARCHITECTURE.md`,
`docs/LIMITATIONS.md`, `docs/EVALUATION.md`, `HANDOFF.md`, lessons and audit brief

**Observed behavior:** Completed capabilities are described as unimplemented,
test totals disagree, and claims such as “every action is logged” or “nothing is
written without preview” exceed current behavior.

**Required resolution:**

- Establish one current-status section and one canonical validation count source.
- Update architecture, limitations, security, evaluation, handoff, lessons, and
  audit instructions after code behavior is finalized.
- Replace absolute safety language with precise per-command guarantees.
- Add a documentation consistency check for test totals, capability status, and
  known superseded runtime facts.

**Acceptance criteria:** Fixed-string and link audits find no contradictory status,
test count, hook, or Gemini activation statements.

### ACS-010 — Release and reproducibility controls are incomplete

**Severity:** Low until publication; release-blocking for a public v1  
**Affected areas:** license, CI, pre-commit installation, cross-platform coverage,
installation/usage/troubleshooting documentation, build dependency pinning

**Observed behavior:** No license is selected, no CI workflow exists, the tracked
pre-commit hook is not active, cross-platform claims are not continuously tested,
and several required standalone documents are absent.

**Required resolution:**

- Obtain owner approval for a license; do not select one automatically.
- Add pinned CI actions and a Python/OS matrix appropriate to supported platforms.
- Provide an explicit, verifiable pre-commit installation path or remove claims
  that it already runs.
- Create `docs/INSTALLATION.md`, `docs/USAGE.md`, and
  `docs/TROUBLESHOOTING.md`; link them from the README.
- Pin build tooling consistently with repository supply-chain policy.
- Record unsupported platforms honestly until CI or manual evidence exists.

**Acceptance criteria:** A clean clone can install, validate, and run the sandbox
workflow from documentation alone; publication remains blocked until the owner
selects a license.

## 5. Required implementation order

1. **Security containment:** ACS-001, then ACS-008.
2. **Write and workflow correctness:** ACS-006, ACS-002, ACS-003, ACS-007.
3. **Runtime integration:** ACS-004 and ACS-005.
4. **Documentation and release:** ACS-009 and ACS-010 only after behavior stabilizes.

Later phases may add tests earlier, but no later phase may weaken an earlier
security acceptance criterion.

## 6. Global verification requirements

- Preserve the existing 123-test baseline while adding requirement-linked tests.
- Every consequential path gets a negative test: invalid path, failed validation,
  failed write, wrong credentials where applicable, or ambiguous promote input.
- Run the documented isolated pytest command on every supported OS.
- Run sandboxed CLI goal tests without touching real runtime configuration.
- Verify `git status` contains only the intended implementation slice before
  handoff.
- Apply the critique contract after each plan, with a maximum of two critique/fix
  cycles per slice.

## 7. Explicitly out of scope

- Automatic git commit or push.
- Cloud-hosted synchronization or multi-user coordination.
- Automatic conflict merging when source attribution is ambiguous.
- A claim that pattern matching eliminates all secret or prompt-injection risk.
- Supporting additional AI runtimes before the three current adapters are correct.

