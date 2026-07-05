"""Session-start sensing: what changed, and which command resolves it.

Read-only. The brief output is consumed by an AI runtime at session start, so
it is fixed, deterministic phrasing that instructs the AI to ask the operator
before running anything. This module must never crash the session hook: gate
errors raised during dry-run planning are converted into findings.
"""

import json
from dataclasses import asdict, dataclass

from .config import Config, ConfigError
from .neutralize import NeutralLanguageError
from .project import project
from .secrets import SecretFoundError
from .skills import CompanionFileError, project_skills
from .validation import validate_skill_name


@dataclass
class Finding:
    kind: str      # source-ahead | runtime-edit | unmanaged-skill | gate-failure
    runtime: str   # runtime name, or "source" for gate failures
    target: str    # file / skill identifier
    keep: str      # command that applies or preserves the change ("" if n/a)
    discard: str   # command that discards the change ("" if n/a)


def scan(config: Config) -> list[Finding]:
    findings: list[Finding] = []

    try:
        for a in project(config, dry_run=True):
            if a.kind in ("update", "create"):
                findings.append(
                    Finding("source-ahead", a.runtime, str(a.dest),
                            "agent-config-sync project", "")
                )
            elif a.kind == "drift":
                findings.append(
                    Finding("runtime-edit", a.runtime, str(a.dest),
                            f"agent-config-sync promote {a.runtime}",
                            f"agent-config-sync project {a.runtime} --force")
                )
    except SecretFoundError as exc:
        findings.append(Finding("gate-failure", "source", "instructions",
                                f"fix source content: {exc}", ""))
    except ConfigError as exc:
        findings.append(Finding("gate-failure", "source", "config",
                                f"fix config: {exc}", ""))

    try:
        for a in project_skills(config, dry_run=True):
            if a.kind in ("update", "create"):
                findings.append(
                    Finding("source-ahead", a.runtime, f"{a.name}/{a.relpath}",
                            "agent-config-sync project", "")
                )
            elif a.kind == "drift":
                if a.relpath == "SKILL.md":
                    keep = f"agent-config-sync enroll {a.name} --body-file {a.dest}"
                else:
                    keep = (f"review {a.dest} and copy it into skills/{a.name}/ "
                            "in the source repo")
                findings.append(
                    Finding("runtime-edit", a.runtime, f"{a.name}/{a.relpath}",
                            keep,
                            f"agent-config-sync project {a.runtime} --force")
                )
    except (NeutralLanguageError, SecretFoundError, CompanionFileError, ConfigError) as exc:
        findings.append(Finding("gate-failure", "source", "skills",
                                f"fix source content: {exc}", ""))

    managed = set(config.managed_skills)
    ignored = set(config.sense_ignore_skills)
    for rt_name, rt in config.runtimes.items():
        base = rt.skills_dest
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or not (child / "SKILL.md").exists():
                continue
            name = child.name
            if name in managed or name in ignored:
                continue
            try:
                validate_skill_name(name)
            except ConfigError:
                findings.append(Finding("unmanaged-skill", rt_name, name, "", ""))
                continue
            findings.append(
                Finding("unmanaged-skill", rt_name, name,
                        f"agent-config-sync enroll {name} --from {rt_name}", "")
            )
    return findings


def format_brief(findings: list[Finding]) -> str:
    if not findings:
        return "agent-config-sync sense: all runtimes in sync; no unmanaged skills."

    lines = [
        f"agent-config-sync sense: {len(findings)} finding(s). "
        "Ask the operator before running any command below."
    ]

    source_ahead = [f for f in findings if f.kind == "source-ahead"]
    if source_ahead:
        examples = ", ".join(f"{f.runtime}:{f.target}" for f in source_ahead[:3])
        more = f" (+{len(source_ahead) - 3} more)" if len(source_ahead) > 3 else ""
        lines.append(
            f"- source ahead for {len(source_ahead)} file(s): {examples}{more} "
            "-> to apply: agent-config-sync project"
        )

    for f in findings:
        if f.kind == "runtime-edit":
            lines.append(
                f"- runtime edit in {f.runtime}:{f.target} "
                f"-> keep: {f.keep} | discard: {f.discard}"
            )
        elif f.kind == "unmanaged-skill":
            if f.keep:
                lines.append(
                    f"- unmanaged skill '{f.target}' in {f.runtime} "
                    f"-> enroll: {f.keep} (or add it to sense_ignore_skills)"
                )
            else:
                lines.append(
                    f"- unmanaged skill '{f.target}' in {f.runtime} "
                    "-> name not enrollable as-is; rename to lowercase/hyphen "
                    "grammar first (or add it to sense_ignore_skills)"
                )
        elif f.kind == "gate-failure":
            lines.append(f"- gate failure in {f.target}: {f.keep}")

    return "\n".join(lines)


def format_json(findings: list[Finding]) -> str:
    return json.dumps(
        {"count": len(findings), "findings": [asdict(f) for f in findings]},
        indent=2,
    )
