"""Tests for EvidenceSaturationDetector in rca Tier 1.

These tests verify the evidence saturation detection algorithm that uses
semantic similarity and diminishing returns detection to determine when
sufficient evidence has been gathered.

Run with: pytest P:/.claude/skills/debugrca/tests/test_evidence_saturation.py -v
"""

import sys
import warnings
from pathlib import Path
from unittest.mock import MagicMock

# Add package src to path for imports
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)


# Import CKS helper for mocking
def _import_cks():
    """Import CKS module with deprecation warnings suppressed."""
    csf_src = str(Path("P:/__csf/src").resolve())
    if csf_src not in sys.path:
        sys.path.insert(0, csf_src)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        from cks.unified import CKS
    return CKS


# Helper function to import evidence_saturation module
def _import_detector():
    """Import EvidenceSaturationDetector from rca package."""
    from rca.evidence_saturation import EvidenceSaturationDetector as ESD

    return ESD


class TestEvidenceSaturationDetectorInit:
    """Tests for EvidenceSaturationDetector initialization."""

    def test_init_with_threshold(self):
        """Test initialization with custom threshold.

        Given: An EvidenceSaturationDetector is created
        When: Initialized with threshold=0.85
        Then: The threshold should be stored correctly
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.85, query_type="technical")
        assert detector.threshold == 0.85
        assert detector.query_type == "technical"

    def test_init_with_default_threshold(self):
        """Test initialization with default threshold.

        Given: An EvidenceSaturationDetector is created
        When: Initialized without parameters
        Then: Default threshold of 0.75 should be used
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        assert detector.threshold == 0.75
        assert detector.query_type == "default"

    def test_init_with_cks_client(self):
        """Test initialization with CKS client.

        Given: An EvidenceSaturationDetector is created
        When: Initialized with a CKS client
        Then: The client should be stored for semantic search
        """
        EvidenceSaturationDetector = _import_detector()

        mock_cks = MagicMock()
        detector = EvidenceSaturationDetector(
            threshold=0.8, query_type="balanced", cks_client=mock_cks
        )
        assert detector.cks_client == mock_cks

    def test_init_without_cks_client(self):
        """Test initialization without CKS client.

        Given: An EvidenceSaturationDetector is created without CKS
        When: CKS client is not provided
        Then: Should use keyword similarity fallback
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(cks_client=None)
        assert detector.cks_client is None


class TestCheckSaturation:
    """Tests for check_saturation method."""

    def test_check_saturation_empty_evidence(self):
        """Test saturation check with empty evidence lists.

        Given: No existing or new evidence
        When: check_saturation is called
        Then: Should return False (not saturated)
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.85)
        result = detector.check_saturation([], [])
        assert result is False

    def test_check_saturation_with_novel_evidence(self):
        """Test saturation check with novel evidence.

        Given: Existing evidence and new distinct evidence
        When: check_saturation is called with dissimilar content
        Then: Should return False (not saturated)
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.85)
        existing = ["Database connection timeout", "Authentication failed"]
        new = ["Network packet loss detected", "Memory leak in heap"]

        result = detector.check_saturation(existing, new)
        assert result is False

    def test_check_saturation_with_redundant_evidence(self):
        """Test saturation check with redundant evidence.

        Given: Existing evidence and new similar evidence
        When: check_saturation is called with similar content above threshold
        Then: Should return True (saturated)

        Note: Uses test data where all pairs have keyword overlap for Jaccard
        similarity testing. For semantic similarity via CKS, more varied text
        would work with higher thresholds.
        """
        EvidenceSaturationDetector = _import_detector()

        # Use lower threshold for Jaccard (keyword overlap) similarity
        detector = EvidenceSaturationDetector(threshold=0.4)
        existing = ["Database connection timeout"]
        new = ["Database timeout error", "Connection timeout error"]

        result = detector.check_saturation(existing, new)
        # All pairs share keyword overlap above threshold
        assert result is True

    def test_check_saturation_below_threshold(self):
        """Test saturation check with similarity below threshold.

        Given: Existing evidence and new somewhat similar evidence
        When: Similarity is below the threshold
        Then: Should return False (not saturated)
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.95)
        existing = ["Database connection timeout"]
        new = ["Connection pool exhausted"]

        result = detector.check_saturation(existing, new)
        assert result is False


