#!/usr/bin/env python3
"""Director-friendly formatting with decision tables."""

from __future__ import annotations

from typing import Any, NamedTuple


class TestStrictness(NamedTuple):
    """Test strictness settings based on risk."""

    t1_required: bool
    t2_required: bool
    run_pytest_cov: bool
    health_check: bool
    solo_dev_scan: bool


def determine_strictness(risk_score: float) -> TestStrictness:
    """
    Map risk score to test strictness.

    Risk Thresholds:
        0.0 - 0.4: LOW    → T1 optional, T2 warn-only
        0.4 - 0.7: MEDIUM → T1 required, T2 warn-only
        0.7 - 1.0: HIGH   → T1+T2 required, hard fail

    Always run:
        - health_check (fast, prevents test suite issues)
        - solo_dev_scan (constitutional compliance)
    """
    if risk_score >= 0.7:
        return TestStrictness(
            t1_required=True,
            t2_required=True,
            run_pytest_cov=True,
            health_check=True,
            solo_dev_scan=True,
        )
    elif risk_score >= 0.4:
        return TestStrictness(
            t1_required=True,
            t2_required=False,
            run_pytest_cov=True,
            health_check=True,
            solo_dev_scan=True,
        )
    else:
        return TestStrictness(
            t1_required=False,
            t2_required=False,
            run_pytest_cov=False,
            health_check=True,
            solo_dev_scan=True,
        )


def format_director_report(
    work_context: dict[str, Any],
    risk_score: float,
    strictness: TestStrictness,
    test_results: dict[str, Any],
    coverage_results: dict[str, Any] | None = None,
) -> str:
    """
    Format output as director decision summary.

    Sections:
        1. Executive Summary (risk + decision)
        2. Decision Table (what tests to run)
        3. Gap Analysis (AI-ready priority list)
        4. Actionable Next Steps (DUF-style options)
    """
    # Extract incremental scope from test_results if available
    incremental_scope = test_results.get("incremental_scope", {})
    total_tests = incremental_scope.get("total_tests", 0)
    affected_tests = incremental_scope.get("affected_tests", [])

    # Determine if tests need to be created
    needs_test_creation = total_tests == 0 or (affected_tests and len(affected_tests) == 0)

    lines = [
        "## Executive Summary",
        "",
        f"Risk Score: {risk_score:.2f}/1.0 ({'HIGH' if risk_score >= 0.7 else 'MEDIUM' if risk_score >= 0.4 else 'LOW'})",
        f"Context: Working on {', '.join(work_context.get('target_files', ['unknown']))}",
        f"Affected: {len(work_context.get('affected_modules', []))} modules",
        f"Strictness: {'Strict (T1+T2, all test types)' if strictness.t2_required else 'Moderate (T1 only)' if strictness.t1_required else 'Relaxed (optional)'}",
        "",
    ]

    # Add explicit warning if no tests found
    if needs_test_creation:
        lines.extend([
            "⚠️ **WARNING: No tests found in target directory**",
            "",
            "This module has ZERO test coverage. You should create tests before proceeding.",
            "",
        ])

    lines.extend([
        "## Decision Table",
        "",
        "| Component | Required | Rationale |",
        "|-----------|----------|-----------|",
    ])

    # Build decision table
    components = [
        ("Functional", strictness.t1_required, "Core functionality testing"),
        ("Unit Tests", strictness.t1_required, "Tier 1 critical path coverage"),
        ("Integration", strictness.t1_required, "Tests module interactions"),
        ("Regression", strictness.t1_required, "Prevents regressions in deps"),
        ("Intelligent", strictness.t2_required, "AI-generated edge case tests"),
        ("Pytest Cov", strictness.run_pytest_cov, "Coverage analysis"),
        ("Health Chk", strictness.health_check, "Prevents collection errors"),
        ("Solo-Dev", strictness.solo_dev_scan, "Constitutional compliance"),
    ]

    for component, required, rationale in components:
        lines.append(f"| {component} | {'YES' if required else 'NO'}      | {rationale} |")

    lines.extend(["", "## Gap Analysis", ""])

    # Add gap analysis if coverage results available
    if coverage_results:
        missing = coverage_results.get("missing", "")
        if missing:
            lines.append(f"**Missing Coverage:** {missing}")
            lines.append("")

    # Add actionable next steps with explicit action items
    lines.extend(["## Next Steps", ""])

    if needs_test_creation:
        # Explicit action: Create tests
        target_files = work_context.get('target_files', ['this module'])
        lines.extend([
            "🚨 **IMMEDIATE ACTION REQUIRED:**",
            "",
            f"1. **Create tests for:** {', '.join(target_files)}",
            "   - Start with unit tests for core functions",
            "   - Add integration tests for module interactions",
            "   - Include edge case and error path tests",
            "",
            "2. **Recommended approach:**",
            "   - Run `/tdd` to create tests driven by gaps",
            "   - Or create test files manually in tests/ directory",
            "",
            "3. **Approval required:**",
            "   - Should I create a test plan for this module? (y/n)",
            "",
        ])
    else:
        # Standard next steps when tests exist
        lines.append("1. Review and address any coverage gaps")
        lines.append("2. Run full test suite if high-risk changes detected")
        lines.append("3. Validate solo-dev compliance")
        lines.append("4. Generate intelligent tests for edge cases")

    return "\n".join(lines)
