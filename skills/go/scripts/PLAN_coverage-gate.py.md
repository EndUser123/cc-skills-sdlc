# Implementation Plan: coverage-gate.py

## Overview

Create `P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/go/scripts/coverage-gate.py` to enforce minimum test coverage thresholds as a quality gate in the /go orchestrator workflow.

## Context

This script follows the same pattern as `mutation-gate.py`:
- Integrates with /go orchestrator via RUN_ID and GO_STATE_DIR
- Writes verification-result JSON for workflow integration
- Uses proper exit codes (0=success, non-zero=failure)
- Supports env var configuration
- Emits stderr progress messages with gate name prefix

## File to Create

**Path:** `P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/go/scripts/coverage-gate.py`

**Size:** ~350 lines

## Implementation Tasks

### Task 1: Setup and Imports
**Action:** Write file header with imports and constants

**Code:**
```python
#!/usr/bin/env python3
"""Coverage gate for /go - enforce minimum test coverage thresholds."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_THRESHOLD = 80
DEFAULT_MODE = "absolute"
```

**Verification:** `python -m py_compile coverage-gate.py` succeeds

---

### Task 2: Define Dataclasses
**Action:** Add CoverageModule and CoverageGateResult dataclasses

**Code:**
```python
@dataclass
class CoverageModule:
    name: str
    pct_covered: float
    num_statements: int
    num_missing: int
    num_covered: int


@dataclass
class CoverageGateResult:
    run_id: str
    status: str
    threshold: float
    mode: str
    overall_pct: float
    modules: list[CoverageModule] = field(default_factory=list)
    failed_modules: list[str] = field(default_factory=list)
    reason: str = ""
    generated_at: str = ""
```

**Verification:** `python -c "from coverage_gate import CoverageModule; c = CoverageModule('test', 80.0, 100, 20, 80); print(c.name)"` prints "test"

---

### Task 3: Helper Functions
**Action:** Implement now_iso(), write_json(), and load_coverage_from_json()

**Code:**
```python
def now_iso() -> str:
    """Get current timestamp in ISO format with UTC timezone."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: dict[str, Any] | list[Any]) -> None:
    """Write JSON data to file with pretty formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def load_coverage_from_json(coverage_json: Path) -> dict[str, Any]:
    """Load coverage data from coverage.json (pytest-cov --cov-report=json)."""
    with coverage_json.open("r", encoding="utf-8") as f:
        return json.load(f)
```

**Verification:** `python -c "from coverage_gate import write_json, now_iso; import tempfile; p = Path(tempfile.mktemp()); write_json(p, {'test': now_iso()}); print(p.read_text())"` prints valid JSON

---

### Task 4: Load Coverage from .coverage File
**Action:** Implement load_coverage_from_file() to convert .coverage to JSON

**Code:**
```python
def load_coverage_from_file(coverage_file: Path) -> dict[str, Any]:
    """
    Load coverage data from .coverage file.
    Converts coverage.db format to dict structure using coverage report command.
    """
    try:
        result = subprocess.run(
            ["coverage", "report", "--json", f"--data-file={coverage_file}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to convert coverage file: {e.stderr}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from coverage report: {e}") from e
```

**Verification:** Create dummy .coverage file, run function, expect RuntimeError

---

### Task 5: Extract Module Coverage
**Action:** Implement get_module_coverage() to parse coverage data

**Code:**
```python
def get_module_coverage(coverage_data: dict[str, Any]) -> list[CoverageModule]:
    """Extract module coverage from coverage data structure."""
    modules: list[CoverageModule] = []
    files = coverage_data.get("files", {})

    if not files:
        return modules

    for file_path, file_data in files.items():
        module_name = file_path.replace("/", ".").replace("\\", ".").replace(".py", "")
        summary = file_data.get("summary", {})
        pct_covered = summary.get("percent_covered", 0.0)
        num_statements = summary.get("num_statements", 0)
        num_missing = summary.get("num_missing", 0)
        num_covered = num_statements - num_missing

        modules.append(
            CoverageModule(
                name=module_name,
                pct_covered=pct_covered,
                num_statements=num_statements,
                num_missing=num_missing,
                num_covered=num_covered,
            )
        )
    return modules
```

