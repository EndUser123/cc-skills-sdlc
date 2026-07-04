"""Tests for delegation_policy: role / authority / freshness (goal req. 1-7).

Layer map:
  - unit (these tests): pure policy logic over the rewritten prompt + derived
    tier/risk. Proves role selection, mutation authority, and the freshness
    contract without spawning agents or crossing process boundaries.
  - what a unit layer cannot prove: that a real subagent/agy/pi process honors
    the mutation scope. That is a runtime/harness contract, out of scope here;
    the policy only *assigns* the role and *states* the authority.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import (  # noqa: E402
    derive_delegation_policy,
    prompt_hash,
    assert_advisory_fresh,
    generate_proposal,
    detect_risk_signals,
)


# ---------------------------------------------------------------------------
# Goal test 1: context-protection-only prefers claude_subagent over pi_ccr
# ---------------------------------------------------------------------------

class TestContextProtectionPrefersSubagent:
    def test_full_go_no_diversity_uses_subagent_worker(self):
        # implement + full_go + no high-risk + no model-diversity marker
        pol = derive_delegation_policy(
            "fix the bug in the auth flow", "implement", "full_go",
            {"high_risk": False}, "pi")
        assert pol["worker"] == "claude_subagent"
        assert pol["advisory_reviewer"] == "claude_subagent"
        assert pol["prefer_claude_subagent_over_pi_ccr"] is True

    def test_via_generate_proposal_not_pi_ccr(self):
        p = generate_proposal("fix the bug in the auth flow", "r", "t")
        assert p["execution_tier"] == "full_go"
        assert p["delegation_policy"]["worker"] == "claude_subagent"
        # pi_ccr is NOT the worker when only context protection is needed.
        assert p["delegation_policy"]["worker"] != "pi_ccr"


# ---------------------------------------------------------------------------
# Goal test 2: high-risk prompt can require agy or claude_subagent review
# ---------------------------------------------------------------------------

class TestHighRiskRequiresReview:
    def test_high_risk_sets_required_review(self):
        risk = detect_risk_signals("modify the pretooluse gate to block")
        pol = derive_delegation_policy(
            "modify the pretooluse gate to block", "implement",
            "pause_for_authorization", risk, "pi")
        assert pol["required_review"] is True
        assert pol["advisory_reviewer"] in ("agy", "claude_subagent")

    def test_decide_intent_uses_agy_advisory(self):
        # decide intent => adversarial outside-model reviewer
        pol = derive_delegation_policy(
            "should we adopt option A or B", "decide",
            "pause_for_authorization", {"high_risk": False}, "pi")
        assert pol["advisory_reviewer"] == "agy"
        assert pol["advisory_fallback"] == "claude_subagent"

    def test_high_risk_blocking_at_pause(self):
        risk = {"high_risk": True}
        pol = derive_delegation_policy(
            "change the hook", "implement", "pause_for_authorization", risk, "pi")
        assert pol["blocking"] is True


# ---------------------------------------------------------------------------
# Goal test 3: advisory artifact with stale prompt_hash is rejected
# ---------------------------------------------------------------------------

class TestAdvisoryFreshness:
    def test_matching_run_and_hash_passes(self):
        ph = prompt_hash("the prompt")
        artifact = {"run_id": "r1", "prompt_hash": ph, "diff_hash": None}
        assert_advisory_fresh(artifact, "r1", ph)  # no raise

    def test_stale_prompt_hash_raises(self):
        artifact = {"run_id": "r1", "prompt_hash": "old", "diff_hash": None}
        with pytest.raises(ValueError, match="prompt_hash"):
            assert_advisory_fresh(artifact, "r1", "new")

    def test_stale_run_id_raises(self):
        artifact = {"run_id": "old", "prompt_hash": prompt_hash("p")}
        with pytest.raises(ValueError, match="run_id"):
            assert_advisory_fresh(artifact, "new", artifact["prompt_hash"])

    def test_diff_review_requires_diff_hash(self):
        ph = prompt_hash("p")
        artifact = {"run_id": "r1", "prompt_hash": ph, "diff_hash": "d1"}
        # Caller passes a diff_hash expectation; mismatch raises.
        with pytest.raises(ValueError, match="diff_hash"):
            assert_advisory_fresh(artifact, "r1", ph, diff_hash="d2")
        # Matching diff_hash passes.
        assert_advisory_fresh(artifact, "r1", ph, diff_hash="d1")


# ---------------------------------------------------------------------------
# Goal test 4: advisory output is reported as evidence, not authority
# ---------------------------------------------------------------------------

class TestAdvisoryIsEvidenceNotAuthority:
    def test_flag_is_always_true(self):
        for intent, tier in [("implement", "full_go"), ("decide", "pause_for_authorization"),
                             ("investigate", "local_surgical")]:
            pol = derive_delegation_policy(
                "x", intent, tier, {"high_risk": False}, "pi")
            assert pol["advisory_is_evidence_not_authority"] is True

    def test_final_authority_is_evidence_gates(self):
        pol = derive_delegation_policy("x", "implement", "full_go",
                                       {"high_risk": False}, "pi")
        assert "evidence gates" in pol["final_authority"]
        assert pol["final_authority"] != pol["roles"]["advisory_reviewer"]


# ---------------------------------------------------------------------------
# Goal test 5: PI/CCR mutation allowed only in isolated full_go path
# ---------------------------------------------------------------------------

class TestPiCcrMutationIsolated:
    def test_pi_ccr_worker_only_at_full_go_with_diversity(self):
        # model-diversity marker at full_go -> pi_ccr worker
        pol = derive_delegation_policy(
            "cross-model second opinion via worktree failover", "implement",
            "full_go", {"high_risk": False}, "pi")
        assert pol["worker"] == "pi_ccr"

    def test_pi_ccr_never_worker_at_local_surgical(self):
        pol = derive_delegation_policy(
            "fix typo", "implement", "local_surgical", {"high_risk": False}, "local")
        assert pol["worker"] != "pi_ccr"

    def test_pi_ccr_mutation_authority_is_isolated(self):
        pol = derive_delegation_policy("x", "implement", "full_go",
                                       {"high_risk": False}, "pi")
        auth = pol["mutation_authority"]["pi_ccr"].lower()
        assert "isolated" in auth and "full_go" in auth

    def test_no_worker_at_pause(self):
        # pause_for_authorization has no worker until authorized.
        pol = derive_delegation_policy(
            "decide thing", "decide", "pause_for_authorization",
            {"high_risk": False}, "pi")
        assert pol["worker"] is None


# ---------------------------------------------------------------------------
# Smoke: full proposal carries delegation_policy + prompt_hash freshness
# ---------------------------------------------------------------------------

def test_smoke_proposal_carries_delegation_policy():
    p = generate_proposal("fix the bug in the auth flow", "run-d", "tid-d")
    dp = p["delegation_policy"]
    assert dp["worker"] in ("claude_main", "claude_subagent", "local_fast", "agy",
                            "pi_ccr", None)
    assert dp["advisory_reviewer"] in ("claude_main", "claude_subagent", "local_fast",
                                       "agy", "pi_ccr")
    assert set(dp["mutation_authority"]) == {
        "claude_main", "claude_subagent", "local_fast", "agy", "pi_ccr"}
    # freshness carries a non-empty prompt_hash linked to the proposal.
    assert p["freshness"]["prompt_hash"] == dp["freshness"]["prompt_hash"]
    assert len(p["freshness"]["prompt_hash"]) > 0
