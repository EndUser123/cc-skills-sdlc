"""
Tests for the Frustrated User / Unclear Objective Protocol.

This test file verifies:
A. Trigger detection
B. Recommendation mode
C. Evidence hygiene
D. Entity-scope guard
E. Friction budget
F. Output structure for skill/workflow improvement requests
"""

import pytest
from pathlib import Path
from routing import (
    detect_frustrated_user_trigger,
    should_use_recommendation_mode,
    detect_intent_type,
    set_frustrated_user_active,
    get_frustrated_user_active,
    clear_frustrated_user_state,
)
from validate_templates import (
    validate_evidence_hygiene,
    classify_evidence_tier,
    validate_entity_scope,
    validate_friction_budget,
    EVIDENCE_TIERS,
)


class TestTriggerDetection:
    """Test that the Frustrated User Protocol is triggered by the correct patterns."""

    def test_frustrated_user_trigger_full_phrase(self):
        """Test: 'I'm bad with words and don't know what I don't know. What is the optimal happy path?' must trigger the Frustrated User Protocol."""
        query = "I'm bad with words and don't know what I don't know. What is the optimal happy path?"
        assert detect_frustrated_user_trigger(query) is True

    def test_frustrated_user_trigger_frustration_keywords(self):
        """Test that frustration keywords trigger the protocol."""
        frustration_queries = [
            "this is frustrating",
            "this is annoying",
            "this is circular",
            "this is unhelpful",
            "I'm tired of this",
        ]
        for query in frustration_queries:
            assert detect_frustrated_user_trigger(query) is True, f"Failed on: {query}"

    def test_frustrated_user_trigger_uncertainty(self):
        """Test that uncertainty phrases trigger the protocol."""
        uncertainty_queries = [
            "I don't know what I don't know",
            "I don't know where to start",
            "not sure where to begin",
            "I'm bad with words",
            "bad at articulating",
        ]
        for query in uncertainty_queries:
            assert detect_frustrated_user_trigger(query) is True, f"Failed on: {query}"

    def test_frustrated_user_trigger_delegation(self):
        """Test that delegation requests trigger the protocol."""
        delegation_queries = [
            "what do you think is the best path?",
            "what is the optimal happy path?",
            "what should I do?",
            "what do you think?",
            "make this easier",
        ]
        for query in delegation_queries:
            assert detect_frustrated_user_trigger(query) is True, f"Failed on: {query}"

    def test_frustratedated_user_trigger_improvement_request(self):
        """Test that improvement requests trigger the protocol."""
        improvement_queries = [
            "how can we improve this skill?",
            "how can we improve this tool?",
            "how can we improve this workflow?",
            "this is frustrating",
            "this is annoying",
        ]
        for query in improvement_queries:
            assert detect_frustrated_user_trigger(query) is True, f"Failed on: {query}"

    def test_frustrated_user_trigger_choice_pushback(self):
        """Test that choice pushback triggers the protocol."""
        pushback_queries = [
            "stop asking me to choose",
            "just tell me",
            "don't make me choose",
        ]
        for query in pushback_queries:
            assert detect_frustrated_user_trigger(query) is True, f"Failed on: {query}"

    def test_frustrated_user_trigger_no_match(self):
        """Test that normal queries do NOT trigger the protocol."""
        normal_queries = [
            "improve memory system",
            "design a new API",
            "how does routing work?",
            "implement feature X",
        ]
        for query in normal_queries:
            assert detect_frustrated_user_trigger(query) is False, f"Incorrectly triggered on: {query}"

    def test_intent_type_returns_frustrated_user(self):
        """Test that detect_intent_type returns FRUSTRATED_USER when triggered."""
        query = "I'm bad with words and don't know what I don't know. What is the optimal happy path?"
        assert detect_intent_type(query) == "FRUSTRATED_USER"


