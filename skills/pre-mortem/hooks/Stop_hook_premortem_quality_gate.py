#!/usr/bin/env python3
"""StopHook_premortem_quality_gate — validates pre-mortem output quality before synthesis.

Per ADR-20260329: Phase 3 synthesis should not proceed if findings are missing
critical evidence (file:line citations for HIGH/CRITICAL, non-empty findings array,
valid severity tags).

Exit codes: 0 = allow, 2 = block.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Add __lib for shared changelog_writer utility
_SKILLS_LIB = Path(__file__).parent.parent.parent / "__lib"
if str(_SKILLS_LIB) not in sys.path:
    sys.path.insert(0, str(_SKILLS_LIB))

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def run(data: dict) -> dict:
    """Validate pre-mortem Phase 1 findings quality.

    Requires:
    - findings array is non-empty
    - HIGH/CRITICAL findings have file:line citations
    - all severity tags are valid
    """
    findings = data.get("findings", [])

    # QA-001: findings must not be empty
    if not findings:
        return {
            "decision": "block",
            "reason": "findings array is empty — nothing to synthesize",
        }

    # QA-002: severity tags must be valid
    invalid_severities = set()
    for f in findings:
        sev = f.get("severity", "").upper()
        if sev not in VALID_SEVERITIES:
            invalid_severities.add(sev)

    if invalid_severities:
        return {
            "decision": "block",
            "reason": f"Invalid severity tags: {sorted(invalid_severities)}",
        }

    # QA-003: HIGH/CRITICAL findings must have file:line citations
    missing_citations = []
    file_line_pattern = re.compile(r"^.+?:\d+")

    for f in findings:
        sev = f.get("severity", "").upper()
        if sev in ("HIGH", "CRITICAL"):
            location = f.get("location", "")
            if not file_line_pattern.match(location):
                missing_citations.append(f.get("id", "UNKNOWN"))

    if missing_citations:
        return {
            "decision": "block",
            "reason": f"HIGH/CRITICAL findings lack file:line citation: {', '.join(missing_citations)}",
        }

    # All checks passed — write to package CHANGELOG.md
    _write_premortem_changelog(data)

    return {"decision": "allow"}


def _write_premortem_changelog(data: dict) -> None:
    """Write /pre-mortem completion entry to package CHANGELOG.md.

    Args:
        data: Input data containing target path and findings summary
    """
    try:
        from changelog_writer import record_investigation

        # Try multiple field names for target path
        target_path = (
            data.get("target")
            or data.get("target_path")
            or data.get("path")
            or data.get("work_path")
        )
        if not target_path:
            return

        root = Path(target_path)
        while root != root.parent:
            if (root / "CHANGELOG.md").exists():
                finding_count = len(data.get("findings", []))
                record_investigation(
                    package_root=root,
                    skill="/pre-mortem",
                    description=f"Pre-mortem adversarial review — {finding_count} findings",
                )
                break
            root = root.parent
    except Exception:
        pass  # Non-fatal — changelog write failures should not block the response


if __name__ == "__main__":
    input_data = json.load(sys.stdin)
    result = run(input_data)
    print(json.dumps(result))
    sys.exit(0 if result["decision"] == "allow" else 2)
