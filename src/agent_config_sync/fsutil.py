import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class BackupPrunePlan:
    backup_root: Path
    policy: dict[str, int]
    delete: list[Path]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _unique_backup_dest(backup_root: Path, runtime: str, stamp: str, filename: str) -> Path:
    candidate_stamp = stamp
    counter = 1
    while True:
        dest = backup_root / runtime / candidate_stamp / filename
        if not dest.exists():
            return dest
        candidate_stamp = f"{stamp}-{counter:03d}"
        counter += 1


def backup(path: Path, backup_root: Path, runtime: str, stamp: str) -> Path | None:
    if not path.exists():
        return None
    dest = _unique_backup_dest(backup_root, runtime, stamp, path.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def _snapshot_time(path: Path) -> datetime:
    base = path.name.split("-", 1)[0]
    for fmt in ("%Y%m%dT%H%M%S%f", "%Y%m%dT%H%M%S"):
        try:
            return datetime.strptime(base, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _is_contained(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
    except OSError:
        return False
    return resolved == resolved_root or resolved.is_relative_to(resolved_root)


def plan_backup_prune(
    backup_root: Path,
    *,
    keep_latest: int = 10,
    keep_days: int = 30,
    now: datetime | None = None,
) -> BackupPrunePlan:
    if keep_latest < 1:
        raise ValueError("keep_latest must be at least 1")
    if keep_days < 0:
        raise ValueError("keep_days must be non-negative")

    root = backup_root.resolve()
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=keep_days)
    to_delete: list[Path] = []
    if not backup_root.exists():
        return BackupPrunePlan(root, {"keep_latest": keep_latest, "keep_days": keep_days}, [])

    for category in sorted(backup_root.iterdir(), key=lambda p: p.name):
        if not category.is_dir() or category.is_symlink() or not _is_contained(category, root):
            continue
        snapshots = [
            snap
            for snap in category.iterdir()
            if snap.is_dir() and not snap.is_symlink() and _is_contained(snap, root)
        ]
        snapshots.sort(key=lambda p: (_snapshot_time(p), p.name), reverse=True)
        keep = set(snapshots[:keep_latest])
        for snap in snapshots:
            if snap in keep:
                continue
            if _snapshot_time(snap) >= cutoff:
                continue
            to_delete.append(snap)

    return BackupPrunePlan(
        root,
        {"keep_latest": keep_latest, "keep_days": keep_days},
        sorted(to_delete),
    )


def prune_backups(
    backup_root: Path,
    *,
    confirm: bool = False,
    keep_latest: int = 10,
    keep_days: int = 30,
    now: datetime | None = None,
) -> BackupPrunePlan:
    plan = plan_backup_prune(
        backup_root,
        keep_latest=keep_latest,
        keep_days=keep_days,
        now=now,
    )
    if not confirm:
        return plan
    for path in plan.delete:
        if not _is_contained(path, plan.backup_root):
            raise ValueError(f"refusing to delete outside backup root: {path}")
        shutil.rmtree(path)
    return plan