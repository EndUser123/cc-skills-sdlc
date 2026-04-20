"""Test what blocks when trying to skip TDD."""
import os
import sys
import json

# Simulate what happens when we try to Edit without test first
# This is what I did: called Skill("code"), then used Edit directly

# Check TDD contract gate
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
from hooks.PreToolUse_tdd_contract_gate import process_hook

# Simulate Edit to phase_state.py (implementation file)
input_data = {
    "name": "Edit",
    "tool_input": {
        "file_path": str(Path("utils/phase_state.py"))
    },
    "session_id": "test_session",
    "terminal_id": "test_terminal"
}

allow, reason, context = process_hook(input_data)
print(f"TDD Contract Gate: allow={allow}, reason='{reason}'")

# The result: allow=True because file is NOT in a contract yet
print("Result: No block because file not in TDD contract")
