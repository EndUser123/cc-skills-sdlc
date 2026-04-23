"""Complexity scanning using radon — cyclomatic complexity analysis.

Scans Python files for high-complexity functions and methods, returning
findings in the same format as code_scanner.py for unified deduplication.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from radon.complexity import cc_visit
from radon.visitors import Class

logger = logging.getLogger(__name__)


# CC risk mapping (CC value -> (risk_score, rollback_complexity, severity))
_CC_RISK_MAP = [
    (5, 1, "low", "low"),      # CC 1-5: low complexity
    (10, 2, "medium", "medium"),  # CC 6-10: medium complexity
    (20, 3, "medium", "medium"),  # CC 11-20: high complexity
    (float("inf"), 4, "high", "high"),  # CC 21+: very high complexity
]


def _cc_to_risk(cc: int) -> tuple[int, str, str]:
    """Map cyclomatic complexity to risk metadata."""
    for threshold, risk_score, rollback, severity in _CC_RISK_MAP:
        if cc <= threshold:
            return risk_score, rollback, severity
    return 4, "high", "high"


def scan_complexity(
    file_paths: list[str | Path],
    min_cc: int = 5,
) -> list[dict[str, Any]]:
    """Scan Python files for high-cyclomatic-complexity functions.

    Args:
        file_paths: List of Python file paths to scan.
        min_cc: Minimum cyclomatic complexity to report (default 5).
                Functions with CC below this threshold are ignored.

    Returns:
        List of complexity findings, each containing:
            - type: "HIGH_CC"
            - file_path: Path to the file
            - line_number: Line where function is defined
            - description: "CC=N function_name (method of ClassName)"
            - complexity: The cyclomatic complexity value
            - risk_score: 1-4 scale
            - rollback_complexity: "low" | "medium" | "high"
            - state_impact: "low" (CC alone doesn't affect runtime state)
            - severity: "low" | "medium" | "high"
            - finding_type: "complexity"

    Example:
        >>> findings = scan_complexity(["example.py"], min_cc=10)
        >>> for f in findings:
        ...     print(f"{f['description']} CC={f['complexity']}")
    """
    findings = []

    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            logger.debug(f"Skipping non-existent file: {file_path}")
            continue

        if not str(file_path).endswith(".py"):
            logger.debug(f"Skipping non-Python file: {file_path}")
            continue

        try:
            source = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            continue

        try:
            blocks = cc_visit(source)
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            continue

        for block in blocks:
            # Skip Class blocks — they aggregate method CCs, not refactorable units
            if isinstance(block, Class):
                continue
                continue
            cc = block.complexity
            if cc < min_cc:
                continue

            risk_score, rollback_complexity, severity = _cc_to_risk(cc)

            # Format description
            classname = getattr(block, "classname", None)
            func_name = getattr(block, "name", None)
            if classname:
                func_desc = f"method {func_name} of class {classname}"
            else:
                func_desc = f"function {func_name}"

            finding = {
                "type": "HIGH_CC",
                "file_path": str(path),
                "line_number": block.lineno,
                "description": f"CC={cc} {func_desc}",
                "complexity": cc,
                "risk_score": risk_score,
                "rollback_complexity": rollback_complexity,
                "state_impact": "low",
                "severity": severity,
                "finding_type": "complexity",
            }
            findings.append(finding)
            logger.debug(
                f"High-CC finding: {path}:{block.lineno} {func_desc} CC={cc} "
                f"(risk={risk_score}, severity={severity})"
            )

    return findings


# CLI for testing
if __name__ == "__main__":
    import argparse, json, sys

    parser = argparse.ArgumentParser(description="Scan for cyclomatic complexity")
    parser.add_argument("files", nargs="+", help="Python files to scan")
    parser.add_argument("--min-cc", type=int, default=5, help="Minimum CC to report")
    args = parser.parse_args()

    findings = scan_complexity(args.files, min_cc=args.min_cc)
    print(json.dumps(findings, indent=2))
    print(f"\n{len(findings)} findings above CC={args.min_cc}", file=sys.stderr)
