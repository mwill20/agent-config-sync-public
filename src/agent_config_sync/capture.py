import difflib
from dataclasses import dataclass
from pathlib import Path

from .audit import append_audit
from .config import Config
from .enroll import enroll_skill
from .fsutil import atomic_write, backup, default_stamp, sha256_text
from .neutralize import NeutralLanguageError, find_vendor_terms
from .secrets import SecretFoundError, find_secrets
from .validation import resolve_within, validate_skill_name


@dataclass
class CaptureResult:
    kind: str  # "standard" | "skill"
    target: str  # "core" / runtime name, or skill name
    diff: str
    applied: bool


def _standard_path(config: Config, target: str) -> Path:
    if target == "core":
        return config.repo_root / "_shared" / "core.md"
    if target in config.runtimes:
        return config.runtimes[target].overlay
    raise ValueError(
        f"unknown standard target '{target}' (use 'core' or a runtime name)"
    )


def _unified(before: str, after: str, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile=str(path),
            tofile=str(path),
        )
    )


def _write_source(config: Config, path: Path, content: str, *, target: str) -> None:
    stamp = default_stamp()
    backup(path, config.repo_root / ".backups", "source", stamp)
    atomic_write(path, content)
    append_audit(
        config.repo_root,
        {
            "stamp": stamp,
            "runtime": "source",
            "kind": "capture",
            "target": target,
            "dest": str(path),
            "content_sha256": sha256_text(content),
        },
    )


def capture_standard(
    config: Config, target: str, text: str, *, confirm: bool = False
) -> CaptureResult:
    """Capture a standard into the shared source (core) or a runtime overlay.

    Deterministic gate runs BEFORE any write, even in dry-run: a secret aborts
    regardless of confirm. Dry-run (confirm=False) returns the diff without writing.
    """
    secrets = find_secrets(text)
    if secrets:
        raise SecretFoundError(target, secrets)  # binding gate, pre-write
    path = _standard_path(config, target)
    before = path.read_text("utf-8") if path.exists() else ""
    sep = "" if (not before or before.endswith("\n")) else "\n"
    after = before + sep + text.strip("\n") + "\n"
    diff = _unified(before, after, path)
    if confirm:
        _write_source(config, path, after, target=target)
    return CaptureResult("standard", target, diff, confirm)


def capture_skill(
    config: Config, name: str, body: str, *, confirm: bool = False
) -> CaptureResult:
    """Capture a skill body into the source. Binding gates (neutral + secret) run
    before any write, even in dry-run. On confirm, delegates to enroll_skill."""
    name = validate_skill_name(name)
    terms = find_vendor_terms(body, [*config.managed_skills, name])
    if terms:
        raise NeutralLanguageError(name, terms)
    secrets = find_secrets(body)
    if secrets:
        raise SecretFoundError(name, secrets)
    path = resolve_within(
        config.repo_root / "skills", name, "SKILL.md", label="skill source"
    )
    before = path.read_text("utf-8") if path.exists() else ""
    diff = _unified(before, body, path)
    if confirm:
        enroll_skill(config, name, body)
    return CaptureResult("skill", name, diff, confirm)
