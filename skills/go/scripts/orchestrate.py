#!/usr/bin/env python3
"""Canonical /go SDLC orchestrator with selectable worker dispatch.

Default dispatch is pi. Override with:
    python orchestrate.py --dispatch claude --prompt "..."
    GO_DISPATCH=claude python orchestrate.py --prompt "..."
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

VALID_DISPATCHES = ("pi", "claude", "local")
SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parent.parent


@dataclass
class TaskContract:
    """Parsed task contract from active-task_*.json."""

    task_id: str
    title: str
    objective: str
    scope_in: list[str]
    scope_out: list[str]
    acceptance_criteria: list[str]
    verification_commands: list[str]
    forbidden_files: list[str]
    source: str
    raw: dict[str, Any]

    @classmethod
    def from_active_task(cls, data: dict[str, Any]) -> "TaskContract":
        inner = data.get("task", data)
        return cls(
            task_id=inner.get("id", "unknown"),
            title=inner.get("title", ""),
            objective=inner.get("objective", ""),
            scope_in=inner.get("scope_in", []),
            scope_out=inner.get("scope_out", []),
            acceptance_criteria=inner.get("acceptance_criteria", []),
            verification_commands=inner.get("verification_commands", []),
            forbidden_files=inner.get("forbidden_files", []),
            source=data.get("source", "unknown"),
            raw=inner,
        )


@dataclass
class PiModelInfo:
    """Resolved pi model from pi-model_*.json."""

    classifier_model: str
    tier: str
    pi_model: str

    @classmethod
    def load(cls, path: Path) -> "PiModelInfo":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)


@dataclass
class TranscriptVerdict:
    """Verdict from transcript review."""

    verdict: str
    reason: str
    critical_issues: list[str]

    @classmethod
    def from_subagent_json(cls, text: str) -> "TranscriptVerdict":
        data = json.loads(text)
        return cls(
            verdict=data.get("verdict", "FAIL"),
            reason=data.get("reason", ""),
            critical_issues=data.get("critical_issues", []),
        )


def default_dispatch() -> str:
    """Return dispatch mode from GO_DISPATCH, defaulting to pi."""

    value = os.environ.get("GO_DISPATCH", "pi").strip().lower()
    return value if value in VALID_DISPATCHES else "pi"


def script_path(*parts: str) -> Path:
    """Resolve a helper path inside the canonical /go skill."""

    return SKILL_DIR / Path(*parts)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_script(script: Path, args: list[str], state_dir: Path, run_id: str) -> int:
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=state_dir,
        capture_output=False,
    )
    return result.returncode


def phase_marker(state_dir: Path, phase: str, run_id: str) -> Path:
    p = state_dir / f".{phase}_{run_id}"
    touch(p)
    return p


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="/go orchestrator")
    parser.add_argument(
        "--dispatch",
        choices=VALID_DISPATCHES,
        default=default_dispatch(),
        help="Worker dispatch mode. Precedence: CLI, GO_DISPATCH, pi.",
    )
    parser.add_argument("--prompt", help="Task description (overrides task queue)")
    parser.add_argument("--plan", help="Path to plan.md")
    parser.add_argument("--tasks", help="Path to tasks.json")
    parser.add_argument("--scope-in", nargs="*", default=[], help="Scope in patterns")
    parser.add_argument("--forbidden", nargs="*", default=[], help="Forbidden files")
    return parser.parse_args(argv)


def ensure_runtime_env(dispatch: str) -> tuple[Path, str]:
    terminal_id = os.environ.get("TERMINAL_ID", "default")
    run_id = os.environ.get("RUN_ID") or os.environ.get("GO_RUN_ID") or str(uuid.uuid4())
    os.environ["RUN_ID"] = run_id
    os.environ.setdefault("MAX_ATTEMPTS", "3")
    os.environ.setdefault(
        "GO_STATE_DIR",
        str(Path(".claude") / ".artifacts" / terminal_id / "go"),
    )
    state_dir = Path(os.environ["GO_STATE_DIR"])
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir, run_id


def load_or_create_task(args: argparse.Namespace, state_dir: Path, run_id: str) -> TaskContract | None:
    if args.prompt:
        task_data: dict[str, Any] = {
            "run_id": run_id,
            "source": "cli",
            "task": {
                "id": f"prompt-{run_id[:8]}",
                "title": args.prompt[:60],
                "objective": args.prompt,
                "scope_in": args.scope_in or [],
                "scope_out": [],
                "acceptance_criteria": [],
                "verification_commands": [],
                "forbidden_files": args.forbidden or [],
            },
        }
        write_json(state_dir / f"active-task_{run_id}.json", task_data)
    else:
        select_script = script_path("scripts", "select-task.py")
        rc = run_script(select_script, [], state_dir, run_id)
        if rc != 0:
            return None
        phase_marker(state_dir, "task-selected", run_id)
        task_file = state_dir / f"active-task_{run_id}.json"
        task_data = json.loads(task_file.read_text(encoding="utf-8"))

    task = TaskContract.from_active_task(task_data)
    write_json(state_dir / f"task-contract-{run_id}.json", task.raw)
    return task


def create_worktree(dispatch: str, state_dir: Path, run_id: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    prefix = "pi" if dispatch == "pi" else "ai"
    root = Path("P:/worktrees")
    worktree = root / f"{prefix}-task-{ts}"
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "worktree", "add", "-b", f"{prefix}/{prefix}-task-{ts}", str(worktree), "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"git worktree add failed for {worktree}: {detail}")
    write_json(state_dir / f"worktree-{run_id}.json", {"worktree": str(worktree)})
    phase_marker(state_dir, "worktree", run_id)
    return worktree


def classify_and_resolve_pi(state_dir: Path, run_id: str) -> PiModelInfo | None:
    classify_script = script_path("scripts", "classify_complexity.py")
    rc = run_script(classify_script, [], state_dir, run_id)
    if rc != 0:
        return None
    phase_marker(state_dir, "classified", run_id)

    resolve_script = script_path("scripts", "adapters", "pi", "resolve_model.py")
    rc = run_script(resolve_script, [], state_dir, run_id)
    if rc != 0:
        return None
    phase_marker(state_dir, "model-resolved", run_id)
    return PiModelInfo.load(state_dir / f"pi-model_{run_id}.json")


def task_prompt(task_file: Path) -> str:
    task_json = json.loads(task_file.read_text(encoding="utf-8")) if task_file.exists() else {}
    inner = task_json.get("task", task_json)
    parts = [f"Task: {inner.get('title', '')}", f"Objective: {inner.get('objective', '')}"]
    for criterion in inner.get("acceptance_criteria", []):
        parts.append(f"- Accept: {criterion}")
    for command in inner.get("verification_commands", []):
        parts.append(f"- Verify: {command}")
    for item in inner.get("scope_in", []):
        parts.append(f"- Scope: {item}")
    for item in inner.get("forbidden_files", []):
        parts.append(f"- DO NOT modify: {item}")
    return "\n".join(parts)


def dispatch_pi(worktree: Path, state_dir: Path, run_id: str, pi_info: PiModelInfo) -> bool:
    dispatch_script = script_path("scripts", "write_dispatch_result.py")
    subprocess.run([sys.executable, str(dispatch_script)], cwd=state_dir, capture_output=False)

    pi_sessions = state_dir / "pi-sessions"
    pi_sessions.mkdir(parents=True, exist_ok=True)
    task_file = state_dir / f"active-task_{run_id}.json"
    rc = subprocess.run(
        [
            "pi",
            "--model",
            pi_info.pi_model,
            "--print",
            "--session-dir",
            str(pi_sessions),
            "--no-context-files",
            "--system-prompt",
            "You are a coding agent. Complete the task. Use read/edit/write/bash tools. "
            "Run verification commands after writing code.",
            "-p",
            f"@{task_file}",
            task_prompt(task_file),
        ],
        cwd=worktree,
        capture_output=False,
    ).returncode
    if rc != 0:
        return False
    phase_marker(state_dir, "dispatched", run_id)

    review_script = script_path("scripts", "adapters", "pi", "review_transcript.py")
    rc = run_script(review_script, [], state_dir, run_id)
    if rc != 0:
        return False
    phase_marker(state_dir, "transcript-reviewed", run_id)

    verdict_file = state_dir / f"pi-review_{run_id}.json"
    if verdict_file.exists():
        review_data = json.loads(verdict_file.read_text(encoding="utf-8"))
        warnings = review_data.get("warnings", [])
        critical = [w for w in warnings if w.startswith(("BLIND_WRITE", "FORBIDDEN_FILE", "NO_FILES_WRITTEN"))]
        if critical:
            return False
    phase_marker(state_dir, "transcript-verdict", run_id)
    return True


def dispatch_claude_or_local(dispatch: str, state_dir: Path, run_id: str) -> bool:
    write_json(
        state_dir / f"dispatch-result_{run_id}.json",
        {
            "dispatch": dispatch,
            "status": "pending-manual-worker",
            "reason": "Claude/local dispatch is handled by the skill instructions, not a Python subprocess.",
        },
    )
    phase_marker(state_dir, "dispatched", run_id)
    return True


def run_common_tail(worktree: Path, state_dir: Path, run_id: str) -> bool:
    verify_script = script_path("scripts", "verify-task.py")
    rc = run_script(verify_script, [], state_dir, run_id)
    if rc != 0:
        return False
    phase_marker(state_dir, "verified", run_id)

    diff = subprocess.run(
        ["git", "diff", "--stat", "--stat-width", "200"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    if diff.stdout and not any(diff.stdout.startswith(prefix) for prefix in ["0 files", "no changes", "???"]):
        simplify_script = script_path("scripts", "validate_go_contracts.py")
        rc = run_script(simplify_script, [], state_dir, run_id)
        if rc != 0:
            return False
    phase_marker(state_dir, "simplified", run_id)

    review_script = script_path("scripts", "review-passes.py")
    rc = run_script(review_script, [], state_dir, run_id)
    if rc != 0:
        return False
    phase_marker(state_dir, "reviews-passed", run_id)

    qa_script = script_path("scripts", "run-qa-verification.py")
    rc = run_script(qa_script, [], state_dir, run_id)
    if rc != 0:
        return False
    phase_marker(state_dir, "qa-passed", run_id)

    pr_script = script_path("scripts", "pr-artifacts.py")
    rc = run_script(pr_script, [], state_dir, run_id)
    if rc != 0:
        return False
    touch(state_dir / f".pr-ready_{run_id}")
    phase_marker(state_dir, "pr-ready", run_id)

    loop_script = script_path("scripts", "loop-check.py")
    run_script(loop_script, [], state_dir, run_id)
    return True


def orchestrate(args: argparse.Namespace) -> str:
    state_dir, run_id = ensure_runtime_env(args.dispatch)
    task = load_or_create_task(args, state_dir, run_id)
    if task is None:
        return "<promise>BLOCKED</promise>"

    try:
        worktree = create_worktree(args.dispatch, state_dir, run_id)
    except RuntimeError as exc:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {"phase": "worktree", "error": str(exc), "dispatch": args.dispatch},
        )
        touch(state_dir / f".blocked_{run_id}")
        return "<promise>BLOCKED</promise>"
    if args.dispatch == "pi":
        pi_info = classify_and_resolve_pi(state_dir, run_id)
        if pi_info is None or not dispatch_pi(worktree, state_dir, run_id, pi_info):
            return "<promise>BLOCKED</promise>"
    else:
        if not dispatch_claude_or_local(args.dispatch, state_dir, run_id):
            return "<promise>BLOCKED</promise>"

    if not run_common_tail(worktree, state_dir, run_id):
        return "<promise>BLOCKED</promise>"
    return "<promise>PR_READY</promise>"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    token = orchestrate(args)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
