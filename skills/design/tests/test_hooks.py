"""Tests for design enforcement hooks: verify_claims.py and stop_if_unverified.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Paths
SKILL_DIR = Path(__file__).resolve().parent.parent
HOOKS_DIR = SKILL_DIR / "hooks"
VERIFY_SCRIPT = HOOKS_DIR / "verify_claims.py"
STOP_SCRIPT = HOOKS_DIR / "stop_if_unverified.py"


def _run_verify(run_id: str, domain: str, claims: int = 0) -> tuple[int, str, str]:
    result = subprocess.run(
        ["python", str(VERIFY_SCRIPT), run_id, domain, str(claims)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _run_stop(stdin_data: str = '{"prompt":"test"}') -> tuple[int, str, str]:
    env = os.environ.copy()
    # DESIGN_RUN_ID no longer used — state is session-scoped

    result = subprocess.run(
        ["python", str(STOP_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _terminal_id() -> str:
    """Resolve terminal ID, falling back to WT_SESSION or 'default'."""
    tid = os.environ.get("CLAUDE_TERMINAL_ID", "").strip()
    if tid:
        return tid
    tid = os.environ.get("WT_SESSION", "").strip()
    if tid:
        return tid
    return "default"


def _state_dir() -> Path:
    """Resolve the design artifact directory for this terminal session."""
    skill_root = Path(__file__).resolve().parent.parent
    tid = _terminal_id()
    return skill_root / ".claude" / ".artifacts" / tid / "design"


def _state_file() -> Path:
    """Path to the session state file."""
    return _state_dir() / ".state.json"


def _write_unverified_state(run_id: str) -> None:
    """Write a state file with verified=False to test blocking."""
    state_dir = _state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = _state_file()
    record = {
        "run_id": run_id,
        "verified": False,
        "timestamp": time.time(),
    }
    state_file.write_text(json.dumps(record), encoding="utf-8")


def _cleanup():
    """Remove state file."""
    sf = _state_file()
    if sf.exists():
        sf.unlink()


class TestVerifyClaims:
    def test_creates_state_file(self):
        run_id = f"hook-test-{time.time_ns()}"
        try:
            exit_code, stdout, stderr = _run_verify(run_id, "browser_automation", 5)
            assert exit_code == 0, f"verify_claims.py failed: {stderr}"
            assert "VERIFIED" in stdout
            assert run_id in stdout
            assert "browser_automation" in stdout
        finally:
            _cleanup()

    def test_rejects_empty_run_id(self):
        exit_code, stdout, stderr = _run_verify("", "general")
        assert exit_code != 0
        assert "run_id is required" in stderr

    def test_rejects_invalid_domain(self):
        run_id = f"hook-invalid-{time.time_ns()}"
        try:
            exit_code, stdout, stderr = _run_verify(run_id, "invalid_domain")
            assert exit_code != 0
            assert "invalid domain" in stderr
        finally:
            _cleanup()

    def test_all_valid_domains_accepted(self):
        for domain in ("browser_automation", "performance", "api_integration", "general"):
            run_id = f"hook-domain-{domain}-{time.time_ns()}"
            try:
                exit_code, stdout, stderr = _run_verify(run_id, domain)
                assert exit_code == 0, f"Domain '{domain}' should be accepted: {stderr}"
            finally:
                _cleanup()

    def test_state_file_contains_verified_true(self):
        run_id = f"hook-json-{time.time_ns()}"
        try:
            _run_verify(run_id, "performance", 7)
            state_file = _state_file()
            assert state_file.exists(), f"State file not found at {state_file}"
            data = json.loads(state_file.read_text())
            assert data["run_id"] == run_id
            assert data["verification_domain"] == "performance"
            assert data["claims_verified"] == 7
            assert data["verified"] is True
        finally:
            _cleanup()


class TestStopIfUnverified:
    def test_blocks_unverified_state(self):
        """When state file exists but verified!=True, block."""
        run_id = f"hook-block-{time.time_ns()}"
        try:
            _write_unverified_state(run_id)
            _, stdout, _ = _run_stop()
            decision = json.loads(stdout)
            assert decision["decision"] == "block"
            assert "VERIFICATION REQUIRED" in decision["reason"]
        finally:
            _cleanup()

    def test_allows_verified_run_id(self):
        run_id = f"hook-allow-{time.time_ns()}"
        try:
            _run_verify(run_id, "general", 1)
            _, stdout, _ = _run_stop()
            decision = json.loads(stdout)
            assert decision["decision"] == "allow"
        finally:
            _cleanup()

    def test_allows_without_state_file(self):
        """No state file = not a design session = allow."""
        _cleanup()
        _, stdout, _ = _run_stop()
        decision = json.loads(stdout)
        assert decision["decision"] == "allow"

    def test_allows_with_empty_stdin(self):
        result = subprocess.run(
            ["python", str(STOP_SCRIPT)],
            input="",
            capture_output=True,
            text=True,
        )
        decision = json.loads(result.stdout)
        assert decision["decision"] == "allow"

    def test_allows_with_non_json_stdin(self):
        result = subprocess.run(
            ["python", str(STOP_SCRIPT)],
            input="not json at all",
            capture_output=True,
            text=True,
        )
        decision = json.loads(result.stdout)
        assert decision["decision"] == "allow"

    def test_cleans_up_state_after_allow(self):
        run_id = f"hook-cleanup-{time.time_ns()}"
        _run_verify(run_id, "general", 1)
        _run_stop()
        # State file should have been removed by the stop hook
        assert not _state_file().exists(), "State file should be cleaned up after allow"


class TestHookIntegration:
    def test_full_verify_then_stop_flow(self):
        """Verify claims, stop allows, state consumed, second stop allows (no state left)."""
        run_id = f"hook-full-{time.time_ns()}"
        try:
            # Step 1: Verify claims — writes verified state
            exit_code, stdout, stderr = _run_verify(run_id, "api_integration", 4)
            assert exit_code == 0

            # Step 2: Stop hook should allow (state file exists, verified=True)
            _, stdout, _ = _run_stop()
            decision = json.loads(stdout)
            assert decision["decision"] == "allow"

            # Step 3: Second stop should allow — state was consumed, no state left
            _, stdout_2, _ = _run_stop()
            decision_2 = json.loads(stdout_2)
            assert decision_2["decision"] == "allow"
            # No state file means "not a design session in progress" = allow
        finally:
            _cleanup()

    def test_verify_then_stop_blocks_without_verify(self):
        """State file written but consumed by stop, next call blocks if new state not written."""
        run_id = f"hook-no-verify-{time.time_ns()}"
        try:
            # Write a state without verified=True
            _write_unverified_state(run_id)

            # Stop should block
            _, stdout, _ = _run_stop()
            decision = json.loads(stdout)
            assert decision["decision"] == "block"
        finally:
            _cleanup()
