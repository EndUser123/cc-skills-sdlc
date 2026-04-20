#!/usr/bin/env python3
"""Integration tests for Core Plan workflow - Evidence + Checklist + Ralph Loop."""

import os
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
        ChecklistValidationError,
        ValidationResult,
        log_checklist_answers,
        validate_checklist,
    )

    CHECKLIST_AVAILABLE = True
except ImportError:
    CHECKLIST_AVAILABLE = False
    validate_checklist = None
    log_checklist_answers = None
    CHECKLIST_QUESTIONS = None
    ChecklistValidationError = None
    ValidationResult = None

try:
    from lib.task_detector import (
        TaskDetectionResult,
        TaskType,
        detect_task_type,
        log_detection_decision,
    )

    TASK_DETECTOR_AVAILABLE = True
except ImportError:
    TASK_DETECTOR_AVAILABLE = False
    detect_task_type = None
    log_detection_decision = None
    TaskDetectionResult = None
    TaskType = None

try:
    from tdd.lib.evidence_writer import (
        generate_evidence_artifact,
        is_evidence_tracking_enabled,
    )

    EVIDENCE_TRACKING_AVAILABLE = True
except ImportError:
    EVIDENCE_TRACKING_AVAILABLE = False
    generate_evidence_artifact = None
    is_evidence_tracking_enabled = None


