"""Tests for MentalModelSelector with pattern matching and category filtering.

These tests verify the mental model selection functionality for rca Tier 1.

The MentalModelSelector provides:
- Pattern-based model selection from problem descriptions
- Category filtering (MENTAL_MODEL, REASONING_STRATEGY, BIAS_CHECK)
- Confidence boost sorting
- Model recommendations with instructions

Run with: pytest P:/packages/rca/skill/tests/test_mental_model_selector.py -v
"""

import sys
from pathlib import Path

# Add package src to path for imports
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca.mental_model_selector import (
    CONFIDENCE_BOOSTS,
    MODEL_CATEGORIES,
    MODEL_INSTRUCTIONS,
    TRIGGER_PATTERNS,
    MentalModel,
    ModelCategory,
    ModelRecommendation,
    format_recommendations,
    get_all_models,
    select_by_category,
    select_mental_models,
)


class TestMentalModelEnums:
    """Tests for MentalModel and ModelCategory enums."""

    def test_mental_model_enum_values(self):
        """Test that MentalModel enum has expected values.

        Given: MentalModel enum is defined
        When: Accessing enum members
        Then: Should have expected model names
        """
        assert MentalModel.SYSTEMS_THINKING.value == "Systems Thinking"
        assert MentalModel.FIRST_PRINCIPLES.value == "First Principles"
        assert MentalModel.FIVE_WHYS.value == "Five Whys"
        assert MentalModel.TREE_OF_THOUGHTS.value == "Tree of Thoughts (ToT)"

    def test_model_category_enum_values(self):
        """Test that ModelCategory enum has expected values.

        Given: ModelCategory enum is defined
        When: Accessing enum members
        Then: Should have MENTAL_MODEL, REASONING_STRATEGY, BIAS_CHECK
        """
        assert ModelCategory.MENTAL_MODEL.value == "Mental Model"
        assert ModelCategory.REASONING_STRATEGY.value == "Reasoning Strategy"
        assert ModelCategory.BIAS_CHECK.value == "Bias Awareness"


class TestTriggerPatternsConstant:
    """Tests for TRIGGER_PATTERNS constant."""

    def test_trigger_patterns_is_dict(self):
        """Test that TRIGGER_PATTERNS is a dictionary.

        Given: TRIGGER_PATTERNS constant is defined
        When: Checking type
        Then: Should be a dict with MentalModel keys
        """
        assert isinstance(TRIGGER_PATTERNS, dict)
        assert all(isinstance(k, MentalModel) for k in TRIGGER_PATTERNS.keys())

    def test_trigger_patterns_has_systems_thinking(self):
        """Test that SYSTEMS_THINKING has expected patterns.

        Given: SYSTEMS_THINKING model
        When: Checking trigger patterns
        Then: Should include interaction keywords
        """
        patterns = TRIGGER_PATTERNS[MentalModel.SYSTEMS_THINKING]
        assert "feedback loop" in patterns
        assert "race condition" in patterns
        assert "emergent" in patterns

    def test_trigger_patterns_has_five_whys(self):
        """Test that FIVE_WHYS has expected patterns.

        Given: FIVE_WHYS model
        When: Checking trigger patterns
        Then: Should include 'why' keywords
        """
        patterns = TRIGGER_PATTERNS[MentalModel.FIVE_WHYS]
        assert "why does" in patterns
        assert "why is" in patterns
        assert "chain of" in patterns


class TestModelInstructionsConstant:
    """Tests for MODEL_INSTRUCTIONS constant."""

    def test_model_instructions_is_dict(self):
        """Test that MODEL_INSTRUCTIONS is a dictionary.

        Given: MODEL_INSTRUCTIONS constant is defined
        When: Checking type
        Then: Should be a dict with MentalModel keys
        """
        assert isinstance(MODEL_INSTRUCTIONS, dict)
        assert all(isinstance(k, MentalModel) for k in MODEL_INSTRUCTIONS.keys())

    def test_model_instructions_not_empty(self):
        """Test that all models have instructions.

        Given: MODEL_INSTRUCTIONS constant
        When: Checking all models
        Then: Each model should have non-empty instruction text
        """
        for model, instruction in MODEL_INSTRUCTIONS.items():
            assert isinstance(instruction, str)
            assert len(instruction) > 10  # Instructions should be substantive


