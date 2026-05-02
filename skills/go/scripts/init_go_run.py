#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def run_git(args: list[str], root_dir: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


@dataclass
class TaskCandidate:
    task_id: str
    title: str
    objective: str
    source: str
    source_ref: str
    scope_in: list[str]
    scope_out: list[str]
    acceptance_criteria: list[str]
    verification_hint: list[str]
    blocked_by: list[str]
    task_type: str
    candidate_routes: list[str]
    forbidden_files: list[str]
    notes: str = ""


def infer_route(task: TaskCandidate) -> tuple[str, str, str, dict[str, bool], list[str]]:
    title_blob = f"{task.title} {task.objective}".lower()
    scope_blob = " ".join(task.scope_in).lower()
    combined = f"{title_blob} {scope_blob}"

    behavior_change_expected = False
    architecture_unresolved = False
    scope_unclear = False
    cleanup_only = False
    plan_required = False

    planning_signals = [
        "plan", "architecture", "design", "approach", "strategy",
        "roadmap", "sketch", "outline", "proposal",
    ]
    design_signals = [
        "design", "spec", "interface", "api", "schema", "contract",
        "structure", "blueprint", "model", "pattern",
    ]
    refactor_signals = [
        "refactor", "cleanup", "simplify", "restructure", "deduplicate",
        "cohere", "consolidate", "unify", "extract", "rename",
    ]

    route_scores: dict[str, float] = {
        "design_v1.1": 0.0,
        "planning": 0.0,
        "refactor": 0.0,
        "code": 0.0,
    }

    for kw in planning_signals:
        if kw in combined:
            route_scores["planning"] += 1.0
    for kw in design_signals:
        if kw in combined:
            route_scores["design_v1.1"] += 1.0
    for kw in refactor_signals:
        if kw in combined:
            route_scores["refactor"] += 1.0

    behavior_change_keywords = [
        "implement", "add", "create", "build", "new feature",
        "change", "modify", "update", "introduce", "integrate",
    ]
    for kw in behavior_change_keywords:
        if kw in title_blob:
            behavior_change_expected = True
            break

    if not task.scope_in and not task.objective:
        scope_unclear = True
    elif len(task.scope_in) > 10:
        architecture_unresolved = True

    if any(kw in combined for kw in ["refactor", "cleanup", "deduplicate", "cohere"]):
        cleanup_only = True

    if "planning" in task.candidate_routes:
        plan_required = True

    winner = max(route_scores, key=route_scores.get)  # type: ignore
    if route_scores[winner] == 0.0:
        winner = "code"

    route_to_skill = {
        "planning": "/planning",
        "design_v1.1": "/design_v1.1",
        "code": "/code",
        "refactor": "/refactor",
    }

    skill = route_to_skill[winner]
    reasoning_short = [f"Inferred route={winner} from signals", f"type={task.task_type}"]
    if behavior_change_expected:
        reasoning_short.append("behavior_change_expected=true")
    if cleanup_only:
        reasoning_short.append("cleanup_only=true")

    decision_inputs = {
        "behavior_change_expected": behavior_change_expected,
        "architecture_unresolved": architecture_unresolved,
        "scope_unclear": scope_unclear,
        "cleanup_only": cleanup_only,
        "plan_required": plan_required,
    }

    return skill, winner, "routed", decision_inputs, reasoning_short


