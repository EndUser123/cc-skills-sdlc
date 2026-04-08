#!/usr/bin/env python3
"""Unit tests for evidence manager."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.evidence import EvidenceManager


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    old_cwd = Path.cwd()

    # Create state directory
    state_dir = temp_dir / ".claude" / "state"
    state_dir.mkdir(parents=True)

    yield state_dir

    # Cleanup
    shutil.rmtree(temp_dir)


class TestEvidenceManager:
    """Test evidence manager functionality."""

    def test_ledger_creation(self, temp_state_dir):
        """Ledger should be created on initialization."""
        # Monkey-patch the ledger file path
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            assert mgr.ledger_file.exists()
            data = json.loads(mgr.ledger_file.read_text())
            assert data["version"] == "1.0"
            assert data["terminal_id"] == "test_terminal"
        finally:
            mgr.ledger_file = original_path

    def test_record_red(self, temp_state_dir):
        """Record RED stage evidence."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            mgr.record_red(
                "task_1",
                ["tests/test_auth.py"],
                "pytest tests/test_auth.py",
                3
            )

            # Verify evidence was recorded
            status = mgr.get_task_status("task_1")
            assert status["exists"] == True
            assert status["evidence"]["RED"]["completed"] == True
            assert status["evidence"]["RED"]["failing_tests"] == 3
        finally:
            mgr.ledger_file = original_path

    def test_record_green(self, temp_state_dir):
        """Record GREEN stage evidence."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            mgr.record_green(
                "task_1",
                ["src/auth.py"],
                "pytest tests/test_auth.py",
                3
            )

            status = mgr.get_task_status("task_1")
            assert status["evidence"]["GREEN"]["completed"] == True
            assert status["evidence"]["GREEN"]["passing_tests"] == 3
        finally:
            mgr.ledger_file = original_path

    def test_can_mark_done_missing_evidence(self, temp_state_dir):
        """Cannot mark done without all evidence types."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Only record RED evidence
            mgr.record_red("task_1", [], "pytest", 1)

            can_done, msg = mgr.can_mark_done("task_1")
            assert can_done == False
            assert "missing evidence" in msg.lower()
        finally:
            mgr.ledger_file = original_path

    def test_mark_done_success(self, temp_state_dir):
        """Can mark done with all 4 evidence types."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Record all 4 stages
            mgr.record_red("task_1", [], "pytest", 1)
            mgr.record_green("task_1", [], "pytest", 1)
            mgr.record_refactor("task_1", [], "pytest", 1)
            mgr.record_verify("task_1", 0, 0, "PASS")

            can_done, msg = mgr.can_mark_done("task_1")
            assert can_done == True

            mgr.mark_done("task_1")

            status = mgr.get_task_status("task_1")
            assert status["done"] == True
        finally:
            mgr.ledger_file = original_path

    def test_mark_done_failure(self, temp_state_dir):
        """mark_done should raise ValueError with missing evidence."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Only record RED
            mgr.record_red("task_1", [], "pytest", 1)

            with pytest.raises(ValueError, match="missing evidence"):
                mgr.mark_done("task_1")
        finally:
            mgr.ledger_file = original_path


