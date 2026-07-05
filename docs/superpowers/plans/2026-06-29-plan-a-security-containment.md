# Plan A — Security Containment and Deterministic Validation

**Status:** Not started  
**Issues:** ACS-001, ACS-008  
**Depends on:** Audit issue resolution specification  
**Blocks:** Plans B and C

## Goal

Close the demonstrated skill-path allowlist escape and strengthen deterministic
lint gates before any additional workflow changes are trusted.

## Constraints

- No runtime destination may be tested against real user configuration.
- All traversal and secret fixtures must be synthetic and confined to pytest
  temporary directories.
- No new dependency is added without an explicit owner decision and exact version.
- Security tests must prove failure occurs before filesystem mutation.

## Task 1 — Lock the portable skill-name contract

**Files expected to change:** specification if runtime research changes the
contract; central validation module; config/enroll/capture/skills tests.

- [ ] Verify the accepted skill-name grammar for the supported Claude, Codex, and
      Gemini versions.
- [ ] Record the safe intersection as the canonical contract.
- [ ] Define one error type and one user-facing error message for invalid names.
- [ ] Add table-driven failing tests for absolute, drive-qualified, traversal,
      separator, control-character, empty, and over-limit names.
- [ ] Add positive tests for every supported valid form.

**Exit condition:** The naming contract is evidence-based and tests fail against
the current implementation.

## Task 2 — Enforce containment at every boundary

- [ ] Validate CLI names before reading or writing skill content.
- [ ] Validate every `managed_skills` entry during config load.
- [ ] Resolve the final canonical source path and prove it remains under
      `<repo>/skills/<name>`.
- [ ] Resolve each final runtime path and prove it remains under that runtime's
      configured `skills_dest` and allowed root.
- [ ] Apply the same checks to reconciliation and variant-reading paths.
- [ ] Serialize `managed_skills` without unchecked YAML string construction.

**Goal tests:**

- [ ] Reproduce the audit traversal input and prove no outside file is created.
- [ ] Insert a traversal entry directly into sandbox `targets.yaml` and prove
      config loading fails cleanly.
- [ ] Exercise Windows and POSIX path forms.

## Task 3 — Build deterministic lint corpora

- [ ] Create synthetic secret positive cases for supported vendor prefixes,
      assignment forms, JWT-like tokens, and PEM boundaries.
- [ ] Create negative cases for ordinary documentation prose and placeholders.
- [ ] Create neutral-language cases from all three current runtime adapters,
      including case variations.
- [ ] Classify each pattern as blocking or advisory and document why.
- [ ] Ensure CLI messages never print the matched secret text.

## Task 4 — Decide repository-scanner scope

- [ ] Evaluate one pinned free/open-source scanner for CI-only use.
- [ ] Record maintenance, license, false-positive, and supply-chain implications.
- [ ] Obtain owner approval before adding it; otherwise retain a documented manual
      scan step.

## Task 5 — Verify and critique

- [ ] Run focused security tests.
- [ ] Run the full isolated suite.
- [ ] Run sandboxed traversal probes against the installed CLI.
- [ ] Perform security-first critique against ACS-001 and ACS-008 acceptance
      criteria.
- [ ] Update the remediation checklist with evidence, not only checkmarks.

## Plan A completion gate

Plan A is complete only when all skill source and destination paths are contained
under their approved roots and every invalid-name test proves pre-write refusal.

