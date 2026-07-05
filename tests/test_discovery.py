from pathlib import Path

from agent_config_sync.render import render

REPO = Path(__file__).resolve().parents[1]
MARKER = "## Keeping configs in sync"


def test_real_core_has_discovery_section():
    core = (REPO / "_shared" / "core.md").read_text("utf-8")
    assert MARKER in core
    assert "agent-config-sync" in core
    assert "check" in core  # names the verify command


def test_discovery_propagates_to_every_runtime():
    core = (REPO / "_shared" / "core.md").read_text("utf-8")
    for overlay_name in ("claude.md", "codex.md", "gemini.md"):
        overlay = (REPO / "overlays" / overlay_name).read_text("utf-8")
        out = render(core, overlay)
        assert MARKER in out  # discovery reaches each rendered instruction file
