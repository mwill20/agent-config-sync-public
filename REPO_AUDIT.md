# Repository Audit

Current-state scorecard, updated 2026-07-04 after V2 completion (sensing,
ambient watcher, overlap detector, Lessons 12-13).
Supersedes the scorecard produced by the 2026-07-03 external (Codex) audit;
that audit's findings are closed (see `CHANGELOG.md` and `HANDOFF.md`).

## Summary

| Area | Status | Priority | Notes |
|------|--------|----------|-------|
| Purpose and audience | PASS | High | Purpose in the first lines; intended-audience section present |
| Installation and quickstart | PASS | High | Clone/venv/install/dry-run flow with expected output |
| Usage examples | PASS | High | Everyday commands, skills, sense/overlap/watcher, capture/promote, hooks, pruning; `examples/` present |
| Architecture documentation | PASS | High | Overview, mental model, design-decision table current incl. companion payload |
| Dependencies and environment | PASS | High | Exact pins (setuptools, pyyaml, pytest); Python 3.11 floor; CI SHAs pinned |
| Evaluation and results | PASS | High | Append-only log in docs/EVALUATION.md; 208-test baseline incl. live drill documentation with proof rationale |
| Dataset documentation | N/A | Medium | No dataset; user config is runtime input |
| Model documentation | N/A | Medium | No AI/ML model is trained, fine-tuned, or invoked by the tool itself |
| Security documentation | PASS | High | SECURITY.md + four threat models with code-mapped mitigations |
| Deployment documentation | N/A | Medium | Local operator CLI; not deployed as a service |
| Monitoring and maintenance | PASS | Medium | Daily ambient watcher with heartbeat + session-start sensing + audit log + doctor |
| Limitations and trade-offs | PASS | High | LIMITATIONS and TRADEOFFS current (companion payload reconciled) |
| License and usage rights | PASS | High | MIT (this public mirror) |
| Support and contact | PASS | Medium | Support section in README; SECURITY.md reporting path |
| Visual demo and assets | PASS | Medium | Logo in README; text architecture diagram; Mermaid-ready docs |

## Strengths

- Deterministic, tested security gates (secret scan, neutral-language lint at
  enrollment and projection, path containment, drift refusal, scoped force)
  with should-fail tests for every refusal path.
- Append-only evaluation log and audit trail; changes land with tests and docs.
- Cross-runtime behavior verified live in all three runtimes (Claude, Codex,
  Gemini/AntiGravity), including an independent Codex-run audit of this repo.

## Remaining gaps

- LICENSE is a deliberate placeholder until the owner selects one (blocking
  only for public release, which is not planned).
- Lessons complete through Lesson 13 (ambient watcher); Lesson 14 reserved for gated Tier 3.
- Executable skill companions are out of scope by design (see TRADEOFFS).

## Priority fix order

1. None blocking for the current private, single-operator scope.
2. Before any public release: select a license, re-run this audit.
