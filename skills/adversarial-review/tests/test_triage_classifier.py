#!/usr/bin/env python3
"""
Unit tests for triage_classifier.py.

These tests verify that the triage classifier correctly:
1. Queries CKS semantic search for learned triage patterns
2. Returns learned triage if similarity > 0.85
3. Falls back to heuristic rules when no match found
4. Handles edge cases and errors gracefully

Test Categories:
- Semantic Search Integration: CKS queries with similarity threshold
- Heuristic Fallback: Rule-based classification when no learned pattern
- Edge Cases: Empty results, errors, missing fields
- ReDoS Protection: Input validation and timeout handling

All tests should FAIL initially (RED phase) - triage_classifier.py not implemented yet.

Run with: pytest P:/.claude/skills/adversarial-review/tests/test_triage_classifier.py -v
"""

import sys
from pathlib import Path

# Add lib directory to path
lib_dir = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_dir))


def test_classify_finding_function_exists():
    """
    Test that classify_finding() function is defined.

    Given: triage_classifier.py module
    When: Importing and checking for classify_finding function
    Then: Should exist and be callable
    """
    from triage_classifier import classify_finding

    assert callable(classify_finding), "classify_finding should be a callable function"


def test_classify_finding_uses_semantic_search():
    """
    Test that classify_finding() queries CKS semantic search.

    Given: classify_finding() and a finding dict
    When: Classifying a finding
    Then: Should query CKS semantic search with appropriate query
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "SEC-001: Missing input validation",
        "description": "Function lacks input validation leading to potential injection",
        "severity": "HIGH"
    }

    # Mock DaemonClient.search()
    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 0,
            "results": []
        }

        classify_finding(finding)

        # Verify search was called with "cks" backend
        mock_client.search.assert_called_once()
        call_args = mock_client.search.call_args
        assert call_args[0][0] == "cks", "Should use 'cks' backend"


def test_classify_finding_returns_learned_triage_when_similarity_high():
    """
    Test that classify_finding() returns learned triage when similarity > 0.85.

    Given: classify_finding() and CKS has high-similarity match (0.90)
    When: Classifying a finding
    Then: Should return the learned triage from CKS
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "SEC-001: Missing input validation",
        "description": "Function lacks input validation leading to potential injection",
        "severity": "HIGH"
    }

    # Mock DaemonClient.search() with high similarity result
    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 1,
            "results": [
                {
                    "text": "SEC-001 nit - fix_before_merge - User corrected",
                    "similarity": 0.90,  # Above threshold
                    "metadata": {"corrected_triage": "nit"}
                }
            ]
        }

        result = classify_finding(finding)

        assert result == "nit", "Should return learned triage when similarity > 0.85"


def test_classify_finding_ignores_low_similarity_results():
    """
    Test that classify_finding() ignores results with similarity < 0.85.

    Given: classify_finding() and CKS has low-similarity match (0.70)
    When: Classifying a finding
    Then: Should fall back to heuristic rules instead of using low-similarity result
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "SEC-002: SQL injection vulnerability",
        "description": "User input concatenated into SQL query",
        "severity": "HIGH"
    }

    # Mock DaemonClient.search() with low similarity result
    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 1,
            "results": [
                {
                    "text": "SEC-002 fix_before_merge - nit - User corrected",
                    "similarity": 0.70,  # Below threshold
                    "metadata": {"corrected_triage": "fix_before_merge"}
                }
            ]
        }

        result = classify_finding(finding)

        # Should NOT return the low-similarity result
        assert result != "fix_before_merge", "Should ignore results with similarity < 0.85"
        # Should return heuristic-based classification
        assert result in ["nit", "fix_before_merge", "pre-existing"], "Should return valid triage from heuristic"


def test_classify_finding_falls_back_to_heuristics_when_no_results():
    """
    Test that classify_finding() falls back to heuristic rules when CKS has no results.

    Given: classify_finding() and CKS returns empty results
    When: Classifying a finding
    Then: Should apply heuristic rules and return valid triage
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "BUG-001: Off-by-one error in loop",
        "description": "Loop condition should be i < n not i <= n",
        "severity": "MEDIUM"
    }

    # Mock DaemonClient.search() with no results
    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 0,
            "results": []
        }

        result = classify_finding(finding)

        assert result in ["nit", "fix_before_merge", "pre-existing"], "Should return valid triage from heuristic"