**Verification:** Test with coverage.json sample data, verify module extraction

---

### Task 6: Load Module Thresholds
**Action:** Implement get_module_thresholds() to read quality_gates.json

**Code:**
```python
def get_module_thresholds(project_root: Path) -> dict[str, float]:
    """Load per-module thresholds from quality_gates.json if exists."""
    config_path = project_root / "quality_gates.json"
    if not config_path.exists():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("coverage_thresholds", {})
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"Warning: Failed to load quality_gates.json: {e}", file=sys.stderr)
        return {}
```

**Verification:** Test with/without quality_gates.json, verify behavior

---

### Task 7: Calculate Overall Coverage
**Action:** Implement calculate_overall_coverage()

**Code:**
```python
def calculate_overall_coverage(modules: list[CoverageModule]) -> float:
    """Calculate overall coverage percentage across all modules."""
    if not modules:
        return 0.0

    total_statements = sum(m.num_statements for m in modules)
    if total_statements == 0:
        return 0.0

    total_covered = sum(m.num_covered for m in modules)
    return (total_covered / total_statements) * 100
```

**Verification:** Test with sample modules, verify calculation accuracy

---

### Task 8: Coverage Gate Check
**Action:** Implement check_coverage_gate() with threshold validation

**Code:**
```python
def check_coverage_gate(
    modules: list[CoverageModule],
    threshold: float,
    mode: str,
    module_thresholds: dict[str, float] | None = None,
) -> CoverageGateResult:
    """
    Check if coverage meets the threshold.

    Args:
        modules: List of coverage modules
        threshold: Coverage threshold percentage
        mode: 'absolute' or 'delta'
        module_thresholds: Optional per-module thresholds

    Returns:
        CoverageGateResult with pass/fail status
    """
    module_thresholds = module_thresholds or {}
    overall_pct = calculate_overall_coverage(modules)
    failed_modules: list[str] = []

    for module in modules:
        module_threshold = module_thresholds.get(module.name, threshold)
        if module.pct_covered < module_threshold:
            failed_modules.append(
                f"{module.name} ({module.pct_covered:.1f}% < {module_threshold:.1f}%)"
            )

    if mode == "absolute":
        status = "fail" if failed_modules else "pass"
        reason = f"Overall coverage: {overall_pct:.1f}% (threshold: {threshold:.1f}%)"
        if failed_modules:
            reason += f" - Failed modules: {', '.join(failed_modules[:5])}"
            if len(failed_modules) > 5:
                reason += f" and {len(failed_modules) - 5} more"
    else:
        status = "fail" if failed_modules else "pass"
        reason = f"Delta mode - Overall coverage: {overall_pct:.1f}%"

    run_id = os.getenv("RUN_ID", "unknown")

    return CoverageGateResult(
        run_id=run_id,
        status=status,
        threshold=threshold,
        mode=mode,
        overall_pct=overall_pct,
        modules=modules,
        failed_modules=failed_modules,
        reason=reason,
        generated_at=now_iso(),
    )
```

**Verification:** Test pass/fail cases with various coverage levels

---

### Task 9: Write Verification Result
**Action:** Implement write_verification_result() for /go integration

**Code:**
```python
def write_verification_result(
    state_dir: Path,
    result: CoverageGateResult,
) -> None:
    """Write verification result JSON for /go workflow integration."""
    path = state_dir / f"verification-result_{result.run_id}.json"

    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
    else:
        payload = {}

    payload.update(
        {
            "run_id": result.run_id,
            "status": result.status,
            "pr_ready": result.status == "pass",
            "coverage": {
                "threshold": result.threshold,
                "actual": result.overall_pct,
                "mode": result.mode,
                "reason": result.reason,
            },
            "generated_at": result.generated_at,
        }
    )

    artifact_paths = payload.setdefault("artifact_paths", {})
    artifact_paths["coverage_gate"] = str(state_dir / f"coverage-gate-{result.run_id}.json")

    write_json(path, payload)
```

**Verification:** Test writing verification result, verify JSON structure

---

### Task 10: Main Function - Argument Parsing
**Action:** Implement main() with argparse

