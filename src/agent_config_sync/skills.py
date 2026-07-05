from dataclasses import dataclass
from pathlib import Path

from .audit import append_audit
from .config import Config
from .fsutil import atomic_write, backup, default_stamp, sha256_text
from .neutralize import NeutralLanguageError, find_vendor_terms
from .project import ForceScopeError
from .secrets import SecretFoundError, find_secrets
from .state import load_state, save_state
from .validation import resolve_within, validate_skill_name

REFERENCE_FILENAMES = {
    "claude": "claude-code-tools.md",
    "codex": "codex-tools.md",
    "gemini": "gemini-tools.md",
}
_ADAPTER_RELPATHS = {f"references/{fn}" for fn in REFERENCE_FILENAMES.values()}

# Companion payloads are text/reference material only. Executable content
# (scripts, binaries) stays outside the projection trust boundary until it
# gets its own reviewed design.
COMPANION_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".toml"}


class CompanionFileError(Exception):
    def __init__(self, skill: str, relpath: str, reason: str):
        self.skill = skill
        self.relpath = relpath
        super().__init__(f"skill '{skill}' companion '{relpath}': {reason}")


def companion_files(config: Config, name: str) -> dict[str, str]:
    """Enumerate source companion files for a managed skill.

    Everything under skills/<name>/ except SKILL.md projects verbatim to every
    runtime. Fail closed: hidden paths are skipped, non-text extensions and
    adapter-name collisions are refused, and each file must pass the same
    neutral-language gate as the body (secrets are linted by project_skills).
    """
    name = validate_skill_name(name)
    source_dir = resolve_within(config.repo_root / "skills", name, label="skill source")
    out: dict[str, str] = {}
    resolved_root = source_dir.resolve()
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir).as_posix()
        if rel == "SKILL.md":
            continue
        if any(part.startswith(".") for part in path.relative_to(source_dir).parts):
            continue
        # Source containment: refuse symlinks (or any resolution) escaping the
        # skill's source directory — content must come from the reviewed tree.
        if not path.resolve().is_relative_to(resolved_root):
            raise CompanionFileError(
                name, rel, "resolves outside the skill source directory"
            )
        # Case-insensitive: Windows paths would let References/Claude-Code-Tools.md
        # shadow the real adapter at the destination.
        if rel.lower() in _ADAPTER_RELPATHS:
            raise CompanionFileError(
                name, rel, "collides with a runtime adapter filename"
            )
        if path.suffix.lower() not in COMPANION_EXTENSIONS:
            allowed = ", ".join(sorted(COMPANION_EXTENSIONS))
            raise CompanionFileError(
                name, rel, f"extension not allowed (text-only allowlist: {allowed})"
            )
        try:
            content = path.read_text("utf-8")
        except UnicodeDecodeError as exc:
            raise CompanionFileError(
                name, rel, f"not valid UTF-8 text ({exc.reason})"
            ) from exc
        terms = find_vendor_terms(content, config.managed_skills)
        if terms:
            raise NeutralLanguageError(f"{name}/{rel}", terms)
        out[rel] = content
    return out


class SkillDriftError(Exception):
    def __init__(self, items: list[str]):
        self.items = items
        super().__init__(f"un-promoted skill edits in: {', '.join(items)}")


@dataclass
class SkillAction:
    runtime: str
    name: str
    relpath: str
    kind: str
    dest: Path
    content: str


def skill_files(config: Config, runtime: str, name: str) -> dict[str, str]:
    name = validate_skill_name(name)
    body_path = resolve_within(
        config.repo_root / "skills", name, "SKILL.md", label="skill source"
    )
    body = body_path.read_text("utf-8")
    # Re-lint the body at projection: enrollment gates the front door, but a
    # direct edit to the canonical source would otherwise fan out ungated.
    # The per-runtime adapter is the only intentionally vendor-specific file.
    body_terms = find_vendor_terms(body, config.managed_skills)
    if body_terms:
        raise NeutralLanguageError(name, body_terms)
    adapter_name = REFERENCE_FILENAMES[runtime]
    adapter = (config.repo_root / "references" / adapter_name).read_text("utf-8")
    return {
        "SKILL.md": body,
        f"references/{adapter_name}": adapter,
        **companion_files(config, name),
    }


def _classify(content: str, dest: Path, last_hash: str | None, force: bool) -> str:
    if not dest.exists():
        return "create"
    current = dest.read_text("utf-8")
    if current == content:
        return "unchanged"
    if last_hash is not None and sha256_text(current) == last_hash:
        return "update"
    return "forced" if force else "drift"


def project_skills(
    config: Config,
    *,
    dry_run: bool = False,
    force: bool = False,
    stamp: str | None = None,
    only: str | None = None,
) -> list[SkillAction]:
    if only is not None and only not in config.runtimes:
        raise ValueError(f"unknown runtime '{only}'")
    selected = (
        {only: config.runtimes[only]} if only is not None else config.runtimes
    )

    state = load_state(config.repo_root)
    skill_state = state.setdefault("skills", {})

    plan: list[SkillAction] = []
    for runtime in selected:
        rt = config.runtimes[runtime]
        rt_state = skill_state.setdefault(runtime, {})
        for name in config.managed_skills:
            name = validate_skill_name(name)
            for relpath, content in skill_files(config, runtime, name).items():
                matches = find_secrets(content)
                if matches:
                    raise SecretFoundError(runtime, matches)
                key = f"{name}/{relpath}"
                dest = resolve_within(rt.skills_dest, name, relpath, label=f"{runtime} skill")
                kind = _classify(content, dest, rt_state.get(key), force)
                plan.append(SkillAction(runtime, name, relpath, kind, dest, content))

    drifted = [
        f"{a.runtime}:{a.name}/{a.relpath}" for a in plan if a.kind == "drift"
    ]
    if drifted and not dry_run:
        raise SkillDriftError(drifted)
    # Mirror project()'s guard: a blanket --force (no runtime named) must not
    # clobber more than one drifted skill file in a single sweep — make the
    # operator scope it so an unrelated skill learning is never nuked silently.
    forced = [
        f"{a.runtime}:{a.name}/{a.relpath}" for a in plan if a.kind == "forced"
    ]
    if force and only is None and len(forced) > 1 and not dry_run:
        raise ForceScopeError(forced)
    if dry_run:
        return plan

    stamp = stamp or default_stamp()
    backup_root = config.repo_root / ".backups"
    for action in plan:
        if action.kind == "drift":
            continue
        if action.kind == "unchanged":
            # Baseline files that already match the source. Without this, a
            # skill enrolled verbatim never gets a recorded hash, and the next
            # legitimate source edit is misclassified as un-promoted drift.
            key = f"{action.name}/{action.relpath}"
            content_hash = sha256_text(action.content)
            if skill_state[action.runtime].get(key) != content_hash:
                skill_state[action.runtime][key] = content_hash
            continue
        if action.dest.exists():
            backup(action.dest, backup_root, action.runtime, stamp)
        atomic_write(action.dest, action.content)
        content_hash = sha256_text(action.content)
        skill_state[action.runtime][f"{action.name}/{action.relpath}"] = content_hash
        save_state(config.repo_root, state)
        append_audit(
            config.repo_root,
            {
                "stamp": stamp,
                "runtime": action.runtime,
                "kind": action.kind,
                "force": force,
                "dest": str(action.dest),
                "skill": action.name,
                "relpath": action.relpath,
                "content_sha256": content_hash,
            },
        )

    save_state(config.repo_root, state)
    return plan
