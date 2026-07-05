import json

import pytest

from agent_config_sync.lock import LOCK_METADATA, LockError, repo_lock


def test_repo_lock_writes_metadata_and_releases(tmp_path):
    with repo_lock(tmp_path, command="project") as lock_dir:
        metadata = json.loads((lock_dir / LOCK_METADATA).read_text(encoding="utf-8"))
        assert metadata["command"] == "project"
        assert "pid" in metadata
        assert "hostname" in metadata
        assert "created_at" in metadata
    assert not lock_dir.exists()


def test_repo_lock_fails_closed_when_already_held(tmp_path):
    with repo_lock(tmp_path, command="first"):
        with pytest.raises(LockError) as exc:
            with repo_lock(tmp_path, command="second", timeout=0):
                pass
    assert "stale locks are not removed automatically" in str(exc.value)