#!/usr/bin/env python3
"""Append a STEP_COMPLETE entry to the execution ledger. Called from /refactor skill prose."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from state_manager_refactor import append_ledger, read_state

if len(sys.argv) != 2:
    print("Usage: ledger_append.py <STEP_NAME>")
    sys.exit(1)

step = sys.argv[1]
state = read_state()
session_id = state.get("session_id") if state else None
append_ledger(step, "STEP_COMPLETE", session_id)
print(f"Ledger: {step} STEP_COMPLETE recorded")
