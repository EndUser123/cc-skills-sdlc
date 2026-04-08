"""
Tests for behavior_gates_checker.py

Test coverage:
- Agreement pattern detection (implementation commitments)
- Guidance pattern detection (directive guidance)
- TDD context awareness (RED vs GREEN/REFACTOR phases)
- Exclusion patterns (test-writing, delegation, questions, planning)
- False positive prevention
- CLI interface
"""

import json

import pytest
from scripts.behavior_gates_checker import BehaviorGatesChecker


class TestAgreementPatternDetection:
    """Test detection of direct implementation commitments."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [
                    r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add|remove|delete|implement)\s+(?:the\s+)?(?:file|code|function|method|class)\b"
                ],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [r"\bI'll\s+(?:check|verify|validate|review|examine|inspect)\b"],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [r"\b(?:writing|creating)\s+(?:a\s+)?test\b"],
                "implementation_phase_indicators": [r"\b(?:implementing|implementation)\b"]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_agreement_direct_commitment(self, checker):
        """Test detection of direct implementation commitment."""
        text = "I'll fix the code in src/main.py"
        result = checker.check_text(text)
        assert result["has_agreement"] is True
        assert result["has_guidance"] is False

    def test_agreement_multiple_commitments(self, checker):
        """Test detection of multiple implementation commitments."""
        text = "I'll update the file and then I'll modify the function"
        result = checker.check_text(text)
        assert result["has_agreement"] is True

    def test_agreement_case_insensitive(self, checker):
        """Test that agreement detection is case-insensitive."""
        text = "I'LL FIX THE CODE"
        result = checker.check_text(text)
        assert result["has_agreement"] is True

    def test_agreement_not_detected_for_guidance(self, checker):
        """Test that guidance patterns are not detected as agreement."""
        text = "you should modify the function"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert result["has_guidance"] is True


class TestGuidancePatternDetection:
    """Test detection of directive guidance to user."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [r"\bI'll\s+(?:check|verify|validate|review|examine|inspect)\b"],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [r"\b(?:writing|creating)\s+(?:a\s+)?test\b"],
                "implementation_phase_indicators": [r"\b(?:implementing|implementation)\b"]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_guidance_directive(self, checker):
        """Test detection of directive guidance to user."""
        text = "you should modify the function in src/main.py"
        result = checker.check_text(text)
        assert result["has_guidance"] is True
        assert result["has_agreement"] is False

    def test_guidance_multiple_directives(self, checker):
        """Test detection of multiple guidance patterns."""
        text = "you should update the file and change the configuration"
        result = checker.check_text(text)
        assert result["has_guidance"] is True

    def test_guidance_case_insensitive(self, checker):
        """Test that guidance detection is case-insensitive."""
        text = "YOU SHOULD MODIFY THE CODE"
        result = checker.check_text(text)
        assert result["has_guidance"] is True


class TestAgreementExclusions:
    """Test exclusion patterns for agreement detection."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [
                    r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add)\s+(?:the\s+)?(?:file|code|function|method|class)\b",
                    r"\bI'll\s+(?:write|create|add)\b"
                ],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [r"\bI'll\s+(?:check|verify|validate|review|examine|inspect|show)\b"],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [r"\b(?:writing|creating)\s+(?:a\s+)?test\b"],
                "implementation_phase_indicators": [r"\b(?:implementing|implementation)\b"]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_exclusion_test_writing(self, checker):
        """Test that test-writing is excluded from agreement detection."""
        text = "I'll write a test for the function"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert "test_writing" in result["excluded_by"]

    def test_exclusion_guidance_and_planning(self, checker):
        """Test that planning/checking activities are excluded."""
        text = "I'll check the file for issues"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert "guidance_and_planning" in result["excluded_by"]

    def test_exclusion_questions(self, checker):
        """Test that questions are excluded from agreement detection."""
        text = "should I write a test for this"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert "questions" in result["excluded_by"]

    def test_exclusion_delegation(self, checker):
        """Test that delegation statements are excluded."""
        text = "I'll dispatch a subagent to handle this"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert "delegation" in result["excluded_by"]


class TestGuidanceExclusions:
    """Test exclusion patterns for guidance detection."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [r"\bI'll\s+(?:check|verify|validate|review|examine|inspect)\b"],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [
                    r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b",
                    r"\byou\s+should\s+(?:write|create|add)\b"
                ],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [r"\b(?:writing|creating)\s+(?:a\s+)?test\b"],
                "implementation_phase_indicators": [r"\b(?:implementing|implementation)\b"]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_exclusion_test_suggestions(self, checker):
        """Test that test suggestions are excluded from guidance detection."""
        text = "you should write a test for this function"
        result = checker.check_text(text)
        assert result["has_guidance"] is False
        assert "test_suggestions" in result["excluded_by"]

    def test_exclusion_explanations(self, checker):
        """Test that explanatory statements are excluded."""
        text = "you can check the output to see the result"
        result = checker.check_text(text)
        assert result["has_guidance"] is False
        assert "explanations" in result["excluded_by"]


