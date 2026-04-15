"""Tests for hypothesis_generator module - NEW Evidence-Based Features.

These tests verify NEW functionality for generating hypotheses from EVIDENCE
(not just error types/messages). This is NEW behavior that doesn't exist yet.

TDD Cycle: RED Phase - Tests MUST fail before implementation.

Run with: pytest P:/packages/rca/skill/tests/test_hypothesis_generator.py -v
"""

import sys
from pathlib import Path

# Add package src to path for imports
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca.hypothesis_generator import (
    Hypothesis,
    HypothesisCategory,
    HypothesisSet,
)


class TestHypothesisGenerationNoEvidence:
    """Tests for hypothesis generation with no evidence."""

    def test_hypothesis_generation_no_evidence_returns_empty_hypotheses(self):
        """Test that generating hypotheses with no evidence returns empty list.

        Given: No evidence is provided
        When: generate_hypotheses_from_evidence is called with empty evidence
        Then: Should return HypothesisSet with empty hypotheses list
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        result = generate_hypotheses_from_evidence(evidence=[])

        assert isinstance(result, HypothesisSet)
        assert len(result.hypotheses) == 0
        assert result.null_hypothesis is not None

    def test_hypothesis_generation_no_evidence_includes_null_hypothesis(self):
        """Test that null hypothesis is generated even with no evidence.

        Given: No evidence is provided
        When: generate_hypotheses_from_evidence is called with empty evidence
        Then: Should still include null hypothesis
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        result = generate_hypotheses_from_evidence(evidence=[])

        assert result.null_hypothesis is not None
        assert result.null_hypothesis.description == "Error originates outside codebase"
        assert result.null_hypothesis.target_location == "external"


class TestHypothesisGenerationSingleEvidence:
    """Tests for hypothesis generation with single evidence item."""

    def test_hypothesis_generation_single_evidence_generates_one_hypothesis(self):
        """Test that single evidence generates one hypothesis.

        Given: One piece of evidence is provided
        When: generate_hypotheses_from_evidence is called
        Then: Should return HypothesisSet with one hypothesis
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        evidence = [
            {
                "type": "stack_trace",
                "message": "AttributeError: 'NoneType' object has no attribute 'x'",
                "file": "handler.py",
                "line": 42,
            }
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)

        assert isinstance(result, HypothesisSet)
        assert len(result.hypotheses) >= 1

    def test_hypothesis_generation_single_evidence_sets_correct_category(self):
        """Test that single evidence generates hypothesis with correct category.

        Given: Evidence contains AttributeError in stack trace
        When: generate_hypotheses_from_evidence is called
        Then: Generated hypothesis should have NULL_DEREFERENCE category
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        evidence = [
            {
                "type": "stack_trace",
                "message": "AttributeError: 'NoneType' object has no attribute 'data'",
                "file": "processor.py",
                "line": 15,
            }
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)

        categories = [h.category for h in result.hypotheses]
        assert HypothesisCategory.NULL_DEREFERENCE in categories

    def test_hypothesis_generation_single_evidence_includes_supporting_evidence(self):
        """Test that generated hypothesis links to supporting evidence.

        Given: One piece of evidence is provided
        When: generate_hypotheses_from_evidence is called
        Then: Generated hypothesis should include evidence in supporting_evidence list
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        evidence = [
            {
                "type": "log_entry",
                "message": "Variable user_id is None",
                "file": "auth.py",
                "line": 23,
            }
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)

        # At least one hypothesis should reference the evidence
        assert any(len(h.supporting_evidence) > 0 for h in result.hypotheses)


class TestHypothesisGenerationMultipleEvidence:
    """Tests for hypothesis generation with multiple evidence items."""

    def test_hypothesis_generation_multiple_evidence_generates_competing_hypotheses(self):
        """Test that multiple evidence generates multiple competing hypotheses.

        Given: Multiple pieces of conflicting evidence are provided
        When: generate_hypotheses_from_evidence is called
        Then: Should return HypothesisSet with multiple hypotheses
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        evidence = [
            {
                "type": "stack_trace",
                "message": "AttributeError: 'NoneType' object has no attribute 'x'",
                "file": "handler.py",
                "line": 42,
            },
            {
                "type": "log_entry",
                "message": "Variable initialized with default value",
                "file": "handler.py",
                "line": 10,
            },
            {
                "type": "log_entry",
                "message": "Type checking passed earlier in execution",
                "file": "handler.py",
                "line": 30,
            },
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)

        assert len(result.hypotheses) >= 2

    def test_hypothesis_generation_multiple_evidence_ranks_by_priority(self):
        """Test that multiple hypotheses are ranked by priority weight.

        Given: Multiple hypotheses are generated from evidence
        When: HypothesisSet.rank_by_priority is called
        Then: Should return hypotheses sorted by priority_weight (descending)
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        evidence = [
            {
                "type": "stack_trace",
                "message": "IndexError: list index out of range",
                "file": "loop.py",
                "line": 55,
            },
            {"type": "log_entry", "message": "List length is 0", "file": "loop.py", "line": 50},
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)
        ranked = result.rank_by_priority()

        # Verify descending order
        for i in range(len(ranked) - 1):
            assert ranked[i].priority_weight >= ranked[i + 1].priority_weight

    def test_hypothesis_generation_multiple_evidence_groups_by_target_location(self):
        """Test that hypotheses are grouped by target location.

        Given: Evidence from multiple files
        When: generate_hypotheses_from_evidence is called
        Then: Should generate hypotheses with appropriate target locations
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        evidence = [
            {
                "type": "stack_trace",
                "message": "Error in module_a",
                "file": "module_a.py",
                "line": 10,
            },
            {
                "type": "stack_trace",
                "message": "Error in module_b",
                "file": "module_b.py",
                "line": 20,
            },
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)

        target_locations = [h.target_location for h in result.hypotheses]
        assert "module_a.py" in target_locations
        assert "module_b.py" in target_locations


