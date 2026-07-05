# agent-config-sync — Plan 2 / Slice B (part 1): Discovery + `config-sync` skill

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every runtime able to *discover* the source of truth and *verify it is in sync* — by (1) projecting a neutral "discovery" section into all three instruction files, and (2) shipping a dog-fooded, neutral `config-sync` skill that teaches any AI (or you) the check/status/project/enroll workflow in plain language.

**Architecture:** Both deliverables are content-level uses of machinery already built in Plan 1 + Slice A — no new write surface. The discovery section is authored into `_shared/core.md`, so Plan 1's projector fans it into `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` automatically. The `config-sync` skill is a neutral `skills/config-sync/SKILL.md` enrolled via Slice A's `enroll_skill` and projected by `project_skills`. No timestamp stamp is rendered (it would break idempotency — see Global Constraints).

**Tech Stack:** Python 3.11+, stdlib, `pyyaml==6.0.2`; `pytest==8.3.4`. Reuses `render`, `project`, `skills`, `enroll`, `neutralize`. No new dependencies.

## Global Constraints

- Python floor **3.11**; deps pinned (`pyyaml==6.0.2`, dev `pytest==8.3.4`); no new deps.
- Test command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` (global `web3` plugin breaks plain collection).
- **No wall-clock content in projected files.** Any drift signal must be deterministic (same source → identical output) or it breaks idempotency and the `check`/drift guard. This slice renders **no** stamp; `check` is the drift signal.
- **Discovery section lives in `_shared/core.md`** (neutral) so it projects to all three runtimes identically. It must contain no vendor tool names (it passes through, but keep the source neutral).
- **`config-sync` skill body must pass `neutralize.find_vendor_terms` (empty)** — it is the first dog-fooded neutral skill; enrollment enforces this.
- All files UTF-8, LF newlines.

## Verified runtime facts (on-machine, 2026-06-28 — do NOT re-derive)

These were checked live and refine HANDOFF §8 (which was partly wrong). They are
needed by the **B3 hooks plan (next)**, recorded here so it can be written fast:

- **Claude `settings.json` SessionStart schema (verified):**
  ```json
  "hooks": { "SessionStart": [ { "hooks": [ { "type": "command", "command": "<cmd>" } ] } ] }
  ```
  A `SessionStart` hook **already exists** (`skill_compass.py`) plus a `Stop` hook —
  so B3 must **merge/append**, never overwrite the file.
- **Gemini hooks:** there is **no** `gemini hooks list/add`. The only subcommand is
  `gemini hooks migrate --from-claude`, which converts Claude Code hooks into
  Gemini's own `~/.gemini/settings.json` format. **B3 must use `migrate`** rather
  than hand-writing Gemini's hook schema (which is undocumented here).
- **Codex:** no `hooks` and no `skills` subcommand (`codex` has `mcp`, `plugin`, …).
  Confirms the design's instructed-discovery + last-synced fallback for Codex.

**Implication for B3 (out of this plan):** writing `~/.claude/settings.json` is the
first write *outside* the `targets.yaml` allowlist — a new trust boundary. It needs
its own plan (merge-safe read/modify/write, idempotent, backed up) and a
`docs/threat-models/` touch, per owner decision #2 ("the one hook entry").

---

## File Structure

```
_shared/core.md                       MODIFY: add the "## Keeping configs in sync" discovery section
skills/config-sync/SKILL.md           CREATE: neutral dog-fooded skill body
config/targets.yaml                   MODIFY (via enroll): managed_skills += config-sync
tests/test_discovery.py               CREATE: discovery section present + propagates to all overlays
tests/test_config_sync_skill.py       CREATE: skill body is neutral; enroll+project lands it everywhere
README.md / AGENTS.md / HANDOFF.md / docs/EVALUATION.md   MODIFY: document discovery + skill; correct HANDOFF §8
```

No source-code modules change — this slice is content + tests over existing engines.

---

### Task 1: Discovery section in the neutral source

**Files:**
- Modify: `_shared/core.md` (append a discovery section)
- Test: `tests/test_discovery.py`

**Interfaces:**
- Consumes: `render(core_text, overlay_text)` from `agent_config_sync.render` (existing: returns `header + core + overlay`).
- Produces: a stable marker string `Keeping configs in sync` present in every projected instruction file.

- [ ] **Step 1: Write the failing test**

Create `tests/test_discovery.py`:

```python
from pathlib import Path

from agent_config_sync.render import render

REPO = Path(__file__).resolve().parents[1]
MARKER = "## Keeping configs in sync"


def test_real_core_has_discovery_section():
    core = (REPO / "_shared" / "core.md").read_text("utf-8")
    assert MARKER in core
    assert "agent-config-sync" in core
    assert "check" in core  # names the verify command