class TestDetectDiminishingReturns:
    """Tests for detect_diminishing_returns method."""

    def test_diminishing_returns_with_stable_evidence(self):
        """Test diminishing returns detection with stable evidence.

        Given: Evidence history with low similarity items
        When: detect_diminishing_returns is called
        Then: Should return False (no diminishing returns)
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.85)
        history = [
            "Database connection timeout",
            "Authentication module failure",
            "Network packet loss",
            "Memory heap overflow",
            "CPU spike in worker process",
        ]

        result = detector.detect_diminishing_returns(history)
        assert result is False

    def test_diminishing_returns_with_repetitive_evidence(self):
        """Test diminishing returns detection with repetitive evidence.

        Given: Evidence history with 3+ consecutive similar items
        When: detect_diminishing_returns is called
        Then: Should return True (diminishing returns detected)

        Note: Uses test data with identical words to ensure Jaccard similarity
        exceeds the threshold for 3 consecutive items.
        """
        EvidenceSaturationDetector = _import_detector()

        # Use lower threshold for Jaccard (keyword overlap) similarity
        detector = EvidenceSaturationDetector(threshold=0.5)
        history = [
            "database timeout error",
            "database timeout error",
            "database timeout error",
            "unrelated item",
        ]

        result = detector.detect_diminishing_returns(history)
        # First 3 items are identical, so similarity = 1.0 >= 0.5
        assert result is True

    def test_diminishing_returns_short_history(self):
        """Test diminishing returns with insufficient history.

        Given: Evidence history with less than 3 items
        When: detect_diminishing_returns is called
        Then: Should return False (insufficient data)
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.85)
        history = ["Database timeout", "Connection error"]

        result = detector.detect_diminishing_returns(history)
        assert result is False

    def test_diminishing_returns_empty_history(self):
        """Test diminishing returns with empty history.

        Given: Empty evidence history
        When: detect_diminishing_returns is called
        Then: Should return False
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.85)
        result = detector.detect_diminishing_returns([])
        assert result is False


class TestGetSimilarityScore:
    """Tests for get_similarity_score method."""

    def test_similarity_score_identical_texts(self):
        """Test similarity score with identical texts.

        Given: Two identical text strings
        When: get_similarity_score is called
        Then: Should return 1.0 (perfect similarity)
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        score = detector.get_similarity_score(
            "Database connection timeout", "Database connection timeout"
        )
        assert score == 1.0

    def test_similarity_score_completely_different_texts(self):
        """Test similarity score with completely different texts.

        Given: Two completely different text strings
        When: get_similarity_score is called
        Then: Should return a low similarity score
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        score = detector.get_similarity_score(
            "Database connection timeout", "User preference settings panel"
        )
        assert score < 0.3

    def test_similarity_score_similar_texts(self):
        """Test similarity score with similar texts.

        Given: Two semantically similar text strings
        When: get_similarity_score is called
        Then: Should return a high similarity score

        Note: With Jaccard similarity, keyword overlap determines the score.
        These texts share 'database' and 'timeout' out of unique words.
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        score = detector.get_similarity_score(
            "Database connection timeout", "Database timeout error"
        )
        # Jaccard: intersection{database, timeout} / union{database, connection, timeout, error} = 2/4 = 0.5
        assert score >= 0.5

    def test_similarity_score_with_cks(self):
        """Test similarity score using CKS semantic search.

        Given: A detector with CKS client available
        When: get_similarity_score is called
        Then: Should use CKS semantic search for similarity
        """
        EvidenceSaturationDetector = _import_detector()

        mock_cks = MagicMock()
        mock_cks.search_semantic.return_value = [
            {"content": "Database connection timeout", "score": 0.95}
        ]

        detector = EvidenceSaturationDetector(cks_client=mock_cks)
        score = detector.get_similarity_score(
            "Database connection timeout", "Database timeout error"
        )
        # CKS should be called for semantic search
        mock_cks.search_semantic.assert_called_once()
        assert score > 0.0

    def test_similarity_score_fallback_to_jaccard(self):
        """Test similarity score fallback to Jaccard index.

        Given: A detector without CKS client
        When: get_similarity_score is called
        Then: Should use Jaccard index for keyword similarity
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(cks_client=None)
        score = detector.get_similarity_score(
            "database timeout error", "database connection timeout"
        )
        # Should calculate using keyword overlap
        assert 0.0 <= score <= 1.0
        # These texts share "database" and "timeout"
        assert score > 0.0


class TestJaccardSimilarity:
    """Tests for Jaccard similarity fallback calculation."""

    def test_jaccard_no_overlap(self):
        """Test Jaccard similarity with no word overlap.

        Given: Two texts with no common words
        When: Jaccard similarity is calculated
        Then: Should return 0.0
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(cks_client=None)
        score = detector.get_similarity_score("database timeout", "user interface settings")
        assert score == 0.0

    def test_jaccard_partial_overlap(self):
        """Test Jaccard similarity with partial word overlap.

        Given: Two texts with some common words
        When: Jaccard similarity is calculated
        Then: Should return a value between 0 and 1
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(cks_client=None)
        score = detector.get_similarity_score(
            "database connection timeout error", "database timeout"
        )
        # Jaccard: intersection / union
        # intersection: {database, timeout} = 2
        # union: {database, connection, timeout, error} = 4
        # expected: 0.5
        assert 0.4 <= score <= 0.6

    def test_jaccard_complete_overlap(self):
        """Test Jaccard similarity with complete word overlap.

        Given: Two texts with identical words (same set)
        When: Jaccard similarity is calculated
        Then: Should return 1.0
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(cks_client=None)
        score = detector.get_similarity_score("timeout error", "error timeout")
        assert score == 1.0


