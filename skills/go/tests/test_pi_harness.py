#!/usr/bin/env python3
"""Tests for the /go pi harness adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import stat
import sys


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
_PI_HARNESS = _load_module(
    "go_pi_harness",
    PACKAGE / "scripts" / "adapters" / "pi" / "harness.py",
)


def _install_fake_pi(bin_dir: pathlib.Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / ("pi.cmd" if os.name == "nt" else "pi")
    if os.name == "nt":
        emitter = bin_dir / "fake_pi.py"
        emitter.write_text(
            "import json\n"
            "events = [\n"
            "    {'type': 'session', 'id': 'sess-123'},\n"
            "    {'type': 'message_update', 'delta': 'working'},\n"
            "    {'type': 'tool_execution_start', 'toolName': 'edit', 'input': {'path': 'a.py'}},\n"
            "    {'type': 'turn_end', 'message': 'done'},\n"
            "    {'type': 'agent_end', 'messages': [{'role': 'assistant', 'content': 'done'}]},\n"
            "]\n"
            "for event in events:\n"
            "    print(json.dumps(event, separators=(',', ':')))\n",
            encoding="utf-8",
        )
        script.write_text(
            "@echo off\r\n"
            f"\"{sys.executable}\" \"{emitter}\"\r\n",
            encoding="utf-8",
        )
    else:
        script.write_text(
            "#!/usr/bin/env sh\n"
            "printf '%s\\n' '{\"type\":\"session\",\"id\":\"sess-123\",\"cwd\":\"'\"$(pwd)\"'\"}'\n"
            "printf '%s\\n' '{\"type\":\"message_update\",\"delta\":\"working\"}'\n"
            "printf '%s\\n' '{\"type\":\"tool_execution_start\",\"toolName\":\"edit\"}'\n"
            "printf '%s\\n' '{\"type\":\"turn_end\",\"message\":\"done\"}'\n"
            "printf '%s\\n' '{\"type\":\"agent_end\",\"messages\":[{\"role\":\"assistant\",\"content\":\"done\"}]}'\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)


def test_pi_harness_runs_json_mode_and_writes_artifacts(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    _install_fake_pi(bin_dir)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    state_dir = tmp_path / "state"
    worktree = tmp_path / "worktree"
    state_dir.mkdir()
    worktree.mkdir()
    task_file = state_dir / "active-task_run1.json"
    task_file.write_text(
        json.dumps({"task": {"title": "Do it", "objective": "Do it"}}) + "\n",
        encoding="utf-8",
    )

    result = _PI_HARNESS.run_pi_harness(
        worktree=worktree,
        state_dir=state_dir,
        run_id="run1",
        pi_model="minimax/MiniMax-M3",
        prompt="Task: Do it",
    )

    assert result.exit_code == 0
    assert result.session_id == "sess-123"

    events_path = state_dir / "pi-events_run1.jsonl"
    assert events_path.exists()
    assert "\"type\":\"session\"" in events_path.read_text(encoding="utf-8")

    session = json.loads((state_dir / "pi-session_run1.json").read_text(encoding="utf-8"))
    assert session["session_id"] == "sess-123"
    assert pathlib.Path(session["session_dir"]).is_absolute()
    assert "pi --session sess-123" in (state_dir / "resume_run1.txt").read_text(encoding="utf-8")

    dispatch = json.loads((state_dir / "dispatch-result_run1.json").read_text(encoding="utf-8"))
    assert dispatch["dispatch"] == "pi"
    assert dispatch["status"] == "completed"
    assert "--mode" in dispatch["command"]
    assert "--session-dir" in dispatch["command"]
    assert "--no-extensions" in dispatch["command"]
    assert "--no-skills" in dispatch["command"]
