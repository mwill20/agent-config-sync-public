import pytest
import json

from agent_config_sync.audit import AUDIT_FILE
from agent_config_sync.config import ConfigError, load_config
from agent_config_sync.enroll import (
    enroll_skill,
    propose_enrollment,
    update_managed_skills,
)
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


def test_update_managed_skills_refuses_when_not_last_key(tmp_path):
    # If anything but list items/comments follows managed_skills:, a textual
    # rewrite would silently delete it. The guard must refuse instead.
    p = tmp_path / "targets.yaml"
    p.write_text(
        "runtimes: {}\nmanaged_skills: []\ntrailing_key: oops\n", "utf-8"
    )
    with pytest.raises(ConfigError):
        update_managed_skills(p, ["demo"])
    # Original content untouched (no partial write).
    assert "trailing_key: oops" in p.read_text("utf-8")


def test_update_managed_skills_allows_trailing_comments(tmp_path):
    p = tmp_path / "targets.yaml"
    p.write_text("runtimes: {}\nmanaged_skills: []\n# a trailing comment\n", "utf-8")
    update_managed_skills(p, ["demo"])
    out = p.read_text("utf-8")
    assert '  - "demo"' in out


def test_update_managed_skills_rejects_invalid_name_before_write(tmp_path):
    p = tmp_path / "targets.yaml"
    p.write_text("runtimes: {}\nmanaged_skills: []\n", "utf-8")
    before = p.read_text("utf-8")
    with pytest.raises(ConfigError):
        update_managed_skills(p, ["../escaped"])
    assert p.read_text("utf-8") == before


def test_enroll_preserves_targets_comments(fake_env):
    enroll_skill(_cfg(fake_env), "demo", NEUTRAL)
    text = (fake_env.repo / "config" / "targets.yaml").read_text("utf-8")
    assert "runtimes:" in text  # preceding content intact


def test_enroll_backs_up_and_audits_source_overwrite(fake_env, monkeypatch):
    monkeypatch.setattr("agent_config_sync.enroll.default_stamp", lambda: "20260629T120000")
    skill = fake_env.repo / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("old body\n", "utf-8")
    enroll_skill(_cfg(fake_env), "demo", NEUTRAL)
    backup = fake_env.repo / ".backups" / "source" / "20260629T120000" / "SKILL.md"
    assert backup.read_text("utf-8") == "old body\n"
    entries = [
        json.loads(line)
        for line in (fake_env.repo / AUDIT_FILE).read_text("utf-8").splitlines()
    ]
    kinds = {entry["kind"] for entry in entries}
    assert {"enroll-skill", "update-managed-skills"}.issubset(kinds)


def test_enroll_rejects_non_neutral_body(fake_env):
    with pytest.raises(NeutralLanguageError):
        enroll_skill(_cfg(fake_env), "bad", NEUTRAL + "\nUse the Skill tool.\n")


def test_enroll_rejects_secret(fake_env):
    body = NEUTRAL + '\napi_key = "abcd1234efgh5678"\n'
    with pytest.raises(SecretFoundError):
        enroll_skill(_cfg(fake_env), "leaky", body)


def test_enroll_rejects_invalid_name_before_source_write(fake_env):
    before = (fake_env.repo / "config" / "targets.yaml").read_text("utf-8")
    with pytest.raises(ConfigError):
        enroll_skill(_cfg(fake_env), "../escaped", NEUTRAL)
    assert not (fake_env.repo / "escaped" / "SKILL.md").exists()
    assert (fake_env.repo / "config" / "targets.yaml").read_text("utf-8") == before


def test_propose_divergent_variants_raises(fake_env):
    fake_env.seed_skill("claude", "demo", "a\n")
    fake_env.seed_skill("codex", "demo", "b\n")
    with pytest.raises(ReconciliationError):
        propose_enrollment(_cfg(fake_env), "demo")


def test_propose_identical_variants_returns_body(fake_env):
    fake_env.seed_skill("claude", "demo", "x\n")
    fake_env.seed_skill("gemini", "demo", "x\n")
    assert propose_enrollment(_cfg(fake_env), "demo") == "x\n"
