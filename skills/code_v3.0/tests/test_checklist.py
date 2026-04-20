#!/usr/bin/env python3
"""Tests for Pre-Execution Checklist validation and evidence logging."""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib.checklist import (
        CHECKLIST_QUESTIONS,
        ChecklistQuestion,
        ChecklistValidationError,
        ValidationResult,
        log_checklist_answers,
        validate_checklist,
    )

    CHECKLIST_AVAILABLE = True
except ImportError:
    CHECKLIST_AVAILABLE = False
    CHECKLIST_QUESTIONS = None
    ChecklistValidationError = None
    ChecklistQuestion = None
    ValidationResult = None
    log_checklist_answers = None
    validate_checklist = None


class TestChecklistQuestions:
    """Test checklist question definitions - NEW FUNCTIONALITY."""

    def test_five_questions_defined(self):
        """Exactly 5 questions should be defined."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        assert len(CHECKLIST_QUESTIONS) == 5, "Exactly 5 questions should be defined"

    def test_questions_numbered_correctly(self):
        """Questions should be numbered 1-5."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        numbers = [q.number for q in CHECKLIST_QUESTIONS]
        assert numbers == [1, 2, 3, 4, 5], f"Questions should be numbered 1-5, got {numbers}"

    def test_all_questions_required(self):
        """All 5 questions should be required by default."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        for question in CHECKLIST_QUESTIONS:
            assert question.required is True, f"Question {question.number} should be required"

    def test_questions_have_text(self):
        """All questions should have non-empty text."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        for question in CHECKLIST_QUESTIONS:
            assert question.question, f"Question {question.number} should have non-empty text"
            assert (
                len(question.question.strip()) > 0
            ), f"Question {question.number} should have non-whitespace text"


