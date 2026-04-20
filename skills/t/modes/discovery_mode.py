#!/usr/bin/env python3
"""Discovery mode for /t skill - What tests exist? What's missing?"""

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestInfo:
    """Information about a discovered test."""
    file_path: str
    test_name: str
    test_type: str  # unit, integration, edge_case, error_path, regression
    line_number: int | None = None


@dataclass
class DiscoveryResults:
    """Results from test discovery analysis."""
    target: str
    tests_found: list[TestInfo] = field(default_factory=list)
    total_tests: int = 0
    test_types: dict[str, int] = field(default_factory=dict)
    coverage_percent: float | None = None
    missing_coverage: str = ""
    solo_dev_violations: list[dict] = field(default_factory=list)
    health_issues: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


def _resolve_target_path(target: str | None = None) -> Path:
    """
    Resolve the target path to a concrete directory.

    Args:
        target: Target path (file, directory, or None for CWD)

    Returns:
        Resolved directory path
    """
    if target is None:
        return Path.cwd()

    target_path = Path(target).resolve()

    # If target is a file, use its parent directory
    if target_path.is_file():
        return target_path.parent

    # If target is a directory, use it directly
    if target_path.is_dir():
        return target_path

    # Target doesn't exist, return as-is (will fail later)
    return target_path


def _get_terminal_id() -> str:
    """
    Get the terminal/session ID for multi-terminal coordination.

    Returns:
        Terminal identifier string
    """
    return os.environ.get("WT_SESSION") or os.environ.get("TERM") or f"pid-{os.getpid()}"


def discover_tests(target: str | None = None) -> DiscoveryResults:
    """
    Discover all tests related to target.

    Workflow:
        1. Find test files via patterns (test_*.py, *_integration.py)
        2. Classify tests by type (unit, integration, edge case, error path, regression)
        3. Run health check (slow tests, bad paths, missing markers)
        4. Scan for solo-dev pattern violations
        5. Run pytest coverage for real coverage %
        6. Generate structured report

    Args:
        target: Target file or module to analyze

    Returns:
        DiscoveryResults with all findings
    """
    results = DiscoveryResults(target=target or "project root")

    # Step 1: Discover test files
    test_files = _find_test_files(target)
    print(f"Found {len(test_files)} test files")

    # Step 2: Parse and classify tests
    for test_file in test_files:
        tests = _parse_test_file(test_file)
        results.tests_found.extend(tests)
        results.total_tests += len(tests)

    # Step 3: Classify by type
    results.test_types = _classify_by_type(results.tests_found)

    # Step 4: Run health check
    results.health_issues = _run_health_check(target)

    # Step 5: Scan for solo-dev violations
    results.solo_dev_violations = _scan_solo_dev_patterns(target)

    # Step 6: Run pytest coverage
    coverage_data = _run_pytest_coverage(target)
    if coverage_data:
        results.coverage_percent = coverage_data.get("percent", 0.0)
        results.missing_coverage = coverage_data.get("missing", "")

    # Step 7: Identify gaps
    results.gaps = _identify_gaps(results, target)

    return results


def _find_test_files(target: str | None = None) -> list[Path]:
    """Find all test files related to target."""
    test_patterns = [
        "tests/test_*.py",
        "tests/*_integration.py",
        "tests/integration/*.py",
        "test_*.py",
        "*_test.py",
    ]

    test_files = []
    project_root = _resolve_target_path(target)

    for pattern in test_patterns:
        for file_path in project_root.glob(pattern):
            if file_path.is_file() and file_path.suffix == ".py":
                test_files.append(file_path)

    # Deduplicate
    test_files = list(set(test_files))
    return sorted(test_files)


def _parse_test_file(file_path: Path) -> list[TestInfo]:
    """Parse a test file and extract test information."""
    tests = []
    try:
        content = file_path.read_text()
        lines = content.split("\n")

        for i, line in enumerate(lines, start=1):
            # Match test function definitions
            match = re.match(r"^\s*def (test_\w+)\(.*\):", line)
            if match:
                test_name = match.group(1)
                test_type = _classify_test(test_name, file_path.name)
                tests.append(TestInfo(
                    file_path=str(file_path),
                    test_name=test_name,
                    test_type=test_type,
                    line_number=i
                ))
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}")

    return tests


