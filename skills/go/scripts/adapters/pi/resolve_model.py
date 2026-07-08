#!/usr/bin/env python3
"""Resolve classifier model names to pi CLI --model flags.

Reads model-selection JSON from classify_complexity.py output,
maps the model field to a pi-compatible provider/model string,
and writes the resolved value for the dispatch step.

Usage:
    Resolves GO_STATE_DIR/model-selection_{RUN_ID}.json
    Writes GO_STATE_DIR/pi-model_{RUN_ID}.json
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any

# Classifier model name -> pi CLI --model flag
MODEL_MAP: dict[str, str] = {
    "M3": "minimax/MiniMax-M3",
    "GLM-5.2": "zai/glm-5.2",
    "LOCAL_ORNITH": "llama-cpp/ornith-1.0-9b",
}

# Candidate chains per tier: ordered list of model names to try.
# LOCAL_ORNITH is tried first only for T0/T1 safe-deterministic tasks.
# On failure (timeout, thinking-only, empty output), the next candidate is tried.
CANDIDATE_CHAINS: dict[str, list[str]] = {
    "T0": ["LOCAL_ORNITH", "M3"],
    "T1": ["LOCAL_ORNITH", "M3"],
    "T2": ["M3"],
    "T3": ["M3"],
    "T4": ["GLM-5.2", "M3"],
}


def resolve(model_name: str) -> str | None:
    """Map a classifier model name to a pi CLI model flag.

    Returns None if the model is not in the map.
    """
    return MODEL_MAP.get(model_name)


def resolve_chain(tier: str) -> list[str]:
    """Return ordered pi model flags for a complexity tier.

    T0/T1 safe-deterministic tasks get [LOCAL_ORNITH, M3] — local model
    is tried first; on failure M3 is the fallback.
    T2/T3 get [M3] only. T4 gets [GLM-5.2, M3].
    Unknown tiers default to [M3].
    """
    names = CANDIDATE_CHAINS.get(tier, ["M3"])
    resolved = [resolve(n) for n in names]
    # Drop None entries (missing model config) — fail soft to available models.
    return [r for r in resolved if r is not None]


def main() -> None:
    state_dir = pathlib.Path(os.environ.get("GO_STATE_DIR", ""))
    run_id = os.environ.get("RUN_ID", "unknown")

    selection_file = state_dir / f"model-selection_{run_id}.json"
    if not selection_file.exists():
        print(f"ERROR: model-selection file not found: {selection_file}", file=sys.stderr)
        sys.exit(1)

    selection = json.loads(selection_file.read_text(encoding="utf-8"))
    model_name = selection.get("model", "")

    if not model_name:
        print("ERROR: model-selection has no model field", file=sys.stderr)
        sys.exit(1)

    # Handle override tier (GO_MODEL_OVERRIDE was used)
    if selection.get("tier") == "override":
        pi_model = model_name
    else:
        pi_model = resolve(model_name)

    if pi_model is None:
        print(f"ERROR: no pi mapping for model '{model_name}'", file=sys.stderr)
        sys.exit(1)

    # Build candidate chain for the tier
    tier = selection.get("tier", "unknown")
    chain = resolve_chain(tier) if tier != "override" else [pi_model]

    result: dict[str, Any] = {
        "classifier_model": model_name,
        "tier": tier,
        "pi_model": pi_model,
        "candidate_chain": chain,
        "candidate_models": [resolve(n) for n in CANDIDATE_CHAINS.get(tier, ["M3"]) if resolve(n)],
    }

    out = state_dir / f"pi-model_{run_id}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(f"Resolved: {model_name} -> {pi_model}")


if __name__ == "__main__":
    main()
