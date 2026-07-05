import json
import os
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


LOCK_DIR = ".sync-state.lock"
LOCK_METADATA = "owner.json"


class LockError(Exception):
    pass


def _metadata(command: str) -> dict[str, object]:
    return {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
    }


def _read_existing(lock_dir: Path) -> str:
    metadata_path = lock_dir / LOCK_METADATA
    if not metadata_path.exists():
        return "no owner metadata present"
    try:
        return metadata_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return f"owner metadata unreadable: {exc}"


@contextmanager
def repo_lock(
    repo_root: Path,
    *,
    command: str,
    timeout: float = 0.0,
    poll_interval: float = 0.05,
) -> Iterator[Path]:
    """Acquire a repo-scoped mutation lock using atomic directory creation.

    The lock is intentionally conservative: stale-looking locks fail closed and
    are never deleted automatically. The operator can inspect owner.json and then
    remove the lock directory manually if appropriate.
    """
    lock_dir = repo_root / LOCK_DIR
    deadline = time.monotonic() + max(timeout, 0.0)
    acquired = False
    while True:
        try:
            lock_dir.mkdir(mode=0o700)
            acquired = True
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                existing = _read_existing(lock_dir)
                raise LockError(
                    f"repo mutation lock is already held at {lock_dir}. "
                    f"Existing owner: {existing}. Inspect this directory before "
                    "manual removal; stale locks are not removed automatically."
                )
            time.sleep(poll_interval)
    try:
        metadata_path = lock_dir / LOCK_METADATA
        metadata_path.write_text(json.dumps(_metadata(command), sort_keys=True) + "\n", encoding="utf-8")
        yield lock_dir
    finally:
        if acquired:
            metadata_path = lock_dir / LOCK_METADATA
            try:
                if metadata_path.exists():
                    metadata_path.unlink()
                lock_dir.rmdir()
            except FileNotFoundError:
                pass