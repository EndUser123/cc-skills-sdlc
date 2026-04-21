#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def update_run_file(run_path: Path, status: str, final_promise: str | None, notes: str | None = None) -> None:
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    payload["status"] = status
    payload["updated_at"] = now_iso()
    if final_promise is not None:
        payload["final_promise"] = final_promise
    if notes is not None:
        payload["notes"] = notes
    tmp = run_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(run_path)


def update_dispatch_result(artifact_dir: Path, run_id: str, final_status: str, wait_state: str, **kwargs: Any) -> None:
    result_path = artifact_dir / f"dispatch-result_{run_id}.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["final_status"] = final_status
    payload["orchestrator_wait_state"] = wait_state
    for key, value in kwargs.items():
        if value is not None:
            payload[key] = value
    completed_at = now_iso()
    if final_status == "completed":
        payload["completed_at"] = completed_at
    tmp = result_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(result_path)



def emit_promise(final_status: str) -> None:
    promises = {
        "completed": "TASK_COMPLETE",
        "blocked": "TASK_BLOCKED",
        "awaiting": "AWAITING_SKILL_OUTPUT",
    }
    token = promises.get(final_status, "AWAITING_SKILL_OUTPUT")
    print(f"<promise>{token}</promise>")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update dispatch-result artifact after skill outcome")
    parser.add_argument("--artifact-dir", required=True, help="Artifact directory")
    parser.add_argument("--run-id", required=True, help="GO_RUN_ID")
    parser.add_argument("--final-status", required=True, choices=["awaiting", "completed", "blocked"], help="Final status")
    parser.add_argument("--completion-summary")
    parser.add_argument("--blocking-reason")
    parser.add_argument("--next-recommended-action")
    parser.add_argument("--next-recommended-skill")
    parser.add_argument("--produced-artifacts", nargs="*", default=[])
    parser.add_argument("--notes")
    args = parser.parse_args()


    artifact_dir = Path(args.artifact_dir).resolve()
    run_id = args.run_id

    run_path = artifact_dir / f"run_{run_id}.json"
    if not run_path.exists():
        print(f"ERROR: run file not found: {run_path}", file=sys.stderr)
        return 1

    result_path = artifact_dir / f"dispatch-result_{run_id}.json"
    if not result_path.exists():
        print(f"ERROR: dispatch-result file not found: {result_path}", file=sys.stderr)
        return 1

    wait_state = "outcome-recorded"
    update_dispatch_result(
        artifact_dir, run_id,
        final_status=args.final_status,
        wait_state=wait_state,
        completion_summary=args.completion_summary,
        blocking_reason=args.blocking_reason,
        next_recommended_action=args.next_recommended_action,
        next_recommended_skill=args.next_recommended_skill,
        produced_artifacts=args.produced_artifacts if args.produced_artifacts else None,
        notes=args.notes,
    )

    if args.final_status == "completed":
        update_run_file(run_path, status="completed", final_promise="TASK_COMPLETE", notes=args.notes)
    elif args.final_status == "blocked":
        update_run_file(run_path, status="blocked", final_promise="TASK_BLOCKED", notes=args.notes)
        (artifact_dir / f".blocked_{run_id}").touch()
    else:
        update_run_file(run_path, status="dispatched", final_promise="AWAITING_SKILL_OUTPUT", notes=args.notes)

    emit_promise(args.final_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
