#!/usr/bin/env python3
"""
Comprehensive tests for Phase 3: CKS Pattern Auto-Learning.

Tests:
1. Pattern extraction from mechanism-only searches
2. Symptom type classification
3. CKS storage and retrieval
4. Full auto-learning workflow
5. Confidence scoring
6. Context-aware suggestions

Run: python -m pytest tests/test_phase3_auto_learning.py -v
"""

import sys
import tempfile
from pathlib import Path

# Add hooks directory to path
hooks_dir = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(hooks_dir))

from cks_integration import (
    format_patterns_for_workflow,
    get_functional_suggestions_for_mechanism,
    query_rca_patterns,
    store_rca_pattern,
)
from pattern_extractor import (
    calculate_confidence,
    classify_symptom_type,
    extract_learning_from_mechanism_search,
    format_learning_for_cks,
    suggest_functional_pattern,
)


def test_classify_performance_symptoms():
    """Test symptom type classification for PERFORMANCE issues."""
    searches = [
        {"pattern": "Progress(", "type": "mechanism"},
        {"pattern": "update(", "type": "mechanism"},
        {"pattern": "% complete", "type": "mechanism"},
    ]

    symptom = classify_symptom_type(searches)
    assert symptom == "PERFORMANCE", f"Expected PERFORMANCE, got {symptom}"
    print("✓ Progress-related searches → PERFORMANCE")


def test_classify_error_symptoms():
    """Test symptom type classification for ERROR issues."""
    searches = [
        {"pattern": "Exception", "type": "mechanism"},
        {"pattern": "raise ValueError", "type": "mechanism"},
        {"pattern": "Traceback", "type": "mechanism"},
    ]

    symptom = classify_symptom_type(searches)
    assert symptom == "ERROR", f"Expected ERROR, got {symptom}"
    print("✓ Exception-related searches → ERROR")


def test_classify_integration_symptoms():
    """Test symptom type classification for INTEGRATION issues."""
    searches = [
        {"pattern": "API", "type": "mechanism"},
        {"pattern": "http://endpoint", "type": "mechanism"},
        {"pattern": "requests.post", "type": "mechanism"},
    ]

    symptom = classify_symptom_type(searches)
    assert symptom == "INTEGRATION", f"Expected INTEGRATION, got {symptom}"
    print("✓ API-related searches → INTEGRATION")


def test_suggest_functional_for_performance():
    """Test functional pattern suggestion for PERFORMANCE."""
    mechanism_patterns = ["Progress(", "class Progress", "def update_progress"]
    symptom_type = "PERFORMANCE"

    functional = suggest_functional_pattern(symptom_type, mechanism_patterns)
    assert functional in ["yt-api:", "status:", "percent:", "console.log"]
    print(f"✓ PERFORMANCE → suggests '{functional}'")


def test_suggest_functional_for_error():
    """Test functional pattern suggestion for ERROR."""
    mechanism_patterns = ["Exception", "raise ValueError", "try:"]
    symptom_type = "ERROR"

    functional = suggest_functional_pattern(symptom_type, mechanism_patterns)
    assert functional in ["error:", "exception:", "fail:", "traceback"]
    print(f"✓ ERROR → suggests '{functional}'")


def test_suggest_functional_context_aware():
    """Test context-aware functional suggestions."""
    # Progress context → yt-api
    assert suggest_functional_pattern("PERFORMANCE", ["Progress("]) == "yt-api:"

    # Exception context → error
    assert suggest_functional_pattern("ERROR", ["Exception"]) == "error:"

    # API context → response
    assert suggest_functional_pattern("INTEGRATION", ["API"]) == "response:"

    print("✓ Context-aware suggestions work correctly")


def test_confidence_calculation():
    """Test confidence score calculation."""
    # More mechanism searches = higher confidence
    conf_2 = calculate_confidence(2, "PERFORMANCE")
    conf_5 = calculate_confidence(5, "PERFORMANCE")

    assert 0.0 <= conf_2 <= 1.0, f"Confidence out of range: {conf_2}"
    assert 0.0 <= conf_5 <= 1.0, f"Confidence out of range: {conf_5}"
    assert conf_5 > conf_2, "More searches should increase confidence"

    print(f"✓ Confidence: 2 searches = {conf_2}, 5 searches = {conf_5}")


def test_extract_learning_from_mechanism_search():
    """Test pattern extraction from mechanism-only searches."""
    state = {
        "searches": [
            {"pattern": "Progress(", "type": "mechanism", "timestamp": "2026-02-28T10:00:00"},
            {"pattern": "class Progress", "type": "mechanism", "timestamp": "2026-02-28T10:01:00"},
            {"pattern": "def update", "type": "mechanism", "timestamp": "2026-02-28T10:02:00"},
        ]
    }

    learning = extract_learning_from_mechanism_search(state)

    assert learning, "Should extract learning"
    assert learning["symptom_type"] in [
        "PERFORMANCE",
        "ERROR",
        "INTEGRATION",
        "INTERMITTENT",
        "SECURITY",
    ]
    assert "mechanism_patterns" in learning
    assert "functional_suggestion" in learning
    assert "relationship" in learning
    assert learning["confidence"] >= 0.3  # Should have some confidence

    print(f"✓ Extracted learning: {learning['symptom_type']} → {learning['functional_suggestion']}")


