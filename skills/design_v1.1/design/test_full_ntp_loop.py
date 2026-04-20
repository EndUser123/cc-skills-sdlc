"""Full NTP v1.1 tool-gated loop integration test.

Exercises the complete chain:
  1. Create a valid design_draft_<RUNID>.json
  2. Run validate_design.py against it
  3. Verify .verified_<RUNID> flag is created
  4. Call stop_if_unverified.py hook input simulation
  5. Verify the hook outputs "allow" decision
  6. Verify ADR was saved to docs/architecture/
"""
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
DESIGN_DIR = Path(__file__).parent
SKILL_DIR = DESIGN_DIR.parent.parent
PACKAGE_ROOT = SKILL_DIR.parent.parent
HOOK_STOP = SKILL_DIR / "design_v1.1" / "hooks" / "stop_if_unverified.py"
VALIDATE_SCRIPT = DESIGN_DIR / "validate_design.py"
DOCS_ARCH = PACKAGE_ROOT / "cc-skills-sdlc" / "docs" / "architecture"


def _minimal_valid_payload(run_id: str) -> dict:
    cap = {
        "identity_model": "session_id",
        "ordering_strategy": "append",
        "dedupe_mechanism": "none",
        "freshness_authority": "producer",
        "event_source_of_truth": "transcript",
        "decision_closure_status": "open",
        "boundaries": [],
    }
    return {
        "run_id": run_id,
        "mode": "system",
        "scope": "all",
        "user_query": "integration test for full NTP loop",
        "ast_summary": "workspace: integration_test/ (fake)",
        "sop": "1. Draft\n2. Validate\n3. Verify",
        "template_name": "system_precedent_deep",
        "cap": cap,
        "critic_findings": [
            {
                "severity": "low",
                "category": "test",
                "description": "Integration test finding",
                "location": "test_full_ntp_loop.py",
                "suggestion": "none",
                "verified": False,
            }
        ],
        "adr_markdown": """# ADR-Integration-Test

## Status
Accepted

## Context
Integration test for NTP v1.1 full loop validation.
This ADR exists solely for smoke-testing the auto-save mechanism.

## Decision
Use the full tool-gated loop end-to-end.

## Consequences
None — this is a test fixture.
""",
    }


def _run_validate(draft_path: str, mode: str, run_id: str) -> tuple[int, str, str]:
    """Run validate_design.py. Returns (exit_code, stdout, stderr)."""
    result = subprocess.run(
        ["python", str(VALIDATE_SCRIPT), draft_path, mode, run_id],
        capture_output=True,
        text=True,
        cwd=str(DESIGN_DIR),
    )
    return result.returncode, result.stdout, result.stderr


def _call_stop_hook(run_id: str) -> dict | None:
    """Simulate stop_if_unverified.py hook call. Returns parsed JSON decision."""
    import subprocess

    env = os.environ.copy()
    env["DESIGN_RUN_ID"] = run_id

    result = subprocess.run(
        ["python", str(HOOK_STOP)],
        input=json.dumps({"prompt": "test"}),
        capture_output=True,
        text=True,
        env=env,
    )
    if not result.stdout and result.stderr:
        # Hook crashed — surface the traceback
        print(f"HOOK CRASH stderr: {result.stderr}", file=sys.stderr)
    if not result.stdout:
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        print(f"HOOK PARSE ERROR: stdout={result.stdout!r} stderr={result.stderr!r}", file=sys.stderr)
        return None


