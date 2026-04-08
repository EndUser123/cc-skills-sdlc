#!/usr/bin/env python3
"""Tests for tdd_resume.py module."""

import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

# Store original env vars
_ORIG_TDD_STATE_DIR = os.environ.get("TDD_STATE_DIR")
_ORIG_TDD_EVIDENCE_DIR = os.environ.get("TDD_EVIDENCE_DIR")


class TestHelper:
    """Test helper for creating and managing temporary state files."""

    def __init__(self, tmp_dir: Path):
        self.tmp_dir = tmp_dir
        self.terminal_id = "test_terminal_123"
        self.session_id = "test_session_456"
        self.state_dir = tmp_dir / "state" / "tdd"
        self.evidence_dir = tmp_dir / "evidence" / "tdd95"

        # Set environment variables BEFORE importing module
        os.environ["CLAUDE_TERMINAL_ID"] = self.terminal_id
        os.environ["CLAUDE_SESSION_ID"] = self.session_id
        os.environ["TDD_STATE_DIR"] = str(self.state_dir)
        os.environ["TDD_EVIDENCE_DIR"] = str(self.evidence_dir)

        # Create directories
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        """Clean up temporary files."""
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        # Reset environment variables
        os.environ.pop("CLAUDE_TERMINAL_ID", None)
        os.environ.pop("CLAUDE_SESSION_ID", None)
        if _ORIG_TDD_STATE_DIR is not None:
            os.environ["TDD_STATE_DIR"] = _ORIG_TDD_STATE_DIR
        else:
            os.environ.pop("TDD_STATE_DIR", None)
        if _ORIG_TDD_EVIDENCE_DIR is not None:
            os.environ["TDD_EVIDENCE_DIR"] = _ORIG_TDD_EVIDENCE_DIR
        else:
            os.environ.pop("TDD_EVIDENCE_DIR", None)

    def _create_state_file(
        self,
        contract_id: str,
        phase: str,
        test_file: str | None = None,
        impl_files: list[str] | None = None,
        completed: bool = False,
    ):
        """Create a TDD state file for testing."""
        state_data = {
            "contract_id": contract_id,
            "phase": phase,
            "test_file": test_file,
            "impl_files": impl_files or [],
            "completed": completed,
        }
        terminal_dir = self.state_dir / self.terminal_id
        terminal_dir.mkdir(parents=True, exist_ok=True)
        state_file = terminal_dir / f"tdd.{contract_id}.json"
        with open(state_file, "w") as f:
            json.dump(state_data, f)
        return state_file

    def _create_evidence_file(self, contract_id: str, phase: str, evidence_hash: str):
        """Create an evidence file for testing."""
        evidence_data = {
            "contract_id": contract_id,
            "phase": phase,
            "evidence_hash": evidence_hash,
        }
        evidence_dir = self.evidence_dir / contract_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_file = evidence_dir / f"{phase}.json"
        with open(evidence_file, "w") as f:
            json.dump(evidence_data, f)
        return evidence_file


def _reload_tdd_resume():
    """Reload tdd_resume module to pick up new env vars."""
    # Add parent directory to path
    utils_dir = Path(__file__).parent
    if str(utils_dir) not in sys.path:
        sys.path.insert(0, str(utils_dir))

    # Remove cached module if exists
    if "tdd_resume" in sys.modules:
        del sys.modules["tdd_resume"]

    # Fresh import
    import tdd_resume

    importlib.reload(tdd_resume)
    return tdd_resume


class TestGetTerminalId(TestCase):
    """Tests for get_terminal_id function."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.helper = TestHelper(self.tmp_dir)
        self.tdd_resume = _reload_tdd_resume()

    def tearDown(self):
        self.helper.cleanup()

    def test_get_terminal_id(self):
        """Test get_terminal_id returns correct terminal ID from env."""
        assert self.tdd_resume.get_terminal_id() == "test_terminal_123"


class TestGetSessionId(TestCase):
    """Tests for get_session_id function."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.helper = TestHelper(self.tmp_dir)
        self.tdd_resume = _reload_tdd_resume()

    def tearDown(self):
        self.helper.cleanup()

    def test_get_session_id(self):
        """Test get_session_id returns correct session ID from env."""
        assert self.tdd_resume.get_session_id() == "test_session_456"


