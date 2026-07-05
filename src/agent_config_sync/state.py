import json
from pathlib import Path

from .fsutil import atomic_write

STATE_FILE = ".sync-state.json"


def load_state(repo_root: Path) -> dict:
    path = repo_root / STATE_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(repo_root: Path, state: dict) -> None:
    path = repo_root / STATE_FILE
    atomic_write(path, json.dumps(state, indent=2, sort_keys=True) + "\n")
