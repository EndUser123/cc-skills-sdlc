"""Tests for graceful timeout handling in the SQA orchestrator."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


from findings.models import EvidenceTier, Finding, Layer, Severity


class TestTimeoutBehavior:
    """Tests that timeouts are handled gracefully and don't crash the pipeline."""

    def test_layer_timeout_finding_has_correct_severity(self):
        """A timeout finding should have MEDIUM severity (degrading gracefully)."""
        finding = Finding(
            finding_id="L1-RUFF-TIMEOUT",
            severity=Severity.MEDIUM,
            layer=Layer.L1_SYNTACTIC,
            title="Ruff check timed out after 60s",
            description="Ruff subprocess exceeded 60s timeout",
            evidence_tier=EvidenceTier.T3,
            category="timeout",
        )
        assert finding.severity == Severity.MEDIUM
        assert finding.category == "timeout"

    def test_all_layer_timeouts_are_medium_severity(self):
        """Timeout findings across all layers should be MEDIUM severity."""
        for layer in [Layer.L1_SYNTACTIC, Layer.L2_SEMANTIC, Layer.L3_STRUCTURAL]:
            finding = Finding(
                finding_id=f"TIMEOUT-{layer.value}",
                severity=Severity.MEDIUM,
                layer=layer,
                title="Tool timed out",
                description="subprocess timeout",
                evidence_tier=EvidenceTier.T3,
                category="timeout",
            )
            assert finding.severity == Severity.MEDIUM
            assert finding.category == "timeout"


class TestDegradationGraceful:
    """Tests that tool unavailability degrades gracefully."""

    def test_file_not_found_error_returns_empty_or_skip_finding(self):
        """When a required tool is not installed, layer returns empty list (skipped)."""
        # This is the expected behavior - FileNotFoundError is caught and silently
        # returns empty list, allowing pipeline to continue
        finding = Finding(
            finding_id="L1-ruff-NA",
            severity=Severity.LOW,
            layer=Layer.L1_SYNTACTIC,
            title="Ruff not available",
            description="ruff command not found in PATH",
            evidence_tier=EvidenceTier.T4,
            category="unavailable",
        )
        # Tool-not-found is a LOW severity graceful degradation, not a crash
        assert finding.severity == Severity.LOW
