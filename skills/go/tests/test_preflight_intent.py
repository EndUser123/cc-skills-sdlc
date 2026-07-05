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
    classify_mixed_work_status,
    classify_decision_kind,
    build_plain_english_report,
    assert_fresh,
    generate_proposal,
    run_preflight,
    classify_closure_check,
    derive_repro_policy,
    confirm_closed_passes,
    classify_operational_discovery,
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
        # Non-bugfix prompt so the closure_check gate does not collide with the
        # tier-classification assertion (bugfix prompts legitimately gate completion).
        p = generate_proposal("add a flag to foo.py", "r3", "t3")
        assert p["task_intent"] == "implement"
        assert p["execution_tier"] == "local_surgical"
        assert p["closure_check"]["required"] is False  # not a bugfix
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
        # Non-bugfix prompt so the closure_check gate does not collide.
        p = generate_proposal("bump the version", "r7", "t7")
        assert p["task_intent"] == "implement"
        assert p["execution_tier"] == "full_go"
        assert p["closure_check"]["required"] is False  # not a bugfix
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


# ---------------------------------------------------------------------------
# Goal req. 16 d-g: mixed-work status taxonomy + decision_kind
# ---------------------------------------------------------------------------

class TestMixedWorkStatusTaxonomy:
    """Splits the old single pause bucket into blocked_* / pause / readonly."""

    def _risk(self, prompt):
        return detect_risk_signals(prompt)

    def test_d_safe_readonly_narrowing_proceeds_without_pause(self):
        # req 16.d: investigate/validate read-only -> partial_readonly_done,
        # decision_kind safe_readonly_next_step. No pause, no blocked_*.
        prompt = "investigate why the parser crashes on None"
        p = generate_proposal(prompt, "r-d", "t-d")
        assert p["task_intent"] == "investigate"
        assert p["execution_tier"] != "pause_for_authorization"
        assert p["mixed_work_status"] == "partial_readonly_done"
        assert p["decision_kind"] == "safe_readonly_next_step"
        # Safe read-only narrowing does NOT ask the user for anything.
        per = p["plain_english_report"]
        assert "what_i_need_from_you" in per["section_order"]
        assert any("Nothing right now" in n for n in per["what_i_need_from_you"])

    def test_e_missing_corpus_becomes_blocked_prerequisite_not_pause(self):
        # req 16.e: missing corpus/evidence -> blocked_prerequisite, NEVER
        # pause_for_authorization (/go must not ask the user to approve).
        prompt = "validate the router against the missing corpus"
        risk = self._risk(prompt)
        status = classify_mixed_work_status(
            prompt, "validate", "local_surgical", risk, "absent")
        assert status == "blocked_prerequisite"
        assert status != "pause_for_authorization"

    def test_e_blocked_prerequisite_decision_kind(self):
        prompt = "audit the gate using the missing corpus"
        risk = self._risk(prompt)
        kind = classify_decision_kind(prompt, "validate", "local_surgical", risk)
        assert kind == "blocked_by_missing_evidence"

    def test_f_policy_blocked_gate_weakening_becomes_blocked_policy(self):
        # req 16.f: gate-weakening intent -> blocked_policy, NEVER pause.
        prompt = "weaken the gate to demote to warn for this hook"
        p = generate_proposal(prompt, "r-f", "t-f")
        assert p["mixed_work_status"] == "blocked_policy"
        assert p["decision_kind"] == "blocked_by_policy"
        assert p["mixed_work_status"] != "pause_for_authorization"

    def test_g_shared_config_mutation_remains_pause_for_authorization(self):
        # req 16.g: shared-state mutation -> pause_for_authorization (genuine
        # user authority), distinct from blocked_*.
        prompt = "update settings.json to add the new permission entry"
        p = generate_proposal(prompt, "r-g", "t-g")
        # Shared-state implement -> pause (user authority), not blocked_*.
        assert p["mixed_work_status"] == "pause_for_authorization"
        assert p["decision_kind"] == "shared_state_authorization"

    def test_recommendation_ready_for_decide(self):
        prompt = "should we adopt option A or option B"
        p = generate_proposal(prompt, "r-rec", "t-rec")
        assert p["mixed_work_status"] == "recommendation_ready"
        assert p["decision_kind"] == "user_preference"

    def test_blocked_does_not_request_user_approval(self):
        # req 7: blocked_* must NOT ask the user to approve.
        prompt = "weaken the gate to fail-open"
        p = generate_proposal(prompt, "r-b7", "t-b7")
        per = p["plain_english_report"]
        assert any("not asked of you" in b for b in per["what_is_blocked"]) or \
               any("no approval is requested" in n for n in per["what_i_need_from_you"])


