# Audit & Verification Brief — agent-config-sync

> **Audience:** AI engineers (Codex, Gemini, and human reviewers) tasked with
> independently testing, confirming, and auditing this repo on their own machine/runtime.
> **Goal:** give you everything to prove the system works *and* is safe — not to take
> the author's word for it. Every claim here is checkable with a command below.

---

## 0. TL;DR — what to confirm

1. The package imports, and **181 tests pass** (section 3; count grows as
   features land — treat the current suite result as the baseline).
2. Forward projection, skills, capture, and reverse promote behave per spec, including
   the **should-fail** paths (§4).
3. The **startup hook is wired into your runtime** and actually fires (§5 — Codex/Gemini specific).
4. The **security gates are deterministic and binding** (secret, allowlist, neutral-language,
   drift) and the AI never authorizes a write (§6).
5. The reverse `promote` round trip works and **3-way conflicts are refused, not merged** (§4.4).

If any of those fail on your end, that's a finding — record it.

---

## 1. What this is (one paragraph)

A vendor-neutral **source of truth** that projects AI-runtime config into Claude Code,
Codex, and Gemini/AntiGravity. Source = `_shared/core.md` (neutral) + `overlays/<vendor>.md`
(per-vendor) + `skills/<name>/SKILL.md` (neutral skill bodies). `project` renders/copies
the source out (forward); `promote` lifts a runtime edit back into the source (reverse);
`capture` ingests a new rule/skill from chat. All writes are allowlisted, atomic, backed
up, audited, and gated by deterministic checks. A human `--confirm` is the binding control
on the consequential reverse/capture paths.

## 2. Architecture map (file : responsibility)

| File | Responsibility |
|------|----------------|
| `render.py` | Pure: `header + core + overlay` (deterministic) |
| `config.py` + `config/targets.yaml` | Allowlist; path validation (resolve-then-contain) |
| `secrets.py` | `find_secrets` — credential denylist (binding gate) |
| `neutralize.py` | `find_vendor_terms` (binding gate) + cross-runtime reconciliation |
| `fsutil.py` / `state.py` | Atomic write, backup, sha256; `.sync-state.json` hash ledger |
| `project.py` | Forward projection + drift guard (create/unchanged/update/drift/forced) |
| `skills.py` / `enroll.py` | Narrow skill projection (`SKILL.md` + adapter only) / gated one-skill enrollment |
| `capture.py` | Capture-from-chat: route → lint → diff → confirm → write |
| `promote.py` | Reverse: detect divergence → route → capture engine → reproject; 3-way conflict refusal |
| `settingsedit.py` | The allowlist exception: merge-safe Claude `settings.json` + Codex `config.toml` hook writers |
| `doctor.py` | Env + sync health |
| `cli.py` | Command surface + exit-code contract |

Trust boundaries: (1) captured/promoted content → source; (2) source → three agents;
(3) the two hook-config writes (`settings.json`, `config.toml`) — the only writes outside
`targets.yaml`. Threat models: `docs/threat-models/` (poisoned-core, capture/promote, settings-write).

## 3. Environment & baseline (run first)

```bash
git clone <this repo> && cd agent-config-sync
python -m pip install -e ".[dev]"

# Validation command — plain `pytest` is broken in the author's env (a global web3
# plugin poisons collection); this flag is the documented workaround. On a clean
# machine plain `pytest -q` may also work — try both.
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
```
**Expected:** `165 passed`. If your environment differs (Linux/macOS), note any
platform-specific failures, especially hook subprocess behavior.
(`settingsedit`/`cli`) worth auditing on non-Windows.

## 4. Functional verification (safe — uses a sandbox, never your real config)

Point the tool at a throwaway tree so you never touch your real `~/.claude` etc.
Use **native** paths for your OS and your OS path separator for the allowlist
(`;` on Windows, `:` on POSIX).

