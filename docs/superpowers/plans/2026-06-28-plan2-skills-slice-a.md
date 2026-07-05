# agent-config-sync — Plan 2 / Slice A: Skills Projection + Enrollment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author a skill once as a vendor-neutral body and project it into each runtime's skills directory (`~/.claude/skills/<name>/`, `~/.codex/skills/<name>/`, `~/.gemini/skills/<name>/`) — each carrying `SKILL.md` plus that runtime's tool-adapter — safely, idempotently, with enrollment gated by a deterministic neutral-language lint and cross-runtime reconciliation.

**Architecture:** Slice A generalizes Plan 1's `project()` from a single instruction file per runtime to a *set* of files per managed skill. A managed skill's canonical neutral body lives at `skills/<name>/SKILL.md`. For each enrolled skill × runtime, the projector writes `<skills_dest>/<name>/SKILL.md` (the canonical body, verbatim) **plus** `<skills_dest>/<name>/references/<vendor>-tools.md` (that runtime's adapter, copied from the repo's `references/`). Drift, backups, secret-lint, and audit reuse Plan 1's modules unchanged. Enrollment is a separate, deterministic gate: read the skill's existing variants across runtimes → reconcile to one canonical body → require the body to pass the neutral-language lint → write it to source and add the name to `managed_skills`.

**Tech Stack:** Python 3.11+, stdlib (`pathlib`, `hashlib`, `re`, `json`, `shutil`, `os`, `datetime`, `argparse`), `pyyaml==6.0.2`; tests with `pytest==8.3.4`. Reuses existing modules: `render`, `secrets`, `fsutil`, `state`, `config`, `audit`, `project`.

## Global Constraints

