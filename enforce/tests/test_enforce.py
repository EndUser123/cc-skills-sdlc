#!/usr/bin/env python3
"""Tests for enforce/ (shared phase ledger + stop gate)."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Add cc-skills-sdlc root so 'enforce' is a proper package
_enforce_pkg = Path(__file__).resolve().parents[1]  # enforce/
_sdlc_root = _enforce_pkg.parent  # cc-skills-sdlc/
if str(_sdlc_root) not in sys.path:
    sys.path.insert(0, str(_sdlc_root))

from enforce.phase_ledger import (
    write_phase_marker,
    read_phase_ledger,
    reset_phase_ledger,
)
from enforce.stop_gate import evaluate_gates, load_config_for_skill
from enforce.configs import ENFORCE_CONFIGS


# ---------------------------------------------------------------------------
# Phase ledger tests
# ---------------------------------------------------------------------------

class TestPhaseLedgerEnforce:
    """Test the shared phase_ledger.py under enforce/."""

    def setup_method(self) -> None:
        os.environ["CLAUDE_TERMINAL_ID"] = "test-enforce-terminal"
        reset_phase_ledger("code_v4.0")
        reset_phase_ledger("go_v3.0")

    def teardown_method(self) -> None:
        reset_phase_ledger("code_v4.0")
        reset_phase_ledger("go_v3.0")

    def test_write_and_read(self) -> None:
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        ledger = read_phase_ledger("code_v4.0")
        assert ledger is not None
        assert ledger["phases"]["consumer_contract_precheck"]["done"] is True
        assert ledger["phases"]["consumer_contract_precheck"]["result"] == "pass"

    def test_append_only_no_clobber(self) -> None:
        write_phase_marker("code_v4.0", "smoke_validation", {"pytest_exit": 0})
        write_phase_marker("code_v4.0", "smoke_validation", None)  # no payload
        ledger = read_phase_ledger("code_v4.0")
        assert ledger["phases"]["smoke_validation"]["pytest_exit"] == 0

    def test_append_only_with_payload_overwrites(self) -> None:
        write_phase_marker("code_v4.0", "audit_quality_checks", {"tool": "ruff", "tool_exit": 0})
        write_phase_marker("code_v4.0", "audit_quality_checks", {"tool": "mypy", "tool_exit": 1})
        ledger = read_phase_ledger("code_v4.0")
        assert ledger["phases"]["audit_quality_checks"]["tool"] == "mypy"
        assert ledger["phases"]["audit_quality_checks"]["tool_exit"] == 1

    def test_multiple_phases_independent(self) -> None:
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        write_phase_marker("code_v4.0", "smoke_validation", {"pytest_exit": 0})
        write_phase_marker("go_v3.0", "worktree_ready", None)
        ledger_code = read_phase_ledger("code_v4.0")
        ledger_go = read_phase_ledger("go_v3.0")
        assert set(ledger_code["phases"].keys()) == {"consumer_contract_precheck", "smoke_validation"}
        assert set(ledger_go["phases"].keys()) == {"worktree_ready"}

    def test_reset(self) -> None:
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        reset_phase_ledger("code_v4.0")
        assert read_phase_ledger("code_v4.0") is None


# ---------------------------------------------------------------------------
# Stop gate evaluation tests
# ---------------------------------------------------------------------------

class TestStopGateEnforce:
    """Test evaluate_gates() with code_v4.0 and go_v3.0 configs."""

    def setup_method(self) -> None:
        os.environ["CLAUDE_TERMINAL_ID"] = "test-enforce-terminal"
        reset_phase_ledger("code_v4.0")
        reset_phase_ledger("go_v3.0")

    def teardown_method(self) -> None:
        reset_phase_ledger("code_v4.0")
        reset_phase_ledger("go_v3.0")
        # Clean up go flag files
        state_dir = Path.home() / ".claude" / ".artifacts" / "test-enforce-terminal" / "go"
        if state_dir.is_dir():
            import shutil
            shutil.rmtree(state_dir)

    # --- code_v4.0 tests ---

    def test_code_no_ledger_clean(self) -> None:
        """No ledger at all = cold start = exit 0."""
        code_config = load_config_for_skill("code_v4.0")
        exit_code, msg = evaluate_gates("code_v4.0", code_config, os.environ)
        assert exit_code == 0

    def test_code_all_hard_gates_exit_0(self) -> None:
        """All hard gates in ledger = clean exit 0."""
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        write_phase_marker("code_v4.0", "smoke_validation", {"pytest_exit": 0})
        write_phase_marker("code_v4.0", "full_test_suite", {"pytest_exit": 0})
        write_phase_marker("code_v4.0", "audit_quality_checks", {"tool_exit": 0})
        code_config = load_config_for_skill("code_v4.0")
        exit_code, msg = evaluate_gates("code_v4.0", code_config, os.environ)
        assert exit_code == 0

    def test_code_missing_hard_gate_exit_2(self) -> None:
        """Missing hard gate = blocking exit 2."""
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        # smoke_validation missing
        write_phase_marker("code_v4.0", "full_test_suite", {"pytest_exit": 0})
        write_phase_marker("code_v4.0", "audit_quality_checks", {"tool_exit": 0})
        code_config = load_config_for_skill("code_v4.0")
        exit_code, msg = evaluate_gates("code_v4.0", code_config, os.environ)
        assert exit_code == 2
        assert "BLOCKED" in msg
        assert "smoke_validation" in msg

    # Note: advisory phases with ledger_only evidence are placeholder checks
    # and are always treated as satisfied. test_code_missing_advisory_only_exit_1
    # was removed because advisory placeholders don't generate warnings.

    def test_code_fast_mode_skips_full_suite(self) -> None:
        """CLAUDE_CODE_FAST_MODE=1 skips full_test_suite requirement."""
        env = {**os.environ, "CLAUDE_CODE_FAST_MODE": "1"}
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        write_phase_marker("code_v4.0", "smoke_validation", {"pytest_exit": 0})
        # full_test_suite NOT written (skipped in fast mode)
        write_phase_marker("code_v4.0", "audit_quality_checks", {"tool_exit": 0})
        code_config = load_config_for_skill("code_v4.0")
        exit_code, msg = evaluate_gates("code_v4.0", code_config, env)
        assert exit_code == 0

    # --- go_v3.0 tests (file-flag evidence) ---

    def test_go_all_flag_files_exit_0(self) -> None:
        """All Gen 2 flag files present = clean exit 0."""
        state_dir = Path.home() / ".claude" / ".artifacts" / "test-enforce-terminal" / "go"
        state_dir.mkdir(parents=True, exist_ok=True)
        run_id = "TEST123"

        for flag in [".worktree-ready", ".task-selected", ".coded", ".verified",
                      ".simplified", ".reviews-passed", ".qa-passed", ".pr-ready"]:
            (state_dir / f"{flag}_{run_id}").touch()
        (state_dir / "pr-body_TEST123.md").touch()
        (state_dir / "pr-title_TEST123.txt").touch()

        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-enforce-terminal",
            "RUN_ID": run_id,
        }
        go_config = load_config_for_skill("go_v3.0")
        exit_code, msg = evaluate_gates("go_v3.0", go_config, env)
        assert exit_code == 0

    def test_go_missing_hard_flag_exit_2(self) -> None:
        """Missing hard flag file = blocking exit 2."""
        state_dir = Path.home() / ".claude" / ".artifacts" / "test-enforce-terminal" / "go"
        state_dir.mkdir(parents=True, exist_ok=True)
        run_id = "TEST456"

        # Only some flags present
        (state_dir / f".worktree-ready_{run_id}").touch()
        (state_dir / f".task-selected_{run_id}").touch()
        # .coded_ missing
        (state_dir / f".verified_{run_id}").touch()

        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-enforce-terminal",
            "RUN_ID": run_id,
        }
        go_config = load_config_for_skill("go_v3.0")
        exit_code, msg = evaluate_gates("go_v3.0", go_config, env)
        assert exit_code == 2
        assert "BLOCKED" in msg
        assert "code_completed" in msg

    def test_go_without_run_id_is_cold_start_exit_0(self) -> None:
        """No run id means /go has not initialized a run, so Stop must not block."""
        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-enforce-terminal",
        }
        env.pop("RUN_ID", None)
        env.pop("CLAUDE_GO_RUN_ID", None)

        go_config = load_config_for_skill("go_v3.0")
        exit_code, msg = evaluate_gates("go_v3.0", go_config, env)

        assert exit_code == 0
        assert msg == ""

    def test_go_advisory_missing_exit_0(self) -> None:
        """All hard flags present, advisory phases are placeholders = exit 0."""
        state_dir = Path.home() / ".claude" / ".artifacts" / "test-enforce-terminal" / "go"
        state_dir.mkdir(parents=True, exist_ok=True)
        run_id = "TEST789"

        for flag in [".worktree-ready", ".task-selected", ".coded", ".verified",
                      ".simplified", ".reviews-passed", ".qa-passed", ".pr-ready"]:
            (state_dir / f"{flag}_{run_id}").touch()

        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-enforce-terminal",
            "RUN_ID": run_id,
        }
        go_config = load_config_for_skill("go_v3.0")
        exit_code, msg = evaluate_gates("go_v3.0", go_config, env)
        assert exit_code == 0
        assert msg == ""


# ---------------------------------------------------------------------------
# Stop hook script tests (actual subprocess run)
# ---------------------------------------------------------------------------

class TestStopHookScriptsEnforce:
    """Test the actual Stop hook scripts via subprocess."""

    def setup_method(self) -> None:
        os.environ["CLAUDE_TERMINAL_ID"] = "test-hook-terminal"
        reset_phase_ledger("code_v4.0")
        reset_phase_ledger("go_v3.0")

    def teardown_method(self) -> None:
        reset_phase_ledger("code_v4.0")
        reset_phase_ledger("go_v3.0")
        # Clean up go flag files
        state_dir = Path.home() / ".claude" / ".artifacts" / "test-hook-terminal" / "go"
        if state_dir.is_dir():
            import shutil
            shutil.rmtree(state_dir)

    def _run_stop_hook(self, script_path: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        env = {**os.environ, "CLAUDE_TERMINAL_ID": "test-hook-terminal"}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, env=env,
        )

    def test_code_v4_stop_no_ledger_exit_0(self) -> None:
        script = _sdlc_root / "skills" / "code_v4.0" / "hooks" / "Stop_enforce_gate.py"
        if not script.exists():
            pytest.skip("Stop hook script not found")
        r = self._run_stop_hook(script)
        assert r.returncode == 0, f"Expected exit 0, got {r.returncode}: {r.stderr}"

    def test_code_v4_stop_all_gates_exit_0(self) -> None:
        script = _sdlc_root / "skills" / "code_v4.0" / "hooks" / "Stop_enforce_gate.py"
        if not script.exists():
            pytest.skip("Stop hook script not found")
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        write_phase_marker("code_v4.0", "smoke_validation", {"pytest_exit": 0})
        write_phase_marker("code_v4.0", "full_test_suite", {"pytest_exit": 0})
        write_phase_marker("code_v4.0", "audit_quality_checks", {"tool_exit": 0})
        r = self._run_stop_hook(script)
        assert r.returncode == 0, f"Expected exit 0, got {r.returncode}: {r.stderr}"

    def test_code_v4_stop_missing_hard_exit_2(self) -> None:
        script = _sdlc_root / "skills" / "code_v4.0" / "hooks" / "Stop_enforce_gate.py"
        if not script.exists():
            pytest.skip("Stop hook script not found")
        write_phase_marker("code_v4.0", "consumer_contract_precheck", {"result": "pass"})
        # others missing
        r = self._run_stop_hook(script)
        assert r.returncode == 2, f"Expected exit 2, got {r.returncode}: {r.stderr}"
        assert "BLOCKED" in r.stderr

    def test_go_v3_stop_no_flags_exit_2(self) -> None:
        """go_v3 Stop hook when no Gen 2 flag files exist → exit 2."""
        script = _sdlc_root / "skills" / "go" / "hooks" / "Stop_enforce_gate.py"
        if not script.exists():
            pytest.skip("Stop hook script not found")
        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-hook-terminal",
            "RUN_ID": "R999",
        }
        r = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, env=env,
        )
        assert r.returncode == 2, f"Expected exit 2, got {r.returncode}: {r.stderr}"
        assert "BLOCKED" in r.stderr

    def test_go_v3_stop_no_run_id_exit_0(self) -> None:
        """go_v3 Stop hook cold-starts cleanly when no /go run id exists."""
        script = _sdlc_root / "skills" / "go" / "hooks" / "Stop_enforce_gate.py"
        if not script.exists():
            pytest.skip("Stop hook script not found")
        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-hook-terminal",
        }
        env.pop("RUN_ID", None)
        env.pop("CLAUDE_GO_RUN_ID", None)

        r = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, env=env,
        )

        assert r.returncode == 0, f"Expected exit 0, got {r.returncode}: {r.stderr}"
        assert r.stderr == ""

    def test_go_v3_stop_all_flags_exit_0(self) -> None:
        """go_v3 Stop hook when all Gen 2 flag files exist → exit 0."""
        script = _sdlc_root / "skills" / "go" / "hooks" / "Stop_enforce_gate.py"
        if not script.exists():
            pytest.skip("Stop hook script not found")
        state_dir = Path.home() / ".claude" / ".artifacts" / "test-hook-terminal" / "go"
        state_dir.mkdir(parents=True, exist_ok=True)
        run_id = "R999"
        for flag in [".worktree-ready", ".task-selected", ".coded", ".verified",
                     ".simplified", ".reviews-passed", ".qa-passed", ".pr-ready"]:
            (state_dir / f"{flag}_{run_id}").touch()
        (state_dir / "pr-body_R999.md").touch()

        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-hook-terminal",
            "RUN_ID": run_id,
        }
        r = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, env=env,
        )
        assert r.returncode == 0, f"Expected exit 0, got {r.returncode}: {r.stderr}"

    def test_go_v3_stop_missing_advisory_exit_0(self) -> None:
        """go_v3 Stop hook: advisory placeholders treated as satisfied → exit 0."""
        script = _sdlc_root / "skills" / "go" / "hooks" / "Stop_enforce_gate.py"
        if not script.exists():
            pytest.skip("Stop hook script not found")
        state_dir = Path.home() / ".claude" / ".artifacts" / "test-hook-terminal" / "go"
        state_dir.mkdir(parents=True, exist_ok=True)
        run_id = "R888"
        for flag in [".worktree-ready", ".task-selected", ".coded", ".verified",
                     ".simplified", ".reviews-passed", ".qa-passed", ".pr-ready"]:
            (state_dir / f"{flag}_{run_id}").touch()
        (state_dir / "pr-body_R888.md").touch()

        env = {
            **os.environ,
            "CLAUDE_TERMINAL_ID": "test-hook-terminal",
            "RUN_ID": run_id,
        }
        r = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, env=env,
        )
        assert r.returncode == 0, f"Expected exit 0, got {r.returncode}: {r.stderr}"


# ---------------------------------------------------------------------------
# Config registry tests
# ---------------------------------------------------------------------------

class TestEnforceConfigs:
    """Verify configs for code-ef and go meet the always-advisory rule."""

    def test_no_prose_only_hard_gates(self) -> None:
        """No hard gate may lack a concrete evidence field."""
        for skill_id, config in ENFORCE_CONFIGS.items():
            for phase in config:
                if phase["gate_type"] == "hard":
                    evidence = phase.get("evidence")
                    assert evidence is not None, f"{skill_id}:{phase['name']} hard gate has no evidence field"
                    # evidence must be non-empty dict or list
                    if isinstance(evidence, dict):
                        assert "type" in evidence, f"{skill_id}:{phase['name']} hard gate evidence has no 'type'"

    def test_code_ef_hard_gates_ledger_only(self) -> None:
        code_config = ENFORCE_CONFIGS["code-ef"]
        hard = [p for p in code_config if p["gate_type"] == "hard"]
        assert len(hard) == 4
        for p in hard:
            assert p["evidence"]["type"] == "ledger_only"

    def test_go_hard_gates_all_have_file_flag(self) -> None:
        go_config = ENFORCE_CONFIGS["go"]
        hard = [p for p in go_config if p["gate_type"] == "hard"]
        assert len(hard) == 8
        for p in hard:
            ev = p["evidence"]
            items = ev if isinstance(ev, list) else [ev]
            types = [e["type"] for e in items]
            assert "file_flag" in types, f"go:{p['name']} hard gate has no file_flag evidence"

    def test_advisory_phases_present(self) -> None:
        """Both canonical -ef skills must have at least one advisory phase."""
        for skill_id in ENFORCE_CONFIGS:
            config = ENFORCE_CONFIGS[skill_id]
            advisory = [p for p in config if p["gate_type"] == "advisory"]
            assert len(advisory) >= 1, f"{skill_id} has no advisory phases"


# ---------------------------------------------------------------------------
# Canonical name + backward-compat alias tests
# ---------------------------------------------------------------------------

class TestCanonicalEENames:
    """Test that consolidated skill names are canonical and older names are aliases."""

    def test_code_ef_and_code_v4_load_same_phases(self) -> None:
        """code-ef and code_v4.0 resolve to identical phase lists."""
        canonical = ENFORCE_CONFIGS["code-ef"]
        alias = ENFORCE_CONFIGS["code_v4.0"]
        assert canonical is alias  # same list object
        assert [p["name"] for p in canonical] == [p["name"] for p in alias]

    def test_go_aliases_load_same_phases(self) -> None:
        """go, go-ef, and go_v3.0 resolve to identical phase lists."""
        canonical = ENFORCE_CONFIGS["go"]
        ef_alias = ENFORCE_CONFIGS["go-ef"]
        alias = ENFORCE_CONFIGS["go_v3.0"]
        assert canonical is ef_alias
        assert canonical is alias  # same list object
        assert [p["name"] for p in canonical] == [p["name"] for p in alias]

    def test_load_config_for_skill_resolves_code_ef(self) -> None:
        config = load_config_for_skill("code-ef")
        hard = [p for p in config if p["gate_type"] == "hard"]
        assert len(hard) == 4

    def test_load_config_for_skill_resolves_go(self) -> None:
        config = load_config_for_skill("go")
        hard = [p for p in config if p["gate_type"] == "hard"]
        assert len(hard) == 8

    def test_load_config_for_skill_resolves_code_v4_backward_compat(self) -> None:
        config = load_config_for_skill("code_v4.0")
        hard = [p for p in config if p["gate_type"] == "hard"]
        assert len(hard) == 4

    def test_load_config_for_skill_resolves_go_v3_backward_compat(self) -> None:
        config = load_config_for_skill("go_v3.0")
        hard = [p for p in config if p["gate_type"] == "hard"]
        assert len(hard) == 8
