#!/usr/bin/env python3
"""
Plan Updater - In-place plan.md task status updates.

Updates plan.md files with task status markers (STARTED, FINISHED, VALIDATED)
as execution progresses. Supports both /code and /loop-code skills.

Author: Claude Code
Date: 2026-03-15
Related: TASK-001 plan.md in-place updates
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Cross-platform file locking
if sys.platform == "win32":
    pass
else:
    import fcntl


class TimeoutError(Exception):
    """Raised when file lock acquisition times out."""

    pass


class TaskStatus(Enum):
    """Task status markers for plan updates."""

    PENDING = ""
    STARTED = "[STARTED]"
    FINISHED = "[FINISHED]"
    VALIDATED = "[VALIDATED]"


@dataclass
class TaskInfo:
    """Information about a task in plan.md."""

    task_id: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    line_number: int = 0
    raw_line: str = ""


@dataclass
class PlanUpdateResult:
    """Result of plan update operation."""

    success: bool
    plan_path: Path
    tasks_updated: list[TaskInfo] = field(default_factory=list)
    error_message: str | None = None
    backup_path: Path | None = None
    checksum_before: str | None = None
    checksum_after: str | None = None
    checksum_verified: bool = False
    lock_timeout: bool = False


def _compute_checksum(content: str) -> str:
    """Compute SHA256 checksum of content.

    Args:
        content: Text content to checksum

    Returns:
        Hexadecimal SHA256 checksum
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@contextmanager
def _file_lock(
    file_path: Path, timeout: float = 5.0, poll_interval: float = 0.1
) -> Generator[bool, None, None]:
    """Acquire cross-platform file lock with timeout.

    On Windows: Uses a separate .lock file for coordination (msvcrt.locking has issues).
    On Unix: Uses fcntl.flock() on the actual file.

    Args:
        file_path: Path to file to lock
        timeout: Maximum seconds to wait for lock (default: 5.0)
        poll_interval: Seconds between lock attempts (default: 0.1)

    Yields:
        True if lock acquired

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
        OSError: If file operations fail
    """
    lock_acquired = False
    start_time = time.time()

    if sys.platform == "win32":
        # Windows: Use lock file approach
        # (msvcrt.locking doesn't work well for coordination)
        lock_file_path = file_path.with_suffix(file_path.suffix + ".lock")
        lock_fd = None

        try:
            # Try to create and open lock file exclusively
            while time.time() - start_time < timeout:
                try:
                    # O_CREAT | O_EXCL creates file atomically if it doesn't exist
                    # This fails if file already exists (lock is held)
                    lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                    # Write our PID to the lock file for debugging
                    os.write(lock_fd, str(os.getpid()).encode())
                    lock_acquired = True
                    break
                except FileExistsError:
                    # Lock file exists - try to read it to check if it's stale
                    try:
                        # Check if lock file is stale (process no longer running)
                        with open(lock_file_path) as f:
                            pid_str = f.read().strip()
                            if pid_str.isdigit():
                                pid = int(pid_str)
                                # Check if process is still running
                                try:
                                    os.kill(pid, 0)  # Signal 0 checks if process exists
                                    # Process exists - lock is active
                                    pass
                                except OSError:
                                    # Process doesn't exist - stale lock, remove it
                                    lock_file_path.unlink()
                                    continue
                    except (OSError, ValueError):
                        # Couldn't read lock file - assume lock is held
                        pass

                    # Wait before retrying
                    time.sleep(poll_interval)

            if not lock_acquired:
                raise TimeoutError(
                    f"Could not acquire lock on {file_path} "
                    f"within {timeout} seconds (locked by another process)"
                )

            # Yield with lock held
            yield True

        finally:
            # Always release lock by deleting lock file
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except OSError:
                    pass
            if lock_acquired and lock_file_path.exists():
                try:
                    lock_file_path.unlink()
                except OSError:
                    pass  # Best effort cleanup

    else:
        # Unix: Use fcntl.flock() on the actual file
        fd = None
        try:
            fd = os.open(file_path, os.O_RDWR | os.O_CREAT)

            # Try to acquire lock with timeout
            while time.time() - start_time < timeout:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    break
                except OSError as e:
                    # fcntl.flock raises exception with errno EAGAIN
                    if e.errno not in (11, 35):  # EAGAIN = 11, EWOULDBLOCK = 35
                        raise

                    # Wait before retrying
                    time.sleep(poll_interval)

            if not lock_acquired:
                raise TimeoutError(
                    f"Could not acquire lock on {file_path} "
                    f"within {timeout} seconds (locked by another process)"
                )

            # Yield with lock held
            yield True

        finally:
            # Always release lock and close file descriptor
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass  # Best effort unlock
                finally:
                    os.close(fd)


