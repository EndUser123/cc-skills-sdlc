"""Fixture (TP): wiki link resolver with a RECENTLY-EXPIRED workaround tag.

Modeled on plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py:49.
The strict single-candidate cutoff is a real ceiling; the `revisit: 2026-07-01`
tag is the proposed convention. Today is 2026-07-07 -> expired 6 days ago.
A correct scanner MUST flag this (boundary case: just past the deadline).
"""
from __future__ import annotations

BAD_LINK_CHARS = set('"$`()*=<>|&;!#')
DEFAULT_MAX_AGE_DAYS = 90
DEFAULT_STALE_LIMIT = 20

# ponytail: strict single-candidate cutoff. Ambiguous matches (>=2 candidates
# above cutoff) skip — "intelligent" means don't guess when unclear.
# ceiling=moderate, revisit: 2026-07-01
FUZZY_CUTOFF = 0.9


def _is_real_link_target(target: str) -> bool:
    if not target or target[0] in BAD_LINK_CHARS:
        return False
    return "/" in target or "." in target
