# 🎓 Lesson 13: The Night Patrol — Building an Ambient Agent Safely

## 🛡️ Welcome Back, Security Analyst!

What tells you a sensor is healthy: the alerts it sends, or the heartbeat it
sends when there is nothing to alert on? 🔍 Today we explore the **Tier 2
ambient watcher** (`src/agent_config_sync/watcher.py`, `sense.py`, and
`scripts/sense-watcher.ps1`) — the "night patrol" that checks your AI
configuration while no AI session is open, reports what it finds, and — this is
the whole lesson — **can do nothing else by construction**.

"Ambient agent" is a loaded phrase in 2026: usually it means an LLM running
unattended. This project's Tier 2 deliberately builds the *ambient* part with
**zero LLM involvement** — a deterministic patrol — and gates the LLM version
(Tier 3) behind a two-week proving period. That ordering is the design lesson.

---

## 🎯 Learning Objectives

By the end of this lesson you will be able to:

- Explain the three-tier ambient design (session hook → deterministic watcher → gated LLM agent) and why the tiers are ordered that way
- Trace one watcher cycle: scan → pending file → notification → exit code
- Defend the "heartbeat" pattern: why silence must be distinguishable from health
- Justify advisory-only state: why `pending.json` carries no signature and why that is stronger than a bad signature
- Prove read-only-by-construction with the project's own should-fail tests

**Time estimate:** 35 minutes | **Prerequisites:** Lesson 12 (operator loop); Lesson 05 (drift guard) helps

---

## 🧠 What This Component Does — Plain English

The session-start hook (Lesson 12) only fires when you open an AI. If you are
away for three days and something drifts on day one, nobody knows until day
three. The watcher closes that gap: a Windows scheduled task runs one
read-only cycle daily — it runs the same `sense` scan the session hook uses,
writes the findings to a small status file (`pending.json`) in machine-local
state, and pops a desktop balloon. Findings or not, it always says something:
"findings, open a session" or "alive, nothing to report."

The critical property is what it *cannot* do. The watcher never projects,
never promotes, never enrolls, never forces. Its only write in the entire
cycle is its own status file. When you eventually open an AI session, the
session hook re-runs `sense` live — the status file is a heads-up, never the
authority.

**Real-world analogy:** a night security guard who walks the building, writes
observations in a logbook, and phones you if a door is open — but carries no
keys. The guard cannot lock or unlock anything. Whatever the logbook says, the
day shift re-checks the doors themselves before acting.

---

## 🔵🟡🔴 Career Lens — Three Perspectives on This Component

### 🔵 Analyst Lens — What a SOC Analyst Sees Here

This is **agent health monitoring plus scheduled detection sweeps** — the
discipline you already run with SIEM collectors and EDR agents. The daily
balloon is a Wazuh agent heartbeat: `keepalive` received → agent healthy;
silence → the agent itself is the incident, not the absence of threats. The
`pending.json` file is the alert queue that survives you being away from the
console: findings persist until a fresh scan supersedes them, exactly like an
unacknowledged alert staying in the SOAR queue over a weekend. And the drill
that proved it (see `docs/EVALUATION.md`, S3 section) is detection-content
testing 101: plant a known-bad sample, verify the rule names it precisely.

**SOC parallel:** a FortiSIEM collector's keepalive plus a nightly scheduled
correlation sweep — one signal per day, alert or heartbeat, and a silent
collector is itself an alarm condition.

### 🟡 Engineer Lens — What a Cybersecurity Engineer Builds Here

The design splits brains from hands. All logic lives in a **testable Python
core** (`watcher.watch_once` — pure enough to unit test with an injected clock
and pending path); the scheduled task runs a **dumb messenger** PowerShell
wrapper whose only jobs are "call the CLI, show a balloon." That split exists
because PowerShell in a scheduled task is nearly untestable, while a Python
function with injectable parameters gets eight pytest cases including the
security-critical ones. Review question you should be able to answer: why does
`watch_once` take `now` and `pending_path` as parameters instead of reading
the clock and a global path? (Determinism — the same reason `render()` takes
no wall-clock input, Lesson 00.)

**Engineering decision to own:** logic-in-CLI, shell-as-messenger. If the
notification mechanism ever changes (balloon → toast → email), zero tested
code changes — only the 30-line wrapper.

### 🔴 AI Security Engineer Lens — What an AI/ML Security Engineer Watches For