**Code:**
```python
def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Coverage gate for /go orchestrator - enforce minimum test coverage"
    )
    parser.add_argument(
        "--coverage-file",
        type=Path,
        default=None,
        help="Path to coverage.json or .coverage file (default: auto-detect)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=f"Coverage threshold percentage (default: {DEFAULT_THRESHOLD}%, env: GO_COVERAGE_THRESHOLD)",
    )
    parser.add_argument(
        "--mode",
        choices=["absolute", "delta"],
        default=None,
        help=f"Coverage mode (default: {DEFAULT_MODE}, env: GO_COVERAGE_MODE)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory for quality_gates.json lookup (default: cwd)",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path.cwd() / ".verification-results",
        help="State directory for verification results (env: GO_STATE_DIR)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()
    # ... rest of implementation
```

**Verification:** `python coverage-gate.py --help` displays usage

---

### Task 11: Main Function - Configuration Loading
**Action:** Complete configuration loading with env var fallbacks

**Code:**
```python
    # Get configuration from env or args
    threshold = (
        float(os.getenv("GO_COVERAGE_THRESHOLD", args.threshold))
        if args.threshold is None
        else args.threshold
    )
    if threshold is None:
        threshold = DEFAULT_THRESHOLD

    mode = os.getenv("GO_COVERAGE_MODE", args.mode) if args.mode is None else args.mode
    if mode is None:
        mode = DEFAULT_MODE

    state_dir = Path(os.getenv("GO_STATE_DIR", str(args.state_dir)))
    state_dir = state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    run_id = os.getenv("RUN_ID") or os.getenv("GO_RUN_ID", "")
    if not run_id:
        print("ERROR: RUN_ID not set", file=sys.stderr)
        return 2
```

**Verification:** Test with env vars set/unset, verify correct defaults

---

### Task 12: Main Function - Coverage File Detection
**Action:** Auto-detect and load coverage file

**Code:**
```python
    # Auto-detect coverage file
    coverage_file = args.coverage_file
    if coverage_file is None:
        # Try coverage.json first, then .coverage
        for filename in ["coverage.json", ".coverage"]:
            candidate = args.project_root / filename
            if candidate.exists():
                coverage_file = candidate
                if args.verbose:
                    print(f"[coverage-gate] Auto-detected coverage file: {coverage_file}", file=sys.stderr)
                break

    if coverage_file is None:
        print("[coverage-gate] ERROR: No coverage file found (coverage.json or .coverage)", file=sys.stderr)
        print("[coverage-gate] Run pytest with --cov to generate coverage data", file=sys.stderr)
        return 1

    if not coverage_file.exists():
        print(f"[coverage-gate] ERROR: Coverage file not found: {coverage_file}", file=sys.stderr)
        return 1
```

**Verification:** Test with/without coverage files, verify error messages

---

### Task 13: Main Function - Load and Process Coverage
**Action:** Load coverage data and extract modules

**Code:**
```python
    # Load coverage data
    try:
        if coverage_file.name == "coverage.json":
            coverage_data = load_coverage_from_json(coverage_file)
        else:
            coverage_data = load_coverage_from_file(coverage_file)
    except Exception as e:
        print(f"[coverage-gate] ERROR loading coverage data: {e}", file=sys.stderr)
        return 1

    # Extract module coverage
    modules = get_module_coverage(coverage_data)

    if not modules:
        print("[coverage-gate] ERROR: No modules found in coverage data", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"[coverage-gate] Loaded {len(modules)} modules", file=sys.stderr)
```

**Verification:** Test with valid/invalid coverage files, verify module extraction

---

### Task 14: Main Function - Run Coverage Gate
**Action:** Execute gate check and generate reports