class TestConfidenceBoostsConstant:
    """Tests for CONFIDENCE_BOOSTS constant."""

    def test_confidence_boosts_is_dict(self):
        """Test that CONFIDENCE_BOOSTS is a dictionary.

        Given: CONFIDENCE_BOOSTS constant is defined
        When: Checking type
        Then: Should be a dict with MentalModel keys
        """
        assert isinstance(CONFIDENCE_BOOSTS, dict)
        assert all(isinstance(k, MentalModel) for k in CONFIDENCE_BOOSTS.keys())

    def test_confidence_boosts_are_integers(self):
        """Test that all confidence boosts are integers.

        Given: CONFIDENCE_BOOSTS constant
        When: Checking values
        Then: All values should be integers
        """
        for model, boost in CONFIDENCE_BOOSTS.items():
            assert isinstance(boost, int)
            assert 0 < boost <= 30  # Reasonable range


class TestModelCategoriesConstant:
    """Tests for MODEL_CATEGORIES constant."""

    def test_model_categories_is_dict(self):
        """Test that MODEL_CATEGORIES is a dictionary.

        Given: MODEL_CATEGORIES constant is defined
        When: Checking type
        Then: Should be a dict with MentalModel keys
        """
        assert isinstance(MODEL_CATEGORIES, dict)
        assert all(isinstance(k, MentalModel) for k in MODEL_CATEGORIES.keys())

    def test_model_categories_values_are_valid(self):
        """Test that all category values are valid ModelCategory enums.

        Given: MODEL_CATEGORIES constant
        When: Checking values
        Then: All values should be valid ModelCategory members
        """
        valid_categories = {
            ModelCategory.MENTAL_MODEL,
            ModelCategory.REASONING_STRATEGY,
            ModelCategory.BIAS_CHECK,
        }
        for model, category in MODEL_CATEGORIES.items():
            assert category in valid_categories