```bash
SB=/tmp/acs-sbx; rm -rf $SB
mkdir -p $SB/repo/{_shared,overlays,references,skills,config} $SB/home/{.claude,.codex,.gemini}
printf '# Core\nSecurity is the foundation.\n' > $SB/repo/_shared/core.md
for v in claude codex gemini; do printf '## %s\nNeutral.\n' $v > $SB/repo/overlays/$v.md; done
for a in claude-code codex gemini; do printf '# %s adapter\n' $a > $SB/repo/references/$a-tools.md; done
cat > $SB/repo/config/targets.yaml <<YAML
runtimes:
  claude: {instruction_dest: "$SB/home/.claude/CLAUDE.md", overlay: "overlays/claude.md", skills_dest: "$SB/home/.claude/skills"}
  codex:  {instruction_dest: "$SB/home/.codex/AGENTS.md",  overlay: "overlays/codex.md",  skills_dest: "$SB/home/.codex/skills"}
  gemini: {instruction_dest: "$SB/home/.gemini/GEMINI.md", overlay: "overlays/gemini.md", skills_dest: "$SB/home/.gemini/skills"}
managed_skills: []
YAML
export AGENT_CONFIG_SYNC_REPO=$SB/repo
export AGENT_CONFIG_SYNC_ALLOWED_ROOTS="$SB/home/.claude:$SB/home/.codex:$SB/home/.gemini"  # ';' on Windows
```

### 4.1 Forward + idempotency
```bash
agent-config-sync status      # all 'missing'
agent-config-sync project     # all 'create'
agent-config-sync project     # all 'unchanged'  <-- idempotent
agent-config-sync check       # exit 0
```

### 4.2 Drift guard (should refuse)
```bash
printf '\nHAND EDIT\n' >> $SB/home/.gemini/GEMINI.md
agent-config-sync project; echo "exit=$?"     # expect: refusal, exit 2, edit preserved
agent-config-sync project gemini --force; echo "exit=$?"   # expect: exit 0, backup written
```

### 4.3 Capture gates (should abort before write)
```bash
printf 'api_key = "abcd1234efgh5678"\n' > $SB/leak.md
agent-config-sync capture standard --target core --text-file $SB/leak.md --confirm; echo "exit=$?"  # expect 3, core unchanged
printf -- '---\nname: bad\ndescription: x\n---\nUse the Bash tool.\n' > $SB/bad.md
agent-config-sync capture skill --name bad --body-file $SB/bad.md --confirm; echo "exit=$?"          # expect 3 (non-neutral)
```

### 4.4 Reverse promote round trip + 3-way conflict
```bash
agent-config-sync project
printf '\nSHARED LEARNING.\n' >> $SB/home/.gemini/GEMINI.md
agent-config-sync promote gemini --target core --confirm
grep -c "SHARED LEARNING" $SB/home/.claude/CLAUDE.md $SB/home/.codex/AGENTS.md   # expect 1,1
# now force a 3-way conflict:
printf '\nSOURCE MOVED.\n' >> $SB/repo/_shared/core.md
printf '\nLIVE EDIT.\n'    >> $SB/home/.gemini/GEMINI.md
agent-config-sync promote gemini --target core --confirm; echo "exit=$?"          # expect refusal (PromoteConflict), exit 2
```