def parse_plan_md(plan_path: Path) -> list[TaskCandidate]:
    tasks: list[TaskCandidate] = []
    if not plan_path.exists():
        return tasks

    text = plan_path.read_text(encoding="utf-8")
    task_blocks = re.split(r"\n(?=\n##?\s)", text)

    for block in task_blocks:
        block = block.strip()
        if not block:
            continue

        task_match = re.match(r"^##?\s*Task\s+(\S+)\s*[:\-]?\s*(.*)", block, re.IGNORECASE)
        if not task_match:
            continue

        task_id = task_match.group(1).strip()
        remainder = task_match.group(2).strip()

        title = remainder.split("\n")[0] if remainder else task_id
        objective = ""
        scope_in: list[str] = []
        scope_out: list[str] = []
        acceptance_criteria: list[str] = []
        verification_hint: list[str] = []
        blocked_by: list[str] = []
        task_type = "unknown"
        candidate_routes: list[str] = []
        forbidden_files: list[str] = []

        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("- **Objective**:"):
                objective = re.sub(r"- \*\*Objective\*\*:\s*", "", line).strip()
            elif line.startswith("- **Scope (in)**:"):
                raw = re.sub(r"- \*\*Scope \(in\)\*\*:\s*", "", line).strip()
                scope_in = [s.strip() for s in raw.split(",") if s.strip()]
            elif line.startswith("- **Scope (out)**:"):
                raw = re.sub(r"- \*\*Scope \(out\)\*\*:\s*", "", line).strip()
                scope_out = [s.strip() for s in raw.split(",") if s.strip()]
            elif line.startswith("- **Acceptance**:"):
                raw = re.sub(r"- \*\*Acceptance\*\*:\s*", "", line).strip()
                acceptance_criteria = [s.strip() for s in raw.split(";") if s.strip()]
            elif line.startswith("- **Verification**:"):
                raw = re.sub(r"- \*\*Verification\*\*:\s*", "", line).strip()
                verification_hint = [s.strip() for s in raw.split(";") if s.strip()]
            elif line.startswith("- **Blocked by**:"):
                raw = re.sub(r"- \*\*Blocked by\*\*:\s*", "", line).strip()
                blocked_by = [s.strip() for s in raw.split(",") if s.strip()]
            elif line.startswith("- **Type**:"):
                task_type = re.sub(r"- \*\*Type\*\*:\s*", "", line).strip().lower()
            elif line.startswith("- **Routes**:"):
                raw = re.sub(r"- \*\*Routes\*\*:\s*", "", line).strip()
                candidate_routes = [r.strip() for r in raw.split(",") if r.strip()]
            elif line.startswith("- **Forbidden**:"):
                raw = re.sub(r"- \*\*Forbidden\*\*:\s*", "", line).strip()
                forbidden_files = [f.strip() for f in raw.split(",") if f.strip()]

        if not objective:
            objective = title

        tasks.append(
            TaskCandidate(
                task_id=task_id,
                title=title,
                objective=objective,
                source="plan.md",
                source_ref=str(plan_path),
                scope_in=scope_in,
                scope_out=scope_out,
                acceptance_criteria=acceptance_criteria,
                verification_hint=verification_hint,
                blocked_by=blocked_by,
                task_type=task_type,
                candidate_routes=candidate_routes,
                forbidden_files=forbidden_files,
            )
        )

    return tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a /go thin-router run")
    parser.add_argument("--root-dir", required=True, help="Root of the repo")
    parser.add_argument("--terminal-id", required=True, help="Terminal ID")
    parser.add_argument("--go-run-id", required=True, help="GO_RUN_ID")
    parser.add_argument("--artifact-dir", required=True, help="Artifact output directory")
    parser.add_argument("--task-id", help="Explicit task ID")
    parser.add_argument("--title", help="Explicit task title")
    parser.add_argument("--objective", help="Explicit task objective")
    parser.add_argument("--scope-in", nargs="*", default=[], help="Allowed file patterns")
    parser.add_argument("--scope-out", nargs="*", default=[], help="Forbidden file patterns")
    parser.add_argument("--task-type", default="unknown", help="Task type (plan, design, code, refactor)")
    parser.add_argument("--allowed-routes", nargs="*", default=[], help="Candidate routes")
    parser.add_argument("--forbidden-files", nargs="*", default=[], help="Forbidden files")
    parser.add_argument("--plan-md", help="Path to plan.md (fallback task source)")
    return parser.parse_args()


