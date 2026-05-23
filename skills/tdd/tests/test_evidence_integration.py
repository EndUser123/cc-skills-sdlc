#!/usr/bin/env python3
"""Tests for TDD evidence tracking integration - RED phase (failing tests)."""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))  # $CLAUDE_ROOT/skills\tdd
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))  # $CLAUDE_ROOT/skills\tdd\hooks
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "code"))  # $CLAUDE_ROOT/skills\code


class TestTDDEvidenceIntegration:
    """Test TDD-specific evidence tracking - NEW FUNCTIONALITY."""

    def test_tdd_hook_imports_evidence_manager(self):
        """TDD state hook should import EvidenceManager from /code."""
        # This test will FAIL because the import doesn't exist yet
        import PostToolUse_tdd_state as tdd_hook

        # Check if EvidenceManager is imported
        assert hasattr(
            tdd_hook, "EvidenceManager"
        ), "EvidenceManager should be imported in TDD state hook"

    def test_tdd_evidence_recorder_class_exists(self):
        """TDDEvidenceRecorder wrapper class should exist."""
        # This test will FAIL because TDDEvidenceRecorder doesn't exist yet
        from PostToolUse_tdd_state import TDDEvidenceRecorder

        # Check if class exists
        assert TDDEvidenceRecorder is not None, "TDDEvidenceRecorder class should exist"

    def test_record_tdd_state_snapshot(self):
        """Record TDD state snapshot (not test rerun)."""
        # This test will FAIL because evidence recording doesn't exist in hook
        from PostToolUse_tdd_state import record_tdd_evidence

        # Mock TDD state
        tdd_state = {
            "phase": "RED_CONFIRMED",
            "test_file": "tests/test_feature.py",
            "impl_files": [],
            "last_test_result": "failed",
            "last_test_exit_code": 1,
        }

        # Should record evidence
        result = record_tdd_evidence("TDD-001", tdd_state, terminal_id="test")

        assert result is not None, "Should return evidence recording result"
        assert result.get("success") == True, "Evidence recording should succeed"

    def test_evidence_artifact_directory_creation(self):
        """Evidence artifacts should be created in .evidence/ directory."""
        # This test will FAIL because artifact generation doesn't exist yet
        from PostToolUse_tdd_state import generate_evidence_artifact

        artifact_path = generate_evidence_artifact(
            task_id="TDD-001",
            phase="RED",
            evidence={"timestamp": "2026-03-15T10:00:00", "failing_tests": 3},
            terminal_id="test",
        )

        assert artifact_path.exists(), f"Artifact file should exist at {artifact_path}"
        assert artifact_path.suffix == ".md", "Artifact should be markdown file"

    def test_feature_flag_disabled_by_default(self):
        """Evidence tracking should be disabled by default."""
        # This test will FAIL because feature flag doesn't exist yet
        from PostToolUse_tdd_state import is_evidence_tracking_enabled

        # Default should be False
        assert (
            is_evidence_tracking_enabled() == False
        ), "Evidence tracking should be disabled by default"

    def test_feature_flag_enables_evidence_recording(self):
        """Feature flag should enable evidence recording."""
        # This test will FAIL because feature flag doesn't exist yet
        # Set feature flag
        import os

        from PostToolUse_tdd_state import is_evidence_tracking_enabled

        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"

        # Should return True when flag is set
        assert (
            is_evidence_tracking_enabled() == True
        ), "Evidence tracking should be enabled when flag is set"

    def test_evidence_cleanup_after_7_days(self):
        """Evidence artifacts older than 7 days should be cleaned up."""
        # This test will FAIL because cleanup doesn't exist yet
        from PostToolUse_tdd_state import cleanup_old_evidence

        # Create mock old artifacts
        temp_dir = Path(tempfile.mkdtemp())
        evidence_dir = temp_dir / ".evidence"
        evidence_dir.mkdir()

        # Create 10-day-old artifact
        old_artifact = evidence_dir / "TDD-001_RED_2026-03-05.md"
        old_artifact.write_text("# Old evidence")

        # Run cleanup
        cleanup_old_evidence(evidence_dir, max_days=7)

        # Old artifact should be deleted
        assert old_artifact.exists() == False, "Evidence older than 7 days should be cleaned up"

        # Cleanup temp dir
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
