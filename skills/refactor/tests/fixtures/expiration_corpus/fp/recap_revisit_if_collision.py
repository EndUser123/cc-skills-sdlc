"""Fixture (FP): name-collision with `revisit_if` (NOT a ponytail: tag).

Modeled verbatim on plugins/cc-skills-analysis/skills/recap/models.py:191-202.
`revisit_if` is a dataclass field — a list of conditions under which a decision
should be revisited. The keyword `revisit` appears, but it is NOT a
`# ponytail: ... revisit: YYYY-MM-DD` workaround tag. A scanner that substring-
matches the bare word `revisit` would false-positive here. MUST NOT be flagged.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class DecisionStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


@dataclass(slots=True)
class Decision:
    """A continuity-critical decision with rationale and revisit conditions."""
    decision_id: str
    statement: str
    rationale: str | None = None
    impact: str = "medium"
    status: DecisionStatus = DecisionStatus.ACTIVE
    session_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    anchors: list[str] = field(default_factory=list)
    revisit_if: list[str] = field(default_factory=list)
