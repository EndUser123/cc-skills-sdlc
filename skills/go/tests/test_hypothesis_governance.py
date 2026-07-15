"""Tests for hypothesis governance layer — lifecycle, dedup, aging, candidate bridge.

Covers:
- Lifecycle: GENERATED -> UNDER_REVIEW -> ACCEPTED/REJECTED/STALE
- Deduplication: same pattern groups, evidence preserved, counts correct
- Aging: stale detection, last_observed updates
- Safety: hypotheses cannot affect /go, completion, discovery, or routing
"""

from __future__ import annotations
import json
from pathlib import Path

import hypothesis_generator as hg
import hypothesis_governance as gov


def _make_hyp(run_id: str, htype: str = "possible_discovery_gap",
              fingerprint: str = "abc123", finding_count: int = 0,
              confidence: float = 0.7) -> dict:
    outcome = {
        "lifecycle_status": "completed", "qa_verdict": "redo",
        "completion_verdict": "", "completion_blocking_gaps": [],
        "falsification_result": "",
    }
    dr = {
        "artifact_path": "", "surface_fingerprint": fingerprint,
        "finding_count": finding_count, "structural_issue_count": 0,
        "task_intent": "investigate", "evidence_retrieved": False,
    }
    entry = {
        "run_id": run_id, "session_id": "s1", "repository": "test/repo",
        "revision": "abc", "discovery_reference": dr,
        "outcome_reference": outcome,
        "provenance": {"writers": ["run-record.json"]},
    }
    results = hg.generate([entry])
    if not results:
        return {}
    # Filter to requested type if possible
    for r in results:
        ot = r.get("observation", {}).get("type", "")
        if ot == htype:
            return r
    return results[0]


# -- lifecycle ----------------------------------------------------------------


class TestLifecycle:
    def test_set_status_valid(self):
        h = _make_hyp("r1")
        gov.set_status(h, "UNDER_REVIEW", reason="reviewing")
        assert h["status"] == "UNDER_REVIEW"
        assert len(h["status_history"]) == 2  # initial GENERATED + this

    def test_set_status_rejected(self):
        h = _make_hyp("r1")
        gov.set_status(h, "REJECTED", reason="false positive")
        assert h["status"] == "REJECTED"

    def test_set_status_invalid_raises(self):
        import pytest
        h = _make_hyp("r1")
        with pytest.raises(ValueError, match="Invalid status"):
            gov.set_status(h, "IMPLEMENTED")

    def test_set_status_accepted(self):
        h = _make_hyp("r1")
        gov.set_status(h, "ACCEPTED", reason="director approved")
        assert h["status"] == "ACCEPTED"

    def test_set_status_duplicate(self):
        h = _make_hyp("r1")
        gov.set_status(h, "DUPLICATE", reason="already tracked in IC-GO-hyp-...")
        assert h["status"] == "DUPLICATE"

    def test_get_by_status(self):
        h1 = _make_hyp("r1")
        h2 = _make_hyp("r2")
        h3 = _make_hyp("r3")
        gov.set_status(h2, "UNDER_REVIEW")
        result = gov.get_by_status([h1, h2, h3], "GENERATED")
        assert len(result) >= 2
        for r in result:
            assert r["status"] == "GENERATED"

    def test_status_history_append_only(self):
        h = _make_hyp("r1")
        gov.set_status(h, "UNDER_REVIEW")
        gov.set_status(h, "ACCEPTED")
        gov.set_status(h, "STALE")
        assert len(h["status_history"]) == 4  # GENERATED + 3 transitions
        assert h["status_history"][-1]["status"] == "STALE"

    def test_all_allowed_statuses(self):
        import pytest
        h = _make_hyp("r1")
        for s in sorted(gov.ALLOWED_STATUSES):
            gov.set_status(h, s)
            assert h["status"] == s
        # IMPLEMENTED should fail
        with pytest.raises(ValueError):
            gov.set_status(h, "IMPLEMENTED")


# -- deduplication ------------------------------------------------------------


class TestDeduplication:
    def test_dedup_same_fingerprint_and_type(self):
        h1 = _make_hyp("r1", htype="possible_discovery_gap", fingerprint="abc")
        h2 = _make_hyp("r2", htype="possible_discovery_gap", fingerprint="abc")
        deduped = gov.deduplicate([h1, h2])
        # Should merge into one group
        assert len(deduped) <= len([h1, h2])
        # observation_count should reflect both
        assert deduped[0].get("observation_count", 0) >= 2

    def test_dedup_preserves_all_runs(self):
        h1 = _make_hyp("r1", fingerprint="abc")
        h2 = _make_hyp("r2", fingerprint="abc")
        deduped = gov.deduplicate([h1, h2])
        runs = deduped[0].get("evidence", {}).get("runs", [])
        run_ids = {r.get("run_id") for r in runs}
        assert "r1" in run_ids
        assert "r2" in run_ids

    def test_dedup_different_fingerprints_separate(self):
        h1 = _make_hyp("r1", fingerprint="abc")
        h2 = _make_hyp("r2", fingerprint="xyz")
        deduped = gov.deduplicate([h1, h2])
        # Different fingerprints -> at least 2 groups
        assert len(deduped) >= 2

    def test_dedup_preserves_first_seen(self):
        h1 = _make_hyp("r1", fingerprint="abc")
        h2 = _make_hyp("r2", fingerprint="abc")
        deduped = gov.deduplicate([h1, h2])
        merged = deduped[0]
        assert merged.get("generated_at") == h1.get("generated_at")

    def test_dedup_empty(self):
        assert gov.deduplicate([]) == []

    def test_dedup_counts_correct(self):
        h1 = _make_hyp("r1", fingerprint="abc")
        h2 = _make_hyp("r2", fingerprint="abc")
        h3 = _make_hyp("r3", fingerprint="abc")
        deduped = gov.deduplicate([h1, h2, h3])
        # Should merge 3 into 1
        assert len(deduped) == 1
        assert deduped[0].get("observation_count", 0) == 3


