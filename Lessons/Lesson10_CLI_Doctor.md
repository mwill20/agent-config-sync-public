# 🎓 Lesson 10: The Front Desk — cli.py & doctor.py

## 🛡️ Welcome Back, Security Analyst!

A system is only as usable as its front desk. 🔍 Today: **`cli.py`** (the command
surface and its exit-code contract) and **`doctor.py`** (the plain-language health
check). This is where every capability you've learned becomes a command a human — or
another AI — can run safely.

---

## 🎯 Learning Objectives
- Map the eight subcommands to the modules behind them
- Explain the exit-code contract (0–4) and why exit codes matter
- Trace `doctor`'s checks (repo / git / remote / per-runtime sync)
- Explain how errors become clean messages, never tracebacks

**Time estimate:** 18 min | **Prerequisites:** Lessons 02, 05

---

## 🧠 What This Does — Plain English

`cli.py` parses arguments, loads config (catching `ConfigError` → clean exit 3, not a
traceback), dispatches to the right module, and translates exceptions into documented
exit codes. `doctor` runs a handful of checks and prints an `ok`/`attention` column a
non-developer can scan: is the repo present, is git installed, is a remote configured,
is each runtime (and skill) in sync?

**Real-world analogy:** the reception desk + the lobby status board. The desk routes
you to the right office (subcommand); the board shows at a glance what's healthy and
what needs attention (doctor).

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
Exit codes are machine-readable verdicts — the same reason your scripts check a tool's
return code instead of scraping text. `check`'s exit 1 can gate a pre-commit hook or CI;
`doctor` is the at-a-glance health board you'd glance at before trusting the system.
**SOC parallel:** a scanner that returns a status code your SOAR playbook branches on — `0` clean, non-zero = act.

### 🟡 Engineer Lens
One `main(argv)` builds an `argparse` tree, loads config once (wrapped in try/except),
then dispatches. Each handler maps typed exceptions to a stable exit code:
`0` ok · `1` stale · `2` drift/unknown-runtime/conflict · `3` secret/non-neutral/config ·
`4` blanket-force. The contract is the API — documented in the README and depended on by
the hook.
**Engineering decision to own:** a single, documented exit-code contract shared across commands — and wrapping `load_config` so config problems are a clean `3`, not a stack trace (critique Finding F1).

### 🔴 AI Security Engineer Lens
This is the surface an *autonomous agent* drives via the `config-sync` skill. Clean exit
codes + non-traceback errors mean an agent can branch on results deterministically
instead of parsing prose (or being confused by a stack trace). The consequential
commands (`capture`, `promote`, `install-hooks`) require explicit human flags, so an
agent can *prepare* but a human *authorizes* — the autonomy boundary is in the CLI.
**AI security surface:** the human/agent autonomy boundary — the CLI lets an agent do read-only/dry-run freely but gates writes behind `--confirm` a human supplies.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/cli.py — config load is fail-safe
    try:
        config = load_config(_repo_root())
    except ConfigError as exc:
        print(f"Config error: {exc}. Check config/targets.yaml and the allowlist.")
        return 3                      # clean exit, never a traceback (Finding F1)
```

```python
# src/agent_config_sync/doctor.py
def doctor(config) -> list[tuple[str, str, str]]:
    rows = [("repo", "ok" if core.exists() else "attention", str(config.repo_root)),
            ("git", "ok" if shutil.which("git") else "attention", "version control"),
            ("remote", "ok" if remote else "attention", remote or "no off-machine backup")]
    for name, state in status(config).items():
        rows.append((f"sync:{name}", "ok" if state == "in-sync" else "attention", state))
    return rows
```

| Command | Module | Notes |
|---------|--------|-------|
| `project` `check` `status` | project / check / status | core forward + reporting |
| `doctor` | doctor | health board |
| `enroll` | enroll | bring a skill under management |
| `capture` | capture | dry-run default + `--confirm` |
| `promote` | promote | reverse; bare = scan all |
| `install-hooks` | settingsedit | the one allowlist exception |

> ⚠️ **Common pitfall:** depending on stdout text instead of exit codes. The text may
> evolve; the 0–4 contract is stable — branch on the code.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: CLI tests
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_cli.py -q
```
✅ **Success if:** green — incl. exit-code cases (drift→2, config→3, force→4) and capture/promote/install-hooks paths.

### 🔬 Exercise 2: The health board
```bash
agent-config-sync doctor
```
📊 **Expected:** rows for `repo`, `git`, `remote`, and `sync:<runtime>`/`sync:<rt>:skill:*`, each `ok` or `attention`.
✅ **Success if:** you can read system health in one glance.

### 🔬 Exercise 3: Exit-code contract
```bash
agent-config-sync check; echo "check=$?"
agent-config-sync nonsense-command; echo "bad=$?"
```
📊 **Expected:** `check=0` (if in sync) or `1` (stale); an unknown command errors via argparse (non-zero).
✅ **Success if:** you observe deterministic, scriptable return codes.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** Why invest in a documented exit-code contract for a small CLI?
**A:** Exit codes are the machine interface. A pre-commit hook or CI step branches on `check`'s `1`; automation distinguishes a secret (`3`) from drift (`2`) from a force-scope error (`4`) without parsing English. Wrapping config errors to a clean `3` (instead of a traceback) keeps that contract intact even on misconfiguration. The text is for humans; the code is the API.
*Why it works:* shows you design for automation and stable interfaces, not just interactive use.

### 🔴 AI Security Engineering
**Q:** An AI agent operates this tool via a skill. Where's the autonomy boundary?
**A:** In the CLI. Read-only and dry-run commands (`check`, `status`, `doctor`, `capture` without `--confirm`) are safe for an agent to run freely. The consequential writes — `capture --confirm`, `promote --confirm`, `install-hooks` — require an explicit flag a human supplies, and the deterministic gates still bind. So an agent can *prepare and preview* but a human *authorizes* the fan-out. Clean exit codes let the agent branch deterministically instead of misreading prose.
*Why it works:* locates the human-in-the-loop boundary concretely in the interface.

---

## ✅ Key Takeaways
- One `main(argv)` → argparse → load (fail-safe) → dispatch
- Stable exit-code contract: 0 ok · 1 stale · 2 drift/conflict · 3 secret/config · 4 force-scope
- `doctor` = scannable `ok`/`attention` health board
- The CLI is the autonomy boundary: agents prepare/preview, humans confirm writes

## 📋 Quick Reference
| Item | Value |
|------|-------|
| Files | `src/agent_config_sync/cli.py`, `doctor.py`, `__main__.py` |
| Entry | `main(argv) -> int` |
| Commands | `project check status doctor enroll capture promote install-hooks` |
| Exit codes | `0/1/2/3/4` (see README) |
| Tests | `tests/test_cli.py`, `tests/test_doctor.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** thin CLI over library modules; documented exit codes; consequential writes need `--confirm`.
- **Rejected:** an interactive prompt for confirmation — a flag is deterministic and testable.
- **Trade-off:** flags gain scriptability + a clear autonomy boundary; cost a slightly less hand-holding UX (the `config-sync` skill closes that gap for non-devs).

## 🎉 Curriculum complete!
You've traced the whole system: pure render → allowlist → gates → atomic writes/state →
forward projection → skills/enroll → capture → promote → the settings exception → the CLI.

**Modification challenge:** add a new read-only subcommand (e.g. `agent-config-sync where`
that prints the repo root + remote) — wire it into `cli.py`, give it a test, and notice
how the existing patterns make it a 10-minute change.

*Remember: a good front desk makes a powerful system safe to walk up to — for humans and agents alike.* 🛡️
