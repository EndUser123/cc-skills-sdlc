#!/usr/bin/env python3
"""Pi-dispatched SDLC orchestrator for /go-pi.

Sequences: worktree → task → classify → resolve model → pi dispatch →
transcript review (Step 2.5) → verify → simplify → 7-pass review →
QA verification → PR artifacts → loop check.

Usage:
    python orchestrate.py [--prompt TEXT] [--plan FILE] [--tasks FILE]

All state written to $GO_STATE_DIR/*.json.
Phase markers written as $GO_STATE_DIR/.<phase>_<RUN_ID>.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Pydantic state models
# ---------------------------------------------------------------------------

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
    """Verdict from Step 2.5 subagent review."""
    verdict: str  # PASS | FAIL
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Run a Python script; touch phase marker on success."""
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


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def orchestrate(args: argparse.Namespace) -> str:
    """Run the full /go-pi pipeline. Returns a completion token."""
    state_dir = Path(os.environ["GO_STATE_DIR"])
    run_id = os.environ["RUN_ID"]
    max_attempts = int(os.environ.get("MAX_ATTEMPTS", "3"))

    state_dir.mkdir(parents=True, exist_ok=True)

    # ---- STEP 0.5: Synthesize from transcript (if no prompt) ----
    if args.prompt:
        # Write active-task directly from prompt
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
    else:
        # Use existing select-task script
        select_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/select-task.py")
        rc = run_script(select_script, [], state_dir, run_id)
        if rc != 0:
            return "<promise>BLOCKED</promise>"
        phase_marker(state_dir, "task-selected", run_id)
        task_file = state_dir / f"active-task_{run_id}.json"
        task_data = json.loads(task_file.read_text(encoding="utf-8"))

    # Write task contract
    task = TaskContract.from_active_task(task_data)
    write_json(state_dir / f"task-contract-{run_id}.json", task.raw)

    # ---- STEP 1: Worktree provisioning ----
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    worktree = Path(f"P:/worktrees/pi-task-{ts}")
    worktree.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", f"pi/pi-task-{ts}", str(worktree), "HEAD"],
        check=False,
        capture_output=True,
    )
    write_json(state_dir / f"worktree-{run_id}.json", {"worktree": str(worktree)})
    phase_marker(state_dir, "worktree", run_id)

    # ---- STEP 1.5: Classify complexity ----
    classify_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/classify_complexity.py")
    rc = run_script(classify_script, [], state_dir, run_id)
    if rc != 0:
        return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "classified", run_id)

    # ---- STEP 1.6: Resolve model ----
    resolve_script = Path("P:/packages/cc-skills-sdlc/skills/go-pi/scripts/resolve_model.py")
    rc = run_script(resolve_script, [], state_dir, run_id)
    if rc != 0:
        return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "model-resolved", run_id)
    pi_info = PiModelInfo.load(state_dir / f"pi-model_{run_id}.json")

    # ---- STEP 2: Pi dispatch ----
    dispatch_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/write_dispatch_result.py")
    subprocess.run([sys.executable, str(dispatch_script)], cwd=state_dir, capture_output=False)

    pi_sessions = state_dir / "pi-sessions"
    pi_sessions.mkdir(parents=True, exist_ok=True)
    task_file = state_dir / f"active-task_{run_id}.json"
    task_text = task_file.read_text(encoding="utf-8") if task_file.exists() else "{}"
    task_json = json.loads(task_text)
    inner = task_json.get("task", task_json)

    parts = [f"Task: {inner.get('title', '')}", f"Objective: {inner.get('objective', '')}"]
    for c in inner.get("acceptance_criteria", []):
        parts.append(f"- Accept: {c}")
    for v in inner.get("verification_commands", []):
        parts.append(f"- Verify: {v}")
    for f in inner.get("scope_in", []):
        parts.append(f"- Scope: {f}")
    for f in inner.get("forbidden_files", []):
        parts.append(f"- DO NOT modify: {f}")
    task_prompt = "\n".join(parts)

    rc = subprocess.run(
        [
            "pi", "--model", pi_info.pi_model, "--print",
            "--session-dir", str(pi_sessions),
            "--no-context-files",
            "--system-prompt",
            "You are a coding agent. Complete the task. Use read/edit/write/bash tools. "
            "Run verification commands after writing code.",
            "-p", f"@{task_file}",
            task_prompt,
        ],
        cwd=worktree,
        capture_output=False,
    ).returncode

    if rc != 0:
        return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "dispatched", run_id)

    # ---- STEP 2.5: Transcript review ----
    review_script = Path("P:/packages/cc-skills-sdlc/skills/go-pi/scripts/review_transcript.py")
    rc = run_script(review_script, [], state_dir, run_id)
    if rc != 0:
        return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "transcript-reviewed", run_id)

    # Phase B: subagent verdict (inline for now — runs as Agent subagent)
    verdict_file = state_dir / f"pi-review_{run_id}.json"
    if verdict_file.exists():
        review_data = json.loads(verdict_file.read_text(encoding="utf-8"))
        warnings = review_data.get("warnings", [])
        critical = [w for w in warnings if w.startswith(("BLIND_WRITE", "FORBIDDEN_FILE", "NO_FILES_WRITTEN"))]
        if critical:
            return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "transcript-verdict", run_id)

    # ---- STEP 3: Verify ----
    verify_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/verify-task.py")
    rc = run_script(verify_script, [], state_dir, run_id)
    if rc != 0:
        return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "verified", run_id)

    # ---- STEP 4: Simplify (skip if docs-only) ----
    diff = subprocess.run(
        ["git", "diff", "--stat", "--stat-width", "200"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    if diff.stdout and not any(
        diff.stdout.startswith(prefix) for prefix in ["0 files", "no changes", "???"]
    ):
        simplify_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/validate_go_contracts.py")
        rc = run_script(simplify_script, [], state_dir, run_id)
        if rc != 0:
            return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "simplified", run_id)

    # ---- STEP 5: 7-pass review ----
    review_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/review-passes.py")
    rc = run_script(review_script, [], state_dir, run_id)
    if rc != 0:
        return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "reviews-passed", run_id)

    # ---- STEP 5.5: QA verification ----
    qa_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/run-qa-verification.py")
    rc = run_script(qa_script, [], state_dir, run_id)
    if rc != 0:
        return "<promise>BLOCKED</promise>"
    phase_marker(state_dir, "qa-passed", run_id)

    # ---- STEP 6: PR artifacts ----
    pr_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/pr-artifacts.py")
    rc = run_script(pr_script, [], state_dir, run_id)
    touch(state_dir / f".pr-ready_{run_id}")
    phase_marker(state_dir, "pr-ready", run_id)

    # ---- STEP 7: Loop check ----
    loop_script = Path("P:/packages/cc-skills-sdlc/skills/go/scripts/loop-check.py")
    run_script(loop_script, [], state_dir, run_id)

    return "<promise>PR_READY</promise>"


def main() -> int:
    parser = argparse.ArgumentParser(description="/go-pi orchestrator")
    parser.add_argument("--prompt", help="Task description (overrides task queue)")
    parser.add_argument("--plan", help="Path to plan.md")
    parser.add_argument("--tasks", help="Path to tasks.json")
    parser.add_argument("--scope-in", nargs="*", default=[], help="Scope in patterns")
    parser.add_argument("--forbidden", nargs="*", default=[], help="Forbidden files")
    args = parser.parse_args()

    token = orchestrate(args)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())