**Code:**
```python
    # Load per-module thresholds
    module_thresholds = get_module_thresholds(args.project_root)

    # Check coverage gate
    result = check_coverage_gate(modules, threshold, mode, module_thresholds)

    if args.verbose:
        print(f"[coverage-gate] Status: {result.status.upper()}", file=sys.stderr)
        print(f"[coverage-gate] Mode: {result.mode}", file=sys.stderr)
        print(f"[coverage-gate] Threshold: {result.threshold:.1f}%", file=sys.stderr)
        print(f"[coverage-gate] Overall Coverage: {result.overall_pct:.1f}%", file=sys.stderr)
        if result.failed_modules:
            print(f"[coverage-gate] Failed Modules ({len(result.failed_modules)}):", file=sys.stderr)
            for fm in result.failed_modules[:10]:
                print(f"[coverage-gate]   - {fm}", file=sys.stderr)

    # Write coverage report
    coverage_report_path = state_dir / f"coverage-gate-{result.run_id}.json"
    coverage_report = {
        "schema_version": "go.coverage-gate.v1",
        "run_id": result.run_id,
        "status": result.status,
        "threshold": result.threshold,
        "mode": result.mode,
        "overall_pct": result.overall_pct,
        "modules": [
            {
                "name": m.name,
                "pct_covered": m.pct_covered,
                "num_statements": m.num_statements,
                "num_missing": m.num_missing,
                "num_covered": m.num_covered,
            }
            for m in result.modules
        ],
        "failed_modules": result.failed_modules,
        "reason": result.reason,
        "generated_at": result.generated_at,
    }
    write_json(coverage_report_path, coverage_report)
    if args.verbose:
        print(f"[coverage-gate] Coverage report: {coverage_report_path}", file=sys.stderr)
```

**Verification:** Run gate, verify coverage report JSON structure

---

### Task 15: Main Function - Write Verification and Exit
**Action:** Write verification result and return exit code

**Code:**
```python
    # Write verification result
    write_verification_result(state_dir, result)
    if args.verbose:
        print(f"[coverage-gate] Verification result written to state directory", file=sys.stderr)

    # Exit with appropriate code
    if result.status == "fail":
        print(f"[coverage-gate] BLOCK: {result.reason}", file=sys.stderr)
        return 1
    else:
        print(f"[coverage-gate] PASS: {result.reason}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Verification:** Test pass/fail cases, verify exit codes (0 for pass, 1 for fail)

---

## Testing Checklist

### Unit Tests
- [ ] Test now_iso() returns valid ISO timestamp
- [ ] Test write_json() creates valid JSON file
- [ ] Test load_coverage_from_json() with valid/invalid files
- [ ] Test get_module_coverage() with sample data
- [ ] Test get_module_thresholds() with/without quality_gates.json
- [ ] Test calculate_overall_coverage() accuracy
- [ ] Test check_coverage_gate() pass/fail logic
- [ ] Test write_verification_result() JSON structure

### Integration Tests
- [ ] Test auto-detection of coverage.json vs .coverage
- [ ] Test env var override behavior (GO_COVERAGE_THRESHOLD, GO_COVERAGE_MODE, GO_STATE_DIR)
- [ ] Test RUN_ID requirement and error handling
- [ ] Test verbose output format
- [ ] Test exit codes (0=pass, 1=fail, 2=config error)

### Manual Verification
- [ ] Create sample coverage.json with pytest-cov
- [ ] Run `python scripts/coverage-gate.py --verbose`
- [ ] Verify coverage-report-{run_id}.json structure
- [ ] Verify verification-result-{run_id}.json structure
- [ ] Test with quality_gates.json per-module thresholds
- [ ] Test delta mode vs absolute mode

## Success Criteria

1. Script runs without syntax errors
2. Correctly loads coverage.json and .coverage files
3. Calculates overall coverage accurately
4. Enforces threshold with proper pass/fail logic
5. Writes both coverage-report and verification-result JSON files
6. Returns correct exit codes (0=pass, 1=fail, 2=config error)
7. Supports GO_COVERAGE_THRESHOLD and GO_COVERAGE_MODE env vars
8. Supports quality_gates.json per-module thresholds
9. Emits stderr messages with [coverage-gate] prefix
10. Integration with /go workflow verified

## Dependencies

- Python 3.10+ (dataclass field default_factory)
- coverage (for .coverage file conversion)
- pytest-cov (for coverage.json generation)

## Integration Points

- Called by /go orchestrator during verification phase
- Reads from: coverage.json or .coverage, quality_gates.json
- Writes to: {GO_STATE_DIR}/coverage-gate-{run_id}.json, verification-result-{run_id}.json
- Environment variables: RUN_ID, GO_RUN_ID, GO_STATE_DIR, GO_COVERAGE_THRESHOLD, GO_COVERAGE_MODE