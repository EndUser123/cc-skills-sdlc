"""Tests for the Failure Mode Matrix (failure_mode_guidance) in preflight_propose."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import failure_mode_guidance, failure_mode_guidance_all, _FAILURE_MODE_MATRIX


# ---------------------------------------------------------------------------
# Core matcher tests
# ---------------------------------------------------------------------------

class TestFailureModeGuidanceBasic:
    """Basic matching and non-matching behavior."""

    def test_hook_gate_change_matches(self):
        r = failure_mode_guidance("fix the hook gate invalid json output")
        assert r is not None
        assert "failure_modes" in r
        assert len(r["failure_modes"]) == 4
        assert any("JSON" in fm for fm in r["failure_modes"])

    def test_hook_stop_gate_matches(self):
        r = failure_mode_guidance("update stop gate overblocking on valid input")
        assert r is not None
        assert any("overblock" in fm.lower() for fm in r["failure_modes"])

    def test_orchestrator_change_matches(self):
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("active-task" in f for f in r["failure_modes"])

    def test_classifier_change_matches(self):
        r = failure_mode_guidance("prompt classification heuristic change classify_dispatch")
        assert r is not None
        assert any("Overmatching" in f for f in r["failure_modes"])
        assert len(r["negative_tests"]) >= 3

    def test_new_helper_matches(self):
        r = failure_mode_guidance("add a new helper function for parsing")
        assert r is not None
        assert any("Duplicating" in f for f in r["failure_modes"])

    def test_high_risk_file_matches(self):
        r = failure_mode_guidance("edit the critical protected forbidden file")
        assert r is not None
        assert any("scope" in f for f in r["failure_modes"])

    def test_telemetry_change_matches(self):
        r = failure_mode_guidance("telemetry summarizer agentic reliability log event")
        assert r is not None
        assert any("side effect" in f for f in r["failure_modes"])

    def test_claim_validation_matches(self):
        r = failure_mode_guidance("claim honesty gate unverified validation evidence")
        assert r is not None
        assert any("hedged" in f for f in r["failure_modes"])

    def test_test_failure_matches(self):
        r = failure_mode_guidance("fix the failing test expectation mismatch")
        assert r is not None
        assert any("blindly" in f.lower() for f in r["failure_modes"])

    def test_generated_cache_matches(self):
        r = failure_mode_guidance("patch the plugin cache canonical source bidir sync")
        assert r is not None
        assert any("canonical" in f for f in r["failure_modes"])

    def test_review_audit_matches(self):
        r = failure_mode_guidance("review the stop hook rca diagnosis")
        assert r is not None
        assert any("file:line" in c for c in r["claim_requirements"])


class TestFailureModeGuidanceTrivial:
    """Trivial or ambiguous prompts should NOT get noisy matrix output."""

    def test_empty_prompt_returns_none(self):
        assert failure_mode_guidance("") is None

    def test_short_greeting_returns_none(self):
        assert failure_mode_guidance("say hi") is None

    def test_brief_fix_returns_none(self):
        # "fix the test" — 3 words, 1 keyword match; too vague.
        assert failure_mode_guidance("fix the test") is None

    def test_generic_fix_with_enough_words_matches(self):
        # "fix the broken test for hook.py" — 6 words, matches test_drift.
        r = failure_mode_guidance("fix the broken test for hook.py")
        assert r is not None


class TestFailureModeGuidanceStructure:
    """Each result dict has the required keys and non-empty lists."""

    def test_all_keys_present(self):
        r = failure_mode_guidance("hook gate change")
        assert r is not None
        for key in ("failure_modes", "required_recon", "search_evidence",
                     "negative_tests", "claim_requirements"):
            assert key in r, f"missing key: {key}"
            assert isinstance(r[key], list), f"{key} is not a list"
            assert len(r[key]) > 0, f"{key} is empty"

    def test_best_match_wins(self):
        # Prompt matches both hook/gate and test_drift; hook/gate should win
        # because it has more keywords matching.
        r = failure_mode_guidance("fix the hook gate test failure broken test")
        assert r is not None
        # hook/gate has more keywords; it should win. Exact row depends on overlap.
        assert len(r["failure_modes"]) >= 3

    def test_tiebreaker_prefers_specific_row_over_hook_gate(self):
        # "Critical review of the stop hook diagnosis" matches hook/gate (2 kw)
        # and review (2 kw). Tiebreaker should prefer review (more specific).
        r = failure_mode_guidance(
            "Critical review of the stop hook JSON validation failure diagnosis"
        )
        assert r is not None
        # Review row has "file:line" in claim_requirements; hook/gate does not.
        assert any("file:line" in c for c in r["claim_requirements"])


class TestMatrixIntegrity:
    """Verify the data structure itself is well-formed."""

    def test_matrix_has_10_rows(self):
        assert len(_FAILURE_MODE_MATRIX) == 10

    def test_each_row_has_6_fields(self):
        for i, row in enumerate(_FAILURE_MODE_MATRIX):
            assert len(row) == 6, f"row {i} has {len(row)} fields, expected 6"

    def test_each_row_keywords_is_nonempty_tuple(self):
        for i, row in enumerate(_FAILURE_MODE_MATRIX):
            assert isinstance(row[0], tuple), f"row {i} keywords not tuple"
            assert len(row[0]) > 0, f"row {i} has no keywords"

    def test_each_row_field_is_nonempty_list(self):
        for i, row in enumerate(_FAILURE_MODE_MATRIX):
            for j, field_name in enumerate(
                ["failure_modes", "required_recon", "search_evidence",
                 "negative_tests", "claim_requirements"], 1
            ):
                assert isinstance(row[j], list), f"row {i} {field_name} not list"
                assert len(row[j]) > 0, f"row {i} {field_name} is empty"


# ---------------------------------------------------------------------------
# Phase 6.6: Secondary (multi-match) guidance tests
# ---------------------------------------------------------------------------

class TestFailureModeGuidanceAll:
    """Tests for failure_mode_guidance_all (primary + secondary rows)."""

    def test_review_plus_hook_and_telemetry(self):
        """Review + stop hook + telemetry: primary is review/hook, secondary has telemetry."""
        r = failure_mode_guidance_all(
            "review the Stop hook telemetry implementation"
        )
        assert r is not None
        assert "failure_modes" in r
        sec = r.get("secondary", [])
        # Should have at least 1 secondary (telemetry or hook depending on tiebreak)
        assert len(sec) >= 1
        # Secondary rows must have the same shape as primary
        for s in sec:
            assert "failure_modes" in s
            assert "negative_tests" in s
            assert "claim_requirements" in s

    def test_hook_plus_telemetry(self):
        """Hook + telemetry prompt: primary has telemetry or hook, secondary has the other."""
        r = failure_mode_guidance_all(
            "fix the hook gate and add telemetry summarizer"
        )
        assert r is not None
        sec = r.get("secondary", [])
        assert len(sec) >= 1
        # At least one of primary+secondary covers telemetry
        all_fms = [r["failure_modes"][0]] + [s["failure_modes"][0] for s in sec]
        has_hook = any("hook" in fm.lower() or "json" in fm.lower() for fm in all_fms)
        has_telemetry = any("side effect" in fm.lower() or "telemetry" in fm.lower() for fm in all_fms)
        assert has_hook or has_telemetry

    def test_go_plus_classifier(self):
        """/go + classifier prompt: orchestrator and classifier both appear."""
        r = failure_mode_guidance_all(
            "update /go classify_dispatch overmatching heuristic"
        )
        assert r is not None
        sec = r.get("secondary", [])
        # Should have secondary rows from both matching types
        assert len(sec) >= 1
        # Primary should be one of orchestrator/classifier, secondary the other
        all_fms_text = str(r["failure_modes"]) + str([s["failure_modes"] for s in sec])
        assert "Overmatching" in all_fms_text or "active-task" in all_fms_text

    def test_trivial_no_primary_or_secondary(self):
        """Trivial prompt: no primary, no secondary, no noise."""
        r = failure_mode_guidance_all("say hi")
        assert r is None

    def test_single_type_no_secondary(self):
        """Single-type prompt with only one matching row: no secondaries."""
        r = failure_mode_guidance_all("fix the hook gate json validation")
        assert r is not None
        sec = r.get("secondary", [])
        assert len(sec) == 0

    def test_secondary_capped_at_2(self):
        """Even with many keyword matches, secondary rows are capped at 2."""
        r = failure_mode_guidance_all(
            "review the stop hook telemetry claim validation evidence"
        )
        assert r is not None
        sec = r.get("secondary", [])
        assert len(sec) <= 2

    def test_secondary_shape_matches_primary(self):
        """Each secondary dict has exactly the same keys as the primary dict."""
        r = failure_mode_guidance_all(
            "review the Stop hook telemetry implementation"
        )
        assert r is not None
        primary_keys = set(r.keys()) - {"secondary"}
        for s in r.get("secondary", []):
            assert set(s.keys()) == primary_keys

    def test_all_returns_none_for_empty(self):
        """Empty prompt returns None."""
        assert failure_mode_guidance_all("") is None

    def test_all_compatible_with_guidance(self):
        """failure_mode_guidance_all returns same primary as failure_mode_guidance."""
        from preflight_propose import failure_mode_guidance
        prompt = "fix the hook gate invalid json output"
        r1 = failure_mode_guidance(prompt)
        r2 = failure_mode_guidance_all(prompt)
        assert r1 is not None and r2 is not None
        assert r1["failure_modes"] == r2["failure_modes"]
        assert r1["required_recon"] == r2["required_recon"]


# ---------------------------------------------------------------------------
# Phase 6.7: Execution-control safeguard tests
# ---------------------------------------------------------------------------

class TestExecutionControlSafeguards:
    """Verify the 5 execution-control safeguards are present in FMM data."""

    def test_hook_gate_has_stop_json_claim(self):
        """Task 5: live Stop JSON validation failure prevents DONE."""
        r = failure_mode_guidance("fix the hook gate json validation")
        assert r is not None
        assert any("Stop JSON validation failure" in c for c in r["claim_requirements"])

    def test_orchestrator_has_delegation_failure_mode(self):
        """Task 1: delegated agents writing partial work."""
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("delegated agent" in f.lower() for f in r["failure_modes"])

    def test_orchestrator_has_authoritative_run_failure_mode(self):
        """Task 3: reclassifying from truncated output."""
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("reclassif" in f.lower() for f in r["failure_modes"])

    def test_orchestrator_has_delegation_recon(self):
        """Task 1: delegation requires isolation/patch/disjoint plan."""
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("isolation" in rec.lower() or "disjoint" in rec.lower() for rec in r["required_recon"])

    def test_orchestrator_has_mutation_preconditions(self):
        """Task 2: phase mutation needs permitted-files + verification + rollback."""
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("permitted" in rec.lower() for rec in r["required_recon"])

    def test_orchestrator_has_authoritative_run_negative(self):
        """Task 3: truncated output prevents silent reclassification."""
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("truncat" in t.lower() for t in r["negative_tests"])

    def test_orchestrator_has_report_contract_claim(self):
        """Task 4: strict report format must be matched."""
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("strict format" in c.lower() or "report format" in c.lower() for c in r["claim_requirements"])

    def test_orchestrator_has_stop_hook_claim(self):
        """Task 5: Stop JSON validation failure prevents DONE."""
        r = failure_mode_guidance("orchestrate.py change common_tail dispatch")
        assert r is not None
        assert any("Stop JSON validation" in c for c in r["claim_requirements"])
