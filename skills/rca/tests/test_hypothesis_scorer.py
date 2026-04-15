"""Tests for HypothesisScorer with Bayesian updater in rca Tier 1.

These tests verify the hypothesis scoring framework with Bayesian probability
updates, confidence tracking, and weighted ranking.

TDD Cycle: RED Phase - Tests MUST fail before implementation.

Run with: pytest P:/.claude/skills/debugrca/tests/test_hypothesis_scorer.py -v
"""

import sys
from pathlib import Path

import pytest

# Add package src to path for imports
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)


def _import_scorer():
    """Import HypothesisScorer from rca package."""
    from rca.hypothesis_scorer import HypothesisScorer

    return HypothesisScorer


def _import_tracker():
    """Import ConfidenceTracker from rca package."""
    from rca.confidence_tracker import ConfidenceTracker

    return ConfidenceTracker


class TestHypothesisScorerInit:
    """Tests for HypothesisScorer initialization."""

    def test_init_with_default_weights(self):
        """Test initialization with default weights.

        Given: A HypothesisScorer is created
        When: Initialized without parameters
        Then: Default weights should sum to 1.0
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        assert scorer.weights["reproducibility"] == 0.3
        assert scorer.weights["recency"] == 0.2
        assert scorer.weights["impact"] == 0.5
        assert sum(scorer.weights.values()) == pytest.approx(1.0)

    def test_init_with_custom_weights(self):
        """Test initialization with custom weights.

        Given: A HypothesisScorer is created
        When: Initialized with custom weight dict
        Then: Custom weights should be used
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer(weights={"reproducibility": 0.5, "recency": 0.3, "impact": 0.2})
        assert scorer.weights["reproducibility"] == 0.5
        assert scorer.weights["recency"] == 0.3
        assert scorer.weights["impact"] == 0.2


class TestBayesianPrior:
    """Tests for Bayesian prior setting."""

    def test_set_prior_for_new_hypothesis(self):
        """Test setting prior for a new hypothesis.

        Given: A HypothesisScorer is created
        When: set_prior is called with a new hypothesis
        Then: The hypothesis should have the specified prior probability
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Database timeout", 0.3)

        confidence = scorer.get_confidence("Database timeout")
        assert confidence == 0.3

    def test_set_prior_for_existing_hypothesis(self):
        """Test updating prior for an existing hypothesis.

        Given: A hypothesis exists with a prior
        When: set_prior is called with a new value
        Then: The prior should be updated
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Network latency", 0.2)
        assert scorer.get_confidence("Network latency") == 0.2

        scorer.set_prior("Network latency", 0.6)
        assert scorer.get_confidence("Network latency") == 0.6

    def test_set_prior_validates_range(self):
        """Test that set_prior validates the 0-1 range.

        Given: A HypothesisScorer is created
        When: set_prior is called with invalid range
        Then: Should raise ValueError
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        with pytest.raises(ValueError, match="prior must be between 0 and 1"):
            scorer.set_prior("Invalid hypothesis", 1.5)

        with pytest.raises(ValueError, match="prior must be between 0 and 1"):
            scorer.set_prior("Invalid hypothesis", -0.1)


class TestBayesianUpdate:
    """Tests for Bayesian evidence update."""

    def test_update_with_supporting_evidence(self):
        """Test Bayesian update with supporting evidence.

        Given: A hypothesis with prior 0.5
        When: update is called with supporting evidence (likelihood_ratio=3)
        Then: Posterior should increase according to Bayes' rule
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("API timeout", 0.5)

        # Bayes: P(H|E) = P(E|H) * P(H) / P(E)
        # With likelihood_ratio = 3: posterior = (3 * 0.5) / (3 * 0.5 + 1 * 0.5) = 1.5 / 2.0 = 0.75
        scorer.update("API timeout", evidence_supports=True, likelihood_ratio=3.0)

        confidence = scorer.get_confidence("API timeout")
        assert confidence == pytest.approx(0.75, rel=0.01)

    def test_update_with_refuting_evidence(self):
        """Test Bayesian update with refuting evidence.

        Given: A hypothesis with prior 0.7
        When: update is called with refuting evidence (likelihood_ratio=0.2)
        Then: Posterior should decrease
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Memory leak", 0.7)

        # With likelihood_ratio = 0.2: posterior = (0.2 * 0.7) / (0.2 * 0.7 + 1 * 0.3) = 0.14 / 0.44 = 0.318
        scorer.update("Memory leak", evidence_supports=False, likelihood_ratio=0.2)

        confidence = scorer.get_confidence("Memory leak")
        assert confidence < 0.5
        assert confidence == pytest.approx(0.318, rel=0.01)

    def test_update_with_neutral_evidence(self):
        """Test Bayesian update with neutral evidence.

        Given: A hypothesis with prior 0.5
        When: update is called with likelihood_ratio=1
        Then: Posterior should equal prior (no change)
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("CPU spike", 0.5)

        scorer.update("CPU spike", evidence_supports=True, likelihood_ratio=1.0)

        confidence = scorer.get_confidence("CPU spike")
        assert confidence == 0.5

    def test_multiple_sequential_updates(self):
        """Test multiple sequential Bayesian updates.

        Given: A hypothesis with prior 0.3
        When: Multiple updates are applied
        Then: Each update should build on the previous posterior
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Database lock", 0.3)

        # First update: 0.3 -> (2 * 0.3) / (2 * 0.3 + 1 * 0.7) = 0.6 / 1.3 = 0.462
        scorer.update("Database lock", evidence_supports=True, likelihood_ratio=2.0)
        assert scorer.get_confidence("Database lock") == pytest.approx(0.462, rel=0.01)

        # Second update on posterior: 0.462 -> (3 * 0.462) / (3 * 0.462 + 1 * 0.538) = 1.386 / 1.924 = 0.720
        scorer.update("Database lock", evidence_supports=True, likelihood_ratio=3.0)
        assert scorer.get_confidence("Database lock") == pytest.approx(0.720, rel=0.01)

    def test_update_validates_likelihood_ratio(self):
        """Test that update validates likelihood ratio is positive.

        Given: A HypothesisScorer is created
        When: update is called with invalid likelihood_ratio
        Then: Should raise ValueError
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Test", 0.5)

        with pytest.raises(ValueError, match="likelihood_ratio must be positive"):
            scorer.update("Test", evidence_supports=True, likelihood_ratio=0)

        with pytest.raises(ValueError, match="likelihood_ratio must be positive"):
            scorer.update("Test", evidence_supports=True, likelihood_ratio=-1)