class TestHypothesisConfidenceCalculation:
    """Tests for hypothesis confidence calculation based on evidence."""

    def test_hypothesis_confidence_calculation_with_supporting_evidence(self):
        """Test that supporting evidence increases hypothesis confidence.

        Given: A hypothesis with multiple supporting evidence items
        When: calculate_hypothesis_confidence is called
        Then: Should return confidence score > 0.5
        """
        from rca.hypothesis_generator import calculate_hypothesis_confidence

        hypothesis = Hypothesis(
            category=HypothesisCategory.NULL_DEREFERENCE,
            description="Object is None",
            target_location="handler.py",
            priority_weight=0.9,
            falsification_test="Add logging",
            supporting_evidence=[
                "AttributeError: 'NoneType' object",
                "Variable not initialized in constructor",
                "Similar pattern in other modules",
            ],
            contradicting_evidence=[],
        )

        confidence = calculate_hypothesis_confidence(hypothesis)

        assert confidence > 0.5
        assert confidence <= 1.0

    def test_hypothesis_confidence_calculation_with_contradicting_evidence(self):
        """Test that contradicting evidence decreases hypothesis confidence.

        Given: A hypothesis with contradicting evidence
        When: calculate_hypothesis_confidence is called
        Then: Should return confidence score < 0.5
        """
        from rca.hypothesis_generator import calculate_hypothesis_confidence

        hypothesis = Hypothesis(
            category=HypothesisCategory.NULL_DEREFERENCE,
            description="Object is None",
            target_location="handler.py",
            priority_weight=0.9,
            falsification_test="Add logging",
            supporting_evidence=["AttributeError: 'NoneType' object"],
            contradicting_evidence=[
                "Variable initialized with value 5 lines earlier",
                "Type check passes before access",
            ],
        )

        confidence = calculate_hypothesis_confidence(hypothesis)

        assert confidence < 0.5
        assert confidence >= 0.0

    def test_hypothesis_confidence_calculation_balanced_evidence(self):
        """Test confidence calculation with balanced supporting/contradicting evidence.

        Given: A hypothesis with equal supporting and contradicting evidence
        When: calculate_hypothesis_confidence is called
        Then: Should return confidence score around 0.5
        """
        from rca.hypothesis_generator import calculate_hypothesis_confidence

        hypothesis = Hypothesis(
            category=HypothesisCategory.TYPE_MISMATCH,
            description="Wrong type",
            target_location="processor.py",
            priority_weight=0.8,
            falsification_test="Check type",
            supporting_evidence=["TypeError occurred", "Variable passed from untyped source"],
            contradicting_evidence=[
                "Type hints suggest correct type",
                "Similar calls work elsewhere",
            ],
        )

        confidence = calculate_hypothesis_confidence(hypothesis)

        # Should be near 0.5 when evidence is balanced
        assert 0.3 <= confidence <= 0.7

    def test_hypothesis_confidence_calculation_no_evidence(self):
        """Test confidence calculation with no evidence.

        Given: A hypothesis with no supporting or contradicting evidence
        When: calculate_hypothesis_confidence is called
        Then: Should return confidence score based only on priority_weight
        """
        from rca.hypothesis_generator import calculate_hypothesis_confidence

        hypothesis = Hypothesis(
            category=HypothesisCategory.OFF_BY_ONE,
            description="Index error",
            target_location="loop.py",
            priority_weight=0.7,
            falsification_test="Check bounds",
            supporting_evidence=[],
            contradicting_evidence=[],
        )

        confidence = calculate_hypothesis_confidence(hypothesis)

        # With no evidence, confidence should equal priority_weight
        assert confidence == 0.7


