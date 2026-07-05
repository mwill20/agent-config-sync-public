# agent-config-sync — Plan 1: Forward Projection (instruction files)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python CLI that projects a neutral source (`_shared/core.md` + per-vendor overlays) into each runtime's instruction file (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`), safely and idempotently, with a stale-check used by a pre-commit hook.

**Architecture:** A single source of truth lives in this repo. Pure functions render derived content (`render`); a thin command layer (`project`, `check`, `status`) reads source files, computes projected content, and writes only to allowlisted destinations using atomic writes + backups. A JSON state file records the hash of the last content written per runtime, so the tool can tell "source moved ahead" (safe to overwrite) from "someone hand-edited the derived file" (refuse without `--force`).

**Tech Stack:** Python 3.11+, stdlib (`argparse`, `pathlib`, `hashlib`, `difflib`, `json`, `re`, `shutil`, `os`, `datetime`), `pyyaml==6.0.2`; tests with `pytest==8.3.4`.

## Global Constraints

- Python floor: **3.11** (uses `Path.is_relative_to`, `X | None` types).
- Dependencies pinned exactly: runtime `pyyaml==6.0.2`; dev `pytest==8.3.4`. No other third-party deps.
- **Allowlist writes only:** the tool may write solely to paths that resolve under a declared runtime root (`~/.claude`, `~/.codex`, `~/.gemini`). Any other destination is a hard error.
- **No secrets written:** projected content is scanned for credential patterns and the run aborts before any write if a match is found.
- **Atomic writes only:** every file write goes through a temp-file + `os.replace`.
- **Determinism:** timestamps and allowed-roots are injectable so tests are hermetic. No wall-clock or real `$HOME` reads inside testable functions.
- All files UTF-8, LF newlines.
- Package import name: `agent_config_sync`. CLI module: `python -m agent_config_sync`. Console script: `agent-config-sync`.

---

## File Structure

```
pyproject.toml                       # build + deps + console script + pytest config
config/targets.yaml                  # allowlist: runtimes, dest paths, overlays, managed skills
_shared/core.md                      # neutral source (seed content)
overlays/{claude,codex,gemini}.md    # per-vendor source
src/agent_config_sync/
  __init__.py
  render.py     # GENERATED_HEADER, render(core, overlay)
  secrets.py    # SECRET_PATTERNS, find_secrets(), SecretFoundError
  fsutil.py     # atomic_write(), backup(), sha256_text(), default_stamp()
  state.py      # load_state(), save_state()  -> .sync-state.json
  config.py     # Config/RuntimeConfig, load_config(), ConfigError, DEFAULT_ALLOWED_ROOTS
  project.py    # ProjectAction, project(), DriftError, projected_for()
  check.py      # check()
  status.py     # status()
  cli.py        # main(argv) dispatch
tests/
  conftest.py   # fake_env fixture (hermetic repo + fake home)
  test_render.py test_secrets.py test_fsutil.py test_state.py
  test_config.py test_project.py test_check.py test_cli.py
hooks/pre-commit
```

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/agent_config_sync/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces: the `fake_env` pytest fixture returning a `types.SimpleNamespace` with fields `repo: Path`, `home: Path`, `allowed_roots: list[Path]`. Source files (`_shared/core.md`, `overlays/*.md`, `config/targets.yaml`) are pre-written under `repo`; runtime dirs (`.claude/.codex/.gemini`) exist empty under `home`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-config-sync"
version = "0.1.0"
description = "Vendor-neutral source of truth that projects AI runtime config across Claude Code, Codex, and Gemini/AntiGravity."
requires-python = ">=3.11"
dependencies = ["pyyaml==6.0.2"]

[project.optional-dependencies]
dev = ["pytest==8.3.4"]

[project.scripts]
agent-config-sync = "agent_config_sync.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create the package marker**

`src/agent_config_sync/__init__.py`:

```python
"""agent-config-sync: project a neutral source of truth to AI runtime config."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create the hermetic `fake_env` fixture**

`tests/conftest.py`:

```python
import textwrap
import types
from pathlib import Path

import pytest

CORE = "# Core Standards\n\nSecurity is the foundation.\n"
OVERLAYS = {
    "claude": "## Claude\n\nUse the Skill tool to invoke skills.\n",
    "codex": "## Codex\n\nUse apply_patch for file edits.\n",
    "gemini": "## Gemini\n\nUse activate_skill to load skills.\n",
}


