import argparse
from contextlib import nullcontext
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .audit import append_audit
from .check import check
from .capture import capture_skill, capture_standard
from .config import ConfigError, load_config
from .doctor import doctor
from .enroll import enroll_skill, propose_enrollment
from .fsutil import default_stamp, prune_backups
from .lock import LockError, repo_lock
from .neutralize import NeutralLanguageError, ReconciliationError, find_vendor_terms
from .project import DriftError, ForceScopeError, project
from .promote import (
    PromoteAmbiguousChange,
    PromoteBaselineMissing,
    PromoteConflict,
    PromoteSourceBehind,
    detect_divergence,
    promote_instruction,
)
from .secrets import SecretFoundError
from .sense import format_brief, format_json, scan
from .settingsedit import HookInstallError, install_claude_hook, install_codex_hook
from .skills import SkillDriftError, project_skills
from .status import status


def _repo_root() -> Path:
    env = os.environ.get("AGENT_CONFIG_SYNC_REPO")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="backslashreplace")
    except (OSError, ValueError):
        pass




def _mutation_lock(config, enabled: bool, command: str):
    if not enabled:
        return nullcontext()
    return repo_lock(config.repo_root, command=command)


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(prog="agent-config-sync")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("project", help="render source into each runtime")
    p.add_argument(
        "runtime",
        nargs="?",
        help="limit projection to a single runtime (required to scope --force "
        "when more than one runtime has drifted)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    sub.add_parser("check", help="exit non-zero if any runtime is stale")
    se = sub.add_parser(
        "sense",
        help="read-only session-start sensing: what changed and which command resolves it",
    )
    se.add_argument(
        "--json",
        action="store_true",
        help="machine-readable findings (for watchers and automation)",
    )
    ov = sub.add_parser(
        "overlap",
        help="read-only similarity report: a candidate skill vs the managed set",
    )
    ov.add_argument("name", help="candidate skill name")
    ov.add_argument(
        "--from",
        dest="from_runtime",
        help="read the candidate body from this runtime's skills directory",
    )
    ov.add_argument("--body-file", dest="body_file", help="read the candidate body from a file")
    ov.add_argument("--top", type=int, default=5, help="rows to show (default 5)")
    wo = sub.add_parser(
        "watch-once",
        help="one ambient-watcher cycle: run sense, update the pending-findings "
        "file, print a notification title and body (for the scheduled wrapper)",
    )
    wo.add_argument(
        "--pending-file",
        dest="pending_file",
        help="override the pending-findings file path (default: "
        "%%LOCALAPPDATA%%/agent-config-sync/pending.json)",
    )
    sub.add_parser(
        "mcp-serve",
        help="run a read-only MCP stdio server exposing sense/check/status tools",
    )
    sub.add_parser("status", help="show per-runtime sync state")
    sub.add_parser("doctor", help="plain-language environment + sync health check")
    e = sub.add_parser("enroll", help="enroll a skill into the source of truth")
    e.add_argument("name", help="skill name (directory under each runtime's skills/)")
    e.add_argument(
        "--from",
        dest="from_runtime",
        help="canonical runtime to take the body from when variants differ",
    )
    e.add_argument(
        "--body-file",
        dest="body_file",
        help="path to the human-approved neutral SKILL.md body to commit",
    )
    c = sub.add_parser(
        "capture", help="capture a skill or standard into the source (dry-run by default)"
    )
    c.add_argument("kind", choices=["standard", "skill"])
    c.add_argument("--target", help="standard: 'core' (shared) or a runtime name")
    c.add_argument("--name", help="skill: the skill name")
    c.add_argument("--text-file", dest="text_file", help="standard: file with the text")
    c.add_argument("--body-file", dest="body_file", help="skill: file with the SKILL.md body")
    c.add_argument(
        "--confirm",
        action="store_true",
        help="apply to source and project to all runtimes (otherwise dry-run)",
    )
    pr = sub.add_parser(
        "promote", help="lift a runtime's out-of-band edit back into the source"
    )
    pr.add_argument("runtime", nargs="?", help="runtime to promote from (omit to scan all)")
    pr.add_argument("--target", help="'core' (shared) or a runtime name (vendor-specific)")
    pr.add_argument(
        "--confirm", action="store_true", help="apply + reproject (otherwise dry-run)"
    )
    ih = sub.add_parser(
        "install-hooks", help="install the startup drift-check hook into each runtime"
    )
    ih.add_argument(
        "--claude-settings",
        dest="claude_settings",
        help="path to Claude settings.json (default ~/.claude/settings.json)",
    )
    ih.add_argument(
        "--codex-config",
        dest="codex_config",
        help="path to Codex config.toml (default ~/.codex/config.toml)",
    )
    ih.add_argument(
        "--dry-run",
        action="store_true",
        help="show hook targets and commands without writing runtime config",
    )
    pb = sub.add_parser(
        "prune-backups", help="prune old .backups snapshots (dry-run by default)"
    )
    pb.add_argument(
        "--confirm",
        action="store_true",
        help="delete eligible backup snapshots (otherwise dry-run)",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(_repo_root())
    except ConfigError as exc:
        print(f"Config error: {exc}. Check config/targets.yaml and the allowlist.")
        return 3

    if args.cmd == "project":
        if args.runtime is not None and args.runtime not in config.runtimes:
            print(
                f"Unknown runtime '{args.runtime}'. "
                f"Known: {', '.join(config.runtimes)}."
            )
            return 2
        try:
            with _mutation_lock(config, not args.dry_run, "project"):
                # Blanket --force spans instructions AND skills. Neither module
                # sees the other's plan, so count forced targets across both
                # here and refuse a bare --force that would clobber more than one
                # drifted target (instruction or skill) in a single sweep.
                if args.force and args.runtime is None and not args.dry_run:
                    forced = [
                        a.runtime
                        for a in project(config, dry_run=True, force=True)
                        if a.kind == "forced"
                    ] + [
                        f"{a.runtime}:{a.name}/{a.relpath}"
                        for a in project_skills(config, dry_run=True, force=True)
                        if a.kind == "forced"
                    ]
                    if len(forced) > 1:
                        print(
                            f"Refusing a blanket --force across {', '.join(forced)}. "
                            "Name one runtime, e.g. `project claude --force`."
                        )
                        return 4
                plan = project(
                    config,
                    dry_run=args.dry_run,
                    force=args.force,
                    only=args.runtime,
                )
                skill_plan = project_skills(
                    config,
                    dry_run=args.dry_run,
                    force=args.force,
                    only=args.runtime,
                )
        except LockError as exc:
            print(f"Lock error: {exc}")
            return 5
        except (DriftError, SkillDriftError) as exc:
            targets = exc.runtimes if isinstance(exc, DriftError) else exc.items
            print(
                f"Refusing to overwrite un-promoted changes in: {', '.join(targets)}. "
                "Run promote (Plan 3) or pass --force."
            )
            return 2
        except ForceScopeError as exc:
            print(
                f"Refusing a blanket --force across {', '.join(exc.runtimes)}. "
                "Name one runtime, e.g. `project claude --force`."
            )
            return 4
        except SecretFoundError as exc:
            print(f"Aborted: secret-like content for '{exc.runtime}'. No files written.")
            return 3
        except NeutralLanguageError as exc:
            print(
                f"Aborted: '{exc.skill}' contains vendor-specific terms: "
                f"{', '.join(exc.terms)}. Neutralize the source body and retry. "
                "No files written."
            )
            return 3
        for action in plan:
            print(f"{action.kind:10} {action.runtime} -> {action.dest}")
        for action in skill_plan:
            print(f"{action.kind:10} {action.runtime} {action.name} -> {action.dest}")
        return 0

    if args.cmd == "check":
        try:
            stale = check(config)
        except NeutralLanguageError as exc:
            print(
                f"GATE FAILURE: '{exc.skill}' contains vendor-specific terms: "
                f"{', '.join(exc.terms)}. Neutralize the source body."
            )
            return 3
        if stale:
            print("STALE: " + ", ".join(stale))
            return 1
        print("All runtimes in sync.")
        return 0

    if args.cmd == "sense":
        findings = scan(config)
        print(format_json(findings) if args.json else format_brief(findings))
        return 1 if findings else 0

    if args.cmd == "overlap":
        from .overlap import compare, format_report
        from .validation import validate_skill_name

        try:
            name = validate_skill_name(args.name)
        except ConfigError as exc:
            print(f"Aborted: {exc}")
            return 2
        if args.body_file:
            body = Path(args.body_file).read_text("utf-8")
        elif args.from_runtime:
            if args.from_runtime not in config.runtimes:
                print(
                    f"Unknown runtime '{args.from_runtime}'. "
                    f"Known: {', '.join(config.runtimes)}."
                )
                return 2
            path = config.runtimes[args.from_runtime].skills_dest / name / "SKILL.md"
            if not path.exists():
                print(f"No SKILL.md for '{name}' in {args.from_runtime}.")
                return 2
            body = path.read_text("utf-8")
        else:
            print("overlap needs --from <runtime> or --body-file <path>.")
            return 2
        scores = compare(body, config)
        print(format_report(scores, top=args.top))
        return 1 if any(s.flagged for s in scores) else 0

    if args.cmd == "watch-once":
        from .watcher import watch_once

        pending = Path(args.pending_file) if args.pending_file else None
        title, body, code = watch_once(config, pending_path=pending)
        print(title)
        print(body)
        return code

    if args.cmd == "mcp-serve":
        from .mcp_server import serve

        return serve(config)

    if args.cmd == "status":
        for name, state in status(config).items():
            print(f"{state:9} {name}")
        return 0

    if args.cmd == "doctor":
        for name, st, detail in doctor(config):
            print(f"{st:10} {name:16} {detail}")
        return 0

    if args.cmd == "enroll":
        if args.body_file:
            body = Path(args.body_file).read_text("utf-8")
            try:
                enroll_skill(config, args.name, body)
            except NeutralLanguageError as exc:
                print(
                    f"Aborted: skill '{exc.skill}' contains vendor-specific terms: "
                    f"{', '.join(exc.terms)}. Neutralize the body and retry."
                )
                return 3
            except SecretFoundError as exc:
                print(
                    f"Aborted: secret-like content in skill '{exc.runtime}'. "
                    "Nothing enrolled."
                )
                return 3
            except ConfigError as exc:
                print(f"Aborted: {exc}")
                return 2
            print(f"Enrolled '{args.name}'. Run `project` to fan it out.")
            return 0
        try:
            body = propose_enrollment(config, args.name, canonical=args.from_runtime)
        except ReconciliationError as exc:
            print(
                f"Skill '{args.name}' differs across {', '.join(exc.runtimes)}. "
                "Re-run with --from <runtime> to pick the canonical source."
            )
            return 3
        except ConfigError as exc:
            print(f"Aborted: {exc}")
            return 2
        terms = find_vendor_terms(body, [*config.managed_skills, args.name])
        print(f"--- proposed body for '{args.name}' ---")
        print(body)
        if terms:
            print(f"--- vendor terms to neutralize: {', '.join(terms)} ---")
        print(
            "Review/neutralize, save to a file, then "
            f"`enroll {args.name} --body-file <path>`."
        )
        return 0

    if args.cmd == "capture":
        try:
            with _mutation_lock(config, args.confirm, "capture"):
                if args.kind == "standard":
                    if not args.target or not args.text_file:
                        print("capture standard needs --target and --text-file.")
                        return 2
                    text = Path(args.text_file).read_text("utf-8")
                    result = capture_standard(config, args.target, text, confirm=args.confirm)
                else:
                    if not args.name or not args.body_file:
                        print("capture skill needs --name and --body-file.")
                        return 2
                    body = Path(args.body_file).read_text("utf-8")
                    result = capture_skill(config, args.name, body, confirm=args.confirm)
                print(result.diff or "(no change)")
                if not result.applied:
                    print("\nDRY-RUN - nothing written. Re-run with --confirm to apply + project.")
                    return 0
                try:
                    config = load_config(_repo_root())
                    project(config)
                    project_skills(config)
                except (DriftError, SkillDriftError) as exc:
                    targets = exc.runtimes if isinstance(exc, DriftError) else exc.items
                    print(
                        f"Applied source for '{result.target}', but projection refused drift in: "
                        f"{', '.join(targets)}. Resolve drift, then run `agent-config-sync project`."
                    )
                    return 2
                except ForceScopeError as exc:
                    print(
                        f"Applied source for '{result.target}', but projection needs scoped force for: "
                        f"{', '.join(exc.runtimes)}. Resolve drift, then run `agent-config-sync project`."
                    )
                    return 4
                except (SecretFoundError, ConfigError) as exc:
                    print(
                        f"Applied source for '{result.target}', but projection failed: {exc}. "
                        "Fix the source/config, then run `agent-config-sync project`."
                    )
                    return 3
                print(
                    f"\nApplied '{result.target}' and projected to all runtimes. "
                    "Commit the source: "
                    f"git -C {config.repo_root} add -A && git commit -m 'capture: {result.target}'"
                )
                return 0
        except LockError as exc:
            print(f"Lock error: {exc}")
            return 5
        except NeutralLanguageError as exc:
            print(
                f"Aborted: '{exc.skill}' contains vendor-specific terms: "
                f"{', '.join(exc.terms)}. Neutralize and retry."
            )
            return 3
        except SecretFoundError as exc:
            print(f"Aborted: secret-like content in '{exc.runtime}'. Nothing written.")
            return 3
        except ValueError as exc:
            print(f"Aborted: {exc}")
            return 2
        except ConfigError as exc:
            print(f"Aborted: {exc}")
            return 2
    if args.cmd == "promote":
        if args.runtime is None:
            diverged = False
            for name in config.runtimes:
                d = detect_divergence(config, name)
                if d:
                    diverged = True
                    label = "CONFLICT" if d["conflict"] else d["state"]
                    print(f"{label:16} {name}")
            if not diverged:
                print("Nothing to promote - all runtimes match the source.")
            return 0
        if args.runtime not in config.runtimes:
            print(f"Unknown runtime '{args.runtime}'. Known: {', '.join(config.runtimes)}.")
            return 2
        if not args.target:
            print("promote needs --target ('core' or a runtime name).")
            return 2
        try:
            with _mutation_lock(config, args.confirm, "promote"):
                result = promote_instruction(
                    config, args.runtime, args.target, confirm=args.confirm
                )
        except LockError as exc:
            print(f"Lock error: {exc}")
            return 5
        except PromoteConflict as exc:
            print(f"Aborted: {exc}")
            return 2
        except (PromoteBaselineMissing, PromoteSourceBehind, PromoteAmbiguousChange) as exc:
            print(f"Aborted: {exc}")
            return 2
        except (DriftError, ForceScopeError) as exc:
            print(
                f"Promoted '{args.runtime}' to source and updated it, but another "
                f"runtime has an un-promoted edit: {', '.join(exc.runtimes)}. "
                "Resolve it (promote or a scoped --force), then run "
                "`agent-config-sync project`."
            )
            return 2
        except SecretFoundError as exc:
            print(f"Aborted: secret-like content in '{exc.runtime}'. Nothing written.")
            return 3
        except ValueError as exc:
            print(f"Aborted: {exc}")
            return 2
        if result is None:
            print(f"Nothing to promote for '{args.runtime}'.")
            return 0
        print(result.diff or "(no change)")
        if not result.applied:
            print("\nDRY-RUN - nothing written. Re-run with --confirm to promote + reproject.")
            return 0
        print(
            f"\nPromoted '{args.runtime}' -> {args.target} and reprojected all runtimes. "
            f"Commit the source: git -C {config.repo_root} add -A && git commit -m 'promote: {args.runtime}'"
        )
        return 0

    if args.cmd == "prune-backups":
        try:
            with _mutation_lock(config, args.confirm, "prune-backups"):
                result = prune_backups(
                    config.repo_root / ".backups",
                    confirm=args.confirm,
                )
                if args.confirm:
                    categories = sorted({p.parent.name for p in result.delete})
                    append_audit(
                        config.repo_root,
                        {
                            "stamp": default_stamp(),
                            "runtime": "source",
                            "kind": "prune-backups",
                            "confirm": True,
                            "deleted_count": len(result.delete),
                            "categories": categories,
                            "policy": result.policy,
                        },
                    )
        except LockError as exc:
            print(f"Lock error: {exc}")
            return 5
        except ValueError as exc:
            print(f"Aborted: {exc}")
            return 3
        action = "deleted" if args.confirm else "would delete"
        if not result.delete:
            print("No backups eligible for pruning.")
        else:
            prefix = "PRUNED" if args.confirm else "DRY-RUN"
            for path in result.delete:
                print(f"{prefix} {action}: {path}")
        return 0
    if args.cmd == "install-hooks":
        settings = (
            Path(args.claude_settings)
            if args.claude_settings
            else Path.home() / ".claude" / "settings.json"
        )
        hook_cmd = "agent-config-sync sense"
        superseded = ("agent-config-sync check",)
        codex_cfg = (
            Path(args.codex_config)
            if args.codex_config
            else Path.home() / ".codex" / "config.toml"
        )
        gemini = shutil.which("gemini")
        if args.dry_run:
            print(f"DRY-RUN Claude settings target: {settings}")
            if gemini:
                print("DRY-RUN Gemini command: gemini hooks migrate --from-claude")
            else:
                print("DRY-RUN Gemini CLI not found; migration would be skipped")
            print(f"DRY-RUN Codex config target: {codex_cfg}")
            print(f"DRY-RUN hook command: {hook_cmd}")
            return 0
        try:
            with _mutation_lock(config, True, "install-hooks"):
                failed = False
                try:
                    added = install_claude_hook(
                        settings,
                        hook_cmd,
                        backup_root=config.repo_root / ".backups",
                        stamp=default_stamp(),
                        replace_commands=superseded,
                    )
                except HookInstallError as exc:
                    print(f"Hook install failed: {exc}. No changes written.")
                    return 3
                print(f"Claude hook {'installed' if added else 'already present'}.")
                if gemini:
                    try:
                        home = str(Path.home())
                        if sys.platform == "win32":
                            cmd = ["cmd", "/c", gemini, "hooks", "migrate", "--from-claude"]
                        else:
                            cmd = [gemini, "hooks", "migrate", "--from-claude"]
                        proc = subprocess.run(cmd, check=False, cwd=home)
                        if proc.returncode == 0:
                            print("Gemini hook migration succeeded.")
                        else:
                            print(
                                "Gemini hook migration failed "
                                f"(exit {proc.returncode}). Run `gemini hooks migrate --from-claude` manually."
                            )
                            failed = True
                    except OSError as exc:
                        print(
                            f"Gemini hook migration failed ({exc}). Run "
                            "`gemini hooks migrate --from-claude` manually."
                        )
                        failed = True
                else:
                    print(
                        "Gemini CLI not found - skipped; run "
                        "`gemini hooks migrate --from-claude` later."
                    )
                try:
                    codex_added = install_codex_hook(
                        codex_cfg, hook_cmd, backup_root=config.repo_root / ".backups",
                        stamp=default_stamp(),
                        replace_commands=superseded,
                    )
                    print(
                        f"Codex hook {'installed' if codex_added else 'already present'} "
                        "in config.toml."
                    )
                except HookInstallError as exc:
                    print(f"Codex hook failed ({exc}). config.toml unchanged.")
                    failed = True
                return 3 if failed else 0
        except LockError as exc:
            print(f"Lock error: {exc}")
            return 5
    return 0