class PlanUpdater:
    """Updates plan.md files with task status markers.

    Usage:
        updater = PlanUpdater(plan_path)
        result = updater.update_task_status("TASK-001", TaskStatus.STARTED)
        if result.success:
            print(f"Updated {len(result.tasks_updated)} tasks")
    """

    # Task pattern: **TASK-XXX**>: Task title (markdown bold)
    # Allows optional leading whitespace for markdown formatting
    TASK_PATTERN = re.compile(r"^\s*\*\*(TASK-[0-9A-F-]+)\*\*:\s*(.+)$", re.MULTILINE)

    # Status marker pattern: [STATUS] before task title
    STATUS_MARKER_PATTERN = re.compile(
        r"^\s*\*\*(TASK-[0-9A-F-]+)\*\*:\s*(\[STARTED\]|\[FINISHED\]|\[VALIDATED\])?\s*(.+)$",
        re.MULTILINE,
    )

    def __init__(self, plan_path: Path | str, lock_timeout: float = 5.0):
        """Initialize plan updater.

        Args:
            plan_path: Path to plan.md file
            lock_timeout: Maximum seconds to wait for file lock (default: 5.0)
        """
        self.plan_path = Path(plan_path)
        self.lock_timeout = lock_timeout
        self._content: str = ""
        self._tasks: dict[str, TaskInfo] = {}

    def read_plan(self) -> bool:
        """Read and parse plan.md file.

        Returns:
            True if plan was read successfully, False otherwise
        """
        if not self.plan_path.exists():
            return False

        try:
            self._content = self.plan_path.read_text(encoding="utf-8")
            self._parse_tasks()
            return True
        except OSError:
            return False

    def _parse_tasks(self) -> None:
        """Parse task definitions from plan content."""
        self._tasks.clear()

        for match in self.TASK_PATTERN.finditer(self._content):
            task_id = match.group(1)
            title = match.group(2).strip()

            # Check if title starts with a status marker
            status = TaskStatus.PENDING
            clean_title = title

            # Check non-PENDING statuses only (PENDING has empty value which always matches)
            for status_enum in (TaskStatus.STARTED, TaskStatus.FINISHED, TaskStatus.VALIDATED):
                if title.startswith(status_enum.value):
                    status = status_enum
                    # Remove the marker from the title
                    clean_title = title[len(status_enum.value) :].strip()
                    break

            # Find line number
            line_number = self._content[: match.start()].count("\n") + 1

            self._tasks[task_id] = TaskInfo(
                task_id=task_id,
                title=clean_title,
                status=status,
                line_number=line_number,
                raw_line=match.group(0),
            )

    def get_tasks(self) -> dict[str, TaskInfo]:
        """Get all parsed tasks.

        Returns:
            Dictionary mapping task_id to TaskInfo
        """
        return self._tasks.copy()

    def get_task_status(self, task_id: str) -> TaskStatus:
        """Get current status of a task.

        Args:
            task_id: Task identifier (e.g., "TASK-001")

        Returns:
            Current task status, or PENDING if task not found
        """
        task = self._tasks.get(task_id)
        return task.status if task else TaskStatus.PENDING

    def update_task_status(self, task_id: str, status: TaskStatus) -> PlanUpdateResult:
        """Update a single task's status in plan.md.

        Args:
            task_id: Task identifier (e.g., "TASK-001")
            status: New status to set

        Returns:
            PlanUpdateResult with success status and details
        """
        if task_id not in self._tasks:
            return PlanUpdateResult(
                success=False,
                plan_path=self.plan_path,
                error_message=f"Task {task_id} not found in plan",
            )

        task = self._tasks[task_id]

        if task.status == status:
            # No update needed
            return PlanUpdateResult(success=True, plan_path=self.plan_path, tasks_updated=[])

        return self.update_tasks({task_id: status})

    def update_tasks(self, updates: dict[str, TaskStatus]) -> PlanUpdateResult:
        """Update multiple tasks' status in plan.md.

        Args:
            updates: Dictionary mapping task_id to new status

        Returns:
            PlanUpdateResult with success status and details
        """
        # Acquire file lock before modifying
        try:
            with _file_lock(self.plan_path, timeout=self.lock_timeout):
                return self._update_tasks_locked(updates)
        except TimeoutError as e:
            return PlanUpdateResult(
                success=False, plan_path=self.plan_path, error_message=str(e), lock_timeout=True
            )

    def _update_tasks_locked(self, updates: dict[str, TaskStatus]) -> PlanUpdateResult:
        """Internal method: Update tasks when lock is held.

        Args:
            updates: Dictionary mapping task_id to new status

        Returns:
            PlanUpdateResult with success status and details
        """
        # Create backup
        backup_path = self._create_backup()
        if backup_path is None and self._content:
            return PlanUpdateResult(
                success=False, plan_path=self.plan_path, error_message="Failed to create backup"
            )

        # Compute checksum before write
        checksum_before = _compute_checksum(self._content) if self._content else None

        # Build new content
        new_content = self._content
        updated_tasks = []

        for task_id, new_status in updates.items():
            if task_id not in self._tasks:
                continue

            task = self._tasks[task_id]

            # Skip if already has this status
            if task.status == new_status:
                continue

            # Build replacement line with status marker
            old_line = task.raw_line

            # Remove old status marker if present
            # (Use task.title as base, which already has status stripped during parsing)
            clean_title = task.title

            # If old line has a status marker, extract title without it
            # Skip PENDING (empty string) to avoid split() errors
            for status_enum in (TaskStatus.STARTED, TaskStatus.FINISHED, TaskStatus.VALIDATED):
                if old_line.find(status_enum.value) != -1:
                    # Extract the title without the old marker
                    parts = old_line.split(status_enum.value, 1)
                    if len(parts) == 2:
                        clean_title = parts[1].strip()
                    break

            # Add new status marker
            if new_status != TaskStatus.PENDING:
                new_line = f"**{task_id}**: {new_status.value} {clean_title}"
            else:
                new_line = f"**{task_id}**: {clean_title}"

            # Replace in content (use the exact match)
            new_content = new_content.replace(old_line, new_line, 1)

            # Update task info
            task.status = new_status
            task.raw_line = new_line
            updated_tasks.append(task)

        # Write updated content with checksum verification
        try:
            # Compute checksum of what we intend to write
            checksum_intended = _compute_checksum(new_content)

            # Write content (lock file coordination allows normal file access)
            self.plan_path.write_text(new_content, encoding="utf-8")

            # Verify by reading back what was written
            written_content = self.plan_path.read_text(encoding="utf-8")
            checksum_actual = _compute_checksum(written_content)

            checksum_verified = checksum_intended == checksum_actual

            if not checksum_verified:
                # Rollback from backup on checksum mismatch
                if backup_path and backup_path.exists():
                    try:
                        backup_content = backup_path.read_text(encoding="utf-8")
                        self.plan_path.write_text(backup_content, encoding="utf-8")
                    except OSError:
                        pass  # Best effort rollback

                return PlanUpdateResult(
                    success=False,
                    plan_path=self.plan_path,
                    error_message=f"Checksum mismatch: intended {checksum_intended[:8]}..., actual {checksum_actual[:8]}...",
                    backup_path=backup_path,
                    checksum_before=checksum_before,
                    checksum_after=checksum_actual,
                    checksum_verified=False,
                )

            self._content = new_content
            return PlanUpdateResult(
                success=True,
                plan_path=self.plan_path,
                tasks_updated=updated_tasks,
                backup_path=backup_path,
                checksum_before=checksum_before,
                checksum_after=checksum_actual,
                checksum_verified=True,
            )
        except OSError as e:
            return PlanUpdateResult(
                success=False,
                plan_path=self.plan_path,
                error_message=f"Failed to write plan: {e}",
                backup_path=backup_path,
                checksum_before=checksum_before,
                checksum_after=None,
                checksum_verified=False,
            )

    def _create_backup(self) -> Path | None:
        """Create backup of plan.md.

        Returns:
            Path to backup file, or None if backup failed
        """
        if not self._content:
            return None

        try:
            backup_path = self.plan_path.with_suffix(".md.backup")
            backup_path.write_text(self._content, encoding="utf-8")
            return backup_path
        except OSError:
            return None

    def restore_backup(self, backup_path: Path | None = None) -> bool:
        """Restore plan.md from backup.

        Args:
            backup_path: Path to backup file (uses default if None)

        Returns:
            True if restore succeeded, False otherwise
        """
        if backup_path is None:
            backup_path = self.plan_path.with_suffix(".md.backup")

        if not backup_path.exists():
            return False

        try:
            content = backup_path.read_text(encoding="utf-8")
            self.plan_path.write_text(content, encoding="utf-8")
            self._content = content
            self._parse_tasks()
            return True
        except OSError:
            return False


