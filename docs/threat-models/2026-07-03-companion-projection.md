# Threat Model Addendum — Companion-File Projection (2026-07-03)

Extends `2026-06-28-capture-promote-surface.md`. New surface: text companion
files under `skills/<name>/` in the source repository now fan out to every
runtime alongside `SKILL.md`. Framework: STRIDE (same as parent model).

## Trust boundary change

Companions bypass the `enroll` gate (they enter the source by reviewed
operator copy), so enforcement moves to projection time — the last chokepoint
before content crosses into a runtime.

## Threats and mitigations

| ID | Threat (STRIDE) | Mitigation | Code |
|----|-----------------|------------|------|
| C1 | Poisoned companion fans out to all runtimes (Tampering / indirect prompt injection) | Neutral-language gate runs on every companion at projection; refusal aborts the whole plan before any write | `skills.companion_files` (find_vendor_terms) |
| C2 | Secret smuggled via companion (Information Disclosure) | Secret scan runs per projected file, companions included | `skills.project_skills` (find_secrets) |
| C3 | Executable content smuggled as a companion (Elevation of Privilege) | Text-only extension allowlist; anything else refused fail-closed | `skills.companion_files` (COMPANION_EXTENSIONS) |
| C4 | Companion shadows a runtime adapter file (Spoofing) | Case-insensitive collision refusal against all adapter relpaths (Windows path semantics) | `skills.companion_files` (_ADAPTER_RELPATHS) |
| C5 | Hidden/local state projected (Information Disclosure) | Any path segment starting with `.` is skipped | `skills.companion_files` |
| C6 | Companion path escapes destination (Tampering) | Resolved-path containment on every destination | `validation.resolve_within` via `skills.project_skills` |
| C8 | Symlinked companion reads content from outside the reviewed source tree (Tampering / Information Disclosure) | Each source path is resolved and refused if it escapes the skill's source directory; undecodable (non-UTF-8) content is refused with a named error | `skills.companion_files` (resolve containment) |
| C7 | Runtime-side companion edit silently clobbered (Repudiation) | Per-file drift guard with recorded baselines; scoped `--force` required, backup + audit on overwrite | `skills._classify`, `skills.project_skills` |

## Residual risk

- The neutral-language and secret lints are curated pattern lists; they reduce,
  not eliminate, leakage (see `docs/LIMITATIONS.md`).
- Companion deletion does not propagate: a companion removed from the source
  persists at the runtimes until manually removed. Impact: stale reference
  content, not privilege escalation. Accepted for now; revisit if a companion
  ever has to be *revoked* for content reasons.
- `promote` does not yet lift runtime-side companion edits back into the
  source; the drift guard surfaces them but resolution is manual. TODO.
