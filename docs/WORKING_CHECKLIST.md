# Working Checklist — remaining work (living document)

> Single live tracker for remaining slices. Update the checkbox and the Status
> line as each slice progresses; HANDOFF.md points here. Validation baseline:
> `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` (195 passing) and
> `agent-config-sync check` (exit 0). Last updated: 2026-07-04 (V2 COMPLETE:
> all buildable slices done; only the time-gated S7/S8 remain, by design).

## Build order (sequential backbone)

S1 -> S2 -> S3 -> S6, with S4 and S5 runnable in parallel after S1.
S7/S8 are time-gated behind Tier 2 operation. D1-D4 are deferred/blocked.

---

## S1 — Merge V2 branch to main
- [x] Status: DONE 2026-07-04 (fast-forward to 29b8b5b; 195 tests, check green)
- **Goal:** land Tier 1 sensing on `main`; branch `v2-sense-automation` (tip `41edbe1`) merges clean.
- **Touchpoints:** git only (no new edits).
- **Acceptance:** `main` contains the sense feature; CI green; `agent-config-sync check` exit 0 from main.
- **Depends on:** operator approval (OPERATOR GATE — review the branch diff first).

## S2 — Activate the sense hook in live runtimes
- [x] Status: DONE 2026-07-04. Claude + Codex swapped by install-hooks (old check entry replaced, unrelated hooks preserved). Gemini: migrate was a no-op on the existing entry; manual fallback applied (backed up to .backups/gemini/), sense verified in ~/.gemini/settings.json
- **Goal:** session-start hooks run `sense` instead of `check` in all three AIs.
- **Touchpoints:** runtime files only — `~/.claude/settings.json`, `~/.codex/config.toml` (merge-safe writers), Gemini via `gemini hooks migrate --from-claude`. No repo edits.
- **Steps:** `agent-config-sync install-hooks --dry-run` -> review -> `install-hooks` -> read both files to confirm `sense` present, old `check` entry gone, backups exist under `.backups/`.
- **Acceptance:** both configs carry `agent-config-sync sense`; old entry removed; Gemini migration succeeded or manual fallback recorded.
- **Depends on:** S1.

## S3 — Live verification in all three AIs
- [x] Status: DONE 2026-07-04. Controlled drift drills in all three runtimes; full method, results, and proof rationale recorded in docs/EVALUATION.md (S3 section). Ask-before-act confirmed by conduct in Codex and AntiGravity; Claude verified throughout the build session
- **Goal:** prove the full loop: session opens -> sense line appears -> AI asks -> operator approves -> command runs.
- **Steps:** open a session in Claude, Codex, Gemini/AntiGravity; confirm sense output at start; make one harmless runtime edit; confirm the AI names it and asks before acting; resolve; append the result to `docs/EVALUATION.md`.
- **Acceptance:** EVALUATION entry recording per-runtime results.
- **Depends on:** S2. (OPERATOR — requires opening Codex/Gemini sessions.)

## S4 — Disposition of the 12 unmanaged skills
- [x] Status: DONE 2026-07-04. All 12 ENROLLED (none redundant with the managed set; compact-handoff aligned to one canonical managed body). 4 verbatim, 8 neutralized (Gemini tool names, WebFetch mentions, quoted /tmp and /api paths, wrapped cross-references). Lint gap closed along the way: Gemini tool names (grep_search, list_dir, run_shell_command, google_web_search) added to the vendor-term list; project/check now report gate failures cleanly instead of tracebacks. Managed set: 35 skills; sense exit 0
- **Goal:** `sense` reports zero unmanaged-skill findings.
- **Inventory:** codex: `compact-handoff`, `playwright`; gemini: `build-ambient-agent`, `google-agents-cli-adk-code`, `-deploy`, `-eval`, `-observability`, `-publish`, `-scaffold`, `-workflow`, `json-to-pydantic`, `setup-adk`.
- **Touchpoints:** `config/targets.yaml` (`sense_ignore_skills`), `skills/` (per enrollment), docs.
- **Steps:** operator decides each: enroll (`agent-config-sync enroll <name> --from <runtime>`, one at a time, gates apply) or add to `sense_ignore_skills`.
- **Acceptance:** `agent-config-sync sense` exit 0 on unmanaged findings (other finding kinds aside).
- **Depends on:** S1 (avoid branch divergence). (OPERATOR decisions per skill.)