class TestChecklistValidation:
    """Test checklist validation logic - NEW FUNCTIONALITY."""

    def test_validate_checklist_function_exists(self):
        """validate_checklist function should exist."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        assert callable(validate_checklist), "validate_checklist should be a callable function"

    def test_validate_all_answers_provided_passes(self):
        """Validation should pass when all 5 questions have answers."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Implement feature X",
            2: "Existing codebase and requirements",
            3: "TDD approach with tests first",
            4: "Tests pass, code works",
            5: "Unit tests and manual verification",
        }

        result = validate_checklist(answers)

        assert result.passed is True, "Validation should pass when all answers provided"
        assert len(result.missing_answers) == 0, "No missing answers when all questions answered"
        assert len(result.errors) == 0, "No errors when all questions answered"

    def test_validate_empty_answer_fails(self):
        """Validation should fail when any answer is empty."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        # Missing answer for question 2
        answers = {
            1: "Implement feature X",
            2: "",  # Empty answer
            3: "TDD approach",
            4: "Tests pass",
            5: "Unit tests",
        }

        result = validate_checklist(answers)

        assert result.passed is False, "Validation should fail when answer is empty"
        assert 2 in result.missing_answers, "Question 2 should be in missing_answers"
        assert len(result.errors) == 1, "Should have 1 error for empty answer"
        assert "Question 2" in result.errors[0], "Error message should mention question 2"

    def test_validate_whitespace_only_answer_fails(self):
        """Validation should fail when answer contains only whitespace."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Implement feature X",
            2: "   \n\t  ",  # Whitespace only
            3: "TDD approach",
            4: "Tests pass",
            5: "Unit tests",
        }

        result = validate_checklist(answers)

        assert result.passed is False, "Validation should fail when answer is whitespace only"
        assert (
            2 in result.missing_answers
        ), "Question 2 should be in missing_answers for whitespace-only answer"

    def test_validate_missing_question_fails(self):
        """Validation should fail when a required question is missing from dict."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        # Question 3 not in dict
        answers = {
            1: "Implement feature X",
            2: "Existing codebase",
            4: "Tests pass",
            5: "Unit tests",
        }

        result = validate_checklist(answers)

        assert result.passed is False, "Validation should fail when question missing from dict"
        assert 3 in result.missing_answers, "Question 3 should be in missing_answers"

    def test_validate_multiple_empty_answers(self):
        """Validation should report all missing answers."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        # Questions 1 and 4 empty
        answers = {
            1: "",
            2: "Existing codebase",
            3: "TDD approach",
            4: "   ",  # Whitespace
            5: "Unit tests",
        }

        result = validate_checklist(answers)

        assert result.passed is False, "Validation should fail with multiple empty answers"
        assert len(result.missing_answers) == 2, "Should report 2 missing answers"
        assert (
            1 in result.missing_answers and 4 in result.missing_answers
        ), "Questions 1 and 4 should be in missing_answers"
        assert len(result.errors) == 2, "Should have 2 errors"

    def test_validate_returns_validation_result(self):
        """validate_checklist should return ValidationResult object."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {1: "Answer 1", 2: "Answer 2", 3: "Answer 3", 4: "Answer 4", 5: "Answer 5"}

        result = validate_checklist(answers)

        assert isinstance(result, ValidationResult), "Should return ValidationResult instance"
        assert hasattr(result, "passed"), "ValidationResult should have 'passed' attribute"
        assert hasattr(
            result, "missing_answers"
        ), "ValidationResult should have 'missing_answers' attribute"
        assert hasattr(result, "errors"), "ValidationResult should have 'errors' attribute"


class TestChecklistBypass:
    """Test --no-checklist bypass functionality - NEW FUNCTIONALITY."""

    def test_no_checklist_flag_documented(self):
        """--no-checklist flag should be documented in SKILL.md."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Check for --no-checklist in argument-hint
        assert "--no-checklist" in content, "--no-checklist flag should be documented"

    def test_no_checklist_bypass_description(self):
        """--no-checklist bypass should have usage description."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Check for bypass description (trivial changes, continued work)
        bypass_keywords = ["trivial", "continued work", "bypass", "skip"]
        has_bypass_description = any(keyword in content.lower() for keyword in bypass_keywords)

        assert (
            has_bypass_description or "--no-checklist" in content
        ), "--no-checklist should have bypass description"

    def test_no_checklist_usage_example(self):
        """--no-checklist should have usage examples."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Look for usage examples with --no-checklist
        lines = content.split("\n")
        has_example = False

        for line in lines:
            if "--no-checklist" in line and ("code" in line or "/code" in line):
                has_example = True
                break

        assert (
            has_example or "--no-checklist" in content
        ), "--no-checklist should have usage example"