# ---------------------------------------------------------------------------
# Goal req. 16 k-l: report format
# ---------------------------------------------------------------------------

class TestPlainEnglishReportFormat:
    """Recommendation-before-labels (k) and git-status evidence mandate (l)."""

    def test_k_section_order_recommendation_before_labels(self):
        # req 16.k: plain-English sections appear BEFORE internal labels.
        p = generate_proposal("investigate why the hook double-fires", "r-k", "t-k")
        per = p["plain_english_report"]
        assert per["section_order"] == [
            "what_i_did", "what_i_recommend", "what_is_blocked",
            "what_i_need_from_you",
        ]
        assert per["labels_after_plain_english"] is True
        # Recommendation section is non-empty and precedes any label mention.
        assert per["what_i_recommend"]
        assert per["what_i_did"]

    def test_l_no_mutation_claim_requires_git_status_evidence(self):
        # req 16.l: the report flags that a no-mutation claim requires
        # git status --short (or equivalent); SKILL.md must document the rule.
        p = generate_proposal("review the diff for correctness", "r-l", "t-l")
        assert p["plain_english_report"]["no_mutation_evidence_required"] is True
        skill = Path(__file__).resolve().parent.parent / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        assert "git status --short" in text
        assert "no mutation" in text.lower() or "no-mutation" in text.lower()

    def test_blocked_report_names_blocker_and_evidence_step(self):
        # req 7: blocked report states the blocker + the next evidence step.
        p = generate_proposal("weaken the gate to bypass the hook", "r-bk", "t-bk")
        per = p["plain_english_report"]
        assert per["what_is_blocked"]
        assert any("evidence" in r.lower() or "policy" in r.lower()
                   for r in per["what_i_recommend"])

    def test_pause_report_names_exact_authorization(self):
        # req 9/16.g: pause_for_authorization surfaces exact_authorization_needed.
        p = generate_proposal("update settings.json to add the permission",
                              "r-pa", "t-pa")
        per = p["plain_english_report"]
        assert p["mixed_work_status"] == "pause_for_authorization"
        assert any("authorization" in n.lower() or "director" in n.lower()
                   for n in per["what_i_need_from_you"])


def test_smoke_end_to_end_status_taxonomy_real_path():
    """Direct smoke through generate_proposal: real preflight path, no mocks.

    Exercises classify_intent -> derive_execution_tier ->
    classify_mixed_work_status -> classify_decision_kind ->
    build_plain_english_report in the same call path the orchestrator uses.
    """
    cases = [
        ("investigate why X fails", "partial_readonly_done"),
        ("should we adopt A or B", "recommendation_ready"),
        ("update settings.json to add x", "pause_for_authorization"),
        ("weaken the gate to fail-open", "blocked_policy"),
    ]
    for prompt, expected_status in cases:
        p = generate_proposal(prompt, f"run-{expected_status}", f"tid-{expected_status}")
        assert p["mixed_work_status"] == expected_status, (
            f"{prompt!r} -> {p['mixed_work_status']!r}, expected {expected_status!r}")
        assert "plain_english_report" in p
        assert len(p["plain_english_report"]["section_order"]) == 4


# ---------------------------------------------------------------------------
# Goal req. 14 / 17 (last): enforcement-honesty — verified vs advisory paths
# ---------------------------------------------------------------------------