@pytest.fixture
def fake_env(tmp_path: Path):
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    for sub in ("_shared", "overlays", "config"):
        (repo / sub).mkdir(parents=True)
    (repo / "_shared" / "core.md").write_text(CORE, encoding="utf-8")
    for name, text in OVERLAYS.items():
        (repo / "overlays" / f"{name}.md").write_text(text, encoding="utf-8")

    roots = {}
    for runtime, dirname, filename in (
        ("claude", ".claude", "CLAUDE.md"),
        ("codex", ".codex", "AGENTS.md"),
        ("gemini", ".gemini", "GEMINI.md"),
    ):
        root = home / dirname
        root.mkdir(parents=True)
        roots[runtime] = (root, filename)

    targets = textwrap.dedent(f"""
        runtimes:
          claude:
            instruction_dest: "{(roots['claude'][0] / 'CLAUDE.md').as_posix()}"
            overlay: "overlays/claude.md"
            skills_dest: "{(roots['claude'][0] / 'skills').as_posix()}"
          codex:
            instruction_dest: "{(roots['codex'][0] / 'AGENTS.md').as_posix()}"
            overlay: "overlays/codex.md"
            skills_dest: "{(roots['codex'][0] / 'skills').as_posix()}"
          gemini:
            instruction_dest: "{(roots['gemini'][0] / 'GEMINI.md').as_posix()}"
            overlay: "overlays/gemini.md"
            skills_dest: "{(roots['gemini'][0] / 'skills').as_posix()}"
        managed_skills: []
    """).lstrip()
    (repo / "config" / "targets.yaml").write_text(targets, encoding="utf-8")

    return types.SimpleNamespace(
        repo=repo,
        home=home,
        allowed_roots=[roots[r][0] for r in roots],
    )
```

- [ ] **Step 4: Write a smoke test**

`tests/test_smoke.py`:

```python
def test_package_imports():
    import agent_config_sync

    assert agent_config_sync.__version__ == "0.1.0"


def test_fake_env_has_sources(fake_env):
    assert (fake_env.repo / "_shared" / "core.md").exists()
    assert (fake_env.repo / "config" / "targets.yaml").exists()
    assert len(fake_env.allowed_roots) == 3
```

- [ ] **Step 5: Install dev deps and run**

Run: `python -m pip install -e ".[dev]"` then `pytest -q`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/agent_config_sync/__init__.py tests/conftest.py tests/test_smoke.py
git commit -m "chore: scaffold package, pytest config, and hermetic fake_env fixture"
```

---

### Task 2: Render pure function

**Files:**
- Create: `src/agent_config_sync/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Produces: `GENERATED_HEADER: str`; `render(core_text: str, overlay_text: str) -> str`. Output is `header + blank line + core + blank line + overlay` (overlay omitted if blank), always ending in a single trailing newline.

- [ ] **Step 1: Write the failing test**

`tests/test_render.py`:

```python
from agent_config_sync.render import GENERATED_HEADER, render


def test_render_combines_header_core_overlay():
    out = render("# Core\nBody.\n", "## Vendor\nExtra.\n")
    assert out.startswith(GENERATED_HEADER.rstrip("\n"))
    assert "# Core\nBody." in out
    assert "## Vendor\nExtra." in out
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_render_omits_empty_overlay():
    out = render("# Core\nBody.\n", "   \n")
    assert "Body." in out
    # only header + core, no dangling vendor section separator beyond one blank line
    assert out.count("\n\n") == 1  # one separator between header and core


def test_render_is_deterministic():
    a = render("c", "o")
    b = render("c", "o")
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_config_sync.render'`.

- [ ] **Step 3: Write minimal implementation**

`src/agent_config_sync/render.py`:

```python
GENERATED_HEADER = (
    "<!-- GENERATED by agent-config-sync. DO NOT EDIT HERE.\n"
    "     Edit _shared/core.md or overlays/<vendor>.md in the agent-config-sync repo,\n"
    "     then run `agent-config-sync project`. To pull a change made here back into\n"
    "     the source, run `agent-config-sync promote <runtime>`. -->\n"
)


def render(core_text: str, overlay_text: str) -> str:
    parts = [GENERATED_HEADER.rstrip("\n"), core_text.strip("\n")]
    if overlay_text.strip():
        parts.append(overlay_text.strip("\n"))
    return "\n\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_render.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/render.py tests/test_render.py
git commit -m "feat: render() composes header + core + overlay deterministically"
```

---

### Task 3: Secret lint

**Files:**
- Create: `src/agent_config_sync/secrets.py`
- Test: `tests/test_secrets.py`

**Interfaces:**
- Produces: `find_secrets(text: str) -> list[str]` (list of matched secret substrings, empty if none); `class SecretFoundError(Exception)` with attributes `runtime: str` and `matches: list[str]`.

- [ ] **Step 1: Write the failing test (includes should-fail / detection case)**

`tests/test_secrets.py`:

```python
from agent_config_sync.secrets import SecretFoundError, find_secrets


def test_clean_text_has_no_secrets():
    assert find_secrets("# Just docs\nNo credentials here.\n") == []


def test_detects_anthropic_key():
    hits = find_secrets("token: sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA")
    assert hits


def test_detects_aws_access_key():
    assert find_secrets("AKIAIOSFODNN7EXAMPLE")


def test_detects_generic_assignment():
    assert find_secrets('api_key = "supersecretvalue123"')


def test_secret_found_error_carries_context():
    err = SecretFoundError("gemini", ["sk-ant-xxx"])
    assert err.runtime == "gemini"
    assert err.matches == ["sk-ant-xxx"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_secrets.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`src/agent_config_sync/secrets.py`:

```python
import re

SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(
        r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    ),
]


class SecretFoundError(Exception):
    def __init__(self, runtime: str, matches: list[str]):
        self.runtime = runtime
        self.matches = matches
        super().__init__(f"secret-like content for runtime '{runtime}'")


def find_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            hits.append(match.group(0))
    return hits
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_secrets.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/secrets.py tests/test_secrets.py
git commit -m "feat: secret lint with credential pattern detection"
```

---

### Task 4: Filesystem utilities (atomic write, backup, hash, stamp)

**Files:**
- Create: `src/agent_config_sync/fsutil.py`
- Test: `tests/test_fsutil.py`

**Interfaces:**
- Produces:
  - `atomic_write(path: Path, content: str) -> None` (creates parent dirs; temp + `os.replace`)
  - `backup(path: Path, backup_root: Path, runtime: str, stamp: str) -> Path | None` (copies existing file to `backup_root/runtime/stamp/<name>`; returns dest, or `None` if source missing)
  - `sha256_text(text: str) -> str`
  - `default_stamp() -> str` (UTC `YYYYMMDDTHHMMSS`)

- [ ] **Step 1: Write the failing test**

`tests/test_fsutil.py`:

```python
from pathlib import Path

from agent_config_sync.fsutil import atomic_write, backup, default_stamp, sha256_text


