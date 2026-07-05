import json
from pathlib import Path

from .audit import append_audit
from .config import Config, ConfigError
from .fsutil import atomic_write, backup, default_stamp, sha256_text
from .neutralize import (
    NeutralLanguageError,
    find_vendor_terms,
    read_skill_variants,
    reconcile_skill,
)
from .secrets import SecretFoundError, find_secrets
from .validation import resolve_within, validate_skill_name


def propose_enrollment(config: Config, name: str, canonical: str | None = None) -> str:
    name = validate_skill_name(name)
    variants = read_skill_variants(config, name)
    return reconcile_skill(variants, canonical=canonical)


def _render_managed_skills_text(targets_path: Path, names: list[str]) -> str:
    names = [validate_skill_name(name) for name in names]
    text = targets_path.read_text("utf-8")
    marker = "\nmanaged_skills:"
    idx = text.find(marker)
    if idx != -1:
        # This rewrite replaces everything from `managed_skills:` to EOF. That is
        # safe ONLY if nothing but the list (items / blanks / comments) follows.
        # A trailing top-level key would be silently deleted — refuse instead.
        tail_lines = text[idx + 1:].splitlines()[1:]  # skip the key line itself
        for ln in tail_lines:
            stripped = ln.strip()
            if not stripped or stripped == "[]":
                continue
            if ln[0].isspace() or stripped.startswith("#"):
                continue
            raise ConfigError(
                "managed_skills must be the last top-level key in targets.yaml; "
                f"refusing to rewrite — found trailing content: {ln!r}"
            )
        head = text[: idx + 1]
    else:
        head = text if text.endswith("\n") else text + "\n"
    ordered = sorted(set(names))
    if ordered:
        block = "managed_skills:\n" + "".join(
            f"  - {json.dumps(n)}\n" for n in ordered
        )
    else:
        block = "managed_skills: []\n"
    return head + block


def update_managed_skills(targets_path: Path, names: list[str]) -> None:
    atomic_write(targets_path, _render_managed_skills_text(targets_path, names))


def _audit_source_write(config: Config, stamp: str, path: Path, kind: str, target: str, content: str) -> None:
    append_audit(
        config.repo_root,
        {
            "stamp": stamp,
            "runtime": "source",
            "kind": kind,
            "target": target,
            "dest": str(path),
            "content_sha256": sha256_text(content),
        },
    )


def enroll_skill(config: Config, name: str, body: str) -> None:
    name = validate_skill_name(name)
    terms = find_vendor_terms(body, [*config.managed_skills, name])
    if terms:
        raise NeutralLanguageError(name, terms)
    secrets = find_secrets(body)
    if secrets:
        raise SecretFoundError(name, secrets)

    canonical = resolve_within(
        config.repo_root / "skills", name, "SKILL.md", label="skill source"
    )
    targets_path = config.repo_root / "config" / "targets.yaml"
    targets_content = _render_managed_skills_text(
        targets_path,
        [*config.managed_skills, name],
    )

    stamp = default_stamp()
    backup_root = config.repo_root / ".backups"
    backup(canonical, backup_root, "source", stamp)
    backup(targets_path, backup_root, "source", stamp)
    atomic_write(canonical, body)
    _audit_source_write(config, stamp, canonical, "enroll-skill", name, body)
    atomic_write(targets_path, targets_content)
    _audit_source_write(
        config, stamp, targets_path, "update-managed-skills", name, targets_content
    )
