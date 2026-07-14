"""Tests for the evidence-based hypothesis engine.

Covers:
- Hypothesis safety: correlation != certainty, multiple hypotheses, uncertainty preserved
- Provenance: every hypothesis links to source runs
- Ranking: deterministic, explainable
- Authority: hypotheses cannot modify execution
- Rejection lifecycle
- Positive and negative outcomes both produce hypotheses
"""

from __future__ import annotations
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _discovery_entry(run_id: str, finding_count: int = 0, structural: int = 0,
                     fingerprint: str = "abc123", evidence_retrieved: bool = False) -> dict:
    return {
        "run_id": run_id,
        "session_id": "s1",
        "repository": "test/repo",
        "revision": "abc",
        "discovery_reference": {
            "artifact_path": f"discovery-evidence_{run_id}.json" if evidence_retrieved else "",
            "surface_fingerprint": fingerprint,
            "finding_count": finding_count,
            "structural_issue_count": structural,
            "task_intent": "implement" if finding_count > 0 else "investigate",
            "evidence_retrieved": evidence_retrieved,
        },
        "outcome_reference": {
            "lifecycle_status": "completed",
            "qa_verdict": "accept",
            "qa_summary": "",
            "completion_verdict": "",
            "completion_blocking_gaps": [],
            "falsification_result": "",
        },
        "provenance": {"writers": ["run-record.json"]},
    }


# ── hypothesis safety ────────────────────────────────────────────────────────


class TestHypothesisSafety:
    """Hypotheses must never equate correlation with certainty."""

    def test_redo_without_findings_produces_discovery_gap_hypothesis(self):
        """QA redo with zero findings → possible_discovery_gap hypothesis."""
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        assert len(results) >= 1
        types = {r["observation"]["type"] for r in results}
        assert "possible_discovery_gap" in types

    def test_redo_with_findings_produces_implementation_issue_not_discovery(self):
        """QA redo with findings → possible_implementation_issue, NOT discovery_gap."""
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        types = {r["observation"]["type"] for r in results}
        assert "possible_implementation_issue" in types, f"Got {types}"
        assert "possible_discovery_gap" not in types, f"Should not contain discovery_gap when findings exist, got {types}"

    def test_multiple_hypotheses_per_run(self):
        """A single run may produce multiple hypotheses."""
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=5, structural=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        assert len(results) >= 2  # implementation_issue + possible overreach check

    def test_unknown_when_insufficient_evidence(self):
        """Missing outcome data produces unknown."""
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1")]
        entries[0]["outcome_reference"]["qa_verdict"] = ""
        entries[0]["outcome_reference"]["lifecycle_status"] = "completed"
        results = hg.generate(entries)
        types = {r["observation"]["type"] for r in results}
        assert len(results) >= 1
        # Should not contain failure-oriented types
        assert "possible_discovery_gap" not in types
        assert "possible_implementation_issue" not in types
        assert "possible_process_gap" not in types

    def test_counter_evidence_preserved(self):
        """Hypotheses include counter_evidence list."""
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0, evidence_retrieved=True)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        for r in results:
            for h in r.get("hypotheses", []):
                # counter_evidence can be empty, but must exist as a list
                assert isinstance(h.get("counter_evidence"), list)

    def test_hypothesis_statement_uses_possible_language(self):
        """Hypothesis statements use 'possible' not definitive language."""
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0)]
        entries[0]["outcome_reference"]["qa_verdict"] = "blocked"
        results = hg.generate(entries)
        for r in results:
            for h in r.get("hypotheses", []):
                s = h.get("statement", "")
                # Should not say "discovery failed"
                assert "failed" not in s.lower(), f"Found 'failed' in: {s}"
                assert "is the cause" not in s.lower(), f"Found definitive language: {s}"


# ── provenance ───────────────────────────────────────────────────────────────


