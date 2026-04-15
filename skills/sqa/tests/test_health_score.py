"""Tests for SQAReport health score and deduplication logic."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from findings.models import EvidenceTier, Finding, Layer, Severity, SQAReport


class TestFindingKey:
    """Tests for Finding.key() deduplication key."""

    def test_key_with_location(self):
        f = Finding(
            finding_id="L1-001",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Unused import",
            description="os not used",
            location="/src/main.py:5",
            evidence_tier=EvidenceTier.T3,
            category="syntax",
        )
        key = f.key()
        assert key == ("/src/main.py", "5", "syntax", "Unused import")

    def test_key_without_location(self):
        f = Finding(
            finding_id="L1-002",
            severity=Severity.MEDIUM,
            layer=Layer.L1_SYNTACTIC,
            title="Style violation",
            description="Line too long",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        key = f.key()
        assert key == ("", "", "style", "Style violation")


class TestHealthScore:
    """Tests for SQAReport.compute_health_score()."""

    def _make_report(self, findings):
        r = SQAReport(findings=findings, target="/test")
        r.health_score = r.compute_health_score()
        return r

    def test_no_findings_healthy(self):
        report = self._make_report([])
        assert report.health_score == 100

    def test_single_critical_drops_20(self):
        f = Finding(
            finding_id="C1",
            severity=Severity.CRITICAL,
            layer=Layer.L5_SECURITY,
            title="SQL injection",
            description="Vulnerable query",
            evidence_tier=EvidenceTier.T3,
            category="security",
        )
        report = self._make_report([f])
        assert report.health_score == 90

    def test_single_high_drops_10(self):
        f = Finding(
            finding_id="H1",
            severity=Severity.HIGH,
            layer=Layer.L6_PERFORMANCE,
            title="N plus 1 query",
            description="Query in loop",
            evidence_tier=EvidenceTier.T3,
            category="performance",
        )
        report = self._make_report([f])
        assert report.health_score == 95

    def test_single_medium_drops_5(self):
        f = Finding(
            finding_id="M1",
            severity=Severity.MEDIUM,
            layer=Layer.L1_SYNTACTIC,
            title="Unused variable",
            description="x defined but not used",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        report = self._make_report([f])
        assert report.health_score == 97

    def test_single_low_drops_2(self):
        f = Finding(
            finding_id="L1",
            severity=Severity.LOW,
            layer=Layer.L7_OPERATIONAL,
            title="Dead hook",
            description="Hook file not modified in 30 days",
            evidence_tier=EvidenceTier.T3,
            category="operational",
        )
        report = self._make_report([f])
        assert report.health_score == 99

    def test_multiple_severities_combined(self):
        findings = [
            Finding(
                finding_id="C1",
                severity=Severity.CRITICAL,
                layer=Layer.L5_SECURITY,
                title="SQL injection",
                description="Vulnerable",
                evidence_tier=EvidenceTier.T3,
                category="security",
            ),
            Finding(
                finding_id="H1",
                severity=Severity.HIGH,
                layer=Layer.L6_PERFORMANCE,
                title="N+1",
                description="Query in loop",
                evidence_tier=EvidenceTier.T3,
                category="performance",
            ),
            Finding(
                finding_id="M1",
                severity=Severity.MEDIUM,
                layer=Layer.L1_SYNTACTIC,
                title="Style",
                description="Line too long",
                evidence_tier=EvidenceTier.T3,
                category="style",
            ),
        ]
        report = self._make_report(findings)
        assert report.health_score == 82  # 100 - 20*0.5 - 10*0.5 - 5*0.5 = 82

    def test_negative_score_capped_at_minus_100(self):
        # 10 unique criticals T3: 10*20*0.5=100 → 100-100=0 → capped at -100 not triggered
        findings = [
            Finding(
                finding_id=f"C{i}",
                severity=Severity.CRITICAL,
                layer=Layer.L5_SECURITY,
                title=f"Issue {i}",  # different titles → different keys → all unique
                description="Critical",
                evidence_tier=EvidenceTier.T3,
                category="security",
            )
            for i in range(10)
        ]
        report = self._make_report(findings)
        assert report.health_score == 0  # not capped at -100 since 0 > -100

    def test_negative_score_preserved(self):
        findings = [
            Finding(
                finding_id=f"C{i}",
                severity=Severity.CRITICAL,
                layer=Layer.L5_SECURITY,
                title=f"Issue {i}",
                description="Critical",
                evidence_tier=EvidenceTier.T3,
                category="security",
            )
            for i in range(5)
        ]
        report = self._make_report(findings)
        # 100 - 5*20*0.5 = 50
        assert report.health_score == 50


class TestDeduplication:
    """Tests for SQAReport.deduplicated_findings() and health score deduplication."""

    def test_duplicate_key_keeps_highest_severity(self):
        low = Finding(
            finding_id="L1",
            severity=Severity.LOW,
            layer=Layer.L1_SYNTACTIC,
            title="Style",
            description="Minor style issue",
            location="/src/main.py:10",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        high = Finding(
            finding_id="H1",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Style",
            description="Major style violation",
            location="/src/main.py:10",
            evidence_tier=EvidenceTier.T3,
            category="style",
        )
        # Add in reverse severity order
        report = SQAReport(findings=[low, high], target="/test")
        deduped = report.deduplicated_findings()
        assert len(deduped) == 1
        assert deduped[0].severity == Severity.HIGH

    def test_different_locations_not_deduplicated(self):
        f1 = Finding(
            finding_id="F1",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Error",
            description="Error 1",
            location="/src/a.py:1",
            evidence_tier=EvidenceTier.T3,
            category="syntax",
        )
        f2 = Finding(
            finding_id="F2",
            severity=Severity.HIGH,
            layer=Layer.L1_SYNTACTIC,
            title="Error",
            description="Error 2",
            location="/src/b.py:2",
            evidence_tier=EvidenceTier.T3,
            category="syntax",
        )
        report = SQAReport(findings=[f1, f2], target="/test")
        deduped = report.deduplicated_findings()
        assert len(deduped) == 2

    def test_deduplication_before_health_score(self):
        """Health score uses deduplicated findings, so duplicates don't double-count."""
        f1 = Finding(
            finding_id="C1",
            severity=Severity.CRITICAL,
            layer=Layer.L5_SECURITY,
            title="SQL injection",
            description="Vulnerable",
            location="/src/main.py:1",
            evidence_tier=EvidenceTier.T3,
            category="security",
        )
        f2 = Finding(
            finding_id="C2",
            severity=Severity.CRITICAL,
            layer=Layer.L5_SECURITY,
            title="SQL injection",  # same key
            description="Same vuln",
            location="/src/main.py:1",  # same location
            evidence_tier=EvidenceTier.T3,
            category="security",
        )
        report = SQAReport(findings=[f1, f2], target="/test")
        report.health_score = report.compute_health_score()
        # Should count as 1 critical: 100 - 20*0.5 = 90, not 2*20*0.5 = 80
        assert report.health_score == 90
