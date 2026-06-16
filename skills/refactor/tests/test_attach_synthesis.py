"""Tests for the synthesis wire-in in refactor_plan.py.

Covers the _attach_synthesis() helper that bridges priority-based findings
(P0/P1/P2/P3) to severity-based synthesis (CRITICAL/HIGH/MEDIUM/LOW).
"""

import pytest

from scripts.refactor_plan import (
    _attach_synthesis,
    _PRIORITY_TO_SEVERITY,
    _SYNTHESIS_AVAILABLE,
    create_refactor_plan,
)


@pytest.mark.skipif(not _SYNTHESIS_AVAILABLE, reason="synthesize_findings module unavailable")
class TestPriorityToSeverityMapping:
    """The constant must map each priority to its canonical severity."""

    def test_p0_maps_to_critical(self):
        assert _PRIORITY_TO_SEVERITY["P0"] == "CRITICAL"

    def test_p1_maps_to_high(self):
        assert _PRIORITY_TO_SEVERITY["P1"] == "HIGH"

    def test_p2_maps_to_medium(self):
        assert _PRIORITY_TO_SEVERITY["P2"] == "MEDIUM"

    def test_p3_maps_to_low(self):
        assert _PRIORITY_TO_SEVERITY["P3"] == "LOW"

    def test_all_priorities_covered(self):
        # If a new priority is added (e.g. "P-1"), the constant must include it.
        assert set(_PRIORITY_TO_SEVERITY.keys()) == {"P0", "P1", "P2", "P3"}


@pytest.mark.skipif(not _SYNTHESIS_AVAILABLE, reason="synthesize_findings module unavailable")
class TestAttachSynthesis:
    """The _attach_synthesis helper produces consistent block shape."""

    def test_attach_returns_required_keys(self):
        findings = [{"priority": "P0"}, {"priority": "P1"}]
        syn = _attach_synthesis(findings)
        assert "module_available" in syn
        assert "health_score" in syn
        assert "severity_counts" in syn
        assert syn["module_available"] is True

    def test_attach_counts_severities_correctly(self):
        findings = [
            {"priority": "P0"},
            {"priority": "P0"},
            {"priority": "P1"},
            {"priority": "P2"},
            {"priority": "P3"},
        ]
        syn = _attach_synthesis(findings)
        assert syn["severity_counts"] == {
            "CRITICAL": 2,
            "HIGH": 1,
            "MEDIUM": 1,
            "LOW": 1,
        }

    def test_attach_unknown_priority_defaults_to_low(self):
        findings = [{"priority": "P99"}, {"priority": "INVALID"}]
        syn = _attach_synthesis(findings)
        # Both unknown priorities fall through to LOW per the .get(..., "LOW") default
        assert syn["severity_counts"]["LOW"] == 2
        assert syn["severity_counts"]["CRITICAL"] == 0

    def test_attach_health_score_clamped(self):
        # 5 CRITICAL findings = 100 - 100 = 0 (clamped, not negative)
        findings = [{"priority": "P0"} for _ in range(5)]
        syn = _attach_synthesis(findings)
        assert syn["health_score"] == 0

    def test_attach_empty_findings_yields_perfect_score(self):
        syn = _attach_synthesis([])
        assert syn["health_score"] == 100
        assert syn["severity_counts"] == {
            "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0
        }


@pytest.mark.skipif(not _SYNTHESIS_AVAILABLE, reason="synthesize_findings module unavailable")
class TestCreateRefactorPlanIntegration:
    """End-to-end: create_refactor_plan() must include the synthesis block."""

    def test_plan_overview_contains_synthesis(self):
        findings = [
            {"id": "A", "priority": "P0", "title": "Bug", "file": "x.py",
             "description": "bug", "type": "race_condition"},
            {"id": "B", "priority": "P2", "title": "DRY", "file": "y.py",
             "description": "dry", "type": "duplication_removal"},
        ]
        plan = create_refactor_plan(findings, "test/", "sess-1")
        assert "synthesis" in plan["overview"]
        syn = plan["overview"]["synthesis"]
        assert syn["module_available"] is True
        assert syn["severity_counts"]["CRITICAL"] == 1
        assert syn["severity_counts"]["MEDIUM"] == 1
        # Health Score = 100 - 20 - 5 = 75
        assert syn["health_score"] == 75