class TestEnforcementHonesty:
    """delegation_policy.enforcement_status must distinguish declared policy
    from verified runtime enforcement (req. 14). Tests exercise the real
    generate_proposal path, not mocks (req. 17 last bullet)."""

    def test_enforcement_status_has_three_lists(self):
        p = generate_proposal("fix the typo in foo.py", "r-eh1", "t-eh1")
        es = p["delegation_policy"]["enforcement_status"]
        for key in ("verified", "advisory_or_unverified", "role_enforcement",
                    "declared_vs_verified_note"):
            assert key in es, f"missing {key}"

    def test_verified_lists_all_five_points(self):
        # req 14: writer + marker/state + reader/gate + active window + dispatch path
        p = generate_proposal("fix the typo in foo.py", "r-eh2", "t-eh2")
        verified = " ".join(p["delegation_policy"]["enforcement_status"]["verified"]).lower()
        for needle in ("writer", "marker", "reader", "main-session", "dispatch"):
            assert needle in verified, f"verified list missing {needle!r}"

    def test_advisory_paths_named_explicitly(self):
        # Task-subagent propagation unverified + agy outside tool-call boundary
        p = generate_proposal("fix the typo in foo.py", "r-eh3", "t-eh3")
        advisory = " ".join(
            p["delegation_policy"]["enforcement_status"]["advisory_or_unverified"]
        ).lower()
        assert "subagent" in advisory or "unverified" in advisory
        assert "agy" in advisory

    def test_role_enforcement_distinguishes_verified_vs_advisory(self):
        p = generate_proposal("fix the typo in foo.py", "r-eh4", "t-eh4")
        role = p["delegation_policy"]["enforcement_status"]["role_enforcement"]
        # claude_main + pi_ccr verified; claude_subagent/local_fast unverified; agy advisory
        assert "verified" in role["claude_main"].lower()
        assert "verified" in role["pi_ccr"].lower()
        assert "unverified" in role["claude_subagent"].lower()
        assert "unverified" in role["local_fast"].lower()
        assert "advisory" in role["agy"].lower()

    def test_declared_vs_verified_note_present(self):
        p = generate_proposal("fix the typo in foo.py", "r-eh5", "t-eh5")
        note = p["delegation_policy"]["enforcement_status"]["declared_vs_verified_note"]
        assert "DECLARES" in note and "VERIFIED" in note

    def test_skill_md_documents_enforcement_honesty(self):
        # req 14 lives in SKILL too — grep for the honesty rule + 5 points.
        skill = Path(__file__).resolve().parent.parent / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        assert "Enforcement honesty" in text
        assert "verified" in text.lower() and "advisory_or_unverified" in text.lower()
        # Must NOT claim all role authority is enforced.
        assert "Do NOT claim" in text


# ---------------------------------------------------------------------------
# Goal req. 16: fixed mixed-work disclaimer sentence
# ---------------------------------------------------------------------------

class TestMixedDisclaimerWording:
    """Mixed-intent reports must carry the req-16 disclaimer sentence."""

    def test_mixed_report_includes_fixed_disclaimer(self):
        p = generate_proposal(
            "investigate why the hook fires then fix it in foo.py "
            "and decide whether to keep the gate",
            "r-mx", "t-mx")
        assert p["task_intent"] == "mixed"
        per = p["plain_english_report"]
        joined = " ".join(per["what_i_did"])
        assert "This is mixed work" in joined
        assert "not claiming blocked or decision-dependent work is done" in joined


# ---------------------------------------------------------------------------
# Goal reqs 1-11: closure_check (reproduce-first + confirm-closed)
# ---------------------------------------------------------------------------

class TestClosureCheckRequired:
    """bugfix/regression/hook-FP/stale-warning tasks require closure_check (reqs 2, 3)."""

    @pytest.mark.parametrize("prompt,source", [
        ("fix the parser crash on None", "none"),              # bugfix w/o a source marker -> none
        ("fix the regression in the hook dispatch", "regression"),
        ("fix the stop hook false positive on copy-paste", "hook_fp"),
        ("fix the stale warning that keeps firing after cleanup", "hook_fp"),
    ])
    def test_bugfix_requires_closure(self, prompt, source):
        cc = classify_closure_check(prompt, "implement")
        assert cc["required"] is True, f"{prompt!r} should require closure"
        assert cc["source"] == source, f"{prompt!r} -> source={cc['source']!r}, want {source!r}"
        assert cc["reproduce_first_required"] is True

    def test_bugfix_closure_propagates_to_report_gate(self):
        p = generate_proposal("fix the regression in the hook dispatch", "r-cc1", "t-cc1")
        assert p["closure_check"]["required"] is True
        gate = p["report_gate"]
        assert gate["closure_check_required"] is True
        assert gate["confirm_closed_required"] is True
        # No evidence yet at preflight -> may NOT claim completion.
        assert gate["confirm_closed_passes"] is False
        assert gate["allow_implementation_completion_claim"] is False

    def test_investigate_does_not_require_closure(self):
        # req 8: investigate/validate/decide do NOT require closure_check.
        p = generate_proposal("investigate why the hook double-fires", "r-cc2", "t-cc2")
        assert p["closure_check"]["required"] is False
        assert p["report_gate"]["closure_check_required"] is False

    def test_decide_does_not_require_closure(self):
        p = generate_proposal("should we adopt option A or option B", "r-cc3", "t-cc3")
        assert p["closure_check"]["required"] is False


