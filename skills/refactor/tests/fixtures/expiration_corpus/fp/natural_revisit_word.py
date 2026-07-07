"""Fixture (FP): ordinary prose comment containing the word "revisit".

No `ponytail:` tag at all. The word "revisit" appears in natural English
planning prose. A scanner that greps for the bare word would false-positive.
Must only match the structured `revisit: YYYY-MM-DD` token inside a
`# ponytail:` comment, not free-form English. MUST NOT be flagged.
"""
from __future__ import annotations


def plan_next_release(open_issues: list[str]) -> str:
    # TODO: revisit the triage order once we have >50 open issues — the current
    # FIFO works for now but may need priority weighting later. Not a workaround,
    # just deferred product thinking.
    if not open_issues:
        return "nothing to triage"
    return open_issues[0]
