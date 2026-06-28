#!/usr/bin/env python3
"""Tests for /go task selection and claiming."""

import json
import os
import pathlib
import subprocess
import sys

import jsonschema


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "scripts" / "select-task.py"


def _write_tasks(path: pathlib.Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "tasks": [
                    {
                        "id": "TASK-1",
                        "title": "First task",
                        "objective": "Do first task",
                        "status": "ready",
                        "priority": "P1",
                        "scope_in": ["src/first.py"],
                        "scope_out": [],
                        "forbidden_files": [],
                        "acceptance_criteria": ["first done"],
                        "verification_commands": ["python -m pytest tests/test_first.py"],
                    },
                    {
                        "id": "TASK-2",
                        "title": "Second task",
                        "objective": "Do second task",
                        "status": "queued",
                        "priority": "P2",
                        "scope_in": ["src/second.py"],
                        "scope_out": [],
                        "forbidden_files": [],
                        "acceptance_criteria": ["second done"],
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _run_select(tasks_file: pathlib.Path, state_dir: pathlib.Path, run_id: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GO_TASKS_FILE"] = str(tasks_file)
    env["GO_STATE_DIR"] = str(state_dir)
    env["RUN_ID"] = run_id
    env["TERMINAL_ID"] = "test-terminal"
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


def test_select_task_claims_selected_task_in_source_queue(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _write_tasks(tasks_file)

    result = _run_select(tasks_file, state_dir, "run-1")

    assert result.returncode == 0, result.stderr
    active = json.loads((state_dir / "active-task_run-1.json").read_text(encoding="utf-8"))
    assert active["task"]["id"] == "TASK-1"
    assert active["source"] == "tasks-file"
    assert active["source_ref"] == str(tasks_file.resolve())

    updated = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert updated["tasks"][0]["status"] == "selected"
    assert updated["tasks"][0]["selected_by"] == "run-1"
    assert updated["tasks"][1]["status"] == "queued"


def test_select_task_second_run_skips_already_claimed_task(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _write_tasks(tasks_file)

    first = _run_select(tasks_file, state_dir, "run-1")
    second = _run_select(tasks_file, state_dir, "run-2")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_active = json.loads((state_dir / "active-task_run-1.json").read_text(encoding="utf-8"))
    second_active = json.loads((state_dir / "active-task_run-2.json").read_text(encoding="utf-8"))
    assert first_active["task"]["id"] == "TASK-1"
    assert second_active["task"]["id"] == "TASK-2"


def test_select_task_fails_closed_when_lock_exists(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _write_tasks(tasks_file)
    tasks_file.with_suffix(tasks_file.suffix + ".lock").write_text("other-run\n", encoding="utf-8")

    result = _run_select(tasks_file, state_dir, "run-locked")

    assert result.returncode == 3
    assert "locked" in result.stderr.lower()
    assert not (state_dir / "active-task_run-locked.json").exists()


def test_select_task_recovers_stale_lock(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _write_tasks(tasks_file)
    lock = tasks_file.with_suffix(tasks_file.suffix + ".lock")
    lock.write_text("stale-run\n", encoding="utf-8")
    old_time = 1
    os.utime(lock, (old_time, old_time))

    result = _run_select(tasks_file, state_dir, "run-stale")

    assert result.returncode == 0, result.stderr
    assert not lock.exists()
    active = json.loads((state_dir / "active-task_run-stale.json").read_text(encoding="utf-8"))
    assert active["task"]["id"] == "TASK-1"


def test_select_task_chooses_highest_priority_before_file_order(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _write_tasks(tasks_file)
    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    data["tasks"][0]["priority"] = "P9"
    data["tasks"][1]["priority"] = "P1"
    tasks_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    result = _run_select(tasks_file, state_dir, "run-priority")

    assert result.returncode == 0, result.stderr
    active = json.loads((state_dir / "active-task_run-priority.json").read_text(encoding="utf-8"))
    assert active["task"]["id"] == "TASK-2"


def test_select_task_does_not_claim_queue_when_active_artifact_cannot_be_written(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    bad_state_dir = tmp_path / "missing" / "state"
    _write_tasks(tasks_file)

    result = _run_select(tasks_file, bad_state_dir, "run-no-artifact")

    assert result.returncode == 4
    updated = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert updated["tasks"][0]["status"] == "ready"
    assert not (bad_state_dir / "active-task_run-no-artifact.json").exists()


def test_select_task_rewritten_queue_matches_schema(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _write_tasks(tasks_file)

    result = _run_select(tasks_file, state_dir, "run-schema")

    assert result.returncode == 0, result.stderr
    schema = json.loads((PACKAGE / "schemas" / "tasks-file.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(tasks_file.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_select_task_pauses_when_only_gated_tasks_remain(tmp_path):
    """Run-to-completion pause marker: only requires_approval tasks left -> PAUSED_FOR_APPROVAL."""
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    tasks_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "GATED-1",
                        "title": "needs director signoff",
                        "status": "ready",
                        "priority": "P1",
                        "requires_approval": True,
                        "pause_reason": "measurement needs director eyes",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_select(tasks_file, state_dir, "run-paused")

    assert result.returncode == 2, result.stderr
    assert "<promise>PAUSED_FOR_APPROVAL</promise>" in result.stdout
    paused = json.loads((state_dir / ".paused_run-paused").read_text(encoding="utf-8"))
    assert paused["gated"][0]["id"] == "GATED-1"
    assert paused["gated"][0]["reason"] == "measurement needs director eyes"
    # A pause must not mutate the queue or claim a task.
    assert not (state_dir / "active-task_run-paused.json").exists()
    assert json.loads(tasks_file.read_text(encoding="utf-8"))["tasks"][0]["status"] == "ready"


def test_select_task_skips_gated_task_in_favor_of_ungated(tmp_path):
    """A gated task must not preempt an ungated one, even at higher priority."""
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    tasks_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "GATED",
                        "title": "gated higher priority",
                        "status": "ready",
                        "priority": "P1",
                        "requires_approval": True,
                    },
                    {
                        "id": "UNGATED",
                        "title": "ungated lower priority",
                        "status": "ready",
                        "priority": "P2",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_select(tasks_file, state_dir, "run-skip")

    assert result.returncode == 0, result.stderr
    active = json.loads((state_dir / "active-task_run-skip.json").read_text(encoding="utf-8"))
    assert active["task"]["id"] == "UNGATED"
    assert not (state_dir / ".paused_run-skip").exists()


def test_select_task_selects_gated_task_once_approved(tmp_path):
    """Flipping a gated task's status to 'approved' makes it selectable."""
    tasks_file = tmp_path / "tasks.json"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    tasks_file.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "GATED",
                        "title": "approved gate",
                        "status": "approved",
                        "priority": "P1",
                        "requires_approval": True,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_select(tasks_file, state_dir, "run-approved")

    assert result.returncode == 0, result.stderr
    active = json.loads((state_dir / "active-task_run-approved.json").read_text(encoding="utf-8"))
    assert active["task"]["id"] == "GATED"
