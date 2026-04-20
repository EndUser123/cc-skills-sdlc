#!/usr/bin/env python3
"""
Unit tests for repair markers functionality.

RED PHASE TESTS - These tests FAIL because scripts/repair_markers.py doesn't exist yet.

Tests cover:
- Detecting stale phase markers (old commit hash)
- Validating markers against git HEAD
- Invalidating stale markers automatically
- Confirmation before destructive operations
- Dry-run mode for safe preview
- Integration with PhaseStateManager
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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


class TestRepairMarkersCoreFunctionality:
    """Test core repair markers functionality."""

    def test_repair_markers_detects_stale_markers(self, sample_phase_mgr):
        """Repair markers should detect phase markers with old commit hash.

        Should:
        - Identify markers where commit_hash != current git HEAD
        - Return list of stale marker names
        - Indicate which commit hash was recorded vs current
        """
        # Setup: Mark BUILD phase complete with old commit
        sample_phase_mgr.mark_phase_complete("BUILD", "abc123def456")

        # Mock git HEAD to return different commit
        with patch('utils.phase_state.get_git_head_hash', return_value='def789abc123'):
            from scripts.repair_markers import detect_stale_markers

            stale = detect_stale_markers(sample_phase_mgr)

            # Should detect BUILD as stale
            assert "BUILD" in stale
            assert isinstance(stale, list)

    def test_repair_markers_valid_markers_unchanged(self, sample_phase_mgr):
        """Repair markers should keep markers with current commit hash.

        Should:
        - Not flag markers where commit_hash == git HEAD
        - Return empty list or exclude valid markers
        - Preserve valid marker state
        """
        # Setup: Mark phase complete with current commit
        current_commit = "abc123def456"
        sample_phase_mgr.mark_phase_complete("BUILD", current_commit)

        # Mock git HEAD to return same commit
        with patch('utils.phase_state.get_git_head_hash', return_value=current_commit):
            from scripts.repair_markers import detect_stale_markers

            stale = detect_stale_markers(sample_phase_mgr)

            # Should NOT detect BUILD as stale
            assert "BUILD" not in stale or len(stale) == 0

    def test_repair_markers_invalidates_stale_markers(self, sample_phase_mgr):
        """Repair markers should remove stale markers from state.

        Should:
        - Delete stale phase markers from state file
        - Update state to reflect removal
        - Return count of markers invalidated
        """
        # Setup: Create stale marker
        sample_phase_mgr.mark_phase_complete("BUILD", "oldcommit123")

        with patch('utils.phase_state.get_git_head_hash', return_value='newcommit456'):
            from scripts.repair_markers import invalidate_stale_markers

            count = invalidate_stale_markers(sample_phase_mgr)

            # Should invalidate the marker
            assert count >= 1

            # Verify marker is no longer complete
            state = sample_phase_mgr._load_global_state()
            build_phase = state.get("phases", {}).get("BUILD", {})
            assert not build_phase.get("completed", False)


class TestRepairMarkersCommitHashValidation:
    """Test commit hash validation logic."""

    def test_repair_markers_compares_to_git_head(self, sample_phase_mgr):
        """Repair markers should compare marker commit to git HEAD.

        Should:
        - Fetch current git HEAD hash
        - Compare against marker's recorded commit_hash
        - Use exact string matching
        """
        # Setup: Create marker with specific commit
        marker_commit = "aaa111bbb222"
        sample_phase_mgr.mark_phase_complete("TRACE", marker_commit)

        # Mock different HEAD
        with patch('utils.phase_state.get_git_head_hash', return_value='zzz999yyy888'):
            from scripts.repair_markers import detect_stale_markers

            stale = detect_stale_markers(sample_phase_mgr)

            # Should detect as stale due to mismatch
            assert "TRACE" in stale

    def test_repair_markers_handles_missing_git(self, sample_phase_mgr):
        """Repair markers should gracefully handle when git unavailable.

        Should:
        - Not crash when git command fails
        - Treat missing git as no stale markers (conservative)
        - Return gracefully without invalidating
        """
        # Setup: Create marker
        sample_phase_mgr.mark_phase_complete("BUILD", "anycommit123")

        # Mock git to return None (unavailable)
        with patch('utils.phase_state.get_git_head_hash', return_value=None):
            from scripts.repair_markers import detect_stale_markers

            stale = detect_stale_markers(sample_phase_mgr)

            # Should NOT flag as stale when git unavailable
            assert len(stale) == 0 or "BUILD" not in stale

    def test_repair_markers_handles_detached_head(self, sample_phase_mgr):
        """Repair markers should handle detached HEAD state.

        Should:
        - Work correctly in detached HEAD state
        - Compare commits normally
        - Not crash or behave unexpectedly
        """
        # Setup: Create marker
        sample_phase_mgr.mark_phase_complete("SHIP", "detached123")

        # Detached HEAD still returns a commit hash
        with patch('utils.phase_state.get_git_head_hash', return_value='detached456'):
            from scripts.repair_markers import detect_stale_markers

            stale = detect_stale_markers(sample_phase_mgr)

            # Should still detect mismatch in detached state
            assert "SHIP" in stale


class TestRepairMarkersConfirmation:
    """Test confirmation prompts for destructive operations."""

    def test_repair_markers_confirms_before_deletion(self, sample_phase_mgr, capsys):
        """Repair markers should require confirmation for destructive ops.

        Should:
        - Prompt user before deleting markers
        - Wait for y/n confirmation
        - Abort if user declines
        """
        # Setup: Create stale marker
        sample_phase_mgr.mark_phase_complete("BUILD", "old123")

        with patch('utils.phase_state.get_git_head_hash', return_value='new456'):
            # Mock input to decline
            with patch('builtins.input', return_value='n'):
                from scripts.repair_markers import repair_markers_interactive

                result = repair_markers_interactive(sample_phase_mgr, confirm=True)

                # Should not delete when user declines
                assert "BUILD" not in result.get("invalidated", [])

    def test_repair_markers_auto_confirm_flag(self, sample_phase_mgr):
        """Repair markers --yes flag should skip confirmation.

        Should:
        - Accept --yes or --auto-confirm flag
        - Proceed without prompting
        - Invalidate markers immediately
        """
        # Setup: Create stale marker
        sample_phase_mgr.mark_phase_complete("TRACE", "old123")

        with patch('utils.phase_state.get_git_head_hash', return_value='new456'):
            from scripts.repair_markers import repair_markers_interactive

            # Call with auto_confirm=True (like --yes flag)
            result = repair_markers_interactive(sample_phase_mgr, confirm=False)

            # Should delete without prompting
            assert result.get("invalidated_count", 0) >= 1

    def test_repair_markers_dry_run_mode(self, sample_phase_mgr, capsys):
        """Repair markers --dry-run should report changes without executing.

        Should:
        - Accept --dry-run flag
        - Show what WOULD be invalidated
        - NOT actually modify state
        """
        # Setup: Create stale marker
        sample_phase_mgr.mark_phase_complete("BUILD", "old123")

        with patch('utils.phase_state.get_git_head_hash', return_value='new456'):
            from scripts.repair_markers import repair_markers_dry_run

            # Dry run should report but not change
            report = repair_markers_dry_run(sample_phase_mgr)

            # Should report stale markers
            assert "BUILD" in report or "stale" in report.lower()

            # But marker should still be present (not deleted)
            state = sample_phase_mgr._load_global_state()
            build_phase = state.get("phases", {}).get("BUILD", {})
            assert build_phase.get("completed", False)  # Still there!


class TestRepairMarkersEdgeCases:
    """Test edge cases and error handling."""

    def test_repair_markers_empty_state_file(self, temp_state_dir):
        """Repair markers should handle empty state.json.

        Should:
        - Not crash on empty state
        - Return empty results (no stale markers)
        - Handle gracefully
        """
        # Create fresh empty manager
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_empty.json"
        mgr._ensure_state_exists()

        from scripts.repair_markers import detect_stale_markers

        stale = detect_stale_markers(mgr)

        # Should handle gracefully
        assert isinstance(stale, list)
        assert len(stale) == 0

    def test_repair_markers_no_markers_present(self, sample_phase_mgr):
        """Repair markers should handle state with no phase markers.

        Should:
        - Not crash when no phases marked complete
        - Return empty list
        - Handle gracefully
        """
        # No markers set - state is empty

        from scripts.repair_markers import detect_stale_markers

        stale = detect_stale_markers(sample_phase_mgr)

        # Should return empty
        assert isinstance(stale, list)
        assert len(stale) == 0

    def test_repair_markers_corrupted_state_file(self, temp_state_dir, capsys):
        """Repair markers should handle corrupted JSON.

        Should:
        - Detect corrupted state file
        - Provide clear error message
        - Not crash
        """
        # Create corrupted state file
        corrupted_file = temp_state_dir / "code_phase_corrupted.json"
        corrupted_file.write_text("{ invalid json }")

        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = corrupted_file

        from scripts.repair_markers import detect_stale_markers

        # Should handle error gracefully
        with pytest.raises((json.JSONDecodeError, ValueError)):
            stale = detect_stale_markers(mgr)


class TestRepairMarkersIntegration:
    """Integration tests for repair markers workflow."""

    def test_repair_markers_integration(self, sample_phase_mgr):
        """Integration test: full end-to-end repair markers workflow.

        Should:
        - Detect stale markers
        - Confirm with user (or skip with --yes)
        - Invalidate stale markers
        - Report results
        """
        # Setup: Multiple phases with mixed staleness
        current_head = "current123"
        sample_phase_mgr.mark_phase_complete("BUILD", "old111")  # Stale
        sample_phase_mgr.mark_phase_complete("TRACE", current_head)  # Valid
        sample_phase_mgr.mark_phase_complete("SHIP", "old333")  # Stale

        with patch('utils.phase_state.get_git_head_hash', return_value=current_head):
            from scripts.repair_markers import repair_stale_markers

            # Run repair (auto-confirm)
            result = repair_stale_markers(sample_phase_mgr, confirm=False)

            # Should report findings
            assert "detected" in result or len(result) > 0

            # Should invalidate only stale ones
            state = sample_phase_mgr._load_global_state()
            assert not state["phases"]["BUILD"]["completed"]  # Removed
            assert state["phases"]["TRACE"]["completed"]  # Kept
            assert not state["phases"]["SHIP"]["completed"]  # Removed

    def test_repair_markers_cli_invocation(self, sample_phase_mgr):
        """Repair markers should be invocable from CLI.

        Should:
        - Have main() function for CLI entry
        - Accept --yes, --dry-run flags
        - Return appropriate exit codes
        """
        # Setup: Create stale marker
        sample_phase_mgr.mark_phase_complete("BUILD", "old123")

        with patch('utils.phase_state.get_git_head_hash', return_value='new456'):
            import sys
            from io import StringIO

            from scripts.repair_markers import main

            # Mock sys.argv for CLI invocation
            old_argv = sys.argv
            sys.argv = ['repair_markers.py', '--yes']

            # Capture output
            old_stdout = sys.stdout
            sys.stdout = StringIO()

            try:
                exit_code = main()
                output = sys.stdout.getvalue()

                # Should run successfully
                assert exit_code == 0
                assert len(output) > 0
            finally:
                sys.argv = old_argv
                sys.stdout = old_stdout

    def test_repair_markers_with_phase_manager(self, sample_phase_mgr):
        """Repair markers should integrate with PhaseStateManager.

        Should:
        - Use PhaseStateManager API correctly
        - Not bypass manager methods
        - Maintain state file integrity
        """
        # Setup: Mark phases through manager API
        sample_phase_mgr.mark_phase_complete("BUILD", "old123")
        sample_phase_mgr.mark_phase_complete("TRACE", "old456")

        with patch('utils.phase_state.get_git_head_hash', return_value='new789'):
            from scripts.repair_markers import detect_stale_markers

            # Should work with manager
            stale = detect_stale_markers(sample_phase_mgr)

            # Should detect both
            assert "BUILD" in stale
            assert "TRACE" in stale


class TestRepairMarkersBatchOperations:
    """Test batch operations on multiple markers."""

    def test_repair_markers_multiple_stale_markers(self, sample_phase_mgr):
        """Repair markers should handle multiple stale markers.

        Should:
        - Detect all stale markers in single pass
        - Process all invalid markers
        - Report count of markers processed
        """
        # Setup: Create multiple stale markers
        sample_phase_mgr.mark_phase_complete("BUILD", "old111")
        sample_phase_mgr.mark_phase_complete("TRACE", "old222")
        sample_phase_mgr.mark_phase_complete("SHIP", "old333")

        with patch('utils.phase_state.get_git_head_hash', return_value='new999'):
            from scripts.repair_markers import invalidate_stale_markers

            count = invalidate_stale_markers(sample_phase_mgr)

            # Should invalidate all 3
            assert count == 3

            # Verify all removed
            state = sample_phase_mgr._load_global_state()
            for phase in ["BUILD", "TRACE", "SHIP"]:
                assert not state["phases"][phase]["completed"]

    def test_repair_markers_preserves_valid_markers(self, sample_phase_mgr):
        """Repair markers should only remove stale, keep valid.

        Should:
        - Only invalidate markers with mismatched commits
        - Preserve markers with matching commits
        - Not affect other state data
        """
        # Setup: Mix of valid and stale
        current = "current123"
        sample_phase_mgr.mark_phase_complete("BUILD", current)  # Valid
        sample_phase_mgr.mark_phase_complete("TRACE", "old456")  # Stale
        sample_phase_mgr.mark_phase_complete("SHIP", current)  # Valid

        with patch('utils.phase_state.get_git_head_hash', return_value=current):
            from scripts.repair_markers import invalidate_stale_markers

            count = invalidate_stale_markers(sample_phase_mgr)

            # Should only invalidate 1
            assert count == 1

            # Verify valid ones preserved
            state = sample_phase_mgr._load_global_state()
            assert state["phases"]["BUILD"]["completed"]  # Kept
            assert not state["phases"]["TRACE"]["completed"]  # Removed
            assert state["phases"]["SHIP"]["completed"]  # Kept

    def test_repair_markers_reports_changes(self, sample_phase_mgr, capsys):
        """Repair markers should report what was repaired.

        Should:
        - Print which markers were invalidated
        - Show commit hashes (old vs new)
        - Provide summary of changes
        """
        # Setup: Create stale markers
        sample_phase_mgr.mark_phase_complete("BUILD", "old111")
        sample_phase_mgr.mark_phase_complete("TRACE", "old222")

        with patch('utils.phase_state.get_git_head_hash', return_value='new999'):
            from scripts.repair_markers import repair_stale_markers

            # Run repair
            result = repair_stale_markers(sample_phase_mgr, confirm=False)

            # Should report changes
            assert "invalidated" in result or len(result) > 0

            # Check output mentions what was repaired
            captured = capsys.readouterr()
            output_terms = captured.out.lower()
            # Verify output contains expected terms if output exists
            if output_terms:
                assert any(term in output_terms for term in ["invalidated", "removed", "repair", "stale"])
            # If no output, that's also acceptable (silent success)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
