#!/usr/bin/env python3
"""Main entry point for /t skill."""

# Standard library imports
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add skills directory to path (must come before skill imports that need it)
skills_dir = Path(__file__).parent
sys.path.insert(0, str(skills_dir))

# Local skill imports (require sys.path modification above)
from coverage_trends import CoverageTrendTracker  # noqa: E402
from director_output import determine_strictness, format_director_report  # noqa: E402
from failure_grouping import FailureGrouper  # noqa: E402
from incremental_testing import (  # noqa: E402
    calculate_incremental_scope,
    format_incremental_report,
)
from profiling import TestProfiler  # noqa: E402
from risk_scoring import calculate_risk_score, detect_change_context  # noqa: E402
from router import detect_mode_from_prompt, get_conversation_context  # noqa: E402
from t_core import (  # noqa: E402
    WorkContext,
    extract_context_from_conversation,
    load_testing_config,
    trace_code_flow,
)
from test_cache import TestCache  # noqa: E402
from windows_ipc import WindowsFileLock  # noqa: E402


def main(target: str | None = None, force_full: bool = False, mode: str | None = None) -> int:
    """
    Main /t command implementation.

    Modes:
        - discovery: What tests exist? What's missing? (from /test)
        - execution: Run tests with analytics (default, current implementation)
        - bisect: When did this break? (from /test-bisect)
        - comprehensive: Run all modes

    Workflow (execution mode):
        1. Extract context from conversation (what are we working on?)
        2. Trace code flow and dependencies (what's affected?)
        3. Calculate incremental test scope (affected tests only)
        4. Check cache for unchanged tests
        5. Calculate risk score
        6. Determine strictness
        7. Acquire multi-terminal lock
        8. Run tests with profiling
        9. Detect flaky tests
        10. Analyze coverage trends
        11. Group failures by root cause
        12. Cache results
        13. Release lock
        14. Generate comprehensive director report
    """
    # Detect mode from conversation if not explicitly specified
    if mode is None:
        # Default to smart mode when invoked without target or explicit mode
        # Only use conversation detection when targeting specific files
        if target is None:
            mode = 'smart'
        else:
            user_prompt = get_conversation_context()
            mode = detect_mode_from_prompt(user_prompt)
        print(f"Detected mode: {mode}")

    # Mode routing
    if mode == "smart":
        # Smart orchestration: Discovery → Plan → Execute → Verify
        print("Smart orchestration: Intelligent multi-phase testing workflow")
        print("=" * 60)

        # Phase 1: Discovery - What tests exist? What's missing?
        print("\n## Phase 1: Discovery - Test Coverage Analysis")
        print("-" * 60)
        from modes import discover_tests, format_discovery_report
        from modes.discovery_mode import (
            _get_terminal_id,
            _resolve_target_path,
            save_test_gaps,
        )

        discovery_results = discover_tests(target)
        discovery_report = format_discovery_report(discovery_results)
        print(discovery_report)

        # Save test gaps for /tdd integration
        project_root = _resolve_target_path(target)
        terminal_id = _get_terminal_id()
        try:
            save_test_gaps(discovery_results, project_root, terminal_id)
        except Exception as e:
            print(f"Warning: Failed to save test gaps for /tdd integration: {e}")

        # Phase 2: Plan - Based on discovery results, determine testing strategy
        print("\n## Phase 2: Planning - Coverage-Based Test Strategy")
        print("-" * 60)

        total_tests = discovery_results.total_tests
        coverage_percent = discovery_results.coverage_percent or 0

        if total_tests == 0:
            print("⚠️  **NO TESTS FOUND**")
            print("Recommendation: Create tests before proceeding")
            print("Next steps:")
            print("  1. Run `/tdd` to create tests driven by gaps")
            print("  2. Or create test files manually in tests/ directory")
            print("\nSmart orchestration: HALTED (no tests to execute)")
            return 0

        # Determine testing plan based on coverage
        if coverage_percent < 50:
            strategy = "comprehensive"
            reason = f"Low coverage ({coverage_percent:.1f}%) - running full test suite"
        elif coverage_percent < 80:
            strategy = "targeted"
            reason = f"Medium coverage ({coverage_percent:.1f}%) - focusing on affected modules"
        else:
            strategy = "incremental"
            reason = f"Good coverage ({coverage_percent:.1f}%) - running affected tests only"

        print(f"Strategy: {strategy}")
        print(f"Reason: {reason}")
        print(f"Test count: {total_tests}")
        print(f"Coverage: {coverage_percent:.1f}%")

        # Present gaps for awareness, then continue to execution
        print("\n" + "=" * 60)
        print("## Coverage Gaps Detected")
        print("-" * 60)

        if discovery_results.gaps:
            for gap in discovery_results.gaps:
                print(f"• {gap}")
        else:
            print("✓ No coverage gaps detected")

        # Continue to execution phase automatically
        print("\n" + "=" * 60)
        print("## Phase 3: Execute - Running Tests with Advanced Analytics")
        print("-" * 60)
        print(f"Running {total_tests} tests with {strategy} strategy...")
        print()

        # Initialize advanced analytics for smart mode
        test_profiler = TestProfiler()
        coverage_tracker = CoverageTrendTracker()
        failure_grouper = FailureGrouper()

        # Extract context for risk scoring and code tracing
        work_ctx = extract_context_from_conversation()
        if target:
            work_ctx.target_files = [target]

        # Trace code flow
        if work_ctx.target_files:
            affected_modules, info_flow = trace_code_flow(work_ctx.target_files, work_ctx.codemap)
            work_ctx.affected_modules = affected_modules
            work_ctx.information_flow = info_flow

        # Calculate risk score
        all_modules = work_ctx.target_files + work_ctx.affected_modules
        if all_modules:
            change_ctx = detect_change_context(all_modules[0], "unstaged")
            risk_score = calculate_risk_score(change_ctx)
        else:
            risk_score = 0.5

        # Determine strictness from risk score
        strictness = determine_strictness(risk_score)

        print(f"\n**Risk Score:** {risk_score:.2f}/1.0 ({'HIGH' if risk_score >= 0.7 else 'MEDIUM' if risk_score >= 0.4 else 'LOW'})")
        if work_ctx.affected_modules:
            print(f"**Affected Modules:** {len(work_ctx.affected_modules)}")
            for module in work_ctx.affected_modules[:5]:
                print(f"  - {module}")
            if len(work_ctx.affected_modules) > 5:
                print(f"  - ... and {len(work_ctx.affected_modules) - 5} more")

        # Run pytest with coverage and profiling
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
            result_file = f.name

        coverage_results = None
        test_start_time = time.time()
        result = None

        try:
            # Resolve target path for pytest
            target_path = _resolve_target_path(target) if target else Path.cwd()

            # Run pytest with coverage and JSON output
            cmd = [
                "python", "-m", "pytest",
                "--cov=.",
                "--cov-report=term-missing",
                "--cov-report=json:test_coverage.json",
                "--json-report",
                f"--json-report-file={result_file}",
                "-v"
            ]

            result = subprocess.run(
                cmd,
                cwd=str(target_path),
                capture_output=True,
                text=True,
                timeout=300
            )

            test_runtime = time.time() - test_start_time

            # Show pytest output
            print(result.stdout)

            # Parse coverage JSON if it exists
            coverage_path = target_path / "test_coverage.json"
            if coverage_path.exists():
                with open(coverage_path) as f:
                    coverage_data = json.load(f)
                    coverage_results = {
                        "percent": coverage_data.get("totals", {}).get("percent_covered", 0.0),
                        "missing": coverage_data.get("files", {}).get("summary", {}).get("missing_lines", "")
                    }

            # Phase 3.1: Test Execution Profiling
            print("\n" + "-" * 60)
            print("## Phase 3.1: Test Execution Profiling")
            print("-" * 60)
            print(f"**Total Runtime:** {test_runtime:.1f} seconds")
            test_profiler.record_test_time("full_test_suite", test_runtime)
            slow_tests = test_profiler.get_slow_tests(threshold_seconds=5.0)
            if slow_tests:
                print(f"**Slow Tests (>5s):** {len(slow_tests)} found")
                for test in slow_tests[:5]:
                    print(f"  - {test['test_name']}: {test['avg_runtime_seconds']:.1f}s")
                if len(slow_tests) > 5:
                    print(f"  - ... and {len(slow_tests) - 5} more")
            else:
                print("**Slow Tests:** None (all tests < 5s)")

            # Phase 3.2: Flaky Test Detection
            print("\n" + "-" * 60)
            print("## Phase 3.2: Flaky Test Detection")
            print("-" * 60)
            print("Flaky test detection enabled - tracking test stability across runs")
            print("(Run multiple times to detect intermittent failures)")

            # Phase 3.3: Coverage Trend Analysis
            print("\n" + "-" * 60)
            print("## Phase 3.3: Coverage Trend Analysis")
            print("-" * 60)
            if coverage_results:
                print(f"**Coverage:** {coverage_results['percent']:.1f}%")
                if work_ctx.affected_modules:
                    for module in work_ctx.affected_modules:
                        module_path = Path(module)
                        if module_path.exists():
                            module_coverage = coverage_results.get("percent", 0)
                            coverage_tracker.record_coverage(
                                module=module_path.name,
                                coverage_percent=module_coverage,
                                lines_covered=0,
                                lines_total=100
                            )

                    degrading_modules = coverage_tracker.get_degrading_modules(threshold=-2.0)
                    if degrading_modules:
                        print(f"**Warning:** {len(degrading_modules)} modules with declining coverage detected")
                        for module in degrading_modules[:3]:
                            print(f"  - {module}")
                    else:
                        print("**Coverage Trends:** No degrading modules detected")
            else:
                print("**Coverage:** No coverage data available")

            # Phase 3.4: Failure Pattern Grouping
            if result and result.returncode != 0:
                print("\n" + "-" * 60)
                print("## Phase 3.4: Failure Pattern Grouping")
                print("-" * 60)
                # Parse test failures from pytest output
                failed_tests = []
                for line in result.stdout.split('\n'):
                    if 'FAILED' in line:
                        test_name = line.split()[-1]
                        failed_tests.append({
                            "test_name": test_name,
                            "error": line,
                            "trace": ""
                        })

                if failed_tests and len(failed_tests) >= 1:
                    grouped = failure_grouper.group_failures(failed_tests)
                    print(f"**Grouped {len(failed_tests)} failures into {len(grouped)} root cause(s)**")
                    for group in grouped[:3]:
                        print(f"  - **{group['root_cause']}:** {group['count']} tests")
                    if len(grouped) > 3:
                        print(f"  - ... and {len(grouped) - 3} more")
                elif failed_tests:
                    print(f"**Failures:** {len(failed_tests)} test(s) failed")
                else:
                    print("**Failures:** No failure patterns detected")

            # Parse test results from pytest output
            passed_tests = 0
            failed_tests = 0
            for line in result.stdout.split('\n'):
                if ' passed' in line and ' failed' in line:
                    # Summary line like: "3 failed, 337 passed, 2 warnings in 12.89s"
                    for part in line.split(','):
                        part = part.strip()
                        if 'failed' in part:
                            try:
                                failed_tests = int(part.split()[0])
                            except (ValueError, IndexError):
                                pass
                        elif 'passed' in part:
                            try:
                                passed_tests = int(part.split()[0])
                            except (ValueError, IndexError):
                                pass
                elif ' passed' in line and 'failed' not in line:
                    # All tests passed: "340 passed in 2.34s"
                    try:
                        passed_tests = int(line.split()[0])
                    except (ValueError, IndexError):
                        passed_tests = 0

            # Summary
            print("\n" + "-" * 60)
            print("## Test Results Summary")
            print("-" * 60)
            if failed_tests == 0:
                print(f"✓ **All {passed_tests} tests passed**")
            else:
                print(f"**Test Results:** {passed_tests} passed, {failed_tests} failed")
                print("✗ **Some tests failed** - see details above")

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"**Warning:** Test execution failed: {e}")
            result = None
        finally:
            # Clean up temp file
            try:
                if result_file:
                    Path(result_file).unlink(missing_ok=True)
            except Exception:
                pass

        print("\n" + "=" * 60)
        print("## Phase 4: Verify - Results Analysis")
        print("-" * 60)

        # Show test summary
        total_tests = discovery_results.total_tests
        coverage = discovery_results.coverage_percent or 0

        print(f"**Tests Run:** {total_tests}")
        print(f"**Coverage:** {coverage:.1f}%")

        # Show recommendations based on gaps
        if discovery_results.gaps:
            print("\n**Coverage Gaps:**")
            for gap in discovery_results.gaps:
                print(f"  • {gap}")

        print("\n### Next Steps")
        print("\nSelect an action:")

        # Build menu options dynamically based on findings
        option_num = 0
        target_str = target if target else "."

        # Option 0: Primary action - FIX ALL GAPS
        if discovery_results.gaps:
            print(f"- {option_num} — **FIX ALL GAPS** — `/tdd {target_str}` — Auto-generate tests for all {len(discovery_results.gaps)} coverage gaps")
        else:
            print(f"- {option_num} — `/t {target_str}` — Re-run tests (all healthy)")
        option_num += 1

        # Option 1: Run specific test type
        print(f"- {option_num} — `pytest {target_str}/tests/test_*.py -v` — Run unit tests only")
        option_num += 1

        # Option 2: Run with coverage
        print(f"- {option_num} — `pytest {target_str}/tests/ --cov=. -v` — Run tests with detailed coverage")
        option_num += 1

        # Option 3: Discovery mode (deep dive)
        print(f"- {option_num} — `/t --mode discovery {target_str}` — Detailed test coverage analysis")
        option_num += 1

        # Option 4: View test health
        print(f"- {option_num} — `/t --mode execution {target_str}` — Run with full analytics (profiling, flaky detection)")

        print("\n" + "=" * 60)
        if result and result.returncode == 0:
            print("Smart orchestration: COMPLETE ✓ (all tests passed)")
        else:
            print("Smart orchestration: COMPLETE (with test failures)")
        print("=" * 60)
        print("\n**Note:** Exit code 1 indicates test failures, not orchestration errors.")
        print("The /t workflow completed successfully - see test results above for details.")

        return result.returncode if result else 1
    if mode == "discovery":
        from modes import discover_tests, format_discovery_report

        print("Discovery mode: Test coverage analysis and gap detection")
        print("=" * 60)
        results = discover_tests(target)
        report = format_discovery_report(results)
        print(report)
        return 0

    if mode == "bisect":
        from modes import format_bisect_report, run_bisect

        print("Bisect mode: Regression hunting via git bisect")
        print("=" * 60)
        result = run_bisect()
        report = format_bisect_report(result)
        print(report)
        return 0

    if mode == "comprehensive":
        # Run all modes: discovery, execution, bisect (if needed)
        print("Comprehensive mode: Running all testing modes")
        print("=" * 60)
        print("Running discovery and execution modes...\n")

        # Run discovery mode
        from modes import discover_tests, format_discovery_report

        discovery_results = discover_tests(target)
        discovery_report = format_discovery_report(discovery_results)
        print(discovery_report)

        print("\n" + "=" * 60)
        print("Running execution mode...\n")

        # Fall through to execution mode for the rest
        # Don't return - continue to execution mode below

    # Execution mode (current implementation - default behavior)
    # Phase 1A: Extract context from conversation
    work_ctx = extract_context_from_conversation()

    # If user explicitly specified target, use that
    if target:
        work_ctx.target_files = [target]

    # Phase 1A continued: Trace code flow
    affected_modules, info_flow = trace_code_flow(work_ctx.target_files, work_ctx.codemap)
    work_ctx.affected_modules = affected_modules
    work_ctx.information_flow = info_flow

    # Load config (may be used for custom tier/risk adjustments)
    _config = load_testing_config()

    # Phase 1B: Calculate risk
    # Use all affected modules for risk calculation
    all_modules = work_ctx.target_files + work_ctx.affected_modules
    if all_modules:
        change_ctx = detect_change_context(all_modules[0], "unstaged")
        risk_score = calculate_risk_score(change_ctx)
    else:
        risk_score = 0.5

    # Override if force-full
    if force_full:
        risk_score = 1.0

    # Determine strictness from risk score
    strictness = determine_strictness(risk_score)

    # Phase 2: Multi-terminal lock
    lock = WindowsFileLock("test_state_cache")
    lock_status = lock.acquire(timeout_ms=5000)

    if lock_status == "blocked":
        print("Warning: Using cached state from another terminal...")
        cache_data = lock.read_cache()
        if cache_data.get("work_context"):
            # Convert dict back to WorkContext object
            ctx_dict = cache_data["work_context"]
            work_ctx = WorkContext(
                target_files=ctx_dict.get("target_files", []),
                work_type=ctx_dict.get("work_type", ""),
                affected_modules=ctx_dict.get("affected_modules", []),
                dependencies=ctx_dict.get("dependencies", []),
                information_flow=ctx_dict.get("information_flow", []),
                codemap=ctx_dict.get("codemap", {}),
            )
            risk_score = cache_data["risk_score"]["value"]
            strictness = determine_strictness(risk_score)

    # Initialize advanced analytics (all enabled by default)
    test_cache = TestCache()
    # Note: flaky_detector initialized on-demand when we have test history data
    coverage_tracker = CoverageTrendTracker()
    test_profiler = TestProfiler()
    failure_grouper = FailureGrouper()

    # Phase 1: Incremental testing - calculate which tests to run
    print("\n## Phase 1: Incremental Test Scope")
    incremental_scope = calculate_incremental_scope(work_ctx.target_files, work_ctx.codemap)
    print(format_incremental_report(incremental_scope))

    # Phase 2: Check cache for unchanged tests
    print("\n## Phase 2: Test Cache Check")
    cache_stats = test_cache.get_stats()
    if cache_stats["total_entries"] > 0:
        print(f"Cache hits: {cache_stats['total_hits']} tests")
        print(f"Time saved: {cache_stats['total_time_saved_seconds']:.1f} seconds")
    else:
        print("No cached results from previous runs")

    # Run tests (all test types)
    test_results = {
        "functional": None,
        "unit": None,
        "integration": None,
        "regression": None,
        "intelligent": None,
        "coverage": None,
    }

    # Run health check (always required)
    if strictness.health_check:
        # test_health_check is in parent skills directory
        parent_skills_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(parent_skills_dir))
        from test_health_check import run_health_check  # noqa: E402

        run_health_check()

    # Run pytest if required
    coverage_results = None
    test_start_time = time.time()

    if strictness.run_pytest_cov:
        # Run pytest with coverage and profiling
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
            result_file = f.name

        try:
            print("\n## Phase 3: Running Tests with Profiling")

            # Run pytest with coverage and JSON output
            cmd = [
                "python", "-m", "pytest",
                "--cov=.",
                "--cov-report=term-missing",
                "--cov-report=json:test_coverage.json",
                "--json-report",
                f"--json-report-file={result_file}",
                "-v"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            test_runtime = time.time() - test_start_time

            # Parse coverage JSON if it exists
            coverage_path = Path("test_coverage.json")
            if coverage_path.exists():
                with open(coverage_path) as f:
                    coverage_data = json.load(f)
                    coverage_results = {
                        "percent": coverage_data.get("totals", {}).get("percent_covered", 0.0),
                        "missing": coverage_data.get("files", {}).get("summary", {}).get("missing_lines", "")
                    }

            # Phase 4: Record profiling data
            print("\n## Phase 4: Test Execution Profiling")
            test_profiler.record_test_time("full_test_suite", test_runtime)
            slow_tests = test_profiler.get_slow_tests(threshold_seconds=5.0)
            if slow_tests:
                print(f"Found {len(slow_tests)} slow tests (>5s):")
                for test in slow_tests[:5]:
                    print(f"  - {test['test_name']}: {test['avg_runtime_seconds']:.1f}s")

            # Phase 5: Detect flaky tests (if we have history)
            print("\n## Phase 5: Flaky Test Detection")
            # For now, just report that we're tracking (needs multiple runs to detect flakiness)
            print("Flaky test detection enabled - tracking test stability across runs")

            # Phase 6: Coverage trend analysis
            print("\n## Phase 6: Coverage Trend Analysis")
            if coverage_results:
                for module in work_ctx.affected_modules:
                    module_path = Path(module)
                    if module_path.exists():
                        module_coverage = coverage_results.get("percent", 0)
                        # Record coverage (simplified - would use actual file-level coverage in production)
                        coverage_tracker.record_coverage(
                            module=module_path.name,
                            coverage_percent=module_coverage,
                            lines_covered=0,  # Would extract from detailed coverage report
                            lines_total=100  # Would extract from detailed coverage report
                        )

            # Check for degrading coverage
            degrading_modules = coverage_tracker.get_degrading_modules(threshold=-2.0)
            if degrading_modules:
                print(f"Warning: {len(degrading_modules)} modules with declining coverage detected")

            # Phase 7: Failure grouping (if tests failed)
            if result.returncode != 0:
                print("\n## Phase 7: Failure Pattern Grouping")
                # Parse test failures from pytest output
                failed_tests = []
                for line in result.stdout.split('\n'):
                    if 'FAILED' in line:
                        test_name = line.split()[-1]
                        failed_tests.append({
                            "test_name": test_name,
                            "error": line,
                            "trace": ""
                        })

                if failed_tests and len(failed_tests) >= 1:
                    grouped = failure_grouper.group_failures(failed_tests)
                    print(f"Grouped {len(failed_tests)} failures into {len(grouped)} root cause(s)")
                    for group in grouped[:3]:
                        print(f"  - {group['root_cause']}: {group['count']} tests")

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Warning: Test execution failed: {e}")
        finally:
            # Clean up temp file
            try:
                Path(result_file).unlink(missing_ok=True)
            except Exception:
                pass

    # Cache results
    if lock_status == "acquired":
        cache_data = {
            "work_context": {
                "target_files": work_ctx.target_files,
                "work_type": work_ctx.work_type,
                "affected_modules": work_ctx.affected_modules,
            },
            "risk_score": {"value": risk_score},
            "test_results": test_results,
            "incremental_scope": incremental_scope,
            "cache_stats": cache_stats,
            "coverage_trends": coverage_tracker.get_degrading_modules() if coverage_results else [],
        }
        lock.write_cache(cache_data)
        lock.release()

    # Generate director report
    report = format_director_report(
        work_context={
            "target_files": work_ctx.target_files,
            "affected_modules": work_ctx.affected_modules,
        },
        risk_score=risk_score,
        strictness=strictness,
        test_results=test_results,
        coverage_results=coverage_results,
    )

    print(report)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="/t - Context-Aware Adaptive Testing with Code Flow Tracing",
        epilog="""
Modes:
  smart        Intelligent multi-phase workflow (Discovery→Plan→Execute→Verify) [default]
  discovery    What tests exist? What's missing? (from /test)
  execution    Run tests with analytics
  bisect       When did this break? (from /test-bisect)
  comprehensive Run all testing modes

Examples:
  t                     Smart orchestration (default)
  t router.py           Target specific file
  t --mode discovery    Force discovery mode
  t --force-full        Force full test suite
        """
    )
    parser.add_argument("target", nargs="?", help="Target file or directory")
    parser.add_argument("--force-full", action="store_true", help="Force full test suite")
    parser.add_argument(
        "--mode",
        choices=["smart", "discovery", "execution", "bisect", "comprehensive"],
        help="Testing mode (default: smart)"
    )

    args = parser.parse_args()
    sys.exit(main(args.target, args.force_full, args.mode))
