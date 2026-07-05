import pytest

from agent_config_sync.config import load_config
from agent_config_sync.project import project
from agent_config_sync.promote import (
    PromoteAmbiguousChange,
    PromoteBaselineMissing,
    PromoteConflict,
    PromoteSourceBehind,
    detect_divergence,
    promote_instruction,
)


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def _edit_live(cfg, runtime, line):
    dest = cfg.runtimes[runtime].instruction_dest
    dest.write_text(dest.read_text("utf-8") + f"\n{line}\n", "utf-8")


def test_promote_reverse_goal_shared(fake_env):
    # The literal requirement: learn in gemini, get it in claude + codex.
    cfg = _cfg(fake_env)
    project(cfg)
    _edit_live(cfg, "gemini", "SHARED LEARNING.")
    promote_instruction(cfg, "gemini", "core", confirm=True)
    assert "SHARED LEARNING." in cfg.runtimes["claude"].instruction_dest.read_text("utf-8")
    assert "SHARED LEARNING." in cfg.runtimes["codex"].instruction_dest.read_text("utf-8")


def test_promote_vendor_routing_stays_local(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    _edit_live(cfg, "gemini", "GEMINI ONLY.")
    promote_instruction(cfg, "gemini", "gemini", confirm=True)
    assert "GEMINI ONLY." in cfg.runtimes["gemini"].instruction_dest.read_text("utf-8")
    assert "GEMINI ONLY." not in cfg.runtimes["claude"].instruction_dest.read_text("utf-8")


def test_promote_dry_run_writes_nothing(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    _edit_live(cfg, "gemini", "MAYBE SHARED.")
    core_before = (fake_env.repo / "_shared" / "core.md").read_text("utf-8")
    result = promote_instruction(cfg, "gemini", "core", confirm=False)
    assert result.applied is False
    assert (fake_env.repo / "_shared" / "core.md").read_text("utf-8") == core_before
    assert "MAYBE SHARED." not in cfg.runtimes["claude"].instruction_dest.read_text("utf-8")


def test_promote_nothing_to_do_returns_none(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    assert detect_divergence(cfg, "gemini") is None
    assert promote_instruction(cfg, "gemini", "core", confirm=True) is None


def test_promote_idempotent_after_round_trip(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    _edit_live(cfg, "gemini", "ONCE.")
    promote_instruction(cfg, "gemini", "core", confirm=True)
    assert detect_divergence(cfg, "gemini") is None  # converged


def test_promote_three_way_conflict_flagged_not_merged(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    # Source moves AND the live file is edited -> 3-way conflict.
    core = fake_env.repo / "_shared" / "core.md"
    core.write_text(core.read_text("utf-8") + "\nSOURCE MOVED.\n", "utf-8")
    _edit_live(cfg, "gemini", "LIVE EDIT.")
    with pytest.raises(PromoteConflict):
        promote_instruction(cfg, "gemini", "core", confirm=True)
    # core not appended with the live edit
    assert "LIVE EDIT." not in core.read_text("utf-8")


def test_promote_source_only_movement_is_not_conflict(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    core = fake_env.repo / "_shared" / "core.md"
    core.write_text(core.read_text("utf-8") + "\nSOURCE ONLY.\n", "utf-8")
    d = detect_divergence(cfg, "gemini")
    assert d["state"] == "source-behind"
    assert d["conflict"] is False
    with pytest.raises(PromoteSourceBehind):
        promote_instruction(cfg, "gemini", "core", confirm=True)


def test_promote_missing_baseline_refuses(fake_env):
    cfg = _cfg(fake_env)
    with pytest.raises(PromoteBaselineMissing):
        promote_instruction(cfg, "gemini", "core", confirm=True)


def test_promote_delete_exact_source_line(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    gem = cfg.runtimes["gemini"].instruction_dest
    gem.write_text(
        gem.read_text("utf-8").replace("Security is the foundation.\n", ""),
        "utf-8",
    )
    promote_instruction(cfg, "gemini", "core", confirm=True)
    assert "Security is the foundation." not in (fake_env.repo / "_shared" / "core.md").read_text("utf-8")
    assert "Security is the foundation." not in cfg.runtimes["claude"].instruction_dest.read_text("utf-8")


def test_promote_replace_exact_source_line(fake_env):
    cfg = _cfg(fake_env)
    project(cfg)
    gem = cfg.runtimes["gemini"].instruction_dest
    gem.write_text(
        gem.read_text("utf-8").replace(
            "Security is the foundation.", "Security remains mandatory."
        ),
        "utf-8",
    )
    promote_instruction(cfg, "gemini", "core", confirm=True)
    assert "Security remains mandatory." in (fake_env.repo / "_shared" / "core.md").read_text("utf-8")
    assert "Security remains mandatory." in cfg.runtimes["codex"].instruction_dest.read_text("utf-8")


def test_promote_ambiguous_delete_refuses_before_source_write(fake_env):
    cfg = _cfg(fake_env)
    core = fake_env.repo / "_shared" / "core.md"
    core.write_text("# Core Standards\n\nDUPLICATE.\nDUPLICATE.\n", "utf-8")
    project(cfg)
    before = core.read_text("utf-8")
    gem = cfg.runtimes["gemini"].instruction_dest
    gem.write_text(gem.read_text("utf-8").replace("DUPLICATE.\n", "", 1), "utf-8")
    with pytest.raises(PromoteAmbiguousChange):
        promote_instruction(cfg, "gemini", "core", confirm=True)
    assert core.read_text("utf-8") == before
