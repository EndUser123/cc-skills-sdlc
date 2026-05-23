#!/usr/bin/env python3
"""Tests for TDD Evidence Tracking - RED phase (failing tests)."""

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib.evidence_writer import (
        cleanup_old_evidence,
        debug_log,
        generate_evidence_artifact,
        is_evidence_tracking_enabled,
    )

    EVIDENCE_TRACKING_AVAILABLE = True
except ImportError:
    EVIDENCE_TRACKING_AVAILABLE = False
    cleanup_old_evidence = None
    debug_log = None
    generate_evidence_artifact = None
    is_evidence_tracking_enabled = None


class TestEvidenceTrackingModule:
    """Test evidence tracking infrastructure - NEW FUNCTIONALITY."""

    def test_generate_evidence_artifact_function_exists(self):
        """generate_evidence_artifact function should exist."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        assert callable(
            generate_evidence_artifact
        ), "generate_evidence_artifact should be a callable function"

    def test_cleanup_old_evidence_function_exists(self):
        """cleanup_old_evidence function should exist."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        assert callable(cleanup_old_evidence), "cleanup_old_evidence should be a callable function"

    def test_is_evidence_tracking_enabled_function_exists(self):
        """is_evidence_tracking_enabled function should exist for feature flag."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        assert callable(
            is_evidence_tracking_enabled
        ), "is_evidence_tracking_enabled should be a callable function"

    def test_is_evidence_tracking_enabled_returns_bool(self):
        """is_evidence_tracking_enabled should return boolean."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        result = is_evidence_tracking_enabled()
        assert isinstance(result, bool), "is_evidence_tracking_enabled should return a boolean"

    def test_debug_log_function_exists(self):
        """debug_log function should exist for debug logging."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        assert callable(debug_log), "debug_log should be a callable function"


class TestEvidenceArtifactGeneration:
    """Test evidence artifact generation - NEW FUNCTIONALITY."""

    def setup_method(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.evidence_dir = Path(self.temp_dir) / ".evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        # Enable evidence tracking for tests
        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"

    def teardown_method(self):
        """Clean up temporary directory."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        # Clean up environment variable
        os.environ.pop("TDD_EVIDENCE_TRACKING_ENABLED", None)

    def test_generate_evidence_artifact_creates_file(self):
        """generate_evidence_artifact should create evidence file."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        task_id = "TEST-001"
        phase = "RED"
        evidence = {
            "test_files": ["test_example.py"],
            "requirements": ["Test requirement 1"],
        }

        artifact_path = generate_evidence_artifact(
            task_id=task_id,
            phase=phase,
            evidence=evidence,
            skill_dir=Path(self.temp_dir),
            terminal_id="test_terminal",
        )

        assert artifact_path is not None, "generate_evidence_artifact should return a path"
        assert artifact_path.exists(), f"Artifact file should exist at {artifact_path}"

    def test_generate_evidence_artifact_contains_timestamp(self):
        """Evidence artifacts should contain UTC timestamp."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        task_id = "TEST-002"
        phase = "GREEN"
        evidence = {
            "implementation": "Added feature X",
            "test_results": "All tests passed",
        }

        artifact_path = generate_evidence_artifact(
            task_id=task_id,
            phase=phase,
            evidence=evidence,
            skill_dir=Path(self.temp_dir),
            terminal_id="test_terminal",
        )

        content = artifact_path.read_text()
        # Check for timestamp field (with or without markdown bolding)
        assert "Timestamp" in content, "Artifact should contain timestamp field"
        # Check for UTC timezone indicator
        assert (
            "UTC" in content or "+00:00" in content or "Z" in content
        ), "Timestamp should be in UTC"

    def test_generate_evidence_artifact_contains_phase(self):
        """Evidence artifacts should contain phase name."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        task_id = "TEST-003"
        phase = "REFACTOR"
        evidence = {
            "refactoring_changes": "Cleaned up code",
            "test_confirmation": "Tests still pass",
        }

        artifact_path = generate_evidence_artifact(
            task_id=task_id,
            phase=phase,
            evidence=evidence,
            skill_dir=Path(self.temp_dir),
            terminal_id="test_terminal",
        )

        content = artifact_path.read_text()
        assert phase in content, f"Artifact should contain phase name: {phase}"

    def test_generate_evidence_artifact_contains_task_id(self):
        """Evidence artifacts should contain task ID."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        task_id = "TEST-004"
        phase = "RED"
        evidence = {"test_files": ["test_example.py"]}

        artifact_path = generate_evidence_artifact(
            task_id=task_id,
            phase=phase,
            evidence=evidence,
            skill_dir=Path(self.temp_dir),
            terminal_id="test_terminal",
        )

        content = artifact_path.read_text()
        assert task_id in content, f"Artifact should contain task ID: {task_id}"