class TestSlidingWindowDetection:
    """Tests for sliding window detection of diminishing returns."""

    def test_sliding_window_detection_exact(self):
        """Test sliding window finds 3 consecutive similar items.

        Given: Evidence history with exactly 3 similar consecutive items
        When: detect_diminishing_returns is called
        Then: Should detect diminishing returns

        Note: Uses test data with shared keywords for Jaccard similarity.
        """
        EvidenceSaturationDetector = _import_detector()

        # Use lower threshold for keyword overlap similarity
        detector = EvidenceSaturationDetector(threshold=0.5)
        history = [
            "item error code",
            "item error message",
            "item code error",
            "completely different thing",
        ]

        result = detector.detect_diminishing_returns(history)
        # First 3 items all share 'item' and 'error' keywords
        assert result is True

    def test_sliding_window_detection_interleaved(self):
        """Test sliding window with interleaved similar items.

        Given: Evidence history with interleaved similar/dissimilar items
        When: detect_diminishing_returns is called
        Then: Should NOT detect diminishing returns
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(threshold=0.8)
        history = ["Item A", "Very similar to A", "Completely different B", "Very similar to A"]

        result = detector.detect_diminishing_returns(history)
        assert result is False


class TestIntegrationWithConfig:
    """Tests for integration with config module."""

    def test_threshold_from_config(self):
        """Test that threshold can be loaded from config.

        Given: Configuration has a saturation threshold set
        When: Detector is initialized with query_type
        Then: Should use the configured threshold
        """
        EvidenceSaturationDetector = _import_detector()
        # Import config from rca package
        from rca.config import get_saturation_threshold  # noqa: F401

        # Get the config threshold
        expected_threshold = get_saturation_threshold("technical")

        detector = EvidenceSaturationDetector(threshold=expected_threshold, query_type="technical")
        assert detector.threshold == expected_threshold

    def test_local_fallback_mode(self):
        """Test detector works in local fallback mode.

        Given: CKS is unavailable (local-only mode)
        When: Detector is initialized without CKS client
        Then: Should use keyword similarity without errors
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector(cks_client=None)

        # Should not raise errors
        score = detector.get_similarity_score("test one", "test two")
        assert 0.0 <= score <= 1.0

        saturated = detector.check_saturation(["evidence 1"], ["evidence 2"])
        assert isinstance(saturated, bool)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_string_evidence(self):
        """Test handling of empty string evidence.

        Given: Evidence list contains empty strings
        When: check_saturation is called
        Then: Should handle gracefully without errors
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        result = detector.check_saturation([""], ["test"])
        assert isinstance(result, bool)

    def test_single_word_evidence(self):
        """Test handling of single word evidence.

        Given: Evidence with single word
        When: similarity is calculated
        Then: Should handle without errors
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        score = detector.get_similarity_score("timeout", "timeout")
        assert score == 1.0

    def test_very_long_evidence(self):
        """Test handling of very long evidence strings.

        Given: Evidence with very long text
        When: similarity is calculated
        Then: Should handle without errors
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        long_text = "error " * 1000
        score = detector.get_similarity_score(long_text, long_text)
        assert score == 1.0

    def test_unicode_evidence(self):
        """Test handling of unicode characters in evidence.

        Given: Evidence with unicode characters
        When: similarity is calculated
        Then: Should handle without errors
        """
        EvidenceSaturationDetector = _import_detector()

        detector = EvidenceSaturationDetector()
        score = detector.get_similarity_score(
            "Database connection error: \u2717 failed", "Database connection error: \u2717 failed"
        )
        assert score == 1.0
