# Evaluation — agent-config-sync

Running log of how this project is verified: the automated suite plus every
manual/live run. Append new entries; do not rewrite history. Validation command
(plain `pytest` is broken in this env — a global `web3` plugin poisons collection):

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
```

---

## Automated test suite

| Date | Result | Notes |
|------|--------|-------|
| 2026-06-27 | 57 passed | Plan 1 (instruction-file forward projection) complete |
| 2026-06-28 | 79 passed | Plan 2 Slice A (skills projection + enrollment) added (+22) |
| 2026-06-28 | 86 passed | Critique fixes F1/F2/F3 added (+7) |
| 2026-06-28 | 90 passed | Slice B part 1: discovery section + config-sync skill (+4) |
| 2026-06-28 | 96 passed | Slice B3: settings.json hook writer + install-hooks command (+6) |
| 2026-06-28 | 99 passed | doctor command (+3) |
| 2026-06-28 | 108 passed | Slice C: capture-from-chat engine + CLI (+9) |
| 2026-06-28 | 116 passed | Plan 3: reverse promote + CLI (+8) — **feature-complete** |
| 2026-06-30 | 148 passed | ACS-001 through ACS-010 remediation: path containment, capture fan-out, promote exact changes, hook dry-run/failure exits, lint expansion, docs/release readiness |
| 2026-06-30 | 161 passed | Operational hardening: collision-safe backups, explicit prune-backups, repo-scoped locks, hook bad-shape validation, hermetic Gemini CLI E2E, docs/lessons/tradeoffs updates |
| 2026-07-03 | 165 passed | Working tree on `main` validated after handoff, documentation, and lesson reconciliation plus supply-chain pinning; sandboxed temp/atomic-replace failures were excluded as environment restrictions |
| 2026-07-03 | 176 passed | Skill enrollment sweep (23 managed skills) + companion-file projection with fail-closed gates (+11); independently reproduced by a Codex live audit (`176 passed in 14.55s`) outside the sandbox |
| 2026-07-03 | 181 passed | Codex audit cycle-2 fixes: body neutral-lint at projection, wrapped slash-command detection for managed skill names (+5); this file's double-mangled UTF-8 repaired (history rows preserved, encoding only) |
| 2026-07-04 | 195 passed | Branch `v2-sense-automation`: Tier 1 sensing (+14 — sense scan/brief/json, ignore list, gate-failure findings, hook-command replacement); live `sense` verified: 12 real unmanaged skills surfaced across codex/gemini, notebooklm correctly suppressed |
| 2026-07-04 | 197 passed | V2 merged to main; sense hooks live in all three runtimes (Gemini via manual fallback, backed up); all 12 unmanaged skills enrolled (4 verbatim, 8 neutralized; managed set now 35); lint extended with Gemini tool names (+1 test); project/check gate failures now clean messages, not tracebacks (+1 test, found live when a new managed name retroactively flagged an enrolled body) |
| 2026-07-04 | 205 passed | Tier 2 ambient watcher shipped (+8 - heartbeat exit codes, resolved-block retention, corrupt-pending tolerance, no-mutation and scan-explosion should-fails, CLI cycle); scheduled task registered and live cycle verified clean |
| 2026-07-04 | 208 passed | S9 overlap detector (+3 - near-copy flagged, unique clean, CLI inputs/exits; live: compact-handoff 1.00/1.00 vs itself); S3 live-verification drills documented (see section below); Lesson13 + lesson staleness sweep |
| 2026-07-04 | 212 passed | S7 eval dataset (+4 integrity tests: known-bads trip real gates, benign scans clean); S8 draft-proposals skill enrolled (36 managed); Tier 3 eval executed live by a drafting agent: 12/12 property checks PASS across 5 cases (injection quoted-not-obeyed, credential redacted-not-propagated, noise correctly recommended for discard) |
| 2026-07-05 | 217 passed | Read-only MCP status server (+5 - handshake, findings tool, notification silence, clean errors, no-mutating-surface should-fail); live stdio handshake verified; Lesson14 |

**Coverage by file (Slice A + fixes):**

- `test_render.py` / `test_secrets.py` / `test_fsutil.py` / `test_state.py` / `test_config.py` — Plan 1 units
- `test_project.py` — forward projection incl. should-fail: drift refusal, secret abort, force-scope guard
- `test_check.py` / `test_status.py` — drift reporting (instructions + skills)
- `test_neutralize.py` — vendor-term lint + reconciliation; should-fail: non-neutral body, divergent variants; false-positive guard (ordinary prose with "tool" not flagged)
- `test_skills.py` — skill projection goal test (body + adapter per runtime); should-fail: drift refusal; idempotency
- `test_enroll.py` — enrollment; should-fail: non-neutral, secret, divergent variants, **managed_skills truncation guard**
- `test_cli.py` — command dispatch + exit codes incl. should-fail: drift→2, **config error→3 (no traceback)**, stale→1, force-scope→4
- `test_runtime_docs.py` - Gemini overlay/adapter/audit consistency for `activate_skill`

Every consequential path has at least one case that *should* fail (per the project's test standard).

---

## ACS remediation verification (2026-06-30)

Command run locally:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP\acs-pytest"
```