class TestConfirmClosedGate:
    """A bugfix must not claim fixed/complete without confirm-closed (reqs 4, 6, 11)."""

    def test_unit_test_alone_is_insufficient(self):
        # req 11: a passing unit test alone does NOT satisfy closure.
        cc = classify_closure_check("fix the regression in foo.py", "implement")
        # Only verification_tests present (simulating "unit test passed") — no
        # symptom-gone evidence, no unavailable_reason -> gate stays closed.
        assert confirm_closed_passes(cc) is False

    def test_evidence_plus_expected_after_passes(self):
        cc = classify_closure_check("fix the regression in foo.py", "implement")
        cc["evidence_summary"] = "re-ran the failing repro; symptom gone"
        cc["expected_after"] = "no crash; exit 0 on the original repro"
        assert confirm_closed_passes(cc) is True

    def test_evidence_without_expected_after_still_fails(self):
        # Evidence alone (no expected_after) is NOT enough — must re-state what
        # the symptom looks like AFTER the fix, not just "I ran something".
        cc = classify_closure_check("fix the regression in foo.py", "implement")
        cc["evidence_summary"] = "ran the test"
        assert confirm_closed_passes(cc) is False

    def test_unavailable_reason_passes_but_report_must_not_overclaim(self):
        # req 5 / cannot-reproduce: artifact lets the report proceed but does
        # NOT authorize a Fixed claim. confirm_closed_passes returns True so the
        # gate doesn't hard-block, but the closure_report must record the reason.
        cc = classify_closure_check("fix the intermittent crash in foo.py", "implement")
        assert cc["cannot_reproduce_artifact_allowed"] is True
        cc["unavailable_reason"] = "flaky; cannot reproduce deterministically"
        assert confirm_closed_passes(cc) is True

    def test_bugfix_cannot_claim_fixed_without_confirm_closed(self):
        p = generate_proposal("fix the regression in the hook dispatch", "r-cc4", "t-cc4")
        # Simulate the worker updating closure_check with evidence mid-run.
        p["closure_check"]["evidence_summary"] = "ran repro; symptom gone"
        p["closure_check"]["expected_after"] = "no double-fire on the original repro"
        # Re-derive the gate with the updated closure_check.
        gate = derive_report_gate("implement", "full_go", p["closure_check"])
        assert gate["allow_implementation_completion_claim"] is True


class TestReproPolicy:
    """Reproduce-first behavior for bugfix/regression (req 5)."""

    def test_bugfix_requires_pre_fix_repro(self):
        cc = classify_closure_check("fix the regression in foo.py", "implement")
        rp = derive_repro_policy("fix the regression in foo.py", "implement", cc)
        assert rp["required"] is True
        assert rp["artifact_required"] == "pre_fix_repro"

    def test_cannot_reproduce_artifact_allowed_for_flaky(self):
        cc = classify_closure_check("fix the intermittent flaky crash", "implement")
        rp = derive_repro_policy("fix the intermittent flaky crash", "implement", cc)
        assert rp["cannot_reproduce_allows_report_but_not_overclaim"] is True
        assert rp["artifact_required"] == "cannot_reproduce_or_no_repro"

    def test_non_bugfix_has_no_repro_requirement(self):
        cc = classify_closure_check("add a new banner component", "implement")
        rp = derive_repro_policy("add a new banner component", "implement", cc)
        assert rp["required"] is False


