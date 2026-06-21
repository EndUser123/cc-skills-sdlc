#!/usr/bin/env python3
"""Canonical /go SDLC orchestrator with selectable worker dispatch.

Default dispatch is pi. Override with:
    python orchestrate.py --dispatch claude --prompt "..."
    GO_DISPATCH=claude python orchestrate.py --prompt "..."
"""

from __future__ import annotations

import argparse
import importlib.util
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


def load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def now_utc_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_script(
    script: Path,
    args: list[str],
    state_dir: Path,
    run_id: str,
    cwd: Path | None = None,
) -> int:
    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["GO_RUN_ID"] = run_id
    env["GO_STATE_DIR"] = str(state_dir.resolve())
    if cwd is not None:
        env["WORKTREE"] = str(cwd.resolve())
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd or state_dir,
        env=env,
        capture_output=False,
    )
    return result.returncode


def phase_marker(state_dir: Path, phase: str, run_id: str) -> Path:
    p = state_dir / f".{phase}_{run_id}"
    touch(p)
    return p


def write_current_run(state_dir: Path, run_id: str, status: str, dispatch: str) -> None:
    terminal_id = os.environ.get("CLAUDE_TERMINAL_ID") or os.environ.get("TERMINAL_ID", "default")
    payload = {
        "schema_version": "go.current-run.v1",
        "run_id": run_id,
        "terminal_id": terminal_id,
        "go_state_dir": str(state_dir.resolve()),
        "dispatch": dispatch,
        "status": status,
        "updated_at": now_iso(),
    }
    write_json(state_dir / "current-run.json", payload)
    write_json(state_dir / f"current-run_{terminal_id}.json", payload)


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


def default_verification_commands() -> list[str]:
    raw = os.environ.get("GO_DEFAULT_VERIFICATION_COMMANDS", "python -m pytest -q")
    return [part.strip() for part in raw.split(";") if part.strip()]


