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


def test_load_config_accepts_valid_managed_skill_name(fake_env):
    targets = (fake_env.repo / "config" / "targets.yaml").read_text("utf-8")
    targets = targets.replace("managed_skills: []", "managed_skills:\n  - config-sync\n")
    (fake_env.repo / "config" / "targets.yaml").write_text(targets, encoding="utf-8")
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    assert cfg.managed_skills == ["config-sync"]


def test_load_config_rejects_managed_skill_path_traversal(fake_env):
    targets = (fake_env.repo / "config" / "targets.yaml").read_text("utf-8")
    targets = targets.replace("managed_skills: []", "managed_skills:\n  - ../escaped\n")
    (fake_env.repo / "config" / "targets.yaml").write_text(targets, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_load_config_rejects_duplicate_managed_skill(fake_env):
    targets = (fake_env.repo / "config" / "targets.yaml").read_text("utf-8")
    targets = targets.replace("managed_skills: []", "managed_skills:\n  - demo\n  - demo\n")
    (fake_env.repo / "config" / "targets.yaml").write_text(targets, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


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


def test_rejects_overlay_outside_repo(fake_env):
    # Critique finding #5: read-side paths must be contained too. An overlay that
    # escapes the repo could read any file and project it into an instruction file.
    evil = textwrap.dedent(f"""
        runtimes:
          claude:
            instruction_dest: "{(fake_env.allowed_roots[0] / 'CLAUDE.md').as_posix()}"
            overlay: "../../../../etc/passwd"
            skills_dest: "{(fake_env.allowed_roots[0] / 'skills').as_posix()}"
        managed_skills: []
    """).lstrip()
    (fake_env.repo / "config" / "targets.yaml").write_text(evil, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_env_var_allowed_roots(monkeypatch, fake_env):
    import os

    monkeypatch.setenv(
        "AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
        os.pathsep.join(str(r) for r in fake_env.allowed_roots),
    )
    cfg = load_config(fake_env.repo, allowed_roots=None)
    assert set(cfg.runtimes) == {"claude", "codex", "gemini"}
