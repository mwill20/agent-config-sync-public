import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_ALLOWED_ROOTS = [
    Path.home() / ".claude",
    Path.home() / ".codex",
    Path.home() / ".gemini",
]


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    name: str
    instruction_dest: Path
    overlay: Path
    skills_dest: Path


@dataclass(frozen=True)
class Config:
    repo_root: Path
    runtimes: dict[str, "RuntimeConfig"]
    managed_skills: list[str]
    # Skill names sense() must not flag as enrollment candidates — deliberate,
    # operator-recorded exclusions (e.g. a skill that cannot be enrolled yet).
    sense_ignore_skills: list[str] = field(default_factory=list)


def _resolve_allowed(allowed_roots: list[Path] | None) -> list[Path]:
    if allowed_roots is not None:
        roots = allowed_roots
    else:
        env = os.environ.get("AGENT_CONFIG_SYNC_ALLOWED_ROOTS")
        roots = [Path(p) for p in env.split(os.pathsep)] if env else DEFAULT_ALLOWED_ROOTS
    return [Path(r).expanduser().resolve() for r in roots]


def _validate_dest(raw: str, allowed: list[Path]) -> Path:
    resolved = Path(raw).expanduser().resolve()
    for root in allowed:
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    raise ConfigError(f"Destination '{resolved}' is not under an allowed runtime root")


def _validate_source(raw: str, repo_root: Path) -> Path:
    resolved = (repo_root / raw).resolve()
    if resolved == repo_root.resolve() or resolved.is_relative_to(repo_root.resolve()):
        return resolved
    raise ConfigError(f"Source path '{resolved}' is not under the repo root")


def load_config(repo_root: Path, allowed_roots: list[Path] | None = None) -> Config:
    from .validation import validate_skill_name

    allowed = _resolve_allowed(allowed_roots)
    raw = yaml.safe_load((repo_root / "config" / "targets.yaml").read_text("utf-8"))
    if not raw or "runtimes" not in raw:
        raise ConfigError("targets.yaml missing 'runtimes'")

    runtimes: dict[str, RuntimeConfig] = {}
    for name, entry in raw["runtimes"].items():
        try:
            instruction = entry["instruction_dest"]
            overlay = entry["overlay"]
            skills = entry["skills_dest"]
        except (KeyError, TypeError) as exc:
            raise ConfigError(f"runtime '{name}' missing required key: {exc}")
        runtimes[name] = RuntimeConfig(
            name=name,
            instruction_dest=_validate_dest(instruction, allowed),
            overlay=_validate_source(overlay, repo_root),
            skills_dest=_validate_dest(skills, allowed),
        )

    managed = raw.get('managed_skills') or []
    if not isinstance(managed, list):
        raise ConfigError('managed_skills must be a list')
    validated_skills: list[str] = []
    seen: set[str] = set()
    for skill in managed:
        skill = validate_skill_name(skill)
        if skill in seen:
            raise ConfigError(f"duplicate managed skill '{skill}'")
        seen.add(skill)
        validated_skills.append(skill)

    ignored_raw = raw.get("sense_ignore_skills") or []
    if not isinstance(ignored_raw, list):
        raise ConfigError("sense_ignore_skills must be a list")
    ignored: list[str] = []
    for skill in ignored_raw:
        skill = validate_skill_name(skill)
        if skill not in ignored:
            ignored.append(skill)

    return Config(
        repo_root=repo_root,
        runtimes=runtimes,
        managed_skills=validated_skills,
        sense_ignore_skills=ignored,
    )