class TestFullNTPLoop:
    """Integration tests for the complete NTP v1.1 tool-gated loop."""

    def test_full_loop_succeeds(self):
        """Valid draft → validate → flag created → stop hook allows."""
        run_id = f"ntp-integration-{time.time_ns()}"
        payload = _minimal_valid_payload(run_id)

        # Clean up any stale state
        flag_file = DESIGN_DIR / f".verified_{run_id}"
        attempt_file = DESIGN_DIR / f".attempt_{run_id}"
        for f in [flag_file, attempt_file]:
            if f.exists():
                f.unlink()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(payload, fh)
            draft_path = fh.name

        try:
            # Step 1-2: Validation should succeed
            exit_code, stdout, stderr = _run_validate(draft_path, "system", run_id)
            assert exit_code == 0, f"validate_design.py failed:\nstdout={stdout}\nstderr={stderr}"
            assert "SUCCESS" in stdout, f"Expected SUCCESS in output:\n{stdout}"

            # Step 3: Flag should exist
            assert flag_file.exists(), f"Flag file not created: {flag_file}"

            # Step 4: Stop hook should allow
            decision = _call_stop_hook(run_id)
            assert decision is not None, "stop_if_unverified.py returned non-JSON"
            assert decision.get("decision") == "allow", (
                f"stop hook blocked valid design: {decision.get('reason', 'unknown')}"
            )

            # Step 5: ADR should be saved
            adr_files = list(DOCS_ARCH.glob(f"ADR-SYSTEM-*.md"))
            assert len(adr_files) > 0, f"No ADR files found in {DOCS_ARCH}"

            # Verify ADR content is non-trivial
            latest_adr = max(adr_files, key=lambda p: p.stat().st_mtime)
            content = latest_adr.read_text(encoding="utf-8")
            assert len(content) > 100, "ADR appears truncated"
            assert "ADR-Integration-Test" in content

        finally:
            # Cleanup
            for f in [flag_file, attempt_file]:
                if f.exists():
                    f.unlink()
            os.unlink(draft_path)

    def test_stop_hook_blocks_unknown_run_id(self):
        """Stop hook blocks when .verified_<RUNID> does not exist."""
        decision = _call_stop_hook("nonexistent-run-id-12345")
        assert decision is not None
        assert decision.get("decision") == "block", (
            f"stop hook should block unknown RUN ID, got: {decision}"
        )

    def test_stop_hook_allows_without_design_run_id(self):
        """Stop hook allows when DESIGN_RUN_ID is not set (e.g. non-design session)."""
        import subprocess

        result = subprocess.run(
            ["python", str(HOOK_STOP)],
            input=json.dumps({"prompt": "hello, how are you?"}),
            capture_output=True,
            text=True,
        )
        decision = json.loads(result.stdout)
        assert decision.get("decision") == "allow"

    def test_validate_fails_with_invalid_payload(self):
        """Invalid draft → validation fails → no flag created."""
        run_id = f"ntp-invalid-{time.time_ns()}"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump({"run_id": run_id, "mode": "invalid"}, fh)
            draft_path = fh.name

        try:
            exit_code, stdout, stderr = _run_validate(draft_path, "system", run_id)
            assert exit_code != 0, "validate_design.py should have failed"
            assert "ERROR" in stderr

            flag_file = DESIGN_DIR / f".verified_{run_id}"
            assert not flag_file.exists(), "Flag should NOT exist for invalid draft"
        finally:
            os.unlink(draft_path)

    def test_validate_respects_attempt_limit(self):
        """Fourth failed attempt → blocked by attempt limit."""
        run_id = f"ntp-attempt-limit-{time.time_ns()}"

        # Use a payload that fails validation each time (empty ast_summary)
        bad_payload = _minimal_valid_payload(run_id)
        bad_payload["ast_summary"] = ""  # Will fail _validate_logic

        flag_file = DESIGN_DIR / f".verified_{run_id}"
        attempt_file = DESIGN_DIR / f".attempt_{run_id}"
        for f in [flag_file, attempt_file]:
            if f.exists():
                f.unlink()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(bad_payload, fh)
            draft_path = fh.name

        try:
            # First 3 attempts fail validation (ast_summary="") → counter increments
            for i in range(3):
                exit_code, stdout, stderr = _run_validate(draft_path, "system", run_id)
                assert exit_code != 0, f"Attempt {i+1} should have failed"
                assert "ast_summary" in stderr or "ERROR" in stderr

            # 4th attempt → blocked by attempt limit
            exit_code_4, stdout_4, stderr_4 = _run_validate(draft_path, "system", run_id)
            assert exit_code_4 != 0, "4th attempt should be blocked"
            assert "Maximum 3 attempts" in stderr_4 or "attempt" in stderr_4.lower()
        finally:
            for f in [flag_file, attempt_file]:
                if f.exists():
                    f.unlink()
            os.unlink(draft_path)

    def test_cross_cwd_flag_detection(self, monkeypatch, tmp_path):
        """Stop hook finds flag even when called from a different working directory."""
        run_id = f"ntp-cross-cwd-{time.time_ns()}"
        payload = _minimal_valid_payload(run_id)

        flag_file = DESIGN_DIR / f".verified_{run_id}"
        attempt_file = DESIGN_DIR / f".attempt_{run_id}"
        for f in [flag_file, attempt_file]:
            if f.exists():
                f.unlink()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(payload, fh)
            draft_path = fh.name

        try:
            # Validate from DESIGN_DIR (normal cwd)
            exit_code, stdout, stderr = _run_validate(draft_path, "system", run_id)
            assert exit_code == 0, f"validate failed:\n{stderr}"
            assert flag_file.exists(), "Flag not created"

            # Now simulate calling the stop hook from a DIFFERENT cwd
            # (the actual production scenario: hook runs in repo root, not in design/)
            import subprocess

            env = os.environ.copy()
            env["DESIGN_RUN_ID"] = run_id

            # Call stop hook from a completely different directory
            result = subprocess.run(
                ["python", str(HOOK_STOP)],
                input=json.dumps({"prompt": "design question"}),
                capture_output=True,
                text=True,
                env=env,
                cwd=str(tmp_path),  # Different cwd!
            )
            decision = json.loads(result.stdout)
            assert decision.get("decision") == "allow", (
                f"Cross-cwd stop hook blocked valid RUN ID: {decision}"
            )
        finally:
            for f in [flag_file, attempt_file]:
                if f.exists():
                    f.unlink()
            os.unlink(draft_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
