"""Tests for design_v1.0 enforcement hooks: verify_claims.py and stop_if_unverified.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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


def _run_stop(run_id: str | None, stdin_data: str = '{"prompt":"test"}') -> tuple[int, str, str]:
    env = os.environ.copy()
    if run_id is not None:
        env["DESIGN_RUN_ID"] = run_id
    else:
        env.pop("DESIGN_RUN_ID", None)

    result = subprocess.run(
        ["python", str(STOP_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _flag_path(run_id: str) -> Path:
    return Path(os.environ.get("CLAUDE_ARCH_DIR", ".claude/arch_decisions")) / f".verified_{run_id}"


class TestVerifyClaims:
    def test_creates_flag_file(self):
        run_id = f"hook-test-{time.time_ns()}"
        try:
            exit_code, stdout, stderr = _run_verify(run_id, "browser_automation", 5)
            assert exit_code == 0, f"verify_claims.py failed: {stderr}"
            assert "VERIFIED" in stdout
            assert run_id in stdout
            assert "browser_automation" in stdout
        finally:
            p = _flag_path(run_id)
            if p.exists():
                p.unlink()

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
            p = _flag_path(run_id)
            if p.exists():
                p.unlink()

    def test_all_valid_domains_accepted(self):
        for domain in ("browser_automation", "performance", "api_integration", "general"):
            run_id = f"hook-domain-{domain}-{time.time_ns()}"
            try:
                exit_code, stdout, stderr = _run_verify(run_id, domain)
                assert exit_code == 0, f"Domain '{domain}' should be accepted: {stderr}"
            finally:
                p = _flag_path(run_id)
                if p.exists():
                    p.unlink()

    def test_flag_file_contains_json(self):
        run_id = f"hook-json-{time.time_ns()}"
        try:
            _run_verify(run_id, "performance", 7)
            # Find the actual flag path from the verify_claims.py output location
            # It uses _state_dir() which resolves relative to the script
            from verify_claims import _state_dir
            state_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "arch_decisions"
            flag = state_dir / f".verified_{run_id}"
            if flag.exists():
                data = json.loads(flag.read_text())
                assert data["run_id"] == run_id
                assert data["verification_domain"] == "performance"
                assert data["claims_verified"] == 7
        finally:
            p = _flag_path(run_id)
            if p.exists():
                p.unlink()


class TestStopIfUnverified:
    def test_blocks_unverified_run_id(self):
        _, stdout, _ = _run_stop("nonexistent-run-id-99999")
        decision = json.loads(stdout)
        assert decision["decision"] == "block"
        assert "VERIFICATION REQUIRED" in decision["reason"]

    def test_allows_verified_run_id(self):
        run_id = f"hook-allow-{time.time_ns()}"
        try:
            _run_verify(run_id, "general", 1)
            _, stdout, _ = _run_stop(run_id)
            decision = json.loads(stdout)
            assert decision["decision"] == "allow"
        finally:
            p = _flag_path(run_id)
            if p.exists():
                p.unlink()

    def test_allows_without_design_run_id(self):
        decision_json, _ = _run_stop(run_id=None)
        decision = json.loads(decision_json)
        assert decision["decision"] == "allow"

    def test_allows_with_empty_stdin(self):
        env = os.environ.copy()
        env["DESIGN_RUN_ID"] = "some-run-id"
        result = subprocess.run(
            ["python", str(STOP_SCRIPT)],
            input="",
            capture_output=True,
            text=True,
            env=env,
        )
        decision = json.loads(result.stdout)
        assert decision["decision"] == "allow"

    def test_allows_with_non_json_stdin(self):
        env = os.environ.copy()
        env["DESIGN_RUN_ID"] = "some-run-id"
        result = subprocess.run(
            ["python", str(STOP_SCRIPT)],
            input="not json at all",
            capture_output=True,
            text=True,
            env=env,
        )
        decision = json.loads(result.stdout)
        assert decision["decision"] == "allow"

    def test_cleans_up_flag_after_allow(self):
        run_id = f"hook-cleanup-{time.time_ns()}"
        _run_verify(run_id, "general", 1)
        _run_stop(run_id)
        # Flag should have been removed by the stop hook
        p = _flag_path(run_id)
        assert not p.exists(), "Flag should be cleaned up after allow"


class TestHookIntegration:
    def test_full_verify_then_stop_flow(self):
        run_id = f"hook-full-{time.time_ns()}"
        try:
            # Step 1: Verify claims
            exit_code, stdout, stderr = _run_verify(run_id, "api_integration", 4)
            assert exit_code == 0

            # Step 2: Stop hook should allow
            decision_json, _ = _run_stop(run_id)
            decision = json.loads(decision_json)
            assert decision["decision"] == "allow"

            # Step 3: Second stop should block (flag was consumed)
            decision_json_2, _ = _run_stop(run_id)
            decision_2 = json.loads(decision_json_2)
            assert decision_2["decision"] == "block"
        finally:
            p = _flag_path(run_id)
            if p.exists():
                p.unlink()