def _classify_test(test_name: str, file_name: str) -> str:
    """Classify a test by type."""
    name_lower = test_name.lower()

    # Check for integration tests
    if "_integration" in name_lower or "_flow" in name_lower or file_name.endswith("_integration.py"):
        return "integration"

    # Check for edge case tests
    if "edge" in name_lower or "boundary" in name_lower or "empty" in name_lower:
        return "edge_case"

    # Check for error path tests
    if "error" in name_lower or "invalid" in name_lower or "corrupt" in name_lower:
        return "error_path"

    # Check for regression tests
    if "regression" in name_lower or "bisect" in name_lower or "reproduce" in name_lower:
        return "regression"

    # Default: unit test
    return "unit"


def _classify_by_type(tests: list[TestInfo]) -> dict[str, int]:
    """Count tests by type."""
    counts = {"unit": 0, "integration": 0, "edge_case": 0, "error_path": 0, "regression": 0}
    for test in tests:
        counts[test.test_type] = counts.get(test.test_type, 0) + 1
    return counts


def _run_health_check(_target: str | None = None) -> list[dict]:
    """Run health check and return issues."""
    issues = []

    try:
        # Import and run health check from parent skills directory
        parent_skills_dir = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(parent_skills_dir))
        from test_health_check import run_health_check  # noqa: E402

        health_results = run_health_check()

        # Convert to list of issues
        if health_results.get("has_issues"):
            for category, items in health_results.items():
                if isinstance(items, list):
                    for item in items:
                        issues.append({
                            "category": category,
                            "file": item.get("file", "unknown"),
                            "line": item.get("line", "unknown"),
                            "message": item.get("message", "")
                        })
    except ImportError:
        issues.append({
            "category": "health_check",
            "file": "N/A",
            "line": "N/A",
            "message": "test_health_check.py not available"
        })
    except Exception as e:
        issues.append({
            "category": "health_check",
            "file": "N/A",
            "line": "N/A",
            "message": f"Health check failed: {e}"
        })

    return issues


def _scan_solo_dev_patterns(target: str | None = None) -> list[dict]:
    """Scan target for solo-dev constitutional violations."""
    violations = []

    forbidden_patterns = [
        "continuous.monitoring",
        "self.healing",
        "autonomous.execution",
        "team.approval",
        "lock.ordering",
        "enterprise.grade",
        "real.time.metrics",
        "scalability.requirement"
    ]

    # If target is a file, scan it
    # If target is None or a directory, scan all Python files
    if target and Path(target).is_file():
        files_to_scan = [Path(target)]
    else:
        # Scan all .py files in project
        project_root = _resolve_target_path(target)
        files_to_scan = list(project_root.rglob("*.py"))

    for file_path in files_to_scan:
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            for i, line in enumerate(lines, start=1):
                for pattern in forbidden_patterns:
                    if pattern in line:
                        violations.append({
                            "pattern": pattern,
                            "file": str(file_path),
                            "line": i,
                            "snippet": line.strip()
                        })
        except Exception:
            continue

    return violations


