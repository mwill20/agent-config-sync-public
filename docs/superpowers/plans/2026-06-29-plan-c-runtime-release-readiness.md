# Plan C — Runtime Integration and Release Readiness

**Status:** Not started  
**Issues:** ACS-004, ACS-005, ACS-009, ACS-010  
**Depends on:** Plans A and B complete

## Goal

Align runtime adapters, hook installation, documentation, and release evidence
with the behavior proven by Plans A and B.

## Task 1 — Re-verify runtime capability contracts

- [ ] Record installed Claude, Codex, and Gemini versions used for verification.
- [ ] Verify instruction-file discovery, skill discovery, skill activation, and
      SessionStart hook behavior for each runtime.
- [ ] Correct Gemini auto-discovery versus `activate_skill` guidance.
- [ ] Reconcile every adapter with its overlay and audit instructions.
- [ ] Add deterministic contradiction tests for required/denied tool names.

## Task 2 — Make hook installation truthful and verifiable

- [ ] Add a read-only `install-hooks --dry-run` plan showing each target.
- [ ] Produce per-runtime result states.
- [ ] Check Gemini subprocess return code and capture a safe diagnostic.
- [ ] Parse each resulting config and verify the exact fixed hook exists.
- [ ] Return nonzero when any requested runtime fails or remains unverified.
- [ ] Test preservation of unrelated settings, idempotency, malformed structures,
      missing CLIs, subprocess failure, and postcondition failure.
- [ ] Run fresh-session manual verification for all available runtimes and record
      evidence without exposing config contents.

## Task 3 — Reconcile architecture, security, and limitations

- [ ] Update `docs/ARCHITECTURE.md` to include skills, capture, promote, hooks,
      state, audit, transaction stages, and trust boundaries.
- [ ] Update `SECURITY.md` with exact write boundaries and residual risks.
- [ ] Update `docs/LIMITATIONS.md` to describe current, not historical, limits.
- [ ] Update threat models with skill-name containment, partial failure, adapter
      drift, and hook postcondition validation.
- [ ] Replace absolute safety statements with per-command guarantees.

## Task 4 — Reconcile evaluation, handoff, lessons, and audit instructions

- [ ] Establish one canonical test-count and validation-command source.
- [ ] Update `docs/EVALUATION.md` with new requirement-linked tests and manual runs.
- [ ] Replace stale completion state in `HANDOFF.md`.
- [ ] Audit every lesson exercise and expected count against live behavior.
- [ ] Update `docs/AUDIT_BRIEF.md` with corrected runtime and negative-path checks.
- [ ] Run fixed-string audits for superseded Plan status, test counts, Codex hook,
      and Gemini activation claims.

## Task 5 — Complete publication prerequisites

- [ ] Ask the owner to select a license; keep publication blocked until approved.
- [ ] Create and link installation, usage, and troubleshooting documents.
- [ ] Add a pinned CI workflow with supported Python and OS coverage.
- [ ] Decide and document how the tracked pre-commit hook is installed.
- [ ] Pin build tooling according to repository dependency policy.
- [ ] Validate a clean-clone quickstart on each supported OS.
- [ ] State private/public access and support paths accurately.

## Task 6 — Final verification and critique

- [ ] Run full CI-equivalent validation locally where possible.
- [ ] Run the complete audit brief in isolated sandboxes.
- [ ] Verify live hook configuration and fresh-session execution.
- [ ] Run documentation link and contradiction checks.
- [ ] Perform final repository-readiness and security critiques.
- [ ] Record remaining residual risks and owner decisions.

## Plan C completion gate

Plan C is complete only when all supported runtime claims have current evidence,
partial hook installation cannot return success, documentation agrees with tests,
and the owner has resolved the license gate for publication.

