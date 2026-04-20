#!/usr/bin/env python3
"""Unit tests for priority_scorer utility.

These tests verify P0/P1/P2 categorization logic, scoring rules, and confidence scoring.
Run with: pytest tests/test_priority_scorer.py -v
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.priority_scorer import (
    PriorityLevel,
    PriorityScore,
    calculate_priority,
    categorize_finding,
)


class TestP0Categorization:
    """Test P0 (Critical) priority categorization."""

    def test_security_vulnerability_categorized_as_p0(self):
        """
        Test that security vulnerabilities are categorized as P0.

        Given: A finding with type="security" and severity="high"
        When: categorize_finding() is called
        Then: Returns PriorityLevel.P0
        """
        # Arrange
        finding = {
            "type": "security",
            "severity": "high",
            "description": "SQL injection vulnerability"
        }

        # Act
        result = categorize_finding(finding)

        # Assert
        assert result == PriorityLevel.P0


class TestP1Categorization:
    """Test P1 (High) priority categorization."""

    def test_performance_improvement_categorized_as_p1(self):
        """
        Test that major performance improvements are categorized as P1.

        Given: A finding with type="performance" and impact="high"
        When: categorize_finding() is called
        Then: Returns PriorityLevel.P1
        """
        # Arrange
        finding = {
            "type": "performance",
            "impact": "high",
            "description": "Reduce API response time by 50%"
        }

        # Act
        result = categorize_finding(finding)

        # Assert
        assert result == PriorityLevel.P1


class TestP2Categorization:
    """Test P2 (Medium) priority categorization."""

    def test_minor_improvement_categorized_as_p2(self):
        """
        Test that minor improvements are categorized as P2.

        Given: A finding with type="improvement" and impact="low"
        When: categorize_finding() is called
        Then: Returns PriorityLevel.P2
        """
        # Arrange
        finding = {
            "type": "improvement",
            "impact": "low",
            "description": "Improve error message clarity"
        }

        # Act
        result = categorize_finding(finding)

        # Assert
        assert result == PriorityLevel.P2


class TestPriorityScoreCalculation:
    """Test priority score calculation (0.0-1.0 range)."""

    def test_p0_score_high_range(self):
        """
        Test that P0 findings produce scores in high range (0.8-1.0).

        Given: A P0 finding
        When: calculate_priority() is called
        Then: Returns score >= 0.8
        """
        # Arrange
        finding = {
            "type": "security",
            "severity": "high",
            "description": "Critical security vulnerability"
        }

        # Act
        result = calculate_priority(finding)

        # Assert
        assert result.score >= 0.8
        assert result.score <= 1.0


class TestConfidenceScoring:
    """Test confidence scoring based on evidence strength."""

    def test_high_confidence_with_strong_evidence(self):
        """
        Test that strong evidence produces high confidence (0.8-1.0).

        Given: A finding with multiple evidence fields
        When: calculate_priority() is called
        Then: Returns confidence >= 0.8
        """
        # Arrange
        finding = {
            "type": "security",
            "severity": "high",
            "evidence": ["log_entry", "stack_trace", "user_report"],
            "reproducible": True,
            "description": "Well-documented vulnerability"
        }

        # Act
        result = calculate_priority(finding)

        # Assert
        assert result.confidence >= 0.8
        assert result.confidence <= 1.0


class TestEdgeCaseHandling:
    """Test edge case handling for missing fields and unknown types."""

    def test_missing_type_field_defaults_to_p2(self):
        """
        Test that missing 'type' field defaults to P2.

        Given: A finding without 'type' field
        When: categorize_finding() is called
        Then: Returns PriorityLevel.P2
        """
        # Arrange
        finding = {
            "description": "Finding with unknown type"
        }

        # Act
        result = categorize_finding(finding)

        # Assert
        assert result == PriorityLevel.P2

    def test_unknown_type_defaults_to_p2(self):
        """
        Test that unknown 'type' values default to P2.

        Given: A finding with type="unknown_type"
        When: categorize_finding() is called
        Then: Returns PriorityLevel.P2
        """
        # Arrange
        finding = {
            "type": "unknown_type",
            "description": "Finding with unrecognized type"
        }

        # Act
        result = categorize_finding(finding)

        # Assert
        assert result == PriorityLevel.P2


class TestDocumentationRequirements:
    """Test that documentation includes non-blocking disclaimer."""

    def test_module_docstring_exists(self):
        """
        Test that priority_scorer module has documentation.

        Given: The priority_scorer module
        When: Module docstring is accessed
        Then: Docstring exists and mentions priorities are recommendations
        """
        # Arrange & Act
        from utils import priority_scorer
        module_doc = priority_scorer.__doc__

        # Assert
        assert module_doc is not None
        assert len(module_doc.strip()) > 0

    def test_documentation_mentions_non_blocking_nature(self):
        """
        Test that documentation clarifies priorities are non-blocking.

        Given: The priority_scorer module documentation
        When: Docstring is searched for key phrases
        Then: Contains "RECOMMENDATION" or "non-blocking" language
        """
        # Arrange & Act
        from utils import priority_scorer
        module_doc = priority_scorer.__doc__.lower()

        # Assert
        # Check for disclaimer language about priorities being recommendations
        has_recommendation = "recommendation" in module_doc or "recommendations" in module_doc
        has_non_blocking = "non-blocking" in module_doc or "not a block" in module_doc
        has_advisory = "advisory" in module_doc or "guidance" in module_doc

        # At least one disclaimer type should be present
        assert has_recommendation or has_non_blocking or has_advisory,             "Documentation should clarify that priorities are recommendations, not blocks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
