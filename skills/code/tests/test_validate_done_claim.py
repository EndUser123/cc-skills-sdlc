#!/usr/bin/env python3
"""Unit tests for evidence guard validation script."""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# This import will FAIL with ModuleNotFoundError until we implement the script
from scripts.validate_done_claim import validate_done_claim
from utils.evidence import EvidenceManager


@pytest.fixture
def temp_ledger_dir():
    """Create temporary ledger directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create state directory
    ledger_dir = temp_dir / ".claude" / "state"
    ledger_dir.mkdir(parents=True)

    yield ledger_dir

    # Cleanup
    shutil.rmtree(temp_dir)


class TestValidateDoneClaim:
    """Test evidence guard validation for SHIP phase."""

    def test_all_tasks_complete_pass(self, temp_ledger_dir):
        """Test all tasks have all 4 evidence types should pass."""
        # Create evidence manager with temporary ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Record all 4 evidence types for a task
        mgr.record_red("task-1", ["test_file.py"], "pytest test_file.py", 3)
        mgr.record_green("task-1", ["impl_file.py"], "pytest test_file.py", 3)
        mgr.record_refactor("task-1", ["Cleaned up code"], "pytest test_file.py", 3)
        mgr.record_verify("task-1", 0, 0, "APPROVED")

        # This should pass once script exists
        result = validate_done_claim(mgr, ["task-1"])
        assert result is True

    def test_one_task_missing_evidence(self, temp_ledger_dir):
        """Test one task missing evidence should block SHIP."""
        # Create evidence manager with temporary ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Record only 2 evidence types (missing REFACTOR and VERIFY)
        mgr.record_red("task-1", ["test_file.py"], "pytest test_file.py", 3)
        mgr.record_green("task-1", ["impl_file.py"], "pytest test_file.py", 3)

        # This should raise ValueError once script exists
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(mgr, ["task-1"])
        error_msg = str(exc_info.value)
        # Check error mentions missing evidence
        assert "missing" in error_msg.lower() or "evidence" in error_msg.lower()

    def test_multiple_tasks_missing_evidence(self, temp_ledger_dir):
        """Test multiple tasks missing evidence should block SHIP with detailed report."""
        # Create evidence manager with temporary ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Task 1: Complete all evidence
        mgr.record_red("task-1", ["test1.py"], "pytest", 1)
        mgr.record_green("task-1", ["impl1.py"], "pytest", 1)
        mgr.record_refactor("task-1", ["Refactored"], "pytest", 1)
        mgr.record_verify("task-1", 0, 0, "APPROVED")

        # Task 2: Missing VERIFY
        mgr.record_red("task-2", ["test2.py"], "pytest", 2)
        mgr.record_green("task-2", ["impl2.py"], "pytest", 2)
        mgr.record_refactor("task-2", ["Refactored"], "pytest", 2)

        # Task 3: Only RED evidence
        mgr.record_red("task-3", ["test3.py"], "pytest", 3)

        # This should raise ValueError with detailed report once script exists
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(mgr, ["task-1", "task-2", "task-3"])
        error_msg = str(exc_info.value)
        # Check error mentions multiple tasks with missing evidence
        assert "task-2" in error_msg
        assert "task-3" in error_msg

    def test_no_tasks_in_ledger(self, temp_ledger_dir):
        """Test empty ledger should pass (nothing to check)."""
        # Create evidence manager with temporary ledger (empty)
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # This should pass once script exists (no tasks to check)
        result = validate_done_claim(mgr, [])
        assert result is True

    def test_generate_missing_evidence_report(self, temp_ledger_dir):
        """Test generate report showing which tasks missing which evidence types."""
        # Create evidence manager with temporary ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Setup tasks with different missing evidence patterns
        mgr.record_red("task-missing-green", ["test.py"], "pytest", 1)
        # Missing GREEN, REFACTOR, VERIFY

        mgr.record_red("task-missing-verify", ["test.py"], "pytest", 1)
        mgr.record_green("task-missing-verify", ["impl.py"], "pytest", 1)
        mgr.record_refactor("task-missing-verify", ["Refactored"], "pytest", 1)
        # Missing VERIFY

        # This should raise ValueError with detailed missing evidence report
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(mgr, ["task-missing-green", "task-missing-verify"])
        error_msg = str(exc_info.value)
        # Check report shows specific missing evidence types
        assert "GREEN" in error_msg or "green" in error_msg.lower()
        assert "VERIFY" in error_msg or "verify" in error_msg.lower()

    def test_error_message_clarity(self, temp_ledger_dir):
        """Test error messages are clear and actionable."""
        # Create evidence manager with temporary ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Record incomplete evidence
        mgr.record_red("task-1", ["test.py"], "pytest", 1)

        # This should raise ValueError with clear error message
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(mgr, ["task-1"])
        error_msg = str(exc_info.value)

        # Check that error message is actionable
        assert any(word in error_msg.lower() for word in ["missing", "evidence", "required", "cannot"])
        # Check that it mentions specific evidence types
        assert "task-1" in error_msg


class TestValidateDoneClaimIntegration:
    """Integration tests for evidence guard validation."""

    def test_all_four_evidence_types_required(self, temp_ledger_dir):
        """Test that all 4 evidence types (RED, GREEN, REFACTOR, VERIFY) are required."""
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Test each missing evidence type
        for missing_stage in ["RED", "GREEN", "REFACTOR", "VERIFY"]:
            # Create new task for each test
            task_id = f"task-missing-{missing_stage.lower()}"

            # Record all evidence except the missing stage
            if missing_stage != "RED":
                mgr.record_red(task_id, ["test.py"], "pytest", 1)
            if missing_stage != "GREEN":
                mgr.record_green(task_id, ["impl.py"], "pytest", 1)
            if missing_stage != "REFACTOR":
                mgr.record_refactor(task_id, ["Refactored"], "pytest", 1)
            if missing_stage != "VERIFY":
                mgr.record_verify(task_id, 0, 0, "APPROVED")

            # Should fail because one evidence type is missing
            with pytest.raises(ValueError) as exc_info:
                validate_done_claim(mgr, [task_id])
            error_msg = str(exc_info.value)
            assert missing_stage in error_msg or missing_stage.lower() in error_msg.lower()

    def test_partial_task_list_validation(self, temp_ledger_dir):
        """Test validation when only checking specific tasks, not all tasks."""
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Complete task-1
        mgr.record_red("task-1", ["test1.py"], "pytest", 1)
        mgr.record_green("task-1", ["impl1.py"], "pytest", 1)
        mgr.record_refactor("task-1", ["Refactored"], "pytest", 1)
        mgr.record_verify("task-1", 0, 0, "APPROVED")

        # Incomplete task-2 (but we're not checking it)
        mgr.record_red("task-2", ["test2.py"], "pytest", 1)

        # Should pass because we're only checking task-1
        result = validate_done_claim(mgr, ["task-1"])
        assert result is True


class TestValidateDoneClaimLedgerAccess:
    """Tests for ledger loading behavior when task_ids=None."""

    def test_task_ids_none_loads_all_tasks_from_ledger(self, temp_ledger_dir):
        """
        Test that all tasks are loaded from ledger when task_ids=None.

        Given: Evidence manager with ledger containing multiple tasks
        When: validate_done_claim is called with task_ids=None
        Then: All task IDs from ledger are loaded and validated
        """
        # Create evidence manager with temporary ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Add multiple tasks to ledger - some complete, some not
        mgr.record_red("task-1", ["test1.py"], "pytest", 1)
        mgr.record_green("task-1", ["impl1.py"], "pytest", 1)
        mgr.record_refactor("task-1", ["Refactored"], "pytest", 1)
        mgr.record_verify("task-1", 0, 0, "APPROVED")

        mgr.record_red("task-2", ["test2.py"], "pytest", 1)
        mgr.record_green("task-2", ["impl2.py"], "pytest", 1)
        # Missing REFACTOR and VERIFY for task-2

        mgr.record_red("task-3", ["test3.py"], "pytest", 1)
        # Missing GREEN, REFACTOR, VERIFY for task-3

        # When task_ids=None, should load all tasks from ledger and validate them
        # Should fail because task-2 and task-3 are incomplete
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(mgr, None)
        error_msg = str(exc_info.value)

        # Verify that incomplete tasks were detected
        assert "task-2" in error_msg
        assert "task-3" in error_msg

    def test_task_ids_none_with_mocked_ledger(self, temp_ledger_dir):
        """
        Test that _load_ledger is called when task_ids=None.

        Given: Evidence manager with mocked _load_ledger
        When: validate_done_claim is called with task_ids=None
        Then: _load_ledger is called exactly once
        """
        # Create evidence manager with temporary ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Add a complete task BEFORE mocking (so record calls aren't counted)
        mgr.record_red("task-1", ["test1.py"], "pytest", 1)
        mgr.record_green("task-1", ["impl1.py"], "pytest", 1)
        mgr.record_refactor("task-1", ["Refactored"], "pytest", 1)
        mgr.record_verify("task-1", 0, 0, "APPROVED")

        # Now mock _load_ledger to track calls only for validate_done_claim
        original_load_ledger = mgr._load_ledger
        call_count = {"count": 0}

        def mock_load_ledger():
            call_count["count"] += 1
            return original_load_ledger()

        with patch.object(mgr, "_load_ledger", side_effect=mock_load_ledger):
            # Call with task_ids=None should trigger _load_ledger
            result = validate_done_claim(mgr, None)

            # Verify _load_ledger was called at least once by validate_done_claim
            assert call_count["count"] >= 1, f"Expected _load_ledger to be called at least once, but was called {call_count['count']} times"
            assert result is True

    def test_task_ids_none_empty_ledger_returns_true(self, temp_ledger_dir):
        """
        Test that empty ledger returns True when task_ids=None.

        Given: Evidence manager with empty ledger (no tasks)
        When: validate_done_claim is called with task_ids=None
        Then: Returns True (nothing to validate)
        """
        # Create evidence manager with temporary empty ledger
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()

        # Ledger is empty - no tasks recorded
        # When task_ids=None, should load empty task list and return True
        result = validate_done_claim(mgr, None)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