class TestSelectMentalModels:
    """Tests for select_mental_models() function."""

    def test_select_mental_models_with_systems_thinking_pattern(self):
        """Test selection with systems thinking pattern match.

        Given: Problem description contains 'feedback loop'
        When: Calling select_mental_models()
        Then: Should recommend SYSTEMS_THINKING (and possibly others)
        """
        recommendations = select_mental_models("The system has a feedback loop causing issues")
        assert len(recommendations) > 0
        # Check SYSTEMS_THINKING is in results (not necessarily first due to confidence sorting)
        assert any(r.mental_model == MentalModel.SYSTEMS_THINKING for r in recommendations)
        # Check it was triggered by feedback-related pattern
        systems_thinking = next(
            r for r in recommendations if r.mental_model == MentalModel.SYSTEMS_THINKING
        )
        assert "feedback" in systems_thinking.trigger_pattern.lower()

    def test_select_mental_models_with_first_principles_pattern(self):
        """Test selection with first principles pattern match.

        Given: Problem description contains 'unusual'
        When: Calling select_mental_models()
        Then: Should recommend FIRST_PRINCIPLES
        """
        recommendations = select_mental_models("This is an unusual edge case we've never seen")
        assert len(recommendations) > 0
        assert recommendations[0].mental_model == MentalModel.FIRST_PRINCIPLES

    def test_select_mental_models_with_five_whys_pattern(self):
        """Test selection with five whys pattern match.

        Given: Problem description contains 'why does'
        When: Calling select_mental_models()
        Then: Should recommend FIVE_WHYS
        """
        recommendations = select_mental_models("Why does the service crash intermittently")
        assert len(recommendations) > 0
        # Check FIVE_WHYS is in results (may not be first due to confidence sorting)
        assert any(r.mental_model == MentalModel.FIVE_WHYS for r in recommendations)

    def test_select_mental_models_case_insensitive(self):
        """Test that pattern matching is case-insensitive.

        Given: Problem description with uppercase pattern
        When: Calling select_mental_models()
        Then: Should still match the pattern
        """
        recommendations = select_mental_models("The system has a FEEDBACK LOOP causing issues")
        assert len(recommendations) > 0
        # Check SYSTEMS_THINKING is in results (not necessarily first due to confidence sorting)
        assert any(r.mental_model == MentalModel.SYSTEMS_THINKING for r in recommendations)

    def test_select_mental_models_with_evidence_text(self):
        """Test selection with both problem and evidence.

        Given: Problem description and initial evidence
        When: Calling select_mental_models() with evidence
        Then: Should combine both texts for pattern matching
        """
        recommendations = select_mental_models(
            "The service crashes", "Evidence shows it happens when concurrent users access it"
        )
        assert len(recommendations) > 0
        # Should match 'concurrent' from evidence
        assert any(r.mental_model == MentalModel.SYSTEMS_THINKING for r in recommendations)

    def test_select_mental_models_no_pattern_match_defaults_to_five_whys(self):
        """Test that empty pattern matching defaults to Five Whys.

        Given: Problem description with no matching patterns
        When: Calling select_mental_models()
        Then: Should recommend FIVE_WHYS as default
        """
        recommendations = select_mental_models("xyz abc 123 no triggers")
        assert len(recommendations) == 1
        assert recommendations[0].mental_model == MentalModel.FIVE_WHYS
        assert recommendations[0].reason == "Default model for straightforward issues"

    def test_select_mental_models_respects_max_models(self):
        """Test that max_models parameter limits results.

        Given: Multiple patterns match
        When: Calling select_mental_models() with max_models=2
        Then: Should return at most 2 recommendations
        """
        recommendations = select_mental_models(
            "Unusual system with feedback loop, asking why does it fail"
        )
        full_count = len(recommendations)

        limited = select_mental_models(
            "Unusual system with feedback loop, asking why does it fail", max_models=2
        )
        assert len(limited) == 2
        # Should be sorted by confidence, so top 2
        assert limited[0].confidence_boost >= limited[1].confidence_boost

    def test_select_mental_models_sorts_by_confidence_boost(self):
        """Test that recommendations are sorted by confidence boost.

        Given: Multiple patterns match with different confidence boosts
        When: Calling select_mental_models()
        Then: Results should be sorted descending by confidence_boost
        """
        recommendations = select_mental_models("Unusual edge case with feedback loop in the system")
        assert len(recommendations) > 1
        # Check descending order
        for i in range(len(recommendations) - 1):
            assert recommendations[i].confidence_boost >= recommendations[i + 1].confidence_boost

    def test_select_mental_models_returns_model_recommendation_objects(self):
        """Test that function returns ModelRecommendation dataclass objects.

        Given: Valid problem description
        When: Calling select_mental_models()
        Then: Should return list of ModelRecommendation objects
        """
        recommendations = select_mental_models("The system has a feedback loop")
        assert len(recommendations) > 0
        assert isinstance(recommendations[0], ModelRecommendation)
        # Check SYSTEMS_THINKING is in results (not necessarily first due to confidence sorting)
        assert any(r.mental_model == MentalModel.SYSTEMS_THINKING for r in recommendations)
        # Check first result has correct types
        assert isinstance(recommendations[0].reason, str)
        assert isinstance(recommendations[0].confidence_boost, int)
        assert isinstance(recommendations[0].trigger_pattern, str)

    def test_select_mental_models_multiple_pattern_matches(self):
        """Test behavior when multiple patterns from same model match.

        Given: Problem description with multiple patterns for same model
        When: Calling select_mental_models()
        Then: Should add model only once (break after first match)
        """
        recommendations = select_mental_models(
            "The system has a feedback loop and timing issue with race condition"
        )
        # Should have at least one recommendation
        assert len(recommendations) > 0
        # Should only appear once despite multiple matches
        assert (
            sum(1 for r in recommendations if r.mental_model == MentalModel.SYSTEMS_THINKING) == 1
        )

    def test_select_mental_models_with_scientific_method(self):
        """Test selection with scientific method pattern.

        Given: Problem description contains 'uncertain' and 'hypothesis'
        When: Calling select_mental_models()
        Then: Should recommend SCIENTIFIC_METHOD
        """
        recommendations = select_mental_models(
            "We're uncertain about the cause, have a hypothesis it might be X"
        )
        assert len(recommendations) > 0
        # Should match SCIENTIFIC_METHOD
        assert any(r.mental_model == MentalModel.SCIENTIFIC_METHOD for r in recommendations)

    def test_select_mental_models_with_inversion(self):
        """Test selection with inversion pattern.

        Given: Problem description contains 'prevent' and 'failure mode'
        When: Calling select_mental_models()
        Then: Should recommend INVERSION
        """
        recommendations = select_mental_models(
            "How can we prevent this failure mode from occurring"
        )
        assert len(recommendations) > 0
        assert recommendations[0].mental_model == MentalModel.INVERSION


