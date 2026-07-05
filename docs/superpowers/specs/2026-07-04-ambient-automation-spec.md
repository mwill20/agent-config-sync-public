# Spec: Ambient Automation — Watcher (Tier 2) and Proposal Agent (Tier 3)

**Status:** Tiers 2 AND 3 IMPLEMENTED (2026-07-04). Tier 3 shipped as the operator-invoked variant (`draft-proposals` managed skill) after passing its eval dataset 12/12; the UNATTENDED trigger variant remains gated below.
**Date:** 2026-07-04
**Foundation:** Tier 1 (the `sense` command + session-start hooks) is
implemented on the `v2-sense-automation` branch. Tiers 2 and 3 build on
`sense --json` and are gated on Tier 1 proving insufficient in practice.

---

## Tier 2 — Ambient watcher (deterministic, no LLM)

**Goal:** surface findings between AI sessions, so drift and new skills are
noticed without waiting for the next session open or commit.

**Shape (DECIDED 2026-07-04):** one Windows Task Scheduler entry running the
wrapper once **daily**. Rationale: the operator's AI usage is irregular with
wide gaps, and the session-start hook already covers every sit-down moment —
the watcher's job is background awareness plus dead-watcher detection, so one
run per day suffices and the daily clean-run notification doubles as the
heartbeat (no second schedule exists). Interval revisit trigger: drift ever
found to have gone unnoticed for a multi-day gap that mattered.

**On findings:**
- Emit a Windows notification (DECIDED: zero-dependency PowerShell balloon via
  `System.Windows.Forms.NotifyIcon` — no modules to install; revisit only if
  balloons prove unreliable on this machine).
- Write the JSON to a pending-findings file at
  `%LOCALAPPDATA%/agent-config-sync/pending.json` (NOT the repo; it is
  machine state). The file is written atomically (temp+replace, consistent
  with all other writes in this project) and includes a `generated_at` ISO
  timestamp at the top level. The next session-start `sense` run supersedes
  it.

**On clean run (exit 0, no findings):** DO NOT silently delete the file. Write
`pending.json` with the superseded findings preserved so the resolved message
has data to reference:
`{"count": 0, "findings": [], "generated_at": "<ISO>",
"resolved": {"findings": [<previous findings>], "generated_at": "<previous ISO>"}}`.
The next time an AI session starts, it reads this and tells the operator
"Previous findings from <previous ISO date> appear resolved," naming them. The
file is only overwritten naturally by the next watcher run. This keeps a human
in the loop for understanding when drift was fixed. If there was no previous
findings file, omit the `resolved` block.

**On `sense` error (non-zero exit without valid JSON):** write
`pending.json` with a single `gate-failure` finding describing the error,
and emit a notification. A silently failing watcher gives false confidence
that nothing is drifting — analogy: a SIEM agent that stops heartbeating is
itself an alert, not silence.

**Watcher Heartbeat (blocking):** The watcher must emit a low-priority
notification stating "Watcher is alive, no findings" on clean runs. With the
daily cadence this is simply the daily run's clean-path notification — one
signal per day, findings or alive, so silence for a day+ means the watcher is
broken. No separate heartbeat schedule.

**Staleness/Retention (Human-in-the-Loop):** There is no automatic expiration
timer. If a user does not open an AI for a week, a finding from days ago is
still a real finding. `pending.json` persists until the next `sense` run (either
by the watcher or a live session) supersedes it. The AI session-start hook
reads it, but does not auto-delete it.

**pending.json integrity and limits:** `pending.json` is a local-only
machine-state file located in a "neutral zone" (not tied to any specific AI).
It is NOT a trust boundary and carries NO signature — advisory-only by design.
The binding controls are: the AI re-runs `sense` live at session start, and no
consequential decision may use `pending.json` as its sole input. A forged file
at worst produces a misleading notification that prompts the operator to open
a session, where live `sense` reports the truth. (An HMAC/DPAPI signature was
considered and rejected — see `docs/TRADEOFFS.md`, "pending.json integrity":
any local process able to tamper with the file could also read any locally
derivable key, and same-user access already implies far stronger attacks.)

**Registration (DECIDED):** a wrapper script `scripts/sense-watcher.ps1` (to
be created in the Tier 2 build slice) handles run + pending.json + balloon;
registered with:
`schtasks /Create /SC DAILY /ST 09:00 /TN agent-config-sync-sense /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Projects\agent-config-sync\scripts\sense-watcher.ps1"`
Uninstall: `schtasks /Delete /TN agent-config-sync-sense /F`.

**Constraints (blocking):**
- Watcher is read-only end to end: it runs `sense`, notifies, and writes its
  own state file. It never runs `project`, `promote`, `enroll`, or `--force`.
- No credentials, no network. Notification text is the same fixed phrasing as
  the brief output.
- Uninstall path documented next to install (`schtasks /Delete`).

