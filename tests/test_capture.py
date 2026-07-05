import pytest
import json

from agent_config_sync.audit import AUDIT_FILE
from agent_config_sync.capture import capture_skill, capture_standard
from agent_config_sync.config import ConfigError, load_config
from agent_config_sync.neutralize import NeutralLanguageError
from agent_config_sync.secrets import SecretFoundError

NEUTRAL = "---\nname: cap\ndescription: d\n---\n\nDispatch a subagent.\n"


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_capture_standard_dry_run_does_not_write(fake_env):
    cfg = _cfg(fake_env)
    core = fake_env.repo / "_shared" / "core.md"
    before = core.read_text("utf-8")
    result = capture_standard(cfg, "core", "## New rule\nAlways log.", confirm=False)
    assert result.applied is False
    assert "New rule" in result.diff
    assert core.read_text("utf-8") == before  # unchanged on dry-run


def test_capture_standard_confirm_appends(fake_env):
    cfg = _cfg(fake_env)
    core = fake_env.repo / "_shared" / "core.md"
    capture_standard(cfg, "core", "## New rule\nAlways log.", confirm=True)
    assert "Always log." in core.read_text("utf-8")


def test_capture_standard_confirm_audits_source_write(fake_env):
    cfg = _cfg(fake_env)
    capture_standard(cfg, "core", "## Audited\nSource write.", confirm=True)
    entries = [
        json.loads(line)
        for line in (fake_env.repo / AUDIT_FILE).read_text("utf-8").splitlines()
    ]
    assert entries[-1]["runtime"] == "source"
    assert entries[-1]["kind"] == "capture"
    assert entries[-1]["target"] == "core"


def test_capture_standard_overlay_target(fake_env):
    cfg = _cfg(fake_env)
    capture_standard(cfg, "gemini", "## Gemini-only note", confirm=True)
    assert "Gemini-only note" in (fake_env.repo / "overlays" / "gemini.md").read_text("utf-8")


def test_capture_standard_secret_aborts_before_write(fake_env):
    cfg = _cfg(fake_env)
    core = fake_env.repo / "_shared" / "core.md"
    before = core.read_text("utf-8")
    with pytest.raises(SecretFoundError):
        capture_standard(cfg, "core", 'api_key = "abcd1234efgh5678"', confirm=True)
    assert core.read_text("utf-8") == before  # nothing written


def test_capture_standard_unknown_target(fake_env):
    with pytest.raises(ValueError):
        capture_standard(_cfg(fake_env), "nope", "x", confirm=False)


def test_capture_skill_dry_run_then_confirm(fake_env):
    cfg = _cfg(fake_env)
    (fake_env.repo / "skills" / "cap").mkdir(parents=True)
    dry = capture_skill(cfg, "cap", NEUTRAL, confirm=False)
    assert dry.applied is False
    assert not (fake_env.repo / "skills" / "cap" / "SKILL.md").exists()
    capture_skill(cfg, "cap", NEUTRAL, confirm=True)
    assert (fake_env.repo / "skills" / "cap" / "SKILL.md").read_text("utf-8") == NEUTRAL
    assert "cap" in _cfg(fake_env).managed_skills


def test_capture_skill_non_neutral_aborts(fake_env):
    with pytest.raises(NeutralLanguageError):
        capture_skill(_cfg(fake_env), "bad", NEUTRAL + "\nUse the Bash tool.\n", confirm=True)


def test_capture_skill_rejects_invalid_name_before_write(fake_env):
    with pytest.raises(ConfigError):
        capture_skill(_cfg(fake_env), "../../escaped", NEUTRAL, confirm=True)
    assert not (fake_env.repo / "escaped" / "SKILL.md").exists()
