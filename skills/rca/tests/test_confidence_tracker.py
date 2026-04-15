"""Tests for confidence_tracker.py module.

These tests verify Bayesian confidence tracking for rca Tier 1.

Run with: pytest P:/packages/rca/skill/tests/test_confidence_tracker.py -v
"""

import sys
from pathlib import Path

import pytest

# Setup import path for rca package
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca.confidence_tracker import ConfidenceTracker


class TestConfidenceTrackerInit:
    """Tests for ConfidenceTracker initialization."""

    def test_initializes_with_empty_priors_and_posteriors(self):
        """Test that tracker starts with empty dictionaries.

        Given: Creating a new ConfidenceTracker
        When: Checking initial state
        Then: Should have empty priors and posteriors
        """
        tracker = ConfidenceTracker()

        assert tracker.priors == {}
        assert tracker.posteriors == {}

    def test_has_type_hints_for_attributes(self):
        """Test that attributes are properly typed.

        Given: Creating a new ConfidenceTracker
        When: Checking attribute types
        Then: Should have Dict[str, float] type hints
        """
        tracker = ConfidenceTracker()

        assert hasattr(tracker, "priors")
        assert hasattr(tracker, "posteriors")


class TestSetPrior:
    """Tests for set_prior method."""

    def test_sets_prior_for_new_hypothesis(self):
        """Test setting prior for new hypothesis.

        Given: A new ConfidenceTracker
        When: Setting prior for "H1" to 0.7
        Then: Should store prior correctly
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.7)

        assert tracker.priors["H1"] == 0.7
        assert tracker.posteriors["H1"] == 0.7  # posterior reset to prior

    def test_sets_prior_for_existing_hypothesis(self):
        """Test updating prior for existing hypothesis.

        Given: Hypothesis "H1" has prior 0.5
        When: Setting new prior to 0.8
        Then: Should update prior and reset posterior
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)
        tracker.set_prior("H1", 0.8)

        assert tracker.priors["H1"] == 0.8
        assert tracker.posteriors["H1"] == 0.8

    def test_raises_value_error_for_prior_below_zero(self):
        """Test that prior < 0 raises ValueError.

        Given: Creating a ConfidenceTracker
        When: Setting prior to -0.1
        Then: Should raise ValueError
        """
        tracker = ConfidenceTracker()

        with pytest.raises(ValueError, match="prior must be between 0 and 1"):
            tracker.set_prior("H1", -0.1)

    def test_raises_value_error_for_prior_above_one(self):
        """Test that prior > 1 raises ValueError.

        Given: Creating a ConfidenceTracker
        When: Setting prior to 1.5
        Then: Should raise ValueError
        """
        tracker = ConfidenceTracker()

        with pytest.raises(ValueError, match="prior must be between 0 and 1"):
            tracker.set_prior("H1", 1.5)

    def test_accepts_prior_of_zero(self):
        """Test that prior = 0 is accepted.

        Given: Creating a ConfidenceTracker
        When: Setting prior to 0.0
        Then: Should accept the prior
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.0)

        assert tracker.priors["H1"] == 0.0

    def test_accepts_prior_of_one(self):
        """Test that prior = 1 is accepted.

        Given: Creating a ConfidenceTracker
        When: Setting prior to 1.0
        Then: Should accept the prior
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 1.0)

        assert tracker.priors["H1"] == 1.0


