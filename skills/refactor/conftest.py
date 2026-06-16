"""Pytest configuration for the /refactor skill.

Adds the `scripts/` directory to sys.path so module-level imports in
refactor_plan.py (e.g. `from synthesize_findings import ...`) resolve
under pytest's collection-time sys.path.
"""
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
