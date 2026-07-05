# Changelog

Notable changes, newest first. Dates are commit dates on `main`.

## 2026-07-03

- Neutral-language gate now runs on managed skill bodies at projection time
  (previously enrollment-only) and detects wrapped slash-commands that name
  managed skills (e.g. backtick-wrapped). Found by a Codex-run audit of the
  projected `repo-standards` skill.
- Companion-file projection: reviewed text companions under `skills/<name>/`
  fan out to every runtime through the neutral-language and secret gates, with
  a text-only extension allowlist, hidden-path exclusion, adapter-collision
  refusal (case-insensitive), symlink/source containment, and UTF-8 validation.
- Baseline fix: files byte-identical at first projection now get a recorded
  hash, so later source edits classify as clean updates instead of false drift.
- Skill enrollment sweep: 23 global skills managed (16 verbatim, 6 neutralized,
  `config-sync` pre-existing); `notebooklm` deliberately excluded.
- Repaired double-mangled UTF-8 in `docs/EVALUATION.md`; stripped a BOM from
  `skills/lesson-gen/SKILL.md` that broke frontmatter parsing.

## 2026-07-01

- Force-scope guard enforced across skills; promote reprojects with
  runtime-scoped force only.

## 2026-06-30

- Operational hardening: collision-safe backups, `prune-backups`, repo-scoped
  mutation locks, hook shape validation, hermetic CLI E2E coverage.
- ACS-001..010 audit remediation (path containment, capture fan-out, promote
  exactness, hook dry-run/failure exits, lint expansion).

## 2026-06-28

- v1 feature-complete: forward projection, managed skills, capture-from-chat,
  reverse promote, startup drift hooks (Claude/Codex/Gemini), doctor.

## 2026-06-27

- Forward projection for instruction files; drift refusal with scoped force.