# -- aging / staleness --------------------------------------------------------


class TestAging:
    def test_get_stale_returns_old_hypotheses(self):
        h = _make_hyp("r1")
        # Zero-day threshold: anything older than 0 days is stale
        stale = gov.get_stale([h], max_age_days=0)
        assert len(stale) >= 1

    def test_get_stale_skips_accepted(self):
        h = _make_hyp("r1")
        gov.set_status(h, "ACCEPTED")
        # Even with 0-day threshold, ACCEPTED should not be stale
        stale = gov.get_stale([h], max_age_days=0)
        assert h not in stale

    def test_age_hypotheses_marks_stale(self):
        h = _make_hyp("r1")
        gov.age_hypotheses([h], max_age_days=0)
        assert h["status"] == "STALE"
        assert len(h["status_history"]) >= 2

    def test_age_hypotheses_skips_accepted(self):
        h = _make_hyp("r1")
        gov.set_status(h, "ACCEPTED")
        gov.age_hypotheses([h], max_age_days=0)
        assert h["status"] == "ACCEPTED"  # unchanged

    def test_get_stale_readonly_no_mutation(self):
        h = _make_hyp("r1")
        _ = gov.get_stale([h], max_age_days=0)
        # Original status should be GENERATED, not STALE
        assert h["status"] == "GENERATED"


# -- candidate bridge ---------------------------------------------------------


class TestCandidateBridge:
    def test_promote_to_candidate_returns_ic_schema(self):
        h = _make_hyp("r1", htype="possible_discovery_gap")
        cand = gov.promote_to_candidate(h)
        assert cand["candidate_id"].startswith("IC-GO-")
        assert cand["source_skill"] == "go"
        assert isinstance(cand["evidence"], list)
        assert len(cand["evidence"]) >= 1

    def test_accepted_gets_accepted_for_backlog(self):
        h = _make_hyp("r1")
        gov.set_status(h, "ACCEPTED")
        cand = gov.promote_to_candidate(h)
        assert cand["review_status"] == "accepted_for_backlog"

    def test_rejected_gets_rejected_status(self):
        h = _make_hyp("r1")
        gov.set_status(h, "REJECTED")
        cand = gov.promote_to_candidate(h)
        assert cand["review_status"] == "rejected"

    def test_generated_gets_proposed_status(self):
        h = _make_hyp("r1")
        cand = gov.promote_to_candidate(h)
        assert cand["review_status"] == "proposed"

    def test_candidate_has_falsification_condition(self):
        h = _make_hyp("r1")
        cand = gov.promote_to_candidate(h)
        assert cand["falsification_condition"]
        assert "counter-evidence" in cand["falsification_condition"].lower()

    def test_candidate_has_hypothesis_provenance(self):
        h = _make_hyp("r1")
        cand = gov.promote_to_candidate(h)
        assert "_hypothesis_provenance" in cand
        assert cand["_hypothesis_provenance"]["hypothesis_id"]


# -- safety / authority -------------------------------------------------------


class TestAuthority:
    def test_hypothesis_contains_no_authority_fields(self):
        h = _make_hyp("r1")
        json_str = json.dumps(h)
        assert "block" not in json_str.lower()
        assert "modify" not in json_str.lower()
        assert "authorize" not in json_str.lower()

    def test_status_is_generated_not_promoted(self):
        h = _make_hyp("r1")
        assert h["status"] in gov.ALLOWED_STATUSES
        assert h["status"] == "GENERATED"

    def test_governance_functions_cannot_affect_go(self):
        # Verify no gov function returns a verdict, action, or instruction
        h = _make_hyp("r1")
        # set_status just returns the dict
        result = gov.set_status(h.copy(), "UNDER_REVIEW")
        assert not any(k in str(result) for k in ["BLOCK", "MODIFY", "AUTHORIZE"])

    def test_promote_to_candidate_has_no_authority(self):
        h = _make_hyp("r1")
        cand = gov.promote_to_candidate(h)
        ic_str = json.dumps(cand)
        # Candidate must not contain action directives
        assert "must" not in ic_str.lower()

    def test_deduplicate_does_not_promote(self):
        h1 = _make_hyp("r1", fingerprint="abc")
        h2 = _make_hyp("r2", fingerprint="abc")
        deduped = gov.deduplicate([h1, h2])
        for d in deduped:
            assert d.get("status") == "GENERATED"
            assert d.get("status") != "PROMOTED"
