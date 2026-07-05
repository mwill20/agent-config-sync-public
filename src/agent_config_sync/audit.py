import json
from pathlib import Path

AUDIT_FILE = ".sync-audit.log"


def append_audit(repo_root: Path, entry: dict) -> None:
    """Append one JSON record to the local append-only projection audit log.

    The log is the durable record of consequential writes (git does not capture
    writes to ~/.claude etc. — they live outside the repo). One JSON object per
    line so it is grep-able and tail-able for forensic reconstruction.
    """
    path = repo_root / AUDIT_FILE
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