class TestRecommendationMode:
    """Test recommendation mode vs option mode behavior."""

    def test_recommendation_mode_for_happy_path(self):
        """Test that 'optimal happy path' queries trigger recommendation mode."""
        assert should_use_recommendation_mode("what is the optimal happy path?") is True

    def test_recommendation_mode_for_best_path(self):
        """Test that 'best path' queries trigger recommendation mode."""
        assert should_use_recommendation_mode("what is the best path?") is True

    def test_recommendation_mode_for_bad_with_words(self):
        """Test that 'bad with words' queries trigger recommendation mode."""
        assert should_use_recommendation_mode("I'm bad with words, just tell me what to do") is True

    def test_recommendation_mode_for_make_easier(self):
        """Test that 'make this easier' queries trigger recommendation mode."""
        assert should_use_recommendation_mode("make this easier") is True

    def test_recommendation_mode_for_simplify(self):
        """Test that 'simplify' queries trigger recommendation mode."""
        assert should_use_recommendation_mode("simplify this") is True

    def test_option_mode_for_explicit_choice(self):
        """Test that explicit choice requests do NOT trigger recommendation mode."""
        # User explicitly wants to choose, so they should get options
        assert should_use_recommendation_mode("should I use A or B?") is False
        assert should_use_recommendation_mode("which option do you prefer?") is False

    def test_option_mode_for_normal_queries(self):
        """Test that normal queries do NOT trigger recommendation mode."""
        assert should_use_recommendation_mode("improve memory system") is False
        assert should_use_recommendation_mode("design a new API") is False


class TestEvidenceHygiene:
    """Test evidence tier classification and pasted LLM claim handling."""

    def test_pasted_llm_claim_classification(self):
        """Test that a pasted LLM claim is classified as PASTED_LLM_CLAIM."""
        claim = "ChatGPT said that Redis is faster than Memcached."
        tier = classify_evidence_tier(claim, "user")
        assert tier == "PASTED_LLM_CLAIM"

    def test_pasted_claude_claim_classification(self):
        """Test that a pasted Claude claim is classified as PASTED_LLM_CLAIM."""
        claim = "Claude suggested that X is better."
        tier = classify_evidence_tier(claim, "user")
        assert tier == "PASTED_LLM_CLAIM"

    def test_pasted_gpt_claim_classification(self):
        """Test that a pasted GPT claim is classified as PASTED_LLM_CLAIM."""
        claim = "GPT-4 said that this approach is optimal."
        tier = classify_evidence_tier(claim, "user")
        assert tier == "PASTED_LLM_CLAIM"

    def test_verified_claim_from_read_tool(self):
        """Test that a claim from Read tool is classified as VERIFIED_FROM_FILES."""
        claim = "The file contains function X on line 123."
        tier = classify_evidence_tier(claim, "Read tool")
        assert tier == "VERIFIED_FROM_FILES"

    def test_verified_claim_from_grep_tool(self):
        """Test that a claim from Grep tool is classified as VERIFIED_FROM_FILES."""
        claim = "Grep found 3 matches for this pattern."
        tier = classify_evidence_tier(claim, "Grep tool")
        assert tier == "VERIFIED_FROM_FILES"

    def test_user_authoritative_preference(self):
        """Test that user preferences are classified as USER_AUTHORITATIVE."""
        claim = "I want option A"
        tier = classify_evidence_tier(claim, "user")
        assert tier == "USER_AUTHORITATIVE"

    def test_user_authoritative_requirement(self):
        """Test that user requirements are classified as USER_AUTHORITATIVE."""
        claim = "The system must support concurrent access"
        tier = classify_evidence_tier(claim, "user")
        assert tier == "USER_AUTHORITATIVE"

    def test_pasted_llm_unverified_validation_warning(self):
        """Test that unverified pasted LLM claims generate validation warnings."""
        content = "According to ChatGPT, X is better."
        warnings = validate_evidence_hygiene(content)
        assert len(warnings) > 0
        assert any("PASTED_LLM_CLAIM" in w for w in warnings)

    def test_pasted_llm_verified_no_warning(self):
        """Test that marked-as-unverified pasted LLM claims pass validation."""
        content = "According to ChatGPT, X is better (unverified hypothesis)."
        warnings = validate_evidence_hygiene(content)
        assert len(warnings) == 0

    def test_evidence_tiers_dict(self):
        """Test that EVIDENCE_TIERS constant is defined and contains required keys."""
        assert "VERIFIED_FROM_FILES" in EVIDENCE_TIERS
        assert "USER_AUTHORITATIVE" in EVIDENCE_TIERS
        assert "PASTED_LLM_CLAIM" in EVIDENCE_TIERS
        assert "ASSISTANT_INFERENCE" in EVIDENCE_TIERS


