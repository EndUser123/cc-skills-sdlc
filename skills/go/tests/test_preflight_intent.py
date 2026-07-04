"""Tests for task_intent / execution_tier / report_gate classification.

Goal: extend /go so intent controls ceremony, rigor, and completion claims.
Layer map:
  - unit (these tests): pure classifier logic over rewritten prompts.
  - integration (TestRunPreflightPrerequisite): filesystem — verifies the
    tracked prerequisite artifact is written when prompt_review_required and
    support is absent. A unit test cannot prove that boundary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import (  # noqa: E402
    classify_intent,
    detect_risk_signals,
    derive_execution_tier,
    build_decision_advisory,
    derive_report_gate,
    assert_fresh,
    generate_proposal,
    run_preflight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tier(intent: str, **kw) -> str:
    """Derive tier with defaults; override via kw for local_eligible etc."""
    defaults = dict(dispatch="pi", local_eligible=False, requires_approval=False,
                    risk={"high_risk": False})
    defaults.update(kw)
    return derive_execution_tier(intent, **defaults)


# ---------------------------------------------------------------------------
# Goal test 1: investigate must NOT enable completion claim
# ---------------------------------------------------------------------------

class TestInvestigateNoCompletionClaim:
    def test_investigate_intent_classified(self):
        assert classify_intent("investigate why the hook double-fires") == "investigate"

    def test_investigate_tier_is_direct_or_local_surgical(self):
        # No local eligibility, no dispatch -> direct_answer
        assert _tier("investigate") == "direct_answer"
        # Local-eligible read-only recon -> local_surgical (never full_go)
        assert _tier("investigate", dispatch="local", local_eligible=True) == "local_surgical"

    def test_investigate_report_gate_blocks_completion(self):
        gate = derive_report_gate("investigate", "direct_answer")
        assert gate["allow_implementation_completion_claim"] is False
        gate2 = derive_report_gate("investigate", "local_surgical")
        assert gate2["allow_implementation_completion_claim"] is False

    def test_investigate_via_generate_proposal_no_completion(self):
        p = generate_proposal("investigate why the parser crashes on None", "r1", "t1")
        assert p["task_intent"] in ("investigate", "mixed")
        assert p["report_gate"]["allow_implementation_completion_claim"] is False


# ---------------------------------------------------------------------------
# Goal test 2: validate/audit/review -> task_intent=validate
# ---------------------------------------------------------------------------

class TestValidateMapping:
    @pytest.mark.parametrize("prompt", [
        "review the diff for correctness",
        "audit the hook gate coverage",
        "validate the migration script",
        "critically review the proposal",
        "field-test the new router",
    ])
    def test_validates(self, prompt):
        intent = classify_intent(prompt)
        # "critically review" could trip decide on "review"? No -- validate owns review/critique.
        assert intent == "validate", f"{prompt!r} -> {intent}"

    def test_validate_no_completion_claim(self):
        assert derive_report_gate("validate", "local_surgical")[
            "allow_implementation_completion_claim"] is False


# ---------------------------------------------------------------------------
# Goal test 3: decide -> advisory + pause
# ---------------------------------------------------------------------------

class TestDecideAdvisoryAndPause:
    def test_decide_pauses(self):
        assert _tier("decide") == "pause_for_authorization"

    def test_decide_advisory_has_required_fields(self):
        adv = build_decision_advisory("should we adopt option A or B", "decide",
                                      "pause_for_authorization")
        for key in ("options", "recommendation", "long_term_roi",
                    "reversibility", "safest_low_regret_action",
                    "exact_authorization_needed"):
            assert key in adv and adv[key], f"missing/empty {key}"
        assert "director" in adv["exact_authorization_needed"].lower()

    def test_decide_via_generate_proposal(self):
        # Pure decide prompt — no implement verb (would make it mixed).
        p = generate_proposal("should we adopt option A or option B", "r2", "t2")
        assert p["task_intent"] == "decide"
        assert p["execution_tier"] == "pause_for_authorization"
        assert p["report_gate"]["allow_implementation_completion_claim"] is False


# ---------------------------------------------------------------------------
# Goal test 4: small implement -> local_surgical + targeted verification required
# ---------------------------------------------------------------------------

class TestSmallImplementLocalSurgical:
    def test_small_bounded_patch_is_local_surgical(self):
        # Concrete path + bounded marker + short -> classify_dispatch returns local/eligible.
        p = generate_proposal("fix the typo in foo.py", "r3", "t3")
        assert p["task_intent"] == "implement"
        assert p["execution_tier"] == "local_surgical"
        # local_surgical allows a targeted fix claim, NOT full completion.
        assert p["report_gate"]["allow_targeted_fix_claim_only"] is True

    def test_local_surgical_requires_targeted_verification(self):
        gate = derive_report_gate("implement", "local_surgical")
        # Targeted fix only -- full completion claim is disallowed at this tier;
        # the agent may claim a targeted fix, not full SDLC completion.
        assert gate["allow_implementation_completion_claim"] is False
        assert gate["allow_targeted_fix_claim_only"] is True

    def test_full_go_allows_full_completion(self):
        gate = derive_report_gate("implement", "full_go")
        assert gate["allow_implementation_completion_claim"] is True
        assert gate["allow_targeted_fix_claim_only"] is False


# ---------------------------------------------------------------------------
# Goal test 5: hook/gate prompt -> prompt_review_required
# ---------------------------------------------------------------------------

class TestHighRiskPromptReview:
    def test_hook_prompt_sets_prompt_review_required(self):
        risk = detect_risk_signals("change the stop hook to fail-closed")
        assert risk["high_risk"] is True
        assert risk["prompt_review_required"] is True
        assert "hook" in risk["matched_markers"]

    def test_gate_prompt_in_proposal(self):
        p = generate_proposal("modify the pretooluse gate logic", "r4", "t4")
        assert p["prompt_review_required"] is True
        assert p["prompt_review_support"] == "absent"
        # high-risk + absent support -> pause
        assert p["execution_tier"] == "pause_for_authorization"


# ---------------------------------------------------------------------------
# Goal test 6: missing prompt-review support -> record tracked prerequisite
# ---------------------------------------------------------------------------

class TestRunPreflightPrerequisite:
    def test_highrisk_writes_prerequisite_artifact(self, tmp_path):
        class Args:
            prompt = "modify the PreToolUse gate to block on bad input"
        artifact = run_preflight(Args(), tmp_path, "run-hr", "tid-hr")
        assert artifact.is_file()
        prereq = tmp_path / "prompt-review-prerequisite_run-hr.json"
        assert prereq.is_file(), "tracked prerequisite must be written when support absent"
        data = json.loads(prereq.read_text(encoding="utf-8"))
        assert data["kind"] == "missing-prompt-review-support"
        assert data["blocking"] is True
        assert data["matched_markers"]  # non-empty

    def test_lowrisk_writes_no_prerequisite(self, tmp_path):
        class Args:
            prompt = "fix the typo in readme.md"
        run_preflight(Args(), tmp_path, "run-lr", "tid-lr")
        prereq = tmp_path / "prompt-review-prerequisite_run-lr.json"
        assert not prereq.is_file()


# ---------------------------------------------------------------------------
# Goal test 7: mixed -> split/defer, no bundled completion
# ---------------------------------------------------------------------------

class TestMixedNoBundledCompletion:
    def test_mixed_intent_detected(self):
        # implement ("fix") + investigate ("investigat") => mixed
        intent = classify_intent("investigate why X fails then fix it in foo.py")
        assert intent == "mixed"

    def test_mixed_report_gate_defers_children(self):
        gate = derive_report_gate("mixed", "full_go")
        assert gate["must_defer_unauthorized_children"] is True

    def test_mixed_via_generate_proposal(self):
        p = generate_proposal(
            "investigate why the hook fires twice, then fix it, and decide if we keep the gate",
            "r5", "t5")
        assert p["task_intent"] == "mixed"
        assert p["report_gate"]["must_defer_unauthorized_children"] is True
        # mixed still must not claim bundled completion
        assert p["report_gate"]["allow_implementation_completion_claim"] is False


# ---------------------------------------------------------------------------
# Goal test 8: ambiguous investigate+fix defaults to implement/full_go OR mixed
# ---------------------------------------------------------------------------

class TestAmbiguousDefaults:
    def test_ambiguous_defaults_to_implement_or_mixed_never_silent_edit(self):
        # A bare ambiguous prompt with no clear markers defaults to implement.
        intent = classify_intent("handle the thing")
        assert intent == "implement"

    def test_ambiguous_prompt_never_silently_edits(self):
        # Goal req. 8: ambiguous must default to implement/full_go OR pause,
        # NEVER silent direct edit (local_surgical). "handle the thing" has no
        # bounded marker + no path -> classify_dispatch conservatively sets
        # requiresApproval=True -> pause_for_authorization. Either full_go or
        # pause is acceptable; local_surgical is not.
        p = generate_proposal("handle the thing", "r6", "t6")
        assert p["task_intent"] == "implement"
        assert p["execution_tier"] in ("full_go", "pause_for_authorization")
        assert p["execution_tier"] != "local_surgical"  # never silent direct edit

    def test_implement_no_path_routes_to_full_go(self):
        # Bounded implement marker, no path -> pi dispatch, no approval -> full_go.
        p = generate_proposal("fix the bug", "r7", "t7")
        assert p["task_intent"] == "implement"
        assert p["execution_tier"] == "full_go"
        assert p["report_gate"]["allow_implementation_completion_claim"] is True


# ---------------------------------------------------------------------------
# Artifact freshness contract (goal req. 9)
# ---------------------------------------------------------------------------

class TestArtifactFreshness:
    def test_matching_run_passes(self):
        p = generate_proposal("fix foo.py", "run-x", "t")
        assert_fresh(p, "run-x")  # no raise

    def test_mismatched_run_raises(self):
        p = generate_proposal("fix foo.py", "run-old", "t")
        with pytest.raises(ValueError, match="stale proposal"):
            assert_fresh(p, "run-new")


# ---------------------------------------------------------------------------
# ponytail self-check
# ---------------------------------------------------------------------------

def test_smoke_mixed_request_split_and_defer():
    """Direct smoke: one mixed request -> split children + no bundled dispatch.

    Reproduces the goal's 'mixed' scenario end-to-end through the classifier.
    """
    p = generate_proposal(
        "investigate why the gate double-fires, fix the small typo in foo.py, "
        "and decide whether to keep the hook",
        "run-smoke", "tid-smoke")
    assert p["task_intent"] == "mixed"
    # Children are described in decision_advisory.options (split semantics).
    options_text = " ".join(p["decision_advisory"]["options"]).lower()
    assert "authorized low-risk" in options_text  # execute-only-authorized
    assert "defer" in options_text  # defer-decisions
    assert p["report_gate"]["allow_implementation_completion_claim"] is False
    assert p["report_gate"]["must_defer_unauthorized_children"] is True
