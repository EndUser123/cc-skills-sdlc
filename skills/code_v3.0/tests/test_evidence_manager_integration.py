#!/usr/bin/env python3
"""Tests for EvidenceManager integration with /tdd skill."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add paths for imports - use absolute paths to avoid conflicts
# Resolve to code skill root from tests directory
code_skill_root = Path(__file__).parent.parent.resolve()
utils_path = code_skill_root / "utils"
tdd_skill_root = code_skill_root.parent / "tdd"
sys.path.insert(0, str(code_skill_root))  # For code skill modules
sys.path.insert(0, str(utils_path))  # For evidence.py
sys.path.insert(0, str(tdd_skill_root))  # For tdd skill lib

# Module-level variables (will be set during import)
EvidenceManager = None
evidence_writer = None
EVIDENCE_MANAGER_AVAILABLE = False
IMPORT_ERROR = None

try:
    # Import directly using absolute import to avoid naming conflicts
    # The evidence module in hooks/ has a different purpose
    import evidence as evidence_module

    EvidenceManager = evidence_module.EvidenceManager

    # Import evidence_writer from tdd skill
    import lib.evidence_writer as evidence_writer_module

    evidence_writer = evidence_writer_module

    # Set success flag
    EVIDENCE_MANAGER_AVAILABLE = True
    IMPORT_ERROR = None
except (ImportError, AttributeError) as e:
    EVIDENCE_MANAGER_AVAILABLE = False
    IMPORT_ERROR = str(e)


@pytest.fixture(scope="session")
def evidence_availability():
    """Fixture to provide evidence availability status to tests."""
    return {
        "available": EVIDENCE_MANAGER_AVAILABLE,
        "error": IMPORT_ERROR,
        "EvidenceManager": EvidenceManager,
        "evidence_writer": evidence_writer,
    }


class TestEvidenceManagerTDDIntegration:
    """Test EvidenceManager /tdd-specific method for generic evidence format."""

    def setup_method(self):
        """Set up temporary state directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.terminal_id = "test_terminal"

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        import shutil

        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_record_tdd_evidence_red_phase(self):
        """EvidenceManager.record_tdd_evidence() records RED phase correctly."""
        # Change to temp directory to avoid polluting real state
        import os

        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            manager = EvidenceManager(self.terminal_id)

            # Record RED evidence with generic dict
            evidence = {
                "test_files": ["test_feature.py"],
                "test_command": "pytest -v",
                "failing_tests": 3,
            }
            manager.record_tdd_evidence("TASK-001", "RED", evidence)

            # Verify evidence was recorded
            ledger = manager._load_ledger()
            task = ledger["tasks"]["TASK-001"]
            assert task["evidence"]["RED"]["completed"]
            assert task["evidence"]["RED"]["test_files"] == ["test_feature.py"]
            assert task["evidence"]["RED"]["failing_tests"] == 3

        finally:
            os.chdir(original_cwd)

    def test_record_tdd_evidence_green_phase(self):
        """EvidenceManager.record_tdd_evidence() records GREEN phase correctly."""
        import os

        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            manager = EvidenceManager(self.terminal_id)

            # Record GREEN evidence with generic dict
            evidence = {
                "impl_files": ["feature.py"],
                "test_command": "pytest -v",
                "passing_tests": 5,
            }
            manager.record_tdd_evidence("TASK-002", "GREEN", evidence)

            # Verify evidence was recorded
            ledger = manager._load_ledger()
            task = ledger["tasks"]["TASK-002"]
            assert task["evidence"]["GREEN"]["completed"]
            assert task["evidence"]["GREEN"]["impl_files"] == ["feature.py"]
            assert task["evidence"]["GREEN"]["passing_tests"] == 5

        finally:
            os.chdir(original_cwd)

    def test_record_tdd_evidence_refactor_phase(self):
        """EvidenceManager.record_tdd_evidence() records REFACTOR phase correctly."""
        import os

        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            manager = EvidenceManager(self.terminal_id)

            # Record REFACTOR evidence with generic dict
            evidence = {
                "changes": ["Cleaned up code structure", "Removed duplication"],
                "test_command": "pytest -v",
                "passing_tests": 5,
            }
            manager.record_tdd_evidence("TASK-003", "REFACTOR", evidence)

            # Verify evidence was recorded
            ledger = manager._load_ledger()
            task = ledger["tasks"]["TASK-003"]
            assert task["evidence"]["REFACTOR"]["completed"]
            assert "Cleaned up code structure" in task["evidence"]["REFACTOR"]["changes"]
            assert task["evidence"]["REFACTOR"]["passing_tests"] == 5

        finally:
            os.chdir(original_cwd)

    def test_record_tdd_evidence_verify_phase(self):
        """EvidenceManager.record_tdd_evidence() records VERIFY phase correctly."""
        import os

        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            manager = EvidenceManager(self.terminal_id)

            # Record VERIFY evidence with generic dict
            evidence = {"findings": 2, "blocking": 0, "verdict": "PASS"}
            manager.record_tdd_evidence("TASK-004", "VERIFY", evidence)

            # Verify evidence was recorded
            ledger = manager._load_ledger()
            task = ledger["tasks"]["TASK-004"]
            assert task["evidence"]["VERIFY"]["completed"]
            assert task["evidence"]["VERIFY"]["findings"] == 2
            assert task["evidence"]["VERIFY"]["verdict"] == "PASS"

        finally:
            os.chdir(original_cwd)

    def test_record_tdd_evidence_invalid_phase_raises_error(self):
        """EvidenceManager.record_tdd_evidence() raises ValueError for invalid phase."""
        import os

        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            manager = EvidenceManager(self.terminal_id)

            # Try to record invalid phase
            with pytest.raises(ValueError, match="Invalid phase"):
                manager.record_tdd_evidence("TASK-005", "INVALID_PHASE", {})

        finally:
            os.chdir(original_cwd)