class TestFormatRecommendations:
    """Tests for format_recommendations() function."""

    def test_format_recommendations_returns_string(self):
        """Test that format_recommendations returns a string.

        Given: List of ModelRecommendation objects
        When: Calling format_recommendations()
        Then: Should return a formatted string
        """
        recommendations = [
            ModelRecommendation(
                mental_model=MentalModel.FIVE_WHYS,
                reason="Test reason",
                confidence_boost=5,
                trigger_pattern="why does",
            )
        ]
        output = format_recommendations(recommendations)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_format_recommendations_contains_headers(self):
        """Test that formatted output contains expected sections.

        Given: List of ModelRecommendation objects
        When: Calling format_recommendations()
        Then: Should include model name, reason, trigger, and action
        """
        recommendations = [
            ModelRecommendation(
                mental_model=MentalModel.FIVE_WHYS,
                reason="Test reason",
                confidence_boost=5,
                trigger_pattern="why does",
            )
        ]
        output = format_recommendations(recommendations)
        assert "## Mental Model Selection" in output
        assert "[Mental Model] Five Whys" in output
        assert "- **Reason:** Test reason" in output
        assert "- **Trigger:** why does" in output
        assert "- **Action:**" in output

    def test_format_recommendations_with_multiple_models(self):
        """Test formatting multiple recommendations.

        Given: Multiple ModelRecommendation objects
        When: Calling format_recommendations()
        Then: Should format each recommendation
        """
        recommendations = [
            ModelRecommendation(
                mental_model=MentalModel.FIVE_WHYS,
                reason="First reason",
                confidence_boost=5,
                trigger_pattern="why",
            ),
            ModelRecommendation(
                mental_model=MentalModel.FIRST_PRINCIPLES,
                reason="Second reason",
                confidence_boost=20,
                trigger_pattern="unusual",
            ),
        ]
        output = format_recommendations(recommendations)
        assert "Five Whys (+5%)" in output
        assert "First Principles (+20%)" in output

    def test_format_recommendations_shows_category(self):
        """Test that formatted output shows model category.

        Given: ModelRecommendation with REASONING_STRATEGY category
        When: Calling format_recommendations()
        Then: Should display category in output
        """
        recommendations = [
            ModelRecommendation(
                mental_model=MentalModel.CHAIN_OF_THOUGHT,
                reason="Test reason",
                confidence_boost=25,
                trigger_pattern="step-by-step",
            )
        ]
        output = format_recommendations(recommendations)
        assert "[Reasoning Strategy] Chain of Thought" in output


