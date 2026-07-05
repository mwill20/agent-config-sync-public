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
