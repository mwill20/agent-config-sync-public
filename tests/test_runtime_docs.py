from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_gemini_overlay_does_not_deny_adapter_activation_tool():
    adapter = (REPO / "references" / "gemini-tools.md").read_text("utf-8")
    overlay = (REPO / "overlays" / "gemini.md").read_text("utf-8")
    audit = (REPO / "docs" / "AUDIT_BRIEF.md").read_text("utf-8")
    assert "`activate_skill`" in adapter
    denied_phrases = [
        "no `activate_skill`",
        "there is **no** `activate_skill`",
    ]
    for text in (overlay, audit):
        lowered = text.lower()
        assert not any(phrase.lower() in lowered for phrase in denied_phrases)
    assert "Gemini CLI 0.26.0" in adapter
    assert "Gemini CLI 0.26.0" in overlay