- Python floor: **3.11** (uses `Path.is_relative_to`, `X | None` types).
- Dependencies pinned exactly: runtime `pyyaml==6.0.2`; dev `pytest==8.3.4`. No new third-party deps.
- **Allowlist writes only:** every skill file resolves under a declared `skills_dest` (itself validated under `~/.claude`, `~/.codex`, `~/.gemini` by `config._validate_dest`). Any path escaping the allowlist is a hard error.
- **No secrets written:** a skill body is scanned with `find_secrets()` and the run aborts before any write if a match is found (same gate as instruction files).
- **Deterministic gates bind:** the neutral-language lint and cross-runtime reconciliation are binding controls on enrollment. No probabilistic/AI judgment gates a write (AI neutralization only *proposes* a body; `find_vendor_terms()` decides).
- **Atomic writes only:** every write goes through `fsutil.atomic_write` (temp + `os.replace`). Every overwrite is backed up first via `fsutil.backup`.
- **Drift guard:** a managed skill file hand-edited out of band is refused (`SkillDriftError`) unless per-runtime `--force` is given (mirrors Plan 1's `DriftError` / `ForceScopeError`).
- **Determinism:** timestamps (`stamp`) and allowed-roots stay injectable; tests hermetic via the `fake_env` fixture. No wall-clock or real `$HOME` reads inside testable functions.
- All files UTF-8, LF newlines.
- **`managed_skills` must remain the last top-level key in `config/targets.yaml`** (the enrollment writer rewrites that trailing block textually to preserve the file's security comments).
- Run tests with: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` (a broken global `web3` pytest plugin poisons plain collection in this env).

## Decisions carried from the Plan 2 design (resolved 2026-06-28)

- **Incremental opt-in enrollment** — `managed_skills` starts empty; enroll one skill at a time. No bulk rewrite.
- **Capture friction / settings.json hook / durability** — belong to Slices B and C (separate plans). Slice A folds in only the *durability setup step* (private remote) as Task 7, per the owner decision to build it into Plan 2.

---

## File Structure

```
references/
  claude-code-tools.md      # tool adapter, seeded from superpowers (Task 1)
  codex-tools.md
  gemini-tools.md
skills/<name>/SKILL.md       # canonical neutral skill bodies (written by enroll)
overlays/gemini.md           # FIX: remove the wrong "activate_skill" line (Task 1)
config/targets.yaml          # managed_skills enrollment list (rewritten by enroll)
src/agent_config_sync/
  neutralize.py              # find_vendor_terms(), NeutralLanguageError,
                             # read_skill_variants(), reconcile_skill(), ReconciliationError
  skills.py                  # skill_files(), project_skills(), SkillAction, SkillDriftError
  enroll.py                  # propose_enrollment(), enroll_skill(), update_managed_skills()
  cli.py                     # MODIFY: add `enroll`; fold skills into project/check/status
tests/
  conftest.py                # MODIFY: extend fake_env (references + skill-seeding helper)
  test_neutralize.py         # new
  test_skills.py             # new
  test_enroll.py             # new
  test_cli.py                # MODIFY: enroll command + skills in project
docs/
  threat-models/2026-06-28-capture-promote-surface.md   # stub created here (Task 7)
README.md / AGENTS.md / docs/LIMITATIONS.md             # MODIFY (Task 7)
```

### State shape addition

Plan 1 uses `state["instructions"][runtime] = sha256(content)`. Slice A adds a parallel namespace:

```json
{
  "instructions": { "claude": "…", "codex": "…", "gemini": "…" },
  "skills": {
    "claude": { "config-sync/SKILL.md": "…", "config-sync/references/claude-code-tools.md": "…" },
    "codex":  { "config-sync/SKILL.md": "…", "config-sync/references/codex-tools.md": "…" },
    "gemini": { "config-sync/SKILL.md": "…", "config-sync/references/gemini-tools.md": "…" }
  }
}
```

Each skill file is independently drift-classified by its `"<name>/<relpath>"` key.

---

### Task 1: Seed inputs — tool adapters, overlay fix, fixture extension

**Files:**
- Create: `references/claude-code-tools.md`, `references/codex-tools.md`, `references/gemini-tools.md` (copied from superpowers)
- Modify: `overlays/gemini.md` (remove the incorrect skill-loading line)
- Modify: `tests/conftest.py` (extend `fake_env`)
- Test: `tests/test_skills.py` (new — fixture smoke assertions only in this task)

**Interfaces:**
- Produces: repo `references/<vendor>-tools.md` files (real adapter content, not placeholders).
- Produces: extended `fake_env` with new fields `references: dict[str, str]` (the three adapter filenames it wrote) and `repo` now containing a `references/` dir + a `skills/` dir; plus a `seed_skill(runtime: str, name: str, body: str)` callable that writes `<home>/<dir>/skills/<name>/SKILL.md` to simulate a skill already present in a runtime.

- [ ] **Step 1: Locate the superpowers tool adapters**

These already exist on this machine (HANDOFF §8). Find them:

```bash
ls "$HOME/.claude/plugins/cache/claude-plugins-official/superpowers"/*/skills/using-superpowers/references/
```

Expected: `claude-code-tools.md  codex-tools.md  gemini-tools.md  antigravity-tools.md  copilot-tools.md  pi-tools.md`.

- [ ] **Step 2: Copy the three adapters we manage into `references/`**

Copy verbatim (do not hand-author — these are the canonical, verified adapters). Replace `<VER>` with the version dir found in Step 1:

```bash
mkdir -p references
SP="$HOME/.claude/plugins/cache/claude-plugins-official/superpowers/<VER>/skills/using-superpowers/references"
cp "$SP/claude-code-tools.md" references/claude-code-tools.md
cp "$SP/codex-tools.md"        references/codex-tools.md
cp "$SP/gemini-tools.md"       references/gemini-tools.md
```

If the source path cannot be found, STOP and report — do not fabricate adapter content. The adapter maps neutral skill actions ("dispatch a subagent", "read a file") to each runtime's real tools; inventing it would mis-steer the agent.

- [ ] **Step 3: Fix the wrong line in `overlays/gemini.md`**

HANDOFF §8: the overlay currently tells Gemini to "Load skills with `activate_skill`" — verified WRONG (Gemini auto-discovers a `SKILL.md` file-copy; there is no `activate_skill` tool). Find and remove/correct it:

```bash
grep -n "activate_skill" overlays/gemini.md
```

Replace the offending line with the verified mechanism:

```markdown
Skills are discovered automatically from `~/.gemini/skills/<name>/SKILL.md` (file-copy; no manifest, no `activate_skill` tool). AntiGravity loads a skill by reading its `SKILL.md`.
```

- [ ] **Step 4: Extend the `fake_env` fixture**

In `tests/conftest.py`, after the `targets.yaml` write and before the `return`, add the repo `references/`, a repo `skills/` dir, seed adapter files, and a `seed_skill` helper. Replace the existing `return` block with this:

```python
    refs = {
        "claude": "claude-code-tools.md",
        "codex": "codex-tools.md",
        "gemini": "gemini-tools.md",
    }
    (repo / "references").mkdir()
    (repo / "skills").mkdir()
    for runtime, fname in refs.items():
        (repo / "references" / fname).write_text(
            f"# {runtime} tools adapter\n\nMap neutral actions to {runtime} tools.\n",
            encoding="utf-8",
        )

    dir_for = {"claude": ".claude", "codex": ".codex", "gemini": ".gemini"}

    def seed_skill(runtime: str, name: str, body: str) -> Path:
        dest = home / dir_for[runtime] / "skills" / name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        return dest

    return types.SimpleNamespace(
        repo=repo,
        home=home,
        allowed_roots=[roots[r][0] for r in roots],
        references=refs,
        seed_skill=seed_skill,
    )
```

- [ ] **Step 5: Write the fixture smoke test**

Create `tests/test_skills.py`:

```python
def test_fixture_provides_references_and_skill_seeder(fake_env):
    assert (fake_env.repo / "references" / "claude-code-tools.md").exists()
    assert (fake_env.repo / "references" / "codex-tools.md").exists()
    assert (fake_env.repo / "references" / "gemini-tools.md").exists()
    path = fake_env.seed_skill("gemini", "demo", "# Demo\nbody\n")
    assert path.read_text("utf-8") == "# Demo\nbody\n"
    assert path.parent.name == "demo"
```

- [ ] **Step 6: Run it to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_skills.py -q`
Expected: PASS (and the existing 57 tests still pass: re-run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`).

- [ ] **Step 7: Commit**

```bash
git add references/ overlays/gemini.md tests/conftest.py tests/test_skills.py
git commit -m "feat(skills): seed vendor tool adapters, fix gemini overlay, extend fixture"
```

---

### Task 2: Neutral-language lint

**Files:**
- Create: `src/agent_config_sync/neutralize.py`
- Test: `tests/test_neutralize.py`

**Interfaces:**
- Produces: `find_vendor_terms(text: str) -> list[str]` — returns each hard-coded vendor tool name / slash-command found in a skill body. Empty list ⇒ neutral.
- Produces: `class NeutralLanguageError(Exception)` with `.skill: str` and `.terms: list[str]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_neutralize.py`:

```python
from agent_config_sync.neutralize import find_vendor_terms


def test_flags_claude_skill_tool():
    assert "Skill tool" in find_vendor_terms("Invoke the Skill tool to run it.")


def test_flags_codex_apply_patch():
    assert "apply_patch" in find_vendor_terms("Edit files with apply_patch.")


def test_flags_gemini_activate_skill():
    assert "activate_skill" in find_vendor_terms("Load it with activate_skill.")


def test_flags_slash_command():
    terms = find_vendor_terms("Run /critique before merging.")
    assert any(t.startswith("/") for t in terms)


def test_neutral_body_is_clean():
    body = "Dispatch a subagent to read the file, then report findings."
    assert find_vendor_terms(body) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_neutralize.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_config_sync.neutralize'`.

- [ ] **Step 3: Write the implementation**

Create `src/agent_config_sync/neutralize.py`:

```python
import re

# Hard-coded, per-vendor tool names and invocation forms a *neutral* skill body
# must not contain. Mirrors the deterministic-gate model of secrets.find_secrets:
# AI may PROPOSE a neutral rewrite, but this lint DECIDES whether it is clean.
_VENDOR_TERMS = [
    r"Skill tool",
    r"apply_patch",
    r"activate_skill",
    r"\bStrReplace\b",
    r"functions\.[A-Za-z_]+",
]
_VENDOR_PATTERNS = [re.compile(t) for t in _VENDOR_TERMS]
# A slash-command reference like `/critique` (start of line or after whitespace,
# at least two letters so it does not catch paths like `/x`).
_SLASH = re.compile(r"(?:(?<=\s)|^)(/[a-z][a-z0-9-]{2,})", re.MULTILINE)


class NeutralLanguageError(Exception):
    def __init__(self, skill: str, terms: list[str]):
        self.skill = skill
        self.terms = terms
        super().__init__(f"skill '{skill}' contains vendor-specific terms: {terms}")


def find_vendor_terms(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in _VENDOR_PATTERNS:
        for m in pattern.finditer(text):
            hits.append(m.group(0))
    for m in _SLASH.finditer(text):
        hits.append(m.group(1))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_neutralize.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/neutralize.py tests/test_neutralize.py
git commit -m "feat(neutralize): deterministic vendor-term lint for skill bodies"
```

---

### Task 3: Cross-runtime reconciliation

**Files:**
- Modify: `src/agent_config_sync/neutralize.py`
- Test: `tests/test_neutralize.py`

**Interfaces:**
- Consumes: `Config` (for `runtimes` and each `RuntimeConfig.skills_dest`).
- Produces: `read_skill_variants(config: Config, name: str) -> dict[str, str]` — `{runtime: body}` for every runtime whose `<skills_dest>/<name>/SKILL.md` exists.
- Produces: `reconcile_skill(variants: dict[str, str], canonical: str | None = None) -> str` — returns the agreed body if all variants are byte-identical, or the `canonical` runtime's body if specified; raises `ReconciliationError` if variants differ and no `canonical` given.
- Produces: `class ReconciliationError(Exception)` with `.skill` (set by caller; default `""`) and `.runtimes: list[str]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_neutralize.py`:

```python
import pytest

from agent_config_sync.config import load_config
from agent_config_sync.neutralize import (
    ReconciliationError,
    read_skill_variants,
    reconcile_skill,
)


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_read_variants_finds_seeded_skills(fake_env):
    fake_env.seed_skill("claude", "demo", "# Demo\nbody\n")
    fake_env.seed_skill("gemini", "demo", "# Demo\nbody\n")
    variants = read_skill_variants(_cfg(fake_env), "demo")
    assert set(variants) == {"claude", "gemini"}


def test_reconcile_identical_returns_body():
    assert reconcile_skill({"claude": "x\n", "gemini": "x\n"}) == "x\n"


def test_reconcile_divergent_raises():
    with pytest.raises(ReconciliationError) as exc:
        reconcile_skill({"claude": "a\n", "codex": "b\n"})
    assert set(exc.value.runtimes) == {"claude", "codex"}


def test_reconcile_divergent_with_canonical_picks_it():
    body = reconcile_skill({"claude": "a\n", "codex": "b\n"}, canonical="codex")
    assert body == "b\n"
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_neutralize.py -q`
Expected: FAIL with `ImportError` for `read_skill_variants` / `reconcile_skill` / `ReconciliationError`.

- [ ] **Step 3: Write the implementation**

Append to `src/agent_config_sync/neutralize.py` (add `from .config import Config` at the top with the other imports):

```python
class ReconciliationError(Exception):
    def __init__(self, runtimes: list[str], skill: str = ""):
        self.skill = skill
        self.runtimes = runtimes
        super().__init__(
            f"skill '{skill}' differs across runtimes {runtimes}; "
            "choose a canonical source to enroll"
        )


def read_skill_variants(config: Config, name: str) -> dict[str, str]:
    variants: dict[str, str] = {}
    for runtime, rt in config.runtimes.items():
        path = rt.skills_dest / name / "SKILL.md"
        if path.exists():
            variants[runtime] = path.read_text("utf-8")
    return variants


def reconcile_skill(variants: dict[str, str], canonical: str | None = None) -> str:
    if not variants:
        raise ReconciliationError([], "")
    if canonical is not None:
        return variants[canonical]
    bodies = set(variants.values())
    if len(bodies) == 1:
        return next(iter(bodies))
    raise ReconciliationError(sorted(variants.keys()))
```

Put `from .config import Config` alongside `import re` at the top of the file.

- [ ] **Step 4: Run to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_neutralize.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/neutralize.py tests/test_neutralize.py
git commit -m "feat(neutralize): cross-runtime skill reconciliation"
```

---

### Task 4: Skill projection engine

**Files:**
- Create: `src/agent_config_sync/skills.py`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `Config`; `find_secrets`/`SecretFoundError`; `fsutil.atomic_write`/`backup`/`sha256_text`/`default_stamp`; `state.load_state`/`save_state`; `audit.append_audit`. Mirrors `project.project` structure.
- Produces: `REFERENCE_FILENAMES: dict[str, str]` mapping `runtime -> adapter filename` (`{"claude": "claude-code-tools.md", "codex": "codex-tools.md", "gemini": "gemini-tools.md"}`).
- Produces: `skill_files(config, runtime, name) -> dict[str, str]` — `{relpath: content}` for one skill×runtime: `"SKILL.md"` (canonical body) and `"references/<vendor>-tools.md"` (adapter from repo `references/`).
- Produces: `@dataclass SkillAction { runtime: str; name: str; relpath: str; kind: str; dest: Path; content: str }`.
- Produces: `project_skills(config, *, dry_run=False, force=False, stamp=None, only=None) -> list[SkillAction]` — projects every `managed_skills` entry into every (or `only`) runtime; reuses Plan 1's `_classify` semantics (`create`/`unchanged`/`update`/`drift`/`forced`).
- Produces: `class SkillDriftError(Exception)` with `.items: list[str]` (each `"<runtime>:<name>/<relpath>"`).

- [ ] **Step 1: Write the failing goal test**

Append to `tests/test_skills.py`:

```python
import pytest

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill  # used to register canonical body
from agent_config_sync.skills import SkillDriftError, project_skills


NEUTRAL = "---\nname: demo\ndescription: demo skill\n---\n\nDispatch a subagent.\n"


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def _enroll_demo(fake_env):
    # Canonical body written to skills/demo/SKILL.md + managed_skills updated.
    (fake_env.repo / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    (fake_env.repo / "skills" / "demo" / "SKILL.md").write_text(NEUTRAL, "utf-8")
    enroll_skill(_cfg(fake_env), "demo", NEUTRAL)


def test_project_skills_writes_body_and_adapter_per_runtime(fake_env):
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)  # reload: managed_skills now contains "demo"
    project_skills(cfg)
    for runtime, fname in (
        ("claude", "claude-code-tools.md"),
        ("codex", "codex-tools.md"),
        ("gemini", "gemini-tools.md"),
    ):
        base = cfg.runtimes[runtime].skills_dest / "demo"
        assert (base / "SKILL.md").read_text("utf-8") == NEUTRAL
        assert (base / "references" / fname).exists()


def test_project_skills_is_idempotent(fake_env):
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)
    project_skills(cfg)
    actions = project_skills(cfg)
    assert all(a.kind == "unchanged" for a in actions)


def test_project_skills_refuses_unpromoted_drift(fake_env):
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)
    project_skills(cfg)
    edited = cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md"
    edited.write_text(NEUTRAL + "\nHAND EDIT\n", "utf-8")
    with pytest.raises(SkillDriftError) as exc:
        project_skills(cfg)
    assert "claude:demo/SKILL.md" in exc.value.items
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_skills.py -q`
Expected: FAIL (`No module named 'agent_config_sync.skills'` / `enroll`).

- [ ] **Step 3: Write the implementation**

Create `src/agent_config_sync/skills.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from .audit import append_audit
from .config import Config
from .fsutil import atomic_write, backup, default_stamp, sha256_text
from .secrets import SecretFoundError, find_secrets
from .state import load_state, save_state

REFERENCE_FILENAMES = {
    "claude": "claude-code-tools.md",
    "codex": "codex-tools.md",
    "gemini": "gemini-tools.md",
}


class SkillDriftError(Exception):
    def __init__(self, items: list[str]):
        self.items = items
        super().__init__(f"un-promoted skill edits in: {', '.join(items)}")


@dataclass
class SkillAction:
    runtime: str
    name: str
    relpath: str
    kind: str
    dest: Path
    content: str


def skill_files(config: Config, runtime: str, name: str) -> dict[str, str]:
    body = (config.repo_root / "skills" / name / "SKILL.md").read_text("utf-8")
    adapter_name = REFERENCE_FILENAMES[runtime]
    adapter = (config.repo_root / "references" / adapter_name).read_text("utf-8")
    return {
        "SKILL.md": body,
        f"references/{adapter_name}": adapter,
    }


def _classify(content: str, dest: Path, last_hash: str | None, force: bool) -> str:
    if not dest.exists():
        return "create"
    current = dest.read_text("utf-8")
    if current == content:
        return "unchanged"
    if last_hash is not None and sha256_text(current) == last_hash:
        return "update"
    return "forced" if force else "drift"


def project_skills(
    config: Config,
    *,
    dry_run: bool = False,
    force: bool = False,
    stamp: str | None = None,
    only: str | None = None,
) -> list[SkillAction]:
    if only is not None and only not in config.runtimes:
        raise ValueError(f"unknown runtime '{only}'")
    selected = (
        {only: config.runtimes[only]} if only is not None else config.runtimes
    )

    state = load_state(config.repo_root)
    skill_state = state.setdefault("skills", {})

    plan: list[SkillAction] = []
    for runtime in selected:
        rt = config.runtimes[runtime]
        rt_state = skill_state.setdefault(runtime, {})
        for name in config.managed_skills:
            for relpath, content in skill_files(config, runtime, name).items():
                matches = find_secrets(content)
                if matches:
                    raise SecretFoundError(runtime, matches)
                key = f"{name}/{relpath}"
                dest = rt.skills_dest / name / relpath
                kind = _classify(content, dest, rt_state.get(key), force)
                plan.append(SkillAction(runtime, name, relpath, kind, dest, content))

    drifted = [
        f"{a.runtime}:{a.name}/{a.relpath}" for a in plan if a.kind == "drift"
    ]
    if drifted and not dry_run:
        raise SkillDriftError(drifted)
    if dry_run:
        return plan

    stamp = stamp or default_stamp()
    backup_root = config.repo_root / ".backups"
    for action in plan:
        if action.kind in ("unchanged", "drift"):
            continue
        if action.dest.exists():
            backup(action.dest, backup_root, action.runtime, stamp)
        atomic_write(action.dest, action.content)
        content_hash = sha256_text(action.content)
        skill_state[action.runtime][f"{action.name}/{action.relpath}"] = content_hash
        save_state(config.repo_root, state)
        append_audit(
            config.repo_root,
            {
                "stamp": stamp,
                "runtime": action.runtime,
                "kind": action.kind,
                "force": force,
                "dest": str(action.dest),
                "skill": action.name,
                "relpath": action.relpath,
                "content_sha256": content_hash,
            },
        )

    save_state(config.repo_root, state)
    return plan
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_skills.py -q`
Expected: PASS (depends on Task 5's `enroll_skill`; if running tasks strictly in order, the import fails — implement Task 5 then re-run, or temporarily stub `_enroll_demo` to write `managed_skills` directly. Recommended: treat Tasks 4–5 as a pair and run their tests together after both land).

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/skills.py tests/test_skills.py
git commit -m "feat(skills): project managed skills (body + adapter) with drift guard"
```

---

### Task 5: Enrollment flow

**Files:**
- Create: `src/agent_config_sync/enroll.py`
- Test: `tests/test_enroll.py`

**Interfaces:**
- Consumes: `Config`; `neutralize.find_vendor_terms`/`NeutralLanguageError`/`read_skill_variants`/`reconcile_skill`/`ReconciliationError`; `secrets.find_secrets`/`SecretFoundError`; `fsutil.atomic_write`.
- Produces: `propose_enrollment(config, name, canonical=None) -> str` — derives the starting body from the runtime variants via `read_skill_variants` + `reconcile_skill` (raises `ReconciliationError` on divergence with no `canonical`). This is the body an AI neutralizes and a human reviews; it is NOT yet written to source.
- Produces: `enroll_skill(config, name, body) -> None` — the binding gate: `find_vendor_terms(body)` must be empty (else `NeutralLanguageError`) and `find_secrets(body)` must be empty (else `SecretFoundError`); then writes `skills/<name>/SKILL.md` and adds `name` to `managed_skills` in `targets.yaml` (deduped, sorted).
- Produces: `update_managed_skills(targets_path: Path, names: list[str]) -> None` — rewrites the trailing `managed_skills:` block textually, preserving all preceding content and comments. Relies on the Global Constraint that `managed_skills` is the last top-level key.

- [ ] **Step 1: Write the failing test**

Create `tests/test_enroll.py`:

```python
import pytest

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill, propose_enrollment
from agent_config_sync.neutralize import NeutralLanguageError, ReconciliationError
from agent_config_sync.secrets import SecretFoundError

NEUTRAL = "---\nname: demo\ndescription: d\n---\n\nDispatch a subagent.\n"


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_enroll_writes_canonical_and_updates_managed(fake_env):
    cfg = _cfg(fake_env)
    enroll_skill(cfg, "demo", NEUTRAL)
    assert (fake_env.repo / "skills" / "demo" / "SKILL.md").read_text("utf-8") == NEUTRAL
    reloaded = _cfg(fake_env)
    assert "demo" in reloaded.managed_skills


def test_enroll_preserves_targets_comments(fake_env):
    enroll_skill(_cfg(fake_env), "demo", NEUTRAL)
    text = (fake_env.repo / "config" / "targets.yaml").read_text("utf-8")
    assert "runtimes:" in text  # preceding content intact


def test_enroll_rejects_non_neutral_body(fake_env):
    with pytest.raises(NeutralLanguageError):
        enroll_skill(_cfg(fake_env), "bad", NEUTRAL + "\nUse the Skill tool.\n")


def test_enroll_rejects_secret(fake_env):
    body = NEUTRAL + '\napi_key = "abcd1234efgh5678"\n'
    with pytest.raises(SecretFoundError):
        enroll_skill(_cfg(fake_env), "leaky", body)


def test_propose_divergent_variants_raises(fake_env):
    fake_env.seed_skill("claude", "demo", "a\n")
    fake_env.seed_skill("codex", "demo", "b\n")
    with pytest.raises(ReconciliationError):
        propose_enrollment(_cfg(fake_env), "demo")


def test_propose_identical_variants_returns_body(fake_env):
    fake_env.seed_skill("claude", "demo", "x\n")
    fake_env.seed_skill("gemini", "demo", "x\n")
    assert propose_enrollment(_cfg(fake_env), "demo") == "x\n"
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_enroll.py -q`
Expected: FAIL (`No module named 'agent_config_sync.enroll'`).

- [ ] **Step 3: Write the implementation**

Create `src/agent_config_sync/enroll.py`:

```python
from pathlib import Path

from .config import Config
from .fsutil import atomic_write
from .neutralize import (
    NeutralLanguageError,
    find_vendor_terms,
    read_skill_variants,
    reconcile_skill,
)
from .secrets import SecretFoundError, find_secrets


def propose_enrollment(config: Config, name: str, canonical: str | None = None) -> str:
    variants = read_skill_variants(config, name)
    return reconcile_skill(variants, canonical=canonical)


def update_managed_skills(targets_path: Path, names: list[str]) -> None:
    text = targets_path.read_text("utf-8")
    marker = "\nmanaged_skills:"
    idx = text.find(marker)
    head = text[: idx + 1] if idx != -1 else (text if text.endswith("\n") else text + "\n")
    ordered = sorted(set(names))
    if ordered:
        block = "managed_skills:\n" + "".join(f"  - {n}\n" for n in ordered)
    else:
        block = "managed_skills: []\n"
    atomic_write(targets_path, head + block)


def enroll_skill(config: Config, name: str, body: str) -> None:
    terms = find_vendor_terms(body)
    if terms:
        raise NeutralLanguageError(name, terms)
    secrets = find_secrets(body)
    if secrets:
        raise SecretFoundError(name, secrets)

    canonical = config.repo_root / "skills" / name / "SKILL.md"
    atomic_write(canonical, body)
    update_managed_skills(
        config.repo_root / "config" / "targets.yaml",
        [*config.managed_skills, name],
    )
```

Note: `update_managed_skills` keeps everything up to and including the newline before `managed_skills:` (preserving the header comment block above the key), then rewrites the trailing list. The `marker` begins with `\n` so it matches the key only at line start, never a comment substring.

- [ ] **Step 4: Run to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_enroll.py tests/test_skills.py -q`
Expected: PASS (both Task 4 and Task 5 suites green together).

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/enroll.py tests/test_enroll.py
git commit -m "feat(enroll): neutral+secret-gated skill enrollment, comment-safe targets update"
```

---

### Task 6: CLI wiring — `enroll`, and skills folded into `project`/`check`/`status`

**Files:**
- Modify: `src/agent_config_sync/cli.py`
- Modify: `src/agent_config_sync/check.py`, `src/agent_config_sync/status.py` (read the current signatures first; extend to also report skill drift)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `project_skills`, `SkillDriftError` (skills.py); `enroll_skill`, `propose_enrollment` (enroll.py).
- Produces: `agent-config-sync enroll <name> [--from <runtime>]` — runs `propose_enrollment` (printing the proposed body + any vendor terms it would need neutralized), then on a body supplied via `--body-file <path>` runs `enroll_skill`. (Interactive AI-neutralization is Slice C; here `enroll` either prints the proposal or, with `--body-file`, commits a human-prepared neutral body.)
- Produces: `project` and `check` now also act on skills. Exit codes unchanged: `0` clean, `1` drift/stale, `2` secret, `3` config error, `4` force-scope (reuse Plan 1's mapping).

> Read `cli.py`, `check.py`, `status.py` first — wire skills in following their existing dispatch and exit-code patterns rather than the sketch below. The sketch shows intent, not verbatim lines.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py` (match its existing import/helpers style):

```python
def test_cli_enroll_then_project_writes_skill(fake_env, monkeypatch):
    monkeypatch.setenv("AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
                       os.pathsep.join(str(p) for p in fake_env.allowed_roots))
    body = "---\nname: demo\ndescription: d\n---\n\nDispatch a subagent.\n"
    (fake_env.repo / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    body_file = fake_env.repo / "demo-body.md"
    body_file.write_text(body, "utf-8")
    from agent_config_sync.cli import main
    rc = main(["enroll", "demo", "--body-file", str(body_file),
               "--repo", str(fake_env.repo)])
    assert rc == 0
    rc = main(["project", "--repo", str(fake_env.repo)])
    assert rc == 0
    assert (fake_env.repo and
            (load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
             .runtimes["claude"].skills_dest / "demo" / "SKILL.md").exists())
```

(Adapt `--repo` / arg names to whatever `cli.py` already uses; if `cli.main` resolves the repo differently, follow that — do not invent a `--repo` flag that doesn't fit the existing parser.)

- [ ] **Step 2: Run to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_cli.py -q`
Expected: FAIL (unknown `enroll` command).

- [ ] **Step 3: Implement the wiring**

In `cli.py`: add an `enroll` subparser (`name` positional, `--from` optional runtime, `--body-file` optional path). When `--body-file` is given, read it and call `enroll_skill`; else print `propose_enrollment` output and the vendor terms `find_vendor_terms` reports. In the `project` handler, after the existing `project(...)` call, also call `project_skills(...)` with the same `dry_run`/`force`/`only`; map `SkillDriftError` to exit `1` and `SecretFoundError` to exit `2`, consistent with the instruction-file mapping. In `check`, treat skill drift as stale (exit `1`). Keep one shared error-to-exit-code mapping.

- [ ] **Step 4: Run to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS (full suite — Slice A green end to end).

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/cli.py src/agent_config_sync/check.py src/agent_config_sync/status.py tests/test_cli.py
git commit -m "feat(cli): enroll command; project/check/status cover managed skills"
```

---

### Task 7: Durability setup, docs, and threat-model stub

**Files:**
- Create: `docs/threat-models/2026-06-28-capture-promote-surface.md` (stub; completed when Slice C lands)
- Modify: `README.md`, `AGENTS.md`, `docs/LIMITATIONS.md`
- Create: `docs/INSTALLATION.md` section or `SETUP_REMOTE.md` note for the private remote

**Interfaces:** none (docs + setup).

- [ ] **Step 1: Document the private-remote setup (owner decision #4 = fold in)**

Add a "Durability / off-machine backup" section to `README.md` (or `docs/INSTALLATION.md`) with the exact commands. This step REQUIRES the owner's GitHub auth — it cannot be run blind; present it for the owner to execute:

```bash
# Create a PRIVATE remote (owner runs this; requires gh auth).
gh repo create agent-config-sync --private --source=. --remote=origin --push
# Thereafter, capture/project push automatically when 'origin' exists (Slice C).
```

If `gh` is unauthenticated, STOP and report — do not create a public repo (the source carries the owner's full standards; a public push is a disclosure). Document the no-remote state as a hard limitation until this runs.

- [ ] **Step 2: Update LIMITATIONS and AGENTS**

In `docs/LIMITATIONS.md`, add: skills are projected as file copies (no symlink); `managed_skills` must stay the last key in `targets.yaml`; Slice A does not yet do startup discovery/capture (Slices B/C); 3-way skill merge is out of scope. In `AGENTS.md`, document `enroll` and that skills are now managed artifacts (edit `skills/<name>/SKILL.md`, then `project`).

- [ ] **Step 3: Create the threat-model stub**

Create `docs/threat-models/2026-06-28-capture-promote-surface.md` with the assets/trust-boundary skeleton and a TODO that it is completed before Slice C (capture) is considered hardened. The poisoned-skill-body fan-out is the headline threat; the neutral-language lint + secret-lint + human review are the mapped controls (`neutralize.find_vendor_terms`, `secrets.find_secrets`).

- [ ] **Step 4: Run the full suite once more**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/ README.md AGENTS.md
git commit -m "docs(skills): enroll/project usage, remote durability, capture/promote threat-model stub"
```

---

## Self-Review

**Spec coverage (Plan 2 design §5.2 + §7 "A" items):**
- A goal test (body + correct adapter per runtime) → Task 4 Step 1 `test_project_skills_writes_body_and_adapter_per_runtime`. ✅
- A reconciliation should-fail → Task 5 `test_propose_divergent_variants_raises`. ✅
- A neutral-language lint should-fail → Task 5 `test_enroll_rejects_non_neutral_body` + Task 2 suite. ✅
- Idempotency / drift refusal → Task 4 `test_project_skills_is_idempotent`, `test_project_skills_refuses_unpromoted_drift`. ✅
- Secret abort on skill content → Task 5 `test_enroll_rejects_secret` (enrollment) + `project_skills` secret gate (engine). ✅
- `gemini.md` activate_skill fix → Task 1 Step 3. ✅
- `managed_skills` enrollment + corrected adapters → Tasks 1, 5. ✅
- Durability/remote (owner decision #4) → Task 7 Step 1. ✅

**Out of this slice (separate plans):** discovery section + `config-sync` skill + startup hooks (Slice B); capture-from-chat + `doctor` + AI advisory review + settings.json hook wiring (Slice C); reverse `promote` (Plan 3). Slice A delivers working, tested skills projection + enrollment on its own.

**Placeholder scan:** no TBD/TODO-in-code; every code step shows complete code. The two intentional "follow the existing signatures" notes (Task 6 CLI/check/status) are because those files must be read live — the sketch states the exact behavior and exit-code mapping, not a vague "wire it up."

**Type consistency:** `find_vendor_terms`, `read_skill_variants`, `reconcile_skill`, `NeutralLanguageError`, `ReconciliationError`, `SkillAction`, `SkillDriftError`, `project_skills`, `skill_files`, `REFERENCE_FILENAMES`, `propose_enrollment`, `enroll_skill`, `update_managed_skills` — names are identical across the tasks that define and consume them. State namespace `state["skills"][runtime]["<name>/<relpath>"]` is consistent between Task 4's engine and the documented state shape.

**Known cross-task ordering note:** Task 4's tests import `enroll_skill` (Task 5). Implement Tasks 4 and 5 as a pair and run their suites together (called out in Task 4 Step 4). All other tasks are independently green.
