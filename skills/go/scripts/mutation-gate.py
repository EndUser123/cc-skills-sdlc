#!/usr/bin/env python3
"""Run /go mutation gate before PR readiness."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILLS_DIR = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = SKILLS_DIR.parent
for path in (SKILLS_DIR / "__lib", SKILLS_DIR / "t"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mutation_config import QualityGatesError, load_quality_gates  # type: ignore  # noqa: E402
from modes.mutation_mode import run_mutation_for_module  # type: ignore  # noqa: E402

PASSING_STATUSES = {"passed", "waived"}
BLOCKING_STATUSES = {"failed", "timeout", "blocked", "skipped"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_modules(raw: str) -> list[str]:
    modules: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        module = chunk.strip()
        if module and module not in modules:
            modules.append(module)
    return modules


def module_to_path_fragment(module: str) -> str:
    return module.replace(".", "/")


def path_matches_module(path: str, module: str) -> bool:
    normalized = path.replace("\\", "/")
    module_file = module_to_path_fragment(module) + ".py"
    return normalized == module_file or normalized.endswith("/" + module_file)


def changed_files(worktree: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def select_modules(gates: Any, worktree: Path) -> list[str]:
    explicit = parse_modules(os.environ.get("GO_MUTATION_MODULES", ""))
    if explicit:
        return explicit
    if gates is None:
        return []

    changed = changed_files(worktree)
    if not changed:
        return []

    selected: list[str] = []
    for module in gates.list_critical_modules():
        if any(path_matches_module(path, module) for path in changed):
            selected.append(module)
    return selected


def result_to_dict(result: Any, gates: Any | None) -> dict[str, Any]:
    data = asdict(result) if is_dataclass(result) else dict(vars(result))
    module = data.get("module", "")
    gate = gates.get_module_gate(module) if gates is not None else None
    return {
        "module": module,
        "tier": getattr(gate, "tier", "critical" if module else "best-effort"),
        "target_score": data.get("target_score"),
        "mutation_score": data.get("mutation_score"),
        "killed": int(data.get("killed") or 0),
        "survived": int(data.get("survived") or 0),
        "skipped": int(data.get("skipped") or 0),
        "timeout": int(data.get("timeout") or 0),
        "status": data.get("status", "blocked"),
        "receipt_path": data.get("receipt_path", ""),
    }


def load_task_id(state_dir: Path, run_id: str) -> str:
    task_file = state_dir / f"active-task_{run_id}.json"
    if not task_file.exists():
        return "unknown"
    try:
        payload = json.loads(task_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "unknown"
    task = payload.get("task", payload)
    return task.get("id", "unknown")


def write_verification_result(
    state_dir: Path,
    run_id: str,
    terminal_id: str,
    status: str,
    mutation: dict[str, Any],
) -> None:
    path = state_dir / f"verification-result_{run_id}.json"
    gate_artifact = state_dir / f"mutation-gate-{run_id}.json"
    if not mutation.get("receipt_path"):
        mutation["receipt_path"] = str(gate_artifact)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
    else:
        payload = {}

    payload.update(
        {
            "run_id": run_id,
            "terminal_id": terminal_id,
            "task_id": payload.get("task_id") or load_task_id(state_dir, run_id),
            "status": status,
            "pr_ready": False,
            "mutation": mutation,
            "generated_at": now_iso(),
        }
    )
    artifact_paths = payload.setdefault("artifact_paths", {})
    artifact_paths["mutation_gate"] = str(gate_artifact)
    write_json(path, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run /go mutation gate")
    parser.parse_args(argv)

    run_id = os.environ.get("RUN_ID") or os.environ.get("GO_RUN_ID", "")
    if not run_id:
        print("ERROR: RUN_ID not set", file=sys.stderr)
        return 2
    state_dir = Path(os.environ.get("GO_STATE_DIR", Path.cwd())).resolve()
    worktree = Path(os.environ.get("WORKTREE", Path.cwd())).resolve()
    terminal_id = os.environ.get("TERMINAL_ID") or os.environ.get("CLAUDE_TERMINAL_ID") or "unknown"
    state_dir.mkdir(parents=True, exist_ok=True)

    try:
        gates = load_quality_gates()
    except QualityGatesError as exc:
        gates = None
        skip_reason = str(exc)
    else:
        skip_reason = "no_mutation_targets"

    modules = select_modules(gates, worktree)
    if not modules:
        mutation = {
            "module": "(none)",
            "tier": "best-effort",
            "target_score": None,
            "mutation_score": None,
            "killed": 0,
            "survived": 0,
            "skipped": 0,
            "timeout": 0,
            "status": "not-run",
            "receipt_path": "",
        }
        payload = {
            "schema_version": "go.mutation-gate.v1",
            "run_id": run_id,
            "status": "skipped",
            "reason": "no_mutation_targets",
            "detail": skip_reason,
            "modules": [],
            "generated_at": now_iso(),
        }
        write_json(state_dir / f"mutation-gate-{run_id}.json", payload)
        write_verification_result(state_dir, run_id, terminal_id, "passed", mutation)
        print("[mutation-gate] SKIP: no mutation targets", file=sys.stderr)
        return 0

    results = [result_to_dict(run_mutation_for_module(module, project_root=worktree), gates) for module in modules]
    blocking = [result for result in results if result.get("status") in BLOCKING_STATUSES]
    overall = "failed" if blocking else "waived" if any(r.get("status") == "waived" for r in results) else "passed"
    should_block = bool(blocking and (gates is None or getattr(gates, "block_pr_on_failure", True)))

    payload = {
        "schema_version": "go.mutation-gate.v1",
        "run_id": run_id,
        "status": overall,
        "modules": results,
        "generated_at": now_iso(),
    }
    if blocking:
        payload["blocking_modules"] = [result["module"] for result in blocking]
    write_json(state_dir / f"mutation-gate-{run_id}.json", payload)

    mutation = blocking[0] if blocking else results[0]
    write_verification_result(state_dir, run_id, terminal_id, "failed" if should_block else overall, mutation)

    if should_block:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "mutation",
                "reason_code": "mutation_failed",
                "modules": [result["module"] for result in blocking],
            },
        )
        (state_dir / f".blocked_{run_id}").touch()
        print("[mutation-gate] BLOCK: mutation gate failed", file=sys.stderr)
        return 1

    print(f"[mutation-gate] {overall.upper()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