def test_extract_learning_requires_minimum_searches():
    """Test that extraction requires minimum 2 mechanism searches."""
    state = {
        "searches": [
            {"pattern": "Progress(", "type": "mechanism", "timestamp": "2026-02-28T10:00:00"},
        ]
    }

    learning = extract_learning_from_mechanism_search(state)

    assert not learning, "Should not extract with < 2 searches"
    print("✓ Requires minimum 2 mechanism searches")


def test_format_learning_for_cks():
    """Test CKS formatting of learning entries."""
    learning = {
        "type": "rca_search_pattern",
        "symptom_type": "PERFORMANCE",
        "mechanism_patterns": ["Progress(", "class Progress"],
        "functional_suggestion": "yt-api:",
        "confidence": 0.8,
        "created_at": "2026-02-28T10:00:00",
        "relationship": "Test relationship",
    }

    formatted = format_learning_for_cks(learning)

    assert "# RCA Search Pattern: PERFORMANCE" in formatted
    assert "**Confidence:** 0.8" in formatted
    assert "yt-api:" in formatted
    assert "Test relationship" in formatted

    print("✓ CKS formatting produces structured markdown")


def test_cks_storage_and_retrieval():
    """Test full CKS storage and retrieval cycle."""
    # Use temporary directory for isolated test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override RCA_PATTERNS_DIR to use temp directory
        import cks_integration

        original_dir = cks_integration.RCA_PATTERNS_DIR
        cks_integration.RCA_PATTERNS_DIR = Path(tmpdir)

        try:
            # Test storage
            learning = {
                "type": "rca_search_pattern",
                "symptom_type": "PERFORMANCE",
                "mechanism_patterns": ["TestPattern("],
                "functional_suggestion": "test-functional:",
                "relationship": "Test relationship",
                "confidence": 0.7,
                "created_at": "2026-02-28T10:00:00",
                "times_helpful": 0,
            }

            stored = store_rca_pattern(learning)
            assert stored, "Should store pattern successfully"

            # Test retrieval
            patterns = query_rca_patterns("PERFORMANCE")
            assert len(patterns) > 0, "Should retrieve stored pattern"

            retrieved = patterns[0]
            assert retrieved["symptom_type"] == "PERFORMANCE"
            assert retrieved["functional_suggestion"] == "test-functional:"

            print("✓ CKS storage and retrieval cycle works")

        finally:
            # Restore original directory
            cks_integration.RCA_PATTERNS_DIR = original_dir


def test_query_filters_by_symptom_type():
    """Test that CKS query filters by symptom type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import cks_integration

        original_dir = cks_integration.RCA_PATTERNS_DIR
        cks_integration.RCA_PATTERNS_DIR = Path(tmpdir)

        try:
            # Store PERFORMANCE pattern
            learning1 = {
                "type": "rca_search_pattern",
                "symptom_type": "PERFORMANCE",
                "mechanism_patterns": ["Progress("],
                "functional_suggestion": "yt-api:",
                "relationship": "Test",
                "confidence": 0.8,
                "created_at": "2026-02-28T10:00:00",
                "times_helpful": 0,
            }
            store_rca_pattern(learning1)

            # Store ERROR pattern
            learning2 = {
                "type": "rca_search_pattern",
                "symptom_type": "ERROR",
                "mechanism_patterns": ["Exception"],
                "functional_suggestion": "error:",
                "relationship": "Test",
                "confidence": 0.7,
                "created_at": "2026-02-28T10:00:00",
                "times_helpful": 0,
            }
            store_rca_pattern(learning2)

            # Query PERFORMANCE only
            perf_patterns = query_rca_patterns("PERFORMANCE")
            assert all(p["symptom_type"] == "PERFORMANCE" for p in perf_patterns)
            assert len(perf_patterns) >= 1

            # Query ERROR only
            error_patterns = query_rca_patterns("ERROR")
            assert all(p["symptom_type"] == "ERROR" for p in error_patterns)
            assert len(error_patterns) >= 1

            # Query all
            all_patterns = query_rca_patterns()
            assert len(all_patterns) >= 2

            print("✓ CKS query filters correctly by symptom type")

        finally:
            cks_integration.RCA_PATTERNS_DIR = original_dir


def test_low_confidence_not_stored():
    """Test that low confidence patterns are not stored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import cks_integration

        original_dir = cks_integration.RCA_PATTERNS_DIR
        cks_integration.RCA_PATTERNS_DIR = Path(tmpdir)

        try:
            learning = {
                "type": "rca_search_pattern",
                "symptom_type": "PERFORMANCE",
                "mechanism_patterns": ["Test("],
                "functional_suggestion": "test:",
                "relationship": "Test",
                "confidence": 0.3,  # Below threshold
                "created_at": "2026-02-28T10:00:00",
                "times_helpful": 0,
            }

            stored = store_rca_pattern(learning)
            assert not stored, "Should not store low-confidence pattern"

            patterns = query_rca_patterns()
            assert len(patterns) == 0, "Should have no patterns"

            print("✓ Low confidence patterns not stored")

        finally:
            cks_integration.RCA_PATTERNS_DIR = original_dir


