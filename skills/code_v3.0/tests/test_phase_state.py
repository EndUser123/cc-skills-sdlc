#!/usr/bin/env python3
"""Unit tests for phase state manager."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.phase_state import (
    PhaseStateManager,
    get_git_head_hash,
)


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


class TestPhaseStateManager:
    """Test phase state manager functionality."""

    def test_state_creation(self, temp_state_dir):
        """State files should be created on initialization."""
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file
        original_build = mgr.build_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr.build_state_file = temp_state_dir / "code_build_state_test_terminal.json"
            mgr._ensure_state_exists()

            assert mgr.global_state_file.exists()
            assert mgr.build_state_file.exists()

            # Verify global state structure
            global_data = json.loads(mgr.global_state_file.read_text())
            assert global_data["version"] == "1.0"
            assert "phases" in global_data

            # Verify build state structure
            build_data = json.loads(mgr.build_state_file.read_text())
            assert build_data["version"] == "1.0"
            assert build_data["terminal_id"] == "test_terminal"
        finally:
            mgr.global_state_file = original_global
            mgr.build_state_file = original_build

    def test_mark_phase_complete(self, temp_state_dir):
        """Mark phase as complete with commit hash."""
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr._ensure_state_exists()

            mgr.mark_phase_complete("BUILD", "abc123")

            status = mgr.get_phase_status("BUILD")
            assert status["completed"] == True
            assert status["commit_hash"] == "abc123"
            assert status["terminal_id"] == "test_terminal"
        finally:
            mgr.global_state_file = original_global

    def test_is_phase_valid(self, temp_state_dir):
        """Phase validity check with commit hash."""
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr._ensure_state_exists()

            # Mark phase complete with test hash
            mgr.mark_phase_complete("BUILD", "abc123")

            # Since git HEAD won't match "abc123", phase should be invalid
            # (unless we're in a repo with HEAD == "abc123", which is unlikely)
            current_hash = get_git_head_hash()
            if current_hash == "abc123":
                # In a test repo with this exact hash (unlikely)
                assert mgr.is_phase_valid("BUILD") is True
            else:
                # Normal case: hashes don't match
                assert mgr.is_phase_valid("BUILD") is False

            # Test without commit hash - should always be invalid
            mgr.mark_phase_complete("TRACE", None)
            assert mgr.is_phase_valid("TRACE") is False
        finally:
            mgr.global_state_file = original_global

    def test_invalidate_phase(self, temp_state_dir):
        """Invalidate a phase."""
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr._ensure_state_exists()

            mgr.mark_phase_complete("BUILD", "abc123")
            mgr.invalidate_phase("BUILD")

            status = mgr.get_phase_status("BUILD")
            assert status["completed"] == False
        finally:
            mgr.global_state_file = original_global

    def test_build_ownership(self, temp_state_dir):
        """Build ownership acquisition and release."""
        mgr = PhaseStateManager("test_terminal")
        original_build = mgr.build_state_file

        try:
            mgr.build_state_file = temp_state_dir / "code_build_state_test_terminal.json"
            mgr._ensure_state_exists()

            # Acquire ownership
            assert mgr.acquire_build_ownership() == True

            state = mgr._load_build_state()
            assert state["current_owner"] == "test_terminal"

            # Release ownership
            mgr.release_build_ownership()

            state = mgr._load_build_state()
            assert state["current_owner"] is None
        finally:
            mgr.build_state_file = original_build

    def test_get_all_phases_status(self, temp_state_dir):
        """Get status of all phases."""
        mgr = PhaseStateManager("test_terminal")
        original_global = mgr.global_state_file

        try:
            mgr.global_state_file = temp_state_dir / "code_phase_state.json"
            mgr._ensure_state_exists()

            mgr.mark_phase_complete("BUILD", "abc123")
            mgr.mark_phase_complete("TRACE", "def456")

            all_status = mgr.get_all_phases_status()

            assert "BUILD" in all_status
            assert "TRACE" in all_status
            assert all_status["BUILD"]["completed"] == True
            assert all_status["TRACE"]["completed"] == True
        finally:
            mgr.global_state_file = original_global


class TestGitHash:
    """Test git hash retrieval."""

    def test_get_git_head_hash(self):
        """Should return hash or None depending on git repo."""
        hash_value = get_git_head_hash()

        # In a git repo, should return 40-char hex string
        # Not in a git repo, should return None
        if hash_value:
            assert len(hash_value) == 40
            assert all(c in "0123456789abcdef" for c in hash_value)
        else:
            assert hash_value is None


class TestGitHashExceptionHandling:
    """Tests for exception handling in get_git_head_hash()."""

    def test_timeout_expired_returns_none(self):
        """
        Test that get_git_head_hash() returns None when subprocess.run raises TimeoutExpired.

        Given: subprocess.run will raise subprocess.TimeoutExpired
        When: get_git_head_hash() is called
        Then: The function catches the exception and returns None
        """
        # Arrange
        mock_timeout = subprocess.TimeoutExpired("git", 5)

        # Act & Assert
        with patch("utils.phase_state.subprocess.run", side_effect=mock_timeout):
            result = get_git_head_hash()
            assert result is None

    def test_file_not_found_returns_none(self):
        """
        Test that get_git_head_hash() returns None when subprocess.run raises FileNotFoundError.

        Given: subprocess.run will raise FileNotFoundError (e.g., git not installed)
        When: get_git_head_hash() is called
        Then: The function catches the exception and returns None
        """
        # Arrange
        mock_not_found = FileNotFoundError("git not found")

        # Act & Assert
        with patch("utils.phase_state.subprocess.run", side_effect=mock_not_found):
            result = get_git_head_hash()
            assert result is None

    def test_generic_exception_propagates(self):
        """
        Test that get_git_head_hash() propagates unexpected exceptions.

        Given: subprocess.run will raise an unexpected exception (e.g., PermissionError)
        When: get_git_head_hash() is called
        Then: The exception should propagate to the caller
        """
        # Arrange
        mock_permission_error = PermissionError("Permission denied")

        # Act & Assert
        with patch("utils.phase_state.subprocess.run", side_effect=mock_permission_error):
            with pytest.raises(PermissionError):
                get_git_head_hash()


class TestTerminalIdSanitization:
    """Test terminal ID sanitization for multi-terminal isolation."""

    def test_sanitization_removes_dangerous_chars(self):
        """Dangerous characters should be removed from terminal ID."""
        from utils.phase_state import _sanitize_terminal_id

        # Path traversal attempts
        assert _sanitize_terminal_id("../../etc/passwd") == "etcpasswd"
        assert _sanitize_terminal_id("terminal_1/../../secret") == "terminal_1secret"

        # Special characters
        assert _sanitize_terminal_id("terminal@1#") == "terminal1"
        assert _sanitize_terminal_id("term.inal") == "terminal"

    def test_sanitization_preserves_safe_chars(self):
        """Safe characters (alphanumeric, underscore, hyphen) should be preserved."""
        from utils.phase_state import _sanitize_terminal_id

        assert _sanitize_terminal_id("terminal_123") == "terminal_123"
        assert _sanitize_terminal_id("term-456") == "term-456"
        assert _sanitize_terminal_id("Term_123-ABC") == "Term_123-ABC"

    def test_sanitization_fallback_to_default(self):
        """Empty or None input should fallback to 'default'."""
        from utils.phase_state import _sanitize_terminal_id

        assert _sanitize_terminal_id("") == "default"
        assert _sanitize_terminal_id(None) == "default"
        # After stripping all special chars, empty string falls back to default
        assert _sanitize_terminal_id("@#$") == "default"

    def test_terminal_scoped_state_paths(self):
        """State file paths should include sanitized terminal ID."""
        from utils.phase_state import PhaseStateManager

        mgr1 = PhaseStateManager("terminal_1")
        mgr2 = PhaseStateManager("terminal_2")

        # Each terminal should have different state files
        assert mgr1.global_state_file != mgr2.global_state_file
        assert mgr1.build_state_file != mgr2.build_state_file

        # Paths should contain terminal ID
        assert "terminal_1" in str(mgr1.global_state_file)
        assert "terminal_2" in str(mgr2.global_state_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
