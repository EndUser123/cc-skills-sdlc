#!/usr/bin/env python3
"""
Unit tests for plan_updater.py module.

Tests cover:
1. Plan reading and parsing
2. Task status updates (single and batch)
3. Status marker detection and replacement
4. Backup creation and restoration
5. Error handling for missing files/tasks
"""

import os

# Add utils directory to path for imports
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

from plan_updater import (
    PlanUpdater,
    TaskStatus,
    get_plan_tasks,
    update_plan_task_status,
)


class TestPlanUpdaterReading:
    """Test plan reading and task parsing."""

    def test_read_nonexistent_plan(self):
        """Reading a non-existent plan should return False."""
        updater = PlanUpdater("/nonexistent/plan.md")
        assert not updater.read_plan()

    def test_read_valid_plan(self):
        """Reading a valid plan should parse tasks correctly."""
        plan_content = """
# Test Plan

## Tasks

**TASK-001**: First task
**TASK-002**: Second task

## Notes
Some notes here.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            assert updater.read_plan()

            tasks = updater.get_tasks()
            assert len(tasks) == 2
            assert "TASK-001" in tasks
            assert "TASK-002" in tasks
            assert tasks["TASK-001"].title == "First task"
            assert tasks["TASK-002"].title == "Second task"
        finally:
            os.unlink(plan_path)

    def test_parse_tasks_with_status_markers(self):
        """Tasks with existing status markers should be parsed correctly."""
        plan_content = """
# Test Plan

**TASK-001**: [STARTED] First task
**TASK-002**: Second task
**TASK-003**: [FINISHED] Third task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            assert updater.read_plan()

            tasks = updater.get_tasks()
            assert tasks["TASK-001"].status == TaskStatus.STARTED
            assert tasks["TASK-001"].title == "First task"
            assert tasks["TASK-002"].status == TaskStatus.PENDING
            assert tasks["TASK-003"].status == TaskStatus.FINISHED
        finally:
            os.unlink(plan_path)


class TestPlanUpdaterStatusUpdates:
    """Test task status update functionality."""

    def test_update_single_task_status(self):
        """Updating a single task should add status marker."""
        plan_content = """
# Test Plan

**TASK-001**: First task
**TASK-002**: Second task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()

            result = updater.update_task_status("TASK-001", TaskStatus.STARTED)
            assert result.success
            assert len(result.tasks_updated) == 1
            assert result.tasks_updated[0].task_id == "TASK-001"

            # Verify the file was updated
            updated_content = plan_path.read_text()
            assert "**TASK-001**: [STARTED] First task" in updated_content
            assert "**TASK-002**: Second task" in updated_content
        finally:
            os.unlink(plan_path)
            backup = Path(str(plan_path) + ".backup")
            if backup.exists():
                backup.unlink()

    def test_update_task_with_existing_status(self):
        """Updating a task that already has the target status should be no-op."""
        plan_content = """
# Test Plan

**TASK-001**: [STARTED] First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()

            result = updater.update_task_status("TASK-001", TaskStatus.STARTED)
            assert result.success
            assert len(result.tasks_updated) == 0
        finally:
            os.unlink(plan_path)

    def test_update_nonexistent_task(self):
        """Updating a non-existent task should fail gracefully."""
        plan_content = """
# Test Plan

**TASK-001**: First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()

            result = updater.update_task_status("TASK-999", TaskStatus.STARTED)
            assert not result.success
            assert "TASK-999 not found" in result.error_message
        finally:
            os.unlink(plan_path)

    def test_update_task_status_from_started_to_finished(self):
        """Updating task status should replace existing marker."""
        plan_content = """
# Test Plan

**TASK-001**: [STARTED] First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()

            result = updater.update_task_status("TASK-001", TaskStatus.FINISHED)
            assert result.success

            updated_content = plan_path.read_text()
            assert "[FINISHED] First task" in updated_content
            assert "[STARTED]" not in updated_content
        finally:
            os.unlink(plan_path)

    def test_update_multiple_tasks(self):
        """Batch update should update all specified tasks."""
        plan_content = """
# Test Plan

**TASK-001**: First task
**TASK-002**: Second task
**TASK-003**: Third task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()

            result = updater.update_tasks(
                {
                    "TASK-001": TaskStatus.STARTED,
                    "TASK-003": TaskStatus.FINISHED,
                }
            )
            assert result.success
            assert len(result.tasks_updated) == 2

            updated_content = plan_path.read_text()
            assert "[STARTED] First task" in updated_content
            assert "[FINISHED] Third task" in updated_content
            assert "Second task" in updated_content  # Unchanged
        finally:
            os.unlink(plan_path)


class TestPlanUpdaterBackup:
    """Test backup creation and restoration."""

    def test_backup_created_on_update(self):
        """Updating a task should create a backup file."""
        plan_content = """
# Test Plan

