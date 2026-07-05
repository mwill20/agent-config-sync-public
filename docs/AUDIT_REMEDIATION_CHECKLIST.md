# Audit Remediation Checklist

**Status:** ACS-001 through ACS-010 implemented and locally verified on 2026-06-30.  
**Specification:** `docs/superpowers/specs/2026-06-29-audit-issue-resolution-spec.md`  
**Final validation:** `148 passed in 14.06s` with the isolated pytest command recorded in `docs/EVALUATION.md`.

## Issue status

| ID | Issue | Severity | Plan | Status | Evidence |
|---|---|---:|---|---|---|
| ACS-001 | Skill-name source/runtime allowlist escape | High | A | Verified | `validation.py`; config/enroll/capture/skills/neutralize containment tests; traversal rejected before write |
| ACS-002 | Confirmed skill capture misses immediate fan-out | High | B | Verified | `test_cli_capture_skill_confirm_projects_immediately`; config reload after enrollment |
| ACS-003 | Promote false conflict and non-additive edit loss | High | B | Verified | Promote tests cover append, delete, replace, source-behind, true conflict, missing baseline, ambiguous mapping |
| ACS-004 | Gemini `activate_skill` contradiction | High | C | Verified | `overlays/gemini.md`, `references/gemini-tools.md`, `docs/AUDIT_BRIEF.md`, `test_runtime_docs.py` |
| ACS-005 | Hook partial failure returns success | Medium | C | Verified | Dry-run no-write behavior tested; Gemini nonzero/exception and Codex parse-failure tests return exit 3 |
| ACS-006 | Inconsistent atomicity, backup, audit, and partial-failure semantics | Medium | B | Verified | Atomic state write; source backup/audit tests; post-capture projection failures return nonzero recovery state |
| ACS-007 | Windows Unicode output failure after completed writes | Medium | B | Verified | CLI stdout configured to UTF-8/backslashreplace; unit test covers configuration |
| ACS-008 | Secret and neutral-language lint gaps | Low | A | Verified | Expanded secret/tool corpora and false-positive tests pass |
| ACS-009 | Documentation and safety-claim drift | Medium | C | Verified | README, architecture, limitations, security, audit brief, evaluation, threat model reconciled |
| ACS-010 | Release/reproducibility gaps | Release blocker | C | Verified | Private-repo no-license decision recorded; installation/usage/troubleshooting docs, pinned-checkout CI workflow, documented validation path |

## Plan A - Security containment

- [x] Portable skill-name contract implemented: lowercase letters, numbers, single hyphens, max 64 chars, Windows reserved names refused.
- [x] Central name validation implemented at config, enroll, capture, skill projection, and variant-read boundaries.
- [x] `managed_skills` config validation implemented, including duplicate rejection.
- [x] Final source-path containment enforced with `resolve_within`.
- [x] Final runtime-path containment enforced with `resolve_within`.
- [x] YAML update path serializes skill names with JSON quoting.
- [x] Traversal tests prove invalid names abort before source/config writes.
- [x] Synthetic secret corpus expanded: OpenAI, private-key header, JWT-like token.
- [x] Runtime tool-name corpus expanded: shell/web/request-user/case-insensitive forms.
- [x] Blocking versus advisory lint behavior documented in security/evaluation/limitations docs.
- [x] Repository secret-scanner decision recorded: pattern lint remains local; dedicated scanner is a future CI hardening option, not selected here.
- [x] Full isolated suite passes.
- [x] Security critique completed through regression tests and threat-model updates.

## Plan B - Workflow correctness

- [x] Write-stage and recovery contract documented in usage/troubleshooting/evaluation.
- [x] State writes are atomic and validated.
- [x] Source capture/enrollment backups implemented.
- [x] Source mutation audit events implemented.
- [x] Full preflight added for skill enrollment target YAML rewrite before canonical skill write.
- [x] Partial post-capture projection failure returns nonzero with recovery state.
- [x] Confirmed skill capture projects in one command.
- [x] Capture postconditions covered by CLI regression test.
- [x] True promote state classification implemented.
- [x] Missing promote baseline refuses safely.
- [x] Append promote goal test passes.
- [x] Delete promote goal test passes.
- [x] Replace promote goal test passes.
- [x] Ambiguous mapping refuses before write.
- [x] Windows UTF-8 output configuration test passes.
- [x] Fault-injection coverage includes mid-loop projection state persistence and hook failures.
- [x] Full isolated suite passes.
- [x] Security and correctness critique completed through focused should-fail tests.

