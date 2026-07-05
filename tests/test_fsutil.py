from datetime import datetime, timezone
from pathlib import Path

from agent_config_sync.fsutil import (
    atomic_write,
    backup,
    default_stamp,
    plan_backup_prune,
    prune_backups,
    sha256_text,
)


def test_atomic_write_creates_dirs_and_content(tmp_path: Path):
    target = tmp_path / "a" / "b" / "file.md"
    atomic_write(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert not list(target.parent.glob("*.tmp"))


def test_atomic_write_overwrites(tmp_path: Path):
    target = tmp_path / "file.md"
    atomic_write(target, "one\n")
    atomic_write(target, "two\n")
    assert target.read_text(encoding="utf-8") == "two\n"


def test_backup_copies_existing(tmp_path: Path):
    src = tmp_path / "CLAUDE.md"
    src.write_text("orig\n", encoding="utf-8")
    dest = backup(src, tmp_path / ".backups", "claude", "20260627T120000")
    assert dest is not None
    assert dest.read_text(encoding="utf-8") == "orig\n"
    assert dest == tmp_path / ".backups" / "claude" / "20260627T120000" / "CLAUDE.md"


def test_backup_same_stamp_never_overwrites_existing_backup(tmp_path: Path):
    src = tmp_path / "CLAUDE.md"
    backup_root = tmp_path / ".backups"
    src.write_text("first\n", encoding="utf-8")
    first = backup(src, backup_root, "claude", "20260627T120000")
    src.write_text("second\n", encoding="utf-8")
    second = backup(src, backup_root, "claude", "20260627T120000")

    assert first is not None and second is not None
    assert first != second
    assert first.read_text(encoding="utf-8") == "first\n"
    assert second.read_text(encoding="utf-8") == "second\n"
    assert second.parent.name == "20260627T120000-001"


def test_backup_returns_none_when_missing(tmp_path: Path):
    assert backup(tmp_path / "nope.md", tmp_path / ".backups", "claude", "s") is None


def test_sha256_is_stable():
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abd")


def test_default_stamp_format_is_orderable_and_microsecond_precise():
    stamp = default_stamp()
    assert len(stamp) == 21
    assert stamp[8] == "T"
    datetime.strptime(stamp, "%Y%m%dT%H%M%S%f")


def _snapshot(root: Path, category: str, stamp: str) -> Path:
    path = root / category / stamp
    path.mkdir(parents=True)
    (path / "file.md").write_text(stamp, encoding="utf-8")
    return path


def test_plan_backup_prune_keeps_newest_ten_snapshots(tmp_path: Path):
    backup_root = tmp_path / ".backups"
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    old_delete = _snapshot(backup_root, "claude", "20260501T000000000000")
    old_keep_by_count = [
        _snapshot(backup_root, "claude", f"20260502T0000{i:02d}000000")
        for i in range(10)
    ]

    plan = plan_backup_prune(backup_root, now=now)

    assert old_delete in plan.delete
    assert not any(path in plan.delete for path in old_keep_by_count)


def test_prune_backups_dry_run_deletes_nothing(tmp_path: Path):
    backup_root = tmp_path / ".backups"
    old = _snapshot(backup_root, "source", "20260501T000000000000")
    for i in range(10):
        _snapshot(backup_root, "source", f"20260502T0000{i:02d}000000")

    plan = prune_backups(
        backup_root,
        confirm=False,
        now=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    assert old in plan.delete
    assert old.exists()


def test_prune_backups_confirm_deletes_only_planned_snapshots(tmp_path: Path):
    backup_root = tmp_path / ".backups"
    old = _snapshot(backup_root, "source", "20260501T000000000000")
    kept = [
        _snapshot(backup_root, "source", f"20260502T0000{i:02d}000000")
        for i in range(10)
    ]

    plan = prune_backups(
        backup_root,
        confirm=True,
        now=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    assert old in plan.delete
    assert not old.exists()
    assert all(path.exists() for path in kept)


def test_prune_backups_ignores_symlink_escape(tmp_path: Path):
    backup_root = tmp_path / ".backups"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "do-not-delete.txt").write_text("keep\n", encoding="utf-8")
    category = backup_root / "source"
    category.mkdir(parents=True)
    link = category / "20260501T000000000000"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    plan = prune_backups(
        backup_root,
        confirm=True,
        now=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    assert link not in plan.delete
    assert (outside / "do-not-delete.txt").exists()