Tier 2 is the **pre-LLM scaffolding for agentic automation**, and its
boundaries are the ones you will fight for in every agent review. Three
surfaces: (1) `pending.json` is written into a world-writable-by-same-user
location and later *read into an AI's context* — an indirect prompt-injection
channel; the control is architectural, not cryptographic: the file is
advisory-only and the AI always re-runs `sense` live, so forged content buys
an attacker one wasted glance. (2) The scheduled task executes a script daily
with user privileges — the script is version-controlled and reviewed, and the
task command is a fixed literal. (3) The Tier 2→3 gate: no LLM is added until
the deterministic patrol has run two clean weeks and handled one real event.
Prove the rails before you put a probabilistic driver on them.

**AI security surface:** unattended-agent state files consumed by LLMs. The
binding control here is "never the sole input to a consequential decision" —
enforced by design (live re-run at session start), not by trusting the file.

---

## 🗺️ Where This Fits in the System

```
                     you are away  ──────────────  you sit down
                          │                             │
   Task Scheduler (daily) │                             │ AI session opens
                          ▼                             ▼
   scripts/sense-watcher.ps1 ──▶ agent-config-sync   SessionStart hook ──▶ sense (live)
        (messenger)              watch-once                                   │
                                    │                                         ▼
                          sense.scan() read-only                    AI names findings,
                                    │                               asks you, runs the
                     pending.json + balloon 🔔                      approved command
                     (advisory heads-up only)
```

If the watcher dies, nothing breaks — the session hook still covers every
sit-down. What you lose is between-session awareness, and the heartbeat design
makes that loss *visible*: a day with no balloon means the patrol itself needs
attention.

---

## 🔑 Key Concepts

### Heartbeat (dead-man's signal)
A periodic "I'm alive, nothing to report" message. Without it, silence is
ambiguous: healthy-and-quiet looks identical to crashed. This watcher folds
the heartbeat into the daily cadence — one run per day means the clean-run
balloon *is* the heartbeat; no second schedule exists.

### Advisory-only state
Data that may inform but never authorize. `pending.json` carries no signature
by explicit decision (see TRADEOFFS, "pending.json integrity"): any local
process that could forge it could also read any locally derivable signing key,
so a signature would be theater. The honest control is that nothing
consequential ever rides on the file alone.

### Read-only-by-construction
The watcher's inability to mutate is not a policy sentence — it is the absence
of any code path to a mutating function, proven by a should-fail test that
plants real drift and asserts the runtime and source files are byte-identical
after the cycle.

---

## 📝 Code Walkthrough

### One cycle, no exceptions escape

```python
# src/agent_config_sync/watcher.py — watch_once (core)
    try:
        findings = scan(config)
    except Exception as exc:  # noqa: BLE001 — watcher must never die silently
        findings = [
            Finding("gate-failure", "source", "watcher",
                    f"sense failed: {exc}", "")
        ]
```

| Lines | What it does | Why it was designed this way |
|-------|-------------|------------------------------|
| `scan(config)` | Reuses the exact session-hook scan — one detection engine, two triggers | No second implementation to drift from the first (the SIEM sin of two copies of one rule) |
| broad `except` | Converts ANY failure into a reportable finding | A watcher that dies silently produces false confidence — the failure mode this whole tier exists to eliminate |

### The resolved block — memory across the findings→clean transition

```python
# src/agent_config_sync/watcher.py — watch_once (persistence)
    if not findings and isinstance(previous, dict) and previous.get("count", 0):
        payload["resolved"] = {
            "findings": previous.get("findings", []),
            "generated_at": previous.get("generated_at", ""),
        }
```

When a clean run supersedes a findings run, the superseded findings are
preserved under `resolved` — so the next session can tell you "the thing from
Tuesday is fixed," by name. Without this, the overwrite would destroy the very
information the message needs (a spec contradiction caught in critique before
implementation — see the ambient-automation spec history).

> ⚠️ **Common pitfall:** treating `pending.json` as the source of truth. It is
> a sticky note. The session hook re-runs `sense` live precisely so a stale or
> forged note can never drive an action.

### The messenger that cannot act

```powershell
# scripts/sense-watcher.ps1 (excerpt)
$out = & agent-config-sync watch-once 2>&1
$code = $LASTEXITCODE
...
$icon.BalloonTipTitle = $title
$icon.BalloonTipText = $body
$icon.ShowBalloonTip(10000)
```

