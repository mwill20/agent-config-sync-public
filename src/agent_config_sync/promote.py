import difflib

from .capture import CaptureResult, _standard_path, _unified, _write_source, capture_standard
from .config import Config
from .fsutil import sha256_text
from .project import project, projected_for
from .secrets import SecretFoundError, find_secrets
from .state import load_state


class PromoteConflict(Exception):
    """Source moved since last project AND the live file was edited (3-way).

    v1 flags this for manual resolution rather than auto-merging — there is no
    single source of truth at conflict time.
    """

    def __init__(self, runtime: str):
        self.runtime = runtime
        super().__init__(
            f"3-way conflict for '{runtime}': the source also changed since the "
            "last project. Resolve manually (re-project, then re-promote)."
        )


class PromoteBaselineMissing(Exception):
    def __init__(self, runtime: str):
        self.runtime = runtime
        super().__init__(
            f"missing last-projected baseline for '{runtime}'. Run project first, "
            "then make the runtime edit again or promote from a tracked baseline."
        )


class PromoteSourceBehind(Exception):
    def __init__(self, runtime: str):
        self.runtime = runtime
        super().__init__(
            f"'{runtime}' has no live edit to promote; the source moved ahead. "
            "Run `agent-config-sync project` to update the runtime."
        )


class PromoteAmbiguousChange(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)


def _added_lines(projected: str, live: str) -> str:
    diff = difflib.ndiff(projected.splitlines(True), live.splitlines(True))
    return "".join(line[2:] for line in diff if line.startswith("+ "))


def _change_ops(projected: str, live: str) -> list[dict[str, object]]:
    before = projected.splitlines(True)
    after = live.splitlines(True)
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    ops: list[dict[str, object]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        ops.append(
            {
                "tag": tag,
                "old": "".join(before[i1:i2]),
                "new": "".join(after[j1:j2]),
                "old_end": i2,
            }
        )
    return ops


def _append_at_end(projected: str, ops: list[dict[str, object]]) -> str | None:
    lines = projected.splitlines(True)
    if not ops or any(op["tag"] != "insert" for op in ops):
        return None
    if any(op["old_end"] != len(lines) for op in ops):
        return None
    return "".join(str(op["new"]) for op in ops)


def _apply_exact_changes(config: Config, target: str, ops: list[dict[str, object]], *, confirm: bool) -> CaptureResult:
    path = _standard_path(config, target)
    before = path.read_text("utf-8") if path.exists() else ""
    after = before
    for op in ops:
        if op["tag"] == "insert":
            raise PromoteAmbiguousChange(
                "mid-file insertion cannot be attributed safely; edit the source manually"
            )
        old = str(op["old"])
        new = str(op["new"])
        matches = after.count(old)
        if not old or matches != 1:
            raise PromoteAmbiguousChange(
                "promote change is not uniquely attributable to the selected source target"
            )
        after = after.replace(old, new, 1)
    matches = find_secrets(after)
    if matches:
        raise SecretFoundError(target, matches)
    diff = _unified(before, after, path)
    if confirm:
        _write_source(config, path, after, target=target)
    return CaptureResult("standard", target, diff, confirm)


def detect_divergence(config: Config, runtime: str) -> dict | None:
    """Return None if the live instruction file matches its projection, else a
    dict describing whether runtime drift is promotable or must be refused."""
    rt = config.runtimes[runtime]
    projected = projected_for(config.repo_root, rt)
    live = rt.instruction_dest.read_text("utf-8") if rt.instruction_dest.exists() else ""
    if live == projected:
        return None
    last = load_state(config.repo_root).get("instructions", {}).get(runtime)
    projected_hash = sha256_text(projected)
    live_hash = sha256_text(live)
    if last is None:
        state = "missing-baseline"
    else:
        source_moved = projected_hash != last
        live_moved = live_hash != last
        if source_moved and live_moved:
            state = "conflict"
        elif source_moved:
            state = "source-behind"
        else:
            state = "live-only"
    return {
        "projected": projected,
        "live": live,
        "added": _added_lines(projected, live),
        "ops": _change_ops(projected, live),
        "state": state,
        "conflict": state == "conflict",
    }


def promote_instruction(
    config: Config, runtime: str, target: str, *, confirm: bool = False
) -> CaptureResult | None:
    """Lift a runtime's out-of-band edit back into the source (core or an overlay)
    via the capture engine, then force-reproject so every runtime converges.

    Returns None if there is nothing to promote. Raises PromoteConflict on a
    3-way conflict (never auto-merges)."""
    d = detect_divergence(config, runtime)
    if d is None:
        return None
    if d["state"] == "missing-baseline":
        raise PromoteBaselineMissing(runtime)
    if d["state"] == "source-behind":
        raise PromoteSourceBehind(runtime)
    if d["state"] == "conflict":
        raise PromoteConflict(runtime)
    added = _append_at_end(d["projected"], d["ops"])
    if added is not None:
        result = capture_standard(config, target, added, confirm=confirm)
    else:
        result = _apply_exact_changes(config, target, d["ops"], confirm=confirm)
    if confirm:
        # The promoted runtime's live file is (intentionally) drifted, so reproject
        # it with a force scoped to just that runtime. Then reproject the rest
        # without force: if another runtime carries its own un-promoted edit, the
        # second pass raises DriftError naming that runtime instead of silently
        # clobbering a learning that was never promoted (a bare force here could
        # also trip ForceScopeError and abort after the source was already written).
        project(config, force=True, only=runtime)
        project(config)
    return result
