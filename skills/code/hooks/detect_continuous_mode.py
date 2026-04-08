#!/usr/bin/env python3
"""
Detects execution mode for /code skill.

DEFAULT BEHAVIOR (v2.24.0+): Continuous mode is ON by default.
- Runs through all phases without stopping at phase boundaries
- Only stops for genuine blockers (ambiguous requirements, errors, etc.)
- Aligns with Till-Done Execution Rule: "Phase boundaries are NOT stopping points"

OPT-OUT: User can request interactive/step-by-step mode with:
- --interactive, --step-by-step, -i flags
- Phrases: "step by step", "pause after each phase", "interactive mode"

Usage:
    python detect_continuous_mode.py "<user_query>"
    echo "<user_query>" | python detect_continuous_mode.py

Exit codes:
    0 - Successfully processed (check stdout for CONTINUOUS_MODE_DETECTED value)
    1 - Error occurred

Output format:
    CONTINUOUS_MODE_DETECTED: true|false
    STATE_FILE: <path_to_state_file>
"""

import os
import re
import sys
from pathlib import Path

# Patterns that indicate user wants to OPT-IN to continuous mode
# (NOTE: These are now redundant since continuous is default, kept for compatibility)
CONTINUOUS_PATTERNS = [
    r"continue to the end",
    r"continue to the plan to the end",
    r"don't stop until done",
    r"don't stop until.*complete",
    r"execute all phases",
    r"work through.*end",
    r"work.*to the end",
    r"finish all steps",
    r"finish.*all.*steps",
    r"run.*to completion",
    r"run.*through.*end",
    r"auto.*pilot",
    r"complete.*all.*phases",
    r"complete.*all.*tasks",
    r"no.*stopping",
    r"without.*stopping",
    r"without.*pausing",
]

# Patterns that indicate user wants to OPT-OUT of continuous mode (request interactive)
INTERACTIVE_PATTERNS = [
    r"--interactive",
    r"--step-by-step",
    r"--step-by-phase",
    r"-i\b",  # word boundary to avoid matching in middle of words
    r"step by step",
    r"step-by-step",
    r"pause after each phase",
    r"pause after each step",
    r"interactive mode",
    r"ask me before continuing",
    r"confirm each phase",
    r"approve each phase",
]

# State file location (persists across subprocess calls)
STATE_DIR = Path(".claude/skills/code/.state")
STATE_FILE = STATE_DIR / "continuous_mode.flag"


def detect_continuous_mode(user_query: str) -> bool:
    """
    Check if user requested continuous execution mode.

    DEFAULT BEHAVIOR (v2.24.0+): Returns True (continuous mode ON by default)
    OPT-OUT: Returns False only if user explicitly requests interactive mode

    Args:
        user_query: The user's query text to analyze

    Returns:
        True (continuous mode) by default
        False (interactive mode) only if opt-out patterns detected
    """
    if not user_query:
        return True  # Default to continuous mode

    query_lower = user_query.lower()

    # Check for opt-out patterns (user wants interactive/step-by-step mode)
    for pattern in INTERACTIVE_PATTERNS:
        if re.search(pattern, query_lower):
            return False  # User opted out of continuous mode

    # Default to continuous mode ON
    return True


def set_continuous_mode_flag(enabled: bool) -> None:
    """
    Set the continuous mode state file.

    This creates a persistent flag that subprocess calls can check.
    The state file approach ensures the flag survives process boundaries.

    Args:
        enabled: Whether to enable or disable continuous mode
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if enabled:
        STATE_FILE.write_text("1")
    else:
        # Remove flag file if disabling
        if STATE_FILE.exists():
            STATE_FILE.unlink()


def set_environment_flag(enabled: bool) -> None:
    """
    Set environment variable for current process.

    Note: This only affects the current process and direct children.
    For cross-boundary persistence, also use set_continuous_mode_flag().

    Args:
        enabled: Whether to enable or disable continuous mode
    """
    if enabled:
        os.environ["CODE_CONTINUOUS_MODE"] = "1"
    else:
        os.environ.pop("CODE_CONTINUOUS_MODE", None)


def main():
    """Main entry point."""
    # Read query from argument or stdin
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = sys.stdin.read().strip()

    # Detect continuous mode intent
    is_continuous = detect_continuous_mode(query)

    # Set both environment variable and state file
    set_environment_flag(is_continuous)
    set_continuous_mode_flag(is_continuous)

    # Output result (machine-readable)
    print(f"CONTINUOUS_MODE_DETECTED: {str(is_continuous).lower()}")
    print(f"STATE_FILE: {STATE_FILE.absolute()}")
    print(f"ENV_VAR: CODE_CONTINUOUS_MODE={os.environ.get('CODE_CONTINUOUS_MODE', '0')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