The wrapper calls exactly one CLI command and shows exactly one balloon. It
parses nothing into decisions, takes no flags, and contains no mutating
command. **Design pattern used:** dumb pipe / smart core — the same reason a
SOAR notification action doesn't embed remediation logic.

---

## 🧪 Hands-On Exercises

> All three exercises touch only `pending.json` (machine-local state). None
> can modify your repo or runtimes.

### 🔬 Exercise 1: Run the patrol on demand

Proves the daily cycle works right now — no waiting for the schedule.

```powershell
# PowerShell
agent-config-sync watch-once
Get-Content "$env:LOCALAPPDATA\agent-config-sync\pending.json"
```

```bash
# Bash
agent-config-sync watch-once
cat "$LOCALAPPDATA/agent-config-sync/pending.json"
```

📊 **Expected output:**
```
agent-config-sync: watcher alive
No findings. All runtimes in sync.
{
  "count": 0,
  "findings": [],
  "generated_at": "2026-07-05T03:20:31Z"
}
```

✅ **You succeeded if:** exit code 0, two-line notification text, and a fresh
`generated_at` timestamp in the file (a balloon may also appear).

### 🔬 Exercise 2: Watch the resolved block appear

Proves the findings→clean transition preserves what was fixed.

```powershell
Set-Content "$env:LOCALAPPDATA\agent-config-sync\pending.json" '{"count": 1, "findings": [{"kind": "unmanaged-skill", "runtime": "codex", "target": "demo-drill", "keep": "", "discard": ""}], "generated_at": "2026-07-04T00:00:00Z"}'
agent-config-sync watch-once
Get-Content "$env:LOCALAPPDATA\agent-config-sync\pending.json"
```

📊 **Expected output:** `count` is 0, and a `resolved` block carries the
`demo-drill` finding with the old `2026-07-04T00:00:00Z` timestamp.

✅ **You succeeded if:** the superseded finding survives inside `resolved` —
the "previous findings from [date] appear resolved" message has its data.

### 🔬 Exercise 3: Intentional Failure — corrupt the logbook

Proves garbage state cannot crash the patrol.

```powershell
Set-Content "$env:LOCALAPPDATA\agent-config-sync\pending.json" '{broken json'
agent-config-sync watch-once
```

📊 **Expected output:**
```
agent-config-sync: watcher alive
No findings. All runtimes in sync.
```

✅ **You succeeded if:** exit 0, no traceback, and the file is valid JSON
again afterward — corruption tolerated and healed, not fatal.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering Interview

**Q:** Your monitoring job runs on a schedule and writes a status file. Walk
me through your failure-mode design: what happens when the check itself
throws, when the status file is corrupt, and when the job silently stops?

**A:** Three distinct answers, all fail-visible. A throwing check is caught
and converted into a reportable finding — the run still completes and
notifies, because a monitor that dies silently manufactures false confidence.
A corrupt status file is treated as absent and rewritten atomically
(temp+replace) — prior corruption cannot poison future runs. And a silently
stopped job is caught by the heartbeat: the design emits exactly one signal
per day, findings or "alive," so a missing signal is itself the alert. The
common thread is that every failure path degrades into a *visible* state,
never a quiet one.

*Why this answer works:* it shows failure-mode thinking as a design input
rather than an afterthought, with a concrete mechanism per mode.

### 🔴 AI Security Engineering Interview

**Q:** You want an unattended agent to act on configuration drift. How do you
introduce LLM autonomy into that pipeline without creating an unattended
write-path?

**A:** Stage the autonomy. First ship the ambient part deterministically — a
scheduled read-only scan with heartbeat and persisted findings — and gate the
LLM tier behind operational proof (here: two clean weeks plus one real event
resolved through the human workflow). When the LLM tier lands, it inherits
hard boundaries: it reads findings and drafts proposals into a scratch
location enforced by a deterministic write sandbox — not by prompt
instructions, because the files it reads are untrusted and could redirect it.
Its output re-enters through the same content gates as human input, and every
apply stays behind an explicit operator confirm. The LLM never holds write
authority at any stage; autonomy grows in the proposal quality, not in the
permission set.

*Why this answer works:* it demonstrates staged-autonomy design and treats
prompt injection as a given to be engineered around, not an edge case.

---

