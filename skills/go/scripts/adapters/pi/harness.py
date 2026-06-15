#!/usr/bin/env python3
"""Headless PI harness for /go.

The harness owns PI process execution and durable PI artifacts. The
orchestrator decides when to call it; this module decides how PI is invoked,
how JSONL is captured, and what resume/evidence files are written.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PI_TOOLS = "read,grep,find,ls,edit,write,bash"


@dataclass
class PiHarnessResult:
    exit_code: int
    session_id: str | None
    transcript_path: Path
    session_dir: Path
    command: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_pi_command(
    pi_model: str,
    session_dir: Path,
    task_file: Path,
    prompt: str,
    tools: str | None = None,
) -> list[str]:
    """Build the conservative headless PI command used by /go."""
    pi_executable = shutil.which("pi") or "pi"
    cmd = [
        pi_executable,
        "-p",
        "--mode",
        "json",
        "--model",
        pi_model,
        "--session-dir",
        str(session_dir),
        "--no-context-files",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
    ]
    tool_list = tools if tools is not None else os.environ.get("GO_PI_TOOLS", DEFAULT_PI_TOOLS)
    if tool_list:
        cmd.extend(["--tools", tool_list])
    cmd.extend(
        [
            "--system-prompt",
            "You are a coding agent. Complete the task. Use read/edit/write/bash tools. "
            "Run verification commands after writing code.",
            "-p",
            f"@{task_file}",
            prompt,
        ]
    )
    return cmd


def parse_jsonl_events(text: str) -> list[dict[str, Any]]:
    """Parse PI JSONL output, ignoring non-JSON diagnostic lines."""
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def extract_session_id(events: list[dict[str, Any]]) -> str | None:
    """Extract a PI session id from common JSONL event shapes."""
    for event in events:
        if event.get("type") == "session":
            value = event.get("id") or event.get("session_id") or event.get("sessionId")
            if value:
                return str(value)
        value = event.get("session_id") or event.get("sessionId")
        if value:
            return str(value)
    return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_pi_artifacts(
    state_dir: Path,
    run_id: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    command: list[str],
    session_dir: Path,
    worktree: Path,
) -> PiHarnessResult:
    events_path = state_dir / f"pi-events_{run_id}.jsonl"
    transcript_path = state_dir / f"pi-transcript_{run_id}.jsonl"
    stderr_path = state_dir / f"pi-stderr_{run_id}.txt"

    events_path.write_text(stdout, encoding="utf-8")
    transcript_path.write_text(stdout, encoding="utf-8")
    if stderr:
        stderr_path.write_text(stderr, encoding="utf-8")

    events = parse_jsonl_events(stdout)
    session_id = extract_session_id(events)
    resume_line = ""
    if session_id:
        resume_line = f"pi --session {session_id} --session-dir {session_dir}"
        (state_dir / f"resume_{run_id}.txt").write_text(resume_line + "\n", encoding="utf-8")

    write_json(
        state_dir / f"pi-session_{run_id}.json",
        {
            "schema_version": "go.pi-session.v1",
            "run_id": run_id,
            "session_id": session_id,
            "session_dir": str(session_dir),
            "worktree": str(worktree),
            "events_path": str(events_path),
            "transcript_path": str(transcript_path),
            "resume_command": resume_line,
            "exit_code": exit_code,
            "event_count": len(events),
            "created_at": now_iso(),
        },
    )
    write_json(
        state_dir / f"dispatch-result_{run_id}.json",
        {
            "schema_version": "go.dispatch-result.v1",
            "run_id": run_id,
            "dispatch": "pi",
            "status": "completed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "command": command,
            "session_id": session_id,
            "session_dir": str(session_dir),
            "transcript_path": str(transcript_path),
            "stderr_path": str(stderr_path) if stderr else None,
            "updated_at": now_iso(),
        },
    )
    if exit_code != 0:
        (state_dir / f".blocked_{run_id}").touch()
    return PiHarnessResult(
        exit_code=exit_code,
        session_id=session_id,
        transcript_path=transcript_path,
        session_dir=session_dir,
        command=command,
    )


def write_failed_pi_artifacts(
    state_dir: Path,
    run_id: str,
    command: list[str],
    session_dir: Path,
    worktree: Path,
    status: str,
    error: BaseException,
    stdout: str = "",
    stderr: str = "",
) -> PiHarnessResult:
    """Write failure artifacts when PI cannot produce a normal result."""
    result = write_pi_artifacts(
        state_dir=state_dir,
        run_id=run_id,
        exit_code=124 if status == "timed_out" else 127,
        stdout=stdout,
        stderr=stderr or str(error),
        command=command,
        session_dir=session_dir,
        worktree=worktree,
    )
    dispatch_path = state_dir / f"dispatch-result_{run_id}.json"
    payload = json.loads(dispatch_path.read_text(encoding="utf-8"))
    payload["status"] = status
    payload["error_type"] = type(error).__name__
    payload["error"] = str(error)
    write_json(dispatch_path, payload)
    (state_dir / f".blocked_{run_id}").touch()
    return result


def run_pi_harness(
    worktree: Path,
    state_dir: Path,
    run_id: str,
    pi_model: str,
    prompt: str,
) -> PiHarnessResult:
    """Run PI in headless JSON mode and write /go PI artifacts."""
    state_dir = state_dir.resolve()
    worktree = worktree.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    session_dir = (state_dir / "pi-sessions" / run_id).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    task_file = (state_dir / f"active-task_{run_id}.json").resolve()
    command = build_pi_command(pi_model, session_dir, task_file, prompt)

    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["GO_STATE_DIR"] = str(state_dir)
    env["WORKTREE"] = str(worktree)
    env["PI_CODING_AGENT_SESSION_DIR"] = str(session_dir)

    timeout = int(os.environ.get("GO_PI_TIMEOUT_SECONDS", "1800"))
    try:
        proc = subprocess.run(
            command,
            cwd=worktree,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.output or ""
        stderr = exc.stderr or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return write_failed_pi_artifacts(
            state_dir=state_dir,
            run_id=run_id,
            command=command,
            session_dir=session_dir,
            worktree=worktree,
            status="timed_out",
            error=exc,
            stdout=output,
            stderr=stderr,
        )
    except OSError as exc:
        return write_failed_pi_artifacts(
            state_dir=state_dir,
            run_id=run_id,
            command=command,
            session_dir=session_dir,
            worktree=worktree,
            status="failed",
            error=exc,
        )
    return write_pi_artifacts(
        state_dir=state_dir,
        run_id=run_id,
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        command=command,
        session_dir=session_dir,
        worktree=worktree,
    )