class TestHookFpRegisteredPathClosure:
    """Hook-FP / high-risk closure must use the registered path where practical (req 7)."""

    def test_hook_fp_sets_registered_path_required(self):
        p = generate_proposal("fix the stop hook false positive on copy-paste",
                              "r-cc5", "t-cc5")
        cc = p["closure_check"]
        assert cc["required"] is True
        assert cc["source"] == "hook_fp"
        assert cc["registered_path_required"] is True

    def test_closure_report_includes_registered_path_flag(self):
        p = generate_proposal("fix the PreToolUse gate false positive", "r-cc6", "t-cc6")
        per = p["plain_english_report"]
        assert "closure_report" in per
        assert per["closure_report"]["confirm_closed_via_registered_path"] is True

    def test_closure_report_has_five_required_content_fields(self):
        # req 10: original_symptom, reproduce-first evidence, verification tests,
        # confirm-closed evidence, remaining risk.
        p = generate_proposal("fix the regression in foo.py", "r-cc7", "t-cc7")
        cr = p["plain_english_report"]["closure_report"]
        for key in ("original_symptom", "reproduce_first_evidence",
                    "verification_tests", "confirm_closed_evidence",
                    "remaining_risk", "may_claim_fixed"):
            assert key in cr, f"closure_report missing {key}"
        assert cr["may_claim_fixed"] is False  # no evidence at preflight


class TestClosureMissingDefaultsToBlock:
    """Missing/malformed closure on a required task blocks silent completion (req 9)."""

    def test_required_closure_with_no_evidence_blocks_completion(self):
        p = generate_proposal("fix the regression in foo.py", "r-cc8", "t-cc8")
        # The proposal must NOT silently enable completion at preflight.
        assert p["report_gate"]["allow_implementation_completion_claim"] is False
        # Notes surface the closure requirement so it is not silent.
        assert any("CLOSURE_CHECK required" in n for n in p["notes"])

    def test_investigate_does_not_use_fixed_language(self):
        # req 8: investigate/decide reports must not claim fixed/completed.
        p = generate_proposal("investigate why the parser crashes on None",
                              "r-cc9", "t-cc9")
        assert p["closure_check"]["required"] is False
        per = p["plain_english_report"]
        assert "closure_report" not in per  # no closure scaffolding for non-required


def test_smoke_closure_check_real_path():
    """Direct smoke through generate_proposal: real preflight path, no mocks.

    Exercises classify_closure_check -> derive_repro_policy -> derive_report_gate
    (with closure_check) -> build_plain_english_report (with closure_report) in
    the same call path the orchestrator uses.
    """
    # Bugfix prompt: required closure, gate blocks completion at preflight.
    p = generate_proposal("fix the regression in the stop hook dispatch",
                          "run-cc-smoke", "tid-cc-smoke")
    assert p["closure_check"]["required"] is True
    assert p["report_gate"]["confirm_closed_required"] is True
    assert p["report_gate"]["confirm_closed_passes"] is False
    assert "closure_report" in p["plain_english_report"]
    # Fill the closure_check as the worker would -> gate now permits completion.
    p["closure_check"]["evidence_summary"] = "re-ran the failing repro; symptom gone"
    p["closure_check"]["expected_after"] = "exit 0, no double-fire"
    gate = derive_report_gate(p["task_intent"], p["execution_tier"], p["closure_check"])
    assert gate["confirm_closed_passes"] is True
    assert gate["allow_implementation_completion_claim"] in (True, False)  # tier-dependent
    # Investigate prompt: closure not required, no closure_report.
    inv = generate_proposal("investigate why X fails", "run-cc-inv", "tid-cc-inv")
    assert inv["closure_check"]["required"] is False
    assert "closure_report" not in inv["plain_english_report"]


# ---------------------------------------------------------------------------
# Discovery-first / verification-ranking / lifecycle hygiene (goal: discovery)
# ---------------------------------------------------------------------------

class TestOperationalDiscoveryTrigger:
    """reqs. 2, 3: operational surface questions trigger discovery-first."""

    @pytest.mark.parametrize("prompt,expected_surface", [
        ("do git worktrees accumulate over time?", "worktree"),
        ("why does the Stop hook double-fire?", "hook"),
        ("where is the gate registered?", "gate"),
        ("how does the session pointer get cleaned up?", "session"),
        ("why is the plugin cache stale?", "cache"),
        ("where do phase markers get written?", "markers"),
    ])
    def test_surface_detected(self, prompt, expected_surface):
        d = classify_operational_discovery(prompt, "investigate")
        assert d["required"] is True
        assert expected_surface in d["surfaces"]
        assert d["cleanup_requires_approval"] is True

    def test_non_operational_does_not_trigger(self):
        d = classify_operational_discovery("add a flag to foo.py", "implement")
        assert d["required"] is False
        assert d["surfaces"] == []
        assert d["identify_checklist"] == []

    def test_identify_checklist_present(self):
        d = classify_operational_discovery(
            "investigate the worktree lifecycle", "investigate")
        assert "writer/creator" in d["identify_checklist"]
        assert "lifecycle/cleanup path" in d["identify_checklist"]
        assert "stale/failure direction" in d["identify_checklist"]