## ✅ Key Takeaways

- Ambient ≠ LLM: the watcher delivers unattended awareness with zero
  probabilistic components — and that ordering (rails before driver) is the
  design
- One detection engine (`sense.scan`), two triggers (session hook, daily
  patrol) — never two implementations
- One signal per day, findings or heartbeat: silence is always meaningful
- `pending.json` is advisory-only; the honest control is the live re-run, not
  a forgeable signature
- Read-only-by-construction is proven by a should-fail test, not asserted by
  a comment

---

## 📋 Quick Reference Card

| Item | Value |
|------|-------|
| File | `src/agent_config_sync/watcher.py` (+ `scripts/sense-watcher.ps1`) |
| Entry point | `watch_once(config, pending_path=None, now=None)` / CLI `watch-once` |
| Input | live config; optional pending-path and clock injection for tests |
| Output | `(title, body, exit_code)`; writes only `pending.json` |
| Key config | `%LOCALAPPDATA%/agent-config-sync/pending.json`; task `agent-config-sync-sense` (daily 09:00) |
| Error behavior | scan failure → gate-failure finding; corrupt pending → tolerated and healed |
| Dependencies | `sense.scan`, stdlib only |
| Test file | `tests/test_watcher.py` (8 cases incl. 2 blocking should-fails) |

---

## 📌 Implemented vs. Recommended

### What This Project Implements ✅
- Deterministic daily patrol with folded-in heartbeat (`watcher.watch_once`)
- HITL retention with `resolved` block across findings→clean transitions
- No-mutation guarantee proven by test (`test_watcher_never_mutates_runtimes_or_source`)
- Task registration/uninstall documented in the wrapper script header

### General Best Practices — Recommended but Not Implemented Here
- Watcher run history/log rotation (only the latest state is kept) — `Recommended (not implemented here)`
- OS-level task hardening (dedicated limited account for the scheduled task) — `Recommended (not implemented here)`

---

## ⚖️ Decisions & Trade-offs

### Decisions Touched
| Decision | Statement | Why It Matters Here |
|----------|-----------|---------------------|
| Daily cadence | One run/day; clean-run balloon doubles as heartbeat | Irregular operator usage + session hook covers sit-downs; one schedule, one signal |
| Advisory-only pending.json | No signature; live re-run is the control | A locally derivable key is readable by the same attacker — signing would be theater |
| Logic in Python, shell as messenger | `watch_once` tested; ps1 is 30 dumb lines | Notification mechanics can change without touching tested code |

### What We Explicitly Rejected
- **HMAC/DPAPI signing of pending.json:** considered in critique, rejected —
  same-user access defeats any local key, and the file was never a trust
  boundary (full rationale in `docs/TRADEOFFS.md`).
- **Minute-level polling:** config drift is slow and the operator's usage is
  irregular; tight polling buys noise, not safety.

### Trade-off Log
| Choice Made | What We Gained | What We Gave Up |
|-------------|----------------|-----------------|
| Daily, not continuous | One meaningful signal/day; near-zero footprint | Up to ~24h between-session detection latency |
| Deterministic Tier 2 before LLM Tier 3 | Proven rails; injection surface deferred until gated | Proposal-drafting convenience waits two weeks |

### Future Gate Conditions
- Tier 2 runs ≥2 weeks clean AND one real drift resolved through the
  notification workflow → Tier 3 (LLM proposal agent) may begin, starting
  with its eval dataset (S7)
- A drift event going unnoticed across a multi-day gap that mattered →
  revisit the daily cadence

---

## 🚀 You Have Reached the Current Frontier

Lesson 13 is the newest lesson; Tier 3 (the proposal-drafting agent) will earn
Lesson 14 only after it passes its gate and its eval dataset.

**Optional deeper dive:** read the Tier 3 sections of
`docs/superpowers/specs/2026-07-04-ambient-automation-spec.md` — the write
sandbox, instruction-integrity, and eval-dataset requirements are a compact
blueprint for reviewing anyone's ambient-LLM design.

**Modification challenge (<30 min):** change the wrapper to also write the
balloon title/body to a rotating text log next to `pending.json`, then re-run
Exercise 1 and confirm the log line appears. (Wrapper-only change — note that
zero Python tests needed to change, which is the logic/messenger split earning
its keep.)

*Remember: prove the rails deterministic before you put a probabilistic driver on them.* 🛡️
