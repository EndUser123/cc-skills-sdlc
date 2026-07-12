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
BOUNDARY_RE = re.compile(
    r"\b(?:hook|handoff|schema|registry|cross[- ]component|producer|consumer|transport)\b",
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


def _section_content(text: str, heading_pattern: str) -> str:
    match = re.search(rf"^#+\s+(?:{heading_pattern})\s*$", text, re.I | re.M)
    if not match:
        return ""
    tail = text[match.end():]
    next_heading = re.search(r"^#+\s+", tail, re.M)
    return tail[: next_heading.start() if next_heading else len(tail)]


def validate_plan(path: Path) -> dict:
    findings: list[dict[str, str]] = []
    try:
        plan_bytes = path.read_bytes()
        text = plan_bytes.decode("utf-8")
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

    ledger_content = _section_content(text, r"(?:Evidence|Claim) Ledger")
    if not ledger_content or ledger_content.count("|") < 4:
        findings.append({"code": "LEDGER", "detail": "implementation-ready plans require an Evidence Ledger"})

    falsifier_content = _section_content(text, r"Falsifiers?|Falsification")
    if not falsifier_content or not re.search(r"(?:^\s*[-*]\s+|\|)", falsifier_content, re.M):
        findings.append({"code": "FALSIFIER", "detail": "plan must name at least one falsifier"})

    if BOUNDARY_RE.search(text) and not _heading_exists(text, "Contract Boundary Matrix"):
        findings.append({"code": "BOUNDARY", "detail": "boundary-sensitive plan requires Contract Boundary Matrix"})

    # Unknowns are not automatically blockers: the plan may contain historical
    # hypotheses or explicitly deferred investigation.  The hard promotion
    # checks are the status, blocker count, required evidence artifacts, and
    # explicit falsifier.  This keeps the gate mechanical rather than semantic.
    digest = hashlib.sha256(plan_bytes).hexdigest()
    return {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "plan_path": str(path.resolve()),
        "plan_sha256": digest,
        "verdict": "PASS" if not findings else "BLOCKED",
        "findings": findings,
    }


def read_verified_plan(path: Path) -> str | None:
    """Return plan text only when its current bytes have a valid PASS sidecar."""
    try:
        plan_bytes = path.read_bytes()
        text = plan_bytes.decode("utf-8")
        artifact = path.with_suffix(path.suffix + ".evidence-gate.json")
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        frontmatter = _frontmatter(text)
        current_result = validate_plan(path)
        if (
            current_result.get("verdict") == "PASS"
            and payload.get("schema_version") == 1
            and payload.get("verdict") == "PASS"
            and payload.get("findings") == []
            and payload.get("plan_sha256") == hashlib.sha256(plan_bytes).hexdigest()
            and Path(payload.get("plan_path", "")).resolve() == path.resolve()
            and frontmatter.get("status") == "implementation-ready"
            and frontmatter.get("unresolved_blockers", "0") == "0"
        ):
            return text
    except (OSError, UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return None


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
