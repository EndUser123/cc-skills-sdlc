"""Fixture (TP): dependency-graph gate with a VERY-OLD expired workaround tag.

Modeled on plugins/cc-aca-epistemic/hooks/pretool/PreToolUse_investigation_gate.py:1054.
The static-import-resolution ceiling is real; the `revisit: 2025-12-01` tag is
the proposed convention. Today is 2026-07-07 -> expired ~7 months ago.
A correct scanner MUST flag this (long-stale debt, highest signal).
"""
from __future__ import annotations

# Dependency discovery stays useful for EDITS to existing files; gating new-file
# creation on it blocked every plugin bootstrap (see cc-council transcript).
# ponytail: ceiling — static import resolution is fundamentally lossy for dynamic
# sys.path code; upgrade path is runtime-aware resolution, not more gates.
# ceiling=strict, revisit: 2025-12-01


def greenfield_exempt(state: dict) -> bool:
    # Greenfield exemption
    if state.get("greenfield_declared"):
        return True
    return False
