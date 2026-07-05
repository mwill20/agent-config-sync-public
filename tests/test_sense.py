import json

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill
from agent_config_sync.project import project
from agent_config_sync.sense import format_brief, format_json, scan
from agent_config_sync.skills import project_skills

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


def test_clean_tree_yields_no_findings(fake_env):
    cfg = _clean_state(fake_env)
    findings = scan(cfg)
    assert findings == []
    assert "all runtimes in sync" in format_brief(findings)


def test_source_ahead_recommends_project(fake_env):
    cfg = _clean_state(fake_env)
    core = fake_env.repo / "_shared" / "core.md"
    core.write_text(core.read_text("utf-8") + "\nNew shared rule.\n", "utf-8")
    findings = scan(cfg)
    kinds = {f.kind for f in findings}
    assert kinds == {"source-ahead"}
    assert len(findings) == 3  # one per runtime instruction file
    brief = format_brief(findings)
    assert "source ahead" in brief
    assert "agent-config-sync project" in brief
    assert "Ask the operator" in brief


def test_runtime_instruction_edit_names_both_resolutions(fake_env):
    cfg = _clean_state(fake_env)
    dest = cfg.runtimes["claude"].instruction_dest
    dest.write_text(dest.read_text("utf-8") + "\nLOCAL EDIT\n", "utf-8")
    findings = scan(cfg)
    edits = [f for f in findings if f.kind == "runtime-edit"]
    assert len(edits) == 1
    assert edits[0].runtime == "claude"
    assert edits[0].keep == "agent-config-sync promote claude"
    assert edits[0].discard == "agent-config-sync project claude --force"
    brief = format_brief(findings)
    assert "keep: agent-config-sync promote claude" in brief
    assert "discard: agent-config-sync project claude --force" in brief


def test_runtime_skill_body_edit_recommends_reenroll(fake_env):
    cfg = _clean_state(fake_env)
    dest = cfg.runtimes["gemini"].skills_dest / "demo" / "SKILL.md"
    dest.write_text(NEUTRAL + "\nLOCAL SKILL EDIT\n", "utf-8")
    findings = scan(cfg)
    edits = [f for f in findings if f.kind == "runtime-edit"]
    assert len(edits) == 1
    assert edits[0].target == "demo/SKILL.md"
    assert edits[0].keep.startswith("agent-config-sync enroll demo --body-file ")
    assert edits[0].discard == "agent-config-sync project gemini --force"


def test_unmanaged_skill_reported_as_enrollment_candidate(fake_env):
    cfg = _clean_state(fake_env)
    fake_env.seed_skill("claude", "extra", "# Extra\nbody\n")
    findings = scan(cfg)
    unmanaged = [f for f in findings if f.kind == "unmanaged-skill"]
    assert len(unmanaged) == 1
    assert unmanaged[0].target == "extra"
    assert unmanaged[0].keep == "agent-config-sync enroll extra --from claude"
    assert "sense_ignore_skills" in format_brief(findings)


def test_sense_ignore_skills_suppresses_candidate(fake_env):
    _clean_state(fake_env)
    fake_env.seed_skill("claude", "extra", "# Extra\nbody\n")
    targets = fake_env.repo / "config" / "targets.yaml"
    targets.write_text(
        targets.read_text("utf-8").replace(
            "managed_skills:",
            'sense_ignore_skills:\n  - "extra"\nmanaged_skills:',
            1,
        ),
        "utf-8",
    )
    cfg = _cfg(fake_env)
    assert cfg.sense_ignore_skills == ["extra"]
    assert [f for f in scan(cfg) if f.kind == "unmanaged-skill"] == []


def test_unenrollable_name_reported_without_command(fake_env):
    cfg = _clean_state(fake_env)
    bad = cfg.runtimes["claude"].skills_dest / "Bad_Name"
    bad.mkdir(parents=True)
    (bad / "SKILL.md").write_text("# nope\n", "utf-8")
    findings = scan(cfg)
    unmanaged = [f for f in findings if f.kind == "unmanaged-skill"]
    assert len(unmanaged) == 1
    assert unmanaged[0].keep == ""
    assert "not enrollable" in format_brief(findings)


def test_source_gate_failure_is_a_finding_not_a_crash(fake_env):
    # should-fail: a vendor term planted in the canonical source must surface
    # as a finding — the session hook must never see a traceback
    cfg = _clean_state(fake_env)
    source = fake_env.repo / "skills" / "demo" / "SKILL.md"
    source.write_text(NEUTRAL + "\nUse the Bash tool here.\n", "utf-8")
    findings = scan(cfg)
    gates = [f for f in findings if f.kind == "gate-failure"]
    assert len(gates) == 1
    assert "fix source content" in gates[0].keep
    assert "gate failure" in format_brief(findings)


def test_json_output_schema(fake_env):
    cfg = _clean_state(fake_env)
    fake_env.seed_skill("codex", "extra", "# Extra\nbody\n")
    payload = json.loads(format_json(scan(cfg)))
    assert payload["count"] == 1
    finding = payload["findings"][0]
    assert set(finding) == {"kind", "runtime", "target", "keep", "discard"}


def test_cli_exit_codes(fake_env, monkeypatch):
    _clean_state(fake_env)
    import os

    from agent_config_sync.cli import main

    monkeypatch.setenv("AGENT_CONFIG_SYNC_REPO", str(fake_env.repo))
    monkeypatch.setenv(
        "AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
        os.pathsep.join(str(r) for r in fake_env.allowed_roots),
    )
    assert main(["sense"]) == 0
    fake_env.seed_skill("claude", "extra", "# Extra\nbody\n")
    assert main(["sense"]) == 1
    assert main(["sense", "--json"]) == 1
