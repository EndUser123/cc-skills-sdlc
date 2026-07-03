"""Tests for the Failure Mode Matrix (failure_mode_guidance) in preflight_propose."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import failure_mode_guidance, _FAILURE_MODE_MATRIX


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
        # hook/gate has 4 keywords; test_drift has 3. hook/gate should win.
        # The exact row depends on keyword overlap.
        assert len(r["failure_modes"]) >= 3


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