def build_explicit_task(args: argparse.Namespace) -> TaskCandidate:
    task_id = args.task_id or "explicit"
    return TaskCandidate(
        task_id=task_id,
        title=args.title or "Explicit task",
        objective=args.objective or "",
        source="cli",
        source_ref="command-line",
        scope_in=args.scope_in,
        scope_out=args.scope_out,
        acceptance_criteria=[],
        verification_hint=[],
        blocked_by=[],
        task_type=args.task_type,
        candidate_routes=args.allowed_routes,
        forbidden_files=args.forbidden_files,
    )


def main() -> int:
    args = parse_args()
    root = Path(args.root_dir).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    go_run_id = args.go_run_id
    terminal_id = args.terminal_id

    if args.task_id and args.objective:
        task = build_explicit_task(args)
    else:
        plan_md_path = args.plan_md or str(root / "plan.md")
        candidates = parse_plan_md(Path(plan_md_path))
        if not candidates:
            print(f"ERROR: no tasks found in {plan_md_path}", file=sys.stderr)
            return 1
        task = candidates[0]

    skill, route, dispatch_status, decision_inputs, reasoning_short = infer_route(task)

    created_at = now_iso()

    run_payload: dict[str, Any] = {
        "schema_version": "go.run.v1",
        "go_run_id": go_run_id,
        "terminal_id": terminal_id,
        "status": "dispatched",
        "created_at": created_at,
        "skill_version": "3.1.0",
        "orchestrator_role": "thin-router",
        "artifact_dir": str(artifact_dir),
        "active_route": route,
        "final_promise": "GO_DISPATCHED",
    }

    selected_task_payload: dict[str, Any] = {
        "schema_version": "go.selected-task.v1",
        "go_run_id": go_run_id,
        "terminal_id": terminal_id,
        "task_id": task.task_id,
        "title": task.title,
        "objective": task.objective,
        "scope": {"in": task.scope_in, "out": task.scope_out},
        "source": task.source,
        "source_ref": task.source_ref,
        "allowed_files": task.scope_in,
        "forbidden_files": task.forbidden_files,
        "acceptance_criteria": task.acceptance_criteria,
        "verification_hint": task.verification_hint,
        "selected_at": created_at,
        "status": "selected",
        "task_type": task.task_type,
        "candidate_routes": task.candidate_routes,
    }

    dispatch_decision_payload: dict[str, Any] = {
        "schema_version": "go.dispatch-decision.v1",
        "go_run_id": go_run_id,
        "terminal_id": terminal_id,
        "task_id": task.task_id,
        "route": route,
        "delegated_skill": skill,
        "reasoning_short": reasoning_short,
        "blocking_preconditions": task.blocked_by,
        "decision_inputs": decision_inputs,
        "dispatch_status": dispatch_status,
        "decided_at": created_at,
    }

    dispatch_result_payload: dict[str, Any] = {
        "schema_version": "go.dispatch-result.v1",
        "go_run_id": go_run_id,
        "terminal_id": terminal_id,
        "task_id": task.task_id,
        "route": route,
        "delegated_skill": skill,
        "dispatch_status": "dispatched",
        "delegated_at": created_at,
        "expected_outcome_type": "unknown",
        "orchestrator_wait_state": "awaiting-skill-outcome",
        "final_status": "awaiting",
    }

    write_json(artifact_dir / f"run_{go_run_id}.json", run_payload)
    write_json(artifact_dir / f"selected-task_{go_run_id}.json", selected_task_payload)
    write_json(artifact_dir / f"dispatch-decision_{go_run_id}.json", dispatch_decision_payload)
    write_json(artifact_dir / f"dispatch-result_{go_run_id}.json", dispatch_result_payload)

    next_action = f"Delegated to {skill} for task {task.task_id}; waiting for outcome..."
    write_text(artifact_dir / f"next-action_{go_run_id}.md", next_action)

    (artifact_dir / f".dispatched_{go_run_id}").touch()

    print(f"Run initialized: {go_run_id}")
    print(f"Task: {task.task_id} -> {route} ({skill})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