## Plan C - Runtime and release readiness

- [x] Supported Gemini runtime version recorded: Gemini CLI 0.26.0.
- [x] Gemini discovery/activation guidance reconciled.
- [x] Overlay/adapter contradiction test passes.
- [x] Hook installer read-only dry run implemented and tested.
- [x] Hook installer reports per-runtime outcomes and returns nonzero on failures.
- [x] Nonzero Gemini migration is a command failure.
- [x] Hook postconditions covered by unit-level config parse/command checks.
- [x] Partial installation cannot return 0 when a resolvable step fails.
- [ ] Fresh-session Claude hook execution: not re-run against real runtime in this remediation pass; prior live verification documented.
- [ ] Fresh-session Codex hook execution: not re-run against real runtime in this remediation pass; prior live verification documented.
- [ ] Fresh-session Gemini hook execution: not re-run against real runtime in this remediation pass; prior live verification documented.
- [x] Architecture documentation reconciled.
- [x] Security and threat models reconciled.
- [x] Limitations documentation reconciled.
- [x] Evaluation and audit brief reconciled.
- [ ] Handoff and lessons reconciled: lesson files are historical walkthroughs and may need a separate education-doc refresh.
- [x] Documentation contradiction scan over active docs passes for the audited stale claims.
- [x] Owner decided no license file is needed while the repository remains private.
- [x] CI matrix added with pinned checkout action.
- [x] Pre-commit installation path documented via `hooks/pre-commit` and installation docs.
- [x] Installation, usage, and troubleshooting docs added.
- [ ] Clean-clone quickstart verified on supported platforms: CI workflow added; local clean-clone across all hosted OSes not run in this environment.
- [x] Final security critique completed through tests and threat model.
- [x] Final repository-readiness critique completed through repo-standards docs pass.

## Required validation evidence

- [x] Baseline command and final count recorded in `docs/EVALUATION.md`.
- [x] Each issue has focused goal coverage and at least one should-fail path where applicable.
- [x] Sandboxed/unit transcripts cover project, capture, promote, and hooks without touching real runtime config.
- [x] No automated test touched real runtime configuration.
- [x] `git status` reviewed during remediation.
- [x] Remaining limitations and accepted risks are recorded below.

## Owner decision gates / accepted risks

- [ ] Approve the portable skill-name grammar for any existing nonconforming personal skills.
- [ ] Decide whether to add a dedicated pinned CI-only secret scanner.
- [x] Ambiguous promote changes remain manual-only and are documented.
- [x] License decision recorded: no license file while private; revisit before publication or third-party reuse.
- [ ] Confirm the supported OS/Python matrix for v1 beyond the added hosted-runner CI workflow.

## Operational hardening follow-up (2026-06-30)

**Specification:** `docs/implementation_plan.md`

| ID | Issue | Status | Evidence |
|---|---|---|---|
| OP-001 | Backup timestamp collision risk | Verified | `default_stamp()` microseconds; `backup()` collision suffix; same-stamp backup test |
| OP-002 | Unbounded backup accumulation | Verified | `prune-backups` dry-run default, `--confirm` deletion, retention tests, audit event |
| OP-003 | Concurrent mutating command race | Verified | `lock.py`; CLI lock around mutating paths; lock metadata/no-write-on-lock-failure test |
| OP-004 | Hook bad-shape crashes | Verified | Claude/Codex schema validation tests raise `HookInstallError` without writes |
| OP-005 | Cross-platform subprocess wiring gap | Verified | `tests/test_cli_e2e.py`; CI hermetic Gemini CLI E2E step |
| OP-006 | Docs/lessons/tradeoffs drift | Verified | README, usage, troubleshooting, architecture, limitations, tradeoffs, lesson 11, threat model updated |

Final operational-hardening validation: `161 passed in 8.77s` with the isolated pytest command recorded in `docs/EVALUATION.md`.

Operational hardening keeps accepted limitations explicit: Gemini migration is
still owned by Gemini CLI, CI still does not install live runtimes, and stale
locks require manual operator inspection.


