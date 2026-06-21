"""Regression test runner with baseline comparison."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal


def load_task_contract(state_dir: Path, run_id: str) -> dict:
    """Load active task contract."""
    task_file = state_dir / f"active-task_{run_id}.json"
    if not task_file.exists():
        return {}
    return json.loads(task_file.read_text(encoding="utf-8"))


def find_baseline(state_dir: Path, test_name: str, run_id: str) -> Path | None:
    """Find baseline file for a test."""
    baseline_dir = state_dir / "baselines"
    pattern = f"{test_name}_baseline_{run_id}_*.txt"
    matches = sorted(baseline_dir.glob(pattern))
    return matches[-1] if matches else None


def regenerate_baseline(state_dir: Path, test_name: str, run_id: str, output: str) -> Path:
    """Regenerate baseline file."""
    baseline_dir = state_dir / "baselines"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    baseline_path = baseline_dir / f"{test_name}_baseline_{run_id}_{timestamp}.txt"
    baseline_path.write_text(output, encoding="utf-8")
    return baseline_path


def compare_output(expected: str, actual: str, tolerance: int = 0) -> list[str]:
    """Compare baseline against actual output.

    Returns list of divergence descriptions.
    """
    expected_lines = expected.strip().split("\n")
    actual_lines = actual.strip().split("\n")

    divergences = []

    # Missing lines (expected but not in actual)
    for line in expected_lines:
        if line and line not in actual_lines:
            divergences.append(f"MISSING: {line}")

    # Extra lines (actual but not in expected)
    for line in actual_lines:
        if line and line not in expected_lines:
            divergences.append(f"EXTRA: {line}")

    # Tolerance: allow up to N lines of drift
    if 0 < tolerance < len(divergences):
        divergences = divergences[:tolerance]

    return divergences


def run_regression_test(
    command: str,
    test_name: str,
    state_dir: Path,
    run_id: str,
) -> Literal["pass", "fail", "skip"]:
    """Run a single regression test.

    Returns:
        "pass", "fail", or "skip"
    """
    skip_baselines = os.environ.get("GO_SKIP_BASELINES", "0") == "1"
    regenerate = os.environ.get("GO_REGENERATE_BASELINES", "0") == "1"

    baseline = find_baseline(state_dir, test_name, run_id)

    if baseline is None and skip_baselines:
        print(f"SKIP: {test_name} (no baseline and GO_SKIP_BASELINES=1)")
        return "skip"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            timeout=300,
        )
        actual = result.stdout

        if regenerate:
            baseline_path = regenerate_baseline(state_dir, test_name, run_id, actual)
            print(f"REGENERATED: {test_name} -> {baseline_path.name}")
            return "pass"

        if baseline is None:
            print(f"FAIL: {test_name} (no baseline, set GO_REGENERATE_BASELINES=1 to create)")
            return "fail"

        expected = baseline.read_text(encoding="utf-8")
        divergences = compare_output(expected, actual)

        if divergences:
            print(f"FAIL: {test_name}")
            for div in divergences:
                print(f"  {div}")
            return "fail"

        print(f"PASS: {test_name}")
        return "pass"

    except subprocess.TimeoutExpired:
        print(f"FAIL: {test_name} (timeout)")
        return "fail"
    except Exception as e:
        print(f"FAIL: {test_name} ({e})")
        return "fail"


def main() -> int:
    state_dir = Path(os.environ["GO_STATE_DIR"])
    run_id = os.environ["RUN_ID"]

    task = load_task_contract(state_dir, run_id)
    verification_commands = task.get("verification_commands", [])

    if not verification_commands:
        print("No verification commands in task contract")
        return 0

    tolerance = int(os.environ.get("GO_REGRESSION_TOLERANCE", "0"))

    results = {"run_id": run_id, "tests": [], "overall": "pass"}
    failed = False

    for i, command in enumerate(verification_commands):
        test_name = f"test_{i}"
        status = run_regression_test(command, test_name, state_dir, run_id)

        results["tests"].append({
            "test_name": test_name,
            "command": command,
            "status": status,
        })

        if status == "fail":
            failed = True
            results["overall"] = "fail"

    # Write report
    report_path = state_dir / f"regression-report_{run_id}.json"
    report_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
