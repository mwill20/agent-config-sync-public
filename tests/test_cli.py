import sys

from agent_config_sync.cli import _configure_stdout, main
from agent_config_sync.config import load_config
from agent_config_sync.status import status


def _env(monkeypatch, fake_env):
    monkeypatch.setenv("AGENT_CONFIG_SYNC_REPO", str(fake_env.repo))
    monkeypatch.setenv(
        "AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
        __import__("os").pathsep.join(str(r) for r in fake_env.allowed_roots),
    )


def test_cli_configures_stdout_utf8(monkeypatch):
    class Stream:
        def __init__(self):
            self.kwargs = None

        def reconfigure(self, **kwargs):
            self.kwargs = kwargs

    stream = Stream()
    monkeypatch.setattr(sys, "stdout", stream)
    _configure_stdout()
    assert stream.kwargs == {"encoding": "utf-8", "errors": "backslashreplace"}


def test_status_lifecycle(fake_env):
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    assert status(cfg)["claude"] == "missing"


def test_cli_check_exit_code_when_stale(monkeypatch, fake_env, capsys):
    _env(monkeypatch, fake_env)
    assert main(["check"]) == 1
    assert "STALE" in capsys.readouterr().out


def test_cli_project_then_check_clean(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    assert main(["project"]) == 0
    assert main(["check"]) == 0


def test_cli_project_drift_exit_2(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    main(["project"])
    dest = fake_env.allowed_roots[0] / "CLAUDE.md"
    dest.write_text("HAND EDIT\n", "utf-8")
    assert main(["project"]) == 2


def test_cli_project_runtime_arg_scopes(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    assert main(["project", "claude"]) == 0
    assert (fake_env.allowed_roots[0] / "CLAUDE.md").exists()
    assert not (fake_env.allowed_roots[1] / "AGENTS.md").exists()


def test_cli_bare_force_multiple_drift_exit_4(monkeypatch, fake_env, capsys):
    _env(monkeypatch, fake_env)
    main(["project"])
    (fake_env.allowed_roots[0] / "CLAUDE.md").write_text("A\n", "utf-8")
    (fake_env.allowed_roots[2] / "GEMINI.md").write_text("B\n", "utf-8")
    assert main(["project", "--force"]) == 4
    assert "claude" in capsys.readouterr().out


def test_cli_scoped_force_succeeds(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    main(["project"])
    (fake_env.allowed_roots[0] / "CLAUDE.md").write_text("A\n", "utf-8")
    (fake_env.allowed_roots[2] / "GEMINI.md").write_text("B\n", "utf-8")
    assert main(["project", "claude", "--force"]) == 0
    assert "A\n" not in (fake_env.allowed_roots[0] / "CLAUDE.md").read_text("utf-8")
    assert (fake_env.allowed_roots[2] / "GEMINI.md").read_text("utf-8") == "B\n"


def test_cli_bare_force_refuses_mixed_instruction_and_skill_drift(monkeypatch, fake_env):
    # Overseer finding #1 (mixed case): a blanket --force must count instruction
    # AND skill drift together, not per-artifact-class, or it silently clobbers
    # one of each in a single sweep.
    _env(monkeypatch, fake_env)
    bf = fake_env.repo / "demo-body.md"
    bf.write_text("---\nname: demo\ndescription: d\n---\n\nDispatch a subagent.\n", "utf-8")
    main(["enroll", "demo", "--body-file", str(bf)])
    main(["project"])
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    cfg.runtimes["claude"].instruction_dest.write_text("HAND EDIT\n", "utf-8")
    skill = cfg.runtimes["gemini"].skills_dest / "demo" / "SKILL.md"
    skill.write_text(skill.read_text("utf-8") + "\nSKILL EDIT\n", "utf-8")
    assert main(["project", "--force"]) == 4
    assert cfg.runtimes["claude"].instruction_dest.read_text("utf-8") == "HAND EDIT\n"
    assert "SKILL EDIT" in skill.read_text("utf-8")


def test_cli_promote_refuses_when_other_runtime_drifted(monkeypatch, fake_env):
    # Overseer finding #2: promoting must not silently clobber an independent
    # un-promoted edit in another runtime during the reproject.
    _env(monkeypatch, fake_env)
    main(["project"])
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    gem = cfg.runtimes["gemini"].instruction_dest
    gem.write_text(gem.read_text("utf-8") + "\nLEARNED IN GEMINI.\n", "utf-8")
    claude = cfg.runtimes["claude"].instruction_dest
    claude.write_text("INDEPENDENT CLAUDE EDIT\n", "utf-8")
    assert main(["promote", "gemini", "--target", "core", "--confirm"]) == 2
    # Source captured the gemini learning...
    assert "LEARNED IN GEMINI." in (fake_env.repo / "_shared" / "core.md").read_text("utf-8")
    # ...but claude's independent edit was NOT clobbered.
    assert claude.read_text("utf-8") == "INDEPENDENT CLAUDE EDIT\n"


_BODY = "---\nname: demo\ndescription: d\n---\n\nDispatch a subagent.\n"


def test_cli_enroll_then_project_writes_skill(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    bf = fake_env.repo / "demo-body.md"
    bf.write_text(_BODY, "utf-8")
    assert main(["enroll", "demo", "--body-file", str(bf)]) == 0
    assert main(["project"]) == 0
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    assert (cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md").exists()
    assert (
        cfg.runtimes["gemini"].skills_dest / "demo" / "references" / "gemini-tools.md"
    ).exists()


def test_cli_enroll_rejects_non_neutral_body(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    bf = fake_env.repo / "bad-body.md"
    bf.write_text(_BODY + "\nUse the Skill tool.\n", "utf-8")
    assert main(["enroll", "bad", "--body-file", str(bf)]) == 3


def test_cli_config_error_exits_3_no_traceback(monkeypatch, fake_env, capsys):
    monkeypatch.setenv("AGENT_CONFIG_SYNC_REPO", str(fake_env.repo))
    # Point the allowlist at a root that does NOT contain the dests -> ConfigError.
    monkeypatch.setenv("AGENT_CONFIG_SYNC_ALLOWED_ROOTS", str(fake_env.repo / "nope"))
    assert main(["status"]) == 3
    assert "config" in capsys.readouterr().out.lower()


def test_cli_check_flags_skill_drift(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    bf = fake_env.repo / "demo-body.md"
    bf.write_text(_BODY, "utf-8")
    main(["enroll", "demo", "--body-file", str(bf)])
    main(["project"])
    assert main(["check"]) == 0
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    edited = cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md"
    edited.write_text(_BODY + "\nHAND EDIT\n", "utf-8")
    assert main(["check"]) == 1


def test_cli_capture_standard_dry_run_then_confirm(monkeypatch, fake_env, tmp_path):
    _env(monkeypatch, fake_env)
    tf = tmp_path / "t.md"
    tf.write_text("## Captured rule\nAlways log.\n", "utf-8")
    core = fake_env.repo / "_shared" / "core.md"
    before = core.read_text("utf-8")
    assert main(["capture", "standard", "--target", "core", "--text-file", str(tf)]) == 0
    assert core.read_text("utf-8") == before  # dry-run wrote nothing
    assert main(
        ["capture", "standard", "--target", "core", "--text-file", str(tf), "--confirm"]
    ) == 0
    assert "Always log." in core.read_text("utf-8")
    assert "Always log." in (fake_env.allowed_roots[0] / "CLAUDE.md").read_text("utf-8")


def test_cli_capture_skill_confirm_projects_immediately(monkeypatch, fake_env, tmp_path):
    _env(monkeypatch, fake_env)
    bf = tmp_path / "skill.md"
    bf.write_text(_BODY, "utf-8")
    assert main(["capture", "skill", "--name", "demo", "--body-file", str(bf), "--confirm"]) == 0
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    assert "demo" in cfg.managed_skills
    assert (cfg.runtimes["claude"].skills_dest / "demo" / "SKILL.md").exists()
    assert (cfg.runtimes["codex"].skills_dest / "demo" / "SKILL.md").exists()
    assert (cfg.runtimes["gemini"].skills_dest / "demo" / "SKILL.md").exists()


def test_cli_capture_secret_exit_3(monkeypatch, fake_env, tmp_path):
    _env(monkeypatch, fake_env)
    tf = tmp_path / "s.md"
    tf.write_text('api_key = "abcd1234efgh5678"\n', "utf-8")
    assert main(
        ["capture", "standard", "--target", "core", "--text-file", str(tf), "--confirm"]
    ) == 3


def test_cli_promote_reverse_to_claude(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    main(["project"])
    cfg = load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)
    gem = cfg.runtimes["gemini"].instruction_dest
    gem.write_text(gem.read_text("utf-8") + "\nLEARNED IN GEMINI.\n", "utf-8")
    # dry-run writes nothing
    assert main(["promote", "gemini", "--target", "core"]) == 0
    assert "LEARNED IN GEMINI." not in cfg.runtimes["claude"].instruction_dest.read_text("utf-8")
    # confirm fans it out
    assert main(["promote", "gemini", "--target", "core", "--confirm"]) == 0
    assert "LEARNED IN GEMINI." in cfg.runtimes["claude"].instruction_dest.read_text("utf-8")


def test_cli_promote_scan_all_clean(monkeypatch, fake_env, capsys):
    _env(monkeypatch, fake_env)
    main(["project"])
    assert main(["promote"]) == 0
    assert "Nothing to promote" in capsys.readouterr().out


def test_cli_install_hooks_claude(monkeypatch, fake_env, tmp_path):
    import json

    _env(monkeypatch, fake_env)
    # Skip the gemini shell-out so the test never touches real ~/.gemini config.
    monkeypatch.setattr("agent_config_sync.cli.shutil.which", lambda name: None)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), "utf-8")
    codex = tmp_path / "config.toml"  # temp so the test never touches real ~/.codex
    rc = main([
        "install-hooks", "--claude-settings", str(settings), "--codex-config", str(codex)
    ])
    assert rc == 0
    data = json.loads(settings.read_text("utf-8"))
    cmds = [h["command"] for e in data["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("sense" in c for c in cmds)
    # Codex hook landed in config.toml too
    import tomllib
    cdata = tomllib.loads(codex.read_text("utf-8"))
    ccmds = [h["command"] for e in cdata["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("sense" in c for c in ccmds)


def test_cli_install_hooks_dry_run_writes_nothing(monkeypatch, fake_env, tmp_path, capsys):
    _env(monkeypatch, fake_env)
    monkeypatch.setattr("agent_config_sync.cli.shutil.which", lambda name: "gemini")
    settings = tmp_path / "settings.json"
    codex = tmp_path / "config.toml"
    rc = main([
        "install-hooks",
        "--dry-run",
        "--claude-settings",
        str(settings),
        "--codex-config",
        str(codex),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRY-RUN" in out
    assert not settings.exists()
    assert not codex.exists()


def test_cli_install_hooks_gemini_failure_is_clean(monkeypatch, fake_env, tmp_path):
    import json

    _env(monkeypatch, fake_env)
    # gemini resolvable but the subprocess fails (e.g. Windows .cmd quirk) ->
    # must NOT crash; the Claude hook still installs, but overall exit is nonzero.
    monkeypatch.setattr("agent_config_sync.cli.shutil.which", lambda name: "gemini")

    def _boom(*a, **k):
        raise FileNotFoundError("simulated CreateProcess failure")

    monkeypatch.setattr("agent_config_sync.cli.subprocess.run", _boom)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), "utf-8")
    codex = tmp_path / "config.toml"
    rc = main([
        "install-hooks", "--claude-settings", str(settings), "--codex-config", str(codex)
    ])
    assert rc == 3
    data = json.loads(settings.read_text("utf-8"))
    cmds = [h["command"] for e in data["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("sense" in c for c in cmds)


def test_cli_install_hooks_gemini_nonzero_returns_failure(monkeypatch, fake_env, tmp_path):
    import json
    import subprocess

    _env(monkeypatch, fake_env)
    monkeypatch.setattr("agent_config_sync.cli.shutil.which", lambda name: "gemini")
    monkeypatch.setattr(
        "agent_config_sync.cli.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 7),
    )
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), "utf-8")
    codex = tmp_path / "config.toml"
    rc = main([
        "install-hooks", "--claude-settings", str(settings), "--codex-config", str(codex)
    ])
    assert rc == 3


def test_cli_install_hooks_codex_failure_returns_failure(monkeypatch, fake_env, tmp_path):
    import json

    _env(monkeypatch, fake_env)
    monkeypatch.setattr("agent_config_sync.cli.shutil.which", lambda name: None)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), "utf-8")
    codex = tmp_path / "config.toml"
    codex.write_text("this = = invalid toml", "utf-8")
    rc = main([
        "install-hooks", "--claude-settings", str(settings), "--codex-config", str(codex)
    ])
    assert rc == 3


def _backup_snapshot(repo, category, stamp):
    path = repo / ".backups" / category / stamp
    path.mkdir(parents=True)
    (path / "file.md").write_text(stamp, encoding="utf-8")
    return path


def test_cli_prune_backups_dry_run_writes_nothing(monkeypatch, fake_env, capsys):
    _env(monkeypatch, fake_env)
    old = _backup_snapshot(fake_env.repo, "source", "20200101T000000000000")
    for i in range(10):
        _backup_snapshot(fake_env.repo, "source", f"20200102T0000{i:02d}000000")

    assert main(["prune-backups"]) == 0
    out = capsys.readouterr().out

    assert "DRY-RUN" in out
    assert str(old) in out
    assert old.exists()
    assert not (fake_env.repo / ".sync-audit.log").exists()


def test_cli_prune_backups_confirm_deletes_and_audits(monkeypatch, fake_env):
    _env(monkeypatch, fake_env)
    old = _backup_snapshot(fake_env.repo, "source", "20200101T000000000000")
    for i in range(10):
        _backup_snapshot(fake_env.repo, "source", f"20200102T0000{i:02d}000000")

    assert main(["prune-backups", "--confirm"]) == 0

    assert not old.exists()
    audit = (fake_env.repo / ".sync-audit.log").read_text(encoding="utf-8")
    assert '"kind": "prune-backups"' in audit
    assert '"deleted_count": 1' in audit


def test_cli_project_lock_failure_writes_nothing(monkeypatch, fake_env):
    from agent_config_sync.lock import LOCK_METADATA, repo_lock

    _env(monkeypatch, fake_env)
    with repo_lock(fake_env.repo, command="held") as lock_dir:
        assert (lock_dir / LOCK_METADATA).exists()
        rc = main(["project"])

    assert rc == 5
    assert not (fake_env.allowed_roots[0] / "CLAUDE.md").exists()
    assert not (fake_env.repo / ".sync-state.json").exists()


def test_cli_project_and_check_report_gate_failure_cleanly(monkeypatch, fake_env):
    # should-fail: a vendor term in a managed source body must produce a clean
    # refusal with exit 3, never a traceback (found live 2026-07-04 when a new
    # managed name retroactively flagged an existing body)
    import json as _json

    _env(monkeypatch, fake_env)
    skill_dir = fake_env.repo / "skills" / "demo"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\n\nUse the Bash tool.\n", "utf-8"
    )
    targets = fake_env.repo / "config" / "targets.yaml"
    targets.write_text(
        targets.read_text("utf-8").replace(
            "managed_skills: []", 'managed_skills:\n  - "demo"'
        ),
        "utf-8",
    )
    assert main(["project"]) == 3
    assert main(["check"]) == 3
