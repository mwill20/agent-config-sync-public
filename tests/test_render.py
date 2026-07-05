from agent_config_sync.render import GENERATED_HEADER, render


def test_render_combines_header_core_overlay():
    out = render("# Core\nBody.\n", "## Vendor\nExtra.\n")
    assert out.startswith(GENERATED_HEADER.rstrip("\n"))
    assert "# Core\nBody." in out
    assert "## Vendor\nExtra." in out
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_render_omits_empty_overlay():
    out = render("# Core\nBody.\n", "   \n")
    assert "Body." in out
    # only header + core, no dangling vendor section separator beyond one blank line
    assert out.count("\n\n") == 1  # one separator between header and core


def test_render_is_deterministic():
    a = render("c", "o")
    b = render("c", "o")
    assert a == b
