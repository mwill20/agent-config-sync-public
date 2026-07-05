from .config import Config
from .fsutil import sha256_text
from .project import projected_for
from .skills import project_skills
from .state import load_state

_SKILL_STATE = {
    "create": "missing",
    "unchanged": "in-sync",
    "update": "behind",
    "drift": "edited",
    "forced": "edited",
}


def status(config: Config) -> dict[str, str]:
    inst_state = load_state(config.repo_root).get("instructions", {})
    result: dict[str, str] = {}
    for name, rt in config.runtimes.items():
        projected = projected_for(config.repo_root, rt)
        dest = rt.instruction_dest
        if not dest.exists():
            result[name] = "missing"
            continue
        current = dest.read_text("utf-8")
        if current == projected:
            result[name] = "in-sync"
        elif inst_state.get(name) == sha256_text(current):
            result[name] = "behind"
        else:
            result[name] = "edited"
    # One line per managed skill per runtime, keyed "<runtime>:skill:<name>".
    for action in project_skills(config, dry_run=True):
        if action.relpath == "SKILL.md":
            result[f"{action.runtime}:skill:{action.name}"] = _SKILL_STATE[action.kind]
    return result
