import pytest

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill
from agent_config_sync.neutralize import NeutralLanguageError
from agent_config_sync.project import ForceScopeError
from agent_config_sync.secrets import SecretFoundError
from agent_config_sync.skills import (
    CompanionFileError,
    SkillDriftError,
    project_skills,
)

NEUTRAL = "---\nname: demo\ndescription: demo skill\n---\n\nDispatch a subagent.\n"


def test_fixture_provides_references_and_skill_seeder(fake_env):
    assert (fake_env.repo / "references" / "claude-code-tools.md").exists()
    assert (fake_env.repo / "references" / "codex-tools.md").exists()
    assert (fake_env.repo / "references" / "gemini-tools.md").exists()
    path = fake_env.seed_skill("gemini", "demo", "# Demo\nbody\n")
    assert path.read_text("utf-8") == "# Demo\nbody\n"
    assert path.parent.name == "demo"


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def _enroll_demo(fake_env):
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


def test_bare_force_refuses_when_multiple_skills_drifted(fake_env):
    # Overseer finding #1: a blanket --force must not clobber more than one
    # drifted skill file in a single sweep.
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)
    project_skills(cfg)
    for runtime in ("claude", "gemini"):
        edited = cfg.runtimes[runtime].skills_dest / "demo" / "SKILL.md"
        edited.write_text(NEUTRAL + f"\nEDIT {runtime}\n", "utf-8")
    with pytest.raises(ForceScopeError) as exc:
        project_skills(cfg, force=True)
    assert len(exc.value.runtimes) == 2
    # Neither drifted skill was overwritten by the refused sweep.
    for runtime in ("claude", "gemini"):
        edited = cfg.runtimes[runtime].skills_dest / "demo" / "SKILL.md"
        assert f"EDIT {runtime}" in edited.read_text("utf-8")


def _add_companion(fake_env, relpath, content):
    path = fake_env.repo / "skills" / "demo" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, "utf-8")
    return path


def test_companion_files_project_to_all_runtimes(fake_env):
    _enroll_demo(fake_env)
    _add_companion(fake_env, "lessons/intro.md", "# Intro\nneutral lesson\n")
    _add_companion(fake_env, "config.toml", "key = 1\n")
    cfg = _cfg(fake_env)
    project_skills(cfg)
    for runtime in ("claude", "codex", "gemini"):
        base = cfg.runtimes[runtime].skills_dest / "demo"
        assert (base / "lessons" / "intro.md").read_text("utf-8") == "# Intro\nneutral lesson\n"
        assert (base / "config.toml").read_text("utf-8") == "key = 1\n"
    actions = project_skills(cfg)
    assert all(a.kind == "unchanged" for a in actions)


def test_companion_hidden_paths_are_skipped(fake_env):
    _enroll_demo(fake_env)
    _add_companion(fake_env, ".hidden.md", "secret-ish local state\n")
    _add_companion(fake_env, ".cache/notes.md", "cache\n")
    cfg = _cfg(fake_env)
    project_skills(cfg)
    base = cfg.runtimes["claude"].skills_dest / "demo"
    assert not (base / ".hidden.md").exists()
    assert not (base / ".cache").exists()


def test_companion_disallowed_extension_refused(fake_env):
    # should-fail: executable content must not cross the projection boundary
    _enroll_demo(fake_env)
    _add_companion(fake_env, "scripts/run.py", "print('hi')\n")
    cfg = _cfg(fake_env)
    with pytest.raises(CompanionFileError) as exc:
        project_skills(cfg)
    assert "scripts/run.py" in str(exc.value)
    assert not (cfg.runtimes["claude"].skills_dest / "demo" / "scripts").exists()


def test_companion_adapter_collision_refused(fake_env):
    # should-fail: a companion must not shadow a runtime adapter file
    _enroll_demo(fake_env)
    _add_companion(fake_env, "references/claude-code-tools.md", "fake adapter\n")
    cfg = _cfg(fake_env)
    with pytest.raises(CompanionFileError) as exc:
        project_skills(cfg)
    assert "claude-code-tools.md" in str(exc.value)


def test_companion_case_insensitive_adapter_collision_refused(fake_env):
    # should-fail: Windows-style case variance must not bypass the adapter guard
    _enroll_demo(fake_env)
    _add_companion(fake_env, "references/CLAUDE-CODE-TOOLS.md", "fake adapter\n")
    cfg = _cfg(fake_env)
    with pytest.raises(CompanionFileError):
        project_skills(cfg)


def test_companion_invalid_utf8_refused_with_clear_error(fake_env):
    # should-fail: binary content renamed .md gets a controlled refusal
    _enroll_demo(fake_env)
    path = fake_env.repo / "skills" / "demo" / "notes.md"
    path.write_bytes(b"\xff\xfe\x00 not text")
    cfg = _cfg(fake_env)
    with pytest.raises(CompanionFileError) as exc:
        project_skills(cfg)
    assert "notes.md" in str(exc.value)


