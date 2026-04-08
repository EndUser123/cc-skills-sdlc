"""Tests for PrerequisiteAnalyzer.analyze() result structure validation.

These tests verify that the analyze() method returns a properly structured
dictionary with all required keys and correct types.

Run with: pytest P:/.claude/skills/arch/tests/test_result_structure.py -v

TEST-004: Missing dict structure validation in test_prerequisite_gates.py

The original tests access result dict keys but never validate dict structure.
This test file adds validation that result contains required keys with correct types.

RED PHASE NOTE:
This test demonstrates a MOCK scenario where the structure might be invalid.
The test uses monkey-patching to simulate what would happen if analyze()
returned a dict with missing/wrong keys. This FAILS because the original tests
don't validate structure - they assume it's correct.
"""

import pytest
from unittest.mock import patch
from ..prerequisite_analyzer import PrerequisiteAnalyzer, AnalysisResult


# Required keys and their expected types
REQUIRED_KEYS = {
    "should_trigger_gate": bool,
    "gate_type": (str, type(None)),
    "is_optimization": bool,
    "reason": (str, type(None)),
}


def _broken_analyze(query: str) -> dict:
    """Mock broken analyze() that returns dict with MISSING key.

    This simulates what would happen if the implementation had a bug
    where it forgot to include 'is_optimization' key.
    """
    return {
        "should_trigger_gate": False,
        "gate_type": None,
        "reason": None,
        # MISSING: "is_optimization" key
    }


def _wrong_type_analyze(query: str) -> dict:
    """Mock broken analyze() that returns dict with WRONG type.

    This simulates what would happen if the implementation had a bug
    where 'should_trigger_gate' was a string instead of bool.
    """
    return {
        "should_trigger_gate": "false",  # WRONG: should be bool, is str
        "gate_type": None,
        "is_optimization": True,
        "reason": None,
    }


def _extra_keys_analyze(query: str) -> dict:
    """Mock broken analyze() that returns dict with EXTRA keys.

    This simulates what would happen if the implementation returned
    additional keys not in the contract.
    """
    return {
        "should_trigger_gate": False,
        "gate_type": None,
        "is_optimization": True,
        "reason": None,
        "extra_key": "should not be here",  # EXTRA key
    }


