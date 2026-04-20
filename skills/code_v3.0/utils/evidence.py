#!/usr/bin/env python3
"""
Evidence ledger manager for /code skill TDD workflow.

Tracks RED/GREEN/REFACTOR/VERIFY evidence per task, enables resume
after interruption, enforces completion guard (4 evidence types required).
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Workspace state path for /code skill evidence
_DEFAULT_EVIDENCE_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", "P:/")) / ".claude" / "state"


class EvidenceManager:
    """Manage TDD evidence ledger for /code skill BUILD phase."""

    def __init__(self, terminal_id: str):
        """Initialize evidence manager for terminal."""
        self.terminal_id = terminal_id
        self.ledger_file = _DEFAULT_EVIDENCE_DIR / f"code_evidence_{terminal_id}.json"
        self._ensure_ledger_exists()

    def _ensure_ledger_exists(self):
        """Create ledger if it doesn't exist."""
        if not self.ledger_file.exists():
            self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
            self.ledger_file.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "terminal_id": self.terminal_id,
                        "task_list_id": None,
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "tasks": {},
                    },
                    indent=2,
                )
            )

    def _load_ledger(self) -> dict:
        """Load ledger from disk."""
        return json.loads(self.ledger_file.read_text())

    def _save_ledger(self, ledger: dict):
        """Save ledger to disk."""
        ledger["last_updated"] = datetime.now().isoformat()
        self.ledger_file.write_text(json.dumps(ledger, indent=2))

    def _load_ledger_locked(self) -> dict:
        """Load ledger state.

        The Windows byte-range locking path proved unreliable in test and hook
        environments, causing permission leaks on teardown. Use the regular
        read path here until a robust cross-process locking strategy is added.
        """
        return self._load_ledger()

    def _save_ledger_locked(self, ledger: dict):
        """Save ledger state.

        See `_load_ledger_locked()` for why this currently falls back to the
        regular write path.
        """
        self._save_ledger(ledger)

    def _verify_implementation_exists(self, task_id: str) -> list[str]:
        """Verify all files in evidence actually exist. Returns missing files."""
        ledger = self._load_ledger_locked()  # Use locked path for consistency
        task = ledger["tasks"].get(task_id)
        if not task:
            return []

        missing = []
        evidence = task.get("evidence", {})

        # Check GREEN impl_files
        green = evidence.get("GREEN", {})
        for file_path in green.get("impl_files", []):
            if not Path(file_path).exists():
                missing.append(file_path)

        # Check RED test_files
        red = evidence.get("RED", {})
        for file_path in red.get("test_files", []):
            if not Path(file_path).exists():
                missing.append(file_path)

        return missing

    def _append_evidence(self, task_id: str, stage: str, evidence: dict):
        """Append evidence to task in ledger."""
        ledger = self._load_ledger()

        if task_id not in ledger["tasks"]:
            ledger["tasks"][task_id] = {"description": "", "evidence": {}}

        ledger["tasks"][task_id]["evidence"][stage] = evidence
        self._save_ledger(ledger)

    def record_red(
        self, task_id: str, test_files: list[str], test_command: str, failing_tests: int
    ):
        """Record RED stage evidence."""
        self._append_evidence(
            task_id,
            "RED",
            {
                "completed": True,
                "timestamp": datetime.now().isoformat(),
                "test_files": test_files,
                "test_command": test_command,
                "failing_tests": failing_tests,
            },
        )

    def record_green(
        self, task_id: str, impl_files: list[str], test_command: str, passing_tests: int
    ):
        """Record GREEN stage evidence."""
        self._append_evidence(
            task_id,
            "GREEN",
            {
                "completed": True,
                "timestamp": datetime.now().isoformat(),
                "impl_files": impl_files,
                "test_command": test_command,
                "passing_tests": passing_tests,
            },
        )

    def record_refactor(
        self, task_id: str, changes: list[str], test_command: str, passing_tests: int
    ):
        """Record REFACTOR stage evidence."""
        self._append_evidence(
            task_id,
            "REFACTOR",
            {
                "completed": True,
                "timestamp": datetime.now().isoformat(),
                "changes": changes,
                "test_command": test_command,
                "passing_tests": passing_tests,
            },
        )

    def record_verify(self, task_id: str, findings: int, blocking: int, verdict: str):
        """Record VERIFY stage evidence."""
        self._append_evidence(
            task_id,
            "VERIFY",
            {
                "completed": True,
                "timestamp": datetime.now().isoformat(),
                "findings": findings,
                "blocking": blocking,
                "verdict": verdict,
            },
        )

    def can_mark_done(self, task_id: str) -> tuple[bool, str]:
        """Check if task has all 4 evidence types."""
        ledger = self._load_ledger()
        task = ledger["tasks"].get(task_id)

        if not task:
            return False, f"Task {task_id} not found in ledger"

        evidence = task.get("evidence", {})
        required = ["RED", "GREEN", "REFACTOR", "VERIFY"]
        missing = [s for s in required if not evidence.get(s, {}).get("completed")]

        if missing:
            return False, f"Cannot mark task done: missing evidence for {', '.join(missing)}"

        return True, "All evidence present"

    def mark_done(self, task_id: str):
        """Mark task as done after verifying evidence and implementation exist."""
        can_done, msg = self.can_mark_done(task_id)
        if not can_done:
            raise ValueError(msg)

        missing = self._verify_implementation_exists(task_id)
        if missing:
            raise ValueError(f"Implementation files missing: {missing}")

        ledger = self._load_ledger_locked()
        ledger["tasks"][task_id]["done"] = True
        ledger["tasks"][task_id]["done_at"] = datetime.now().isoformat()
        self._save_ledger_locked(ledger)

    def get_task_status(self, task_id: str) -> dict:
        """Get current status of task."""
        ledger = self._load_ledger()
        task = ledger["tasks"].get(task_id)

        if not task:
            return {"exists": False}

        evidence = task.get("evidence", {})
        return {
            "exists": True,
            "description": task.get("description", ""),
            "done": task.get("done", False),
            "stages_complete": sum(1 for e in evidence.values() if e.get("completed")),
            "total_stages": 4,
            "evidence": evidence,
        }

    def get_completion_statistics(self) -> dict:
        """
        Calculate Task Success Rate (TSR) from evidence ledger.

        TSR = (Successfully Completed Tasks / Total Attempted Tasks) × 100

        Returns:
            Dict with:
                - total_attempted: Total number of tasks attempted
                - completed: Tasks with all 4 evidence types and marked as done
                - failed: Tasks with incomplete evidence or not done
                - blocked: Tasks with no evidence or missing critical stages
                - tsr: Task Success Rate percentage (0-100)
        """
        ledger = self._load_ledger()
        tasks = ledger.get("tasks", {})

        # Count tasks by status
        total_attempted = len(tasks)
        completed = 0
        failed = 0
        blocked = 0

        for task_id, task_data in tasks.items():
            # Check if task is done (has all 4 evidence types and done=True)
            if task_data.get("done", False):
                # Verify all 4 evidence types are present
                evidence = task_data.get("evidence", {})
                required = ["RED", "GREEN", "REFACTOR", "VERIFY"]
                all_present = all(evidence.get(stage, {}).get("completed") for stage in required)

                if all_present:
                    completed += 1
                else:
                    # Task marked done but missing evidence - count as failed
                    failed += 1
            else:
                # Task not done - check evidence progress
                evidence = task_data.get("evidence", {})
                stages_complete = sum(1 for e in evidence.values() if e.get("completed"))

                if stages_complete == 0:
                    # No evidence at all - blocked
                    blocked += 1
                else:
                    # Some evidence but not complete - failed
                    failed += 1

        # Calculate TSR (avoid division by zero)
        tsr = 0.0
        if total_attempted > 0:
            tsr = (completed / total_attempted) * 100

        return {
            "total_attempted": total_attempted,
            "completed": completed,
            "failed": failed,
            "blocked": blocked,
            "tsr": round(tsr, 2),
        }

    def record_tdd_evidence(self, task_id: str, phase: str, evidence: dict):
        """Record generic TDD evidence from /tdd skill.

        This method extends EvidenceManager to support /tdd's generic evidence
        format, allowing unified evidence tracking across /code and /tdd skills.

        Args:
            task_id: TDD task identifier (e.g., "TASK-001")
            phase: TDD phase (RED, GREEN, REFACTOR, VERIFY, or custom)
            evidence: Generic evidence dictionary containing phase-specific details

        Example:
            manager.record_tdd_evidence("TASK-001", "RED", {
                "test_files": ["test_feature.py"],
                "test_command": "pytest test_feature.py -v",
                "failing_tests": 3
            })
        """
        self._append_evidence(
            task_id,
            phase,
            {
                "completed": True,
                "timestamp": datetime.now().isoformat(),
                **evidence,  # Merge provided evidence dict
            },
        )


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python evidence.py <terminal_id> [task_id]")
        sys.exit(1)

    terminal_id = sys.argv[1]
    mgr = EvidenceManager(terminal_id)

    if len(sys.argv) >= 3:
        task_id = sys.argv[2]
        status = mgr.get_task_status(task_id)
        print(f"Task {task_id} status:")
        print(f"  Exists: {status['exists']}")
        if status["exists"]:
            print(f"  Done: {status['done']}")
            print(f"  Stages: {status['stages_complete']}/{status['total_stages']}")
    else:
        print(f"Evidence ledger: {mgr.ledger_file}")
        ledger = mgr._load_ledger()
        print(f"Tasks: {len(ledger['tasks'])}")
        for task_id, task_data in ledger["tasks"].items():
            print(f"  {task_id}: {task_data.get('description', 'no description')}")
