# Threat Model — Capture / Promote Surface

**Status:** Active — covers Slice C (`capture`) and Plan 3 (`promote`), now built.
**Framework:** MITRE ATLAS + OWASP LLM Top 10 (indirect prompt injection is the
headline risk) with STRIDE for the file-write mechanics.

---

## Why this surface is the highest-risk in the project

`capture` and `promote` take content that may originate from an attacker
(pasted text, web content, a hand-edited runtime file) and write it into the
**source of truth**, which `project` then fans out to **three AI agents at once**.
A poisoned `_shared/core.md` is an indirect-prompt-injection amplifier.

## Assets

- `_shared/core.md`, `overlays/<vendor>.md`, `skills/<name>/SKILL.md` — source of truth.
- `config/targets.yaml` — the write allowlist.
- The projected runtime files + skills.

## Trust boundaries

1. **Captured / promoted content → source.** Untrusted text crosses into the
   source. (`capture.py`, `promote.py`)
2. **Source → three runtimes.** One edit steers all three agents. (`project.py`)

## Threats & mitigations (code-mapped)

| ID | Threat | Mitigation | Code pointer |
|----|--------|------------|--------------|
| T1 | Poisoned skill/standard fans out to all 3 agents (indirect prompt injection) | **Human confirm gate** (`--confirm`; dry-run is the default) + deterministic lints; the AI's routing/review is advisory only and performed by the chat agent, never by the tool | `capture.capture_standard`/`capture_skill` (confirm flag); cli capture/promote handlers |
| T2 | Secret smuggled into source via capture/promote | `secrets.find_secrets` runs **before any write, even in dry-run** — abort on match | `capture.capture_standard` / `capture.capture_skill` |
| T3 | Non-neutral skill body projected to all runtimes | `neutralize.find_vendor_terms` binding gate | `capture.capture_skill`, `enroll.enroll_skill` |
| T4 | Write escapes the allowlist | `config._validate_dest` / `_validate_source`; capture targets restricted to `core`/known runtime/`skills/` | `config.py`, `capture._standard_path` |
| T5 | Reverse `promote` silently auto-merges a source-also-moved conflict | 3-way conflict **detected via `.sync-state.json` hash and raised**, never merged | `promote.detect_divergence`, `promote.PromoteConflict` |
| T6 | Probabilistic/AI judgment authorizes a write | Tool exposes only deterministic gates + an explicit `confirm`; a human passes `--confirm` | cli (capture/promote require `--confirm`) |
| T7 | Promote overwrites a hand-edited runtime, losing other in-flight edits | Force-reproject affects one drifted runtime (blanket-force guard blocks >1); every overwrite is backed up | `promote.promote_instruction`, `project.ForceScopeError`, `fsutil.backup` |
| T8 | Skill name escapes source or runtime skill directories | Central skill-name validation plus final resolved-path containment before source/runtime skill reads and writes | `validation.validate_skill_name`, `validation.resolve_within`, `enroll.py`, `skills.py`, `neutralize.py` |
| T9 | Promote deletion/replacement mutates the wrong source block | Non-append promote changes apply only when the removed/replaced block occurs exactly once in the selected source target; ambiguous mappings abort before write | `promote._apply_exact_changes` |

## Residual risk

- Secret lint is pattern-based (reduces, not eliminates) — see LIMITATIONS.
- Neutral-language lint is a curated denylist (see LIMITATIONS) — a human still
  reviews the diff before `--confirm`.
- v1 `promote` flags 3-way conflicts but does not offer a guided merge (a true
  3-way merge needs last-projected *content*, not just its hash — future `state.py`
  enhancement; Plan 3 spec §9).
- The human confirm is the binding control for prompt-injection content; if a user
  blindly `--confirm`s attacker text, it propagates. Dry-run-by-default + the
  visible diff are the mitigations; user judgment is the last line.