class TestHypothesisGeneratorIntegration:
    """Integration tests for evidence-based hypothesis generation."""

    def test_full_workflow_evidence_to_hypotheses_with_confidence(self):
        """Test full workflow from evidence to ranked hypotheses with confidence.

        Given: Multiple pieces of evidence from different sources
        When: generate_hypotheses_from_evidence and calculate_hypothesis_confidence are called
        Then: Should produce ranked hypotheses with confidence scores
        """
        from rca.hypothesis_generator import (
            calculate_hypothesis_confidence,
            generate_hypotheses_from_evidence,
        )

        evidence = [
            {
                "type": "stack_trace",
                "message": "KeyError: 'config'",
                "file": "config_loader.py",
                "line": 88,
            },
            {
                "type": "log_entry",
                "message": "Config file loaded successfully",
                "file": "config_loader.py",
                "line": 50,
            },
            {
                "type": "log_entry",
                "message": "Required key 'config' not found in dict",
                "file": "config_loader.py",
                "line": 85,
            },
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)

        assert len(result.hypotheses) >= 1

        # Calculate confidence for each hypothesis
        confidences = []
        for hyp in result.hypotheses:
            conf = calculate_hypothesis_confidence(hyp)
            confidences.append((hyp.description, conf))

        # All confidences should be valid
        for desc, conf in confidences:
            assert 0.0 <= conf <= 1.0

    def test_evidence_with_metadata_generates_targeted_hypotheses(self):
        """Test that evidence metadata (file, line) improves hypothesis targeting.

        Given: Evidence with file and line number metadata
        When: generate_hypotheses_from_evidence is called
        Then: Generated hypotheses should have accurate target_location
        """
        from rca.hypothesis_generator import generate_hypotheses_from_evidence

        evidence = [
            {
                "type": "stack_trace",
                "message": "ValueError: invalid literal",
                "file": "parser.py",
                "line": 123,
            }
        ]

        result = generate_hypotheses_from_evidence(evidence=evidence)

        # At least one hypothesis should target the specific file
        assert any(hyp.target_location == "parser.py" for hyp in result.hypotheses)