def test_classify_finding_handles_cks_error_gracefully():
    """
    Test that classify_finding() handles CKS errors gracefully.

    Given: classify_finding() and CKS search throws an exception
    When: Classifying a finding
    Then: Should fall back to heuristic rules without crashing
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "QUAL-001: Inconsistent naming",
        "description": "Variable name doesn't follow conventions",
        "severity": "LOW"
    }

    # Mock DaemonClient to raise exception
    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.side_effect = Exception("CKS daemon not responding")

        result = classify_finding(finding)

        # Should not crash, should fall back to heuristic
        assert result in ["nit", "fix_before_merge", "pre-existing"], "Should return valid triage despite CKS error"


def test_heuristic_rules_classify_high_severity_as_fix_before_merge():
    """
    Test that heuristic rules classify HIGH severity as fix_before_merge.

    Given: classify_finding() and no CKS results
    When: Classifying a HIGH severity finding
    Then: Heuristic rules should return "fix_before_merge"
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "SEC-001: Critical security vulnerability",
        "description": "Remote code execution vulnerability",
        "severity": "HIGH"
    }

    # Mock DaemonClient.search() with no results
    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 0,
            "results": []
        }

        result = classify_finding(finding)

        assert result == "fix_before_merge", "HIGH severity should be classified as fix_before_merge"


def test_heuristic_rules_classify_low_severity_as_nit():
    """
    Test that heuristic rules classify LOW severity as nit.

    Given: classify_finding() and no CKS results
    When: Classifying a LOW severity finding
    Then: Heuristic rules should return "nit"
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "STYLE-001: Missing whitespace",
        "description": "Missing space after comma in function call",
        "severity": "LOW"
    }

    # Mock DaemonClient.search() with no results
    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 0,
            "results": []
        }

        result = classify_finding(finding)

        assert result == "nit", "LOW severity should be classified as nit"


def test_heuristic_rules_classify_medium_severity_context_dependent():
    """
    Test that heuristic rules handle MEDIUM severity based on context.

    Given: classify_finding() and no CKS results
    When: Classifying a MEDIUM severity finding
    Then: Heuristic rules should use context keywords to determine triage
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    # Test case 1: MEDIUM with security keyword
    finding_security = {
        "title": "SEC-002: Potential XSS",
        "description": "Output not properly escaped",
        "severity": "MEDIUM"
    }

    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 0,
            "results": []
        }

        result = classify_finding(finding_security)
        assert result in ["nit", "fix_before_merge", "pre-existing"], "Should return valid triage"


def test_classify_finding_constructs_appropriate_query():
    """
    Test that classify_finding() constructs appropriate search query from finding.

    Given: classify_finding() and a finding dict
    When: Constructing search query
    Then: Should combine title and description for semantic search
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    finding = {
        "title": "SEC-001: Missing validation",
        "description": "Function doesn't validate user input"
    }

    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 0,
            "results": []
        }

        classify_finding(finding)

        # Verify search query includes finding information
        call_args = mock_client.search.call_args
        query = call_args[0][1]  # Second argument is the query

        # Query should contain meaningful information from finding
        assert len(query) > 0, "Query should not be empty"
        assert "validation" in query.lower() or "sec" in query.lower(), "Query should include finding details"


def test_classify_finding_handles_missing_finding_fields():
    """
    Test that classify_finding() handles missing fields in finding dict.

    Given: classify_finding() and finding with missing fields
    When: Classifying with incomplete data
    Then: Should not crash, should fall back to heuristic
    """
    from triage_classifier import classify_finding
    from unittest.mock import patch, MagicMock

    # Test with minimal finding data
    finding = {"title": "SEC-001: Something wrong"}

    with patch("triage_classifier.DaemonClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "status": "success",
            "count": 0,
            "results": []
        }

        result = classify_finding(finding)

        assert result in ["nit", "fix_before_merge", "pre-existing"], "Should handle missing fields gracefully"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
