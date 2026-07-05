# 🎓 Lesson 02: The Guest List — config.py & targets.yaml, the Write Trust Boundary

## 🛡️ Welcome Back, Security Analyst!

A bouncer with a guest list only lets named people in. 🔍 Today: **`config.py`**
(`src/agent_config_sync/config.py`) and **`config/targets.yaml`** — the allowlist
that decides the *only* paths this tool may ever write to. Everything else is refused
before a single byte is written.

---

## 🎯 Learning Objectives
- Read `targets.yaml` and explain what each field authorizes
- Trace path validation (`_validate_dest`, `_validate_source`)
- Explain why destinations must resolve **under** a known runtime root
- Connect allowlisting to least privilege

**Time estimate:** 18 min | **Prerequisites:** Lesson 00

---

## 🧠 What This Does — Plain English

`targets.yaml` lists, per runtime, where the instruction file goes, which overlay
feeds it, and where skills go. `load_config` reads that file and **validates every
path**: destinations must resolve under `~/.claude`, `~/.codex`, or `~/.gemini`;
source paths must resolve under the repo. A path that escapes is a hard error — the
run stops before any write.

**Real-world analogy:** a firewall allowlist. Traffic to a declared host/port is
permitted; everything else is denied by default. The default is *no*.

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
This is allowlisting / least privilege made concrete — the same model as an EDR
application-control policy: only approved binaries (here, approved *paths*) are
permitted. If a config tried to write to `C:\Windows`, this is the control that says no.
**SOC parallel:** `targets.yaml` is an allowlist policy; `_validate_dest` is the enforcement engine that denies anything off-list.

### 🟡 Engineer Lens
Validation uses `Path.expanduser().resolve()` then `is_relative_to(root)` — resolving
symlinks and `..` *before* the containment check, so a path like
`~/.claude/../../evil` can't sneak through. Allowed roots are injectable
(`AGENT_CONFIG_SYNC_ALLOWED_ROOTS` env or a param) so tests are hermetic.
**Engineering decision to own:** resolve-then-contain is the correct order — checking containment on an unresolved path is a classic path-traversal bug.

### 🔴 AI Security Engineer Lens
This is the trust boundary that stops a poisoned `targets.yaml` (or a bug) from
writing agent instructions to an arbitrary location, or reading "source" from outside
the repo. In an agentic system where the tool runs semi-autonomously, this boundary is
what bounds the blast radius of a bad config.
**AI security surface:** containment of the write/read surface — the allowlist is the capability boundary for an automated process.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/config.py
def _validate_dest(raw: str, allowed: list[Path]) -> Path:
    resolved = Path(raw).expanduser().resolve()
    for root in allowed:
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    raise ConfigError(f"Destination '{resolved}' is not under an allowed runtime root")

def _validate_source(raw: str, repo_root: Path) -> Path:
    resolved = (repo_root / raw).resolve()
    if resolved == repo_root.resolve() or resolved.is_relative_to(repo_root.resolve()):
        return resolved
    raise ConfigError(f"Source path '{resolved}' is not under the repo root")
```

| Lines | What it does | Why |
|-------|-------------|-----|
| `expanduser().resolve()` | Expands `~`, resolves `..`/symlinks | Normalizes before the check (anti-traversal) |
| `is_relative_to(root)` | Containment test | The actual allowlist gate |
| `raise ConfigError` | Hard stop | Fail-closed: deny by default |

```yaml
# config/targets.yaml (shape)
runtimes:
  claude: {instruction_dest: "~/.claude/CLAUDE.md", overlay: "overlays/claude.md", skills_dest: "~/.claude/skills"}
managed_skills:
  - config-sync   # MUST remain the last top-level key (enroll rewrites this block)
```

> ⚠️ **Common pitfall:** putting another key after `managed_skills` — `enroll` rewrites
> the trailing block and will *refuse* (raise `ConfigError`) rather than truncate it
> (a guard added after a critique finding).

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Allowlist tests
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_config.py -q
```
✅ **Success if:** green, including the out-of-allowlist rejection case.

### 🔬 Exercise 2: Trigger a clean config error (intentional failure)
Point the allowlist somewhere that doesn't contain the dests:
```bash
AGENT_CONFIG_SYNC_REPO=. AGENT_CONFIG_SYNC_ALLOWED_ROOTS=/tmp/nope agent-config-sync status
echo "exit=$?"
```
📊 **Expected:** `Config error: Destination ... is not under an allowed runtime root.` and `exit=3` — a clean message, **not** a traceback (fixed as critique Finding F1).
✅ **Success if:** exit 3, no Python stack trace.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** Why resolve a path before the containment check instead of after?
**A:** `resolve()` collapses `..` and symlinks to an absolute real path. Checking containment on the raw string would let `~/.claude/../../etc/passwd` pass a naive prefix test; resolving first means the comparison is against the true target, closing the path-traversal hole. It's fail-closed — anything not provably inside an allowed root is rejected.
*Why it works:* shows awareness of a specific, common vulnerability class and the correct mitigation order.

### 🔴 AI Security Engineering
**Q:** An automated tool writes agent instructions. How do you bound where it can write?
**A:** A declared allowlist (`targets.yaml`) validated at load time, enforced on every write, default-deny. It's the capability boundary: even if upstream logic is buggy or the config is tampered, writes can only land under known runtime roots, bounding blast radius — and reads are similarly contained to the repo.
*Why it works:* applies least-privilege thinking to an autonomous process, not just a user.

---

## ✅ Key Takeaways
- `targets.yaml` is the allowlist; `config.py` enforces it, default-deny
- Resolve-then-contain prevents path traversal
- Allowed roots + repo containment bound both writes and source reads
- `managed_skills` must stay the last key (enroll guard)

## 📋 Quick Reference
| Item | Value |
|------|-------|
| Files | `src/agent_config_sync/config.py`, `config/targets.yaml` |
| Entry point | `load_config(repo_root, allowed_roots=None) -> Config` |
| Error | `ConfigError` (CLI maps to exit 3) |
| Env override | `AGENT_CONFIG_SYNC_ALLOWED_ROOTS`, `AGENT_CONFIG_SYNC_REPO` |
| Test | `tests/test_config.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** allowlist in YAML, validated at load.
- **Rejected:** writing wherever a path points (no boundary) — unacceptable for a tool that edits global config.
- **Trade-off:** explicit allowlist gains a hard capability boundary; gives up the convenience of arbitrary destinations (by design).

## 🚀 Next: Lesson 03 — the deterministic gates (`secrets.py` + `neutralize.py`).
*Remember: default-deny. If it's not on the list, it doesn't get written.* 🛡️