class TestImplementationVerification:
    """Test implementation file verification for false completion prevention."""

    def test_verify_implementation_exists_all_files_present(self, temp_state_dir):
        """Should return empty list when all files exist."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Create test files
            test_impl = temp_state_dir / "impl.py"
            test_file = temp_state_dir / "test.py"
            test_impl.write_text("# impl")
            test_file.write_text("# test")

            # Record evidence with existing files
            mgr.record_red("task_1", [str(test_file)], "pytest", 1)
            mgr.record_green("task_1", [str(test_impl)], "pytest", 1)

            # Verify
            missing = mgr._verify_implementation_exists("task_1")
            assert missing == []
        finally:
            mgr.ledger_file = original_path

    def test_verify_implementation_exists_missing_impl_file(self, temp_state_dir):
        """Should detect missing implementation file."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Only create test file, not impl
            test_file = temp_state_dir / "test.py"
            test_file.write_text("# test")

            # Record evidence with missing impl file
            mgr.record_red("task_1", [str(test_file)], "pytest", 1)
            mgr.record_green("task_1", [str(temp_state_dir / "missing_impl.py")], "pytest", 1)

            # Verify
            missing = mgr._verify_implementation_exists("task_1")
            assert len(missing) == 1
            assert "missing_impl.py" in missing[0]
        finally:
            mgr.ledger_file = original_path

    def test_verify_implementation_exists_missing_test_file(self, temp_state_dir):
        """Should detect missing test file."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Only create impl file, not test
            test_impl = temp_state_dir / "impl.py"
            test_impl.write_text("# impl")

            # Record evidence with missing test file
            mgr.record_red("task_1", [str(temp_state_dir / "missing_test.py")], "pytest", 1)
            mgr.record_green("task_1", [str(test_impl)], "pytest", 1)

            # Verify
            missing = mgr._verify_implementation_exists("task_1")
            assert len(missing) == 1
            assert "missing_test.py" in missing[0]
        finally:
            mgr.ledger_file = original_path

    def test_verify_implementation_exists_multiple_missing(self, temp_state_dir):
        """Should detect all missing files."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Record evidence with missing files
            mgr.record_red("task_1", [str(temp_state_dir / "missing1.py")], "pytest", 1)
            mgr.record_green("task_1", [str(temp_state_dir / "missing2.py")], "pytest", 1)

            # Verify
            missing = mgr._verify_implementation_exists("task_1")
            assert len(missing) == 2
        finally:
            mgr.ledger_file = original_path

    def test_verify_implementation_unknown_task(self, temp_state_dir):
        """Should return empty list for unknown task."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Verify unknown task
            missing = mgr._verify_implementation_exists("unknown_task")
            assert missing == []
        finally:
            mgr.ledger_file = original_path


class TestMarkDoneWithVerification:
    """Test mark_done with implementation file verification."""

    def test_mark_done_blocks_on_missing_impl_file(self, temp_state_dir):
        """mark_done should raise ValueError when implementation file is missing."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Create test file but not impl file
            test_file = temp_state_dir / "test.py"
            test_file.write_text("# test")

            # Record all evidence with missing impl file
            mgr.record_red("task_1", [str(test_file)], "pytest", 1)
            mgr.record_green("task_1", [str(temp_state_dir / "missing_impl.py")], "pytest", 1)
            mgr.record_refactor("task_1", [], "pytest", 1)
            mgr.record_verify("task_1", 0, 0, "PASS")

            # Should raise ValueError
            with pytest.raises(ValueError, match="Implementation files missing"):
                mgr.mark_done("task_1")
        finally:
            mgr.ledger_file = original_path

    def test_mark_done_succeeds_with_all_files_present(self, temp_state_dir):
        """mark_done should succeed when all files exist."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Create both files
            test_file = temp_state_dir / "test.py"
            test_impl = temp_state_dir / "impl.py"
            test_file.write_text("# test")
            test_impl.write_text("# impl")

            # Record all evidence with existing files
            mgr.record_red("task_1", [str(test_file)], "pytest", 1)
            mgr.record_green("task_1", [str(test_impl)], "pytest", 1)
            mgr.record_refactor("task_1", [], "pytest", 1)
            mgr.record_verify("task_1", 0, 0, "PASS")

            # Should succeed
            mgr.mark_done("task_1")

            # Verify task is marked done
            status = mgr.get_task_status("task_1")
            assert status["done"] == True
        finally:
            mgr.ledger_file = original_path


class TestFileLocking:
    """Test Windows file locking for multi-terminal safety."""

    def test_load_ledger_locked_returns_data(self, temp_state_dir):
        """Locked load should return ledger data."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Load with lock
            ledger = mgr._load_ledger_locked()
            assert ledger["version"] == "1.0"
            assert ledger["terminal_id"] == "test_terminal"
        finally:
            mgr.ledger_file = original_path

    def test_save_ledger_locked_persists_data(self, temp_state_dir):
        """Locked save should persist ledger data."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Record some evidence
            mgr.record_red("task_1", [], "pytest", 1)

            # Save with lock
            ledger = mgr._load_ledger_locked()
            ledger["test_key"] = "test_value"
            mgr._save_ledger_locked(ledger)

            # Verify persistence
            reloaded = mgr._load_ledger_locked()
            assert reloaded["test_key"] == "test_value"
        finally:
            mgr.ledger_file = original_path

    def test_mark_done_uses_locked_methods(self, temp_state_dir):
        """mark_done should use locked ledger methods."""
        mgr = EvidenceManager("test_terminal")
        original_path = mgr.ledger_file

        try:
            mgr.ledger_file = temp_state_dir / "code_evidence_test_terminal.json"
            mgr._ensure_ledger_exists()

            # Create files
            test_file = temp_state_dir / "test.py"
            test_impl = temp_state_dir / "impl.py"
            test_file.write_text("# test")
            test_impl.write_text("# impl")

            # Record all evidence
            mgr.record_red("task_1", [str(test_file)], "pytest", 1)
            mgr.record_green("task_1", [str(test_impl)], "pytest", 1)
            mgr.record_refactor("task_1", [], "pytest", 1)
            mgr.record_verify("task_1", 0, 0, "PASS")

            # Mark done (should use locked methods)
            mgr.mark_done("task_1")

            # Verify task is done
            status = mgr.get_task_status("task_1")
            assert status["done"] == True
            assert "done_at" in status
        finally:
            mgr.ledger_file = original_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
