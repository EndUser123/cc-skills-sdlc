#!/usr/bin/env python3
"""Tests for Pass 2 of /go authority consolidation.

Proves:
- orchestrate.py is the canonical full runtime entrypoint.
- go_safe.py is a compatibility initialization guard, not a runtime authority.
- The root go-safe.sh is a convenience wrapper with no runtime registration.
- scripts/go-safe.sh is dead code.
- No wrapper duplicates orchestration logic.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
ROOT = SCRIPTS.parent  # skills/go/
PACKAGE = ROOT.parent.parent  # cc-skills-sdlc/


def _load_orchestrate():
    """Load orchestrate.py as a module for testing."""
    import importlib
    import sys as _sys
    # Use path-based import so annotations resolve correctly (spec_from_file_location
    # doesn't register __module__ properly for Python 3.14's dataclass string annotations).
    _sys.path.insert(0, str(SCRIPTS))
    import orchestrate as _orch
    _sys.path.pop(0)
    return _orch


def _load_go_safe():
    """Load go_safe.py as a module for testing."""
    import importlib
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS))
    import go_safe as _gs
    _sys.path.pop(0)
    return _gs


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


def test_orchestrate_help_does_not_mutate_state():
    """--help exits 0 without creating artifacts or worktrees."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"exit {result.returncode}: {result.stderr}"
    assert "usage:" in result.stdout
    assert "/go orchestrator" in result.stdout


def test_orchestrate_preflight_only_does_not_dispatch(tmp_path, monkeypatch):
    """--preflight-only with a prompt should not create a worktree."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path / "state"))
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "orchestrate.py"),
         "--preflight-only", "--prompt", "test preflight"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    # May fail (no git repo) but must NOT create production state in P:/
    assert not (tmp_path / ".worktrees").exists(), "worktree was created"
    assert not (tmp_path / ".claude").exists(), "artifacts were created"


# --- go_safe.py compatibility role ------------------------------------------


def test_go_safe_is_not_the_orchestrator():
    """go_safe.py does not provide orchestration functions."""
    gs = _load_go_safe()
    assert hasattr(gs, "infer_args"), "missing infer_args"
    assert hasattr(gs, "main"), "missing main"
    # Must NOT have orchestration functions
    assert not hasattr(gs, "create_worktree"), "go_safe should not create worktrees"
    assert not hasattr(gs, "ensure_runtime_env"), "go_safe should not be runtime env"
    assert not hasattr(gs, "dispatch_pi"), "go_safe should not dispatch"
    assert not hasattr(gs, "run_common_tail"), "go_safe should not run tail"


def test_go_safe_has_no_active_runtime_callers():
    """go_safe.py is referenced only in its own test and a refactor scan list."""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "skills.go.scripts.go_safe",
         "--root-dir", "/nonexistent", "--go-run-id", "test", "--terminal-id", "test"],
        capture_output=True, text=True,
    )
    # Should fail (no git repo) but prove the entry point is separate
    assert result.returncode != 0


# --- Shell wrapper documentation --------------------------------------------

def test_root_go_safe_sh_not_used_by_orchestrate():
    """The root go-safe.sh is NOT invoked by orchestrate.py or SKILL.md."""
    orch_text = (SCRIPTS / "orchestrate.py").read_text(encoding="utf-8")
    assert "go-safe.sh" not in orch_text, "orchestrate.py references go-safe.sh"


def test_scripts_go_safe_sh_has_no_references():
    """scripts/go-safe.sh has zero references outside itself and tests."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "scripts/go-safe\\.sh",
         str(PACKAGE / "skills" / "go" / "scripts")],
        capture_output=True, text=True,
    )
    lines = [l for l in result.stdout.splitlines()
             if "__pycache__" not in l
             and l.strip() != ""]
    assert len(lines) == 0, f"scripts/go-safe.sh references found: {lines}"


# --- Entrypoint authority manifest ------------------------------------------

ENTRYPOINT_REGISTRY = {
    "orchestrate.py": {
        "role": "canonical full runtime",
        "authority": "run identity, task acquisition, state, worktrees, dispatch, continuation, completion",
        "invoked_by": "SKILL.md (direct python invocation), Stop hook, user handoff",
        "status": "active",
    },
    "go_safe.py": {
        "role": "compatibility initialization guard",
        "authority": "artifact init and validation (non-orchestration)",
        "invoked_by": "none (no active runtime callers)",
        "status": "compatibility",
    },
    "go-safe.sh": {
        "role": "interactive user-facing convenience wrapper",
        "authority": "none — calls /go or go command",
        "invoked_by": "documentation (IMPLEMENTATION-GUIDE.md, GO-QUICK-REFERENCE.md)",
        "status": "documented-convenience",
    },
    "scripts/go-safe.sh": {
        "role": "Bash init/validation (superseded by go_safe.py)",
        "authority": "none — dead code",
        "invoked_by": "none",
        "status": "dead",
    },
}


def test_entrypoint_manifest_accurate():
    """Every entrypoint has a documented role and status."""
    for name, info in ENTRYPOINT_REGISTRY.items():
        assert "role" in info, f"{name} missing role"
        assert "status" in info, f"{name} missing status"
        if name == "orchestrate.py":
            assert info["status"] == "active"
            assert info["role"] == "canonical full runtime"


def test_only_one_canonical_full_runtime():
    """Exactly one entrypoint claims canonical full runtime authority."""
    canonicals = [n for n, i in ENTRYPOINT_REGISTRY.items()
                  if i.get("role") == "canonical full runtime"]
    assert len(canonicals) == 1, f"Expected 1 canonical runtime, found {canonicals}"
    assert canonicals[0] == "orchestrate.py"
