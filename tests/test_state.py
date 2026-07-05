from pathlib import Path

from agent_config_sync.state import load_state, save_state


def test_load_missing_returns_empty(tmp_path: Path):
    assert load_state(tmp_path) == {}


def test_save_then_load_roundtrip(tmp_path: Path):
    save_state(tmp_path, {"instructions": {"claude": "abc"}})
    assert load_state(tmp_path) == {"instructions": {"claude": "abc"}}
    assert (tmp_path / ".sync-state.json").exists()
    assert not (tmp_path / ".sync-state.json.tmp").exists()