**Test plan skeleton (`TODO`):** wrapper unit tests (findings → notification
call, no-findings → heartbeat cadence, sense error → notification with
gate-failure finding and pending-file updated), pending-file write/supersede
including the `resolved` block on clean runs, atomic write verification, and
a should-fail proving the watcher cannot reach any mutating CLI path.

---

## Tier 2 → Tier 3 gate

Tier 3 code must not be written until Tier 2 is deployed and stable. This is
a **sequencing gate**, not an architectural dependency — Tier 3 does not
consume `pending.json`; it runs `sense --json` directly.

**Gate criteria (all must hold before starting Tier 3):**
- Tier 2 watcher has been running for ≥2 weeks without error-state findings.
- At least one real drift event has been surfaced and resolved via the
  notification → operator → resolution-command workflow.
- Tier 2 test suite passes, including the should-fail mutating-path test.

---

## Tier 3 — Proposal-drafting ambient agent (LLM, gated)

**Goal:** when sense reports a runtime edit or an enrollment candidate, an AI
session drafts the resolution *proposal* (a promote diff preview, or a
neutralized `SKILL.md` body ready for `enroll --body-file`) so the operator
reviews a finished artifact instead of doing the neutralization by hand.

**Trigger (DECIDED 2026-07-04):** operator-invoked - the `draft-proposals`
managed skill, run inside a live AI session on the operator's request after a
sense/watcher notification. The unattended/scheduled trigger variant remains
GATED on the original criteria below (operator decision: gate scoped, not
removed - the operator-watched variant carries none of the unattended risk
the gate protects against).

**Autonomy boundary (blocking, mirrors the existing threat model):**
- The agent READS `sense --json` output and the referenced files; it WRITES
  only proposal artifacts to the proposals scratch location
  (`%LOCALAPPDATA%/agent-config-sync/proposals/`), never to
  the source repo or any runtime config.
- All applies stay behind the existing deterministic gates and the operator:
  `enroll --body-file`, `capture --confirm`, `promote --confirm`.
- Every agent run is visible: operator-invoked means the full transcript IS
  the log (the session record); artifacts carry drafting notes naming every
  change made. If the unattended variant ever ships, it needs its own
  append-only run log.

**Prompt-injection surface (blocking):**
- The agent reads runtime-edited files, which are untrusted input by
  definition. Three layers of defense:
  1. **Output gate (existing):** the proposal artifact must pass the same
     neutral-language and secret gates on the way in (`enroll` already
     enforces this) — the agent's output is a *candidate*, never a decision.
  2. **Write-boundary enforcement (new, required):** the agent must operate
     under a deterministic write sandbox — a path-constrained write wrapper
     or filesystem-level restriction that enforces the scratch-only boundary
     at the OS/tool level, not just via prompt instructions. A sufficiently
     crafted runtime edit could redirect the agent's behavior (e.g., "write
     to `_shared/core.md` instead of scratch") without the output ever
     failing the enroll gate. The prompt is one layer; the binding control
     is the deterministic constraint.
  3. **Instruction integrity:** the agent's system prompt must be a reviewed,
     version-controlled artifact stored in the source repo (e.g.,
     `skills/<name>/SKILL.md`), not ad-hoc text. This makes instruction
     integrity auditable and keeps the system prompt under the same review
     gate as all other managed content.

**Mechanism (DECIDED): operator-invoked skill** - narrowest threat surface of
the three candidates (operator watches every action; no standing cost; no
headless credentials). The instruction-integrity requirement is satisfied
structurally: the agent's system prompt IS `skills/draft-proposals/SKILL.md`,
version-controlled, gate-screened, and projected like all managed content.
The write sandbox for this variant is the operator's supervision plus the
gates on re-entry; a deterministic path-constrained sandbox becomes mandatory
only for the unattended variant. Original candidates for reference: a scheduled
headless AI session, a cron-style routine in the AI tool, or a manual
"draft proposals" skill the operator invokes after a notification. Note:
the choice affects the threat surface. A headless session with full tool
access has a wider autonomy boundary than a sandboxed script or
operator-invoked skill. Document the chosen mechanism's threat implications
in the Tier 3 threat-model entry.

**Test/verification skeleton (`TODO`):**
1. **Eval Dataset:** Before building Tier 3, create a benchmark dataset of
   runtime edits (benign, adversarial, edge-case) and expected proposal outputs.
   The agent must pass these baselines to prove it works safely.
2. Proposal artifact passes enroll gates verbatim.
3. Agent cannot write outside the scratch location (should-fail, enforced by the
   write sandbox, not just the prompt).
4. Injection attempt planted in a runtime-edited file does not alter the
   proposal workflow's instructions.
5. Agent system prompt matches the version-controlled source.

---

## Out of scope (both tiers)

- Auto-applying any change without an operator command.
- Watching arbitrary directories beyond the allowlisted runtime roots and the
  source repo.
- Implementing any of this now.

