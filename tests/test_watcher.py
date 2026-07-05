import json

import pytest

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill
from agent_config_sync.project import project
from agent_config_sync.skills import project_skills
from agent_config_sync.watcher import watch_once

NEUTRAL = "---\nname: demo\ndescription: demo skill\n---\n\nDispatch a subagent.\n"


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def _clean_state(fake_env):
    (fake_env.repo / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    (fake_env.repo / "skills" / "demo" / "SKILL.md").write_text(NEUTRAL, "utf-8")
    enroll_skill(_cfg(fake_env), "demo", NEUTRAL)
    cfg = _cfg(fake_env)
    project(cfg)
    project_skills(cfg)
    return cfg


def _pending(tmp_path):
    return tmp_path / "state" / "pending.json"


def test_clean_run_is_heartbeat_exit_zero(fake_env, tmp_path):
    cfg = _clean_state(fake_env)
    title, body, code = watch_once(cfg, pending_path=_pending(tmp_path), now="T1")
    assert code == 0
    assert "alive" in title
    data = json.loads(_pending(tmp_path).read_text("utf-8"))
    assert data == {"count": 0, "findings": [], "generated_at": "T1"}


def test_findings_run_exits_one_and_persists(fake_env, tmp_path):
    cfg = _clean_state(fake_env)
    fake_env.seed_skill("claude", "extra", "# Extra\nbody\n")
    title, body, code = watch_once(cfg, pending_path=_pending(tmp_path), now="T1")
    assert code == 1
    assert "findings" in title
    data = json.loads(_pending(tmp_path).read_text("utf-8"))
    assert data["count"] == 1
    assert data["findings"][0]["kind"] == "unmanaged-skill"


def test_findings_to_clean_preserves_resolved_block(fake_env, tmp_path):
    cfg = _clean_state(fake_env)
    extra = fake_env.seed_skill("claude", "extra", "# Extra\nbody\n")
    watch_once(cfg, pending_path=_pending(tmp_path), now="T1")
    extra.unlink()
    extra.parent.rmdir()
    _, _, code = watch_once(cfg, pending_path=_pending(tmp_path), now="T2")
    assert code == 0
    data = json.loads(_pending(tmp_path).read_text("utf-8"))
    assert data["count"] == 0
    assert data["generated_at"] == "T2"
    assert data["resolved"]["generated_at"] == "T1"
    assert data["resolved"]["findings"][0]["target"] == "extra"


def test_clean_after_clean_has_no_resolved_block(fake_env, tmp_path):
    cfg = _clean_state(fake_env)
    watch_once(cfg, pending_path=_pending(tmp_path), now="T1")
    watch_once(cfg, pending_path=_pending(tmp_path), now="T2")
    data = json.loads(_pending(tmp_path).read_text("utf-8"))
    assert "resolved" not in data


def test_corrupt_pending_file_is_tolerated(fake_env, tmp_path):
    # should-fail input: garbage where JSON is expected must not crash the cycle
    cfg = _clean_state(fake_env)
    p = _pending(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text("{not json", "utf-8")
    _, _, code = watch_once(cfg, pending_path=p, now="T1")
    assert code == 0
    assert json.loads(p.read_text("utf-8"))["count"] == 0


def test_watcher_never_mutates_runtimes_or_source(fake_env, tmp_path):
    # should-fail (blocking constraint): even with drift present, the watcher
    # only writes its own pending file
    cfg = _clean_state(fake_env)
    dest = cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md"
    edited = NEUTRAL + "\nLOCAL EDIT\n"
    dest.write_text(edited, "utf-8")
    source = fake_env.repo / "skills" / "demo" / "SKILL.md"
    _, _, code = watch_once(cfg, pending_path=_pending(tmp_path), now="T1")
    assert code == 1
    assert dest.read_text("utf-8") == edited          # runtime untouched
    assert source.read_text("utf-8") == NEUTRAL       # source untouched


def test_scan_explosion_becomes_gate_failure_finding(fake_env, tmp_path, monkeypatch):
    # should-fail: an unexpected error must surface as a finding, never a
    # silent death or a traceback
    cfg = _clean_state(fake_env)
    monkeypatch.setattr(
        "agent_config_sync.watcher.scan",
        lambda _cfg: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    title, body, code = watch_once(cfg, pending_path=_pending(tmp_path), now="T1")
    assert code == 1
    data = json.loads(_pending(tmp_path).read_text("utf-8"))
    assert data["findings"][0]["kind"] == "gate-failure"
    assert "boom" in data["findings"][0]["keep"]


def test_cli_watch_once_two_line_output(fake_env, tmp_path, monkeypatch, capsys):
    import os

    from agent_config_sync.cli import main

    _clean_state(fake_env)
    monkeypatch.setenv("AGENT_CONFIG_SYNC_REPO", str(fake_env.repo))
    monkeypatch.setenv(
        "AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
        os.pathsep.join(str(r) for r in fake_env.allowed_roots),
    )
    pending = _pending(tmp_path)
    assert main(["watch-once", "--pending-file", str(pending)]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 2
    assert "alive" in out[0]
    assert pending.exists()
