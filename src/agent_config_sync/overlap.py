"""Read-only skill-overlap report.

Deterministic similarity signals between a candidate skill body and every
managed skill: body-text ratio and frontmatter-description ratio. High scores
mean "review for redundancy before enrolling" - they are a triage signal, not
a verdict. Whether two skills are truly redundant, and how to merge the useful
parts of both, stays an operator judgment executed through the normal enroll
gates (see docs/WORKING_CHECKLIST.md S9 rationale).

Body comparison is capped at the first 12,000 characters per side so the
report stays interactive on large bodies; the cap is deterministic and
documented here rather than silent.
"""

import difflib
import re
from dataclasses import dataclass

from .config import Config

_DESC = re.compile(r"^description:\s*(.+)$", re.MULTILINE)
_BODY_CAP = 12_000
REVIEW_BODY = 0.80
REVIEW_DESC = 0.75


@dataclass
class OverlapScore:
    name: str
    body: float
    description: float
    flagged: bool


def _description(body: str) -> str:
    m = _DESC.search(body)
    return m.group(1).strip() if m else ""


def compare(candidate_body: str, config: Config) -> list[OverlapScore]:
    cand_body = candidate_body[:_BODY_CAP]
    cand_desc = _description(candidate_body)
    scores: list[OverlapScore] = []
    for name in config.managed_skills:
        managed = (config.repo_root / "skills" / name / "SKILL.md").read_text("utf-8")
        body = difflib.SequenceMatcher(None, cand_body, managed[:_BODY_CAP]).ratio()
        desc = (
            difflib.SequenceMatcher(None, cand_desc, _description(managed)).ratio()
            if cand_desc
            else 0.0
        )
        scores.append(
            OverlapScore(
                name,
                round(body, 3),
                round(desc, 3),
                body >= REVIEW_BODY or desc >= REVIEW_DESC,
            )
        )
    scores.sort(key=lambda s: max(s.body, s.description), reverse=True)
    return scores


def format_report(scores: list[OverlapScore], top: int = 5) -> str:
    lines = ["body  desc  managed skill"]
    for s in scores[:top]:
        mark = "  REVIEW" if s.flagged else ""
        lines.append(f"{s.body:.2f}  {s.description:.2f}  {s.name}{mark}")
    if any(s.flagged for s in scores):
        lines.append(
            "REVIEW flags mean: inspect for redundancy before enrolling. "
            "Merging useful parts of both is an operator decision, executed "
            "through the enroll gates - this report never decides."
        )
    else:
        lines.append("No high-overlap candidates; looks unique to the managed set.")
    return "\n".join(lines)