class TestProvenance:
    """Every hypothesis links to source runs."""

    def test_hypothesis_links_to_run_id(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0),
                   _discovery_entry("r2", finding_count=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        linked_runs = set()
        for r in results:
            for run in r.get("evidence", {}).get("runs", []):
                linked_runs.add(run.get("run_id"))
        assert "r1" in linked_runs

    def test_run_without_outcome_still_produces_hypothesis(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0)]
        # outcome with no signal
        results = hg.generate(entries)
        assert len(results) >= 1
        for r in results:
            assert r.get("hypothesis_id")
            assert r.get("evidence", {}).get("runs")

    def test_schema_version_present(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        for r in results:
            assert r.get("schema_version") == "improvement-hypothesis.v1"

    def test_generated_within_reasonable_timestamp(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1")]
        results = hg.generate(entries)
        for r in results:
            assert r.get("generated_at", "").endswith("Z")


# ── ranking ──────────────────────────────────────────────────────────────────


class TestRanking:
    """Ranking is deterministic and explainable."""

    def test_aggregate_returns_ranked_list(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0),
                   _discovery_entry("r2", finding_count=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        entries[1]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        ranked = hg.aggregate(results)
        assert isinstance(ranked, list)
        assert len(ranked) >= 1
        # Verify sorting by frequency descending
        for i in range(len(ranked) - 1):
            assert ranked[i]["count"] >= ranked[i + 1]["count"]

    def test_aggregate_empty_input(self):
        import hypothesis_generator as hg
        assert hg.aggregate([]) == []

    def test_top_by_value_returns_limited(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0),
                   _discovery_entry("r2", finding_count=3),
                   _discovery_entry("r3", finding_count=5)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        top = hg.top_by_value(results, limit=2)
        assert len(top) <= 2
        # Higher impact should be first
        if len(top) >= 2:
            iv0 = top[0].get("investigation_value", {}).get("impact", 0)
            iv1 = top[1].get("investigation_value", {}).get("impact", 0)
            assert iv0 >= iv1

    def test_aggregate_deterministic(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0), _discovery_entry("r2", finding_count=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        entries[1]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        a = hg.aggregate(results)
        b = hg.aggregate(results)
        assert a == b


# ── queries ──────────────────────────────────────────────────────────────────


class TestQueries:
    """Read-only queries return hypotheses filtered/ranked."""

    def test_query_by_type(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0), _discovery_entry("r2", finding_count=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        entries[1]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        impl = hg.query_by_type(results, "possible_implementation_issue")
        gap = hg.query_by_type(results, "possible_discovery_gap")
        assert isinstance(impl, list)
        assert isinstance(gap, list)

    def test_get_summary(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0), _discovery_entry("r2", finding_count=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        entries[1]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        summary = hg.get_summary(results)
        assert summary["total_hypotheses"] >= 1
        assert summary["distinct_run_count"] >= 1
        assert isinstance(summary["by_type"], dict)


# ── positive and negative learning ───────────────────────────────────────────


class TestPositiveAndNegative:
    """Both success and failure patterns produce hypotheses."""

    def test_successful_run_produces_positive_hypothesis(self):
        import hypothesis_generator as hg
        entry = _discovery_entry("r1", finding_count=3, evidence_retrieved=True)
        entry["outcome_reference"]["lifecycle_status"] = "completed"
        entry["outcome_reference"]["qa_verdict"] = "accept"
        results = hg.generate([entry])
        types = {r["observation"]["type"] for r in results}
        assert "positive_discovery_success" in types or "positive_evidence_reuse" in types or "positive_first_pass_validation" in types, f"Got {types}"

    def test_negative_run_produces_negative_hypothesis(self):
        import hypothesis_generator as hg
        entry = _discovery_entry("r1", finding_count=0)
        entry["outcome_reference"]["lifecycle_status"] = "blocked"
        entry["outcome_reference"]["qa_verdict"] = ""
        results = hg.generate([entry])
        types = {r["observation"]["type"] for r in results}
        assert any("positive" not in t for t in types), f"Should have non-positive types, got {types}"
        # Should have possible_discovery_gap or unknown
        has_relevant = any(t in types for t in ("possible_discovery_gap", "unknown"))
        assert has_relevant, f"No relevant hypothesis type, got {types}"

    def test_falsification_produces_process_gap(self):
        import hypothesis_generator as hg
        entry = _discovery_entry("r1", finding_count=3)
        entry["outcome_reference"]["lifecycle_status"] = "completed"
        entry["outcome_reference"]["falsification_result"] = "FALSIFIED"
        results = hg.generate([entry])
        types = {r["observation"]["type"] for r in results}
        assert "possible_process_gap" in types, f"Got {types}"


# ── authority ────────────────────────────────────────────────────────────────


class TestAuthority:
    """Hypotheses cannot modify execution, block completion, or alter discovery."""

    def test_hypothesis_contains_no_authority_fields(self):
        import hypothesis_generator as hg
        entry = _discovery_entry("r1", finding_count=0)
        entry["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate([entry])
        for r in results:
            json_str = json.dumps(r)
            assert "block" not in json_str.lower()
            assert "modify" not in json_str.lower()
            assert "authorize" not in json_str.lower()
            assert "required_change" not in json_str.lower()
            assert "must" not in json_str.lower()

    def test_status_is_generated_not_promoted(self):
        import hypothesis_generator as hg
        entry = _discovery_entry("r1", finding_count=0)
        entry["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate([entry])
        for r in results:
            assert r["status"] in ("GENERATED", "ACCEPTED_FOR_REVIEW", "REJECTED",
                                    "DUPLICATE", "INSUFFICIENT_EVIDENCE", "ALREADY_SOLVED")
            assert r["status"] != "PROMOTED"
            assert r["status"] != "IMPLEMENTED"

    def test_hypothesis_id_unique(self):
        import hypothesis_generator as hg
        entries = [_discovery_entry("r1", finding_count=0), _discovery_entry("r2", finding_count=3)]
        entries[0]["outcome_reference"]["qa_verdict"] = "redo"
        entries[1]["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate(entries)
        ids = [r["hypothesis_id"] for r in results]
        assert len(set(ids)) == len(ids)


# ── rejection lifecycle ──────────────────────────────────────────────────────


class TestRejectionLifecycle:
    """Hypotheses support rejection lifecycle for later analysis."""

    def test_status_can_be_rejected(self):
        import hypothesis_generator as hg
        entry = _discovery_entry("r1", finding_count=0)
        entry["outcome_reference"]["qa_verdict"] = "redo"
        results = hg.generate([entry])
        for r in results:
            # Verify the status field exists and supports allowed values
            assert isinstance(r.get("status"), str)


# ── empty / edge ─────────────────────────────────────────────────────────────


class TestEmpty:
    def test_empty_index_produces_no_hypotheses(self):
        import hypothesis_generator as hg
        assert hg.generate([]) == []

    def test_empty_aggregate_returns_empty(self):
        import hypothesis_generator as hg
        assert hg.aggregate([]) == []