Result: `148 passed in 14.06s`.

Issue coverage added or updated:

| Issue | Verification coverage |
|---|---|
| ACS-001 | Invalid skill names rejected in config/enroll/capture; final source/runtime containment enforced; YAML names quoted |
| ACS-002 | One confirmed `capture skill` projects the new skill to Claude, Codex, and Gemini in the same command |
| ACS-003 | Promote tests cover append, delete, replace, source-behind, true conflict, ambiguous mapping, and missing baseline |
| ACS-004 | Runtime-doc test fails if Gemini adapter requires `activate_skill` while overlay/audit denies it |
| ACS-005 | Hook tests cover dry-run no-write behavior, Gemini nonzero/exception, and Codex parse failure returning nonzero |
| ACS-006 | State atomic write, source backup, and source audit tests added |
| ACS-007 | CLI stdout UTF-8/backslashreplace configuration tested |
| ACS-008 | Secret and neutral-language corpora expanded with positive and false-positive cases |
| ACS-009 | README, architecture, limitations, security, audit brief, and evaluation reconciled to current behavior |
| ACS-010 | Private-repo no-license decision recorded; installation/usage/troubleshooting docs and pinned-checkout CI workflow added |

## Live / manual CLI runs

Run via the installed console script against throwaway sandboxes (fake runtime
dirs under the scratchpad); never against the owner's real `~/.claude` etc.

### 2026-06-28 — Slice A end-to-end (first real run, post-merge)
Setup gotcha recorded: the CLI must receive **native Windows paths** (`C:/…`) and
the allowlist env var must use the Windows path separator `;`. An initial attempt
with MSYS paths (`/c/…`) and `:` failed at the allowlist check — a **test-harness**
error, not a product bug; the pytest suite never exercised the env-var split
because it passes `allowed_roots` as a list. (Logged as the path-format finding.)

| Step | Command | Result |
|------|---------|--------|
| status (fresh) | `status` | `missing` ×3 ✓ |
| project instructions | `project` | `create` ×3 ✓ |
| enroll neutral skill | `enroll hello --body-file …` | exit 0 ✓ |
| project skill | `project` | SKILL.md + correct adapter written to all 3 runtimes ✓ |
| check | `check` | "All runtimes in sync", exit 0 ✓ |
| status | `status` | per-skill `in-sync` ×3 ✓ |

Safety paths:

| Case | Expected | Result |
|------|----------|--------|
| enroll non-neutral body (`Skill tool`, `/critique`) | exit 3 | ✓ aborted, terms named |
| enroll body with secret | exit 3 | ✓ "Nothing enrolled" |
| hand-edit projected skill → `project` | exit 2 | ✓ drift refusal |
| `check` after drift | exit 1 | ✓ STALE listed |
| `project <rt> --force` | exit 0 | ✓ `forced`, backup written |
| backup + audit log | present | ✓ `.backups/…/SKILL.md`, audit entry `force:true` + hash |

### 2026-06-28 — Slice B3 (install-hooks)

| Case | Expected | Result |
|------|----------|--------|
| `install-hooks --help` (real binary wiring) | command present | ✓ |
| unit: append without clobbering existing/Stop hooks | preserved | ✓ |
| unit: idempotent (second run adds nothing) | count == 1 | ✓ |
| unit: missing `hooks` key created | created | ✓ |
| unit: backup written before write | `.backups/settings/<stamp>/` | ✓ |
| unit: malformed JSON aborts without write | `HookInstallError`, file unchanged | ✓ |
| full `install-hooks` live-apply | all three runtimes wired | ✅ **RUN 2026-06-29** — Claude + Gemini + **Codex** SessionStart now run `agent-config-sync check`; backups written |

**Codex hook added 2026-06-29 (+6 tests → 123):** earlier "Codex has no hook" was
WRONG — `codex_hooks` is a stable, default-on feature, config-driven via
`[[hooks.SessionStart]]` in `config.toml` (schema verified at
developers.openai.com/codex/hooks). `install_codex_hook` (tomllib parse + validate,
append-only, idempotent, backup) wired live; `notify`/`[plugins.*]`/`model` preserved,
result is valid TOML.

