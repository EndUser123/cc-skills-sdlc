"""Regression tests for the Stop-side completion-authority reduction.

The broad completion-authority logic (overclaim detection, evidence-level
downgrade, nearest-target binding, completion-authority log) was removed
from Stop_enforce_gate.py. The orchestrator-side completion_evidence_review.py
is the single source of truth for broad completion evidence; Stop hooks
verify only narrow, session-bound artifacts.

Per the repo anti-mock policy: real imports of Stop_enforce_gate, real
tmp_path state dirs, no Mock objects.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
GATE_PY = PLUGIN_ROOT / "hooks" / "Stop_enforce_gate.py"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _load_gate():
    spec = importlib.util.spec_from_file_location("stop_enforce_gate", GATE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def test_broad_overclaim_helpers_removed(gate):
    """Broad completion-authority helpers must not exist in Stop_enforce_gate."""
    for name in (
        "_OVERCLAIM_TERMS",
        "_detect_overclaim",
        "_has_evidence_file",
        "_evaluate_completion_evidence",
        "_downgrade_from_overclaim",
        "_write_completion_log",
        "_select_nearest_target",
        "evaluate_completion_authority",
    ):
        assert not hasattr(gate, name), (
            f"Stop_enforce_gate.{name} should be removed — broad completion "
            f"authority belongs in completion_evidence_review.py"
        )


def test_narrow_session_helpers_preserved(gate):
    """Narrow session-bound helpers must still exist."""
    assert callable(gate._read_active_task)
    assert callable(gate._is_validation_complete)
    assert callable(gate.main)


def test_main_does_not_invoke_completion_authority(gate, tmp_path, capsys):
    """main() must not block on completion-authority downgrades.

    Regression: a worker summary containing 'fixed'/'complete' must NOT
    trigger a Stop-side block — that classification belongs to the
    orchestrator-side completion_evidence_review.py only.
    """
    import json

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps({
        "session_id": "test-session",
        "stop_hook_active": False,
    }), encoding="utf-8")
    pointer_dir = Path("P:/.claude/.artifacts") / "go-sessions"
    pointer_dir.mkdir(parents=True, exist_ok=True)
    pointer = pointer_dir / "test-session.json"
    pointer.write_text(json.dumps({
        "go_state_dir": str(state_dir),
        "run_id": "run-X",
        "updated_at": "2026-07-08T12:00:00+00:00",
    }), encoding="utf-8")
    # Active task contains "fixed"/"complete" — would have triggered the old gate.
    (state_dir / "active-task_run-X.json").write_text(json.dumps({
        "task": {"summary": "Migration complete; bug fixed", "task_type": "implementation"},
    }), encoding="utf-8")

    import io
    import sys as _sys

    saved_stdin = _sys.stdin
    _sys.stdin = open(payload_file, "r", encoding="utf-8")
    try:
        try:
            gate.main()
        except SystemExit as e:
            # main() may exit 0 (allow) or fall through to enforce.stop_gate.
            # What it must NOT do is emit a {"decision":"block"} JSON.
            pass
    finally:
        _sys.stdin.close()
        _sys.stdin = saved_stdin

    captured = capsys.readouterr()
    # Old gate would have emitted a {"decision":"block"} with "continue: ..."
    # on this input. New gate must not.
    assert '"decision": "block"' not in captured.out, (
        f"Stop-side completion-authority block fired: {captured.out!r}"
    )
    # Cleanup the pointer so we don't leave test residue.
    pointer.unlink(missing_ok=True)