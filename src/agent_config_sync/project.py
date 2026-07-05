from dataclasses import dataclass
from pathlib import Path

from .audit import append_audit
from .config import Config, RuntimeConfig
from .fsutil import atomic_write, backup, default_stamp, sha256_text
from .render import render
from .secrets import SecretFoundError, find_secrets
from .state import load_state, save_state


class DriftError(Exception):
    def __init__(self, runtimes: list[str]):
        self.runtimes = runtimes
        super().__init__(f"un-promoted changes in: {', '.join(runtimes)}")


class ForceScopeError(Exception):
    """A bare --force would overwrite more than one drifted runtime at once."""

    def __init__(self, runtimes: list[str]):
        self.runtimes = runtimes
        super().__init__(
            "refusing a blanket --force across multiple drifted runtimes: "
            f"{', '.join(runtimes)}. Re-run with an explicit runtime, "
            "e.g. `project <runtime> --force`."
        )


@dataclass
class ProjectAction:
    runtime: str
    kind: str
    dest: Path
    content: str


def projected_for(repo_root: Path, rt: RuntimeConfig) -> str:
    core = (repo_root / "_shared" / "core.md").read_text("utf-8")
    overlay = rt.overlay.read_text("utf-8") if rt.overlay.exists() else ""
    return render(core, overlay)


def _classify(projected: str, dest: Path, last_hash: str | None, force: bool) -> str:
    if not dest.exists():
        return "create"
    current = dest.read_text("utf-8")
    if current == projected:
        return "unchanged"
    if last_hash is not None and sha256_text(current) == last_hash:
        return "update"
    return "forced" if force else "drift"


def project(
    config: Config,
    *,
    dry_run: bool = False,
    force: bool = False,
    stamp: str | None = None,
    only: str | None = None,
) -> list[ProjectAction]:
    if only is not None and only not in config.runtimes:
        raise ValueError(f"unknown runtime '{only}'")
    selected = (
        {only: config.runtimes[only]} if only is not None else config.runtimes
    )

    state = load_state(config.repo_root)
    inst_state = state.setdefault("instructions", {})

    plan: list[ProjectAction] = []
    for name, rt in selected.items():
        projected = projected_for(config.repo_root, rt)
        matches = find_secrets(projected)
        if matches:
            raise SecretFoundError(name, matches)
        kind = _classify(projected, rt.instruction_dest, inst_state.get(name), force)
        plan.append(ProjectAction(name, kind, rt.instruction_dest, projected))

    drifted = [a.runtime for a in plan if a.kind == "drift"]
    if drifted and not dry_run:
        raise DriftError(drifted)
    # A blanket --force (no runtime named) must not clobber more than one
    # drifted runtime in a single sweep — make the operator scope it.
    forced = [a.runtime for a in plan if a.kind == "forced"]
    if force and only is None and len(forced) > 1 and not dry_run:
        raise ForceScopeError(forced)
    if dry_run:
        return plan

    stamp = stamp or default_stamp()
    backup_root = config.repo_root / ".backups"
    for action in plan:
        if action.kind in ("unchanged", "drift"):
            continue
        if action.dest.exists():
            backup(action.dest, backup_root, action.runtime, stamp)
        atomic_write(action.dest, action.content)
        content_hash = sha256_text(action.content)
        inst_state[action.runtime] = content_hash
        # Persist after each successful write so recorded hashes never lag disk:
        # a mid-loop failure must not leave earlier writes unrecorded (would
        # misclassify our own output as drift on the next run).
        save_state(config.repo_root, state)
        append_audit(
            config.repo_root,
            {
                "stamp": stamp,
                "runtime": action.runtime,
                "kind": action.kind,
                "force": force,
                "dest": str(action.dest),
                "content_sha256": content_hash,
            },
        )

    save_state(config.repo_root, state)
    return plan
