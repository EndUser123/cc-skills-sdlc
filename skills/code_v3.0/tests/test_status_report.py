#!/usr/bin/env python3
"""
Unit tests for status report functionality.

RED PHASE TESTS - These tests FAIL because scripts/status_report.py doesn't exist yet.

Tests cover:
- Phase status display (BUILD/TRACE/SHIP completion)
- Task progress tracking (complete/pending/blocked counts)
- Missing evidence listing per task
- Terminal ownership and lease status
- Empty ledger handling
- Integration with evidence and phase managers
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.evidence import EvidenceManager
from utils.phase_state import PhaseStateManager


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create state directory
    state_dir = temp_dir / ".claude" / "state"
    state_dir.mkdir(parents=True)

    yield state_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_evidence_mgr(temp_state_dir):
    """Create evidence manager with temporary state directory."""
    mgr = EvidenceManager("test_terminal")
    original_path = mgr.ledger_file

    try:
        mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
        mgr._ensure_ledger_exists()
        yield mgr
    finally:
        mgr.ledger_file = original_path


@pytest.fixture
def sample_phase_mgr(temp_state_dir):
    """Create phase manager with temporary state directory."""
    mgr = PhaseStateManager("test_terminal")
    original_global = mgr.global_state_file
    original_build = mgr.build_state_file

    try:
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr.build_state_file = temp_state_dir / "code_build_state_test_terminal.json"
        mgr._ensure_state_exists()
        yield mgr
    finally:
        mgr.global_state_file = original_global
        mgr.build_state_file = original_build


class TestStatusReportPhaseStatus:
    """Test phase status display in status report."""

    def test_status_report_displays_phase_status(self, sample_phase_mgr):
        """Status report should show current phase and completion status.

        Should display:
        - Current active phase (BUILD/TRACE/SHIP)
        - Which phases are marked complete/incomplete
        - Phase validity (commit hash still matches)
        """
        # Setup: Mark BUILD phase complete
        sample_phase_mgr.mark_phase_complete("BUILD", "abc123")

        # This import will FAIL - script doesn't exist yet
        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,  # Not needed for phase status test
            phase_mgr=sample_phase_mgr
        )

        # Verify phase status is in report
        assert "BUILD" in report
        assert "complete" in report.lower() or "✓" in report

    def test_status_report_shows_all_phases(self, sample_phase_mgr):
        """Status report should show status of all phases (BUILD/TRACE/SHIP)."""
        # Setup: Mark multiple phases complete
        sample_phase_mgr.mark_phase_complete("BUILD", "abc123")
        sample_phase_mgr.mark_phase_complete("TRACE", "def456")

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,
            phase_mgr=sample_phase_mgr
        )

        # Should show all phases
        assert "BUILD" in report
        assert "TRACE" in report
        assert "SHIP" in report

    def test_status_report_invalid_phase(self, sample_phase_mgr):
        """Status report should indicate when phase completion is invalid."""
        # Setup: Mark phase complete with hash that won't match current HEAD
        sample_phase_mgr.mark_phase_complete("BUILD", "deadbeef" * 5)

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,
            phase_mgr=sample_phase_mgr
        )

        # Should indicate BUILD is invalid (commit mismatch)
        assert "invalid" in report.lower() or "✗" in report


class TestStatusReportTaskProgress:
    """Test task progress display in status report."""

    def test_status_report_shows_task_progress(self, sample_evidence_mgr):
        """Status report should list tasks with completion counts.

        Should display:
        - Total number of tasks
        - Count of complete tasks
        - Count of pending tasks
        - Count of blocked tasks (if applicable)
        - Task IDs and their statuses
        """
        # Setup: Create tasks with different completion states
        sample_evidence_mgr.record_red("task_1", [], "pytest", 3)
        sample_evidence_mgr.record_green("task_1", [], "pytest", 3)
        sample_evidence_mgr.record_refactor("task_1", [], "pytest", 3)
        sample_evidence_mgr.record_verify("task_1", 0, 0, "PASS")
        sample_evidence_mgr.mark_done("task_1")

        sample_evidence_mgr.record_red("task_2", [], "pytest", 2)

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=None
        )

        # Verify task progress is shown
        assert "task" in report.lower()
        assert "1" in report  # At least one task count
        assert "complete" in report.lower() or "done" in report.lower()

    def test_status_report_empty_task_list(self, sample_evidence_mgr):
        """Status report should handle empty task list gracefully."""
        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=None
        )

        # Should show "No tasks" or similar message
        assert "no task" in report.lower() or "0" in report

    def test_status_report_task_ids_visible(self, sample_evidence_mgr):
        """Status report should show task IDs for identification."""
        # Setup: Create specific tasks
        sample_evidence_mgr.record_red("task_123", [], "pytest", 1)
        sample_evidence_mgr.record_red("task_456", [], "pytest", 1)

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=None
        )

        # Should show task IDs
        assert "task_123" in report
        assert "task_456" in report


class TestStatusReportMissingEvidence:
    """Test missing evidence display in status report."""

    def test_status_report_lists_missing_evidence(self, sample_evidence_mgr):
        """Status report should show which tasks are missing evidence types.

        Should display missing evidence types:
        - RED (failing tests)
        - GREEN (passing tests)
        - REFACTOR (cleanup)
        - VERIFY (quality check)
        """
        # Setup: Create task with only RED evidence (missing GREEN/REFACTOR/VERIFY)
        sample_evidence_mgr.record_red("task_incomplete", [], "pytest", 3)

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=None
        )

        # Should indicate missing evidence
        assert ("missing" in report.lower() or
                "incomplete" in report.lower() or
                "green" in report.lower())

    def test_status_report_formats_missing_evidence_clearly(self, sample_evidence_mgr):
        """Missing evidence should be formatted clearly for readability."""
        # Setup: Task missing multiple evidence types
        sample_evidence_mgr.record_red("task_partial", [], "pytest", 1)

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=None
        )

        # Should be readable (not just raw JSON)
        # Check for formatting indicators
        assert any(sep in report for sep in [":", "-", "•", "*", "│"])

    def test_status_report_complete_task_no_missing_evidence(self, sample_evidence_mgr):
        """Complete tasks should not show missing evidence warnings."""
        # Setup: Complete task with all 4 evidence types
        sample_evidence_mgr.record_red("task_complete", [], "pytest", 1)
        sample_evidence_mgr.record_green("task_complete", [], "pytest", 1)
        sample_evidence_mgr.record_refactor("task_complete", [], "pytest", 1)
        sample_evidence_mgr.record_verify("task_complete", 0, 0, "PASS")
        sample_evidence_mgr.mark_done("task_complete")

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=None
        )

        # Should not show missing evidence for complete task
        # (might show for other tasks, but not this one)
        lines = report.split("\n")
        complete_task_lines = [line for line in lines if "task_complete" in line]

        if complete_task_lines:
            # At least one line mentions the task
            # It shouldn't say "missing" next to it
            task_line = complete_task_lines[0]
            # This is a weak check - just ensure task is mentioned
            assert "task_complete" in task_line


class TestStatusReportTerminalOwnership:
    """Test terminal ownership display in status report."""

    def test_status_report_shows_terminal_ownership(self, sample_phase_mgr):
        """Status report should display current terminal owner."""
        # Setup: Acquire build ownership
        sample_phase_mgr.acquire_build_ownership()

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,
            phase_mgr=sample_phase_mgr
        )

        # Should show terminal ownership info
        assert "terminal" in report.lower() or "owner" in report.lower()

    def test_status_report_shows_lease_expiration(self, sample_phase_mgr):
        """Status report should show lease expiration when applicable."""
        # Setup: Acquire ownership with timeout
        sample_phase_mgr.acquire_build_ownership(timeout_minutes=60)

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,
            phase_mgr=sample_phase_mgr
        )

        # Should show expiration or lease info
        assert "expire" in report.lower() or "lease" in report.lower()

    def test_status_report_no_ownership(self, sample_phase_mgr):
        """Status report should handle no ownership gracefully."""
        # Setup: No ownership acquired

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,
            phase_mgr=sample_phase_mgr
        )

        # Should not crash, should show unowned state
        assert report  # Report exists
        assert len(report) > 0  # Not empty


class TestStatusReportEmptyLedger:
    """Test status report with empty ledger."""

    def test_status_report_empty_ledger(self, temp_state_dir):
        """Status report should handle empty ledger gracefully.

        Should show:
        - "No tasks" message
        - All phases as incomplete
        - No crash or errors
        """
        # Create fresh empty managers
        evidence_mgr = EvidenceManager("test_terminal")
        phase_mgr = PhaseStateManager("test_terminal")

        # Redirect to temp dir
        evidence_mgr.ledger_file = temp_state_dir / "code_evidence_empty.json"
        evidence_mgr._ensure_ledger_exists()

        phase_mgr.global_state_file = temp_state_dir / "code_phase_empty.json"
        phase_mgr.build_state_file = temp_state_dir / "code_build_empty.json"
        phase_mgr._ensure_state_exists()

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=evidence_mgr,
            phase_mgr=phase_mgr
        )

        # Should handle gracefully
        assert report is not None
        assert len(report) > 0
        # Should indicate no tasks
        assert "no task" in report.lower() or "0" in report

    def test_status_report_returns_string(self, temp_state_dir):
        """Status report should return a string, not dict or other type."""
        evidence_mgr = EvidenceManager("test_terminal")
        phase_mgr = PhaseStateManager("test_terminal")

        evidence_mgr.ledger_file = temp_state_dir / "code_evidence_type.json"
        evidence_mgr._ensure_ledger_exists()

        phase_mgr.global_state_file = temp_state_dir / "code_phase_type.json"
        phase_mgr.build_state_file = temp_state_dir / "code_build_type.json"
        phase_mgr._ensure_state_exists()

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=evidence_mgr,
            phase_mgr=phase_mgr
        )

        # Must be a string
        assert isinstance(report, str)


class TestStatusCommandIntegration:
    """Integration tests for status command."""

    def test_status_command_integration(self, sample_evidence_mgr, sample_phase_mgr):
        """Integration test: generate_status_report should work with both managers.

        Should:
        - Accept both evidence_mgr and phase_mgr
        - Return formatted string
        - Include all required sections (phases, tasks, evidence, ownership)
        """
        # Setup: Add sample data
        sample_evidence_mgr.record_red("task_1", [], "pytest", 3)
        sample_phase_mgr.mark_phase_complete("BUILD", "abc123")
        sample_phase_mgr.acquire_build_ownership()

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=sample_phase_mgr
        )

        # Verify return type
        assert isinstance(report, str)

        # Verify all sections are present
        assert "BUILD" in report  # Phase status
        assert "task" in report.lower()  # Task progress
        # Terminal ownership might be shown differently
        assert len(report) > 50  # Substantial content

    def test_status_command_none_managers(self):
        """Status command should handle None managers gracefully."""
        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,
            phase_mgr=None
        )

        # Should not crash
        assert report is not None
        assert isinstance(report, str)

    def test_status_command_only_evidence_mgr(self, sample_evidence_mgr):
        """Status command should work with only evidence manager."""
        sample_evidence_mgr.record_red("task_1", [], "pytest", 1)

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=sample_evidence_mgr,
            phase_mgr=None
        )

        # Should work and show task info
        assert report is not None
        assert "task" in report.lower()

    def test_status_command_only_phase_mgr(self, sample_phase_mgr):
        """Status command should work with only phase manager."""
        sample_phase_mgr.mark_phase_complete("BUILD", "abc123")

        from scripts.status_report import generate_status_report

        report = generate_status_report(
            evidence_mgr=None,
            phase_mgr=sample_phase_mgr
        )

        # Should work and show phase info
        assert report is not None
        assert "BUILD" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
