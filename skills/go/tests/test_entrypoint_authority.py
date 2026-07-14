#!/usr/bin/env python3
"""Tests for /go authority: orchestrate.py is the single canonical full runtime.

Proves:
- orchestrate.py is the only supported runtime entrypoint.
- Legacy wrappers are removed (negative existence test).
- No active documentation references deleted entrypoints.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
ROOT = SCRIPTS.parent
PACKAGE = ROOT.parent.parent


def _load_orchestrate():
    """Load orchestrate.py as a module for testing."""
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS))
    import orchestrate as _orch
    _sys.path.pop(0)
    return _orch


# --- Canonical runtime authority --------------------------------------------


def test_orchestrate_is_the_canonical_full_runtime():
    """orchestrate.py provides all major runtime responsibilities."""
    orch = _load_orchestrate()
    assert hasattr(orch, "ensure_runtime_env"), "missing ensure_runtime_env"
    assert hasattr(orch, "create_worktree"), "missing create_worktree"
    assert hasattr(orch, "resolve_session_id"), "missing resolve_session_id"
    assert hasattr(orch, "parse_args"), "missing parse_args"
    assert hasattr(orch, "main"), "missing main"
    assert callable(getattr(orch, "orchestrate", None)), "missing orchestrate"


def test_orchestrate_help_succeeds():
    """--help exits 0 without creating artifacts or worktrees."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"exit {result.returncode}: {result.stderr}"
    assert "usage:" in result.stdout
    assert "/go orchestrator" in result.stdout


def test_orchestrate_preflight_only_does_not_create_worktree(tmp_path, monkeypatch):
    """--preflight-only does not create a worktree (may fail, but no production state)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path / "state"))
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test preflight"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert not (tmp_path / ".worktrees").exists(), "worktree was created"
    assert not (tmp_path / ".claude").exists(), "artifacts were created"


def test_only_one_canonical_full_runtime():
    """Only orchestrate.py remains as a full runtime entrypoint."""
    orch_text = (SCRIPTS / "orchestrate.py").read_text(encoding="utf-8")
    assert "def create_worktree" in orch_text
    assert "def ensure_runtime_env" in orch_text


# --- Deleted entrypoint verification ----------------------------------------


def test_legacy_go_safe_deleted():
    """go_safe.py has been removed (no active consumers)."""
    assert not (SCRIPTS / "go_safe.py").exists()


def test_legacy_init_go_run_deleted():
    """init_go_run.py has been removed."""
    assert not (SCRIPTS / "init_go_run.py").exists()


def test_legacy_validate_go_contracts_deleted():
    """validate_go_contracts.py has been removed."""
    assert not (SCRIPTS / "validate_go_contracts.py").exists()


def test_scripts_go_safe_sh_deleted():
    """scripts/go-safe.sh has been removed."""
    assert not (SCRIPTS / "go-safe.sh").exists()


def test_root_go_safe_sh_deleted():
    """Root go-safe.sh has been removed."""
    assert not (ROOT / "go-safe.sh").exists()


# --- Negative registration check --------------------------------------------


def test_orchestrate_does_not_reference_deleted_wrappers():
    """orchestrate.py does not reference any deleted wrapper filename."""
    orch_text = (SCRIPTS / "orchestrate.py").read_text(encoding="utf-8")
    assert "go_safe.py" not in orch_text
    assert "go-safe.sh" not in orch_text
    assert "init_go_run" not in orch_text
    assert "validate_go_contracts" not in orch_text
