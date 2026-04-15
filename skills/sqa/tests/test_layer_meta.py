"""Tests for meta-synthesis layer (consensus, blind-spot, evidence quality)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from findings.models import EvidenceTier, Finding, Layer, Severity
from layers.layer_meta import (
    _check_evidence_quality,
    _detect_blind_spots,
    _detect_consensus,
    _enforce_evidence_citations,
    run_meta,
)


class TestDetectConsensus:
    """Tests for _detect_consensus."""

    def test_single_layer_no_consensus(self):
        f = Finding(
            finding_id="L1-001",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Error",
            description="Error",
            location="/src/a.py:1",
            evidence_tier=EvidenceTier.T3,
            category="syntax",
        )
        result = _detect_consensus([f])
        assert result == []

    def test_two_layers_same_location_creates_consensus(self):
        f1 = Finding(
            finding_id="L1-001",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Style violation",
            description="Error",
            location="/src/a.py:1",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        f2 = Finding(
            finding_id="L3-001",
            severity=Severity.HIGH,
            layer=Layer.L3_STRUCTURAL,
            title="Style violation",
            description="Structural issue",
            location="/src/a.py:1",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        result = _detect_consensus([f1, f2])
        assert len(result) == 1
        assert result[0].severity == Severity.HIGH
        assert result[0].consensus == 2
        assert "L1_SYNTACTIC" in result[0].description
        assert "L3_STRUCTURAL" in result[0].description

    def test_consensus_uses_highest_severity(self):
        f1 = Finding(
            finding_id="L1-001",
            severity=Severity.LOW,
            layer=Layer.L1_SYNTACTIC,
            title="Style violation",
            description="Issue",
            location="/src/a.py:1",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        f2 = Finding(
            finding_id="L2-001",
            severity=Severity.CRITICAL,
            layer=Layer.L2_SEMANTIC,
            title="Style violation",
            description="Issue",
            location="/src/a.py:1",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        result = _detect_consensus([f1, f2])
        assert result[0].severity == Severity.CRITICAL


class TestDetectBlindSpots:
    """Tests for _detect_blind_spots."""

    def test_no_blind_spot_when_layer_finds_issues(self):
        f = Finding(
            finding_id="L1-001",
            severity=Severity.MEDIUM,
            layer=Layer.L1_SYNTACTIC,
            title="Syntax error",
            description="Error",
            evidence_tier=EvidenceTier.T3,
            category="syntax",
        )
        result = _detect_blind_spots([f])
        # L1 was available and found syntax issues — no blind spot
        syntax_blind = [r for r in result if "syntax" in r.title and "L1_SYNTACTIC" in r.title]
        assert len(syntax_blind) == 0

    def test_no_blind_spot_for_D5_degraded_layer(self):
        # D5 graceful degradation means L5 never ran — this is NOT a blind spot
        # We only flag when a layer RAN but found nothing in its expected categories
        # So if L5 is not in all_findings at all, we shouldn't flag it
        # (the "layer was degraded" case is handled by the orchestrator, not meta)
        _detect_blind_spots([])
        # No findings means no blind spot detection (no layer "ran but found nothing")


class TestCheckEvidenceQuality:
    """Tests for _check_evidence_quality."""

    def test_t4_finding_flagged(self):
        f = Finding(
            finding_id="L1-HEURISTIC",
            severity=Severity.LOW,
            layer=Layer.L1_SYNTACTIC,
            title="Heuristic finding",
            description="Based on heuristic",
            evidence_tier=EvidenceTier.T4,
            category="style",
        )
        result = _check_evidence_quality([f])
        assert len(result) == 1
        assert "META-EVIDENCE-Q" in result[0].finding_id
        assert result[0].severity == Severity.LOW

    def test_t3_finding_not_flagged(self):
        f = Finding(
            finding_id="L1-001",
            severity=Severity.MEDIUM,
            layer=Layer.L1_SYNTACTIC,
            title="Logical finding",
            description="Based on logic",
            evidence_tier=EvidenceTier.T3,
            category="syntax",
        )
        result = _check_evidence_quality([f])
        assert len(result) == 0


class TestRunMeta:
    """Tests for run_meta (full meta-synthesis)."""

    def test_run_meta_combines_all_three(self):
        # A T4 finding that triggers evidence quality check
        f_t4 = Finding(
            finding_id="L1-HEURISTIC",
            severity=Severity.LOW,
            layer=Layer.L1_SYNTACTIC,
            title="Heuristic",
            description="Heuristic based",
            evidence_tier=EvidenceTier.T4,
            category="style",
        )
        result = run_meta([f_t4])
        # Should include the T4 quality finding
        assert len(result) >= 1


class TestEnforceEvidenceCitations:
    """Tests for _enforce_evidence_citations (CHANGE-002)."""

    def test_t1_no_location_downgrades_to_t3(self):
        """T1 finding with no location is downgraded to T3."""
        f = Finding(
            finding_id="L1-001",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Style issue",
            description="Missing location",
            location=None,  # No location
            evidence_tier=EvidenceTier.T1,
            category="style",
        )
        new_findings, count = _enforce_evidence_citations([f])
        assert count == 1
        assert new_findings[0].evidence_tier == EvidenceTier.T3

    def test_t1_with_location_preserved(self):
        """T1 finding WITH location stays T1."""
        f = Finding(
            finding_id="L1-002",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Style issue",
            description="Has location",
            location="/src/main.py:10",
            evidence_tier=EvidenceTier.T1,
            category="style",
        )
        new_findings, count = _enforce_evidence_citations([f])
        assert count == 0
        assert new_findings[0].evidence_tier == EvidenceTier.T1

    def test_t4_unchanged(self):
        """T4 finding is not downgraded further."""
        f = Finding(
            finding_id="L1-003",
            severity=Severity.LOW,
            layer=Layer.L1_SYNTACTIC,
            title="Heuristic",
            description="Already T4",
            location=None,
            evidence_tier=EvidenceTier.T4,
            category="style",
        )
        new_findings, count = _enforce_evidence_citations([f])
        assert count == 0
        assert new_findings[0].evidence_tier == EvidenceTier.T4

    def test_architectural_no_location_stays_t1(self):
        """Architectural finding without location stays T1 (exempt)."""
        f = Finding(
            finding_id="L3-001",
            severity=Severity.HIGH,
            layer=Layer.L3_STRUCTURAL,
            title="Architecture issue",
            description="No location but exempt",
            location=None,
            evidence_tier=EvidenceTier.T1,
            category="architectural",
        )
        new_findings, count = _enforce_evidence_citations([f])
        assert count == 0
        assert new_findings[0].evidence_tier == EvidenceTier.T1

    def test_architectural_capitalized_exempt(self):
        """Architectural (capitalized) also exempt due to case-insensitive matching."""
        f = Finding(
            finding_id="L3-002",
            severity=Severity.HIGH,
            layer=Layer.L3_STRUCTURAL,
            title="Architecture",
            description="Capitalized category",
            location=None,
            evidence_tier=EvidenceTier.T2,
            category="Architectural",
        )
        new_findings, count = _enforce_evidence_citations([f])
        assert count == 0
        assert new_findings[0].evidence_tier == EvidenceTier.T2

    def test_multiple_downgrades(self):
        """Multiple findings can be downgraded in one pass."""
        findings = [
            Finding(
                finding_id="L1-001",
                severity=Severity.HIGH,
                layer=Layer.L1_SYNTACTIC,
                title="Issue 1",
                description="No location",
                location=None,
                evidence_tier=EvidenceTier.T1,
                category="syntax",
            ),
            Finding(
                finding_id="L2-001",
                severity=Severity.MEDIUM,
                layer=Layer.L2_SEMANTIC,
                title="Issue 2",
                description="No location either",
                location=None,
                evidence_tier=EvidenceTier.T2,
                category="test",
            ),
        ]
        new_findings, count = _enforce_evidence_citations(findings)
        assert count == 2
        assert new_findings[0].evidence_tier == EvidenceTier.T3
        assert new_findings[1].evidence_tier == EvidenceTier.T3

    def test_original_findings_not_mutated(self):
        """Original findings list is not mutated (immutability)."""
        f = Finding(
            finding_id="L1-001",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Original",
            description="Should not be changed",
            location=None,
            evidence_tier=EvidenceTier.T1,
            category="syntax",
        )
        original_tier = f.evidence_tier
        _enforce_evidence_citations([f])
        # Original finding should be unchanged
        assert f.evidence_tier == original_tier

    def test_meta_finding_added_when_downgrades_occur(self):
        """run_meta adds META-EVIDENCE-DOWNGRADE finding when downgrades happen."""
        f = Finding(
            finding_id="L1-001",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Style issue",
            description="No location",
            location=None,
            evidence_tier=EvidenceTier.T1,
            category="syntax",
        )
        result = run_meta([f])
        # Should have at least the downgrade meta-finding
        downgrade_findings = [r for r in result if "META-EVIDENCE-DOWNGRADE" in r.finding_id]
        assert len(downgrade_findings) >= 1
        assert downgrade_findings[0].severity == Severity.LOW
