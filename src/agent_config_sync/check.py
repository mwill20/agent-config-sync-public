from .config import Config
from .project import projected_for
from .skills import project_skills


def check(config: Config) -> list[str]:
    stale: list[str] = []
    for name, rt in config.runtimes.items():
        projected = projected_for(config.repo_root, rt)
        dest = rt.instruction_dest
        if not dest.exists() or dest.read_text("utf-8") != projected:
            stale.append(name)
    # Managed skills: a dry-run projection reports every file that is not
    # byte-identical to source (missing/source-moved/hand-edited) as non-"unchanged".
    for action in project_skills(config, dry_run=True):
        if action.kind != "unchanged":
            stale.append(f"{action.runtime}:{action.name}/{action.relpath}")
    return stale
