#!/usr/bin/env python3
"""
SQA Assertions - Binary verification for /sqa self-verification system.

Validates that /sqa actually ran the layers it claims to have run,
halt logic was followed, and completion is legitimate.

Exit codes:
  0 = all assertions pass
  1 = assertion failed (blocking)
  2 = cannot verify (state missing)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from sqa_state_tracker import load_state


_SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _should_halt(findings: int, severity: str, threshold: str) -> bool:
    """Check if findings should trigger halt."""
    if threshold == "NONE":
        return False
    if threshold == "CRITICAL":
        return severity == "CRITICAL"
    if threshold == "HIGH":
        return severity in ("HIGH", "CRITICAL")
    if threshold == "MEDIUM":
        return severity in ("MEDIUM", "HIGH", "CRITICAL")
    return False


def _assertions_pass(state: dict) -> tuple[bool, list[str]]:
    """Run all assertions against state. Returns (passed, errors)."""
    errors: list[str] = []

    # A1: State file exists - already verified by load_state returning non-None

    # A2: All layers up to final_layer_completed have ran=True
    final = state.get("final_layer_completed")
    if final is None:
        errors.append("A2: No final_layer_completed set - /sqa may not have completed any layer")
        return False, errors

    layer_order = [f"L{i}" for i in range(8)]
    final_idx = layer_order.index(final) if final in layer_order else -1

    for i in range(final_idx + 1):
        layer_name = f"L{i}"
        if layer_name not in state.get("layers", {}):
            errors.append(f"A2: Layer {layer_name} not in state but should have run")
            continue
        layer_state = state["layers"][layer_name]
        if not layer_state.get("ran", False) and not layer_state.get("skipped", False):
            errors.append(f"A2: Layer {layer_name} marked as not ran and not skipped")

    # A3: If halt_triggered_at is set, no layers after it have ran=True
    halt_at = state.get("halt_triggered_at")
    if halt_at is not None and halt_at in layer_order:
        halt_idx = layer_order.index(halt_at)
        for i in range(halt_idx + 1, len(layer_order)):
            layer_name = f"L{i}"
            if layer_name in state.get("layers", {}):
                ls = state["layers"][layer_name]
                if ls.get("ran", False) and not ls.get("skipped", False):
                    errors.append(
                        f"A3: Layer {layer_name} ran after halt at {halt_at} - halt logic violated"
                    )

    # A4: findings count consistency - findings must be non-negative
    for layer_name, layer_state in state.get("layers", {}).items():
        findings = layer_state.get("findings", 0)
        if findings < 0:
            errors.append(f"A4: Layer {layer_name} has negative findings count: {findings}")

    # A5: final_layer_completed is consistent with halt_triggered_at
    # If halt was triggered, final_layer should match halt layer (not be past it)
    if halt_at is not None and final != halt_at:
        errors.append(f"A5: final_layer_completed={final} inconsistent with halt_triggered_at={halt_at}")

    return len(errors) == 0, errors


def main() -> int:
    """Main entry point. Returns exit code."""
    # Try to load state
    state = load_state()

    if state is None:
        print("Cannot verify: no SQA state file found", file=sys.stderr)
        print("Ensure /sqa ran and state was written before claiming completion", file=sys.stderr)
        sys.exit(2)

    state_dict = state if isinstance(state, dict) else state.to_dict()

    passed, errors = _assertions_pass(state_dict)

    if not passed:
        print("SQA assertions FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print("", file=sys.stderr)
        print("SQA completion BLOCKED - fix issues before claiming done", file=sys.stderr)
        sys.exit(1)

    print("SQA assertions PASSED")
    print(f"  Target: {state_dict.get('target')}")
    print(f"  Final layer: {state_dict.get('final_layer_completed')}")
    print(f"  Halt triggered: {state_dict.get('halt_triggered_at', 'none')}")
    sys.exit(0)


if __name__ == "__main__":
    main()