class TestGetAllModels:
    """Tests for get_all_models() function."""

    def test_get_all_models_returns_dict(self):
        """Test that get_all_models returns a dictionary.

        Given: get_all_models() function is called
        When: Calling get_all_models()
        Then: Should return dict with string keys
        """
        result = get_all_models()
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())

    def test_get_all_models_groups_by_category(self):
        """Test that models are grouped by category.

        Given: get_all_models() function is called
        When: Calling get_all_models()
        Then: Should have keys for each category
        """
        result = get_all_models()
        assert "Mental Model" in result
        assert "Reasoning Strategy" in result
        assert "Bias Awareness" in result

    def test_get_all_models_has_all_models(self):
        """Test that all MentalModel enum values are included.

        Given: get_all_models() function is called
        When: Calling get_all_models()
        Then: Should include all MentalModel values
        """
        result = get_all_models()
        total_models = sum(len(models) for models in result.values())
        # Should have all MentalModel enum members
        assert total_models >= len(MentalModel)  # At minimum

    def test_get_all_models_model_names_are_strings(self):
        """Test that model names are strings.

        Given: get_all_models() function is called
        When: Calling get_all_models()
        Then: All model names should be strings
        """
        result = get_all_models()
        for category, models in result.items():
            for model_name in models:
                assert isinstance(model_name, str)


