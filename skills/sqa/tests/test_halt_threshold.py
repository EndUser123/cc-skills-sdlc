"""Test halt threshold logic in SeverityHaltTracker."""

import pytest

from orchestrator import SeverityHaltTracker, HALT_SEVERITY_ORDER
from findings.models import Finding, Severity, Layer


class TestHaltThresholdLogic:
    """Test that halt threshold is enforced correctly."""

    def test_halt_on_critical_finding(self):
        """Test that CRITICAL findings trigger halt with HIGH threshold."""
        tracker = SeverityHaltTracker(threshold="HIGH")

        critical_finding = Finding(
            finding_id="TEST-001",
            severity=Severity.CRITICAL,
            layer=Layer.L0,
            title="Critical issue",
            description="A critical problem",
        )

        assert tracker.should_halt([critical_finding]) is True

    def test_halt_on_high_finding_with_high_threshold(self):
        """Test that HIGH findings trigger halt with HIGH threshold."""
        tracker = SeverityHaltTracker(threshold="HIGH")

        high_finding = Finding(
            finding_id="TEST-002",
            severity=Severity.HIGH,
            layer=Layer.L0,
            title="High issue",
            description="A high problem",
        )

        assert tracker.should_halt([high_finding]) is True

    def test_no_halt_on_medium_finding_with_high_threshold(self):
        """Test that MEDIUM findings do NOT trigger halt with HIGH threshold."""
        tracker = SeverityHaltTracker(threshold="HIGH")

        medium_finding = Finding(
            finding_id="TEST-003",
            severity=Severity.MEDIUM,
            layer=Layer.L0,
            title="Medium issue",
            description="A medium problem",
        )

        assert tracker.should_halt([medium_finding]) is False

    def test_halt_threshold_none_never_halts(self):
        """Test that NONE threshold never halts regardless of findings."""
        tracker = SeverityHaltTracker(threshold="NONE")

        critical_finding = Finding(
            finding_id="TEST-004",
            severity=Severity.CRITICAL,
            layer=Layer.L0,
            title="Critical issue",
            description="A critical problem",
        )

        assert tracker.should_halt([critical_finding]) is False

    def test_halt_on_medium_finding_with_medium_threshold(self):
        """Test that MEDIUM findings trigger halt with MEDIUM threshold."""
        tracker = SeverityHaltTracker(threshold="MEDIUM")

        medium_finding = Finding(
            finding_id="TEST-005",
            severity=Severity.MEDIUM,
            layer=Layer.L0,
            title="Medium issue",
            description="A medium problem",
        )

        assert tracker.should_halt([medium_finding]) is True

    def test_no_halt_on_low_finding_with_medium_threshold(self):
        """Test that LOW findings do NOT trigger halt with MEDIUM threshold."""
        tracker = SeverityHaltTracker(threshold="MEDIUM")

        low_finding = Finding(
            finding_id="TEST-006",
            severity=Severity.LOW,
            layer=Layer.L0,
            title="Low issue",
            description="A low problem",
        )

        assert tracker.should_halt([low_finding]) is False

    def test_halt_message_generation(self):
        """Test that halt message summarizes findings correctly."""
        tracker = SeverityHaltTracker(threshold="HIGH")

        findings = [
            Finding(
                finding_id=f"TEST-{i:03d}",
                severity=Severity.CRITICAL if i == 0 else Severity.HIGH,
                layer=Layer.L0,
                title=f"Issue {i}",
                description=f"Problem {i}",
            )
            for i in range(3)
        ]

        message = tracker.get_halt_message(findings)
        assert "[HALT]" in message
        assert "CRITICAL: 1 finding(s)" in message
        assert "HIGH: 2 finding(s)" in message

    def test_severity_order_is_correct(self):
        """Test that HALT_SEVERITY_ORDER is correctly defined."""
        assert HALT_SEVERITY_ORDER == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        # Verify index ordering
        assert HALT_SEVERITY_ORDER.index("LOW") < HALT_SEVERITY_ORDER.index("HIGH")
        assert HALT_SEVERITY_ORDER.index("HIGH") < HALT_SEVERITY_ORDER.index("CRITICAL")
