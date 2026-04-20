#!/usr/bin/env python3
"""Test discovery and coverage analysis for /code skill.

This module provides functionality to discover tests and analyze actual coverage
using pytest, documenting gaps rather than making assumptions.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class TestDiscovery:
    """Discover and analyze test coverage for /code skill."""

    def __init__(self, project_root: Path):
        """Initialize test discovery.

        Args:
            project_root: Path to /code skill directory
        """
        self.project_root = Path(project_root)
        self.tests_dir = self.project_root / "tests"
        self.lib_dir = self.project_root / "lib"
        self.hooks_dir = self.project_root / "hooks"

    def run_pytest_with_coverage(
        self, cov_targets: list[str], verbose: bool = True, timeout: int = 120
    ) -> dict[str, Any]:
        """Run pytest with coverage and return results.

        Args:
            cov_targets: List of coverage targets (e.g., ["lib", "hooks"])
            verbose: Enable verbose output
            timeout: Timeout in seconds (default: 120)

        Returns:
            Dict with test results and coverage data
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(self.tests_dir),
            "-v" if verbose else "-q",
            f"--timeout={timeout}",  # Use timeout parameter
        ]

        # Add coverage arguments
        for target in cov_targets:
            cmd.extend([f"--cov={target}"])

        cmd.extend(["--cov-report=json", "--cov-report=term-missing"])

        print(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, cwd=str(self.project_root), capture_output=True, text=True, timeout=timeout
            )

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired as e:
            # Try to get partial output
            partial_output = ""
            try:
                if e.stdout:
                    partial_output = e.stdout.decode("utf-8", errors="ignore")
            except:
                pass

            return {
                "exit_code": -1,
                "stdout": partial_output,
                "stderr": f"pytest timed out after {timeout} seconds. Consider running tests separately or increasing timeout.",
                "success": False,
                "timeout": True,
            }
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}

    def parse_coverage_report(self, coverage_file: Path) -> dict[str, Any]:
        """Parse pytest-cov coverage.json file.

        Args:
            coverage_file: Path to coverage.json

        Returns:
            Dict with parsed coverage data
        """
        if not coverage_file.exists():
            return {
                "error": f"Coverage file not found: {coverage_file}",
                "files": {},
                "summary": {},
            }

        try:
            with open(coverage_file) as f:
                data = json.load(f)

            return {
                "files": data.get("files", {}),
                "summary": data.get("totals", {}),
                "covered_lines": data.get("totals", {}).get("covered_lines", 0),
                "num_statements": data.get("totals", {}).get("num_statements", 0),
                "percent_covered": data.get("totals", {}).get("percent_covered", 0.0),
            }
        except Exception as e:
            return {"error": f"Failed to parse coverage file: {e}", "files": {}, "summary": {}}

    def analyze_coverage_gaps(self, coverage_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Analyze coverage data and identify gaps.

        Args:
            coverage_data: Parsed coverage data from parse_coverage_report

        Returns:
            List of coverage gaps (files below threshold)
        """
        gaps = []
        threshold = 80.0  # 80% coverage threshold

        for filename, file_data in coverage_data.get("files", {}).items():
            summary = file_data.get("summary", {})
            percent_covered = summary.get("percent_covered", 0.0)

            if percent_covered < threshold:
                missing_lines = summary.get("missing_lines", 0)
                gaps.append(
                    {
                        "file": filename,
                        "percent_covered": percent_covered,
                        "missing_lines": missing_lines,
                        "gap": threshold - percent_covered,
                    }
                )

        # Sort by gap size (descending)
        gaps.sort(key=lambda x: x["gap"], reverse=True)

        return gaps

    def generate_discovery_report(self, timeout: int = 120) -> str:
        """Generate comprehensive test discovery report.

        Args:
            timeout: Timeout in seconds for pytest execution

        Returns:
            Formatted report with test results and coverage analysis
        """
        lines = []
        lines.append("=" * 70)
        lines.append("Test Discovery Report")
        lines.append("=" * 70)
        lines.append("")

        # Run pytest with coverage
        cov_targets = []
        if self.lib_dir.exists():
            cov_targets.append("lib")
        if self.hooks_dir.exists():
            cov_targets.append("hooks")

        if not cov_targets:
            lines.append("No coverage targets found (lib/ or hooks/ directories)")
            lines.append("")
            lines.append("Recommendation: Run tests without coverage")
            lines.append("  Command: pytest tests/ -v")
            lines.append("=" * 70)
            return "\n".join(lines)

        result = self.run_pytest_with_coverage(cov_targets, timeout=timeout)

        lines.append("Pytest Output:")
        lines.append("-" * 70)
        if result["stdout"]:
            # Show last 50 lines of stdout to avoid overwhelming output
            stdout_lines = result["stdout"].split("\n")
            if len(stdout_lines) > 50:
                lines.append(f"... ({len(stdout_lines) - 50} lines omitted) ...\n")
                lines.extend(stdout_lines[-50:])
            else:
                lines.append(result["stdout"])
        else:
            lines.append("(No output)")

        if result.get("timeout"):
            lines.append("")
            lines.append("⚠️ TEST TIMEOUT WARNING")
            lines.append("-" * 70)
            lines.append(f"Tests timed out after {timeout} seconds.")
            lines.append("")
            lines.append("Recommendations:")
            lines.append("  1. Run tests separately: pytest tests/ -v --timeout=180")
            lines.append("  2. Run specific test files: pytest tests/test_<module>.py -v")
            lines.append("  3. Check for hanging tests or infinite loops")
            lines.append("  4. Increase timeout: python tests/test_discovery.py")

        if result["stderr"]:
            lines.append("")
            lines.append("Errors/Warnings:")
            lines.append("-" * 70)
            lines.append(result["stderr"])

        # Parse coverage data (only if tests completed)
        if not result.get("timeout"):
            coverage_file = self.project_root / "coverage.json"
            coverage_data = self.parse_coverage_report(coverage_file)

            if "error" in coverage_data:
                lines.append("")
                lines.append(f"Coverage Parse Error: {coverage_data['error']}")
                lines.append("")
                lines.append("Possible causes:")
                lines.append("  - Tests failed before coverage could be generated")
                lines.append("  - pytest-cov plugin not installed")
                lines.append("  - No tests found for specified modules")
            else:
                lines.append("")
                lines.append("Coverage Summary:")
                lines.append("-" * 70)
                lines.append(f"Total Statements: {coverage_data.get('num_statements', 0)}")
                lines.append(f"Covered Lines: {coverage_data.get('covered_lines', 0)}")
                lines.append(f"Coverage: {coverage_data.get('percent_covered', 0.0):.1f}%")

                # Analyze gaps
                gaps = self.analyze_coverage_gaps(coverage_data)

                if gaps:
                    lines.append("")
                    lines.append("Coverage Gaps (Below 80% threshold):")
                    lines.append("-" * 70)
                    for gap in gaps[:10]:  # Show top 10 gaps
                        lines.append(
                            f"  {gap['file']}: {gap['percent_covered']:.1f}% "
                            f"(gap: {gap['gap']:.1f}%, "
                            f"missing: {gap['missing_lines']} lines)"
                        )
                    if len(gaps) > 10:
                        lines.append(f"  ... and {len(gaps) - 10} more files with coverage gaps")
                else:
                    lines.append("")
                    lines.append("✓ All files meet 80% coverage threshold")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


def test_discovery_basic():
    """Test basic test discovery functionality."""
    project_root = Path(__file__).parent.parent

    discovery = TestDiscovery(project_root)

    # Verify initialization
    assert discovery.project_root == project_root
    assert discovery.tests_dir == project_root / "tests"
    assert discovery.lib_dir == project_root / "lib"
    assert discovery.hooks_dir == project_root / "hooks"


def test_run_pytest_with_coverage():
    """Test running pytest with coverage."""
    project_root = Path(__file__).parent.parent

    discovery = TestDiscovery(project_root)

    # Run pytest with coverage (should work even if tests fail)
    result = discovery.run_pytest_with_coverage(["lib"])

    # Verify result structure
    assert "exit_code" in result
    assert "stdout" in result
    assert "stderr" in result
    assert "success" in result

    # Verify pytest was actually run
    assert "pytest" in result["stdout"] or result["exit_code"] != 0


def test_parse_coverage_report_missing_file():
    """Test parsing coverage report when file doesn't exist."""
    project_root = Path(__file__).parent.parent
    discovery = TestDiscovery(project_root)

    coverage_file = project_root / "nonexistent_coverage.json"
    data = discovery.parse_coverage_report(coverage_file)

    # Should return error structure
    assert "error" in data
    assert "not found" in data["error"]


def test_analyze_coverage_gaps_empty_data():
    """Test coverage gap analysis with empty data."""
    project_root = Path(__file__).parent.parent
    discovery = TestDiscovery(project_root)

    gaps = discovery.analyze_coverage_gaps({"files": {}})

    # Should return empty list
    assert gaps == []


def test_generate_discovery_report():
    """Test generating discovery report."""
    project_root = Path(__file__).parent.parent
    discovery = TestDiscovery(project_root)

    report = discovery.generate_discovery_report()

    # Verify report structure
    assert "Test Discovery Report" in report
    assert "=" * 70 in report
    assert len(report) > 100  # Should have substantial content


if __name__ == "__main__":
    """CLI entry point for test discovery."""

    # Find project root
    project_root = Path(__file__).parent.parent

    # Create TestDiscovery instance
    discovery = TestDiscovery(project_root)

    # Generate and print report
    report = discovery.generate_discovery_report()
    print(report)