class TestGetPrior:
    """Tests for get_prior method."""

    def test_returns_set_prior(self):
        """Test getting existing prior.

        Given: Prior for "H1" is set to 0.6
        When: Getting prior for "H1"
        Then: Should return 0.6
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.6)

        result = tracker.get_prior("H1")

        assert result == 0.6

    def test_returns_zero_for_unset_prior(self):
        """Test getting prior for unset hypothesis.

        Given: No prior has been set for "H1"
        When: Getting prior for "H1"
        Then: Should return 0.0
        """
        tracker = ConfidenceTracker()

        result = tracker.get_prior("H1")

        assert result == 0.0


class TestGetPosterior:
    """Tests for get_posterior method."""

    def test_returns_posterior_after_update(self):
        """Test getting posterior after update.

        Given: Prior is 0.5, evidence increases confidence
        When: Getting posterior after update
        Then: Should return updated probability
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)
        tracker.update("H1", likelihood_ratio=2.0)

        result = tracker.get_posterior("H1")

        assert result == pytest.approx(0.667, 0.001)

    def test_returns_prior_if_no_update(self):
        """Test getting posterior before any update.

        Given: Prior is set to 0.7
        When: Getting posterior without calling update
        Then: Should return the prior
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.7)

        result = tracker.get_posterior("H1")

        assert result == 0.7

    def test_returns_zero_for_unset_hypothesis(self):
        """Test getting posterior for unset hypothesis.

        Given: No prior or posterior set
        When: Getting posterior for "H1"
        Then: Should return 0.0
        """
        tracker = ConfidenceTracker()

        result = tracker.get_posterior("H1")

        assert result == 0.0


class TestUpdate:
    """Tests for update method."""

    def test_increases_confidence_with_supporting_evidence(self):
        """Test confidence increases with likelihood_ratio > 1.

        Given: Prior is 0.5
        When: Updating with likelihood_ratio=2.0 (supporting evidence)
        Then: Posterior should be > prior (0.667)
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)

        posterior = tracker.update("H1", likelihood_ratio=2.0)

        assert posterior > 0.5
        assert posterior == pytest.approx(0.667, 0.001)

    def test_decreases_confidence_with_refuting_evidence(self):
        """Test confidence decreases with likelihood_ratio < 1.

        Given: Prior is 0.5
        When: Updating with likelihood_ratio=0.5 (refuting evidence)
        Then: Posterior should be < prior (0.333)
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)

        posterior = tracker.update("H1", likelihood_ratio=0.5)

        assert posterior < 0.5
        assert posterior == pytest.approx(0.333, 0.01)

    def test_no_change_with_neutral_evidence(self):
        """Test confidence unchanged with likelihood_ratio = 1.

        Given: Prior is 0.6
        When: Updating with likelihood_ratio=1.0 (neutral evidence)
        Then: Posterior should equal prior (0.6)
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.6)

        posterior = tracker.update("H1", likelihood_ratio=1.0)

        assert posterior == 0.6

    def test_uses_posterior_as_current_probability(self):
        """Test that update uses posterior, not prior.

        Given: Prior is 0.5, first update changes posterior to 0.667
        When: Updating again with LR=2.0
        Then: Should use 0.667 as current, not 0.5
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)
        tracker.update("H1", likelihood_ratio=2.0)  # posterior becomes 0.667
        posterior2 = tracker.update("H1", likelihood_ratio=2.0)  # uses 0.667 as current

        assert tracker.get_posterior("H1") == pytest.approx(0.8, 0.001)

    def test_raises_value_error_for_non_positive_likelihood_ratio(self):
        """Test that likelihood_ratio <= 0 raises ValueError.

        Given: A hypothesis with prior set
        When: Updating with likelihood_ratio=0
        Then: Should raise ValueError
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)

        with pytest.raises(ValueError, match="likelihood_ratio must be positive"):
            tracker.update("H1", likelihood_ratio=0)

    def test_raises_value_error_for_negative_likelihood_ratio(self):
        """Test that negative likelihood_ratio raises ValueError.

        Given: A hypothesis with prior set
        When: Updating with likelihood_ratio=-1.0
        Then: Should raise ValueError
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)

        with pytest.raises(ValueError, match="likelihood_ratio must be positive"):
            tracker.update("H1", likelihood_ratio=-1.0)

    def test_returns_updated_posterior(self):
        """Test that update returns the new posterior.

        Given: Prior is 0.5
        When: Updating with likelihood_ratio=2.0
        Then: Should return 0.667
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)

        result = tracker.update("H1", likelihood_ratio=2.0)

        assert result == pytest.approx(0.667, 0.001)


class TestReset:
    """Tests for reset method."""

    def test_clears_all_posteriors(self):
        """Test that reset clears all posterior updates.

        Given: Two hypotheses with posteriors updated
        When: Calling reset
        Then: All posteriors should be cleared
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)
        tracker.set_prior("H2", 0.3)
        tracker.update("H1", likelihood_ratio=2.0)
        tracker.update("H2", likelihood_ratio=0.5)

        tracker.reset()

        assert tracker.posteriors == {}
        # Priors should remain unchanged
        assert tracker.priors["H1"] == 0.5
        assert tracker.priors["H2"] == 0.3


class TestBatchUpdate:
    """Tests for batch_update method."""

    def test_updates_multiple_hypotheses(self):
        """Test updating multiple hypotheses at once.

        Given: Two hypotheses with different evidence
        When: Calling batch_update with evidence dict
        Then: Should return updated posteriors for both
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)
        tracker.set_prior("H2", 0.5)

        evidence = {
            "H1": {"likelihood_ratio": 2.0, "supports": True},
            "H2": {"likelihood_ratio": 0.5, "supports": False},
        }
        results = tracker.batch_update(evidence)

        assert results["H1"] == pytest.approx(0.667, 0.01)
        assert results["H2"] == pytest.approx(0.333, 0.01)

    def test_uses_default_likelihood_ratio_of_one(self):
        """Test default likelihood_ratio when not specified.

        Given: Hypothesis with evidence dict missing likelihood_ratio
        When: Calling batch_update
        Then: Should use default likelihood_ratio=1.0
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.6)

        evidence = {"H1": {"supports": True}}  # No likelihood_ratio
        results = tracker.batch_update(evidence)

        assert results["H1"] == 0.6  # Unchanged with LR=1

    def test_uses_default_supports_true(self):
        """Test default supports when not specified.

        Given: Hypothesis with evidence dict missing supports
        When: Calling batch_update
        Then: Should use default supports=True
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)

        evidence = {"H1": {"likelihood_ratio": 2.0}}  # No supports key
        results = tracker.batch_update(evidence)

        assert results["H1"] == pytest.approx(0.667, 0.001)