def _heading_or_stem(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title[:80]
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or "Plan task"


def create_plan_task(args: argparse.Namespace, state_dir: Path, run_id: str) -> TaskContract | None:
    plan_path = Path(args.plan).expanduser().resolve()
    if not plan_path.exists():
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "task-selection",
                "reason_code": "plan_file_not_found",
                "path": str(plan_path),
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return None

    plan_text = plan_path.read_text(encoding="utf-8")
    title = _heading_or_stem(plan_path, plan_text)
    terminal_id = os.environ.get("TERMINAL_ID", "default")
    selected_at = now_utc_z()
    task_data: dict[str, Any] = {
        "run_id": run_id,
        "terminal_id": terminal_id,
        "selected_at": selected_at,
        "source": "plan-md",
        "source_ref": str(plan_path),
        "task": {
            "id": f"plan-{run_id[:8]}",
            "title": title,
            "objective": plan_text.strip() or title,
            "status": "selected",
            "priority": "P1",
            "scope_in": args.scope_in or [],
            "scope_out": [],
            "acceptance_criteria": [line.strip("- ").strip() for line in plan_text.splitlines() if line.strip().startswith("- ")],
            "verification_commands": default_verification_commands(),
            "forbidden_files": args.forbidden or [],
            "task_type": "implementation",
        },
    }
    write_json(state_dir / f"active-task_{run_id}.json", task_data)
    phase_marker(state_dir, "task-selected", run_id)
    return TaskContract.from_active_task(task_data)


def ensure_runtime_env(dispatch: str) -> tuple[Path, str]:
    terminal_id = os.environ.get("TERMINAL_ID", "default")
    os.environ["TERMINAL_ID"] = terminal_id
    os.environ.setdefault("CLAUDE_TERMINAL_ID", terminal_id)
    run_id = os.environ.get("RUN_ID") or os.environ.get("GO_RUN_ID") or str(uuid.uuid4())
    os.environ["RUN_ID"] = run_id
    os.environ["GO_RUN_ID"] = run_id
    os.environ.setdefault("MAX_ATTEMPTS", "3")
    default_state_dir = Path.cwd() / ".claude" / ".artifacts" / terminal_id / "go"
    state_dir = Path(os.environ.get("GO_STATE_DIR", str(default_state_dir))).resolve()
    os.environ["GO_STATE_DIR"] = str(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir, run_id


def load_or_create_task(args: argparse.Namespace, state_dir: Path, run_id: str) -> TaskContract | None:
    if args.prompt:
        explicit_verification = os.environ.get("GO_DEFAULT_VERIFICATION_COMMANDS", "").strip()
        verification_commands = default_verification_commands()
        if os.environ.get("GO_REQUIRE_EXPLICIT_VERIFICATION") == "1" and not explicit_verification:
            write_json(
                state_dir / f"blocked_{run_id}.json",
                {
                    "phase": "task-selection",
                    "reason_code": "missing_verification_commands",
                    "message": "Prompt task requires explicit verification commands before dispatch.",
                },
            )
            touch(state_dir / f".blocked_{run_id}")
            return None
        selected_at = now_utc_z()
        terminal_id = os.environ.get("TERMINAL_ID", "default")
        task_data: dict[str, Any] = {
            "run_id": run_id,
            "terminal_id": terminal_id,
            "selected_at": selected_at,
            "source": "cli",
            "source_ref": "cli",
            "task": {
                "id": f"prompt-{run_id[:8]}",
                "title": args.prompt[:60],
                "objective": args.prompt,
                "status": "selected",
                "priority": "P1",
                "scope_in": args.scope_in or [],
                "scope_out": [],
                "acceptance_criteria": [],
                "verification_commands": verification_commands,
                "forbidden_files": args.forbidden or [],
                "task_type": "implementation",
            },
        }
        write_json(state_dir / f"active-task_{run_id}.json", task_data)
        phase_marker(state_dir, "task-selected", run_id)
    elif args.plan:
        task = create_plan_task(args, state_dir, run_id)
        if task is None:
            return None
        write_json(state_dir / f"task-contract-{run_id}.json", task.raw)
        return task
    else:
        select_script = script_path("scripts", "select-task.py")
        if args.tasks:
            os.environ["GO_TASKS_FILE"] = str(Path(args.tasks).expanduser().resolve())
        else:
            os.environ.setdefault("GO_TASKS_FILE", str((Path.cwd() / ".claude" / "tasks" / "tasks.json").resolve()))
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
    run_suffix_source = run_id[4:] if run_id.startswith("run-") else run_id
    suffix = "".join(ch for ch in run_suffix_source if ch.isalnum())[:8] or uuid.uuid4().hex[:8]
    root = Path("P:/worktrees")
    worktree = root / f"{prefix}-task-{ts}-{suffix}"
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "worktree", "add", "-b", f"{prefix}/{prefix}-task-{ts}-{suffix}", str(worktree), "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"git worktree add failed for {worktree}: {detail}")
    write_json(state_dir / f"worktree-{run_id}.json", {"worktree": str(worktree)})
    phase_marker(state_dir, "worktree-ready", run_id)
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
    task_file = state_dir / f"active-task_{run_id}.json"
    harness = load_script_module(
        "go_pi_harness_runtime",
        script_path("scripts", "adapters", "pi", "harness.py"),
    )
    result = harness.run_pi_harness(
        worktree=worktree,
        state_dir=state_dir,
        run_id=run_id,
        pi_model=pi_info.pi_model,
        prompt=task_prompt(task_file),
    )
    if result.exit_code != 0:
        return False
    phase_marker(state_dir, "dispatched", run_id)

    review_script = script_path("scripts", "adapters", "pi", "review_transcript.py")
    rc = run_script(review_script, [], state_dir, run_id)
    if rc != 0:
        return False
    phase_marker(state_dir, "transcript-reviewed", run_id)

    verdict_file = state_dir / f"pi-review_{run_id}.json"
    critical: list[str] = []
    if verdict_file.exists():
        review_data = json.loads(verdict_file.read_text(encoding="utf-8"))
        warnings = review_data.get("warnings", [])
        critical = [w for w in warnings if w.startswith(("BLIND_WRITE", "FORBIDDEN_FILE", "NO_FILES_WRITTEN"))]
    if critical:
        return False
    phase_marker(state_dir, "transcript-verdict", run_id)
    phase_marker(state_dir, "coded", run_id)
    return True


def dispatch_claude(state_dir: Path, run_id: str) -> bool:
    write_json(
        state_dir / f"dispatch-result_{run_id}.json",
        {
            "dispatch": "claude",
            "status": "unsupported-automated-dispatch",
            "reason": "Claude dispatch has no non-interactive worker implementation in this orchestrator.",
        },
    )
    touch(state_dir / f".blocked_{run_id}")
    return False


def dispatch_local(state_dir: Path, run_id: str) -> bool:
    # Check for local LLM dispatch path
    local_llm = os.environ.get("GO_LOCAL_LLM", "").strip()
    if local_llm:
        # Dispatch to local LLM (LM Studio, Ollama, vLLM)
        dispatch_script = script_path("scripts", "adapters", "local", "dispatch_local.py")
        rc = run_script(dispatch_script, [], state_dir, run_id, cwd=Path.cwd())
        if rc != 0:
            write_json(
                state_dir / f"dispatch-result_{run_id}.json",
                {
                    "dispatch": "local",
                    "status": "failed",
                    "reason": f"Local LLM dispatch failed: {local_llm}",
                },
            )
            return False
        phase_marker(state_dir, "worktree-ready", run_id)
        phase_marker(state_dir, "dispatched", run_id)
        phase_marker(state_dir, "coded", run_id)
        return True

    # Default: skipped worker (verify current checkout)
    write_json(
        state_dir / f"dispatch-result_{run_id}.json",
        {
            "dispatch": "local",
            "status": "skipped-worker",
            "reason": "Local dispatch performs no worker step and runs verification against the current checkout.",
        },
    )
    phase_marker(state_dir, "worktree-ready", run_id)
    phase_marker(state_dir, "dispatched", run_id)
    phase_marker(state_dir, "coded", run_id)
    return True


def run_simplify_gate(worktree: Path, state_dir: Path, run_id: str, diff_stat: str) -> bool:
    status_path = state_dir / f"simplify-status_{run_id}.md"
    simplify_command = os.environ.get("GO_SIMPLIFY_COMMAND", "").strip()
    if not simplify_command:
        status_path.write_text(
            "\n".join(
                [
                    "# Simplify Gate",
                    "",
                    "Status: SKIPPED",
                    "Reason: GO_SIMPLIFY_COMMAND is not set.",
                    "",
                    "Diff stat:",
                    "```",
                    diff_stat.rstrip(),
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return True

    result = subprocess.run(
        simplify_command,
        cwd=worktree,
        shell=True,
        capture_output=True,
        text=True,
    )
    status_path.write_text(
        "\n".join(
            [
                "# Simplify Gate",
                "",
                f"Status: {'PASS' if result.returncode == 0 else 'FAIL'}",
                f"Command: {simplify_command}",
                f"Exit code: {result.returncode}",
                "",
                "Stdout:",
                "```",
                (result.stdout or "").rstrip(),
                "```",
                "",
                "Stderr:",
                "```",
                (result.stderr or "").rstrip(),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if result.returncode != 0:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "simplify",
                "reason_code": "simplify_command_failed",
                "command": simplify_command,
                "exit_code": result.returncode,
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return False
    return True


def run_common_tail(worktree: Path, state_dir: Path, run_id: str) -> bool:
    # Step 1: Run verification (verify-task.py)
    verify_script = script_path("scripts", "verify-task.py")
    rc = run_script(verify_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "verified", run_id)

    # Step 2: Get diff for simplify gate
    diff = subprocess.run(
        ["git", "diff", "--stat", "--stat-width", "200"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    if diff.returncode != 0:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "diff",
                "reason_code": "git_diff_failed",
                "stderr": (diff.stderr or diff.stdout or "").strip(),
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return False

    # Step 3: Run simplify gate (if there are changes)
    if diff.stdout and not any(diff.stdout.startswith(prefix) for prefix in ["0 files", "no changes", "???"]):
        if not run_simplify_gate(worktree, state_dir, run_id, diff.stdout):
            return False
    phase_marker(state_dir, "simplified", run_id)

    # Step 4: Run refactor review (between simplify and regressions)
    refactor_script = script_path("scripts", "refactor-review.py")
    rc = run_script(refactor_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "refactor-reviewed", run_id)

    # Step 5: Run regression tests (before verify-task)
    regression_script = script_path("scripts", "regression-runner.py")
    rc = run_script(regression_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "regression-passed", run_id)

    # Step 6: Run code reviews
    review_script = script_path("scripts", "review-passes.py")
    rc = run_script(review_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "reviews-passed", run_id)

    # Step 7: Run QA verification
    qa_script = script_path("scripts", "run-qa-verification.py")
    qa_args = ["--dry-run"] if os.environ.get("GO_QA_DRY_RUN", "").strip() == "1" else []
    rc = run_script(qa_script, qa_args, state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "qa-passed", run_id)

    # Step 8: Run mutation gate
    mutation_script = script_path("scripts", "mutation-gate.py")
    rc = run_script(mutation_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "mutation-passed", run_id)

    # Step 9: Run coverage gate (before pr-artifacts)
    coverage_script = script_path("scripts", "coverage-gate.py")
    rc = run_script(coverage_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "coverage-passed", run_id)

    # Step 10: Generate PR artifacts
    pr_script = script_path("scripts", "pr-artifacts.py")
    rc = run_script(pr_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    touch(state_dir / f".pr-ready_{run_id}")
    phase_marker(state_dir, "pr-ready", run_id)

    # Step 11: Run loop check (non-blocking)
    loop_script = script_path("scripts", "loop-check.py")
    run_script(loop_script, [], state_dir, run_id, cwd=worktree)
    return True


def orchestrate(args: argparse.Namespace) -> str:
    state_dir, run_id = ensure_runtime_env(args.dispatch)
    write_current_run(state_dir, run_id, "running", args.dispatch)

    def finish(status: str) -> str:
        write_current_run(state_dir, run_id, status, args.dispatch)
        if status == "pr_ready":
            return "<promise>PR_READY</promise>"
        return "<promise>BLOCKED</promise>"

    task = load_or_create_task(args, state_dir, run_id)
    if task is None:
        return finish("blocked")

    if args.dispatch == "local":
        if not dispatch_local(state_dir, run_id):
            return finish("blocked")
        if not run_common_tail(Path.cwd(), state_dir, run_id):
            return finish("blocked")
        return finish("pr_ready")

    if args.dispatch == "claude":
        if not dispatch_claude(state_dir, run_id):
            return finish("blocked")

    try:
        worktree = create_worktree(args.dispatch, state_dir, run_id)
    except RuntimeError as exc:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {"phase": "worktree", "error": str(exc), "dispatch": args.dispatch},
        )
        touch(state_dir / f".blocked_{run_id}")
        return finish("blocked")
    if args.dispatch == "pi":
        pi_info = classify_and_resolve_pi(state_dir, run_id)
        if pi_info is None or not dispatch_pi(worktree, state_dir, run_id, pi_info):
            return finish("blocked")

    if not run_common_tail(worktree, state_dir, run_id):
        return finish("blocked")
    return finish("pr_ready")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    token = orchestrate(args)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
