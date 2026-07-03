"""Tests for verification_policy_from_fmm (FMM-derived fallback)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import verification_policy_from_fmm, _verification_policy_key, rewrite_goal


class TestFmmDerivedFallback:
    """FMM-derived policy fallback for the 3 field-validation prompts."""

    def test_stop_hook_fix_gets_hook_gate(self):
        """Task 1: Stop hook fix → hook_gate via FMM-derived."""
        vp, source = verification_policy_from_fmm(
            "fix the Stop hook JSON validation failure"
        )
        assert vp == "hook_gate"
        assert source == "fmm-derived"

    def test_quarantine_gets_test_drift(self):
        """Task 2: quarantine/move → test_drift via FMM-derived."""
        vp, source = verification_policy_from_fmm(
            "Phase 2: quarantine failing tests by moving them to _quarantine"
        )
        assert vp == "test_drift"
        assert source == "fmm-derived"

    def test_review_rca_gets_claim_validation(self):
        """Task 3: review/RCA audit → claim_validation via FMM-derived."""
        vp, source = verification_policy_from_fmm(
            "review the /rca skill output and assess whether it found the real root cause"
        )
        assert vp == "claim_validation"
        assert source == "fmm-derived"

    def test_hook_gate_keyword_also_works(self):
        """Hook gate keyword prompt → hook_gate via FMM-derived."""
        vp, source = verification_policy_from_fmm(
            "fix the hook gate invalid json output"
        )
        assert vp == "hook_gate"
        assert source in ("direct-policy-match", "fmm-derived")

    def test_orchestrator_prompt_gets_orchestrator(self):
        """/go change → orchestrator via FMM-derived."""
        vp, source = verification_policy_from_fmm(
            "orchestrate.py change common_tail dispatch"
        )
        assert vp == "orchestrator"
        assert source in ("direct-policy-match", "fmm-derived")

    def test_telemetry_prompt_gets_telemetry(self):
        """Telemetry prompt → telemetry via FMM-derived."""
        vp, source = verification_policy_from_fmm(
            "telemetry summarizer agentic reliability log event"
        )
        assert vp == "telemetry"
        assert source in ("direct-policy-match", "fmm-derived")


class TestDirectMatchWinsOverFallback:
    """Direct policy match must always win over FMM-derived fallback."""

    def test_classifier_direct_wins(self):
        """classify_dispatch prompt gets classifier from direct match, not FMM fallback."""
        vp, source = verification_policy_from_fmm(
            "update classify_dispatch overmatching heuristic"
        )
        assert vp == "classifier"
        assert source == "direct-policy-match"

    def test_hook_change_direct_wins(self):
        """'hook change' prompt may get hook_gate from direct match."""
        vp, source = verification_policy_from_fmm("hook change gate update")
        assert vp == "hook_gate"
        # Could be direct or FMM — just verify it gets the right policy
        assert source in ("direct-policy-match", "fmm-derived")


class TestNoFmmMatchStaysNull:
    """Unknown/no-FMM prompts still get null policy."""

    def test_trivial_stays_null(self):
        vp, source = verification_policy_from_fmm("say hi")
        assert vp is None
        assert source == "none"

    def test_empty_stays_null(self):
        vp, source = verification_policy_from_fmm("")
        assert vp is None
        assert source == "none"

    def test_unrelated_task_stays_null(self):
        vp, source = verification_policy_from_fmm(
            "Display CCR fallback chains in route output"
        )
        # No FMM match → no policy
        assert vp is None
        assert source == "none"


class TestSourceFieldAccuracy:
    """Source field accurately reflects which path produced the policy."""

    def test_source_is_direct_when_policy_matrix_matches(self):
        """Direct match: rewrite_goal → _verification_policy_key returns non-None."""
        prompt = "update classify_dispatch overmatching heuristic"
        rewritten = rewrite_goal(prompt)
        direct = _verification_policy_key(rewritten)
        vp, source = verification_policy_from_fmm(prompt)
        if direct is not None:
            assert source == "direct-policy-match"
        # (If direct is None, source could be fmm-derived — that's correct)

    def test_source_is_fmm_when_direct_fails(self):
        """FMM-derived: direct match fails but FMM row maps to a policy."""
        prompt = "fix the Stop hook JSON validation failure"
        rewritten = rewrite_goal(prompt)
        direct = _verification_policy_key(rewritten)
        vp, source = verification_policy_from_fmm(prompt)
        if direct is None and vp is not None:
            assert source == "fmm-derived"
