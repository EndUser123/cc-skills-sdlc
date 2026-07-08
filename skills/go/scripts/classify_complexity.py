#!/usr/bin/env python3
"""Classify task complexity and select model for Bifrost routing.

Reads active-task JSON, computes complexity tier from heuristic signals,
and outputs a model-selection JSON for /go Step 2 dispatch.

Tier map:
  T1-T3 (standard) -> M3
  T4    (architectural) -> GLM-5.2

Override: GO_MODEL_OVERRIDE env var bypasses classification entirely.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from typing import Any


TIER_MODEL_MAP: dict[str, str] = {
    "T0": "LOCAL_ORNITH",
    "T1": "OPENCODE_DEEPSEEK",
    "T2": "OPENCODE_DEEPSEEK",
    "T3": "OPENCODE_DEEPSEEK",
    "T4": "GLM-5.2",
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

# TASK-004: pi-default-flip gate. When "advisory", the dispatcher logs the
# model_affinity recommendation but routes per existing rules. Flipping to
# "default_pi" is gated on test_pi_suitability_corpus.py passing
# precision >= 0.7 AND recall >= 0.6 over the >= 20-prompt corpus. Do NOT
# flip without re-running the corpus test.
PI_DEFAULT_FLIP = "advisory"

# pi has prompt-size transport limits (#914); above this the pi path is a
# poor fit regardless of intent. Conservative ceiling; adjust with evidence.
_PI_PROMPT_MAX_CHARS = 8000

# Concreteness signals that distinguish a bounded code edit (pi-suitable)
# from a plan-handoff pointer or a design/orchestration ask. The intent
# classifier marks plan-handoffs as `implement` upstream; without a
# concrete-target check the advisor would over-recommend pi on bare
# "/go the plan" / "/go execute phase 1" prompts. .md is intentionally
# excluded — plan files and SKILL.md are contract/spec surfaces, not code.
_PI_CODE_EXT = re.compile(r"\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|sh|toml|yaml|yml|json)\b", re.I)
_PI_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_PI_IMPL_VERB = re.compile(r"\b(?:implement|refactor|fix|add|write|update|extend|extract|introduce)", re.I)
_PI_TASK_TAG = re.compile(r"\bTASK-\d+\b", re.I)
_PI_CODE_UNIT = re.compile(r"\b(?:regression test|test|function|method|class|module|phase)\b", re.I)


def _has_concrete_code_target(prompt: str) -> bool:
    """True when the prompt names a specific code artifact or unit of work.

    Plan-handoff pointers ("the plan", "execute phase 1", "TASK-NNNN via queue")
    and design/orchestration asks lack this signal — they are not pi-bound from
    the prompt alone, so the advisor returns neutral (route per existing rules).
    """
    if _PI_CODE_EXT.search(prompt):
        return True
    if _PI_SNAKE.search(prompt):
        return True
    if _PI_TASK_TAG.search(prompt) and _PI_IMPL_VERB.search(prompt):
        return True
    if _PI_IMPL_VERB.search(prompt) and _PI_CODE_UNIT.search(prompt):
        return True
    return False




# T0 local-eligibility: tasks safe enough to try the local model first.
# Conservative: only read-only deterministic tasks with small scope.
_LOCAL_INELIGIBLE_TASK_TYPES = frozenset({"hook", "gate", "cache", "state", "migration"})
_LOCAL_INELIGIBLE_INTENTS = frozenset({"decide", "investigate", "validate", "design", "mixed"})
_LOCAL_MAX_SCOPE = 3  # files
_LOCAL_MAX_CRITERIA = 3
_LOCAL_MAX_VERIFICATION = 2
_LOCAL_MAX_PROMPT = 3000  # chars


def _is_local_eligible(task: dict[str, Any], task_type: str, prompt: str = "") -> bool:
    """True only for safe deterministic tasks suitable for local-model trial.

    Conservative by design — when in doubt, return False (M3 is the safe default).
    The local model gets tried only when ALL conditions hold.
    """
    if task_type in _LOCAL_INELIGIBLE_TASK_TYPES:
        return False
    if len(task.get("scope_in", [])) > _LOCAL_MAX_SCOPE:
        return False
    if len(task.get("acceptance_criteria", [])) > _LOCAL_MAX_CRITERIA:
        return False
    if len(task.get("verification_commands", [])) > _LOCAL_MAX_VERIFICATION:
        return False
    if task.get("forbidden_files"):
        return False
    if prompt and len(prompt) > _LOCAL_MAX_PROMPT:
        return False
    return True

def classify_model_affinity(
    task_intent: str,
    execution_tier: str,
    high_risk: bool,
    prompt_length: int,
    prompt: str = "",
) -> str:
    """Rule-based pi-suitability recommendation. Advisory-only.

    Returns ``"pi" | "claude" | "neutral"``. ``"neutral"`` is the documented
    absent-value default — consumers MUST treat a missing field as neutral
    and route per existing rules.

    Rooted in /go's own intent/risk semantics (independent of execution_tier,
    which is downstream of dispatch and would couple the recommendation to the
    very routing it advises on):
      - direct_answer -> claude (no worker; conversational).
      - decide / investigate / validate intents -> claude (need Claude's
        judgment or are read-only; pi is a coding worker, not a strategist).
      - high_risk surface (hooks/gates/settings/state) -> claude.
      - prompt longer than _PI_PROMPT_MAX_CHARS -> claude (#914 transport).
      - implement intent AND a concrete code target (file path, identifier,
        TASK-NNNN+verb, or verb+code-unit) -> pi. The concreteness gate
        excludes plan-handoff pointers and design asks that the upstream
        intent classifier mislabels as `implement`.
      - everything else (mixed, planning, ambiguous plan-handoff) -> neutral.

    Note: pause_for_authorization is NOT a claude trigger — a paused task
    still has a worker fit; authorization gates WHEN, not WHO.
    """
    if execution_tier == "direct_answer":
        return "claude"
    if task_intent in ("decide", "investigate", "validate"):
        return "claude"
    if high_risk:
        return "claude"
    if prompt_length > _PI_PROMPT_MAX_CHARS:
        return "claude"
    if task_intent == "implement" and _has_concrete_code_target(prompt):
        return "pi"
    return "neutral"


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

    # T0 check: if this is a simple deterministic task, try local model first.
    if tier in ("T1", "T2") and _is_local_eligible(task, task_type):
        tier = "T0"

    # Only design/planning tasks can reach T4 (GLM-5.2).
    # Implementation/refactor/config cap at T3 (M3).
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

    task_file_str = os.environ.get("GO_TASK_FILE", "")
    task_file = pathlib.Path(task_file_str) if task_file_str else None
    if not task_file or not task_file.is_file():
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
