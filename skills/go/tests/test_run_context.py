#!/usr/bin/env python3
"""Tests for run_context.resolve() — the disk-authority run-identity reader.

Covers INV-1..INV-5 + D7/D8 (rev 1.1). Hermetic: all disk state under tmp_path,
canonical_terminal_id_from_env monkeypatched to a fixed value.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_context  # noqa: E402


RUN_ID = "run-abc123"
TERMINAL_ID = "console_test_tid"


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """tmp_path-based state dir + a fixed canonical terminal_id."""
    state_dir = tmp_path / "go-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        run_context, "canonical_terminal_id_from_env", lambda: TERMINAL_ID
    )
    # Strip env fast-path vars so disk tiers are exercised unless a test sets them.
    for var in ("GO_RUN_ID", "RUN_ID", "CLAUDE_GO_RUN_ID", "GO_STATE_DIR"):
        monkeypatch.delenv(var, raising=False)
    return state_dir


def _write_current_run(state_dir, run_id, terminal_id=TERMINAL_ID, status="running"):
    payload = {
        "schema_version": "go.current-run.v1",
        "run_id": run_id,
        "terminal_id": terminal_id,
        "go_state_dir": str(state_dir.resolve()),
        "dispatch": "local",
        "status": status,
        "updated_at": "2026-06-28T00:00:00Z",
    }
    (state_dir / f"current-run_{terminal_id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    (state_dir / "current-run.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_env_json(state_dir, run_id, terminal_id=TERMINAL_ID):
    payload = {
        "TERMINAL_ID": terminal_id,
        "RUN_ID": run_id,
        "GO_STATE_DIR": str(state_dir.resolve()),
        "GO_TASKS_FILE": "tasks.json",
    }
    (state_dir / "env.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_active_task(state_dir, run_id):
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"id": "TASK-1"}}), encoding="utf-8"
    )


# (a) Precedence order — five branches ----------------------------------------


def test_precedence_env_beats_current_run(isolated_state, monkeypatch):
    monkeypatch.setenv("GO_RUN_ID", RUN_ID)
    _write_current_run(isolated_state, RUN_ID)  # agrees with env
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert ctx.run_id == RUN_ID
    assert ctx.source == "env"


def test_precedence_current_run_beats_env_json(isolated_state):
    _write_current_run(isolated_state, "from-current-run")
    _write_env_json(isolated_state, "from-env-json")
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert ctx.run_id == "from-current-run"
    assert ctx.source == "current-run"


def test_precedence_env_json_beats_active_task_mtime(isolated_state):
    _write_env_json(isolated_state, "from-env-json")
    _write_active_task(isolated_state, "from-active-task")
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert ctx.run_id == "from-env-json"
    assert ctx.source == "env.json"


def test_precedence_active_task_mtime_is_fourth(isolated_state):
    _write_active_task(isolated_state, "from-active-task")
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert ctx.run_id == "from-active-task"
    assert ctx.source == "active-task-mtime"


def test_precedence_unresolved_is_fifth(isolated_state):
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is False
    assert ctx.source == "unresolved"


# (b) INV-2 compaction recovery -------------------------------------------------


def test_compaction_recovers_run_id(isolated_state):
    """Env fully unset + disk state present ⇒ recovers original run_id."""
    _write_current_run(isolated_state, RUN_ID)
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert ctx.run_id == RUN_ID
    assert ctx.state_dir == isolated_state.resolve()


# (c) INV-2 explicit-fail -------------------------------------------------------


def test_unresolved_writes_marker(isolated_state):
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is False
    assert ctx.run_id == ""
    marker = isolated_state / f".unresolved-run_{TERMINAL_ID}.json"
    assert marker.exists()
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["terminal_id"] == TERMINAL_ID
    assert "reason" in data


# (d) INV-1 stale-env disk-wins (D1 discriminator) -----------------------------


def test_stale_env_disk_wins(isolated_state, monkeypatch):
    monkeypatch.setenv("GO_RUN_ID", "stale-env-value")
    _write_current_run(isolated_state, "fresh-disk-value")  # differs from env
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert ctx.run_id == "fresh-disk-value"  # disk wins, not env
    assert ctx.source == "current-run"


# (e) INV-5 half-write tolerance -----------------------------------------------


def test_truncated_current_run_falls_through(isolated_state):
    (isolated_state / f"current-run_{TERMINAL_ID}.json").write_text(
        '{"run_id": "ab', encoding="utf-8"  # truncated JSON
    )
    _write_env_json(isolated_state, "from-env-json")
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert ctx.run_id == "from-env-json"
    assert ctx.source == "env.json"


# (f) D7 status-stale rejection -------------------------------------------------


@pytest.mark.parametrize("status", ["completed", "aborted", "failed"])
def test_status_stale_falls_through(isolated_state, status):
    _write_current_run(isolated_state, "dead-run", status=status)
    _write_env_json(isolated_state, "live-run")
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.run_id == "live-run"
    assert ctx.source == "env.json"


# (g) INV-3 two-terminal isolation ---------------------------------------------


def test_two_terminals_isolate_state_dirs(tmp_path, monkeypatch):
    tid_a, tid_b = "console_A", "console_B"
    dir_a = tmp_path / "a" / "go"
    dir_b = tmp_path / "b" / "go"
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)
    _write_current_run(dir_a, "run-a", terminal_id=tid_a)
    _write_current_run(dir_b, "run-b", terminal_id=tid_b)

    monkeypatch.setattr(run_context, "canonical_terminal_id_from_env", lambda: tid_a)
    ctx_a = run_context.resolve(state_dir_hint=dir_a)
    monkeypatch.setattr(run_context, "canonical_terminal_id_from_env", lambda: tid_b)
    ctx_b = run_context.resolve(state_dir_hint=dir_b)

    assert ctx_a.run_id == "run-a"
    assert ctx_b.run_id == "run-b"
    assert ctx_a.state_dir != ctx_b.state_dir
    assert ctx_a.run_id != ctx_b.run_id


# (h) INV-4 canonical-name write ------------------------------------------------


def test_resolve_reads_aliases_writes_go_run_id(isolated_state, monkeypatch):
    """Seed env RUN_ID=X (alias), assert source=env. resolve() must not WRITE;
    canonical write key is GO_RUN_ID — verified by orchestrate.write_current_run
    which emits run_id only. Here we assert alias-read + env source."""
    monkeypatch.setenv("RUN_ID", "alias-value")  # alias, not canonical GO_RUN_ID
    _write_current_run(isolated_state, "alias-value")  # agrees
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.source == "env"
    assert ctx.run_id == "alias-value"


# (i) Malformed-state tolerance -------------------------------------------------


def test_malformed_current_run_falls_through(isolated_state):
    for bad in ("{}", '{"run_id": 123}', "not-json-at-all"):
        # Reset + write each malformed shape, env.json is the fallback.
        _write_env_json(isolated_state, "from-env-json")  # ensure fallback exists
        (isolated_state / f"current-run_{TERMINAL_ID}.json").write_text(
            bad, encoding="utf-8"
        )
        ctx = run_context.resolve(state_dir_hint=isolated_state)
        assert ctx.run_id == "from-env-json", f"failed on malformed: {bad}"
        assert ctx.source == "env.json"


def test_env_json_missing_required_field_falls_through(isolated_state):
    # env.json present but missing RUN_ID → must not bind an empty/None run_id.
    (isolated_state / "env.json").write_text(
        json.dumps({"TERMINAL_ID": TERMINAL_ID, "GO_STATE_DIR": str(isolated_state)}),
        encoding="utf-8",
    )
    _write_active_task(isolated_state, "from-active-task")
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.run_id == "from-active-task"
    assert ctx.source == "active-task-mtime"


# (j) D8 fallback-detection -----------------------------------------------------


def test_fallback_terminal_id_unresolved(isolated_state, monkeypatch):
    """canonical_terminal_id_from_env() returns None ⇒ resolved=False, marker written."""
    monkeypatch.setattr(run_context, "canonical_terminal_id_from_env", lambda: None)
    _write_current_run(isolated_state, "would-bind")  # disk present, but no tid
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is False
    assert ctx.tid_source == "none"
    # Marker written with empty terminal_id (no tid to scope it).
    markers = list(isolated_state.glob(".unresolved-run_*.json"))
    assert markers, "expected unresolved marker on fallback tid"


# (k) Marker lifecycle ----------------------------------------------------------


def test_marker_deleted_on_success(isolated_state):
    # First resolve fails → marker written.
    run_context.resolve(state_dir_hint=isolated_state)
    marker = isolated_state / f".unresolved-run_{TERMINAL_ID}.json"
    assert marker.exists()
    # Seed disk state → next resolve succeeds → marker deleted.
    _write_current_run(isolated_state, RUN_ID)
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is True
    assert not marker.exists()


# (l) Marker-write failure ------------------------------------------------------


def test_marker_write_failure_no_raise(isolated_state):
    """Read-only state dir on failure path ⇒ no exception, resolved=False."""
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.resolved is False  # baseline: marker written normally
    # Now make the marker file undeletable/readonly and force another failure.
    marker = isolated_state / f".unresolved-run_{TERMINAL_ID}.json"
    marker.chmod(0o444) if os.name != "nt" else None
    # Re-resolve with no disk state still fails; must not raise regardless of FS perms.
    try:
        ctx2 = run_context.resolve(state_dir_hint=isolated_state)
        assert ctx2.resolved is False
    finally:
        marker.chmod(0o644) if os.name != "nt" else None


# tid_source audit field --------------------------------------------------------


def test_tid_source_canonical_env(isolated_state):
    _write_current_run(isolated_state, RUN_ID)
    ctx = run_context.resolve(state_dir_hint=isolated_state)
    assert ctx.tid_source == "canonical-env"
    assert ctx.terminal_id == TERMINAL_ID
