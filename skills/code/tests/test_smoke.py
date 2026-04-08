#!/usr/bin/env python3
"""Smoke tests for Core Plan workflow - simulates actual user commands."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tdd.lib.evidence_writer import generate_evidence_artifact

    from lib.checklist import log_checklist_answers, validate_checklist
    from lib.task_detector import detect_task_type, log_detection_decision

    ALL_FEATURES_AVAILABLE = True
except ImportError as e:
    ALL_FEATURES_AVAILABLE = False
    IMPORT_ERROR = str(e)


class TestSmokeCorePlanWorkflow:
    """Smoke tests for Core Plan v1 workflow - simulates real user scenarios."""

    def setup_method(self):
        """Set up temporary project directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

        # Enable evidence tracking for tests
        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        os.environ.pop("TDD_EVIDENCE_TRACKING_ENABLED", None)

    def test_smoke_user_creates_feature_with_evidence(self):
        """SMOKE TEST: User creates feature with TDD evidence tracking.

        Scenario:
        1. User starts RED phase (writes test)
        2. Evidence tracking creates RED artifact
        3. User completes GREEN phase (implementation passes)
        4. Evidence tracking creates GREEN artifact
        5. User completes REFACTOR phase (cleanup)
        6. Evidence tracking creates REFACTOR artifact

        Expected: All artifacts created with timestamps in .evidence/
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        task_id = "SMOKE-001"

        # Phase 1: RED - Write failing test
        red_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="RED",
            evidence={
                "test_files": ["test_feature.py"],
                "test_status": "FAILING",
                "requirement": "Test should fail initially",
            },
            skill_dir=self.project_root,
            terminal_id="smoke_test_terminal",
        )

        assert red_evidence.exists(), "RED evidence artifact should exist"
        red_content = red_evidence.read_text()
        assert "RED" in red_content, "RED phase should be documented"
        assert "Timestamp" in red_content, "Artifact should have timestamp"

        # Phase 2: GREEN - Implementation passes
        green_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="GREEN",
            evidence={
                "implementation": "Added feature X",
                "test_status": "PASSING",
                "test_results": "All tests pass",
            },
            skill_dir=self.project_root,
            terminal_id="smoke_test_terminal",
        )

        assert green_evidence.exists(), "GREEN evidence artifact should exist"
        green_content = green_evidence.read_text()
        assert "GREEN" in green_content, "GREEN phase should be documented"

        # Phase 3: REFACTOR - Code cleanup
        refactor_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="REFACTOR",
            evidence={
                "refactoring": "Cleaned up code structure",
                "test_status": "STILL_PASSING",
                "verification": "Tests still pass after refactor",
            },
            skill_dir=self.project_root,
            terminal_id="smoke_test_terminal",
        )

        assert refactor_evidence.exists(), "REFACTOR evidence artifact should exist"
        refactor_content = refactor_evidence.read_text()
        assert "REFACTOR" in refactor_content, "REFACTOR phase should be documented"

        # Verify all artifacts are in .evidence directory
        evidence_dir = self.project_root / ".evidence"
        assert evidence_dir.exists(), ".evidence directory should exist"
        evidence_files = list(evidence_dir.glob("*.md"))
        assert (
            len(evidence_files) == 3
        ), f"Should have 3 evidence files, found {len(evidence_files)}"

    def test_smoke_user_validates_checklist_before_coding(self):
        """SMOKE TEST: User completes pre-execution checklist before starting work.

        Scenario:
        1. User invokes /code for feature implementation
        2. Pre-execution checklist presented (5 questions)
        3. User answers all questions
        4. Validation passes
        5. Answers logged to .evidence/pre_execution.md

        Expected: Checklist validation passes, evidence logged
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        # User answers all 5 questions
        checklist_answers = {
            1: "Implement user authentication with JWT tokens",
            2: "Existing codebase has auth patterns in src/auth/",
            3: "TDD approach: RED → GREEN → REFACTOR cycle",
            4: "All tests pass, authentication works correctly",
            5: "Unit tests + integration tests + manual API verification",
        }

        # Validate checklist
        validation_result = validate_checklist(checklist_answers)

        assert validation_result.passed is True, "Checklist validation should pass"
        assert len(validation_result.missing_answers) == 0, "No missing answers"
        assert len(validation_result.errors) == 0, "No validation errors"

        # Log answers to evidence
        evidence_file = log_checklist_answers(
            checklist_answers,
            self.project_root,
            "User authentication feature",
        )

        assert evidence_file.exists(), "Checklist evidence file should exist"
        assert (
            evidence_file.name == "pre_execution.md"
        ), "Evidence file should be named pre_execution.md"

        content = evidence_file.read_text()
        assert "User authentication feature" in content, "Feature description should be in evidence"

        # Verify all 5 questions are logged
        for q_num in range(1, 6):
            assert f"Q{q_num}:" in content, f"Question {q_num} should be in evidence"

    def test_smoke_task_detection_auto_enables_ralph_loop(self):
        """SMOKE TEST: Task type detection auto-enables Ralph Loop for implementation tasks.

        Scenario:
        1. User types: /code "implement user authentication"
        2. Task detector analyzes query
        3. Detected as IMPLEMENTATION task
        4. Ralph Loop auto-enabled
        5. Decision logged to .evidence/ralph_auto_detection.md

        Expected: Ralph Loop enabled for implementation, logged to evidence
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        # User query for implementation task
        user_query = "implement user authentication system"

        # Task type detection
        detection_result = detect_task_type(user_query)

        assert (
            detection_result.task_type.value == "IMPLEMENTATION"
        ), "Should detect as IMPLEMENTATION task"
        assert (
            detection_result.enable_ralph_loop is True
        ), "Ralph Loop should be auto-enabled for implementation"
        assert (
            detection_result.confidence >= 0.6
        ), "Detection confidence should be moderate or higher"

        # Log decision to evidence
        evidence_file = log_detection_decision(
            result=detection_result,
            query=user_query,
            project_root=self.project_root,
        )

        assert evidence_file.exists(), "Detection evidence file should exist"
        assert (
            evidence_file.name == "ralph_auto_detection.md"
        ), "Evidence file should be named ralph_auto_detection.md"

        content = evidence_file.read_text()
        assert "IMPLEMENTATION" in content, "Task type should be in evidence"
        assert "ENABLED" in content, "Ralph Loop enabled should be in evidence"
        assert user_query in content, "Original query should be in evidence"

    def test_smoke_task_detection_auto_disables_ralph_loop_for_research(self):
        """SMOKE TEST: Task type detection auto-disables Ralph Loop for research tasks.

        Scenario:
        1. User types: /code "research authentication patterns"
        2. Task detector analyzes query
        3. Detected as RESEARCH task
        4. Ralph Loop auto-disabled
        5. Decision logged to .evidence/ralph_auto_detection.md

        Expected: Ralph Loop disabled for research, logged to evidence
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        # User query for research task
        user_query = "research authentication patterns and best practices"

        # Task type detection
        detection_result = detect_task_type(user_query)

        assert detection_result.task_type.value == "RESEARCH", "Should detect as RESEARCH task"
        assert (
            detection_result.enable_ralph_loop is False
        ), "Ralph Loop should be auto-disabled for research"
        assert (
            detection_result.confidence >= 0.6
        ), "Detection confidence should be moderate or higher"

        # Log decision to evidence
        evidence_file = log_detection_decision(
            result=detection_result,
            query=user_query,
            project_root=self.project_root,
        )

        assert evidence_file.exists(), "Detection evidence file should exist"

        content = evidence_file.read_text()
        assert "RESEARCH" in content, "Task type should be in evidence"
        assert "DISABLED" in content, "Ralph Loop disabled should be in evidence"
        assert user_query in content, "Original query should be in evidence"

    def test_smoke_end_to_end_core_plan_workflow(self):
        """SMOKE TEST: Complete Core Plan v1 workflow - all three features working together.

        Scenario:
        1. User invokes /code "implement feature X"
        2. Pre-execution checklist validated
        3. Task type detected (IMPLEMENTATION → Ralph Loop enabled)
        4. TDD cycle creates evidence artifacts
        5. All evidence written to .evidence/

        Expected: Complete workflow succeeds, all evidence created
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        # Step 1: Pre-execution checklist
        checklist_answers = {
            1: "Implement feature X",
            2: "Existing codebase context",
            3: "TDD approach",
            4: "Tests pass",
            5: "Unit tests",
        }

        validation_result = validate_checklist(checklist_answers)
        assert validation_result.passed, "Checklist should validate"

        log_checklist_answers(checklist_answers, self.project_root, "Feature X")

        # Step 2: Task type detection
        query = "implement feature X with tests"
        detection_result = detect_task_type(query)

        assert (
            detection_result.enable_ralph_loop is True
        ), "Ralph Loop should be enabled for implementation"

        log_detection_decision(detection_result, query, self.project_root)

        # Step 3: TDD evidence tracking
        task_id = "SMOKE-E2E-001"

        # RED phase
        red_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="RED",
            evidence={"test_files": ["test_feature_x.py"]},
            skill_dir=self.project_root,
            terminal_id="smoke_e2e_terminal",
        )

        # GREEN phase
        green_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="GREEN",
            evidence={"implementation": "Feature X implemented"},
            skill_dir=self.project_root,
            terminal_id="smoke_e2e_terminal",
        )

        # REFACTOR phase
        refactor_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="REFACTOR",
            evidence={"refactoring": "Code cleaned up"},
            skill_dir=self.project_root,
            terminal_id="smoke_e2e_terminal",
        )

        # Verify all evidence files exist
        evidence_dir = self.project_root / ".evidence"
        assert evidence_dir.exists(), ".evidence directory should exist"

        evidence_files = list(evidence_dir.glob("*.md"))
        assert (
            len(evidence_files) == 4
        ), f"Should have 4 evidence files (checklist + detection + 3 TDD), found {len(evidence_files)}"

        # Verify specific files exist
        assert (evidence_dir / "pre_execution.md").exists(), "Checklist evidence should exist"
        assert (
            evidence_dir / "ralph_auto_detection.md"
        ).exists(), "Detection evidence should exist"

        # Verify TDD evidence files exist (names contain task_id and phase)
        tdd_files = [f for f in evidence_files if "SMOKE-E2E-001" in f.name]
        assert (
            len(tdd_files) == 3
        ), f"Should have 3 TDD evidence files (RED, GREEN, REFACTOR), found {len(tdd_files)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
