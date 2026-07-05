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
