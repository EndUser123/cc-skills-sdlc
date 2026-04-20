#!/usr/bin/env python3
"""Unit tests for phase state manager metadata handling."""

import shutil
import sys
import tempfile
from pathlib import Path

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


class TestPhaseMetadataHandling:
    """Test metadata handling in mark_phase_complete()."""

    def test_mark_phase_complete_with_metadata(self, temp_state_dir):
        """
        Test that metadata dict with multiple key-value pairs is stored and accessible.

        Given: A PhaseStateManager instance
        When: mark_phase_complete() is called with metadata dict containing multiple keys
        Then: Metadata should be stored in phase state and accessible via get_phase_status()
        """
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr._ensure_state_exists()

            # Arrange: Create metadata dict with multiple key-value pairs
            metadata = {
                "test_count": 42,
                "test_duration_ms": 1500,
                "test_runner": "pytest",
                "environment": "development"
            }

            # Act: Mark phase complete with metadata
            mgr.mark_phase_complete("TEST", "abc123", metadata=metadata)

            # Assert: Metadata is accessible via get_phase_status()
            status = mgr.get_phase_status("TEST")

            # Verify basic phase completion still works
            assert status["completed"] == True
            assert status["commit_hash"] == "abc123"

            # Verify metadata is stored and accessible
            assert status["metadata"] == metadata
            assert status["metadata"]["test_count"] == 42
            assert status["metadata"]["test_duration_ms"] == 1500
            assert status["metadata"]["test_runner"] == "pytest"
            assert status["metadata"]["environment"] == "development"

        finally:
            mgr.global_state_file = original_global

    def test_mark_phase_complete_with_empty_metadata(self, temp_state_dir):
        """
        Test that empty metadata dict adds no extra keys to phase state.

        Given: A PhaseStateManager instance
        When: mark_phase_complete() is called with empty dict metadata
        Then: Phase should complete normally but no metadata keys should be added
        """
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr._ensure_state_exists()

            # Act: Mark phase complete with empty metadata
            mgr.mark_phase_complete("BUILD", "def456", metadata={})

            # Assert: Phase completes but metadata dict is empty
            status = mgr.get_phase_status("BUILD")

            assert status["completed"] == True
            assert status["commit_hash"] == "def456"
            assert status["metadata"] == {}

            # Verify only standard keys exist in phase state
            state = mgr._load_global_state()
            phase_state = state["phases"]["BUILD"]
            expected_keys = {"completed", "completed_at", "terminal_id", "commit_hash"}
            assert set(phase_state.keys()) == expected_keys

        finally:
            mgr.global_state_file = original_global

    def test_mark_phase_complete_with_none_metadata(self, temp_state_dir):
        """
        Test that None metadata parameter is handled gracefully.

        Given: A PhaseStateManager instance
        When: mark_phase_complete() is called with metadata=None (default)
        Then: Phase should complete normally without errors and no metadata keys added
        """
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr._ensure_state_exists()

            # Act: Mark phase complete with None metadata (default parameter)
            mgr.mark_phase_complete("TRACE", "ghi789", metadata=None)

            # Assert: Phase completes without errors, no metadata added
            status = mgr.get_phase_status("TRACE")

            assert status["completed"] == True
            assert status["commit_hash"] == "ghi789"
            assert status["metadata"] == {}

            # Verify only standard keys exist in phase state
            state = mgr._load_global_state()
            phase_state = state["phases"]["TRACE"]
            expected_keys = {"completed", "completed_at", "terminal_id", "commit_hash"}
            assert set(phase_state.keys()) == expected_keys

        finally:
            mgr.global_state_file = original_global


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
