#!/usr/bin/env python3
"""Test director-friendly formatting with decision tables."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from director_output import TestStrictness, determine_strictness, format_director_report


def test_determine_strictness_high_risk():
    """Test strictness mapping for high risk (>= 0.7)."""
    strictness = determine_strictness(0.7)

    assert strictness.t1_required is True
    assert strictness.t2_required is True
    assert strictness.run_pytest_cov is True
    assert strictness.health_check is True
    assert strictness.solo_dev_scan is True


def test_determine_strictness_high_risk_upper_bound():
    """Test strictness mapping for maximum risk (1.0)."""
    strictness = determine_strictness(1.0)

    assert strictness.t1_required is True
    assert strictness.t2_required is True
    assert strictness.run_pytest_cov is True


def test_determine_strictness_medium_risk():
    """Test strictness mapping for medium risk (0.4 - 0.7)."""
    strictness = determine_strictness(0.5)

    # Medium risk: T1 required, T2 not required
    assert strictness.t1_required is True
    assert strictness.t2_required is False
    assert strictness.run_pytest_cov is True
    assert strictness.health_check is True
    assert strictness.solo_dev_scan is True


def test_determine_strictness_medium_risk_lower_boundary():
    """Test strictness mapping at medium risk boundary (0.4)."""
    strictness = determine_strictness(0.4)

    # Exactly 0.4 should be medium risk
    assert strictness.t1_required is True
    assert strictness.t2_required is False


def test_determine_strictness_low_risk():
    """Test strictness mapping for low risk (< 0.4)."""
    strictness = determine_strictness(0.3)

    # Low risk: T1 and T2 optional
    assert strictness.t1_required is False
    assert strictness.t2_required is False
    assert strictness.run_pytest_cov is False
    assert strictness.health_check is True
    assert strictness.solo_dev_scan is True


def test_determine_strictness_zero_risk():
    """Test strictness mapping for zero risk (0.0)."""
    strictness = determine_strictness(0.0)

    # Zero risk still has health_check and solo_dev_scan
    assert strictness.t1_required is False
    assert strictness.t2_required is False
    assert strictness.run_pytest_cov is False
    assert strictness.health_check is True
    assert strictness.solo_dev_scan is True


def test_determine_strictness_always_runs_health_check():
    """Test that health_check is always True regardless of risk."""
    for risk_score in [0.0, 0.2, 0.4, 0.6, 0.7, 1.0]:
        strictness = determine_strictness(risk_score)
        assert strictness.health_check is True, f"health_check should be True for risk_score={risk_score}"


def test_determine_strictness_always_runs_solo_dev_scan():
    """Test that solo_dev_scan is always True regardless of risk."""
    for risk_score in [0.0, 0.2, 0.4, 0.6, 0.7, 1.0]:
        strictness = determine_strictness(risk_score)
        assert strictness.solo_dev_scan is True, f"solo_dev_scan should be True for risk_score={risk_score}"


def test_format_director_report_high_risk():
    """Test report formatting with high risk score."""
    work_context = {
        "target_files": ["router.py", "auth.py"],
        "affected_modules": ["handlers.py", "validators.py", "api.py"],
    }

    strictness = TestStrictness(
        t1_required=True,
        t2_required=True,
        run_pytest_cov=True,
        health_check=True,
        solo_dev_scan=True,
    )

    test_results = {"functional": "passed", "unit": "passed"}
    coverage_results = {"percent": 85.0, "missing": "23-27, 45-50"}
    health_results = {"passed": True}

    report = format_director_report(
        work_context=work_context,
        risk_score=0.8,
        strictness=strictness,
        test_results=test_results,
        coverage_results=coverage_results,
        health_results=health_results,
    )

    # Verify executive summary
    assert "## Executive Summary" in report
    assert "Risk Score: 0.80/1.0 (HIGH)" in report
    assert "Context: Working on router.py, auth.py" in report
    assert "Affected: 3 modules" in report
    assert "Strictness: Strict (T1+T2, all test types)" in report

    # Verify decision table
    assert "## Decision Table" in report
    assert "| Functional | YES" in report
    assert "| Unit Tests | YES" in report
    assert "| Integration | YES" in report
    assert "| Intelligent | YES" in report
    assert "| Pytest Cov | YES" in report
    assert "| Health Chk | YES" in report
    assert "| Solo-Dev | YES" in report

    # Verify gap analysis
    assert "## Gap Analysis" in report
    assert "**Missing Coverage:** 23-27, 45-50" in report

    # Verify next steps
    assert "## Next Steps" in report


def test_format_director_report_medium_risk():
    """Test report formatting with medium risk score."""
    work_context = {
        "target_files": ["utils/config.py"],
        "affected_modules": [],
    }

    strictness = TestStrictness(
        t1_required=True,
        t2_required=False,
        run_pytest_cov=True,
        health_check=True,
        solo_dev_scan=True,
    )

    test_results = {"functional": "passed"}

    report = format_director_report(
        work_context=work_context,
        risk_score=0.5,
        strictness=strictness,
        test_results=test_results,
    )

    # Verify risk level is MEDIUM
    assert "Risk Score: 0.50/1.0 (MEDIUM)" in report

    # Verify strictness is Moderate (T1 only)
    assert "Strictness: Moderate (T1 only)" in report

    # Verify T2 not required
    assert "| Intelligent | NO" in report


def test_format_director_report_low_risk():
    """Test report formatting with low risk score."""
    work_context = {
        "target_files": ["docs/readme.md"],
        "affected_modules": [],
    }

    strictness = TestStrictness(
        t1_required=False,
        t2_required=False,
        run_pytest_cov=False,
        health_check=True,
        solo_dev_scan=True,
    )

    test_results = {}

    report = format_director_report(
        work_context=work_context,
        risk_score=0.2,
        strictness=strictness,
        test_results=test_results,
    )

    # Verify risk level is LOW
    assert "Risk Score: 0.20/1.0 (LOW)" in report

    # Verify strictness is Relaxed
    assert "Strictness: Relaxed (optional)" in report

    # Verify most tests are NO
    assert "| Functional | NO" in report
    assert "| Pytest Cov | NO" in report

    # But health_check and solo_dev_scan are always YES
    assert "| Health Chk | YES" in report
    assert "| Solo-Dev | YES" in report


def test_format_director_report_empty_work_context():
    """Test report formatting with minimal work context."""
    work_context = {}

    strictness = determine_strictness(0.6)
    test_results = {}

    report = format_director_report(
        work_context=work_context,
        risk_score=0.6,
        strictness=strictness,
        test_results=test_results,
    )

    # Should handle missing fields gracefully
    assert "## Executive Summary" in report
    assert "Context: Working on unknown" in report
    assert "Affected: 0 modules" in report


def test_format_director_report_no_coverage_results():
    """Test report formatting without coverage results."""
    work_context = {
        "target_files": ["src/module.py"],
        "affected_modules": [],
    }

    strictness = determine_strictness(0.6)
    test_results = {"unit": "passed"}

    report = format_director_report(
        work_context=work_context,
        risk_score=0.6,
        strictness=strictness,
        test_results=test_results,
        coverage_results=None,
    )

    # Should have Gap Analysis section but no missing coverage
    assert "## Gap Analysis" in report
    assert "**Missing Coverage:**" not in report


def test_format_director_report_missing_coverage_empty():
    """Test report formatting with empty missing coverage."""
    work_context = {"target_files": ["test.py"], "affected_modules": []}

    strictness = determine_strictness(0.7)
    test_results = {}
    coverage_results = {"missing": ""}  # Empty missing coverage

    report = format_director_report(
        work_context=work_context,
        risk_score=0.7,
        strictness=strictness,
        test_results=test_results,
        coverage_results=coverage_results,
    )

    # Should not show missing coverage when empty
    assert "**Missing Coverage:**" not in report


def test_format_director_report_decision_table_structure():
    """Test that decision table has correct structure."""
    work_context = {"target_files": ["test.py"], "affected_modules": []}

    strictness = determine_strictness(0.5)
    test_results = {}

    report = format_director_report(
        work_context=work_context,
        risk_score=0.5,
        strictness=strictness,
        test_results=test_results,
    )

    # Verify table headers
    assert "| Component | Required | Rationale |" in report
    assert "|-----------|----------|-----------|" in report

    # Verify all 8 components are present
    components = [
        "Functional",
        "Unit Tests",
        "Integration",
        "Regression",
        "Intelligent",
        "Pytest Cov",
        "Health Chk",
        "Solo-Dev",
    ]

    for component in components:
        assert f"| {component} |" in report


if __name__ == "__main__":
    test_determine_strictness_high_risk()
    print("✅ test_determine_strictness_high_risk passed")

    test_determine_strictness_high_risk_upper_bound()
    print("✅ test_determine_strictness_high_risk_upper_bound passed")

    test_determine_strictness_medium_risk()
    print("✅ test_determine_strictness_medium_risk passed")

    test_determine_strictness_medium_risk_lower_boundary()
    print("✅ test_determine_strictness_medium_risk_lower_boundary passed")

    test_determine_strictness_low_risk()
    print("✅ test_determine_strictness_low_risk passed")

    test_determine_strictness_zero_risk()
    print("✅ test_determine_strictness_zero_risk passed")

    test_determine_strictness_always_runs_health_check()
    print("✅ test_determine_strictness_always_runs_health_check passed")

    test_determine_strictness_always_runs_solo_dev_scan()
    print("✅ test_determine_strictness_always_runs_solo_dev_scan passed")

    test_format_director_report_high_risk()
    print("✅ test_format_director_report_high_risk passed")

    test_format_director_report_medium_risk()
    print("✅ test_format_director_report_medium_risk passed")

    test_format_director_report_low_risk()
    print("✅ test_format_director_report_low_risk passed")

    test_format_director_report_empty_work_context()
    print("✅ test_format_director_report_empty_work_context passed")

    test_format_director_report_no_coverage_results()
    print("✅ test_format_director_report_no_coverage_results passed")

    test_format_director_report_missing_coverage_empty()
    print("✅ test_format_director_report_missing_coverage_empty passed")

    test_format_director_report_decision_table_structure()
    print("✅ test_format_director_report_decision_table_structure passed")

    print("\nAll director_output tests passed!")