class TestTDDContextAwareness:
    """Test TDD phase detection (RED vs GREEN/REFACTOR)."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [r"\bI'll\s+(?:check|verify|validate|review|examine|inspect)\b"],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [
                    r"\b(?:writing|creating)\s+(?:a\s+)?test\b",
                    r"\btest\s+(?:writing|creation|development)\b"
                ],
                "implementation_phase_indicators": [
                    r"\b(?:implementing|implementation)\b",
                    r"\b(?:fixing|fix)\s+(?:the\s+)?(?:test|code)\b"
                ]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_tdd_red_phase_detection(self, checker):
        """Test detection of TDD RED phase (test-writing)."""
        text = "I'm writing a test for the new feature"
        result = checker.check_text(text)
        assert result["tdd_phase"] == "red"

    def test_tdd_implementation_phase_detection(self, checker):
        """Test detection of TDD implementation phase (GREEN/REFACTOR)."""
        text = "I'm implementing the feature now"
        result = checker.check_text(text)
        assert result["tdd_phase"] == "implementation"

    def test_tdd_phase_unknown(self, checker):
        """Test when TDD phase cannot be determined."""
        text = "Let me check the code"
        result = checker.check_text(text)
        assert result["tdd_phase"] == "unknown"

    def test_tdd_context_recommendation_red(self, checker):
        """Test recommendation for TDD RED phase."""
        text = "I'll create the code and I'm writing a test"
        result = checker.check_text(text)
        assert result["tdd_phase"] == "red"
        assert any("test-writing" in rec.lower() for rec in result["recommendations"])


class TestRecommendations:
    """Test actionable recommendations from checker."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [r"\bI'll\s+(?:check|verify|validate|review|examine|inspect)\b"],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [r"\b(?:writing|creating)\s+(?:a\s+)?test\b"],
                "implementation_phase_indicators": [r"\b(?:implementing|implementation)\b"]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_recommendation_for_implementation_commitment(self, checker):
        """Test recommendation when implementation commitment detected."""
        text = "I'll write the code"
        result = checker.check_text(text)
        assert len(result["recommendations"]) > 0
        assert any("delegat" in rec.lower() for rec in result["recommendations"])

    def test_no_recommendation_for_guidance(self, checker):
        """Test that guidance doesn't generate delegation recommendations."""
        text = "you should modify the function"
        result = checker.check_text(text)
        assert result["has_guidance"] is True
        # Guidance is acceptable (user implements), so no delegation recommendation
        assert not any("delegate" in rec.lower() for rec in result["recommendations"])