def test_atomic_write_creates_dirs_and_content(tmp_path: Path):
    target = tmp_path / "a" / "b" / "file.md"
    atomic_write(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert not list(target.parent.glob("*.tmp"))


def test_atomic_write_overwrites(tmp_path: Path):
    target = tmp_path / "file.md"
    atomic_write(target, "one\n")
    atomic_write(target, "two\n")
    assert target.read_text(encoding="utf-8") == "two\n"


def test_backup_copies_existing(tmp_path: Path):
    src = tmp_path / "CLAUDE.md"
    src.write_text("orig\n", encoding="utf-8")
    dest = backup(src, tmp_path / ".backups", "claude", "20260627T120000")
    assert dest is not None
    assert dest.read_text(encoding="utf-8") == "orig\n"
    assert dest == tmp_path / ".backups" / "claude" / "20260627T120000" / "CLAUDE.md"


def test_backup_returns_none_when_missing(tmp_path: Path):
    assert backup(tmp_path / "nope.md", tmp_path / ".backups", "claude", "s") is None


def test_sha256_is_stable():
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abd")


def test_default_stamp_format():
    stamp = default_stamp()
    assert len(stamp) == 15 and stamp[8] == "T"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fsutil.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`src/agent_config_sync/fsutil.py`:

```python
import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def backup(path: Path, backup_root: Path, runtime: str, stamp: str) -> Path | None:
    if not path.exists():
        return None
    dest = backup_root / runtime / stamp / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fsutil.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/fsutil.py tests/test_fsutil.py
git commit -m "feat: atomic_write, backup, sha256_text, default_stamp"
```

---

### Task 5: State file (last-projected hashes)

**Files:**
- Create: `src/agent_config_sync/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `load_state(repo_root: Path) -> dict` (returns `{}` if `.sync-state.json` absent); `save_state(repo_root: Path, state: dict) -> None`. State shape: `{"instructions": {"<runtime>": "<sha256>"}}`.

- [ ] **Step 1: Write the failing test**

`tests/test_state.py`:

```python
from pathlib import Path

from agent_config_sync.state import load_state, save_state


def test_load_missing_returns_empty(tmp_path: Path):
    assert load_state(tmp_path) == {}


def test_save_then_load_roundtrip(tmp_path: Path):
    save_state(tmp_path, {"instructions": {"claude": "abc"}})
    assert load_state(tmp_path) == {"instructions": {"claude": "abc"}}
    assert (tmp_path / ".sync-state.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`src/agent_config_sync/state.py`:

```python
import json
from pathlib import Path

STATE_FILE = ".sync-state.json"


def load_state(repo_root: Path) -> dict:
    path = repo_root / STATE_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(repo_root: Path, state: dict) -> None:
    path = repo_root / STATE_FILE
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/state.py tests/test_state.py
git commit -m "feat: .sync-state.json load/save for last-projected hashes"
```

---

### Task 6: Config loader with allowlist validation

**Files:**
- Create: `src/agent_config_sync/config.py`
- Create: `config/targets.yaml` (the real, committed manifest)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `pyyaml`.
- Produces:
  - `class ConfigError(Exception)`
  - `RuntimeConfig` dataclass: `name: str`, `instruction_dest: Path`, `overlay: Path` (absolute, repo-relative resolved), `skills_dest: Path`
  - `Config` dataclass: `repo_root: Path`, `runtimes: dict[str, RuntimeConfig]`, `managed_skills: list[str]`
  - `DEFAULT_ALLOWED_ROOTS: list[Path]`
  - `load_config(repo_root: Path, allowed_roots: list[Path] | None = None) -> Config`. When `allowed_roots` is `None`, read `AGENT_CONFIG_SYNC_ALLOWED_ROOTS` (os.pathsep-separated) or fall back to `DEFAULT_ALLOWED_ROOTS`. Every `instruction_dest`/`skills_dest` must resolve under an allowed root or `ConfigError` is raised.

- [ ] **Step 1: Write the failing test (includes should-fail allowlist case)**

`tests/test_config.py`:

```python
import textwrap

import pytest

from agent_config_sync.config import ConfigError, load_config


def test_load_config_parses_runtimes(fake_env):
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    assert set(cfg.runtimes) == {"claude", "codex", "gemini"}
    claude = cfg.runtimes["claude"]
    assert claude.instruction_dest.name == "CLAUDE.md"
    assert claude.overlay == fake_env.repo / "overlays" / "claude.md"
    assert cfg.managed_skills == []


def test_rejects_dest_outside_allowlist(fake_env):
    evil = textwrap.dedent("""
        runtimes:
          claude:
            instruction_dest: "/etc/passwd"
            overlay: "overlays/claude.md"
            skills_dest: "/tmp/skills"
        managed_skills: []
    """).lstrip()
    (fake_env.repo / "config" / "targets.yaml").write_text(evil, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`src/agent_config_sync/config.py`:

```python
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_ALLOWED_ROOTS = [
    Path.home() / ".claude",
    Path.home() / ".codex",
    Path.home() / ".gemini",
]


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    name: str
    instruction_dest: Path
    overlay: Path
    skills_dest: Path


@dataclass(frozen=True)
class Config:
    repo_root: Path
    runtimes: dict[str, "RuntimeConfig"]
    managed_skills: list[str]


def _resolve_allowed(allowed_roots: list[Path] | None) -> list[Path]:
    if allowed_roots is not None:
        roots = allowed_roots
    else:
        env = os.environ.get("AGENT_CONFIG_SYNC_ALLOWED_ROOTS")
        roots = [Path(p) for p in env.split(os.pathsep)] if env else DEFAULT_ALLOWED_ROOTS
    return [Path(r).expanduser().resolve() for r in roots]


def _validate_dest(raw: str, allowed: list[Path]) -> Path:
    resolved = Path(raw).expanduser().resolve()
    for root in allowed:
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    raise ConfigError(f"Destination '{resolved}' is not under an allowed runtime root")


def load_config(repo_root: Path, allowed_roots: list[Path] | None = None) -> Config:
    allowed = _resolve_allowed(allowed_roots)
    raw = yaml.safe_load((repo_root / "config" / "targets.yaml").read_text("utf-8"))
    if not raw or "runtimes" not in raw:
        raise ConfigError("targets.yaml missing 'runtimes'")

    runtimes: dict[str, RuntimeConfig] = {}
    for name, entry in raw["runtimes"].items():
        try:
            instruction = entry["instruction_dest"]
            overlay = entry["overlay"]
            skills = entry["skills_dest"]
        except (KeyError, TypeError) as exc:
            raise ConfigError(f"runtime '{name}' missing required key: {exc}")
        runtimes[name] = RuntimeConfig(
            name=name,
            instruction_dest=_validate_dest(instruction, allowed),
            overlay=(repo_root / overlay).resolve(),
            skills_dest=_validate_dest(skills, allowed),
        )

    return Config(
        repo_root=repo_root,
        runtimes=runtimes,
        managed_skills=list(raw.get("managed_skills") or []),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -q`
Expected: 2 passed.

- [ ] **Step 5: Write the real committed manifest**

`config/targets.yaml`:

```yaml
# Allowlist of what agent-config-sync may write, and where.
# Destinations MUST resolve under ~/.claude, ~/.codex, or ~/.gemini.
runtimes:
  claude:
    instruction_dest: "~/.claude/CLAUDE.md"
    overlay: "overlays/claude.md"
    skills_dest: "~/.claude/skills"
  codex:
    instruction_dest: "~/.codex/AGENTS.md"
    overlay: "overlays/codex.md"
    skills_dest: "~/.codex/skills"
  gemini:
    instruction_dest: "~/.gemini/GEMINI.md"
    overlay: "overlays/gemini.md"
    skills_dest: "~/.gemini/skills"

# Skills under management (Plan 2). Empty for the forward-instructions slice.
managed_skills: []
```

- [ ] **Step 6: Commit**

```bash
git add src/agent_config_sync/config.py config/targets.yaml tests/test_config.py
git commit -m "feat: config loader with allowlist path validation + real targets.yaml"
```

---

### Task 7: `project` command (forward projection + safety)

**Files:**
- Create: `src/agent_config_sync/project.py`
- Test: `tests/test_project.py`

**Interfaces:**
- Consumes: `render`, `find_secrets`/`SecretFoundError`, `atomic_write`/`backup`/`sha256_text`/`default_stamp`, `load_state`/`save_state`, `Config`/`RuntimeConfig`.
- Produces:
  - `projected_for(repo_root: Path, rt: RuntimeConfig) -> str`
  - `class DriftError(Exception)` with attribute `runtimes: list[str]`
  - `@dataclass ProjectAction`: `runtime: str`, `kind: str`, `dest: Path`, `content: str` (kind ∈ `create|unchanged|update|forced|drift`)
  - `project(config: Config, *, dry_run: bool = False, force: bool = False, stamp: str | None = None) -> list[ProjectAction]`. Raises `SecretFoundError` (before any write) if projected content matches a secret pattern; raises `DriftError` if any runtime has an out-of-band edit and neither `force` nor `dry_run` is set. On apply, backs up existing dest, atomically writes projected content, and records `sha256(projected)` in state.

- [ ] **Step 1: Write the failing tests (goal + should-fail cases)**

`tests/test_project.py`:

```python
import pytest

from agent_config_sync.config import load_config
from agent_config_sync.project import DriftError, project, projected_for
from agent_config_sync.secrets import SecretFoundError


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_project_writes_all_runtimes(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    claude = cfg.runtimes["claude"].instruction_dest.read_text("utf-8")
    assert "Security is the foundation." in claude        # core flowed
    assert "Use the Skill tool" in claude                 # claude overlay
    gemini = cfg.runtimes["gemini"].instruction_dest.read_text("utf-8")
    assert "Use activate_skill" in gemini
    assert "Use the Skill tool" not in gemini             # overlays don't cross


def test_project_is_idempotent(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    actions = project(cfg)
    assert all(a.kind == "unchanged" for a in actions)


def test_dry_run_writes_nothing(fake_env):
    cfg = _cfg(fake_env)
    actions = project(cfg, dry_run=True)
    assert not cfg.runtimes["claude"].instruction_dest.exists()
    assert {a.kind for a in actions} == {"create"}


def test_source_change_updates_safely(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    (fake_env.repo / "_shared" / "core.md").write_text("# Core\nNEW LINE.\n", "utf-8")
    actions = {a.runtime: a.kind for a in project(cfg)}
    assert actions["claude"] == "update"
    assert "NEW LINE." in cfg.runtimes["claude"].instruction_dest.read_text("utf-8")


def test_refuses_unpromoted_drift(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    dest = cfg.runtimes["claude"].instruction_dest
    dest.write_text(dest.read_text("utf-8") + "\nHAND EDIT\n", "utf-8")
    with pytest.raises(DriftError) as exc:
        project(cfg)
    assert "claude" in exc.value.runtimes


def test_force_overwrites_drift_after_backup(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    dest = cfg.runtimes["claude"].instruction_dest
    dest.write_text("HAND EDIT\n", "utf-8")
    project(cfg, force=True, stamp="20260627T120000")
    assert "HAND EDIT" not in dest.read_text("utf-8")
    backup = fake_env.repo / ".backups" / "claude" / "20260627T120000" / "CLAUDE.md"
    assert backup.read_text("utf-8") == "HAND EDIT\n"


def test_secret_in_source_aborts_before_write(fake_env):
    cfg = _cfg(fake_env)
    (fake_env.repo / "overlays" / "claude.md").write_text(
        'key = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAA"\n', "utf-8"
    )
    with pytest.raises(SecretFoundError):
        project(cfg)
    assert not cfg.runtimes["claude"].instruction_dest.exists()


def test_projected_for_matches_render(fake_env):
    cfg = _cfg(fake_env)
    out = projected_for(fake_env.repo, cfg.runtimes["codex"])
    assert "Use apply_patch" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`src/agent_config_sync/project.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from .config import Config, RuntimeConfig
from .fsutil import atomic_write, backup, default_stamp, sha256_text
from .render import render
from .secrets import SecretFoundError, find_secrets
from .state import load_state, save_state


class DriftError(Exception):
    def __init__(self, runtimes: list[str]):
        self.runtimes = runtimes
        super().__init__(f"un-promoted changes in: {', '.join(runtimes)}")


@dataclass
class ProjectAction:
    runtime: str
    kind: str
    dest: Path
    content: str


def projected_for(repo_root: Path, rt: RuntimeConfig) -> str:
    core = (repo_root / "_shared" / "core.md").read_text("utf-8")
    overlay = rt.overlay.read_text("utf-8") if rt.overlay.exists() else ""
    return render(core, overlay)


def _classify(projected: str, dest: Path, last_hash: str | None, force: bool) -> str:
    if not dest.exists():
        return "create"
    current = dest.read_text("utf-8")
    if current == projected:
        return "unchanged"
    if last_hash is not None and sha256_text(current) == last_hash:
        return "update"
    return "forced" if force else "drift"


def project(
    config: Config,
    *,
    dry_run: bool = False,
    force: bool = False,
    stamp: str | None = None,
) -> list[ProjectAction]:
    state = load_state(config.repo_root)
    inst_state = state.setdefault("instructions", {})

    plan: list[ProjectAction] = []
    for name, rt in config.runtimes.items():
        projected = projected_for(config.repo_root, rt)
        matches = find_secrets(projected)
        if matches:
            raise SecretFoundError(name, matches)
        kind = _classify(projected, rt.instruction_dest, inst_state.get(name), force)
        plan.append(ProjectAction(name, kind, rt.instruction_dest, projected))

    drifted = [a.runtime for a in plan if a.kind == "drift"]
    if drifted and not dry_run:
        raise DriftError(drifted)
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
        inst_state[action.runtime] = sha256_text(action.content)

    save_state(config.repo_root, state)
    return plan
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/project.py tests/test_project.py
git commit -m "feat: project command with drift guard, backups, secret abort, idempotency"
```

---

### Task 8: `check` command (stale detection)

**Files:**
- Create: `src/agent_config_sync/check.py`
- Test: `tests/test_check.py`

**Interfaces:**
- Consumes: `projected_for`, `Config`.
- Produces: `check(config: Config) -> list[str]` returning the names of runtimes whose instruction file is missing or differs from projected output (empty list = all in sync).

- [ ] **Step 1: Write the failing test**

`tests/test_check.py`:

```python
from agent_config_sync.check import check
from agent_config_sync.config import load_config
from agent_config_sync.project import project


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_check_reports_all_stale_before_project(fake_env):
    assert sorted(check(_cfg(fake_env))) == ["claude", "codex", "gemini"]


def test_check_clean_after_project(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    assert check(cfg) == []


def test_check_flags_single_stale_runtime(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    cfg.runtimes["gemini"].instruction_dest.write_text("changed\n", "utf-8")
    assert check(cfg) == ["gemini"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_check.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`src/agent_config_sync/check.py`:

```python
from .config import Config
from .project import projected_for


def check(config: Config) -> list[str]:
    stale: list[str] = []
    for name, rt in config.runtimes.items():
        projected = projected_for(config.repo_root, rt)
        dest = rt.instruction_dest
        if not dest.exists() or dest.read_text("utf-8") != projected:
            stale.append(name)
    return stale
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_check.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_config_sync/check.py tests/test_check.py
git commit -m "feat: check command reports stale runtimes"
```

---

### Task 9: `status` + CLI wiring

**Files:**
- Create: `src/agent_config_sync/status.py`
- Create: `src/agent_config_sync/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config`, `project`/`DriftError`, `check`, `SecretFoundError`, `projected_for`, `load_state`, `sha256_text`.
- Produces:
  - `status(config: Config) -> dict[str, str]` mapping runtime → one of `in-sync|behind|edited|missing`.
  - `main(argv: list[str] | None = None) -> int`. Subcommands: `project` (`--dry-run`, `--force`), `check`, `status`. Repo root from `AGENT_CONFIG_SYNC_REPO` env or `Path(__file__).resolve().parents[2]`. Exit codes: 0 ok; 1 `check` found stale; 2 `DriftError`; 3 `SecretFoundError`.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
from agent_config_sync.cli import main
from agent_config_sync.config import load_config
from agent_config_sync.status import status


def _env(monkeypatch, fake_env):
    monkeypatch.setenv("AGENT_CONFIG_SYNC_REPO", str(fake_env.repo))
    monkeypatch.setenv(
        "AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
        __import__("os").pathsep.join(str(r) for r in fake_env.allowed_roots),
    )


def test_status_lifecycle(fake_env):
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    assert status(cfg)["claude"] == "missing"


def test_cli_check_exit_code_when_stale(monkeypatch, fake_env, capsys):
    _env(monkeypatch, fake_env)
    assert main(["check"]) == 1
    assert "STALE" in capsys.readouterr().out


def test_cli_project_then_check_clean(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    assert main(["project"]) == 0
    assert main(["check"]) == 0


def test_cli_project_drift_exit_2(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    main(["project"])
    dest = fake_env.allowed_roots[0] / "CLAUDE.md"
    dest.write_text("HAND EDIT\n", "utf-8")
    assert main(["project"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `status.py`**

`src/agent_config_sync/status.py`:

```python
from .config import Config
from .fsutil import sha256_text
from .project import projected_for
from .state import load_state


def status(config: Config) -> dict[str, str]:
    inst_state = load_state(config.repo_root).get("instructions", {})
    result: dict[str, str] = {}
    for name, rt in config.runtimes.items():
        projected = projected_for(config.repo_root, rt)
        dest = rt.instruction_dest
        if not dest.exists():
            result[name] = "missing"
            continue
        current = dest.read_text("utf-8")
        if current == projected:
            result[name] = "in-sync"
        elif inst_state.get(name) == sha256_text(current):
            result[name] = "behind"
        else:
            result[name] = "edited"
    return result
```

- [ ] **Step 4: Write `cli.py`**

`src/agent_config_sync/cli.py`:

```python
import argparse
import os
from pathlib import Path

from .check import check
from .config import load_config
from .project import DriftError, project
from .secrets import SecretFoundError
from .status import status


def _repo_root() -> Path:
    env = os.environ.get("AGENT_CONFIG_SYNC_REPO")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-config-sync")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("project", help="render source into each runtime")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    sub.add_parser("check", help="exit non-zero if any runtime is stale")
    sub.add_parser("status", help="show per-runtime sync state")
    args = parser.parse_args(argv)

    config = load_config(_repo_root())

    if args.cmd == "project":
        try:
            plan = project(config, dry_run=args.dry_run, force=args.force)
        except DriftError as exc:
            print(
                f"Refusing to overwrite un-promoted changes in: {', '.join(exc.runtimes)}. "
                "Run promote (Plan 2) or pass --force."
            )
            return 2
        except SecretFoundError as exc:
            print(f"Aborted: secret-like content for '{exc.runtime}'. No files written.")
            return 3
        for action in plan:
            print(f"{action.kind:10} {action.runtime} -> {action.dest}")
        return 0

    if args.cmd == "check":
        stale = check(config)
        if stale:
            print("STALE: " + ", ".join(stale))
            return 1
        print("All runtimes in sync.")
        return 0

    if args.cmd == "status":
        for name, state in status(config).items():
            print(f"{state:9} {name}")
        return 0

    return 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -q`
Expected: 4 passed.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: all tests pass (33).

- [ ] **Step 7: Commit**

```bash
git add src/agent_config_sync/status.py src/agent_config_sync/cli.py tests/test_cli.py
git commit -m "feat: status command and CLI dispatch with documented exit codes"
```

---

### Task 10: Pre-commit hook + repo standard docs

**Files:**
- Create: `hooks/pre-commit`
- Create: `SECURITY.md`, `.env.example`, `AGENTS.md`
- Create: `docs/ARCHITECTURE.md`, `docs/LIMITATIONS.md`
- Modify: `README.md` (replace "not implemented yet" banner with install + real usage; document that the console command is `agent-config-sync` and `sync` is an optional alias)

**Interfaces:** none (operational + documentation).

- [ ] **Step 1: Write the pre-commit hook**

`hooks/pre-commit`:

```sh
#!/bin/sh
# Block commits when any runtime instruction file is out of sync with source.
python -m agent_config_sync check || {
    echo "agent-config-sync: derived files are stale. Run 'python -m agent_config_sync project' and re-add."
    exit 1
}
```

- [ ] **Step 2: Install and verify the hook**

Run:
```bash
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
python -m agent_config_sync check; echo "exit=$?"
```
Expected: prints `STALE: ...` and `exit=1` if runtimes are not yet projected, or `All runtimes in sync.` and `exit=0` after a `project` run. (Confirms the hook's command works; do not commit broken state.)

- [ ] **Step 3: Write `SECURITY.md`**

`SECURITY.md`:

```markdown
# Security Policy

## What this tool does to your system
agent-config-sync writes to AI runtime instruction files under `~/.claude`,
`~/.codex`, and `~/.gemini`. It writes **only** to paths declared in
`config/targets.yaml` that resolve under those roots; any other destination is
rejected at load time.

## Controls
- **Allowlist:** destinations validated against runtime roots (`config.py`).
- **No secrets:** projected content is scanned for credential patterns and the
  run aborts before any write on a match (`secrets.py`).
- **No clobbering:** `project` refuses to overwrite a file edited out-of-band
  (tracked via `.sync-state.json`); use `promote` (Plan 2) or `--force`.
- **Backups:** every overwrite is copied under `.backups/` first.
- **Audit:** git history records every source change and projection.

## Threat note
These files steer AI agents. A poisoned `core.md` propagates to all runtimes,
making it an indirect prompt-injection vector. The reverse-flow `promote` path
(Plan 2) is therefore gated by human diff review. A full threat model lives in
`docs/threat-models/` once `promote` is implemented.

## Reporting
Open a private issue or contact the maintainer. Do not include secrets in reports.
```

- [ ] **Step 4: Write `.env.example`, `AGENTS.md`, and docs**

`.env.example`:

```bash
# Override the repo root the CLI reads (defaults to the package's repo).
# AGENT_CONFIG_SYNC_REPO=/c/Projects/agent-config-sync
# Override allowed runtime roots (os.pathsep-separated) — testing only.
# AGENT_CONFIG_SYNC_ALLOWED_ROOTS=
```

`AGENTS.md`:

```markdown
# AGENTS.md — agent-config-sync

This repo is the source of truth for AI runtime config. Rules for any agent
working here:

- Never hand-edit `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, or
  `~/.gemini/GEMINI.md` directly — they are generated. Edit `_shared/core.md`
  or `overlays/<vendor>.md`, then run `python -m agent_config_sync project`.
- Never add credentials to any source file; the secret lint will abort the run.
- Only paths in `config/targets.yaml` may be written; do not broaden the
  allowlist without human review.
- Run `pytest -q` before committing; the pre-commit hook runs `check`.
```

`docs/ARCHITECTURE.md`:

```markdown
# Architecture

Source of truth: `_shared/core.md` + `overlays/<vendor>.md`.
Projection: `render()` composes `header + core + overlay`; `project()` writes it
to each runtime's instruction file (allowlisted), backing up and hash-tracking.
`check()` (used by the pre-commit hook) fails when a derived file drifts from
source. `status()` classifies each runtime as in-sync / behind / edited / missing.
State: `.sync-state.json` stores the hash of the last content written per runtime,
distinguishing a forward update from an out-of-band hand edit.

See `docs/superpowers/specs/2026-06-27-cross-runtime-sync-design.md` for the
full design and the Plan 2/3 roadmap (skills projection, reverse promote).
```

`docs/LIMITATIONS.md`:

```markdown
# Limitations

- **Forward, instruction files only** in this slice. Skills projection (Plan 2)
  and reverse `promote` (Plan 3) are not yet implemented.
- **Manual trigger.** Projection runs only when you invoke it; the pre-commit
  hook only *detects* drift, it does not auto-fix.
- **Single machine.** Paths are local; no remote sync.
- **Secret lint is pattern-based** — it reduces, not eliminates, the risk of
  committing a credential. Do not rely on it as your only secret control.
- **Backups accumulate** under `.backups/`; prune manually.
```

- [ ] **Step 5: Update README usage section**

In `README.md`, replace the design-stage banner with an install block and change the quickstart commands from `sync <cmd>` to `python -m agent_config_sync <cmd>` (and note `agent-config-sync` is installed as a console script; `sync` may be added as a personal shell alias). Add:

```markdown
## Install
python -m pip install -e ".[dev]"
python -m agent_config_sync project   # first projection
```

- [ ] **Step 6: Commit**

```bash
git add hooks/pre-commit SECURITY.md .env.example AGENTS.md docs/ARCHITECTURE.md docs/LIMITATIONS.md README.md
git commit -m "docs: pre-commit hook, SECURITY/AGENTS/ARCHITECTURE/LIMITATIONS, README usage"
```

---

## Self-Review

**Spec coverage (against `2026-06-27-cross-runtime-sync-design.md`):**
- D-1 scope instructions+skills → instructions covered here; **skills deferred to Plan 2** (stated in §11 and Limitations). ✔ (intentional split)
- D-2 promote reverse flow → **Plan 3** (out of scope here, documented). ✔ (intentional)
- D-3 manual + stale-check hook → Tasks 7, 8, 10. ✔
- D-4 core + overlays → Tasks 2, 6. ✔
- D-5 git source of truth → repo already initialized; commits throughout. ✔
- D-6 Python stdlib + pyyaml/pytest pinned → Global Constraints, Task 1. ✔
- §8 safety: allowlist (Task 6), no-clobber drift guard (Task 7), backups (Tasks 4/7), secret lint (Tasks 3/7), atomic writes (Task 4), audit via git. ✔
- §9 tests: forward goal (Task 7), idempotency (Task 7), should-fail drift/secret/allowlist/stale (Tasks 6/7/8). ✔ (reverse goal test belongs to Plan 3)

**Placeholder scan:** no TBD/TODO in steps; every code step shows full code. README license TODO is the one allowed placeholder.

**Type consistency:** `projected_for(repo_root, rt)` defined in Task 7, consumed by Tasks 8/9. `ProjectAction(runtime, kind, dest, content)` consistent across project/cli. `load_config(repo_root, allowed_roots=None)` signature identical in all consumers. `DriftError.runtimes` / `SecretFoundError.runtime` used consistently in cli. State shape `{"instructions": {runtime: sha}}` consistent across state/project/status.

---

## Follow-on plans (not in this plan)

- **Plan 2 — Skills projection (forward).** Copy `managed_skills` from `skills/<name>/SKILL.md` into each runtime's `skills_dest`, with the same allowlist/backup/drift/state machinery extended to skill directories; wire `references/<vendor>-tools.md` adapters.
- **Plan 3 — Reverse `promote`.** `promote <runtime> [path]`: diff live runtime file/skill vs projected, interactively assign each hunk to core / overlay / neutralized skill, then re-project. Includes the reverse goal test (learn-in-Gemini → appears-in-Claude) and the `docs/threat-models/` entry.
