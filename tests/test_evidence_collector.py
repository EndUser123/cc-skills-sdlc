"""Tests for evidence_collector."""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "refactor"))

from scripts.evidence_collector import (
    PhaseEvidence,
    FindingEvidence,
    collect_test_evidence,
    verify_tdd_red,
    verify_tdd_green,
    get_evidence_collector,
)


class TestPhaseEvidence:
    """Tests for PhaseEvidence dataclass."""

    def test_phase_evidence_creation(self) -> None:
        ev = PhaseEvidence(
            finding_id="TEST-001",
            phase="RED",
            test_file="tests/test_x.py",
            test_passed=False,
            stdout="FAILED",
            stderr="",
            returncode=1,
            duration_seconds=0.5,
            timestamp="2026-04-22T10:00:00Z",
        )
        assert ev.finding_id == "TEST-001"
        assert ev.phase == "RED"
        assert ev.test_passed is False

    def test_finding_evidence_phases(self) -> None:
        ev1 = PhaseEvidence(
            finding_id="TEST-001",
            phase="RED",
            test_file="tests/test_x.py",
            test_passed=False,
            stdout="",
            stderr="",
            returncode=1,
            duration_seconds=0.1,
            timestamp="2026-04-22T10:00:00Z",
        )
        finding = FindingEvidence(
            finding_id="TEST-001",
            file="src/x.py",
            line=10,
            description="unused variable",
            phases=[ev1],
            rollback_commits=["abc123"],
            overall_pass=False,
        )
        assert len(finding.phases) == 1
        assert finding.phases[0].phase == "RED"
        assert finding.overall_pass is False


class TestGetEvidenceCollector:
    """Tests for get_evidence_collector (disk I/O)."""

    def test_missing_evidence_returns_none(self, tmp_path: Path) -> None:
        result = get_evidence_collector("NONEXISTENT", tmp_path)
        assert result is None

    def test_loads_stored_evidence(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        # Write consolidated format (single file per finding, multiple phases)
        evidence_file = state_dir / "evidence_TEST-001.json"
        evidence_file.write_text(
            json.dumps({
                "finding_id": "TEST-001",
                "file": "src/x.py",
                "line": 10,
                "description": "unused variable",
                "phases": [{
                    "finding_id": "TEST-001",
                    "phase": "RED",
                    "test_file": "tests/test_x.py",
                    "test_passed": False,
                    "stdout": "",
                    "stderr": "",
                    "returncode": 1,
                    "duration_seconds": 0.1,
                    "timestamp": "2026-04-22T10:00:00Z",
                }],
                "rollback_commits": [],
                "overall_pass": False,
            }),
            encoding="utf-8",
        )

        result = get_evidence_collector("TEST-001", tmp_path)
        assert result is not None
        assert result.finding_id == "TEST-001"
        assert result.phases[0].phase == "RED"
        assert result.phases[0].test_passed is False

    def test_corrupted_json_returns_none(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        evidence_file = state_dir / "evidence_BAD-001_RED.json"
        evidence_file.write_text("{ not valid json }", encoding="utf-8")

        result = get_evidence_collector("BAD-001", tmp_path)
        assert result is None