class TestFalsePositivePrevention:
    """Test scenarios that previously caused false positives."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [
                    r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add)\s+(?:the\s+)?(?:file|code|function|method|class)\b",
                    r"\bI'll\s+show\b"
                ],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [
                        r"\bI'll\s+(?:check|verify|validate|review|examine|inspect)\b",
                        r"\bI'll\s+show\s+you\b"
                    ],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [
                    r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b",
                    r"\byou\s+can\b"
                ],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [r"\b(?:writing|creating)\s+(?:a\s+)?test\b"],
                "implementation_phase_indicators": [r"\b(?:implementing|implementation)\b"]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_false_positive_showing_results(self, checker):
        """Test that showing results doesn't trigger agreement."""
        text = "I'll show you the results from the analysis"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert "guidance_and_planning" in result["excluded_by"]

    def test_false_positive_you_can_explanation(self, checker):
        """Test that 'you can' explanations don't trigger guidance."""
        text = "you can see the results in the output"
        result = checker.check_text(text)
        assert result["has_guidance"] is False
        assert "explanations" in result["excluded_by"]

    def test_false_positive_test_writing(self, checker):
        """Test that test-writing doesn't trigger implementation commitment."""
        text = "I'll write a test for the authentication module"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert "test_writing" in result["excluded_by"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create a checker instance with test config."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [r"\bI'll\s+(?:update|fix|edit|modify|change|create|write|add)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_writing": [r"\bI'll\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "guidance_and_planning": [r"\bI'll\s+(?:check|verify|validate|review|examine|inspect)\b"],
                    "questions": [r"\bshould\s+I\s+(?:write|create|add|modify|change)\b"],
                    "delegation": [r"\bI'll\s+(?:dispatch|delegate|call|invoke|use|run)\s+(?:the|a|an)?\s+(?:Task\s+tool|agent|subagent)\b"]
                }
            },
            "guidance_patterns": {
                "direct_guidance": [r"\byou\s+should\s+(?:modify|change|update|edit|fix|add|remove|delete)\s+(?:the\s+)?(?:file|code|function|method|class)\b"],
                "excluded_patterns": {
                    "test_suggestions": [r"\byou\s+should\s+(?:write|create|add)\s+(?:a\s+)?test\b"],
                    "explanations": [r"\byou\s+can\s+(?:see|check|verify|use|try)\b"]
                }
            },
            "tdd_context": {
                "red_phase_indicators": [r"\b(?:writing|creating)\s+(?:a\s+)?test\b"],
                "implementation_phase_indicators": [r"\b(?:implementing|implementation)\b"]
            }
        }))
        return BehaviorGatesChecker(config_path=config_path)

    def test_empty_text(self, checker):
        """Test handling of empty text."""
        result = checker.check_text("")
        assert result["has_agreement"] is False
        assert result["has_guidance"] is False
        assert result["tdd_phase"] == "unknown"

    def test_text_with_only_whitespace(self, checker):
        """Test handling of whitespace-only text."""
        result = checker.check_text("   \n\t  ")
        assert result["has_agreement"] is False
        assert result["has_guidance"] is False

    def test_multiple_exclusions(self, checker):
        """Test handling of multiple exclusion matches."""
        text = "should I write a test or check the existing code?"
        result = checker.check_text(text)
        assert result["has_agreement"] is False
        assert "questions" in result["excluded_by"]

    def test_agreement_and_guidance_both_present(self, checker):
        """Test when both agreement and guidance patterns are present."""
        text = "I'll fix the code and you should update the file"
        result = checker.check_text(text)
        assert result["has_agreement"] is True
        assert result["has_guidance"] is True


class TestCLIAPI:
    """Test CLI interface for behavior gates checker."""

    def test_cli_with_simple_text(self, tmp_path, capsys):
        """Test CLI invocation with simple text."""
        from scripts.behavior_gates_checker import main

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "agreement_patterns": {
                "direct_commitments": [r"\bI'll\s+fix\b"],
                "excluded_patterns": {
                    "test_writing": [],
                    "guidance_and_planning": [],
                    "questions": [],
                    "delegation": []
                }
            },
            "guidance_patterns": {
                "direct_guidance": [r"\byou\s+should\s+fix\b"],
                "excluded_patterns": {
                    "test_suggestions": [],
                    "explanations": []
                }
            },
            "tdd_context": {
                "red_phase_indicators": [],
                "implementation_phase_indicators": []
            }
        }))

        # Simulate CLI call
        import sys
        old_argv = sys.argv
        sys.argv = ["behavior_gates_checker.py", "--config", str(config_path), "I'll fix the code"]

        try:
            exit_code = main()
            assert exit_code == 0

            captured = capsys.readouterr()
            assert "Agreement" in captured.out
            assert "True" in captured.out
        finally:
            sys.argv = old_argv
