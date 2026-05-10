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
    "M27": "minimax/MiniMax-M2.7",
    "GLM-5.1": "zai/glm-5.1",
}


def resolve(model_name: str) -> str | None:
    """Map a classifier model name to a pi CLI model flag.

    Returns None if the model is not in the map.
    """
    return MODEL_MAP.get(model_name)


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

    result: dict[str, Any] = {
        "classifier_model": model_name,
        "tier": selection.get("tier", "unknown"),
        "pi_model": pi_model,
    }

    out = state_dir / f"pi-model_{run_id}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(f"Resolved: {model_name} -> {pi_model}")


if __name__ == "__main__":
    main()
