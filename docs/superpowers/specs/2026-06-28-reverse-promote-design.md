# Design Spec — agent-config-sync Plan 3 (Reverse `promote`)

**Status:** Approved design (pre-implementation)
**Date:** 2026-06-28
**Author:** Brainstormed collaboratively (owner + Claude)
**Builds on:** Plan 1 (instruction-file projection, built) and Plan 2 (skills + discovery + **capture engine**) — `docs/superpowers/specs/2026-06-28-skills-discovery-capture-design.md`
**Parent design:** `docs/superpowers/specs/2026-06-27-cross-runtime-sync-design.md` (D-2, §6, §7)
**Next step:** writing-plans → implementation slices

---

## 1. Problem & goal

Forward projection (Plans 1–2) pushes the source out to every runtime. But the
owner's key use case is the **reverse**: a learning made *inside one runtime* —
a hand-edit to `~/.gemini/GEMINI.md`, a skill authored while working in Codex —
must be liftable back into the source and then propagated to the others.
"Learn something in Gemini, get it in Claude."

The forward drift guard already **detects** this divergence (it refuses to
overwrite an out-of-band edit). `promote` is the **resolution path**: it takes
that divergence, routes each piece to the right source location, and re-projects.

**Goal:** simple and safe for a non-dev to pull a good change out of any runtime
and share it — with the same deterministic guardrails as the forward path, and a
human diff review as the security gate (a reverse edit fans out to three agents).

## 2. Locked decisions

| # | Decision | Choice |
|---|----------|--------|
| D3-1 | Engine | **Shared.** `promote` feeds the Plan 2 **capture engine** (route → lint → diff → AI advisory review → human confirm → commit → project). `promote` adds only a front layer: *detect divergence + classify per section.* |
| D3-2 | Divergence basis | Diff the **live file against the current projection** (`projected_for`). Detect the source-also-moved case via the `.sync-state.json` hash and **flag a 3-way conflict for manual resolution — never silent auto-merge.** |
| D3-3 | Routing granularity | **Per markdown `##` section.** AI proposes shared→`core` / vendor→`overlay` / `skill` with a one-line reason; the human approves or flips each. |
| D3-4 | New skill in a runtime | Detected and offered for **enrollment via Plan 2 neutralize-on-enrollment** (neutral-language lint + cross-runtime reconciliation + review), then projected to the others. |
| D3-5 | Security gate | Human diff review is the binding control (parent D-2); deterministic lints (secret/allowlist) also bind; AI routing/review is advisory only. |

## 3. Dependency & build order

`promote` reuses the capture backend, so **Plan 2 capability C (capture) is built
first.** Overall sequence across plans: Plan 2 A (skills) → B (discovery) → C
(capture) → **Plan 3 (promote)**. Plan 3 is one implementation slice on top of C.

## 4. Architecture

### 4.1 New component

```
src/agent_config_sync/promote.py     # the front layer (below); delegates to capture engine
```

`promote.py` does **detection + classification**, then hands each approved
divergence to the capture engine as a proposed source change. It owns no
write/commit/project logic of its own — that lives in the shared engine.

### 4.2 Flow — `promote <runtime> [path]`

1. **Detect divergence.** Compute `projected = projected_for(runtime)` for the
   target instruction file (or skill). Compare against the live file.
   - If live == projected → nothing to promote (report clean).
   - **Conflict check (D3-2):** if `sha256(projected) != .sync-state.json` hash for
     that target, the *source* also moved since last project. Flag a **3-way
     conflict** for the affected sections and route them to manual resolution
     (show both deltas, plain language, no auto-merge).
2. **Classify per section (D3-3).** Split the live-vs-projected delta by markdown
   `##` section. For each diverging section the AI proposes a destination
   (shared→`core.md` / vendor→`overlays/<runtime>.md` / a `skill`) with a one-line
   reason.
3. **Human routes.** The owner approves or flips each section's destination
   (per-section, not per-hunk — readable for a non-dev).
