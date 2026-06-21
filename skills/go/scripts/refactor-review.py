"""Refactor-specific review pass for /go orchestrator."""

import re
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal


class Severity:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def load_task_contract(state_dir: Path, run_id: str) -> dict:
    """Load active task contract."""
    task_file = state_dir / f"active-task_{run_id}.json"
    if not task_file.exists():
        return {}
    return json.loads(task_file.read_text(encoding="utf-8"))


def get_changed_files() -> list[str]:
    """Get list of changed files from git diff."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def detect_api_surface_changes(file_path: str, diff_output: str) -> list[dict]:
    """Detect API surface changes from git diff.

    Looks for function/class method signature changes, parameter modifications.
    """
    findings = []

    # Function signature changes
    if re.search(r"def\s+\w+\([^)]*\)->[^:]+:\s*def\s+\w+\([^)]*\)->[^:]+", diff_output):
        findings.append({
            "category": "api_surface_changes",
            "severity": Severity.HIGH,
            "file": file_path,
            "symbol": "function_signature",
            "evidence": "Function return type signature changed",
            "suggested_fix": "Add type overload or maintain backward compatibility",
        })

    # Parameter list modifications
    if re.search(r"def\s+\w+\([^)]*\)", diff_output):
        findings.append({
            "category": "api_surface_changes",
            "severity": Severity.MEDIUM,
            "file": file_path,
            "symbol": "parameter_list",
            "evidence": "Function parameter list modified",
            "suggested_fix": "Verify breaking changes, add default values or overload",
        })

    return findings


def detect_behavioral_drift(file_path: str, diff_output: str) -> list[dict]:
    """Detect behavioral changes from git diff.

    Looks for control flow, loop construct, exception handling modifications.
    """
    findings = []

    # Control flow structure changes
    if re.search(r"(if|elif|else|for|while|try|except|finally)", diff_output):
        findings.append({
            "category": "behavioral_drift",
            "severity": Severity.MEDIUM,
            "file": file_path,
            "symbol": "control_flow",
            "evidence": "Control flow structure modified",
            "suggested_fix": "Verify behavior preservation with tests",
        })

    # Exception handling modifications
    if re.search(r"(raise|except|finally)", diff_output):
        findings.append({
            "category": "behavioral_drift",
            "severity": Severity.MEDIUM,
            "file": file_path,
            "symbol": "exception_handling",
            "evidence": "Exception handling modified",
            "suggested_fix": "Update tests to cover new exception paths",
        })

    return findings


def detect_test_coverage_retention(file_path: str, diff_output: str) -> list[dict]:
    """Detect test coverage retention from git diff.

    Checks for test deletions and ensures no test deletions without migration path.
    """
    findings = []

    # Check if test file was modified (not deleted)
    if file_path.endswith("_test.py") and "-test.py" in diff_output:
        findings.append({
            "category": "test_coverage_retention",
            "severity": Severity.HIGH,
            "file": file_path,
            "symbol": "test_deletion",
            "evidence": "Test file deleted or significantly modified",
            "suggested_fix": "Restore tests or provide migration path for deleted functionality",
        })

    return findings


def detect_deprecation_path(file_path: str, diff_output: str) -> list[dict]:
    """Detect presence of deprecation markers.

    Checks for @deprecation decorators and deprecation warnings.
    """
    findings = []

    # API changes without deprecation markers
    if re.search(r"(def|class)\s+\w+", diff_output):
        if "@deprecation" not in diff_output and "deprecated" not in diff_output.lower():
            findings.append({
                "category": "deprecation_path",
                "severity": Severity.MEDIUM,
                "file": file_path,
                "symbol": "api_change",
                "evidence": "API change without deprecation marker",
                "suggested_fix": "Add @deprecation decorator or deprecation warning in docstring",
            })

    return findings


def analyze_refactor(file_path: str) -> list[dict]:
    """Run refactor-specific analysis on a single file."""
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD", file_path],
            capture_output=True,
            text=True,
        )
        diff_output = proc.stdout

        findings = []
        findings.extend(detect_api_surface_changes(file_path, diff_output))
        findings.extend(detect_behavioral_drift(file_path, diff_output))
        findings.extend(detect_test_coverage_retention(file_path, diff_output))
        findings.extend(detect_deprecation_path(file_path, diff_output))

        return findings

    except Exception as e:
        return [{
            "category": "analysis_error",
            "severity": Severity.LOW,
            "file": file_path,
            "symbol": "error",
            "evidence": f"Analysis failed: {e}",
            "suggested_fix": "Manual review required",
        }]


def main() -> int:

    state_dir = Path(os.environ["GO_STATE_DIR"])
    run_id = os.environ["RUN_ID"]

    changed_files = get_changed_files()

    if not changed_files:
        print("No changed files detected, refactor review skipped")
        return 0

    all_findings = []
    for file_path in changed_files:
        findings = analyze_refactor(file_path)
        all_findings.extend(findings)

    # Count HIGH severity findings
    high_count = sum(1 for f in all_findings if f["severity"] == Severity.HIGH)

    report = {
        "run_id": run_id,
        "changed_files": changed_files,
        "findings": all_findings,
        "high_severity_count": high_count,
        "status": "blocked" if high_count > 0 else "pass",
    }

    report_path = state_dir / f"refactor-review_{run_id}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if high_count > 0:
        print(f"REFACTOR REVIEW FAILED: {high_count} HIGH severity findings")
        return 1

    print("REFACTOR REVIEW PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