class TestEvidenceWriterIntegration:
    """Test evidence_writer.py integration with EvidenceManager."""

    def setup_method(self):
        """Set up temporary environment for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.terminal_id = "test_writer_terminal"

        # Enable evidence tracking
        import os

        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"

    def teardown_method(self):
        """Clean up temporary environment after each test."""
        import os
        import shutil

        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

        os.environ.pop("TDD_EVIDENCE_TRACKING_ENABLED", None)

    def test_generate_evidence_artifact_uses_evidence_manager(self):
        """generate_evidence_artifact() uses EvidenceManager when available."""
        import os

        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            # Generate RED evidence artifact
            result = evidence_writer.generate_evidence_artifact(
                task_id="TASK-TEST",
                phase="RED",
                evidence={"test_files": ["test_example.py"], "failing_tests": 1},
                skill_dir=Path(self.temp_dir),
                terminal_id=self.terminal_id,
            )

            # Verify EvidenceManager was used (returned ledger file path)
            assert result is not None
            assert "code_evidence_" in str(result)
            assert result.name.startswith("code_evidence_")
            assert result.suffix == ".json"

            # Verify ledger contains the evidence
            ledger = json.loads(result.read_text())
            assert "TASK-TEST" in ledger["tasks"]
            assert ledger["tasks"]["TASK-TEST"]["evidence"]["RED"]["completed"]

        finally:
            os.chdir(original_cwd)

    def test_generate_evidence_artifact_fallback_to_markdown(self):
        """generate_evidence_artifact() falls back to markdown when EvidenceManager unavailable."""
        import os

        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            # Mock EvidenceManager as unavailable
            import lib.evidence_writer as writer_module

            original_available = writer_module.EVIDENCE_MANAGER_AVAILABLE
            writer_module.EVIDENCE_MANAGER_AVAILABLE = False

            # Generate evidence artifact (should use markdown fallback)
            result = evidence_writer.generate_evidence_artifact(
                task_id="TASK-FALLBACK",
                phase="GREEN",
                evidence={"impl_files": ["feature.py"], "passing_tests": 3},
                skill_dir=Path(self.temp_dir),
                terminal_id=None,  # No terminal_id forces markdown fallback
            )

            # Verify markdown file was created
            assert result is not None
            assert result.suffix == ".md"
            assert result.parent.name == ".evidence"

            # Verify markdown content
            content = result.read_text()
            assert "# GREEN Evidence - TASK-FALLBACK" in content
            assert "**Phase**: GREEN" in content

            # Restore original availability
            writer_module.EVIDENCE_MANAGER_AVAILABLE = original_available

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
