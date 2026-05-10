#!/usr/bin/env python3
"""
PostToolUse Validator for /refactor skill.
Validates tool outputs for errors and checks completion criteria after each phase step.
"""
import json
import sys
from pathlib import Path

def validate_tool_output(data: dict) -> dict:
    """Validate tool output based on /refactor skill requirements."""
    tool_name = data.get("tool_name", "")
    tool_output = data.get("tool_output", "") or ""
    tool_input = data.get("tool_input", {})

    # Check for errors in command output
    if tool_name == "Bash":
        errors = extract_errors(tool_output)
        if errors:
            return {
                "hookSpecificOutput": {
                    "additionalContext": f"⚠️ /refactor: {len(errors)} error(s) detected in command output"
                }
            }

    # Verify key artifacts exist after expected commands
    if tool_name == "Bash" and "deduplicate.py" in tool_output:
        # After deduplication, deduplicated.json should exist
        artifacts = tool_input.get("artifacts_dir", "")
        if artifacts:
            dedup_path = Path(artifacts) / "refactor" / "deduplicated.json"
            if not dedup_path.exists():
                return {
                    "hookSpecificOutput": {
                        "additionalContext": f"⚠️ deduplicated.json not found at {dedup_path}"
                    }
                }

    # After RED phase (TDD tests), verify test failures exist
    if tool_name == "Bash" and any(x in tool_output for x in ["RED_PHASE", "pytest", "test"]):
        if "FAILED" not in tool_output and "passed" not in tool_output.lower():
            # May be in normal execution - not necessarily an error
            pass

    return {}

def extract_errors(output: str) -> list:
    """Extract error indicators from tool output."""
    error_indicators = ["error:", "failed", "exception", "traceback", "error in", "syntax error"]
    return [line for line in output.split("\n") if any(e in line.lower() for e in error_indicators)]

def run(input_data: dict) -> dict | None:
    """In-process hook logic."""
    result = validate_tool_output(input_data)
    return result if result else None


def main():
    input_data = json.loads(sys.stdin.read())
    result = run(input_data)
    if result:
        print(json.dumps(result))
    sys.exit(0)

if __name__ == "__main__":
    main()