def test_discovery_propagates_to_every_runtime():
    core = (REPO / "_shared" / "core.md").read_text("utf-8")
    for overlay_name in ("claude.md", "codex.md", "gemini.md"):
        overlay = (REPO / "overlays" / overlay_name).read_text("utf-8")
        out = render(core, overlay)
        assert MARKER in out  # discovery reaches each rendered instruction file
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_discovery.py -q`
Expected: FAIL on `test_real_core_has_discovery_section` (marker not yet in core).

- [ ] **Step 3: Append the discovery section to `_shared/core.md`**

Add this at the end of `_shared/core.md` (neutral — no vendor tool names):

```markdown

## Keeping configs in sync

Your global instruction file and your skills are **generated** from one source of
truth: the `agent-config-sync` repository at `C:\Projects\agent-config-sync`
(mirror: `github.com/mwill20/agent-config-sync-public`). Do not hand-edit the
generated files — edits are overwritten and may be refused as drift.

- **To change a shared standard:** edit `_shared/core.md` in that repo, then run
  `agent-config-sync project`.
- **To change one runtime only:** edit that runtime's `overlays/<vendor>.md`, then
  `agent-config-sync project`.
- **To check whether everything is in sync:** run `agent-config-sync check`
  (exit 0 = in sync; non-zero = something drifted). `agent-config-sync status`
  shows per-runtime detail.
- **To add or update a skill:** use the `config-sync` skill, or run
  `agent-config-sync enroll <name> --body-file <path>` then `project`.