def test_get_functional_suggestions():
    """Test getting functional suggestions based on mechanism pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import cks_integration

        original_dir = cks_integration.RCA_PATTERNS_DIR
        cks_integration.RCA_PATTERNS_DIR = Path(tmpdir)

        try:
            # Store a pattern: Progress( → yt-api:
            learning = {
                "type": "rca_search_pattern",
                "symptom_type": "PERFORMANCE",
                "mechanism_patterns": ["Progress(", "update("],
                "functional_suggestion": "yt-api:",
                "relationship": "Test",
                "confidence": 0.8,
                "created_at": "2026-02-28T10:00:00",
                "times_helpful": 0,
            }
            store_rca_pattern(learning)

            # Query for suggestions based on mechanism pattern
            suggestions = get_functional_suggestions_for_mechanism("Progress(")

            assert "yt-api:" in suggestions, "Should suggest yt-api: for Progress("

            print(f"✓ Functional suggestions for 'Progress(': {suggestions}")

        finally:
            cks_integration.RCA_PATTERNS_DIR = original_dir


def test_format_patterns_for_workflow():
    """Test formatting patterns for workflow display."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import cks_integration

        original_dir = cks_integration.RCA_PATTERNS_DIR
        cks_integration.RCA_PATTERNS_DIR = Path(tmpdir)

        try:
            # Store test pattern
            learning = {
                "type": "rca_search_pattern",
                "symptom_type": "PERFORMANCE",
                "mechanism_patterns": ["Progress("],
                "functional_suggestion": "yt-api:",
                "relationship": "Test",
                "confidence": 0.8,
                "created_at": "2026-02-28T10:00:00",
                "times_helpful": 0,
            }
            store_rca_pattern(learning)

            # Format for workflow
            formatted = format_patterns_for_workflow("PERFORMANCE")

            assert "Learned Search Patterns from CKS" in formatted
            assert "PERFORMANCE (confidence: 0.8)" in formatted
            assert "Progress(" in formatted
            assert "yt-api:" in formatted

            print("✓ Workflow formatting displays patterns clearly")

        finally:
            cks_integration.RCA_PATTERNS_DIR = original_dir


def test_full_auto_learning_workflow():
    """Test complete auto-learning workflow end-to-end."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import cks_integration

        original_dir = cks_integration.RCA_PATTERNS_DIR
        cks_integration.RCA_PATTERNS_DIR = Path(tmpdir)

        try:
            # Simulate mechanism-only search sequence
            state = {
                "searches": [
                    {"pattern": "Progress(", "type": "mechanism"},
                    {"pattern": "class Progress", "type": "mechanism"},
                    {"pattern": "def update_progress", "type": "mechanism"},
                ]
            }

            # Extract learning
            learning = extract_learning_from_mechanism_search(state)
            assert learning, "Should extract learning"

            # Store in CKS
            stored = store_rca_pattern(learning)
            assert stored, "Should store successfully"

            # Retrieve from CKS
            patterns = query_rca_patterns(learning["symptom_type"])
            assert len(patterns) > 0, "Should retrieve stored pattern"

            # Verify round-trip
            retrieved = patterns[0]
            assert retrieved["symptom_type"] == learning["symptom_type"]
            assert retrieved["functional_suggestion"] == learning["functional_suggestion"]

            print("✓ Full auto-learning workflow: extract → store → retrieve")
            print(f"  Symptom: {retrieved['symptom_type']}")
            print(f"  Functional: {retrieved['functional_suggestion']}")

        finally:
            cks_integration.RCA_PATTERNS_DIR = original_dir


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Phase 3: CKS Pattern Auto-Learning")
    print("=" * 70)

    test_classify_performance_symptoms()
    test_classify_error_symptoms()
    test_classify_integration_symptoms()
    test_suggest_functional_for_performance()
    test_suggest_functional_for_error()
    test_suggest_functional_context_aware()
    test_confidence_calculation()
    test_extract_learning_from_mechanism_search()
    test_extract_learning_requires_minimum_searches()
    test_format_learning_for_cks()
    test_cks_storage_and_retrieval()
    test_query_filters_by_symptom_type()
    test_low_confidence_not_stored()
    test_get_functional_suggestions()
    test_format_patterns_for_workflow()
    test_full_auto_learning_workflow()

    print("=" * 70)
    print("✅ All Phase 3 tests passed!")
    print("=" * 70)