class TestEntityScopeGuard:
    """Test that evidence sources match the requested entity scope."""

    def test_entity_scope_valid_same_entity(self):
        """Test that evidence from the same entity passes validation."""
        query = "how does /design work?"
        evidence = [Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/design/routing.py")]
        is_valid, error = validate_entity_scope(query, evidence)
        assert is_valid is True
        assert error == ""

    def test_entity_scope_invalid_different_entity(self):
        """Test that evidence from a different entity fails validation."""
        query = "how does /design work?"
        evidence = [Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/go/routing.py")]
        is_valid, error = validate_entity_scope(query, evidence)
        assert is_valid is False
        assert "design" in error.lower()
        assert "scope" in error.lower()

    def test_entity_scope_valid_multiple_evidence(self):
        """Test that multiple valid evidence sources pass validation."""
        query = "how does /design work?"
        evidence = [
            Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/design/routing.py"),
            Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/design/prerequisite_analyzer.py"),
        ]
        is_valid, error = validate_entity_scope(query, evidence)
        assert is_valid is True
        assert error == ""

    def test_entity_scope_invalid_mixed_evidence(self):
        """Test that mixed valid/invalid evidence fails validation."""
        query = "how does /design work?"
        evidence = [
            Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/design/routing.py"),
            Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/go/routing.py"),
        ]
        is_valid, error = validate_entity_scope(query, evidence)
        assert is_valid is False

    def test_entity_scope_no_named_entity(self):
        """Test that queries without named entities pass (scope not verifiable)."""
        query = "generic query about routing"
        evidence = [Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/design/routing.py")]
        is_valid, error = validate_entity_scope(query, evidence)
        assert is_valid is True
        assert error == ""


class TestFrictionBudget:
    """Test friction budget validation for response quality."""

    def test_friction_budget_pass_recommended_path(self):
        """Test that a recommended path with criterion passes friction budget."""
        content = "I recommend using Redis. Criterion: lowest latency. First step: add dependency."
        issues = validate_friction_budget(content, "fast")
        assert len(issues) == 0

    def test_friction_budget_fail_implementation_choice_without_recommendation(self):
        """Test that repeated 'Which do you prefer?' without recommendation fails."""
        content = "Option A is Redis. Option B is Memcached. Which do you prefer?"
        issues = validate_friction_budget(content, "fast")
        # Should fail on both choice count and missing recommendation
        assert any("implementation_choice" in i for i in issues)
        assert any("No safe default" in i for i in issues)

    def test_friction_budget_fail_excessive_clarifications(self):
        """Test that excessive clarifications fail friction budget."""
        content = (
            "Could you clarify this? And that? And one more thing? And one last thing?"
        )
        issues = validate_friction_budget(content, "fast")
        assert any("clarification" in i for i in issues)

    def test_friction_budget_fail_excessive_permission_pushes(self):
        """Test that excessive permission pushes fail friction budget."""
        content = "May I proceed? Should I do this? Is that OK? Can I proceed now?"
        issues = validate_friction_budget(content, "fast")
        assert any("permission_push" in i for i in issues)

    def test_friction_budget_warn_internal_failures(self):
        """Test that internal failures generate warnings."""
        content = "Tool failed, trying fallback. Another error, retrying."
        issues = validate_friction_budget(content, "fast")
        assert any("internal_failure" in i for i in issues)
        # Should be a warning, not a fail
        assert any("WARN" in i for i in issues)

    def test_friction_budget_deep_template_higher_thresholds(self):
        """Test that deep template has higher thresholds."""
        # Content with more clarifications than fast threshold but within deep threshold
        content = "Could you clarify this? And that? And one more thing?"
        fast_issues = validate_friction_budget(content, "fast")
        deep_issues = validate_friction_budget(content, "deep")
        # Fast should fail (clarifications > 1), deep should pass (clarifications <= 3)
        assert len(fast_issues) > 0
        assert len(deep_issues) == 0


class TestOutputStructureForSkillImprovement:
    """Test that skill/workflow improvement requests use the correct output structure."""

    def test_output_structure_required_sections(self):
        """
        Test that skill improvement request output includes required sections:
        - What is going wrong
        - Best happy path
        - Skill changes
        - First patch to make
        - What this prevents next time
        """
        # This is a conceptual test - the actual validation would be done by
        # examining LLM output, which isn't feasible in unit tests.
        # Instead, we test that the protocol documentation exists.

        from pathlib import Path

        skill_md = Path(__file__).parent.parent / "SKILL.md"
        content = skill_md.read_text()

        # Check that the required sections are documented
        assert "What is going wrong" in content
        assert "Best happy path" in content
        assert "Skill changes" in content
        assert "First patch to make" in content
        assert "What this prevents next time" in content

    def test_agency_mode_bad_with_words(self):
        """Test agency mode triggers for 'I'm bad with words'."""
        assert should_use_recommendation_mode("I'm bad with words") is True

    def test_agency_mode_optimal_happy_path(self):
        """Test agency mode triggers for 'optimal happy path'."""
        assert should_use_recommendation_mode("what is the optimal happy path?") is True

    def test_agency_mode_what_do_you_think(self):
        """Test agency mode triggers for 'what do you think'."""
        assert should_use_recommendation_mode("what do you think?") is True


class TestEvidenceTierLabels:
    """Test that evidence tier labels are defined correctly."""

    def test_verified_from_files_label(self):
        """Test that VERIFIED_FROM_FILES label is defined."""
        assert "VERIFIED_FROM_FILES" in EVIDENCE_TIERS

    def test_user_authoritative_label(self):
        """Test that USER_AUTHORITATIVE label is defined."""
        assert "USER_AUTHORITATIVE" in EVIDENCE_TIERS

    def test_pasted_llm_claim_label(self):
        """Test that PASTED_LLM_CLAIM label is defined."""
        assert "PASTED_LLM_CLAIM" in EVIDENCE_TIERS

    def test_assistant_inference_label(self):
        """Test that ASSISTANT_INFERENCE label is defined."""
        assert "ASSISTANT_INFERENCE" in EVIDENCE_TIERS


class TestStateManagement:
    """Test that frustrated user state can be set and cleared."""

    def test_set_and_get_state(self):
        """Test that state can be set and retrieved."""
        # Initially inactive
        assert get_frustrated_user_active() is False

        # Activate
        set_frustrated_user_active("I'm bad with words")
        assert get_frustrated_user_active() is True

        # Clear
        clear_frustrated_user_state()
        assert get_frustrated_user_active() is False

    def test_state_non_triggering_query(self):
        """Test that non-triggering query doesn't activate state."""
        set_frustrated_user_active("improve memory system")
        assert get_frustrated_user_active() is False

    def test_state_triggering_query(self):
        """Test that triggering query activates state."""
        set_frustrated_user_active("this is frustrating")
        assert get_frustrated_user_active() is True

    def test_state_exports(self):
        """Test that state functions are exported in __all__."""
        from routing import __all__

        assert "set_frustrated_user_active" in __all__
        assert "get_frustrated_user_active" in __all__
        assert "clear_frustrated_user_state" in __all__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])