class TestEvidenceCleanup:
    """Test evidence cleanup policy - NEW FUNCTIONALITY."""

    def setup_method(self):
        """Set up temporary directory with old and new artifacts."""
        self.temp_dir = tempfile.mkdtemp()
        self.evidence_dir = Path(self.temp_dir) / ".evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        # Create old artifact (10 days old)
        old_artifact = self.evidence_dir / "old_task_RED_20260301_120000.md"
        old_artifact.write_text("# Old Evidence\n\nTimestamp: 2026-03-01T12:00:00Z")

        # Set modification time to 10 days ago
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        old_timestamp = old_time.timestamp()
        os.utime(old_artifact, (old_timestamp, old_timestamp))

        # Create new artifact (1 day old)
        new_artifact = self.evidence_dir / "new_task_GREEN_20260310_120000.md"
        new_artifact.write_text("# New Evidence\n\nTimestamp: 2026-03-10T12:00:00Z")

    def teardown_method(self):
        """Clean up temporary directory."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_cleanup_old_evidence_removes_artifacts_older_than_7_days(self):
        """cleanup_old_evidence should remove artifacts older than 7 days."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        cleaned_count = cleanup_old_evidence(self.evidence_dir, max_days=7)

        assert cleaned_count == 1, f"Should clean 1 old artifact, but cleaned {cleaned_count}"

        # Verify old artifact removed
        old_artifact = self.evidence_dir / "old_task_RED_20260301_120000.md"
        assert not old_artifact.exists(), "Old artifact (>7 days) should be removed"

        # Verify new artifact remains
        new_artifact = self.evidence_dir / "new_task_GREEN_20260310_120000.md"
        assert new_artifact.exists(), "New artifact (<7 days) should remain"

    def test_cleanup_old_evidence_returns_count_of_cleaned_files(self):
        """cleanup_old_evidence should return count of cleaned files."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        cleaned_count = cleanup_old_evidence(self.evidence_dir, max_days=7)

        assert isinstance(cleaned_count, int), "cleanup_old_evidence should return an integer count"
        assert cleaned_count >= 0, "Cleaned count should be non-negative"

    def test_cleanup_old_evidence_keeps_recent_artifacts(self):
        """cleanup_old_evidence should keep artifacts newer than 7 days."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        cleanup_old_evidence(self.evidence_dir, max_days=7)

        # Verify new artifact still exists
        new_artifact = self.evidence_dir / "new_task_GREEN_20260310_120000.md"
        assert new_artifact.exists(), "Recent artifact (<7 days) should not be removed"

    def test_cleanup_old_evidence_handles_empty_directory(self):
        """cleanup_old_evidence should handle empty evidence directory."""
        if not EVIDENCE_TRACKING_AVAILABLE:
            pytest.skip("evidence tracking module not available - expected for RED phase")

        empty_dir = Path(self.temp_dir) / "empty_evidence"
        empty_dir.mkdir(parents=True, exist_ok=True)

        cleaned_count = cleanup_old_evidence(empty_dir, max_days=7)

        assert cleaned_count == 0, "cleanup_old_evidence should return 0 for empty directory"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