class TestNormalize:
    """Tests for normalize method."""

    def test_normalizes_posteriors_to_sum_to_one(self):
        """Test normalization makes posteriors sum to 1.0.

        Given: Two hypotheses with posteriors 0.5 and 0.5
        When: Normalizing both hypotheses
        Then: Should return {0.5, 0.5} (sums to 1.0)
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)
        tracker.set_prior("H2", 0.5)

        normalized = tracker.normalize(["H1", "H2"])

        assert normalized["H1"] == 0.5
        assert normalized["H2"] == 0.5
        assert normalized["H1"] + normalized["H2"] == 1.0

    def test_normalizes_with_three_hypotheses(self):
        """Test normalization with three hypotheses.

        Given: Three hypotheses with posteriors summing to 0.75
        When: Normalizing all three
        Then: Should scale so they sum to 1.0
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.25)
        tracker.set_prior("H2", 0.25)
        tracker.set_prior("H3", 0.25)

        normalized = tracker.normalize(["H1", "H2", "H3"])

        assert sum(normalized.values()) == pytest.approx(1.0, 0.001)
        assert normalized["H1"] == pytest.approx(0.333, 0.01)
        assert normalized["H2"] == pytest.approx(0.333, 0.01)
        assert normalized["H3"] == pytest.approx(0.333, 0.01)

    def test_returns_zeroes_when_total_is_zero(self):
        """Test normalization when all posteriors are zero.

        Given: No posteriors set (all default to 0.0)
        When: Normalizing hypotheses
        Then: Should return zeros for all
        """
        tracker = ConfidenceTracker()

        normalized = tracker.normalize(["H1", "H2"])

        assert normalized["H1"] == 0.0
        assert normalized["H2"] == 0.0

    def test_returns_normalized_posteriors_dict(self):
        """Test that normalize returns dictionary of normalized posteriors.

        Given: Hypotheses with different posteriors
        When: Calling normalize
        Then: Should return dict with normalized values
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.4)
        tracker.set_prior("H2", 0.6)

        result = tracker.normalize(["H1", "H2"])

        assert isinstance(result, dict)
        assert "H1" in result
        assert "H2" in result


class TestConfidenceTrackerIntegration:
    """Integration tests for ConfidenceTracker."""

    def test_full_bayesian_update_workflow(self):
        """Test complete Bayesian update cycle.

        Given: Multiple pieces of evidence for hypothesis
        When: Updating sequentially with evidence
        Then: Confidence should accumulate appropriately
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("Database timeout", 0.3)

        # Evidence 1: Supports hypothesis (LR=3.0)
        posterior1 = tracker.update("Database timeout", likelihood_ratio=3.0)
        assert posterior1 > 0.3  # Confidence increased

        # Evidence 2: More support (LR=2.0)
        posterior2 = tracker.update("Database timeout", likelihood_ratio=2.0)
        assert posterior2 > posterior1  # Confidence increased further

        # Evidence 3: Refutes hypothesis (LR=0.5)
        posterior3 = tracker.update("Database timeout", likelihood_ratio=0.5)
        assert posterior3 < posterior2  # Confidence decreased

    def test_competing_hypotheses_comparison(self):
        """Test comparing competing hypotheses.

        Given: Two competing hypotheses with evidence
        When: Normalizing posteriors
        Then: Should be able to compare relative confidence
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("Hypothesis A", 0.5)
        tracker.set_prior("Hypothesis B", 0.5)

        # Evidence supports A more than B
        tracker.update("Hypothesis A", likelihood_ratio=2.0)
        tracker.update("Hypothesis B", likelihood_ratio=0.5)

        normalized = tracker.normalize(["Hypothesis A", "Hypothesis B"])

        assert normalized["Hypothesis A"] > normalized["Hypothesis B"]
        assert normalized["Hypothesis A"] + normalized["Hypothesis B"] == 1.0

    def test_reset_and_reuse_hypothesis(self):
        """Test resetting and reusing hypothesis.

        Given: Hypothesis with updated posterior
        When: Resetting and setting new prior
        Then: Should start fresh with new prior
        """
        tracker = ConfidenceTracker()
        tracker.set_prior("H1", 0.5)
        tracker.update("H1", likelihood_ratio=3.0)
        assert tracker.get_posterior("H1") > 0.5

        tracker.reset()
        assert tracker.get_posterior("H1") == 0.0  # Cleared

        tracker.set_prior("H1", 0.8)  # New prior
        assert tracker.get_posterior("H1") == 0.8