def update_plan_task_status(
    plan_path: Path | str, task_id: str, status: TaskStatus | str
) -> PlanUpdateResult:
    """Convenience function to update a single task status.

    Args:
        plan_path: Path to plan.md file
        task_id: Task identifier (e.g., "TASK-001")
        status: New status (TaskStatus enum or string like "STARTED")

    Returns:
        PlanUpdateResult with success status and details

    Example:
        result = update_plan_task_status("plan.md", "TASK-001", "STARTED")
        if result.success:
            print(f"Task updated: {result.tasks_updated[0].task_id}")
    """
    # Convert string status to enum
    if isinstance(status, str):
        status_map = {
            "": TaskStatus.PENDING,
            "STARTED": TaskStatus.STARTED,
            "FINISHED": TaskStatus.FINISHED,
            "VALIDATED": TaskStatus.VALIDATED,
        }
        status = status_map.get(status.upper(), TaskStatus.PENDING)

    updater = PlanUpdater(plan_path)
    if not updater.read_plan():
        return PlanUpdateResult(
            success=False, plan_path=Path(plan_path), error_message="Failed to read plan file"
        )

    return updater.update_task_status(task_id, status)


def get_plan_tasks(plan_path: Path | str) -> dict[str, TaskInfo]:
    """Convenience function to get all tasks from a plan.

    Args:
        plan_path: Path to plan.md file

    Returns:
        Dictionary mapping task_id to TaskInfo

    Example:
        tasks = get_plan_tasks("plan.md")
        for task_id, task_info in tasks.items():
            print(f"{task_id}: {task_info.status.value} {task_info.title}")
    """
    updater = PlanUpdater(plan_path)
    if not updater.read_plan():
        return {}

    return updater.get_tasks()


if __name__ == "__main__":
    import sys

    # CLI for testing
    if len(sys.argv) < 3:
        print("Usage: python plan_updater.py <plan.md> <task_id> [status]")
        print("Status: PENDING, STARTED, FINISHED, VALIDATED")
        sys.exit(2)

    plan_file = sys.argv[1]
    task = sys.argv[2]
    status_str = sys.argv[3] if len(sys.argv) > 3 else "STARTED"

    result = update_plan_task_status(plan_file, task, status_str)

    if result.success:
        print(f"✅ Updated {len(result.tasks_updated)} task(s)")
        for task_info in result.tasks_updated:
            print(f"  {task_info.task_id}: {task_info.status.value} {task_info.title}")
        if result.checksum_verified:
            print(f"  ✅ Checksum verified: {result.checksum_after[:8]}...")
    else:
        print(f"❌ Failed: {result.error_message}")
        sys.exit(1)