**TASK-001**: First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()
            updater.update_task_status("TASK-001", TaskStatus.STARTED)

            backup_path = plan_path.with_suffix(".md.backup")
            assert backup_path.exists()

            backup_content = backup_path.read_text()
            assert "[STARTED]" not in backup_content  # Original content
        finally:
            os.unlink(plan_path)
            backup = Path(str(plan_path) + ".backup")
            if backup.exists():
                backup.unlink()

    def test_restore_from_backup(self):
        """Restoring from backup should revert plan to original state."""
        plan_content = """
# Test Plan

**TASK-001**: First task
**TASK-002**: Second task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()
            updater.update_task_status("TASK-001", TaskStatus.STARTED)

            # Content was modified
            assert "[STARTED]" in plan_path.read_text()

            # Restore from backup
            assert updater.restore_backup()

            # Content restored to original
            restored_content = plan_path.read_text()
            assert "[STARTED]" not in restored_content
            assert "First task" in restored_content
        finally:
            os.unlink(plan_path)
            backup = Path(str(plan_path) + ".backup")
            if backup.exists():
                backup.unlink()


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_update_plan_task_status_function(self):
        """Convenience function should update task status."""
        plan_content = """
# Test Plan

**TASK-001**: First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            result = update_plan_task_status(plan_path, "TASK-001", "STARTED")
            assert result.success

            updated_content = plan_path.read_text()
            assert "[STARTED] First task" in updated_content
        finally:
            os.unlink(plan_path)

    def test_get_plan_tasks_function(self):
        """Convenience function should return all tasks."""
        plan_content = """
# Test Plan

**TASK-001**: First task
**TASK-002**: Second task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            tasks = get_plan_tasks(plan_path)
            assert len(tasks) == 2
            assert "TASK-001" in tasks
            assert "TASK-002" in tasks
        finally:
            os.unlink(plan_path)

    def test_get_task_status(self):
        """get_task_status should return current status."""
        plan_content = """
# Test Plan

**TASK-001**: [FINISHED] First task
**TASK-002**: Second task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path)
            updater.read_plan()

            assert updater.get_task_status("TASK-001") == TaskStatus.FINISHED
            assert updater.get_task_status("TASK-002") == TaskStatus.PENDING
            assert updater.get_task_status("TASK-999") == TaskStatus.PENDING
        finally:
            os.unlink(plan_path)


class TestTaskStatusEnum:
    """Test TaskStatus enum values."""

    def test_status_values(self):
        """Status enum should have correct string values."""
        assert TaskStatus.PENDING.value == ""
        assert TaskStatus.STARTED.value == "[STARTED]"
        assert TaskStatus.FINISHED.value == "[FINISHED]"
        assert TaskStatus.VALIDATED.value == "[VALIDATED]"


class TestFileLock:
    """Test cross-platform file locking."""

    def test_file_lock_context_manager(self):
        """File lock context manager should acquire and release lock."""
        plan_content = """
# Test Plan

**TASK-001**: First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            from plan_updater import _file_lock

            # Acquire lock and verify it's held
            with _file_lock(plan_path, timeout=1.0):
                # Lock is held within this block
                assert plan_path.exists()
                # Lock file should exist
                lock_file_path = plan_path.with_suffix(".md.lock")
                assert lock_file_path.exists()

            # Lock is released after exiting context
            # Lock file should be cleaned up
            lock_file_path = plan_path.with_suffix(".md.lock")
            assert not lock_file_path.exists()
        finally:
            os.unlink(plan_path)
            # Clean up lock file if it exists
            lock_file_path = plan_path.with_suffix(".md.lock")
            if lock_file_path.exists():
                lock_file_path.unlink()

    def test_file_lock_timeout(self):
        """File lock should timeout when lock cannot be acquired."""
        plan_content = """
# Test Plan

**TASK-001**: First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            from plan_updater import TimeoutError, _file_lock

            # Create lock file manually to simulate contention
            lock_file_path = plan_path.with_suffix(".md.lock")
            lock_file_path.write_text(str(os.getpid()))

            try:
                # Try to acquire lock with short timeout - should fail
                with pytest.raises(TimeoutError, match="Could not acquire lock"):
                    with _file_lock(plan_path, timeout=0.2, poll_interval=0.05):
                        pass
            finally:
                # Clean up lock file
                if lock_file_path.exists():
                    lock_file_path.unlink()
        finally:
            os.unlink(plan_path)

    def test_update_with_lock_success(self):
        """Update should succeed when lock can be acquired."""
        plan_content = """
# Test Plan

**TASK-001**: First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            updater = PlanUpdater(plan_path, lock_timeout=1.0)
            updater.read_plan()

            result = updater.update_task_status("TASK-001", TaskStatus.STARTED)
            assert result.success
            assert not result.lock_timeout
            assert len(result.tasks_updated) == 1
        finally:
            os.unlink(plan_path)
            # Clean up backup
            backup = Path(str(plan_path) + ".backup")
            if backup.exists():
                backup.unlink()
            # Clean up lock file if it exists
            lock_file = plan_path.with_suffix(".md.lock")
            if lock_file.exists():
                lock_file.unlink()

    def test_update_with_lock_timeout_flag(self):
        """Update should set lock_timeout flag when lock acquisition times out."""
        plan_content = """
# Test Plan

**TASK-001**: First task
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            # Create lock file manually to simulate contention
            lock_file_path = plan_path.with_suffix(".md.lock")
            lock_file_path.write_text(str(os.getpid()))

            try:
                # Try to update with short timeout
                updater = PlanUpdater(plan_path, lock_timeout=0.1)
                updater.read_plan()

                result = updater.update_task_status("TASK-001", TaskStatus.STARTED)
                assert not result.success
                assert result.lock_timeout
                assert "Could not acquire lock" in result.error_message
            finally:
                # Clean up lock file
                if lock_file_path.exists():
                    lock_file_path.unlink()
        finally:
            os.unlink(plan_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
