import os

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill
from agent_config_sync.overlap import compare, format_report

NEUTRAL = (
    "---\nname: demo\ndescription: audits repository documentation for gaps\n---\n\n"
    "Inspect the repository, list missing documentation, and propose fixes.\n"
)
UNIQUE = (
    "---\nname: stellar\ndescription: computes satellite orbital ephemerides\n---\n\n"
    "Given two-line element sets, compute look angles for a ground station.\n"
)


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def _enroll_demo(fake_env):
    (fake_env.repo / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    (fake_env.repo / "skills" / "demo" / "SKILL.md").write_text(NEUTRAL, "utf-8")
    enroll_skill(_cfg(fake_env), "demo", NEUTRAL)
    return _cfg(fake_env)


def test_near_copy_is_flagged_for_review(fake_env):
    # should-fail direction 1: a redundant candidate must not scan as unique
    cfg = _enroll_demo(fake_env)
    near_copy = NEUTRAL.replace("propose fixes", "suggest corrections")
    scores = compare(near_copy, cfg)
    assert scores[0].name == "demo"
    assert scores[0].flagged is True
    assert "REVIEW" in format_report(scores)


def test_unique_candidate_is_not_flagged(fake_env):
    # should-fail direction 2: a unique candidate must not be flagged redundant
    cfg = _enroll_demo(fake_env)
    scores = compare(UNIQUE, cfg)
    assert all(not s.flagged for s in scores)
    assert "looks unique" in format_report(scores)


def test_cli_exit_codes_and_inputs(fake_env, monkeypatch, tmp_path, capsys):
    from agent_config_sync.cli import main

    _enroll_demo(fake_env)
    monkeypatch.setenv("AGENT_CONFIG_SYNC_REPO", str(fake_env.repo))
    monkeypatch.setenv(
        "AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
        os.pathsep.join(str(r) for r in fake_env.allowed_roots),
    )
    near = tmp_path / "near.md"
    near.write_text(NEUTRAL.replace("propose fixes", "suggest corrections"), "utf-8")
    assert main(["overlap", "candidate", "--body-file", str(near)]) == 1
    uniq = tmp_path / "uniq.md"
    uniq.write_text(UNIQUE, "utf-8")
    assert main(["overlap", "candidate", "--body-file", str(uniq)]) == 0
    assert main(["overlap", "candidate"]) == 2  # needs a source
    assert main(["overlap", "Bad_Name", "--body-file", str(uniq)]) == 2
    fake_env.seed_skill("claude", "roaming", UNIQUE)
    assert main(["overlap", "roaming", "--from", "claude"]) == 0
    assert main(["overlap", "missing", "--from", "claude"]) == 2