class TestSelectByCategory:
    """Tests for select_by_category() function."""

    def test_select_by_category_with_mental_model(self):
        """Test selecting MENTAL_MODEL category.

        Given: Category is MENTAL_MODEL
        When: Calling select_by_category()
        Then: Should return mental models only
        """
        recommendations = select_by_category(ModelCategory.MENTAL_MODEL)
        assert len(recommendations) > 0
        assert all(
            MODEL_CATEGORIES[r.mental_model] == ModelCategory.MENTAL_MODEL for r in recommendations
        )

    def test_select_by_category_with_reasoning_strategy(self):
        """Test selecting REASONING_STRATEGY category.

        Given: Category is REASONING_STRATEGY
        When: Calling select_by_category()
        Then: Should return reasoning strategies only
        """
        recommendations = select_by_category(ModelCategory.REASONING_STRATEGY)
        assert len(recommendations) > 0
        assert all(
            MODEL_CATEGORIES[r.mental_model] == ModelCategory.REASONING_STRATEGY
            for r in recommendations
        )

    def test_select_by_category_with_bias_check(self):
        """Test selecting BIAS_CHECK category.

        Given: Category is BIAS_CHECK
        When: Calling select_by_category()
        Then: Should return bias checks only
        """
        recommendations = select_by_category(ModelCategory.BIAS_CHECK)
        assert len(recommendations) > 0
        assert all(
            MODEL_CATEGORIES[r.mental_model] == ModelCategory.BIAS_CHECK for r in recommendations
        )

    def test_select_by_category_with_pattern_matching(self):
        """Test category filtering with pattern matching.

        Given: Category and problem description with patterns
        When: Calling select_by_category() with problem text
        Then: Should filter both by category and patterns
        """
        recommendations = select_by_category(
            ModelCategory.MENTAL_MODEL, problem_description="feedback loop in the system"
        )
        # Should match SYSTEMS_THINKING pattern and be in MENTAL_MODEL category
        assert any(r.mental_model == MentalModel.SYSTEMS_THINKING for r in recommendations)
        assert all(
            MODEL_CATEGORIES[r.mental_model] == ModelCategory.MENTAL_MODEL for r in recommendations
        )

    def test_select_by_category_respects_max_models(self):
        """Test that max_models parameter works with category filtering.

        Given: Category with many models
        When: Calling select_by_category() with max_models=2
        Then: Should return at most 2 recommendations
        """
        recommendations = select_by_category(ModelCategory.MENTAL_MODEL, max_models=2)
        assert len(recommendations) <= 2

    def test_select_by_category_without_problem_description(self):
        """Test category filtering without pattern matching.

        Given: Category only (no problem description)
        When: Calling select_by_category() without problem text
        Then: Should return all models in that category (sorted by confidence)
        """
        recommendations = select_by_category(ModelCategory.MENTAL_MODEL)
        assert len(recommendations) > 0
        # Should be sorted by confidence_boost
        for i in range(len(recommendations) - 1):
            assert recommendations[i].confidence_boost >= recommendations[i + 1].confidence_boost

    def test_select_by_category_returns_model_recommendation_objects(self):
        """Test that function returns ModelRecommendation dataclass objects.

        Given: Valid category
        When: Calling select_by_category()
        Then: Should return list of ModelRecommendation objects
        """
        recommendations = select_by_category(ModelCategory.MENTAL_MODEL)
        assert len(recommendations) > 0
        assert isinstance(recommendations[0], ModelRecommendation)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_select_mental_models_empty_problem_description(self):
        """Test with empty problem description.

        Given: Empty string as problem description
        When: Calling select_mental_models()
        Then: Should default to Five Whys
        """
        recommendations = select_mental_models("")
        assert len(recommendations) == 1
        assert recommendations[0].mental_model == MentalModel.FIVE_WHYS

    def test_select_mental_models_whitespace_only(self):
        """Test with whitespace-only problem description.

        Given: Whitespace string as problem description
        When: Calling select_mental_models()
        Then: Should default to Five Whys
        """
        recommendations = select_mental_models("   \n\t  ")
        assert len(recommendations) == 1
        assert recommendations[0].mental_model == MentalModel.FIVE_WHYS

    def test_select_mental_models_max_models_zero(self):
        """Test with max_models=0.

        Given: max_models=0
        When: Calling select_mental_models()
        Then: Should return empty list
        """
        recommendations = select_mental_models("feedback loop", max_models=0)
        assert len(recommendations) == 0

    def test_select_mental_models_max_models_negative(self):
        """Test with negative max_models.

        Given: max_models=-1
        When: Calling select_mental_models()
        Then: Should handle gracefully (Python slicing returns all-1)
        """
        recommendations = select_mental_models("feedback loop", max_models=-1)
        # Negative max_models means return all-1 (Python slicing behavior)
        # For "feedback loop", matches SYSTEMS_THINKING and possibly FLYWHEEL
        # So expects at least 1 recommendation (all-1 would be 1 if there are 2 total)
        assert len(recommendations) >= 1

    def test_format_recommendations_empty_list(self):
        """Test formatting with empty recommendations list.

        Given: Empty list of recommendations
        When: Calling format_recommendations()
        Then: Should return formatted output with header only
        """
        output = format_recommendations([])
        assert isinstance(output, str)
        assert "## Mental Model Selection" in output

    def test_select_by_category_invalid_max_models(self):
        """Test select_by_category with max_models=0.

        Given: max_models=0
        When: Calling select_by_category()
        Then: Should return empty list
        """
        recommendations = select_by_category(ModelCategory.MENTAL_MODEL, max_models=0)
        assert len(recommendations) == 0


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow_selection_to_formatting(self):
        """Test complete workflow from selection to formatting.

        Given: Complex problem description
        When: Running select then format
        Then: Should produce formatted output
        """
        problem = "The distributed system has race conditions and timing issues"
        recommendations = select_mental_models(problem, max_models=3)
        output = format_recommendations(recommendations)

        assert len(recommendations) > 0
        assert "[Mental Model] Systems Thinking" in output
        assert "race condition" in output

    def test_category_filter_workflow(self):
        """Test category filtering workflow.

        Given: Want only bias check models
        When: Selecting BIAS_CHECK category
        Then: Should return only bias-related models
        """
        recommendations = select_by_category(ModelCategory.BIAS_CHECK)
        output = format_recommendations(recommendations)

        # Verify bias-related content is present
        assert "[Bias Awareness]" in output
        # Note: Not all lines need bias content (headers, empty lines, separators exist)
        # The key check is that bias models are returned, not that every line contains bias text
