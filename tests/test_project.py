import pytest

from agent_config_sync import project as project_mod
from agent_config_sync.config import load_config
from agent_config_sync.project import (
    DriftError,
    ForceScopeError,
    project,
    projected_for,
)
from agent_config_sync.secrets import SecretFoundError
from agent_config_sync.state import load_state


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


# --- Critique finding #4: --force was global; scope it per runtime ---

def test_only_restricts_scope(fake_env):
    cfg = _cfg(fake_env)
    project(cfg, only="claude")
    assert cfg.runtimes["claude"].instruction_dest.exists()
    assert not cfg.runtimes["codex"].instruction_dest.exists()
    assert not cfg.runtimes["gemini"].instruction_dest.exists()


def test_force_single_runtime_leaves_others_drifted(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    claude = cfg.runtimes["claude"].instruction_dest
    gemini = cfg.runtimes["gemini"].instruction_dest
    claude.write_text("CLAUDE HAND EDIT\n", "utf-8")
    gemini.write_text("GEMINI HAND EDIT\n", "utf-8")
    project(cfg, only="claude", force=True, stamp="20260627T120000")
    assert "HAND EDIT" not in claude.read_text("utf-8")          # forced
    assert gemini.read_text("utf-8") == "GEMINI HAND EDIT\n"      # untouched


def test_bare_force_refuses_when_multiple_drifted(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    cfg.runtimes["claude"].instruction_dest.write_text("A\n", "utf-8")
    cfg.runtimes["gemini"].instruction_dest.write_text("B\n", "utf-8")
    with pytest.raises(ForceScopeError) as exc:
        project(cfg, force=True)
    assert set(exc.value.runtimes) == {"claude", "gemini"}


def test_bare_force_ok_when_single_drifted(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    claude = cfg.runtimes["claude"].instruction_dest
    claude.write_text("ONLY ONE\n", "utf-8")
    project(cfg, force=True, stamp="20260627T120000")
    assert "ONLY ONE" not in claude.read_text("utf-8")


def test_unknown_only_runtime_rejected(fake_env):
    cfg = _cfg(fake_env)
    with pytest.raises(ValueError):
        project(cfg, only="nope")


def test_project_writes_audit_log(fake_env):
    # Critique finding #1: every projection write must be auditable.
    import json

    from agent_config_sync.audit import AUDIT_FILE

    cfg = _cfg(fake_env)
    project(cfg, stamp="20260627T120000")
    entries = [
        json.loads(line)
        for line in (fake_env.repo / AUDIT_FILE).read_text("utf-8").splitlines()
    ]
    by_rt = {e["runtime"]: e for e in entries}
    assert set(by_rt) == {"claude", "codex", "gemini"}
    assert by_rt["claude"]["kind"] == "create"
    assert by_rt["claude"]["force"] is False
    assert by_rt["claude"]["content_sha256"]
    assert by_rt["claude"]["stamp"] == "20260627T120000"


def test_forced_overwrite_is_audited_with_force_flag(fake_env):
    import json

    from agent_config_sync.audit import AUDIT_FILE

    cfg = _cfg(fake_env)
    project(cfg, stamp="20260627T120000")
    dest = cfg.runtimes["claude"].instruction_dest
    dest.write_text("HAND EDIT\n", "utf-8")
    project(cfg, force=True, stamp="20260627T130000")
    entries = [
        json.loads(line)
        for line in (fake_env.repo / AUDIT_FILE).read_text("utf-8").splitlines()
    ]
    forced = [
        e for e in entries if e["stamp"] == "20260627T130000" and e["runtime"] == "claude"
    ]
    assert forced
    assert forced[0]["force"] is True
    assert forced[0]["kind"] == "forced"


def test_partial_failure_persists_state_for_written_runtimes(fake_env, monkeypatch):
    # Critique finding #3: a mid-loop write failure must not leave state out of
    # sync with disk. The runtime written before the failure must be recorded.
    cfg = _cfg(fake_env)
    real_atomic_write = project_mod.atomic_write

    def flaky_write(path, content):
        if path.name == "AGENTS.md":  # codex — second runtime in the loop
            raise OSError("simulated disk failure")
        return real_atomic_write(path, content)

    monkeypatch.setattr(project_mod, "atomic_write", flaky_write)

    with pytest.raises(OSError):
        project(cfg)

    # claude was written to disk before codex failed; its hash must be persisted.
    persisted = load_state(fake_env.repo).get("instructions", {})
    assert "claude" in persisted
    assert "codex" not in persisted
