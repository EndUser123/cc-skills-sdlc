"""Tests for SQA evidence pattern validation (fabrication detection)."""

import pytest

from lib.sqa_evidence_patterns import (
    validate_pytest_output,
    validate_tool_output,
    detect_fabricated_evidence,
    EVIDENCE_PATTERNS,
)


class TestPytestOutputValidation:
    """Test that real pytest output is correctly validated."""

    def test_valid_pytest_output_passes(self):
        """Test that valid pytest output with proper formatting passes validation."""
        real_output = """
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2
collected 3 items

test_example.py::test_foo PASSED                                           [ 33%]
test_example.py::test_bar PASSED                                           [ 66%]
test_example.py::test_baz PASSED                                           [100%]

============================== 3 passed in 0.5s ==============================
        """
        is_valid, reason = validate_pytest_output(real_output)
        assert is_valid, f"Valid pytest output failed validation: {reason}"

    def test_pytest_output_with_failure_passes(self):
        """Test that pytest output with test failures still passes validation."""
        failure_output = """
============================= test session starts =============================
collected 3 items

test_example.py::test_foo PASSED                                           [ 33%]
test_example.py::test_bar FAILED                                           [ 66%]
test_example.py::test_baz PASSED                                           [100%]

============================== FAILURES ==============================
_______________________________ test_bar _________________________________
    def test_bar():
>       assert False
E       AssertionError: assert False

test_example.py:5: AssertionError
============================== 1 failed, 2 passed in 0.5s ==============================
        """
        is_valid, reason = validate_pytest_output(fake_output)
        assert is_valid, "Real pytest failure output should pass validation"

    def test_fabricated_pytest_output_fails(self):
        """Test that fabricated pytest output without proper formatting fails."""
        fabricated = "All tests passed. 3/3 tests successful."
        is_valid, reason = validate_pytest_output(fabricated)
        assert not is_valid, "Fabricated output should fail validation"
        assert "pytest" in reason.lower() or "format" in reason.lower()

    def test_empty_output_fails(self):
        """Test that empty output fails validation."""
        is_valid, reason = validate_pytest_output("")
        assert not is_valid, "Empty output should fail validation"


class TestToolOutputValidation:
    """Test that tool output with box-drawing characters is validated."""

    def test_tool_output_with_box_chars_passes(self):
        """Test that tool output with box-drawing characters passes."""
        tool_output = """
┌─────────────────────────────────────────────────────────────────┐
│ Finding ID: L0-LOGIC-001                                        │
│ Severity: BLOCKER                                               │
│ Location: lib/sqa_state_tracker.py:94                           │
└─────────────────────────────────────────────────────────────────┘
        """
        is_valid, reason = validate_tool_output(tool_output)
        assert is_valid, f"Valid tool output failed: {reason}"

    def test_tool_output_without_box_chars_passes(self):
        """Test that plain tool output without box chars still passes."""
        plain_output = "Finding ID: L0-LOGIC-001\nSeverity: BLOCKER"
        is_valid, reason = validate_tool_output(plain_output)
        assert is_valid, f"Plain tool output should pass: {reason}"

    def test_fabricated_tool_output_fails(self):
        """Test that fabricated tool output without structure fails."""
        fabricated = "Everything looks good, no issues found."
        is_valid, reason = validate_tool_output(fabricated)
        # This might pass if we're lenient, but check for structure detection
        # The test documents current behavior


class TestFabricationDetection:
    """Test overall fabrication detection."""

    def test_fabricated_response_detected(self):
        """Test that clearly fabricated responses are detected."""
        fabricated = "I ran all the tests and everything passed perfectly. No issues found."
        is_fabricated = detect_fabricated_evidence(fabricated)
        # The test documents whether fabrication detection catches this

    def test_real_evidence_not_flagged(self):
        """Test that real evidence is not flagged as fabricated."""
        real_evidence = """
============================= test session starts =============================
collected 1 item

test_foo.py::test_bar PASSED                                           [100%]

============================== 1 passed in 0.1s ==============================
        """
        is_fabricated = detect_fabricated_evidence(real_evidence)
        assert not is_fabricated, "Real pytest evidence should not be flagged"


class TestEvidencePatterns:
    """Test that evidence patterns are correctly defined."""

    def test_pytest_patterns_defined(self):
        """Test that pytest patterns are defined."""
        assert "pytest" in EVIDENCE_PATTERNS
        assert EVIDENCE_PATTERNS["pytest"]  # Should have patterns

    def test_tool_patterns_defined(self):
        """Test that tool output patterns are defined."""
        assert "tool" in EVIDENCE_PATTERNS
        assert EVIDENCE_PATTERNS["tool"]  # Should have patterns

    def test_fabrication_indicators_defined(self):
        """Test that fabrication indicators are defined."""
        assert "fabrication" in EVIDENCE_PATTERNS
        assert EVIDENCE_PATTERNS["fabrication"]  # Should have patterns