**Audit point:** confirm the secret/neutral aborts happen *before* any file write
(check the target's mtime/content is unchanged), and the conflict is refused, not merged.

## 5. Runtime-specific verification (the part you bring home)

> These confirm the hook is wired **and actually executes** in YOUR runtime. The author
> verified on Windows; confirm on your platform. `install-hooks` writes your *real*
> config (backed up to `.backups/` first) — review the diff before/after.

### 5.1 Codex
- **Confirm the feature is on:** `codex features list | grep codex_hooks` → `stable true`.
- **Install:** `agent-config-sync install-hooks` (or just the Codex part by inspecting
  `~/.codex/config.toml`).
- **Confirm the hook landed & config is intact:**
  ```bash
  python -c "import tomllib,os; d=tomllib.loads(open(os.path.expanduser('~/.codex/config.toml')).read()); \
  print('hook:', 'agent-config-sync check' in [h['command'] for e in d['hooks']['SessionStart'] for h in e['hooks']]); \
  print('notify preserved:', 'notify' in d); print('plugins preserved:', 'plugins' in d)"
  ```
  Expect `hook: True`, and your pre-existing `notify`/`plugins` still present.
- **Confirm it FIRES:** start a fresh Codex session (`matcher = "startup|resume"`) and
  confirm `agent-config-sync check` runs at SessionStart (it prints sync status / surfaces
  drift). **This is the real end-to-end test — only Codex can confirm it on Codex.**
- **Confirm discovery:** `~/.codex/AGENTS.md` contains the "## Keeping configs in sync"
  section, and `~/.codex/skills/config-sync/SKILL.md` exists.
- **Audit:** is `command` run with session `cwd`? Does `agent-config-sync` resolve on
  Codex's PATH at hook time? If not, the hook prints a not-found — record it.

### 5.2 Gemini / AntiGravity
- **Install path:** `install-hooks` runs `gemini hooks migrate --from-claude` from `$HOME`
  (so it reads the global `~/.claude/settings.json`).
- **Confirm the hook landed:**
  ```bash
  python -c "import json,os; d=json.load(open(os.path.expanduser('~/.gemini/settings.json'))); \
  print('hook:', 'agent-config-sync check' in [h['command'] for e in d['hooks']['SessionStart'] for h in e['hooks']])"
  ```
- **Confirm it FIRES:** start a Gemini CLI session and confirm the SessionStart hook runs.
- **Confirm skills auto-discovery:** `gemini skills list` should show `config-sync` as
  Enabled after projection copies `~/.gemini/skills/config-sync/SKILL.md`.
- **Confirm skill activation:** Gemini CLI 0.26.0 exposes `activate_skill`; use it
  after the file is discoverable. Discovery and activation are separate checks.
- **AntiGravity:** loads a skill by reading its `SKILL.md`; verify activation behavior
  separately if testing AntiGravity rather than Gemini CLI.

### 5.3 Claude (reference)
- `~/.claude/settings.json` `hooks.SessionStart` includes `agent-config-sync check`
  alongside any pre-existing hooks (merge-safe). Confirm a fresh session runs it.

## 6. Security audit checklist

- [ ] **Deterministic gates bind, AI never authorizes a write.** Confirm `capture`/`promote`
      require an explicit human `--confirm`; the tool calls no LLM. (`cli.py`, `capture.py`)
- [ ] **Secret lint** fires before write, in dry-run too. (`secrets.find_secrets`)
- [ ] **Allowlist** uses resolve-then-contain (anti path-traversal). (`config._validate_dest`)
- [ ] **Neutral-language lint** is a curated denylist — probe for gaps (new tool names);
      confirm it does NOT false-positive on prose ("the right tool"). (`neutralize.py`)
- [ ] **Drift guard**: runtime writes are hash-tracked; source-behind, live-only, true conflict, and missing-baseline states are distinct. (`project.py`, `promote.py`)
- [ ] **Hook writers** are merge-safe, idempotent, parse-or-abort, backup-first, fixed
      command (no injection). Codex writer re-validates TOML before writing; no `shell=True`
      (Gemini `.cmd` invoked via `cmd /c` list-args). (`settingsedit.py`)
- [ ] **3-way promote conflict** is refused, not merged. (`promote.PromoteConflict`)
- [ ] **Backups + audit**: source and runtime overwrites copy to `.backups/`; `.sync-audit.log` records consequential writes.
- [ ] **No secrets committed**: `.sync-state.json`, `.sync-audit.log`, `.backups/`, `.claude/` are gitignored.

## 7. Known limitations to probe (see docs/LIMITATIONS.md)

- Secret + neutral-language lints are pattern/denylist based — *reduce*, not eliminate.
- `capture`/`promote` don't auto-`git commit` (print a hint).
- `promote` refuses true source+live conflicts and missing baselines instead of guessing.
- Append-only edits are supported; deletions/replacements require a unique source match.
- Ambiguous promote mappings are refused before source mutation.
- Gemini hook depends on the Gemini CLI's `migrate` conversion (owned by Gemini).
- No `--dry-run` for `install-hooks` yet (TODO in the settings-write threat model).

## 8. Report back

For each runtime, record: did the hook install cleanly? did it FIRE at session start?
were prior configs preserved? did any gate behave differently than §4 expects? File
findings against the relevant `file:function` from §2 so they're actionable.
```