## S5 — Tier 2 design decisions (fill the spec TODOs)
- [x] Status: DONE 2026-07-04. Decided: DAILY cadence (irregular usage + session-start hook covers sit-down moments; the daily clean-run notification IS the heartbeat), zero-dependency PowerShell balloon notifier, single schtasks DAILY 09:00 registration with scripts/sense-watcher.ps1 wrapper (built in S6)
- **Goal:** no open `TODO:` in the Tier 2 section of the ambient-automation spec.
- **Decisions needed:** watcher interval N; notification mechanism (zero-dependency option first); wrapper script shape + exact `schtasks` registration line.
- **Touchpoints:** `docs/superpowers/specs/2026-07-04-ambient-automation-spec.md` only.
- **Acceptance:** Tier 2 section TODO-free; decisions recorded with rationale.
- **Depends on:** S1. (OPERATOR input on the three decisions.)

## S6 — Tier 2 build: ambient watcher
- [x] Status: DONE 2026-07-04. `watcher.py` + `watch-once` CLI (logic in Python, fully tested: 8 tests incl. should-fail no-mutation and scan-explosion paths) + `scripts/sense-watcher.ps1` balloon wrapper. Scheduled task `agent-config-sync-sense` registered DAILY 09:00 and verified Ready; live cycle ran clean and seeded pending.json. Tier 2->3 gate clock starts now (>=2 weeks stable + 1 real drift resolved)
- **Goal:** scheduled watcher runs `sense --json` between sessions, notifies on findings, maintains `pending.json` (advisory-only, HITL retention with `resolved` block), emits the daily heartbeat.
- **Touchpoints:** new wrapper script (likely `scripts/`), new tests, docs (README/USAGE/HANDOFF/EVALUATION), threat-model delta.
- **Acceptance:** spec test plan green incl. the should-fail proving no mutating CLI path is reachable; task registered and heartbeat observed live; uninstall documented.
- **Depends on:** S5, S2.

## S9 — Skill-overlap detector (NEW, from operator request 2026-07-04)
- [x] Status: DONE 2026-07-04. `overlap.py` + `overlap` CLI (body/description similarity, REVIEW flags, exit 1 on flag); 3 tests covering both should-fail directions; live proof: compact-handoff scored 1.00/1.00 against itself, near-zero against everything else
- **Goal:** deterministic, read-only similarity report between a candidate skill body and the managed set (name/description/body signals with scores), feeding the existing propose -> operator-confirm -> gated-enroll flow. Detection is code; "redundant" stays a human judgment; merges are AI-drafted proposals through the enroll gates.
- **Touchpoints:** likely `overlap.py` + CLI surface (or an enroll-propose warning), tests, docs.
- **Acceptance:** running it against a copy of an existing managed skill flags high overlap; against a unique skill reports none; should-fail test for both directions.
- **Depends on:** nothing (S4's one-off analysis validated the approach).

## S7 — Tier 3 eval dataset
- [x] Status: DONE 2026-07-04. evals/tier3/ - 5 cases (benign, injection, vendor-terms, secret, noise) with property-based expected files; integrity tests prove the adversarial inputs trip the real gates
- **Gate:** Tier 2 running >=2 weeks without error-state findings AND >=1 real drift resolved through the notification workflow.
- **Goal:** benchmark set of runtime edits (benign / adversarial / edge) with expected proposal outputs, per spec.
- **Depends on:** S6 + gate criteria.

## S8 — Tier 3 build: proposal-drafting agent
- [x] Status: DONE 2026-07-04 (operator-invoked variant). `draft-proposals` managed skill enrolled and projected to all runtimes (instruction integrity = version-controlled managed content); eval executed live: 12/12 checks PASS incl. injection-not-obeyed and secret-not-propagated. OPERATOR DECISION RECORDED: the 2-week gate was scoped, not removed - it still applies to any UNATTENDED trigger variant; the operator-invoked variant runs inside a watched session at no standing cost
- **Goal:** agent drafts proposals only (write sandbox enforced deterministically; system prompt version-controlled as a managed skill); all applies stay behind operator `--confirm`.
- **Depends on:** S7.

---

## Deferred / blocked (not plannable as ready)

- **D1 — Fourth runtime support.** BLOCKED: gate = operator adopts a fourth AI tool. Spec: `2026-07-04-fourth-runtime-support-spec.md`.
- **D2 — notebooklm clean packaging.** BLOCKED: needs executable-companion boundary decision (text-only allowlist excludes its scripts by design).
- **D3 — LICENSE selection.** BLOCKED: owner decision; only required before any public release.
- **D4 — promote support for companion files.** Optional; schedule when a runtime-side companion edit actually occurs (drift guard surfaces it; resolution is manual today).

## Parallel-safe set (requires approval before dispatch)

**{S4, S5} after S1:** dependency-free of each other, file-disjoint
(S4: `config/targets.yaml` + `skills/`; S5: the spec file only), both
independently verifiable. Both are operator-decision-heavy, so parallel value
is modest — sequential is equally fine.
Everything else is sequential (operator gates or shared doc touchpoints).

## Recommended first move

**S1** — review and merge the branch. Every other slice hangs off it, and it is
pure review: no new code, 195 tests green, all runtimes in sync.
