# Plan B — Capture, Promote, and Write-Safety Correctness

**Status:** Not started  
**Issues:** ACS-002, ACS-003, ACS-006, ACS-007  
**Depends on:** Plan A complete

## Goal

Make each multi-step command behave like a deterministic SOAR playbook: validate
the complete action plan first, execute known stages, verify postconditions, and
report partial failure explicitly.

## Task 1 — Define the write transaction and recovery contract

- [ ] Inventory every write performed by `project`, `project_skills`, `capture`,
      `enroll`, `promote`, state persistence, backup, and audit logging.
- [ ] Define preflight, source mutation, runtime projection, verification, state,
      and audit stages.
- [ ] Decide per stage whether rollback is safe or whether recovery-in-place is
      required.
- [ ] Define exit codes and structured result fields for full success, dry run,
      validation refusal, partial completion, and recovery failure.
- [ ] Add fault-injection tests before implementation.

## Task 2 — Harden state, backup, and audit behavior

- [ ] Make state persistence atomic and validate serialized state before replace.
- [ ] Back up existing canonical source files before capture/enrollment overwrite.
- [ ] Add source-mutation audit records distinct from projection records.
- [ ] Ensure a failed audit append cannot be silently reported as complete success.
- [ ] Test failure immediately before and after every write boundary.

## Task 3 — Correct confirmed skill capture fan-out

- [ ] Build or reload the post-enrollment configuration before projection.
- [ ] Preflight all skill body, adapter, destination, secret, and drift checks.
- [ ] Project the new skill and adapter to every selected runtime in the same
      confirmed workflow.
- [ ] Verify destination contents, state hashes, and audit events before success.
- [ ] Return nonzero with precise recovery guidance if fan-out is incomplete.

**Goal test:** One `capture skill --confirm` command creates the canonical source,
enrolls it, projects all runtime copies, and leaves `check` clean.

## Task 4 — Implement true promote state classification

- [ ] Persist or otherwise obtain the last-projected content required for a true
      three-way comparison.
- [ ] Implement clean, source-behind, live-only, true-conflict, and missing-baseline
      classifications.
- [ ] Prove source-only movement is not a conflict.
- [ ] Prove both source and live movement is refused before mutation.
- [ ] Keep scan-all output and exit behavior consistent with the classification.

## Task 5 — Preserve additions, deletions, and replacements

- [ ] Replace added-lines extraction with a complete change representation.
- [ ] Map exact changes to the human-selected source target.
- [ ] Apply exact deletion/replacement only when the source match is unique.
- [ ] Refuse ambiguous mapping without modifying source or runtimes.
- [ ] Show the complete proposed source diff before confirmation.

**Goal tests:** append, delete, replace, multi-line move, ambiguous duplicate block,
vendor-only routing, and shared routing.

## Task 6 — Make CLI output safe on Windows

- [ ] Establish the supported UTF-8 output behavior for interactive and redirected
      Windows consoles.
- [ ] Add tests for BOM, emoji, non-Latin text, and a restricted console codec.
- [ ] Catch output encoding errors and preserve truthful completion status.
- [ ] Confirm no secret or internal configuration value appears in diagnostics.

## Task 7 — Verify and critique

- [ ] Run focused workflow and fault-injection tests.
- [ ] Run the full isolated suite.
- [ ] Repeat the audit's capture and promote sandbox scenarios.
- [ ] Verify backups, audit records, state, and `check` after each goal scenario.
- [ ] Perform security-first critique against ACS-002, ACS-003, ACS-006, and
      ACS-007.

## Plan B completion gate

Plan B is complete only when successful commands satisfy verified postconditions,
unsupported/ambiguous promote operations refuse before mutation, and every tested
partial failure produces recoverable state plus a nonzero result.

