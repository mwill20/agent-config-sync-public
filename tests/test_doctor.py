from agent_config_sync.config import load_config
from agent_config_sync.doctor import doctor
from agent_config_sync.project import project


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_doctor_reports_core_checks(fake_env):
    rows = doctor(_cfg(fake_env))
    names = [r[0] for r in rows]
    assert "repo" in names and "git" in names and "remote" in names
    assert any(n.startswith("sync:") for n in names)


def test_doctor_flags_out_of_sync_before_project(fake_env):
    statuses = {r[0]: r[1] for r in doctor(_cfg(fake_env))}
    assert statuses["sync:claude"] == "attention"  # nothing projected yet


def test_doctor_ok_after_project(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    statuses = {r[0]: r[1] for r in doctor(cfg)}
    assert statuses["sync:claude"] == "ok"
    assert statuses["sync:codex"] == "ok"
    assert statuses["sync:gemini"] == "ok"
