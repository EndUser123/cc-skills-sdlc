#!/usr/bin/env python3
"""Mechanical promotion gate for implementation plans.

This gate checks plan readiness facts that can be verified without pretending
that static inspection proves runtime value.  It writes a sidecar artifact
whose hash binds the verdict to the exact plan text consumed by /go.

Usage:
    python evidence_gate.py PLAN.md --write-artifact
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path


REQUIRED_HEADINGS = (
    "Goal",
    "Current State With Evidence",
    "Design Decisions and Invariants",
    "Implementation Changes",
    "Test Matrix",
    "Assumptions / Defaults",
    "Open Questions",
)

PLACEHOLDER_RE = re.compile(r"\[(?:TODO|TBD|FIXME|PLACEHOLDER)\]|<TODO>|<TBD>", re.I)
CRITICAL_UNKNOWN_RE = re.compile(
    r"\b(?:open question|unresolved|unknown|assumed|hypothesis)\b", re.I
)
BOUNDARY_RE = re.compile(
    r"\b(?:hook|handoff|artifact|schema|registry|cross[- ]component|state|producer|consumer|transport)\b",
    re.I,
)


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


def _heading_exists(text: str, heading: str) -> bool:
    return bool(re.search(rf"^#+\s+{re.escape(heading)}\s*$", text, re.I | re.M))


def validate_plan(path: Path) -> dict:
    findings: list[dict[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"verdict": "BLOCKED", "findings": [{"code": "FILE", "detail": str(exc)}]}

    frontmatter = _frontmatter(text)
    if frontmatter.get("status") != "implementation-ready":
        findings.append({"code": "STATUS", "detail": "status must be implementation-ready"})
    if frontmatter.get("unresolved_blockers", "0") != "0":
        findings.append({"code": "BLOCKERS", "detail": "unresolved_blockers must be 0"})

    for heading in REQUIRED_HEADINGS:
        if not _heading_exists(text, heading):
            findings.append({"code": "SECTION", "detail": f"missing required section: {heading}"})

    if PLACEHOLDER_RE.search(text):
        findings.append({"code": "PLACEHOLDER", "detail": "placeholder marker remains"})

    has_ledger = bool(re.search(r"^#+\s+(?:Evidence|Claim) Ledger\s*$", text, re.I | re.M))
    if not has_ledger:
        findings.append({"code": "LEDGER", "detail": "implementation-ready plans require an Evidence Ledger"})

    has_falsifier = bool(re.search(r"\bfalsif(?:ier|ication|y)\b", text, re.I))
    if not has_falsifier:
        findings.append({"code": "FALSIFIER", "detail": "plan must name at least one falsifier"})

    if BOUNDARY_RE.search(text) and not _heading_exists(text, "Contract Boundary Matrix"):
        findings.append({"code": "BOUNDARY", "detail": "boundary-sensitive plan requires Contract Boundary Matrix"})

    # Unknowns are not automatically blockers: the plan may contain historical
    # hypotheses or explicitly deferred investigation.  The hard promotion
    # checks are the status, blocker count, required evidence artifacts, and
    # explicit falsifier.  This keeps the gate mechanical rather than semantic.
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "plan_path": str(path.resolve()),
        "plan_sha256": digest,
        "verdict": "PASS" if not findings else "BLOCKED",
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args(argv)
    result = validate_plan(args.plan)
    if args.write_artifact:
        out = args.plan.with_suffix(args.plan.suffix + ".evidence-gate.json")
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
