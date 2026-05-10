#!/usr/bin/env python3
"""Classify task complexity and select model for Bifrost routing.

Reads active-task JSON, computes complexity tier from heuristic signals,
and outputs a model-selection JSON for /go Step 2 dispatch.

Tier map:
  T1-T3 (standard) -> M27
  T4    (architectural) -> GLM-5.1

Override: GO_MODEL_OVERRIDE env var bypasses classification entirely.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any


TIER_MODEL_MAP: dict[str, str] = {
    "T1": "M27",
    "T2": "M27",
    "T3": "M27",
    "T4": "GLM-5.1",
}

# Per-task-type signal subsets prevent config tasks from scoring high
# on irrelevant signals (e.g. forbidden_files count).
SIGNAL_PROFILES: dict[str, list[str]] = {
    "config": ["verification"],
    "implementation": ["file_spread", "criteria", "verification", "sensitivity"],
    "refactor": ["file_spread", "criteria", "verification", "sensitivity"],
    "design": ["file_spread", "criteria", "verification", "sensitivity", "task_type"],
    "planning": ["file_spread", "criteria", "verification", "sensitivity", "task_type"],
}

TASK_TYPE_WEIGHT: dict[str, int] = {
    "config": 1,
    "implementation": 2,
    "refactor": 2,
    "design": 3,
    "planning": 3,
}


def _bucket(value: int, thresholds: list[int]) -> int:
    """Map value to 1/2/3 using [low_max, mid_max] thresholds."""
    if value <= thresholds[0]:
        return 1
    if value <= thresholds[1]:
        return 2
    return 3


def _task_type_weight(task_type: str) -> int:
    return TASK_TYPE_WEIGHT.get(task_type, 2)


def _score_to_tier(score: int, max_possible: int) -> str:
    """Normalize score against max possible, map to tier.

    Falsification: if max_possible <= 0, this would divide by zero.
    Guarded by requiring at least one signal.
    """
    if max_possible <= 0:
        return "T1"
    ratio = score / max_possible
    if ratio <= 0.5:
        return "T1"
    if ratio <= 0.7:
        return "T2"
    if ratio <= 0.85:
        return "T3"
    return "T4"


def _is_decisive(signals: dict[str, int]) -> bool:
    """High confidence when signals agree (no 1+3 spread)."""
    vals = list(signals.values())
    return max(vals) - min(vals) <= 1


def classify(task: dict[str, Any]) -> dict[str, Any]:
    """Classify a task and return model selection.

    Uses pre-set estimated_complexity if available, otherwise computes
    from heuristic signals aligned to the active-task schema fields.
    """
    task_type = task.get("task_type", "implementation")
    estimated = task.get("estimated_complexity")

    # Fast path: use pre-set complexity if available
    if estimated == "high":
        return _result("T4", {"preset": "high"})
    if estimated == "low":
        return _result("T1", {"preset": "low"})

    # Compute from signals
    profile = SIGNAL_PROFILES.get(task_type, SIGNAL_PROFILES["implementation"])
    signals: dict[str, int] = {}

    if "file_spread" in profile:
        signals["file_spread"] = _bucket(len(task.get("scope_in", [])), [1, 4])
    if "criteria" in profile:
        signals["criteria"] = _bucket(len(task.get("acceptance_criteria", [])), [2, 5])
    if "verification" in profile:
        signals["verification"] = _bucket(len(task.get("verification_commands", [])), [1, 3])
    if "sensitivity" in profile:
        signals["sensitivity"] = _bucket(len(task.get("forbidden_files", [])), [0, 2])
    if "task_type" in profile:
        signals["task_type"] = _task_type_weight(task_type)

    if not signals:
        return _result("T1", {})

    score = sum(signals.values())
    max_possible = len(signals) * 3
    tier = _score_to_tier(score, max_possible)

    # Only design/planning tasks can reach T4 (GLM-5.1).
    # Implementation/refactor/config cap at T3 (M27).
    if task_type in ("implementation", "refactor", "config") and tier == "T4":
        tier = "T3"

    confidence = "high" if _is_decisive(signals) else "medium"

    return {
        "tier": tier,
        "model": TIER_MODEL_MAP[tier],
        "confidence": confidence,
        "score": score,
        "max_possible": max_possible,
        "signals": signals,
        "task_type": task_type,
    }


def _result(tier: str, signals: dict[str, int]) -> dict[str, Any]:
    return {
        "tier": tier,
        "model": TIER_MODEL_MAP[tier],
        "confidence": "high",
        "score": 0,
        "max_possible": 0,
        "signals": signals,
        "task_type": "",
    }


def main() -> None:
    override = os.environ.get("GO_MODEL_OVERRIDE")
    if override:
        result = {"tier": "override", "model": override, "confidence": "high",
                  "score": 0, "max_possible": 0, "signals": {"override": True}, "task_type": ""}
        _write_output(result)
        return

    task_file = pathlib.Path(os.environ.get("GO_TASK_FILE", ""))
    if not task_file.exists():
        # Try active-task pattern
        state_dir = pathlib.Path(os.environ.get("GO_STATE_DIR", ""))
        run_id = os.environ.get("RUN_ID", "")
        active = state_dir / f"active-task_{run_id}.json"
        if active.exists():
            task_file = active
        else:
            print("ERROR: no task file found", file=sys.stderr)
            sys.exit(1)

    data = json.loads(task_file.read_text(encoding="utf-8"))
    task = data.get("task", data)  # unwrap active-task envelope or use raw
    result = classify(task)
    _write_output(result)


def _write_output(result: dict[str, Any]) -> None:
    state_dir = pathlib.Path(os.environ.get("GO_STATE_DIR", ""))
    run_id = os.environ.get("RUN_ID", "unknown")
    out = state_dir / f"model-selection_{run_id}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(f"Classified: {result['tier']} -> {result['model']} (confidence: {result['confidence']})")


if __name__ == "__main__":
    main()