class TestFindActiveTDDContracts(TestCase):
    """Tests for find_active_tdd_contracts function."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.helper = TestHelper(self.tmp_dir)
        self.tdd_resume = _reload_tdd_resume()

    def tearDown(self):
        self.helper.cleanup()

    def test_empty(self):
        """Test finding active TDD contracts when terminal has no state files."""
        contracts = self.tdd_resume.find_active_tdd_contracts()
        assert contracts == []

    def test_idle_skipped(self):
        """Test that IDLE contracts are skipped."""
        # Create IDLE state file
        self.helper._create_state_file("idle_contract", "IDLE", completed=True)
        contracts = self.tdd_resume.find_active_tdd_contracts()
        assert contracts == []

    def test_single_active(self):
        """Test finding a single active TDD contract."""
        self.helper._create_state_file("active_1", "RED_CONFIRMED", "test_file.py")
        contracts = self.tdd_resume.find_active_tdd_contracts()
        assert len(contracts) == 1
        assert contracts[0]["contract_id"] == "active_1"
        assert contracts[0]["phase"] == "RED_CONFIRMED"
        assert contracts[0]["test_file"] == "test_file.py"

    def test_multiple_active(self):
        """Test finding multiple active TDD contracts."""
        # Create multiple active state files
        self.helper._create_state_file("contract_1", "AWAITING_RED", "test1.py")
        self.helper._create_state_file("contract_2", "GREEN_CONFIRMED", "test2.py")
        contracts = self.tdd_resume.find_active_tdd_contracts()
        assert len(contracts) == 2
        # Should be sorted by most recent first
        assert contracts[0]["phase"] in ("AWAITING_RED", "GREEN_CONFIRMED")


class TestFindPhase3Evidence(TestCase):
    """Tests for find_phase3_evidence function."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.helper = TestHelper(self.tmp_dir)
        self.tdd_resume = _reload_tdd_resume()

    def tearDown(self):
        self.helper.cleanup()

    def test_empty(self):
        """Test finding Phase 3 evidence when no evidence files exist."""
        evidence = self.tdd_resume.find_phase3_evidence()
        assert evidence == []

    def test_single_contract(self):
        """Test finding Phase 3 evidence for a single contract."""
        self.helper._create_evidence_file("test_contract", "RED", "abc123")
        evidence = self.tdd_resume.find_phase3_evidence()
        assert len(evidence) == 1
        assert evidence[0]["contract_id"] == "test_contract"
        assert evidence[0]["phase"] == "RED"
        assert evidence[0]["evidence_hash"] == "abc123"

    def test_specific_contract(self):
        """Test finding Phase 3 evidence for a specific contract."""
        self.helper._create_evidence_file("contract_1", "RED", "hash1")
        self.helper._create_evidence_file("contract_2", "GREEN", "hash2")
        # Find evidence for specific contract
        evidence = self.tdd_resume.find_phase3_evidence("contract_1")
        assert len(evidence) == 1
        assert evidence[0]["contract_id"] == "contract_1"


class TestGenerateTDDResumeContext(TestCase):
    """Tests for generate_tdd_resume_context function."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.helper = TestHelper(self.tmp_dir)
        self.tdd_resume = _reload_tdd_resume()

    def tearDown(self):
        self.helper.cleanup()

    def test_empty(self):
        """Test generating resume context when no active sessions."""
        context = self.tdd_resume.generate_tdd_resume_context()
        assert context is None

    def test_single(self):
        """Test generating resume context for a single active session."""
        self.helper._create_state_file(
            "test_contract",
            "GREEN_CONFIRMED",
            "test_file.py",
            impl_files=["impl.py"],
        )
        context = self.tdd_resume.generate_tdd_resume_context()
        assert context is not None
        assert "TDD Session Resume Context" in context
        assert "test_contract" in context
        assert "GREEN_CONFIRMED" in context
        assert "test_file.py" in context
        assert "impl.py" in context
        assert "Resume Instructions" in context

    def test_with_evidence(self):
        """Test generating resume context with evidence files."""
        self.helper._create_state_file("test_contract", "GREEN_CONFIRMED", "test_file.py")
        self.helper._create_evidence_file("test_contract", "GREEN", "abc123def456")
        context = self.tdd_resume.generate_tdd_resume_context()
        assert context is not None
        assert "Latest Evidence" in context
        assert "abc123def456" in context


class TestGetTDDStateForHandoff(TestCase):
    """Tests for get_tdd_state_for_handoff function."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.helper = TestHelper(self.tmp_dir)
        self.tdd_resume = _reload_tdd_resume()

    def tearDown(self):
        self.helper.cleanup()

    def test_empty(self):
        """Test getting TDD state for handoff when no active sessions."""
        state = self.tdd_resume.get_tdd_state_for_handoff()
        assert state["active_contracts"] == []
        assert state["evidence_count"] == 0

    def test_with_contracts(self):
        """Test getting TDD state for handoff with active contracts."""
        self.helper._create_state_file("contract_1", "RED_CONFIRMED", "test.py")
        state = self.tdd_resume.get_tdd_state_for_handoff()
        assert len(state["active_contracts"]) == 1
        assert state["active_contracts"][0]["contract_id"] == "contract_1"
        assert state["active_contracts"][0]["phase"] == "RED_CONFIRMED"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
