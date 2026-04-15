"""Tests for weighted scoring models (CHANGE-001: TASK-002)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from findings.models import (
    EvidenceTier,
    Finding,
    Layer,
    Severity,
    SQAReport,
    _compute_layer_weights,
    _compute_per_finding_score,
)


class TestPerFindingScoreFormula:
    """Tests for _compute_per_finding_score."""

    def test_midpoint_defaults_produce_50(self):
        """Midpoint defaults (0.5, 0.5, 0.5) → 50."""
        f = Finding(
            finding_id="TEST-001",
            severity=Severity.MEDIUM,
            layer=Layer.L1_SYNTACTIC,
            title="Test",
            description="Test",
            reproducibility=0.5,
            recency=0.5,
            impact=0.5,
        )
        score = _compute_per_finding_score(f)
        # (0.5*0.3 + 0.5*0.2 + 0.5*0.5)*100 = (0.15+0.1+0.25)*100 = 50
        assert score == 50.0

    def test_all_ones_produce_100(self):
        """All max fields → 100."""
        f = Finding(
            finding_id="TEST-002",
            severity=Severity.HIGH,
            layer=Layer.L2_SEMANTIC,
            title="Test",
            description="Test",
            reproducibility=1.0,
            recency=1.0,
            impact=1.0,
        )
        score = _compute_per_finding_score(f)
        # (1.0*0.3 + 1.0*0.2 + 1.0*0.5)*100 = 100
        assert score == 100.0

    def test_all_zeros_produce_0(self):
        """All min fields → 0."""
        f = Finding(
            finding_id="TEST-003",
            severity=Severity.LOW,
            layer=Layer.L3_STRUCTURAL,
            title="Test",
            description="Test",
            reproducibility=0.0,
            recency=0.0,
            impact=0.0,
        )
        score = _compute_per_finding_score(f)
        assert score == 0.0

    def test_per_finding_score_scaled_to_100(self):
        """Verify formula returns values in [0, 100] range."""
        f = Finding(
            finding_id="TEST-004",
            severity=Severity.CRITICAL,
            layer=Layer.L5_SECURITY,
            title="Test",
            description="Test",
            reproducibility=0.75,
            recency=0.6,
            impact=0.9,
        )
        score = _compute_per_finding_score(f)
        # (0.75*0.3 + 0.6*0.2 + 0.9*0.5)*100 = (0.225+0.12+0.45)*100 = 79.5
        assert score == 79.5


class TestPerFindingScoreClamped:
    """Tests for __post_init__ clamping."""

    def test_values_above_1_clamped_to_1(self):
        """Values > 1.0 are clamped to 1.0."""
        f = Finding(
            finding_id="TEST-005",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Test",
            description="Test",
            reproducibility=1.5,
            recency=2.0,
            impact=0.5,
        )
        # __post_init__ clamps to [0.0, 1.0]
        assert f.reproducibility == 1.0
        assert f.recency == 1.0
        assert f.impact == 0.5

    def test_values_below_0_clamped_to_0(self):
        """Values < 0.0 are clamped to 0.0."""
        f = Finding(
            finding_id="TEST-006",
            severity=Severity.MEDIUM,
            layer=Layer.L1_SYNTACTIC,
            title="Test",
            description="Test",
            reproducibility=-0.5,
            recency=-1.0,
            impact=0.5,
        )
        assert f.reproducibility == 0.0
        assert f.recency == 0.0
        assert f.impact == 0.5


class TestComputeLayerWeights:
    """Tests for _compute_layer_weights."""

    def test_all_layers_active_weights_sum_to_1(self):
        """When all layers are active, weights should sum to ~1.0."""
        findings = [
            Finding(
                finding_id="L2-1",
                severity=Severity.HIGH,
                layer=Layer.L2_SEMANTIC,
                title="L2",
                description="L2",
            ),
            Finding(
                finding_id="L3-1",
                severity=Severity.MEDIUM,
                layer=Layer.L3_STRUCTURAL,
                title="L3",
                description="L3",
            ),
            Finding(
                finding_id="L5-1",
                severity=Severity.LOW,
                layer=Layer.L5_SECURITY,
                title="L5",
                description="L5",
            ),
            Finding(
                finding_id="L1-1",
                severity=Severity.LOW,
                layer=Layer.L1_SYNTACTIC,
                title="L1",
                description="L1",
            ),
            Finding(
                finding_id="L6-1",
                severity=Severity.LOW,
                layer=Layer.L6_PERFORMANCE,
                title="L6",
                description="L6",
            ),
            Finding(
                finding_id="L7-1",
                severity=Severity.LOW,
                layer=Layer.L7_OPERATIONAL,
                title="L7",
                description="L7",
            ),
        ]
        weights = _compute_layer_weights(findings)
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001

    def test_no_findings_returns_zero_weights(self):
        """Empty findings list returns zero weights."""
        weights = _compute_layer_weights([])
        assert all(v == 0.0 for v in weights.values())

    def test_inactive_layer_weight_redistributed(self):
        """When L2 has no findings, its weight redistributes to active layers."""
        findings = [
            Finding(
                finding_id="L1-1",
                severity=Severity.LOW,
                layer=Layer.L1_SYNTACTIC,
                title="L1",
                description="L1",
            ),
        ]
        weights = _compute_layer_weights(findings)
        # L1 should get its own weight plus L2's 0.30 redistributed
        assert weights[Layer.L1_SYNTACTIC] > 0.083


class TestHealthBand:
    """Tests for SQAReport.health_band property."""

    def _report(self, findings=None, score=None):
        r = SQAReport(findings=findings or [], target="/test")
        if score is not None:
            r.health_score = score
        else:
            r.health_score = r.compute_health_score()
        return r

    def test_nominal_band_95_to_100(self):
        for s in [95, 96, 99, 100]:
            r = self._report(score=s)
            assert r.health_band == "NOMINAL", f"score={s}"

    def test_nominal_band_100(self):
        r = self._report(findings=[], score=100)
        assert r.health_band == "NOMINAL"

    def test_minor_band_80_to_94(self):
        for s in [80, 85, 90, 94]:
            r = self._report(score=s)
            assert r.health_band == "MINOR", f"score={s}"

    def test_middle_band_50_to_79(self):
        for s in [50, 60, 70, 79]:
            r = self._report(score=s)
            assert r.health_band == "MIDDLE", f"score={s}"

    def test_critical_band_below_50(self):
        for s in [49, 30, 0, -50]:
            r = self._report(score=s)
            assert r.health_band == "CRITICAL", f"score={s}"

    def test_band_boundary_95_nominal(self):
        """Score 95 is NOMINAL, 94 would be MINOR."""
        r = self._report(score=95)
        assert r.health_band == "NOMINAL"

    def test_band_boundary_80_minor(self):
        """Score 80 is MINOR, 79 is MIDDLE."""
        r80 = self._report(score=80)
        r79 = self._report(score=79)
        assert r80.health_band == "MINOR"
        assert r79.health_band == "MIDDLE"

    def test_band_boundary_50_middle(self):
        """Score 50 is MIDDLE, 49 is CRITICAL."""
        r50 = self._report(score=50)
        r49 = self._report(score=49)
        assert r50.health_band == "MIDDLE"
        assert r49.health_band == "CRITICAL"


class TestHealthScoreWithLayerWeights:
    """Tests for health_score with weighted layer contributions."""

    def _make_report(self, findings):
        r = SQAReport(findings=findings, target="/test")
        r.health_score = r.compute_health_score()
        return r

    def test_no_findings_score_100(self):
        """Empty report scores 100."""
        r = self._make_report([])
        assert r.health_score == 100

    def test_single_critical_reduces_score(self):
        """A single CRITICAL finding should reduce score."""
        f = Finding(
            finding_id="C1",
            severity=Severity.CRITICAL,
            layer=Layer.L5_SECURITY,
            title="SQL injection",
            description="Vulnerable query",
            evidence_tier=EvidenceTier.T3,
            category="security",
        )
        r = self._make_report([f])
        assert r.health_score < 100