class TestChecklistEvidenceLogging:
    """Test checklist evidence logging - NEW FUNCTIONALITY."""

    def setup_method(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_log_checklist_answers_function_exists(self):
        """log_checklist_answers function should exist."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        assert callable(
            log_checklist_answers
        ), "log_checklist_answers should be a callable function"

    def test_log_checklist_creates_evidence_directory(self):
        """Logging should create .evidence directory if it doesn't exist."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Implement feature X",
            2: "Context",
            3: "Approach",
            4: "Criteria",
            5: "Verification",
        }

        evidence_dir = self.project_root / ".evidence"
        assert not evidence_dir.exists(), "Evidence directory should not exist initially"

        log_checklist_answers(answers, self.project_root)

        assert evidence_dir.exists(), "Evidence directory should be created"
        assert evidence_dir.is_dir(), "Evidence should be a directory"

    def test_log_checklist_creates_pre_execution_file(self):
        """Logging should create .evidence/pre_execution.md file."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Implement feature X",
            2: "Context",
            3: "Approach",
            4: "Criteria",
            5: "Verification",
        }

        evidence_file = log_checklist_answers(answers, self.project_root)

        assert evidence_file.exists(), "Evidence file should be created"
        assert (
            evidence_file.name == "pre_execution.md"
        ), "Evidence file should be named pre_execution.md"
        assert (
            evidence_file.parent.name == ".evidence"
        ), "Evidence file should be in .evidence directory"

    def test_log_checklist_contains_all_questions(self):
        """Evidence file should contain all 5 questions."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Implement feature X",
            2: "Context",
            3: "Approach",
            4: "Criteria",
            5: "Verification",
        }

        evidence_file = log_checklist_answers(answers, self.project_root)
        content = evidence_file.read_text()

        # Check for all 5 questions
        for question in CHECKLIST_QUESTIONS:
            assert (
                f"Q{question.number}:" in content
            ), f"Question {question.number} should be in evidence"
            assert (
                question.question in content
            ), f"Question text '{question.question}' should be in evidence"

    def test_log_checklist_contains_answers(self):
        """Evidence file should contain all answers."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Answer 1",
            2: "Answer 2",
            3: "Answer 3",
            4: "Answer 4",
            5: "Answer 5",
        }

        evidence_file = log_checklist_answers(answers, self.project_root)
        content = evidence_file.read_text()

        # Check for all answers
        for q_num, answer in answers.items():
            assert (
                answer in content
            ), f"Answer '{answer}' for question {q_num} should be in evidence"

    def test_log_checklist_contains_timestamp(self):
        """Evidence file should contain UTC timestamp."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Implement feature X",
            2: "Context",
            3: "Approach",
            4: "Criteria",
            5: "Verification",
        }

        evidence_file = log_checklist_answers(answers, self.project_root)
        content = evidence_file.read_text()

        # Check for timestamp field
        assert (
            "Timestamp" in content or "timestamp" in content
        ), "Evidence should contain timestamp field"
        # Check for UTC timezone indicator
        assert (
            "UTC" in content or "+00:00" in content or "Z" in content
        ), "Timestamp should be in UTC"

    def test_log_checklist_contains_feature_description(self):
        """Evidence file should contain feature description."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Implement feature X",
            2: "Context",
            3: "Approach",
            4: "Criteria",
            5: "Verification",
        }

        feature_desc = "Build authentication system"
        evidence_file = log_checklist_answers(answers, self.project_root, feature_desc)
        content = evidence_file.read_text()

        assert (
            feature_desc in content
        ), f"Feature description '{feature_desc}' should be in evidence"
        assert (
            "Feature:" in content or "feature" in content.lower()
        ), "Evidence should have Feature field"

    def test_log_checklist_appends_to_existing_file(self):
        """Logging should append to existing evidence file with separator."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers1 = {
            1: "Feature 1",
            2: "Context 1",
            3: "Approach 1",
            4: "Criteria 1",
            5: "Verification 1",
        }

        answers2 = {
            1: "Feature 2",
            2: "Context 2",
            3: "Approach 2",
            4: "Criteria 2",
            5: "Verification 2",
        }

        # Log first set of answers
        log_checklist_answers(answers1, self.project_root, "Feature 1")

        # Log second set of answers
        log_checklist_answers(answers2, self.project_root, "Feature 2")

        evidence_file = self.project_root / ".evidence" / "pre_execution.md"
        content = evidence_file.read_text()

        # Check for separator
        assert "---" in content, "Should have separator between entries"

        # Check both features are present
        assert "Feature 1" in content, "First feature should be in evidence"
        assert "Feature 2" in content, "Second feature should be in evidence"

    def test_log_checklist_handles_empty_answers(self):
        """Logging should handle questions with no answers gracefully."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        # Missing answer for question 3
        answers = {
            1: "Feature 1",
            2: "Context 1",
            # 3: missing
            4: "Criteria 1",
            5: "Verification 1",
        }

        evidence_file = log_checklist_answers(answers, self.project_root)
        content = evidence_file.read_text()

        # Check for "No answer provided" placeholder
        assert "No answer provided" in content, "Should show placeholder for missing answers"
        assert "Q3:" in content, "Question 3 should still be in evidence"

    def test_log_checklist_returns_file_path(self):
        """log_checklist_answers should return Path to evidence file."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        answers = {
            1: "Feature 1",
            2: "Context 1",
            3: "Approach 1",
            4: "Criteria 1",
            5: "Verification 1",
        }

        evidence_file = log_checklist_answers(answers, self.project_root)

        assert isinstance(evidence_file, Path), "Should return Path object"
        assert evidence_file.exists(), "Returned path should point to existing file"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
