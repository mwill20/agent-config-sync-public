# 🎓 Lesson 03: The Two Bouncers — secrets.py & neutralize.py, Deterministic Gates

## 🛡️ Welcome Back, Security Analyst!

Some checks are advisory ("looks suspicious"); some are binding ("you shall not
pass"). 🔍 Today: the two **deterministic gates** that *bind* — `secrets.py`
(no credentials in source) and `neutralize.py` (no vendor tool names in a neutral
skill). Rule-based, not AI-based — by design.

---

## 🎯 Learning Objectives
- Explain why security gates here are deterministic, never probabilistic
- Read the secret-pattern and vendor-term detectors
- Explain the denylist trade-off (false negatives vs. false positives)
- See where these gates fire in the write paths

**Time estimate:** 20 min | **Prerequisites:** Lesson 00

---

## 🧠 What This Does — Plain English

Before any content reaches the source of truth, two scanners run. `find_secrets`
rejects text that looks like a credential (API keys, tokens, quoted/unquoted
secret assignments). `find_vendor_terms` rejects skill bodies that name a specific
runtime's tools (`Skill tool`, `apply_patch`, `mcp__…`, slash-commands) — those
aren't *neutral* and would mis-steer the other runtimes. A hit aborts the write.

**Real-world analogy:** a SIEM correlation rule. Exact, explainable logic decides
pass/fail — you can read the rule and know why it fired. No "the model felt uneasy."

---

## 🔵🟡🔴 Career Lens

### 🔵 Analyst Lens
These are detection rules with a binding action. `find_secrets` is your secret-scanner
DLP rule; `find_vendor_terms` is a content-policy rule. Both produce explainable hits
you could paste into a ticket — the opposite of an opaque ML verdict.
**SOC parallel:** regex correlation rules that *block*, like a DLP policy that quarantines an email carrying a key.

### 🟡 Engineer Lens
Both are pure functions returning the list of offending matches (empty = clean), with
typed exceptions (`SecretFoundError`, `NeutralLanguageError`) carrying the matches for
a clear message. `neutralize` deliberately splits two classes: common-English tool
names (`Read`, `Edit`) are flagged *only* in `"<Name> tool"` form to avoid false
positives on prose; unique tokens (`apply_patch`, `mcp__…`) are matched bare.
**Engineering decision to own:** the denylist is curated, not exhaustive — a conscious trade of completeness for zero false-positives, documented in LIMITATIONS.

### 🔴 AI Security Engineer Lens
This is the **deterministic-gate-over-probabilistic-judgment** principle, which is the
core defense against prompt injection here: untrusted captured/promoted content is
judged by rules, never by an LLM that the same untrusted content could manipulate. An
AI may *propose* a neutral rewrite; `find_vendor_terms` *decides* if it's clean.
**AI security surface:** the gate that a probabilistic model must never replace — if an LLM could authorize the write, attacker-controlled text could talk its way in.

---

## 📝 Code Walkthrough

```python
# src/agent_config_sync/neutralize.py (the two match classes)
_NAMED_TOOLS = (r"Skill|Bash|Edit|Write|Read|Glob|Grep|Task|Agent|MultiEdit|"
                r"NotebookRead|BashOutput|KillShell")
_VENDOR_TERMS = [
    rf"\b(?:{_NAMED_TOOLS}) tool\b",   # "<Tool> tool" only — not bare 'read'
    r"mcp__[A-Za-z0-9_]+",             # any MCP tool name
    r"\bapply_patch\b", r"\bactivate_skill\b", r"\bTodoWrite\b",
    r"\bsubagent_type\b", r"functions\.[A-Za-z_]+",
]
```

| Pattern | Catches | Avoids |
|---------|---------|--------|
| `\b(?:Bash\|Edit\|…) tool\b` | "Bash tool", "Edit tool" | "the right tool", "This tool" (prose) |
| `mcp__\w+` | any MCP tool id | — |
| bare tokens | `apply_patch`, `TodoWrite` | (unique enough to match bare) |

```python
# src/agent_config_sync/secrets.py (representative patterns)
re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),          # vendor-prefixed key
re.compile(r"(?i)(?:...)?(?:key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
```

> ⚠️ **Common pitfall:** assuming the lints are exhaustive. They *reduce* risk; a human
> still reviews the diff before `--confirm`. A novel credential format or a new runtime
> tool name can slip a gate — add patterns as you find them.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Gate tests
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_secrets.py tests/test_neutralize.py -q
```
✅ **Success if:** green — incl. should-fail cases and the prose-not-flagged guard.

### 🔬 Exercise 2: Probe the neutral lint
```bash
python -c "from agent_config_sync.neutralize import find_vendor_terms as f; print(f('Use the Bash tool and mcp__x__y; pick the right tool.'))"
```
📊 **Expected:** `['Bash tool', 'mcp__x__y']` — note "the right tool" is **not** flagged.
✅ **Success if:** only the real vendor terms appear.

### 🔬 Exercise 3: Secret blocked (intentional failure)
```bash
python -c "from agent_config_sync.secrets import find_secrets as f; print(f('api_key = \"abcd1234efgh5678\"'))"
```
📊 **Expected:** a non-empty list (the match).
✅ **Success if:** the assignment is detected.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering
**Q:** Your neutral-language lint is a denylist. What's the weakness and why accept it?
**A:** Denylists miss the unknown — a new runtime tool name passes until added. The alternative (a broad `\w+ tool` rule) would false-positive on ordinary prose like "the right tool," blocking legitimate enrollment. We curate the list, match common-English names only in `"<Name> tool"` form, and keep a human diff review as the backstop. It's a deliberate completeness-vs-false-positive trade, documented in LIMITATIONS.
*Why it works:* shows you reason about detection trade-offs and compensating controls, not just "add more regex."

### 🔴 AI Security Engineering
**Q:** Why must these gates be deterministic in a system that also uses AI review?
**A:** The content being judged may be attacker-controlled and is destined for three agents' prompts. If an LLM authorized the write, that same untrusted text could manipulate the judge (prompt injection). Deterministic rules can't be talked out of their verdict. The LLM's role is advisory enrichment only; rules + a human confirm are the binding controls.
*Why it works:* names the injection-of-the-judge risk and the correct architectural boundary.

---

## ✅ Key Takeaways
- Two binding gates: secret-lint and neutral-language lint
- Pure, explainable, deterministic — never an LLM verdict
- Curated denylist: zero false-positives over exhaustiveness, human backstop
- They fire before any write, even in dry-run

## 📋 Quick Reference
| Item | Value |
|------|-------|
| Files | `src/agent_config_sync/secrets.py`, `neutralize.py` |
| Entry points | `find_secrets(text)`, `find_vendor_terms(text)` |
| Exceptions | `SecretFoundError`, `NeutralLanguageError` |
| Tests | `tests/test_secrets.py`, `tests/test_neutralize.py` |

## ⚖️ Decisions & Trade-offs
- **Decision:** deterministic gates bind; AI review advisory only.
- **Rejected:** LLM-based "is this safe?" gate — injectable by the very content it judges.
- **Trade-off:** regex/denylist gains explainability + injection-resistance; gives up catching novel formats (mitigated by human review).

## 🚀 Next: Lesson 04 — atomic writes & drift hashing (`fsutil.py` + `state.py`).
*Remember: a security gate you can read is a security gate you can trust.* 🛡️
