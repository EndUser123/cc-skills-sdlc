#!/usr/bin/env python3
"""Unit tests for phase transition validation script."""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# This import will FAIL with ModuleNotFoundError until we implement the script
from scripts.validate_phase_transition import validate_phase_transition
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


class TestValidatePhaseTransition:
    """Test phase transition validation functionality."""

    def test_valid_transition_build_to_trace(self, temp_state_dir):
        """Test valid BUILD → TRACE transition."""
        # Setup BUILD phase as complete
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()
        mgr.mark_phase_complete("BUILD", "abc123")

        # This should pass once script exists
        result = validate_phase_transition("TRACE", mgr)
        assert result is True

    def test_valid_transition_trace_to_ship(self, temp_state_dir):
        """Test valid TRACE → SHIP transition."""
        # Setup TRACE phase as complete
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()
        mgr.mark_phase_complete("TRACE", "abc123")

        # This should pass once script exists
        result = validate_phase_transition("SHIP", mgr)
        assert result is True

    def test_invalid_transition_bootstrap_to_ship(self, temp_state_dir):
        """Test invalid BOOTSTRAP → SHIP transition (skips phases)."""
        # Setup BOOTSTRAP phase as complete
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()
        mgr.mark_phase_complete("BOOTSTRAP", "abc123")

        # This should fail with proper error message once script exists
        with pytest.raises(ValueError) as exc_info:
            validate_phase_transition("SHIP", mgr)
        # Error should mention that previous phase is not completed
        assert "previous phase" in str(exc_info.value).lower()
        assert "not completed" in str(exc_info.value).lower()

    def test_invalid_regression_ship_to_build(self, temp_state_dir):
        """Test invalid SHIP → BUILD transition (regression)."""
        # Setup SHIP phase as complete
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()
        mgr.mark_phase_complete("SHIP", "abc123")

        # This should fail with proper error message once script exists
        with pytest.raises(ValueError) as exc_info:
            validate_phase_transition("BUILD", mgr)
        assert "regression" in str(exc_info.value).lower()

    def test_phase_validity_check_rollback_detected(self, temp_state_dir):
        """Test phase validation fails after git rollback."""
        # Setup BUILD phase as complete with 40-char hash (real git hash format)
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()
        # Use 40-char hash to trigger rollback detection
        mgr.mark_phase_complete("BUILD", "abc123def456789abc123def456789abc123def4")

        # Mock git head hash to simulate rollback (different from recorded hash)
        with patch('utils.phase_state.get_git_head_hash', return_value="def456abc123def456abc123def456abc123def456"):
            # This should fail with rollback error once script exists
            with pytest.raises(ValueError) as exc_info:
                validate_phase_transition("TRACE", mgr)
            assert "rollback" in str(exc_info.value).lower()

    def test_phase_validity_check_no_commit_hash(self, temp_state_dir):
        """Test phase validation fails without commit hash."""
        # Setup BUILD phase as complete but no commit hash
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()
        mgr.mark_phase_complete("BUILD", None)  # No commit hash

        # Mock git head hash to simulate no commit
        with patch('utils.phase_state.get_git_head_hash', return_value=None):
            # This should fail with no commit hash error once script exists
            with pytest.raises(ValueError) as exc_info:
                validate_phase_transition("TRACE", mgr)
            assert "commit hash" in str(exc_info.value).lower()

    def test_error_message_clarity(self, temp_state_dir):
        """Test that error messages are clear and actionable."""
        # Test invalid transition error message
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()
        mgr.mark_phase_complete("SHIP", "abc123")

        try:
            validate_phase_transition("BUILD", mgr)
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            # Check that error message contains key information
            assert "BUILD" in error_msg
            assert "SHIP" in error_msg
            assert "regression" in error_msg.lower()
            # Check that it provides actionable information
            assert "detected" in error_msg.lower() or "cannot" in error_msg.lower()
            # Check for phase order information
            assert "phase order" in error_msg.lower() or "unidirectional" in error_msg.lower()


class TestPhaseTransitionIntegration:
    """Integration tests for phase transition validation."""

    def test_phase_order_enforcement_sequence(self, temp_state_dir):
        """Test full phase sequence enforcement: BUILD → TRACE → SHIP."""
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()

        # Simulate complete phase sequence
        mgr.mark_phase_complete("BUILD", "build123")

        # This should work when script is implemented
        validate_phase_transition("TRACE", mgr)  # Should pass

        mgr.mark_phase_complete("TRACE", "trace123")

        # This should work when script is implemented
        validate_phase_transition("SHIP", mgr)  # Should pass

    def test_phase_with_missing_phase_state(self, temp_state_dir):
        """Test transition when previous phase is not completed."""
        mgr = PhaseStateManager("test_terminal")
        mgr.global_state_file = temp_state_dir / "code_phase_state.json"
        mgr._ensure_state_exists()

        # Don't complete any phase
        try:
            validate_phase_transition("TRACE", mgr)
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            assert "previous phase" in str(e).lower()
            assert "not completed" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
