"""Tests for orchestrator utility functions."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from findings.models import EvidenceTier, Finding, Layer, Severity, SQAReport
from orchestrator import (
    L2State,
    _atomic_write,
    _get_terminal_state_dir,
    _validate_target,
    save_report,
)


class TestValidateTarget:
    """Tests for _validate_target()."""

    def test_validate_target_accepts_sqa_skill_directory(self):
        """_validate_target accepts an existing directory within workspace."""
        # Use the SQA skill dir itself (always within allowed roots)
        sqa_dir = Path(__file__).parent.parent
        result = _validate_target(str(sqa_dir))
        assert result == sqa_dir.resolve()

    def test_validate_target_rejects_nonexistent_path(self):
        """_validate_target raises AssertionError for nonexistent path."""
        import pytest
        # Use a path that cannot exist on Windows (reserved device names)
        with pytest.raises(AssertionError, match="does not exist"):
            _validate_target("NUL:$")

    def test_validate_target_rejects_symlink(self, tmp_path: Path):
        """_validate_target raises AssertionError for symlink outside allowed roots."""
        import pytest
        link_path = tmp_path / "link"
        link_path.symlink_to(tmp_path)
        with pytest.raises(AssertionError, match="outside allowed roots"):
            _validate_target(str(link_path))


class TestAtomicWrite:
    """Tests for _atomic_write()."""

    def test_atomic_write_creates_file(self, tmp_path: Path):
        """_atomic_write creates the file."""
        p = tmp_path / "test.txt"
        _atomic_write(p, "hello world")
        assert p.exists()
        assert p.read_text() == "hello world"

    def test_atomic_write_overwrites(self, tmp_path: Path):
        """_atomic_write overwrites existing content."""
        p = tmp_path / "test.txt"
        _atomic_write(p, "first")
        _atomic_write(p, "second")
        assert p.read_text() == "second"


class TestGetTerminalStateDir:
    """Tests for _get_terminal_state_dir()."""

    def test_returns_path_object(self):
        """_get_terminal_state_dir returns a Path."""
        result = _get_terminal_state_dir()
        assert isinstance(result, Path)

    def test_path_contains_terminal_id(self, monkeypatch):
        """Path includes sanitized terminal ID."""
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test-term-123")
        result = _get_terminal_state_dir()
        assert "test-term-123" in str(result)


class TestL2State:
    """Tests for L2State dataclass."""

    def test_l2_state_fields(self):
        """L2State stores layer2 state correctly."""
        state = L2State(layer2_had_failures=True, target="/test/path")
        assert state.layer2_had_failures is True
        assert state.target == "/test/path"


class TestSaveReport:
    """Tests for save_report()."""

    def test_save_report_writes_json(self, monkeypatch, tmp_path: Path):
        """save_report writes a JSON file to terminal-isolated path."""
        import hashlib
        import shutil

        monkeypatch.setenv("TERMINAL_ID", "test_orch_terminal")
        findings = [
            Finding(
                finding_id="TEST-001",
                severity=Severity.MEDIUM,
                layer=Layer.L4_REQUIREMENTS,
                title="Test finding",
                description="Testing save_report",
                evidence_tier=EvidenceTier.T3,
                category="quality",
            )
        ]
        report = SQAReport(findings=findings, target=str(tmp_path))
        report.health_score = 95
        report.timestamp = "2026-04-04T12:00:00+00:00"

        save_report(report, tmp_path / "ignored.json")

        tid = "test_orch_terminal"
        target_hash = hashlib.sha256(report.target.encode()).hexdigest()[:16]
        report_dir = Path.home() / ".claude" / "sqa_reports" / f"terminal_{tid}"
        terminal_path = report_dir / f"{target_hash}.json"

        try:
            assert terminal_path.exists()
            import json
            data = json.loads(terminal_path.read_text())
            assert data["target"] == str(tmp_path)
            assert data["health_score"] == 95
            assert len(data["findings"]) == 1
        finally:
            shutil.rmtree(report_dir, ignore_errors=True)