If a change you made inside this runtime should be shared, it must be promoted
back to the source (reverse `promote` — see the repo's roadmap) rather than left
as a local edit.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_discovery.py -q`
Expected: PASS (both tests).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS (86 prior + 2 new = 88).

- [ ] **Step 6: Commit**

```bash
git add _shared/core.md tests/test_discovery.py
git commit -m "feat(discovery): neutral 'keeping configs in sync' section in core source"
```

---

### Task 2: The dog-fooded `config-sync` skill

**Files:**
- Create: `skills/config-sync/SKILL.md`
- Test: `tests/test_config_sync_skill.py`

**Interfaces:**
- Consumes: `neutralize.find_vendor_terms` (lint), `enroll.enroll_skill`, `skills.project_skills`, `config.load_config` (all existing).
- Produces: a managed skill named `config-sync` whose body is vendor-neutral and which projects into every runtime as `SKILL.md` + that runtime's tool adapter.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_sync_skill.py`:

```python
from pathlib import Path

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill
from agent_config_sync.neutralize import find_vendor_terms
from agent_config_sync.skills import project_skills

REPO = Path(__file__).resolve().parents[1]


def test_config_sync_skill_body_is_neutral():
    body = (REPO / "skills" / "config-sync" / "SKILL.md").read_text("utf-8")
    assert find_vendor_terms(body) == []  # no vendor tool names / slash commands


def test_config_sync_projects_to_all_runtimes(fake_env):
    # Author the skill body into the fake repo and enroll + project it.
    body = (REPO / "skills" / "config-sync" / "SKILL.md").read_text("utf-8")
    (fake_env.repo / "skills" / "config-sync").mkdir(parents=True)
    (fake_env.repo / "skills" / "config-sync" / "SKILL.md").write_text(body, "utf-8")
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    enroll_skill(cfg, "config-sync", body)
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)  # reload
    project_skills(cfg)
    for runtime in ("claude", "codex", "gemini"):
        base = cfg.runtimes[runtime].skills_dest / "config-sync"
        assert (base / "SKILL.md").read_text("utf-8") == body
        assert (base / "references").is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_config_sync_skill.py -q`
Expected: FAIL (skill file does not exist).

- [ ] **Step 3: Create `skills/config-sync/SKILL.md`** (neutral body)

```markdown
---
name: config-sync
description: Keep this AI's global instructions and skills in sync with the shared source of truth, and add new ones safely.
---

# Keeping your AI config in sync

This runtime's global instruction file and skills are generated from one shared
source (the `agent-config-sync` repository). Use this skill to check sync, apply
updates, and add new skills or standards — the same way in every AI.

## Check whether you are in sync

Run `agent-config-sync check`. Exit 0 means everything matches the source.
A non-zero result means something drifted; run `agent-config-sync status` to see
which runtime and which file.

## Apply the latest source

Run `agent-config-sync project` to regenerate this runtime's instruction file and
managed skills from the source. It refuses to overwrite a file you hand-edited
(to avoid losing your change) unless you scope it to one runtime with `--force`.

## Add or update a skill

1. Write the skill body as a neutral `SKILL.md` (describe actions, not a specific
   runtime's tools — e.g. "dispatch a subagent", "read a file").
2. Run `agent-config-sync enroll <name> --body-file <path>`. This refuses bodies
   that contain runtime-specific tool names or secrets.
3. Run `agent-config-sync project` to copy it into every runtime.

## Add or change a standard

Edit the shared source (`_shared/core.md` for something every AI should follow,
or `overlays/<runtime>.md` for one runtime), then run `agent-config-sync project`.

## If something looks wrong

Every overwrite is backed up under the repo's `.backups/` folder, and every
action is recorded in the audit log. Recover a previous version from there.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_config_sync_skill.py -q`
Expected: PASS. If `test_config_sync_skill_body_is_neutral` fails, the body
contains a flagged term — reword to neutral action language (do not weaken the lint).

- [ ] **Step 5: Run the full suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS (90 total).

- [ ] **Step 6: Commit**

```bash
git add skills/config-sync/SKILL.md tests/test_config_sync_skill.py
git commit -m "feat(skills): neutral dog-fooded config-sync skill"
```

---

### Task 3: Enroll `config-sync` into the real source + docs

**Files:**
- Modify: `config/targets.yaml` (via `enroll` — `managed_skills += config-sync`)
- Modify: `README.md`, `AGENTS.md`, `HANDOFF.md`, `docs/EVALUATION.md`

**Interfaces:** none new (CLI + docs).

- [ ] **Step 1: Enroll the skill into the real repo source**

Run from the repo root (writes `skills/config-sync/SKILL.md` is already present;
this adds it to `managed_skills` in the real `targets.yaml`):

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m agent_config_sync enroll config-sync \
  --body-file skills/config-sync/SKILL.md
```

Expected: `Enrolled 'config-sync'. Run \`project\` to fan it out.` (exit 0).
Confirm `config/targets.yaml` now lists `- config-sync` under `managed_skills`
and the file's comments/structure above are intact.

- [ ] **Step 2: Verify the suite still passes with the skill enrolled**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS (the enrolled skill does not break any fake-env test).

- [ ] **Step 3: Document discovery + the skill**

- `README.md`: under the skills section, add a line that a `config-sync` skill is
  projected into every runtime so any AI can run the sync workflow; note the
  discovery section now appears in each instruction file.
- `AGENTS.md`: note that `config-sync` is a managed skill and the discovery
  section is the canonical "where is the source / how to check" pointer.
- `HANDOFF.md`: mark Slice B part 1 done; **correct §8** — replace the wrong
  "`gemini hooks` (incl. list)" wording with the verified facts from this plan's
  "Verified runtime facts" section; note B3 (hooks/settings.json) is the next plan.
- `docs/EVALUATION.md`: add a suite-count row (→ 90) and any live runs performed.

- [ ] **Step 4: Commit**

```bash
git add config/targets.yaml README.md AGENTS.md HANDOFF.md docs/EVALUATION.md
git commit -m "feat(discovery): enroll config-sync skill; docs + corrected HANDOFF hook facts"
```

- [ ] **Step 5 (owner-run apply, optional): project to live config**

This writes the discovery section + `config-sync` skill into the real
`~/.claude`, `~/.codex`, `~/.gemini`. Run when ready (it backs up first):

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m agent_config_sync project --dry-run   # preview
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m agent_config_sync project              # apply
```

---

## Self-Review

**Spec coverage (Plan 2 design §5.3 capability B):**
- "Discovery section in `_shared/core.md` → projects into all three instruction files" → Task 1 (`test_discovery_propagates_to_every_runtime`). ✅
- "`config-sync` managed skill (dog-foods A; neutral)" → Tasks 2–3 (neutral-body test + enroll + project test). ✅
- "Last-synced stamp" → **deliberately dropped** (would break idempotency; documented in Global Constraints). The `check` command is the drift signal. ✅ (design deviation, justified)
- "Startup hook (settings.json / gemini migrate / codex fallback)" → **scoped to the next plan (B3)**; verified facts captured here. ◻️ (intentional split — new trust boundary)

**Placeholder scan:** none — every code/content step shows the full text. The two doc steps name exact files and exact edits.

**Type consistency:** uses only existing, verified signatures (`render`, `find_vendor_terms`, `enroll_skill`, `project_skills`, `load_config`); the `config-sync` name and `## Keeping configs in sync` marker are identical across tasks and tests.

**Out of scope (next plans):** B3 startup-hook installation (settings.json writer + `gemini hooks migrate` + Codex instructed fallback) with its threat-model touch; `doctor` health command (Plan 2 §5.5); Slice C capture; Plan 3 promote.
```