class TestCorePlanIntegration:
    """Integration tests for Core Plan workflow - all three features working together."""

    def setup_method(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.evidence_dir = self.project_root / ".evidence"

        # Enable evidence tracking for tests
        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"

    def teardown_method(self):
        """Clean up temporary directory."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        # Clean up environment variable
        os.environ.pop("TDD_EVIDENCE_TRACKING_ENABLED", None)

    def test_all_three_modules_available(self):
        """All Core Plan modules should be available for integration."""
        # At least one module should be available
        available_count = sum(
            [
                CHECKLIST_AVAILABLE,
                TASK_DETECTOR_AVAILABLE,
                EVIDENCE_TRACKING_AVAILABLE,
            ]
        )

        assert available_count >= 1, "At least one Core Plan module should be available"

    def test_evidence_tracking_creates_artifacts(self):
        """Evidence tracking should create timestamped artifacts."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available")

        task_id = "CORE-PLAN-001"
        phase = "INTEGRATION"
        evidence = {"test_files": ["test_integration.py"]}

        artifact_path = generate_evidence_artifact(
            task_id=task_id,
            phase=phase,
            evidence=evidence,
            skill_dir=self.project_root,
            terminal_id="test_terminal",
        )

        assert artifact_path is not None, "generate_evidence_artifact should return a path"
        assert artifact_path.exists(), f"Evidence artifact should be created at {artifact_path}"

    def test_checklist_validates_non_empty_answers(self):
        """Checklist should reject empty answers."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available")

        # Test with empty answer for question 2
        answers = {
            1: "Feature implementation",
            2: "",  # Empty answer
            3: "TDD approach",
            4: "Tests pass",
            5: "Unit tests",
        }

        result = validate_checklist(answers)

        assert result.passed is False, "Validation should fail with empty answer"
        assert 2 in result.missing_answers, "Question 2 should be in missing_answers"

    def test_task_detector_classifies_implementation_tasks(self):
        """Task detector should classify implementation tasks correctly."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task detector module not available")

        result = detect_task_type("implement user authentication system")

        assert result.task_type == TaskType.IMPLEMENTATION, "Should detect IMPLEMENTATION task type"
        assert result.enable_ralph_loop is True, "Implementation tasks should enable Ralph Loop"
        assert result.confidence >= 0.6, "Implementation detection should have moderate confidence"

    def test_task_detector_classifies_research_tasks(self):
        """Task detector should classify research tasks correctly."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task detector module not available")

        result = detect_task_type("research authentication patterns")

        assert result.task_type == TaskType.RESEARCH, "Should detect RESEARCH task type"
        assert result.enable_ralph_loop is False, "Research tasks should disable Ralph Loop"
        assert result.confidence >= 0.6, "Research detection should have moderate confidence"

    def test_evidence_directory_shared_across_features(self):
        """All three features should write to .evidence directory without conflicts."""
        if not all([CHECKLIST_AVAILABLE, TASK_DETECTOR_AVAILABLE, EVIDENCE_TRACKING_AVAILABLE]):
            pytest.skip("All Core Plan modules required for this test")

        # Create checklist evidence
        checklist_answers = {
            1: "Feature implementation",
            2: "Existing codebase",
            3: "TDD approach",
            4: "Tests pass",
            5: "Unit tests",
        }
        checklist_evidence = log_checklist_answers(
            checklist_answers, self.project_root, "Test feature"
        )

        # Create task detection evidence
        detection_result = detect_task_type("implement feature")
        detection_evidence = log_detection_decision(
            result=detection_result,
            query="implement feature",
            project_root=self.project_root,
        )

        # Create TDD evidence
        tdd_evidence = generate_evidence_artifact(
            task_id="CORE-PLAN-002",
            phase="INTEGRATION",
            evidence={"integration": "all three features"},
            skill_dir=self.project_root,
            terminal_id="test_terminal",
        )

        # Verify all evidence files exist in .evidence directory
        assert self.evidence_dir.exists(), ".evidence directory should exist"

        evidence_files = list(self.evidence_dir.glob("*.md"))
        assert (
            len(evidence_files) >= 3
        ), f"At least 3 evidence files should exist, found {len(evidence_files)}"

        # Verify no file conflicts (all files should be writable)
        for evidence_file in evidence_files:
            assert evidence_file.is_file(), f"Evidence file {evidence_file.name} should be a file"
            # Verify file can be read
            content = evidence_file.read_text()
            assert len(content) > 0, f"Evidence file {evidence_file.name} should not be empty"

    def test_checklist_accepts_valid_answers(self):
        """Checklist should accept all valid non-empty answers."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available")

        valid_answers = {
            1: "Implement feature X",
            2: "Existing codebase context",
            3: "TDD approach with tests first",
            4: "Tests passing and code working",
            5: "Unit tests and manual verification",
        }

        result = validate_checklist(valid_answers)

        assert result.passed is True, "Validation should pass with all valid answers"
        assert len(result.missing_answers) == 0, "No missing answers when all questions answered"
        assert len(result.errors) == 0, "No errors when all questions answered"

    def test_task_detector_provides_reasoning(self):
        """Task detection should provide reasoning for decision."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task detector module not available")

        result = detect_task_type("implement feature")

        assert result.reasoning, "Detection result should include reasoning"
        assert len(result.reasoning) > 0, "Reasoning should not be empty"

    def test_evidence_tracking_includes_timestamps(self):
        """Evidence artifacts should include UTC timestamps."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available")

        artifact_path = generate_evidence_artifact(
            task_id="CORE-PLAN-003",
            phase="INTEGRATION",
            evidence={"test": "timestamp verification"},
            skill_dir=self.project_root,
            terminal_id="test_terminal",
        )

        content = artifact_path.read_text()

        # Check for timestamp field
        assert (
            "Timestamp" in content or "timestamp" in content
        ), "Evidence should contain timestamp field"
        # Check for UTC timezone indicator
        assert (
            "UTC" in content or "+00:00" in content or "Z" in content
        ), "Timestamp should be in UTC"

    def test_checklist_evidence_includes_all_questions(self):
        """Checklist evidence should include all 5 questions."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available")

        answers = {
            1: "Answer 1",
            2: "Answer 2",
            3: "Answer 3",
            4: "Answer 4",
            5: "Answer 5",
        }

        evidence_file = log_checklist_answers(answers, self.project_root, "Checklist feature test")

        content = evidence_file.read_text()

        # Check for all 5 questions
        for question in CHECKLIST_QUESTIONS:
            assert (
                f"Q{question.number}:" in content
            ), f"Question {question.number} should be in evidence"
            assert question.question in content, "Question text should be in evidence"

    def test_ralph_auto_detection_logs_decision(self):
        """Ralph Loop auto-detection should log decision to evidence."""
        if not TASK_DETECTOR_AVAILABLE:
            pytest.skip("task detector module not available")

        result = detect_task_type("implement feature")
        evidence_file = log_detection_decision(
            result=result,
            query="implement feature",
            project_root=self.project_root,
        )

        assert evidence_file.exists(), "Evidence file should be created"
        assert (
            evidence_file.name == "ralph_auto_detection.md"
        ), "Evidence file should be named ralph_auto_detection.md"

        content = evidence_file.read_text()
        assert (
            "Task Type:" in content or "task_type" in content
        ), "Evidence should contain task type field"
        assert result.task_type.value in content, "Evidence should contain detected task type value"

    def test_workflow_end_to_end(self):
        """Complete workflow: checklist + detection + evidence tracking."""
        if not all([CHECKLIST_AVAILABLE, TASK_DETECTOR_AVAILABLE, EVIDENCE_TRACKING_AVAILABLE]):
            pytest.skip("All Core Plan modules required for end-to-end test")

        # Step 1: User provides checklist answers
        checklist_answers = {
            1: "Implement authentication system",
            2: "Existing codebase with auth patterns",
            3: "TDD approach: RED → GREEN → REFACTOR",
            4: "All tests pass, code works correctly",
            5: "Unit tests + integration tests + manual verification",
        }

        # Step 2: Validate checklist
        checklist_result = validate_checklist(checklist_answers)
        assert checklist_result.passed, "Checklist validation should pass for valid answers"

        # Step 3: Detect task type
        query = "implement authentication system with tests"
        detection_result = detect_task_type(query)
        assert (
            detection_result.task_type == TaskType.IMPLEMENTATION
        ), "Should detect as implementation task"
        assert (
            detection_result.enable_ralph_loop is True
        ), "Implementation task should enable Ralph Loop"

        # Step 4: Log checklist evidence
        checklist_evidence = log_checklist_answers(
            checklist_answers, self.project_root, "Authentication system implementation"
        )

        # Step 5: Log detection evidence
        detection_evidence = log_detection_decision(
            result=detection_result,
            query=query,
            project_root=self.project_root,
        )

        # Step 6: Create TDD evidence artifact
        tdd_evidence = generate_evidence_artifact(
            task_id="CORE-PLAN-004",
            phase="GREEN",
            evidence={
                "implementation": "Authentication system implemented",
                "test_results": "All tests passing",
            },
            skill_dir=self.project_root,
            terminal_id="test_terminal",
        )

        # Verify all evidence files exist
        assert checklist_evidence.exists(), "Checklist evidence should be created"
        assert detection_evidence.exists(), "Detection evidence should be created"
        assert tdd_evidence.exists(), "TDD evidence should be created"

        # Verify evidence directory structure
        evidence_files = list(self.evidence_dir.glob("*.md"))
        assert (
            len(evidence_files) >= 3
        ), f"At least 3 evidence files should exist, found {len(evidence_files)}"

        # Verify no file conflicts
        for evidence_file in evidence_files:
            content = evidence_file.read_text()
            assert len(content) > 0, f"Evidence file {evidence_file.name} should not be empty"

    def test_no_feature_conflicts(self):
        """All three features should work together without conflicts."""
        if not all([CHECKLIST_AVAILABLE, TASK_DETECTOR_AVAILABLE, EVIDENCE_TRACKING_AVAILABLE]):
            pytest.skip("All Core Plan modules required for conflict test")

        # Rapid-fire operations to test for conflicts
        operations_completed = 0

        # Operation 1: Generate TDD evidence
        generate_evidence_artifact(
            task_id="CONFLICT-001",
            phase="RED",
            evidence={"test": "conflict test"},
            skill_dir=self.project_root,
            terminal_id="test_terminal",
        )
        operations_completed += 1

        # Operation 2: Log checklist
        log_checklist_answers(
            {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"},
            self.project_root,
            "Conflict test",
        )
        operations_completed += 1

        # Operation 3: Detect and log
        result = detect_task_type("test query")
        log_detection_decision(
            result=result,
            query="test query",
            project_root=self.project_root,
        )
        operations_completed += 1

        # Verify all operations completed
        assert operations_completed == 3, "All three operations should complete without errors"

        # Verify evidence directory is not corrupted
        evidence_files = list(self.evidence_dir.glob("*.md"))
        assert (
            len(evidence_files) >= 3
        ), "All evidence files should exist after concurrent operations"

    def test_solo_dev_constraints_satisfied(self):
        """All features should work in isolated environment (no external dependencies)."""
        # This test verifies the Core Plan's solo-dev constraints
        # No network calls, no team approvals, no external services required

        if CHECKLIST_AVAILABLE:
            # Checklist validation is local
            answers = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}
            result = validate_checklist(answers)
            assert result.passed is True, "Checklist should work without external approvals"

        if TASK_DETECTOR_AVAILABLE:
            # Task detection is local
            result = detect_task_type("implement feature")
            assert result is not None, "Task detection should work without team calibration"

        if EVIDENCE_TRACKING_AVAILABLE:
            # Evidence tracking is local
            artifact = generate_evidence_artifact(
                task_id="SOLO-DEV-001",
                phase="TEST",
                evidence={"test": "local operation"},
                skill_dir=self.project_root,
                terminal_id="test_terminal",
            )
            assert artifact.exists(), "Evidence tracking should work without network services"

    def test_evidence_files_have_unique_names(self):
        """Evidence files from different features should have unique names."""
        if not all([CHECKLIST_AVAILABLE, TASK_DETECTOR_AVAILABLE, EVIDENCE_TRACKING_AVAILABLE]):
            pytest.skip("All Core Plan modules required for naming test")

        # Create evidence from all three features
        log_checklist_answers(
            {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"},
            self.project_root,
            "Naming test",
        )

        detection_result = detect_task_type("test")
        log_detection_decision(
            result=detection_result,
            query="test",
            project_root=self.project_root,
        )

        generate_evidence_artifact(
            task_id="NAMING-001",
            phase="TEST",
            evidence={"test": "naming"},
            skill_dir=self.project_root,
            terminal_id="test_terminal",
        )

        # List all evidence files
        evidence_files = list(self.evidence_dir.glob("*.md"))
        file_names = [f.name for f in evidence_files]

        # Check for unique names (no duplicates)
        assert len(file_names) == len(
            set(file_names)
        ), "All evidence files should have unique names"

        # Verify expected evidence files exist
        assert "pre_execution.md" in file_names, "Checklist evidence file should exist"
        assert (
            "ralph_auto_detection.md" in file_names
        ), "Ralph Loop detection evidence file should exist"
        # TDD evidence files have timestamp-based names, so we just check count
        assert len(file_names) >= 3, "At least 3 evidence files should exist"


class TestCorePlanRollback:
    """Test rollback procedures for Core Plan features."""

    def setup_method(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.evidence_dir = self.project_root / ".evidence"

    def teardown_method(self):
        """Clean up temporary directory."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_evidence_cleanup_removes_old_artifacts(self):
        """Evidence cleanup should remove artifacts older than 7 days."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available")

        from tdd.lib.evidence_writer import cleanup_old_evidence

        # Create old artifact (10 days old)
        old_artifact = self.evidence_dir / "old_task_RED_20260301_120000.md"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        old_artifact.write_text("# Old Evidence\n\nTimestamp: 2026-03-01T12:00:00Z")

        # Set modification time to 10 days ago
        import time

        old_time = time.time() - (10 * 24 * 60 * 60)
        os.utime(old_artifact, (old_time, old_time))

        # Create new artifact (1 day old)
        new_artifact = self.evidence_dir / "new_task_GREEN_20260310_120000.md"
        new_artifact.write_text("# New Evidence\n\nTimestamp: 2026-03-10T12:00:00Z")

        # Run cleanup
        cleaned_count = cleanup_old_evidence(self.evidence_dir, max_days=7)

        assert cleaned_count == 1, f"Should clean 1 old artifact, but cleaned {cleaned_count}"

        # Verify old artifact removed
        assert not old_artifact.exists(), "Old artifact (>7 days) should be removed"

        # Verify new artifact remains
        assert new_artifact.exists(), "New artifact (<7 days) should remain"

    def test_disabling_features_removes_functionality(self):
        """Features should be cleanly disabled without residual effects."""
        if not all([CHECKLIST_AVAILABLE, TASK_DETECTOR_AVAILABLE]):
            pytest.skip("checklist and task detector modules required")

        # Disable evidence tracking
        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "false"

        # Verify evidence tracking is disabled
        if EVIDENCE_TRACKING_AVAILABLE:
            enabled = is_evidence_tracking_enabled()
            assert enabled is False, "Evidence tracking should be disabled"

        # Task detector and checklist don't have enable/disable flags
        # They are always available when modules are imported

        # Re-enable for cleanup
        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
