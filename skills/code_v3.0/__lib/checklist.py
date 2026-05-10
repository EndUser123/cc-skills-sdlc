#!/usr/bin/env python3
"""
Pre-Execution Checklist Module for /code skill

Validates that all 5 pre-execution questions have non-empty answers
before starting development work. Logs answers to evidence file for audit trail.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ChecklistQuestion:
    """A single pre-execution checklist question."""
    number: int
    question: str
    required: bool = True


@dataclass
class ValidationResult:
    """Result of checklist validation."""
    passed: bool
    missing_answers: list[int]  # List of question numbers (1-5) with missing answers
    answers: dict[int, str]  # Answers keyed by question number (1-5)
    errors: list[str]  # Error messages for validation failures


class ChecklistValidationError(Exception):
    """Raised when checklist validation fails."""
    pass


# The 5 pre-execution questions
CHECKLIST_QUESTIONS = [
    ChecklistQuestion(
        number=1,
        question="What is being asked for?",
        required=True
    ),
    ChecklistQuestion(
        number=2,
        question="What context do you have?",
        required=True
    ),
    ChecklistQuestion(
        number=3,
        question="What is the implementation approach?",
        required=True
    ),
    ChecklistQuestion(
        number=4,
        question="What are the acceptance criteria?",
        required=True
    ),
    ChecklistQuestion(
        number=5,
        question="What verification is needed?",
        required=True
    ),
]


def _normalize_answer_keys(answers: dict[int, str] | dict[str, str]) -> dict[int, str]:
    """Normalize answer keys to integers (1-5).

    Args:
        answers: Dictionary of question IDs to user answers
            Keys can be integers (1-5) or strings ("q1"-"q5")

    Returns:
        Dictionary with integer keys (1-5)
    """
    normalized_answers: dict[int, str] = {}
    for key, value in answers.items():
        if isinstance(key, str):
            if key.startswith("q"):
                key = int(key[1:])
            else:
                try:
                    key = int(key)
                except ValueError:
                    continue
        normalized_answers[key] = value
    return normalized_answers


def validate_checklist(answers: dict[int, str] | dict[str, str]) -> ValidationResult:
    """Validate checklist answers and return ValidationResult.

    This is a convenience wrapper that converts the dict result to ValidationResult.
    Use validate_checklist_answers() for detailed dict output.

    Args:
        answers: Dictionary of question IDs to user answers
            Keys can be integers (1-5) or strings ("q1"-"q5")
            Values: User's answers to each question

    Returns:
        ValidationResult with passed status and missing questions
    """
    result = validate_checklist_answers(answers)
    return ValidationResult(
        passed=result["passed"],
        missing_answers=result["missing_numbers"],
        answers=result["normalized_answers"],
        errors=result["errors"]
    )


def validate_checklist_answers(answers: dict[int, str] | dict[str, str]) -> dict[str, Any]:
    """Validate that all checklist answers are non-empty.

    Args:
        answers: Dictionary of question IDs to user answers
            Keys can be integers (1-5) or strings ("q1"-"q5")
            Values: User's answers to each question

    Returns:
        dict: Validation result with keys:
            - passed (bool): True if all answers non-empty (or bypassed)
            - missing_numbers (list[int]): List of question numbers with empty answers
            - normalized_answers (dict[int, str]): Answers normalized to integer keys
            - errors (list[str]): Error messages for missing answers

    Note:
        Validation is bypassed when CODE_NO_CHECKLIST environment variable
        is set to "true". This allows --no-checklist flag to skip validation.
    """
    # Check for --no-checklist bypass flag
    bypass = os.environ.get("CODE_NO_CHECKLIST", "false").lower() == "true"

    if bypass:
        # Normalize answers even when bypassed (for logging)
        normalized_answers = _normalize_answer_keys(answers)

        # Return passed result with bypass indication
        return {
            "passed": True,
            "missing_numbers": [],
            "normalized_answers": normalized_answers,
            "errors": [],
            "bypassed": True
        }

    # Normalize answer keys to integers (1-5)
    normalized_answers = _normalize_answer_keys(answers)

    # All 5 questions must have non-empty answers
    required_questions = [1, 2, 3, 4, 5]

    # Check for empty or whitespace-only answers
    missing_numbers: list[int] = []
    errors: list[str] = []
    for q_num in required_questions:
        answer = normalized_answers.get(q_num, "").strip()
        if not answer:
            missing_numbers.append(q_num)
            errors.append(f"Question {q_num} requires a non-empty answer")

    passed = len(missing_numbers) == 0

    return {
        "passed": passed,
        "missing_numbers": missing_numbers,
        "normalized_answers": normalized_answers,
        "errors": errors
    }


def log_checklist_answers(
    answers: dict[int, str] | dict[str, str],
    evidence_dir: Path,
    terminal_id: str | None = None
) -> Path | None:
    """Log checklist answers to evidence file for audit trail.

    Args:
        answers: Dictionary of question IDs to user answers
            Keys can be integers (1-5) or strings ("q1"-"q5")
        evidence_dir: Base directory for evidence files
        terminal_id: Terminal ID for multi-terminal isolation

    Returns:
        Path: Path to created evidence file, or None if bypassed

    Note:
        Evidence creation is bypassed when CODE_NO_CHECKLIST environment variable
        is set to "true". This prevents evidence file creation during bypass.
    """
    # Check for --no-checklist bypass flag
    bypass = os.environ.get("CODE_NO_CHECKLIST", "false").lower() == "true"

    if bypass:
        # Return None to indicate no evidence file created
        return None

    # Normalize answer keys to integers (1-5)
    normalized_answers = _normalize_answer_keys(answers)

    # Build evidence directory path with terminal isolation
    evidence_path = evidence_dir / "pre_execution"
    if terminal_id:
        evidence_path = evidence_path / terminal_id
    else:
        evidence_path = evidence_path / "default"

    # Create filename with timestamp
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    evidence_file = evidence_path / f"checklist_{timestamp}.md"

    # CRITICAL FIX: Create parent directories before writing file
    # This ensures the terminal-specific directory exists
    evidence_file.parent.mkdir(parents=True, exist_ok=True)

    # Format answers for logging
    questions = {
        1: "1. What is being asked for?",
        2: "2. What context do you have?",
        3: "3. What is the implementation approach?",
        4: "4. What are the acceptance criteria?",
        5: "5. What verification is needed?"
    }

    # Write markdown evidence file
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write("# Pre-Execution Checklist\n")
        f.write(f"**Timestamp**: {datetime.now(UTC).isoformat()}\n")
        if terminal_id:
            f.write(f"**Terminal ID**: {terminal_id}\n")
        f.write("\n")

        for q_num in [1, 2, 3, 4, 5]:
            question = questions.get(q_num, f"{q_num}.")
            answer = normalized_answers.get(q_num, "").strip()

            f.write(f"## {question}\n\n")
            f.write(f"**Answer**: {answer if answer else '(empty)'}\n\n")

    return evidence_file


def main():
    """Module main function for testing."""
    # Example usage
    sample_answers = {
        1: "Implement user authentication with JWT",
        2: "Read CLAUDE.md, searched for existing auth implementations",
        3: "Modify auth.py, add tests, moderate difficulty",
        4: "Tests pass, JWT tokens work correctly",
        5: "Unit tests, manual verification, rollback via git revert"
    }

    result = validate_checklist_answers(sample_answers)
    print(f"Validation result: {result}")

    evidence_file = log_checklist_answers(
        sample_answers,
        Path("P:\\\\\\.claude/skills/code"),
        terminal_id="test_terminal"
    )
    print(f"Evidence logged to: {evidence_file}")


if __name__ == "__main__":
    main()
