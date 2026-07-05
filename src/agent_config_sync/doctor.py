import shutil
import subprocess

from .config import Config
from .status import status


def _git_remote(repo_root) -> str | None:
    if not shutil.which("git"):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def doctor(config: Config) -> list[tuple[str, str, str]]:
    """Plain-language health checks: (check, status, detail).

    status is "ok" or "attention" so a non-dev can scan the column.
    """
    rows: list[tuple[str, str, str]] = []

    core = config.repo_root / "_shared" / "core.md"
    rows.append(
        ("repo", "ok" if core.exists() else "attention", str(config.repo_root))
    )
    rows.append(
        ("git", "ok" if shutil.which("git") else "attention", "version control")
    )
    remote = _git_remote(config.repo_root)
    rows.append(
        ("remote", "ok" if remote else "attention", remote or "no off-machine backup")
    )

    for name, state in status(config).items():
        rows.append((f"sync:{name}", "ok" if state == "in-sync" else "attention", state))

    return rows