class TestGetConfidence:
    """Tests for get_confidence method."""

    def test_get_confidence_for_unknown_hypothesis(self):
        """Test getting confidence for non-existent hypothesis.

        Given: A HypothesisScorer without the hypothesis
        When: get_confidence is called
        Then: Should return 0.0 (no prior set)
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        confidence = scorer.get_confidence("Unknown hypothesis")
        assert confidence == 0.0

    def test_get_confidence_after_updates(self):
        """Test confidence reflects all accumulated evidence.

        Given: A hypothesis with prior and multiple updates
        When: get_confidence is called
        Then: Should return the current posterior probability
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Disk I/O", 0.4)
        scorer.update("Disk I/O", evidence_supports=True, likelihood_ratio=2.5)

        confidence = scorer.get_confidence("Disk I/O")
        assert 0.4 < confidence < 1.0


class TestWeightedRanking:
    """Tests for weighted ranking formula: Reproducibility(0.3) * Recency(0.2) * Impact(0.5)."""

    def test_rank_with_single_hypothesis(self):
        """Test ranking with a single hypothesis.

        Given: One hypothesis with factors
        When: rank is called
        Then: Should return list with that hypothesis
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("API timeout", 0.5)

        ranked = scorer.rank(["API timeout"])
        assert len(ranked) == 1
        assert ranked[0] == "API timeout"

    def test_rank_with_multiple_hypotheses(self):
        """Test ranking orders by weighted score.

        Given: Multiple hypotheses with different factors
        When: rank is called
        Then: Should return hypotheses ordered by weighted score
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        # H1: 0.3*0.9 + 0.2*0.8 + 0.5*0.7 = 0.27 + 0.16 + 0.35 = 0.78
        scorer.set_prior("Database timeout", 0.5)
        scorer.add_hypothesis("Database timeout", reproducibility=0.9, recency=0.8, impact=0.7)

        # H2: 0.3*0.5 + 0.2*0.9 + 0.5*0.6 = 0.15 + 0.18 + 0.30 = 0.63
        scorer.set_prior("Network latency", 0.5)
        scorer.add_hypothesis("Network latency", reproducibility=0.5, recency=0.9, impact=0.6)

        # H3: 0.3*1.0 + 0.2*0.5 + 0.5*0.9 = 0.30 + 0.10 + 0.45 = 0.85
        scorer.set_prior("Memory leak", 0.5)
        scorer.add_hypothesis("Memory leak", reproducibility=1.0, recency=0.5, impact=0.9)

        ranked = scorer.rank(["Database timeout", "Network latency", "Memory leak"])
        assert ranked == ["Memory leak", "Database timeout", "Network latency"]

    def test_rank_with_confidence_integration(self):
        """Test ranking integrates confidence with weighted score.

        Given: Hypotheses with priors and weighted scores
        When: rank is called
        Then: Should rank by (weighted_score * confidence)
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        # H1: High weighted score (0.85) but low confidence (0.3) = 0.255
        scorer.set_prior("H1", 0.3)
        scorer.add_hypothesis("H1", reproducibility=1.0, recency=0.5, impact=0.9)

        # H2: Medium weighted score (0.70) but high confidence (0.9) = 0.63
        scorer.set_prior("H2", 0.9)
        scorer.add_hypothesis("H2", reproducibility=0.8, recency=0.7, impact=0.6)

        ranked = scorer.rank(["H1", "H2"])
        assert ranked == ["H2", "H1"]  # H2 wins due to higher confidence

    def test_rank_empty_list(self):
        """Test ranking with empty hypothesis list.

        Given: No hypotheses to rank
        When: rank is called with empty list
        Then: Should return empty list
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        ranked = scorer.rank([])
        assert ranked == []

    def test_rank_with_tie_breaker(self):
        """Test ranking with tie-breaking on equal scores.

        Given: Two hypotheses with identical combined scores
        When: rank is called
        Then: Should maintain deterministic order (alphabetical or insertion)
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("H1", 0.5)
        scorer.add_hypothesis("H1", reproducibility=0.5, recency=0.5, impact=0.5)
        scorer.set_prior("H2", 0.5)
        scorer.add_hypothesis("H2", reproducibility=0.5, recency=0.5, impact=0.5)

        ranked = scorer.rank(["H1", "H2"])
        assert len(ranked) == 2
        # Both have same score, order should be deterministic
        assert "H1" in ranked
        assert "H2" in ranked


class TestConfidenceTracker:
    """Tests for ConfidenceTracker module."""

    def test_confidence_tracker_init(self):
        """Test ConfidenceTracker initialization.

        Given: A ConfidenceTracker is created
        When: Initialized with hypotheses
        Then: Should store initial probabilities
        """
        ConfidenceTracker = _import_tracker()

        tracker = ConfidenceTracker()
        assert tracker.priors == {}

    def test_confidence_tracker_set_prior(self):
        """Test setting prior in ConfidenceTracker.

        Given: A ConfidenceTracker is created
        When: set_prior is called
        Then: Should store the prior probability
        """
        ConfidenceTracker = _import_tracker()

        tracker = ConfidenceTracker()
        tracker.set_prior("Database timeout", 0.4)

        assert tracker.get_prior("Database timeout") == 0.4

    def test_confidence_tracker_bayesian_update(self):
        """Test Bayesian update in ConfidenceTracker.

        Given: A hypothesis with prior 0.5
        When: update is called with likelihood_ratio=2
        Then: Should compute correct posterior
        """
        ConfidenceTracker = _import_tracker()

        tracker = ConfidenceTracker()
        tracker.set_prior("API latency", 0.5)

        # P(H|E) = (2 * 0.5) / (2 * 0.5 + 1 * 0.5) = 1.0 / 1.5 = 0.667
        posterior = tracker.update("API latency", likelihood_ratio=2.0, evidence_supports=True)

        assert posterior == pytest.approx(0.667, rel=0.01)
        assert tracker.get_posterior("API latency") == pytest.approx(0.667, rel=0.01)

    def test_confidence_tracker_get_posterior_no_prior(self):
        """Test get_posterior for hypothesis with no prior.

        Given: A ConfidenceTracker without the hypothesis
        When: get_posterior is called
        Then: Should return 0.0
        """
        ConfidenceTracker = _import_tracker()

        tracker = ConfidenceTracker()
        posterior = tracker.get_posterior("Unknown")
        assert posterior == 0.0

    def test_confidence_tracker_reset(self):
        """Test resetting posteriors to priors.

        Given: A ConfidenceTracker with updated hypotheses
        When: reset is called
        Then: Should clear all posterior updates
        """
        ConfidenceTracker = _import_tracker()

        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.3)
        tracker.update("H1", likelihood_ratio=2.0, evidence_supports=True)
        assert tracker.get_posterior("H1") > 0.3

        tracker.reset()
        assert tracker.get_posterior("H1") == 0.0

    def test_confidence_tracker_batch_update(self):
        """Test batch updating multiple hypotheses.

        Given: Multiple hypotheses with priors
        When: batch_update is called with evidence
        Then: Should update all hypotheses
        """
        ConfidenceTracker = _import_tracker()

        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.4)
        tracker.set_prior("H2", 0.6)

        evidence = {
            "H1": {"likelihood_ratio": 2.0, "supports": True},
            "H2": {"likelihood_ratio": 0.5, "supports": False},
        }

        tracker.batch_update(evidence)

        assert tracker.get_posterior("H1") > 0.4
        assert tracker.get_posterior("H2") < 0.6

    def test_confidence_tracker_normalize(self):
        """Test normalizing posteriors to sum to 1.

        Given: Multiple hypotheses with posteriors
        When: normalize is called
        Then: Posteriors should sum to 1.0
        """
        ConfidenceTracker = _import_tracker()

        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.3)
        tracker.set_prior("H2", 0.4)
        tracker.set_prior("H3", 0.2)

        tracker.update("H1", likelihood_ratio=3.0, evidence_supports=True)
        tracker.update("H2", likelihood_ratio=2.0, evidence_supports=True)
        tracker.update("H3", likelihood_ratio=1.5, evidence_supports=True)

        normalized = tracker.normalize(["H1", "H2", "H3"])
        assert sum(normalized.values()) == pytest.approx(1.0, rel=0.01)


class TestIntegration:
    """Integration tests for HypothesisScorer and ConfidenceTracker."""

    def test_scorer_uses_confidence_tracker(self):
        """Test that HypothesisScorer uses ConfidenceTracker for priors.

        Given: A HypothesisScorer with confidence tracking
        When: set_prior and update are called
        Then: ConfidenceTracker should be used internally
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Integration test", 0.5)
        scorer.update("Integration test", evidence_supports=True, likelihood_ratio=2.0)

        confidence = scorer.get_confidence("Integration test")
        assert confidence > 0.5

    def test_rank_combines_score_and_confidence(self):
        """Test that ranking combines weighted score with Bayesian confidence.

        Given: Hypotheses with different scores and confidences
        When: rank is called
        Then: Should prioritize balanced high-score + high-confidence
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        # High score, low confidence: 0.85 * 0.3 = 0.255
        scorer.set_prior("High score low confidence", 0.3)
        scorer.add_hypothesis(
            "High score low confidence", reproducibility=1.0, recency=0.9, impact=0.8
        )

        # Medium score, high confidence: 0.65 * 0.9 = 0.585
        scorer.set_prior("Medium score high confidence", 0.9)
        scorer.add_hypothesis(
            "Medium score high confidence", reproducibility=0.7, recency=0.6, impact=0.65
        )

        ranked = scorer.rank(["High score low confidence", "Medium score high confidence"])
        assert ranked[0] == "Medium score high confidence"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_prior_at_boundaries(self):
        """Test priors at 0.0 and 1.0 boundaries.

        Given: Hypotheses with priors at boundaries
        When: Operations are performed
        Then: Should handle correctly
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Certain", 1.0)
        scorer.set_prior("Impossible", 0.0)

        assert scorer.get_confidence("Certain") == 1.0
        assert scorer.get_confidence("Impossible") == 0.0

    def test_update_with_extreme_likelihood_ratio(self):
        """Test update with extreme likelihood ratio.

        Given: A hypothesis with prior 0.5
        When: update is called with very high likelihood_ratio
        Then: Should approach 1.0 but not exceed
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Extreme", 0.5)

        # Very strong evidence
        scorer.update("Extreme", evidence_supports=True, likelihood_ratio=1000.0)

        confidence = scorer.get_confidence("Extreme")
        assert confidence > 0.99
        assert confidence <= 1.0

    def test_rank_with_nonexistent_hypothesis(self):
        """Test ranking with hypothesis that doesn't exist.

        Given: A list containing a non-existent hypothesis
        When: rank is called
        Then: Should handle gracefully (assign 0 score)
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        ranked = scorer.rank(["Non-existent"])
        assert ranked == [] or ranked == ["Non-existent"]

    def test_unicode_hypothesis_names(self):
        """Test handling of unicode in hypothesis names.

        Given: Hypothesis names with unicode characters
        When: Operations are performed
        Then: Should handle without errors
        """
        HypothesisScorer = _import_scorer()

        scorer = HypothesisScorer()
        scorer.set_prior("Database timeout: connection failed", 0.5)
        scorer.update(
            "Database timeout: connection failed", evidence_supports=True, likelihood_ratio=2.0
        )

        confidence = scorer.get_confidence("Database timeout: connection failed")
        assert confidence > 0.5
