from pathlib import Path

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill
from agent_config_sync.neutralize import find_vendor_terms
from agent_config_sync.skills import project_skills

REPO = Path(__file__).resolve().parents[1]


def test_config_sync_skill_body_is_neutral():
    body = (REPO / "skills" / "config-sync" / "SKILL.md").read_text("utf-8")
    assert find_vendor_terms(body) == []  # no vendor tool names / slash commands


def test_config_sync_projects_to_all_runtimes(fake_env):
    body = (REPO / "skills" / "config-sync" / "SKILL.md").read_text("utf-8")
    (fake_env.repo / "skills" / "config-sync").mkdir(parents=True)
    (fake_env.repo / "skills" / "config-sync" / "SKILL.md").write_text(body, "utf-8")
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    enroll_skill(cfg, "config-sync", body)
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)  # reload
    project_skills(cfg)
    for runtime in ("claude", "codex", "gemini"):
        base = cfg.runtimes[runtime].skills_dest / "config-sync"
        assert (base / "SKILL.md").read_text("utf-8") == body
        assert (base / "references").is_dir()
