import json
import os
import stat
import sys
import tomllib

from agent_config_sync.cli import main


def _env(monkeypatch, fake_env):
    monkeypatch.setenv("AGENT_CONFIG_SYNC_REPO", str(fake_env.repo))
    monkeypatch.setenv(
        "AGENT_CONFIG_SYNC_ALLOWED_ROOTS",
        os.pathsep.join(str(r) for r in fake_env.allowed_roots),
    )


def _write_mock_gemini(mock_dir):
    if sys.platform == "win32":
        script = mock_dir / "gemini.cmd"
        script.write_text(
            "@echo off\r\n"
            "if \"%1\"==\"hooks\" if \"%2\"==\"migrate\" if \"%3\"==\"--from-claude\" exit /b 0\r\n"
            "exit /b 9\r\n",
            encoding="utf-8",
        )
    else:
        script = mock_dir / "gemini"
        script.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"hooks\" ] && [ \"$2\" = \"migrate\" ] && [ \"$3\" = \"--from-claude\" ]; then\n"
            "  exit 0\n"
            "fi\n"
            "exit 9\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_install_hooks_uses_mock_gemini_from_path(monkeypatch, fake_env, tmp_path, capsys):
    _env(monkeypatch, fake_env)
    mock_dir = tmp_path / "mock-bin"
    mock_dir.mkdir()
    _write_mock_gemini(mock_dir)
    monkeypatch.setenv("PATH", str(mock_dir) + os.pathsep + os.environ.get("PATH", ""))

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"SessionStart": []}}), encoding="utf-8")
    codex = tmp_path / "config.toml"

    rc = main([
        "install-hooks",
        "--claude-settings",
        str(settings),
        "--codex-config",
        str(codex),
    ])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Gemini hook migration succeeded." in out
    claude_data = json.loads(settings.read_text(encoding="utf-8"))
    claude_cmds = [
        h["command"]
        for entry in claude_data["hooks"]["SessionStart"]
        for h in entry["hooks"]
    ]
    assert "agent-config-sync sense" in claude_cmds
    codex_data = tomllib.loads(codex.read_text(encoding="utf-8"))
    codex_cmds = [
        h["command"]
        for entry in codex_data["hooks"]["SessionStart"]
        for h in entry["hooks"]
    ]
    assert "agent-config-sync sense" in codex_cmds