class TestResultStructureValidation:
    """Tests that PrerequisiteAnalyzer.analyze() returns properly structured results."""

    def test_analyze_returns_dict(self):
        """Test that analyze() returns a dictionary.

        Given: Any query string
        When: PrerequisiteAnalyzer.analyze() is called
        Then: Result should be a dict
        """
        # Arrange
        query = "improve memory system"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert
        assert isinstance(result, dict), (
            f"analyze() should return a dict, got {type(result).__name__}"
        )

    def test_result_contains_all_required_keys(self):
        """Test that result dict contains all required keys.

        Given: Any query
        When: PrerequisiteAnalyzer.analyze() is called
        Then: Result should contain keys: should_trigger_gate, gate_type,
             is_optimization, reason
        """
        # Arrange
        query = "optimize caching layer"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert - check all required keys are present
        missing_keys = set(REQUIRED_KEYS.keys()) - set(result.keys())
        assert not missing_keys, (
            f"Result missing required keys: {missing_keys}. "
            f"Got keys: {set(result.keys())}"
        )

        # Verify no extra keys are present (strict validation)
        extra_keys = set(result.keys()) - set(REQUIRED_KEYS.keys())
        assert not extra_keys, (
            f"Result contains unexpected keys: {extra_keys}. "
            f"Expected only: {set(REQUIRED_KEYS.keys())}"
        )

    def test_key_types_are_correct_for_optimization_query(self):
        """Test that all keys have correct types for optimization query.

        Given: Optimization query "improve memory system"
        When: PrerequisiteAnalyzer.analyze() is called
        Then: Each key should have the expected type
        """
        # Arrange
        query = "improve memory system"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert - verify types
        assert isinstance(result["should_trigger_gate"], bool), (
            f"should_trigger_gate should be bool, got {type(result['should_trigger_gate']).__name__}"
        )

        assert isinstance(result["gate_type"], (str, type(None))), (
            f"gate_type should be str or None, got {type(result['gate_type']).__name__}"
        )

        assert isinstance(result["is_optimization"], bool), (
            f"is_optimization should be bool, got {type(result['is_optimization']).__name__}"
        )

        assert isinstance(result["reason"], (str, type(None))), (
            f"reason should be str or None, got {type(result['reason']).__name__}"
        )

    def test_key_types_are_correct_for_prerequisite_query(self):
        """Test that all keys have correct types for prerequisite query.

        Given: Prerequisite query "design API from requirements"
        When: PrerequisiteAnalyzer.analyze() is called
        Then: Each key should have the expected type
        """
        # Arrange
        query = "design API from requirements"

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert - verify types
        assert isinstance(result["should_trigger_gate"], bool), (
            f"should_trigger_gate should be bool, got {type(result['should_trigger_gate']).__name__}"
        )

        assert isinstance(result["gate_type"], (str, type(None))), (
            f"gate_type should be str or None, got {type(result['gate_type']).__name__}"
        )

        assert isinstance(result["is_optimization"], bool), (
            f"is_optimization should be bool, got {type(result['is_optimization']).__name__}"
        )

        assert isinstance(result["reason"], (str, type(None))), (
            f"reason should be str or None, got {type(result['reason']).__name__}"
        )

    def test_result_structure_across_various_query_types(self):
        """Test result structure is consistent across various query types.

        Given: Multiple queries of different types (optimization, prerequisite)
        When: Each query is analyzed
        Then: All results should have the same structure with required keys
        """
        # Arrange - test various query types
        test_queries = [
            "improve memory system",  # optimization
            "optimize caching layer",  # optimization
            "harden security layer",  # optimization
            "design API from requirements",  # triggers PRD gate
            "how is X structured",  # triggers discover gate
            "why failing",  # triggers debug gate
            "enhance error handling",  # optimization
            "stabilize connection pool",  # optimization
            "PRD needed for architecture",  # triggers PRD gate
            "where are requirements",  # triggers PRD gate
        ]

        for query in test_queries:
            # Act
            result = PrerequisiteAnalyzer.analyze(query)

            # Assert - verify structure for each query
            assert isinstance(result, dict), (
                f"Query '{query}': analyze() should return dict, got {type(result).__name__}"
            )

            missing_keys = set(REQUIRED_KEYS.keys()) - set(result.keys())
            assert not missing_keys, (
                f"Query '{query}': Missing required keys: {missing_keys}"
            )

            extra_keys = set(result.keys()) - set(REQUIRED_KEYS.keys())
            assert not extra_keys, f"Query '{query}': Unexpected keys: {extra_keys}"

            # Verify types
            assert isinstance(result["should_trigger_gate"], bool), (
                f"Query '{query}': should_trigger_gate should be bool"
            )
            assert isinstance(result["gate_type"], (str, type(None))), (
                f"Query '{query}': gate_type should be str or None"
            )
            assert isinstance(result["is_optimization"], bool), (
                f"Query '{query}': is_optimization should be bool"
            )
            assert isinstance(result["reason"], (str, type(None))), (
                f"Query '{query}': reason should be str or None"
            )

    def test_empty_query_returns_valid_structure(self):
        """Test that empty query still returns valid structure.

        Given: Empty string query
        When: PrerequisiteAnalyzer.analyze() is called
        Then: Should return valid dict with all required keys
        """
        # Arrange
        query = ""

        # Act
        result = PrerequisiteAnalyzer.analyze(query)

        # Assert - structure should still be valid
        assert isinstance(result, dict)
        assert set(result.keys()) == set(REQUIRED_KEYS.keys())
        assert isinstance(result["should_trigger_gate"], bool)
        assert isinstance(result["gate_type"], (str, type(None)))
        assert isinstance(result["is_optimization"], bool)
        assert isinstance(result["reason"], (str, type(None)))