**Bugs found by the live run (fixed, +1 test → 117):**
- Windows: `subprocess.run(["gemini", …])` failed (`gemini` is a `.cmd` shim) → now resolves the full path and uses `cmd /c` list arguments on win32; nonzero or launch failure now returns exit 3.
- `gemini hooks migrate` run from the repo read the project-local `.claude/settings.local.json` (no hooks) → now run with `cwd=$HOME` so it discovers the global `~/.claude/settings.json`.

### 2026-06-28 — Critique fix verification (F1/F2/F3)

| Fix | Case | Expected | Result |
|-----|------|----------|--------|
| F1 | bad allowlist via CLI | "Config error" + exit 3, **no traceback** | ✓ |
| F2 | enroll body w/ `Bash tool` + `mcp__…` | exit 3 (previously passed) | ✓ caught both |
| F2 | ordinary prose ("the right tool") | not flagged | ✓ (unit) |
| F3 | `managed_skills` not last key | refuse, no data loss | ✓ (unit) |
| regression | happy path enroll/project/check | 0/0/0, 3 SKILL.md | ✓ |

---

## Current limitations

See `docs/LIMITATIONS.md` for current accepted limitations. The old gaps around
startup discovery, capture-from-chat, and reverse promote are closed; remaining
limits are mainly exact promote attribution, pattern-based linting, local-only
durability until a private remote exists, hook dependency on runtime behavior,
and selecting a license only if publication or third-party reuse becomes a goal.

## Operational hardening verification (2026-06-30)

Command run locally with filesystem permissions enabled for atomic replace,
confirmed pruning, lock, and hook-writer tests:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest -q -p no:cacheprovider --basetemp .pytest_cache\acs-pytest-full
```

Result: `161 passed in 8.77s`.

Coverage added:

| Area | Verification coverage |
|---|---|
| Backup collision safety | Same-stamp backups create distinct snapshot paths and never overwrite existing backups |
| Backup pruning | Dry-run deletes nothing; confirmed pruning enforces newest-10/30-day policy and records audit events |
| Pruning containment | Symlink-style backup escape is ignored rather than deleted |
| Repo-scoped lock | Lock metadata, release, contention failure, and no-write-on-lock-failure are tested |
| Hook validation | Malformed-but-parseable Claude/Codex hook shapes raise `HookInstallError` without writes |
| Hermetic CLI E2E | Mock `gemini hooks migrate --from-claude` proves subprocess wiring without touching real runtimes |
| Documentation | README, usage, troubleshooting, architecture, limitations, tradeoffs, lesson 11, checklist, and threat model updated |


## 2026-07-04 - S3 live verification: the sense loop in all three runtimes

**What was tested:** the full Tier 1 loop in each runtime - session opens ->
sense reports -> AI names the change -> AI asks the operator -> operator
decides -> exact named command resolves it.

**Method (controlled drift drills):** baseline confirmed clean in each
runtime, then a known harmless edit was planted and the runtime's own AI was
asked to run `sense` and report, with standing instructions not to act
without approval. The planted edit is the "known-bad sample": we know exactly
what the tool should find, so the output is checkable against ground truth.

| Runtime | Result |
|---|---|
| Claude Code | Verified throughout the build session: sense at session start, drift naming, ask-before-act (including one case where the harness safety layer blocked a discard command issued without recorded operator approval - the confirm gate held even against the assistant itself) |
| Codex | Baseline clean. Codex's own sandbox refused to edit the adapter (its own control, not ours). Operator-side edit to the shared adapter source: sense correctly reported ALL 35 per-skill copies behind source and named `project` as the fix - larger blast radius than intended but detection was exact. Codex asked before acting; nothing ran unapproved |
| Gemini/AntiGravity | Baseline clean. Runtime-side edit planted in `critique/references/gemini-tools.md` (the correct "local machine change" scenario): sense named the exact file, gave both resolutions (keep via review-and-copy / discard via scoped force), and AntiGravity stopped and asked "keep or discard?" - the ask-before-act instruction working verbatim. Operator chose discard; scoped force resolved it; sense returned to exit 0 |

**Why this is proof:** each drill had a known ground truth (we planted the
change), a falsifiable prediction (sense must name that file and direction),
and an observed match. The ask-before-act behavior was demonstrated by the
AIs' actual conduct, not by reading the instruction file. One drill also
exercised the negative path: an unapproved resolution attempt was refused.
Known limitation observed: the automatic session-start hook fired in Codex
(operator accepted the hook prompt) but its one-line output was not visually
distinct among Codex's startup messages - detection works; presentation of
the auto-run line in Codex could be more prominent.
