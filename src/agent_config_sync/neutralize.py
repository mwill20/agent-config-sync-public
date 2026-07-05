import re

from .config import Config
from .validation import resolve_within, validate_skill_name

# Per-vendor tool names and invocation forms a *neutral* skill body must not
# contain. Mirrors the deterministic-gate model of secrets.find_secrets: an AI
# may PROPOSE a neutral rewrite, but this lint DECIDES whether it is clean.
#
# Two classes are matched differently to stay both complete and low-false-positive:
#  1. Common-English tool names (Skill, Read, Write, Edit, Task, ...) are flagged
#     ONLY in the "<Name> tool" phrasing — bare-word matching would trip on
#     ordinary prose ("read the file", "the right tool").
#  2. Unique identifiers that never occur in neutral prose (apply_patch, mcp__*,
#     TodoWrite, ...) are matched bare.
# This is a curated list; add new runtime tools here as they appear (see
# docs/LIMITATIONS.md — the lint reduces, not eliminates, non-neutral leakage).
_NAMED_TOOLS = (
    r"Skill|Bash|Edit|Write|Read|Glob|Grep|Task|Agent|MultiEdit|NotebookRead|"
    r"BashOutput|KillShell"
)
_VENDOR_TERMS = [
    rf"\b(?:{_NAMED_TOOLS}) tool\b",
    r"mcp__[A-Za-z0-9_]+",
    r"\bapply_patch\b",
    r"\bactivate_skill\b",
    r"\bgrep_search\b",
    r"\blist_dir\b",
    r"\brun_shell_command\b",
    r"\bgoogle_web_search\b",
    r"\bshell_command\b",
    r"\brequest_user_input\b",
    r"\bweb(?:__|\.)run\b",
    r"\bimage_gen\b",
    r"\bStrReplace\b",
    r"\bstr_replace_editor\b",
    r"\bTodoWrite\b",
    r"\bNotebookEdit\b",
    r"\bWebFetch\b",
    r"\bWebSearch\b",
    r"\bsubagent_type\b",
    r"functions\.[A-Za-z_]+",
]
_VENDOR_PATTERNS = [re.compile(t, re.IGNORECASE) for t in _VENDOR_TERMS]
# A slash-command reference like `/critique` (start of line or after whitespace,
# at least two letters so it does not catch paths like `/x`).
_SLASH = re.compile(r"(?:(?<=\s)|^)(/[a-z][a-z0-9-]{2,})", re.MULTILINE)


class NeutralLanguageError(Exception):
    def __init__(self, skill: str, terms: list[str]):
        self.skill = skill
        self.terms = terms
        super().__init__(f"skill '{skill}' contains vendor-specific terms: {terms}")


def find_vendor_terms(text: str, skill_names: tuple[str, ...] | list[str] = ()) -> list[str]:
    hits: list[str] = []
    for pattern in _VENDOR_PATTERNS:
        for m in pattern.finditer(text):
            hits.append(m.group(0))
    for m in _SLASH.finditer(text):
        hits.append(m.group(1))
    # A slash followed by a KNOWN skill name is a slash-command reference no
    # matter how it is wrapped (backticks, quotes, parens) — the whitespace
    # rule above misses `/critique`. The (?<![\w/]) guard keeps genuine paths
    # and URLs (docs/threat-model, https://x/y) out.
    for name in skill_names:
        for m in re.finditer(rf"(?<![\w/])(/{re.escape(name)})\b", text):
            hits.append(m.group(1))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


class ReconciliationError(Exception):
    def __init__(self, runtimes: list[str], skill: str = ""):
        self.skill = skill
        self.runtimes = runtimes
        super().__init__(
            f"skill '{skill}' differs across runtimes {runtimes}; "
            "choose a canonical source to enroll"
        )


def read_skill_variants(config: Config, name: str) -> dict[str, str]:
    name = validate_skill_name(name)
    variants: dict[str, str] = {}
    for runtime, rt in config.runtimes.items():
        path = resolve_within(rt.skills_dest, name, "SKILL.md", label=f"{runtime} skill")
        if path.exists():
            variants[runtime] = path.read_text("utf-8")
    return variants


def reconcile_skill(variants: dict[str, str], canonical: str | None = None) -> str:
    if not variants:
        raise ReconciliationError([], "")
    if canonical is not None:
        return variants[canonical]
    bodies = set(variants.values())
    if len(bodies) == 1:
        return next(iter(bodies))
    raise ReconciliationError(sorted(variants.keys()))