def _run_pytest_coverage(_target: str | None = None) -> dict | None:
    """Run pytest and return coverage data."""
    try:
        # Run pytest with coverage
        cmd = [
            "python", "-m", "pytest",
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-report-json=test_coverage.json",
            "-v"
        ]

        _ = subprocess.run(  # Run pytest, output captured via JSON
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        # Parse coverage JSON if it exists
        coverage_path = Path("test_coverage.json")
        if coverage_path.exists():
            with open(coverage_path) as f:
                coverage_data = json.load(f)
                return {
                    "percent": coverage_data.get("totals", {}).get("percent_covered", 0.0),
                    "missing": coverage_data.get("files", {}).get("summary", {}).get("missing_lines", "")
                }

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: Coverage collection failed: {e}")
    except Exception as e:
        print(f"Warning: Unexpected error: {e}")

    return None


def _identify_gaps(results: DiscoveryResults, _target: str | None) -> list[str]:
    """Identify test gaps and missing coverage."""
    gaps = []

    # Add health check gaps
    for issue in results.health_issues:
        gaps.append(f"Health issue: {issue['message']}")

    # Add solo-dev violation gaps
    for violation in results.solo_dev_violations:
        gaps.append(f"Solo-dev violation: {violation['pattern']} in {Path(violation['file']).name}:{violation['line']}")

    # Add coverage gaps
    if results.coverage_percent and results.coverage_percent < 100:
        gaps.append(f"Coverage gap: {results.coverage_percent:.1f}% covered, missing: {results.missing_coverage}")

    # Add missing test type gaps
    for test_type, count in results.test_types.items():
        if count == 0:
            gaps.append(f"Missing test type: {test_type} tests")

    return gaps


def format_discovery_report(results: DiscoveryResults) -> str:
    """Format discovery results as a readable report."""
    lines = [
        "# Test Coverage Discovery Report",
        "",
        f"**Target:** {results.target}",
        f"**Tests Found:** {results.total_tests}",
        "",
        "## Test Classification",
        ""
    ]

    for test_type, count in results.test_types.items():
        lines.append(f"- **{test_type.replace('_', ' ').title()}:** {count}")

    lines.extend([
        "",
        "## Coverage Summary",
        ""
    ])

    if results.coverage_percent is not None:
        lines.append(f"**Coverage:** {results.coverage_percent:.1f}%")
        if results.missing_coverage:
            lines.append(f"**Missing:** {results.missing_coverage}")
    else:
        lines.append("*Coverage data unavailable*")

    lines.extend([
        "",
        "## Health Check Issues",
        ""
    ])

    if results.health_issues:
        for issue in results.health_issues:
            lines.append(f"❌ **{issue['category']}:** {Path(issue['file']).name}:{issue['line']}")
            lines.append(f"   {issue['message']}")
    else:
        lines.append("*No health issues detected*")

    lines.extend([
        "",
        "## Solo-Dev Violations",
        ""
    ])

    if results.solo_dev_violations:
        for violation in results.solo_dev_violations[:10]:  # Limit to first 10
            lines.append(f"❌ **{violation['pattern']}:** {Path(violation['file']).name}:{violation['line']}")
    else:
        lines.append("*No solo-dev violations detected*")

    lines.extend([
        "",
        "## Coverage Gaps",
        ""
    ])

    if results.gaps:
        for gap in results.gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("*No gaps identified*")

    return "\n".join(lines)


def save_test_gaps(results: DiscoveryResults, project_root: Path, terminal_id: str) -> None:
    """
    Save discovery results to terminal-scoped gap file for /tdd integration.

    Uses atomic handoff pattern:
    - Write to _PENDING.json (in progress)
    - Rename to _READY.json (atomic signal for /tdd to consume)

    Args:
        results: Discovery results from discover_tests()
        project_root: Project root directory
        terminal_id: Terminal/session identifier
    """
    from datetime import UTC, datetime

    gaps_dir = project_root / ".claude" / "state" / "test_gaps"
    gaps_dir.mkdir(parents=True, exist_ok=True)

    pending_file = gaps_dir / f"{terminal_id}_gaps_PENDING.json"

    # Prepare gap data
    gaps_data = {
        "target": results.target,
        "gaps": results.gaps,
        "test_types": results.test_types,
        "coverage_percent": results.coverage_percent,
        "total_tests": results.total_tests,
        "timestamp": datetime.now(UTC).isoformat()
    }

    # Write to temp file first (atomic pattern)
    fd, temp_path = tempfile.mkstemp(suffix=".json", dir=gaps_dir, text=True)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(gaps_data, f, indent=2)

        # Atomic rename to PENDING
        os.replace(temp_path, str(pending_file))

        # Atomic rename to READY (signal for /tdd)
        ready_file = pending_file.with_name("_READY.json")
        pending_file.rename(ready_file)

    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    # Test the discovery mode
    results = discover_tests()
    print(format_discovery_report(results))