def test_companion_symlink_escaping_source_refused(fake_env, tmp_path):
    # should-fail: a symlink pointing outside the reviewed source tree
    _enroll_demo(fake_env)
    outside = tmp_path / "outside.md"
    outside.write_text("content from outside the source tree\n", "utf-8")
    link = fake_env.repo / "skills" / "demo" / "linked.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not permitted in this environment")
    cfg = _cfg(fake_env)
    with pytest.raises(CompanionFileError) as exc:
        project_skills(cfg)
    assert "linked.md" in str(exc.value)


def test_companion_with_secret_refused(fake_env):
    # should-fail: secret lint covers companions, not just bodies
    _enroll_demo(fake_env)
    _add_companion(fake_env, "notes.md", "aws key AKIAIOSFODNN7EXAMPLE\n")
    cfg = _cfg(fake_env)
    with pytest.raises(SecretFoundError):
        project_skills(cfg)


def test_companion_with_vendor_terms_refused(fake_env):
    # should-fail: companions travel to every runtime, so the neutral-language
    # gate applies to them the same as to bodies
    _enroll_demo(fake_env)
    _add_companion(fake_env, "guide.md", "Use the Bash tool to run this.\n")
    cfg = _cfg(fake_env)
    with pytest.raises(NeutralLanguageError) as exc:
        project_skills(cfg)
    assert "demo/guide.md" in str(exc.value)


def test_unchanged_projection_baselines_hash_so_source_edit_is_update(fake_env):
    # A skill whose runtime copy is byte-identical at first projection must
    # still get a recorded baseline; the next source edit is a clean update,
    # not false drift.
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)
    dest = cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(NEUTRAL, "utf-8")  # pre-existing identical runtime copy
    project_skills(cfg)
    edited_source = NEUTRAL + "\nSource improvement.\n"
    (fake_env.repo / "skills" / "demo" / "SKILL.md").write_text(edited_source, "utf-8")
    actions = project_skills(cfg)
    kinds = {a.kind for a in actions if a.runtime == "claude" and a.relpath == "SKILL.md"}
    assert kinds == {"update"}
    assert dest.read_text("utf-8") == edited_source


def test_source_body_edited_with_vendor_terms_refused_at_projection(fake_env):
    # should-fail (Codex audit finding): enrollment gates the front door, but a
    # direct canonical-source edit must not fan out ungated
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)
    project_skills(cfg)
    source = fake_env.repo / "skills" / "demo" / "SKILL.md"
    source.write_text(NEUTRAL + "\nNow use the Bash tool for this step.\n", "utf-8")
    with pytest.raises(NeutralLanguageError):
        project_skills(cfg)
    # nothing was written: the runtime copy is still the clean body
    dest = cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md"
    assert "Bash tool" not in dest.read_text("utf-8")


def test_source_body_with_wrapped_skill_slash_command_refused(fake_env):
    # should-fail: `/other-skill` in backticks is a slash-command reference
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)
    source = fake_env.repo / "skills" / "demo" / "SKILL.md"
    source.write_text(NEUTRAL + "\nRun `/config-sync` afterwards.\n", "utf-8")
    (fake_env.repo / "config" / "targets.yaml").write_text(
        (fake_env.repo / "config" / "targets.yaml")
        .read_text("utf-8")
        .replace('managed_skills:\n  - "demo"', 'managed_skills:\n  - "config-sync"\n  - "demo"'),
        "utf-8",
    )
    (fake_env.repo / "skills" / "config-sync").mkdir(exist_ok=True)
    (fake_env.repo / "skills" / "config-sync" / "SKILL.md").write_text(NEUTRAL, "utf-8")
    cfg = _cfg(fake_env)
    with pytest.raises(NeutralLanguageError) as exc:
        project_skills(cfg)
    assert "/config-sync" in str(exc.value)


def test_companion_runtime_edit_trips_drift_guard(fake_env):
    _enroll_demo(fake_env)
    _add_companion(fake_env, "lessons/intro.md", "# Intro\n")
    cfg = _cfg(fake_env)
    project_skills(cfg)
    edited = cfg.runtimes["claude"].skills_dest / "demo" / "lessons" / "intro.md"
    edited.write_text("# Intro\nHAND EDIT\n", "utf-8")
    with pytest.raises(SkillDriftError) as exc:
        project_skills(cfg)
    assert "claude:demo/lessons/intro.md" in exc.value.items


def test_scoped_force_overwrites_one_skill_leaves_other(fake_env):
    _enroll_demo(fake_env)
    cfg = _cfg(fake_env)
    project_skills(cfg)
    for runtime in ("claude", "gemini"):
        edited = cfg.runtimes[runtime].skills_dest / "demo" / "SKILL.md"
        edited.write_text(NEUTRAL + f"\nEDIT {runtime}\n", "utf-8")
    project_skills(cfg, only="claude", force=True, stamp="20260627T120000")
    claude = cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md"
    gemini = cfg.runtimes["gemini"].skills_dest / "demo" / "SKILL.md"
    assert "EDIT claude" not in claude.read_text("utf-8")   # forced
    assert "EDIT gemini" in gemini.read_text("utf-8")       # untouched