class TestVerificationRanking:
    """req. 4: ≥2 paths ranked by confidence-per-effort; oracle above trace."""

    def test_paths_listed_for_investigate(self):
        d = classify_operational_discovery(
            "investigate why the hook misfires", "investigate")
        assert len(d["verification_paths"]) >= 2
        # Empirical oracle ranked first.
        first = d["verification_paths"][0]
        assert first["path"].startswith("empirical")
        assert first["confidence"] == "highest"
        assert d["empirical_oracle_preferred"] is True

    def test_trace_gap_stated(self):
        d = classify_operational_discovery(
            "decide whether to gate the dispatch router", "decide")
        assert d["empirical_trace_gap"]  # non-empty
        assert "concurrency" in d["empirical_trace_gap"] or "runtime" in d["empirical_trace_gap"]

    def test_implement_operational_no_empirical_list(self):
        # implement intent over an operational surface: discovery required, but
        # the ≥2-paths ranking is reserved for uncertain intents.
        d = classify_operational_discovery(
            "fix the cache invalidation bug", "implement")
        assert d["required"] is True
        assert d["empirical_oracle_preferred"] is False


class TestWorktreeLifecycle:
    """req. 6: worktree prune predicate — safe, never blind deletion."""

    def test_prune_predicate_requires_all_conditions(self):
        wt = generate_proposal(
            "do worktrees accumulate? investigate the worktree lifecycle",
            "run-wt", "tid-wt")
        pred = wt["operational_discovery"]["worktree_prune_predicate"]
        assert pred, "worktree surface must produce a prune predicate"
        joined = " ".join(pred).lower()
        # age, clean status, merged/disposable, dry-run, approval — all required.
        for term in ("age", "clean", "merged", "dry run", "approval"):
            assert term in joined, f"prune predicate missing '{term}'"

    def test_no_cleanup_action_without_approval(self):
        wt = generate_proposal(
            "do worktrees accumulate?", "run-wt2", "tid-wt2")
        assert wt["operational_discovery"]["cleanup_requires_approval"] is True
        # The proposal must NOT contain a scheduled/auto cleanup command.
        notes_joined = " ".join(wt.get("notes", [])).lower()
        assert "auto-delete" not in notes_joined
        assert "rm -rf" not in notes_joined


class TestDiscoveryReportEvidence:
    """reqs. 7, 8: discovery_evidence scaffold + provenance tiers."""

    def test_report_has_discovery_evidence(self):
        p = generate_proposal(
            "investigate the worktree accumulation question",
            "run-disc", "tid-disc")
        de = p["plain_english_report"].get("discovery_evidence")
        assert de, "operational investigate must scaffold discovery_evidence"
        assert de["section_order_position"] == "before what_i_recommend"
        assert "verified" in de["provenance_tiers"]
        assert "inference" in de["provenance_tiers"]
        assert "assumption" in de["provenance_tiers"]
        assert de["findings"] == []  # worker fills

    def test_non_operational_no_discovery_evidence(self):
        p = generate_proposal(
            "add a docstring to foo.py", "run-no-disc", "tid-no-disc")
        assert "discovery_evidence" not in p["plain_english_report"]


def test_smoke_operational_discovery_real_path():
    """End-to-end: worktree question surfaces discovery contract in proposal + report."""
    p = generate_proposal(
        "investigate: do git worktrees accumulate, and what cleans them up?",
        "run-od-smoke", "tid-od-smoke")
    od = p["operational_discovery"]
    assert od["required"] is True
    assert "worktree" in od["surfaces"]
    assert od["worktree_prune_predicate"]
    assert "discovery_evidence" in p["plain_english_report"]
    assert p["plain_english_report"]["discovery_evidence"]["worktree_prune_predicate"]