4. **Hand to the capture engine.** Each routed section becomes a proposed source
   change. The engine runs the binding deterministic lints (secret/allowlist; and
   neutral-language lint for skill content), shows the consolidated source diff,
   posts the **advisory** AI review, waits for the **human confirm**, then
   commits, pushes (if a remote exists), and re-projects to all runtimes.

### 4.3 New skill case (D3-4)

`promote <runtime>` (no path) also scans the runtime's `skills/` dir for a skill
**not** in `managed_skills`. If found, it offers enrollment via Plan 2's
neutralize-on-enrollment (neutral-language lint → AI-proposed neutral body →
cross-runtime reconciliation if it already exists elsewhere and differs → human
review). On approval it becomes a managed skill and projects to the others.

### 4.4 `promote` with no path

Scans **all three runtimes** for diverged instruction files *and* unmanaged
skills, and prints a plain-language summary (reuses Plan 2 `doctor` + the shared
failure layer). The owner picks what to promote from there.

## 5. Data flow (the key use case)

```
edit ~/.gemini/GEMINI.md  ──promote gemini──▶  diff live vs projection
        │                                            │ classify per section
        │                                            ▼
        │                         AI proposes: "this section is shared → core.md"
        │                                            │ human approves
        │                                            ▼
        │                       capture engine: lint → diff → review → confirm
        │                                            ▼
        └────────────▶  lands in _shared/core.md ──project──▶ now in CLAUDE.md + AGENTS.md
```

A vendor-specific tweak instead routes to `overlays/gemini.md` and stays local.

## 6. Security & safety

- **Reverse flow is the highest-risk surface.** A promoted edit to `core.md` fans
  out to all three agents — an indirect-prompt-injection amplifier. The **human
  diff review is the security control** (parent D-2), not a UX nicety. The AI
  routing/review is advisory and visually segregated; it never authorizes a write.
- **Deterministic gates bind:** secret-lint, allowlist, and (for skills)
  neutral-language lint, inherited from the capture engine.
- **No silent merges (D3-2):** a source-also-moved conflict is flagged for manual
  resolution, never auto-merged.
- **Backups + audit:** every re-project backs up the targets first and appends to
  `.sync-audit.log`; promote actions are logged (runtime, sections routed,
  destinations, content hashes, stamp).
- **Threat model:** the capture/promote surface gets a `docs/threat-models/` entry
  (shared with Plan 2-C) before the reverse path is considered hardened.

## 7. Testing (tied to goals; includes should-fail)

- **Reverse goal test (the literal requirement):** in a fake 3-runtime tree, edit
  `GEMINI.md` → `promote gemini` → route the section to shared → re-project →
  **assert the change now appears in CLAUDE.md and AGENTS.md.**
- **Vendor-routing test:** a section routed to `overlays/gemini.md` appears only in
  `GEMINI.md` after re-project, not in the others.
- **Should-fail / safety:**
  - 3-way conflict (source moved + live edited) is **flagged for manual
    resolution, not merged**.
  - a secret inside a promoted section **aborts before any source write**.
  - promoting a skill that differs across runtimes triggers **reconciliation**
    before enrollment.
  - `promote` refuses to act outside the `targets.yaml` allowlist.
- **Idempotency:** promoting, then re-running `promote` on the same runtime, finds
  nothing to promote (live == projection after the round trip).

## 8. Deliverables

- `src/agent_config_sync/promote.py` (detection + per-section classification),
  delegating to the Plan 2 capture engine.
- CLI: `agent-config-sync promote <runtime> [path]` and bare `promote` (scan-all).
- Tests above (reverse goal + should-fail).
- `docs/threat-models/` entry (shared with Plan 2-C capture surface).
- README / AGENTS / LIMITATIONS updates for the reverse flow and the 3-way-conflict
  limitation.

## 9. Out of scope / future

- **True 3-way merge.** v1 detects-and-flags the source-also-moved conflict. A
  real 3-way merge needs the last-projected *content* (not just its hash) stored —
  a future enhancement to `state.py` / a content cache.
- **Auto/bidirectional merge** — permanently rejected (no source of truth at
  conflict time; parent §3 non-goal).
- **Promoting non-instruction/non-skill config** (MCP, settings, hooks) — out of
  scope, same as parent §3.