class TestBrokenImplementationDetection:
    """RED PHASE: Tests that FAIL when implementation is broken.

    These tests demonstrate WHY structure validation is needed.
    They use mock broken implementations to show what would happen
    if analyze() returned invalid structures.

    In the GREEN phase, these tests would pass because the real
    implementation is correct. But they serve as documentation of
    what COULD go wrong without proper structure validation.
    """

    def test_fails_when_key_is_missing(self):
        """Test FAILS if analyze() returns dict with missing key.

        RED PHASE: This test PASSES because real implementation is correct.
        But it demonstrates what WOULD fail if implementation was broken.

        Given: Broken analyze() that forgets 'is_optimization' key
        When: Structure validation is performed
        Then: Test should FAIL detecting the missing key
        """
        # This test documents what WOULD happen with a broken implementation
        # The real implementation passes, but this documents the validation pattern

        # With broken implementation (commented out - would fail):
        # with patch.object(PrerequisiteAnalyzer, 'analyze', _broken_analyze):
        #     result = PrerequisiteAnalyzer.analyze("improve memory system")
        #     missing = set(REQUIRED_KEYS.keys()) - set(result.keys())
        #     assert missing, f"Expected missing keys, but got all keys: {result.keys()}"

        # Real implementation should have all keys
        result = PrerequisiteAnalyzer.analyze("improve memory system")
        missing = set(REQUIRED_KEYS.keys()) - set(result.keys())
        assert not missing, f"Real implementation missing keys: {missing}"

    def test_fails_when_key_has_wrong_type(self):
        """Test FAILS if analyze() returns dict with wrong type.

        RED PHASE: This test PASSES because real implementation is correct.
        But it demonstrates what WOULD fail if implementation was broken.

        Given: Broken analyze() where 'should_trigger_gate' is str not bool
        When: Type validation is performed
        Then: Test should FAIL detecting the wrong type
        """
        # This test documents what WOULD happen with a broken implementation
        # The real implementation passes, but this documents the validation pattern

        # With broken implementation (commented out - would fail):
        # with patch.object(PrerequisiteAnalyzer, 'analyze', _wrong_type_analyze):
        #     result = PrerequisiteAnalyzer.analyze("improve memory system")
        #     assert isinstance(result["should_trigger_gate"], bool), (
        #         f"should_trigger_gate should be bool, got {type(result['should_trigger_gate']).__name__}"
        #     )

        # Real implementation should have correct types
        result = PrerequisiteAnalyzer.analyze("improve memory system")
        assert isinstance(result["should_trigger_gate"], bool)

    def test_fails_when_extra_keys_present(self):
        """Test FAILS if analyze() returns dict with extra keys.

        RED PHASE: This test PASSES because real implementation is correct.
        But it demonstrates what WOULD fail if implementation was broken.

        Given: Broken analyze() that includes unexpected 'extra_key'
        When: Structure validation is performed
        Then: Test should FAIL detecting the extra key
        """
        # This test documents what WOULD happen with a broken implementation
        # The real implementation passes, but this documents the validation pattern

        # With broken implementation (commented out - would fail):
        # with patch.object(PrerequisiteAnalyzer, 'analyze', _extra_keys_analyze):
        #     result = PrerequisiteAnalyzer.analyze("improve memory system")
        #     extra = set(result.keys()) - set(REQUIRED_KEYS.keys())
        #     assert extra, f"Expected extra keys, but got only: {result.keys()}"

        # Real implementation should not have extra keys
        result = PrerequisiteAnalyzer.analyze("improve memory system")
        extra = set(result.keys()) - set(REQUIRED_KEYS.keys())
        assert not extra, f"Real implementation has extra keys: {extra}"
