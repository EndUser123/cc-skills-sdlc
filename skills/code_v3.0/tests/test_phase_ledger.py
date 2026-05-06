#!/usr/bin/env python3
"""Tests for code_phase_ledger.py and Stop_code_phase_gate.py."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add hooks dir to path for direct import
_HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(_HOOKS_DIR))

from code_phase_ledger import (
    read_phase_ledger,
    write_phase_marker,
    reset_ledger,
)


class TestPhaseLedger:
    """Tests for code_phase_ledger.py."""

    def setup_method(self) -> None:
        os.environ["CLAUDE_TERMINAL_ID"] = "test-ledger-terminal"
        reset_ledger()

    def teardown_method(self) -> None:
        reset_ledger()

    def test_write_and_read(self) -> None:
        write_phase_marker("smoke_validation", {"pytest_exit": 0})
        ledger = read_phase_ledger()
        assert ledger is not None
        assert ledger["phases"]["smoke_validation"]["done"] is True
        assert ledger["phases"]["smoke_validation"]["pytest_exit"] == 0

    def test_append_only_no_clobber(self) -> None:
        write_phase_marker("audit_quality_checks", {"tool": "ruff", "tool_exit": 0})
        # Write again without payload — should be no-op since done:true
        write_phase_marker("audit_quality_checks", None)
        ledger = read_phase_ledger()
        assert ledger["phases"]["audit_quality_checks"]["tool"] == "ruff"

    def test_append_only_with_payload_overwrites(self) -> None:
        write_phase_marker("audit_quality_checks", {"tool": "ruff", "tool_exit": 0})
        # Write again WITH payload — should merge
        write_phase_marker("audit_quality_checks", {"tool": "mypy", "tool_exit": 1})
        ledger = read_phase_ledger()
        assert ledger["phases"]["audit_quality_checks"]["tool"] == "mypy"
        assert ledger["phases"]["audit_quality_checks"]["tool_exit"] == 1

    def test_multiple_phases_independent(self) -> None:
        write_phase_marker("smoke_validation", {"pytest_exit": 0})
        write_phase_marker("audit_quality_checks", {"tool": "ruff", "tool_exit": 0})
        write_phase_marker("consumer_contract_precheck", {"result": "pass"})
        ledger = read_phase_ledger()
        assert set(ledger["phases"].keys()) == {
            "smoke_validation",
            "audit_quality_checks",
            "consumer_contract_precheck",
        }

    def test_reset(self) -> None:
        write_phase_marker("smoke_validation", {"pytest_exit": 0})
        reset_ledger()
        assert read_phase_ledger() is None


class TestStopGateExitCodes:
    """Tests for Stop_code_phase_gate.py exit code semantics."""

    def _run_gate(self, phases: dict) -> tuple[int, str, str]:
        """Write ledger, run Stop gate, return (exit_code, stdout, stderr)."""
        import tempfile
        tid = "test-stop-gate"
        state_dir = Path.home() / ".claude" / ".state" / "code" / tid
        state_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = state_dir / "phase-ledger.json"
        ledger_path.write_text(
            json.dumps({"session_id": tid, "phases": phases}),
            encoding="utf-8",
        )
        env = {**os.environ, "CLAUDE_TERMINAL_ID": tid, "CLAUDE_CODE_FAST_MODE": ""}
        result = subprocess.run(
            [sys.executable, str(_HOOKS_DIR / "Stop_code_phase_gate.py")],
            capture_output=True,
            text=True,
            env=env,
        )
        # Clean up
        ledger_path.unlink(missing_ok=True)
        return result.returncode, result.stdout, result.stderr

    def test_no_ledger_allows_stop(self) -> None:
        os.environ["CLAUDE_TERMINAL_ID"] = "no-ledger-terminal"
        result = subprocess.run(
            [sys.executable, str(_HOOKS_DIR / "Stop_code_phase_gate.py")],
            capture_output=True,
            text=True,
            env={**os.environ},
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"

    def test_all_gates_pass_exit_0(self) -> None:
        phases = {
            "consumer_contract_precheck": {"done": True, "result": "pass"},
            "smoke_validation": {"done": True, "pytest_exit": 0},
            "full_test_suite": {"done": True, "tsr": 100.0},
            "audit_quality_checks": {"done": True, "tool_exit": 0},
        }
        exit_code, _, _ = self._run_gate(phases)
        assert exit_code == 0, f"Expected exit 0 (all passed), got {exit_code}"

    def test_missing_hard_gate_blocks_exit_2(self) -> None:
        # Only smoke — missing precheck, suite, audit
        phases = {
            "smoke_validation": {"done": True, "pytest_exit": 0},
        }
        exit_code, _, stderr = self._run_gate(phases)
        assert exit_code == 2, f"Expected exit 2 (blocked), got {exit_code}"
        assert "BLOCKED" in stderr
        assert "consumer_contract_precheck" in stderr

    def test_advisory_missing_does_not_block(self) -> None:
        # All hard gates pass, advisory missing
        phases = {
            "consumer_contract_precheck": {"done": True},
            "smoke_validation": {"done": True},
            "full_test_suite": {"done": True},
            "audit_quality_checks": {"done": True},
            # producer_consumer_trace_verification missing — advisory
        }
        exit_code, _, stderr = self._run_gate(phases)
        assert exit_code == 0, f"Expected exit 0 (advisory only), got {exit_code}"
        # Advisory warning should still appear
        assert "advisory" in stderr.lower()

    def test_fast_mode_skips_full_suite(self) -> None:
        # full_suite missing but fast mode set — should pass
        phases = {
            "consumer_contract_precheck": {"done": True},
            "smoke_validation": {"done": True},
            # full_test_suite missing
            "audit_quality_checks": {"done": True},
        }
        tid = "test-fast-mode"
        state_dir = Path.home() / ".claude" / ".state" / "code" / tid
        state_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = state_dir / "phase-ledger.json"
        ledger_path.write_text(
            json.dumps({"session_id": tid, "phases": phases}),
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": tid,
            "CLAUDE_CODE_FAST_MODE": "1",
        }
        result = subprocess.run(
            [sys.executable, str(_HOOKS_DIR / "Stop_code_phase_gate.py")],
            capture_output=True,
            text=True,
            env=env,
        )
        ledger_path.unlink(missing_ok=True)
        assert result.returncode == 0, f"Expected exit 0 in fast mode, got {result.returncode}"
