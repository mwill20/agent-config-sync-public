"""Tier 2 ambient watcher core: one daily cycle.

Read-only with respect to the source repo and every runtime: the only write is
the pending-findings file in machine-local state. The scheduled PowerShell
wrapper (scripts/sense-watcher.ps1) calls `agent-config-sync watch-once` and
shows the returned title/body as a balloon notification. The clean-run
notification doubles as the heartbeat (see the ambient-automation spec).
"""

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .sense import Finding, scan


def default_pending_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "state")
    return Path(base) / "agent-config-sync" / "pending.json"


def watch_once(
    config: Config,
    pending_path: Path | None = None,
    now: str | None = None,
) -> tuple[str, str, int]:
    """Run one watcher cycle. Returns (title, body, exit_code).

    exit 0 = clean (heartbeat), 1 = findings. The pending file is advisory-only
    (no signature — see TRADEOFFS); a findings->clean transition preserves the
    superseded findings in a `resolved` block so the next session can name what
    was fixed. Never raises: a failing scan becomes a gate-failure finding,
    because a silently dead watcher is itself the failure mode to avoid.
    """
    pending_path = pending_path or default_pending_path()
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        findings = scan(config)
    except Exception as exc:  # noqa: BLE001 — watcher must never die silently
        findings = [
            Finding("gate-failure", "source", "watcher",
                    f"sense failed: {exc}", "")
        ]

    previous = None
    if pending_path.exists():
        try:
            previous = json.loads(pending_path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            previous = None

    payload: dict = {
        "count": len(findings),
        "findings": [asdict(f) for f in findings],
        "generated_at": now,
    }
    if not findings and isinstance(previous, dict) and previous.get("count", 0):
        payload["resolved"] = {
            "findings": previous.get("findings", []),
            "generated_at": previous.get("generated_at", ""),
        }

    pending_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = pending_path.with_name(pending_path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, pending_path)

    if findings:
        title = "agent-config-sync: findings"
        body = (
            f"{len(findings)} finding(s). Open an AI session; it will explain "
            "and ask before acting."
        )
        return title, body, 1
    title = "agent-config-sync: watcher alive"
    body = "No findings. All runtimes in sync."
    return title, body, 0
