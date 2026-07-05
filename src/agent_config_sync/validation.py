import re
from pathlib import Path

from .config import ConfigError


_SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

_WINDOWS_RESERVED = {
    'con', 'prn', 'aux', 'nul',
    'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
    'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9',
}


def validate_skill_name(name: str) -> str:
    if not isinstance(name, str):
        raise ConfigError("skill name must be a string")
    if not 1 <= len(name) <= 64 or not _SKILL_NAME.fullmatch(name):
        raise ConfigError(
            "invalid skill name: use 1-64 lowercase letters, numbers, and "
            "single hyphens; no paths, dots, spaces, or underscores"
        )
    if name in _WINDOWS_RESERVED:
        raise ConfigError(f"invalid skill name '{name}': reserved on Windows")
    return name


def resolve_within(root: Path, *parts: str | Path, label: str = "path") -> Path:
    base = root.expanduser().resolve()
    resolved = base.joinpath(*parts).resolve()
    if resolved == base or resolved.is_relative_to(base):
        return resolved
    raise ConfigError(f'{label} escapes allowed root: {resolved}')
