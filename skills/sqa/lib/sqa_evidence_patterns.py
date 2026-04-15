"""
Shared evidence patterns for /sqa skill validation.

Adapted from /p skill's evidence_patterns.py.
Provides common patterns and functions for detecting real tool execution
vs fabricated results in /sqa skill responses. Used by completion and
halt validator Stop hooks.
"""

from __future__ import annotations

import re

# Minimum number of box-drawing characters that suggests a formatted table
# without actual tool execution evidence (potential fabrication indicator)
MIN_BOX_DRAWING_CHARS = 10

# Evidence patterns that indicate real tool execution happened.
# These are artifacts from Bash output, Task agent results, file reads, etc.
EXECUTION_EVIDENCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"pytest"),
    re.compile(r"PASSED|FAILED|ERROR"),
    re.compile(r"git (status|branch|diff|log|tag)"),
    re.compile(r"collected \d+ items?"),
    re.compile(r"\.py::\w+"),
    re.compile(r"(Read|Glob|Bash|Task|Agent)\("),
    re.compile(r"exit code"),
    re.compile(r"ruff"),
    re.compile(r"mypy"),
    re.compile(r"adversarial-"),
    re.compile(r"L\d+.*\w+"),  # Layer references like "L1", "L5"
    re.compile(r"health.?score", re.IGNORECASE),
]

# Pre-compiled fabrication pattern
# Box-drawing chars: ┌ ┤ ┬ ┼ ┐ └ ┘ ├ ┴ ┬ ─ │ etc.
_MIN_CHARS = MIN_BOX_DRAWING_CHARS
_FABRICATION_PATTERN = re.compile(
    rf"[\u250c\u2514\u252c\u2534\u251c\u2524\u2500\u2502\u2518]" + "{" + str(_MIN_CHARS) + ",}",
    re.IGNORECASE,
)

# Fabrication red flags - patterns suggesting made-up results
FABRICATION_PATTERNS: list[re.Pattern[str]] = [
    _FABRICATION_PATTERN,
]


def check_execution_evidence(text: str) -> tuple[bool, list[str]]:
    """Check for evidence of real tool execution.

    Scans the response text for patterns that indicate actual tool execution
    (pytest output, ruff, mypy, Agent results, etc.) rather than fabricated
    or made-up results.

    Returns:
        (has_evidence, found_patterns) where:
        - has_evidence: True if tool calls found OR at least 2 distinct patterns matched
        - found_patterns: List of matched strings that indicate evidence
    """
    found: list[str] = []

    for pattern in EXECUTION_EVIDENCE_PATTERNS:
        matches = pattern.findall(text)
        found.extend(matches)

    # Check for tool calls - these are strong evidence
    has_tool_calls = bool(re.search(r"(Read|Glob|Bash|Task|Agent)\(", text, re.IGNORECASE))

    if has_tool_calls:
        return True, found

    # No tool calls - need at least 2 distinct patterns to match
    distinct_patterns: list[str] = []
    for pattern in EXECUTION_EVIDENCE_PATTERNS:
        if pattern.search(text):
            distinct_patterns.append(pattern.pattern)
    return len(distinct_patterns) >= 2, found


def has_heavy_tables(text: str) -> bool:
    """Check for suspiciously formatted tables (potential fabrication indicator).

    Box-drawing characters are often used to create neat ASCII tables.
    When these appear heavily (10+ consecutive chars) without evidence of
    real tool execution, it suggests the response was fabricated rather
    than generated from actual tool output.

    Returns:
        True if heavy box-drawing character usage detected
    """
    return bool(_FABRICATION_PATTERN.search(text))


def get_fabrication_error_message() -> str:
    """Get the standard error message for fabrication detection."""
    return (
        "FABRICATION DETECTED: Response contains formatted tables but no evidence "
        "of real tool execution (no pytest output, no ruff/mypy results, no Agent/Bash results). "
        "/sqa MUST use Agent/Bash tools to gather real data. "
        "Re-run the pipeline with actual tool calls."
    )


def validate_sqa_response(
    response_text: str, check_for_completion: bool = False
) -> tuple[bool, str]:
    """Validate an /sqa skill response for fabrication and format.

    Performs common validation checks shared by completion and halt validators:
    1. Checks if the response looks like an /sqa response
    2. Validates execution evidence (blocks fabricated responses with tables but no evidence)
    3. Optionally checks for completion or halt format indicators

    Args:
        response_text: The response text to validate
        check_for_completion: If True, check for completion format; if False, check for halt format

    Returns:
        (allow, reason) where allow is True if validation passes, False otherwise
    """
    # Check if this looks like an /sqa response
    if "/sqa" not in response_text.lower() and "layer" not in response_text.lower():
        return True, "Not a /sqa response"

    # Execution evidence check (applies to ALL /sqa responses)
    has_evidence, found_patterns = check_execution_evidence(response_text)
    heavy_tables_detected = has_heavy_tables(response_text)

    if heavy_tables_detected and not has_evidence:
        return False, get_fabrication_error_message()

    # Format indicator check (completion vs halt)
    if check_for_completion:
        complete_indicators = [
            r"## SQA (Complete|Certification|Certified)",
            r"\*\*Summary:\*\*.*health.?score",
            r"Health Score:\s*\d+",
            r"layers?\s+completed",
            r"ALL\s+LAYERS\s+PASS(ED|ING)?",
            r"\u2705.*(?:L\d+\s+)+",  # Checkmark with layer references
        ]
        has_indicator = any(
            re.search(pattern, response_text, re.IGNORECASE)
            for pattern in complete_indicators
        )
        if not has_indicator:
            return True, "Not a completion message"
    else:
        # Halt indicators: all-tools-unavailable, cannot proceed, etc.
        halt_indicators = [
            r"ERROR:.*cannot proceed",
            r"all\s+tools?\s+unavailable",
            r"layer.*skipped",
            r"halt",
        ]
        has_indicator = any(
            re.search(pattern, response_text, re.IGNORECASE)
            for pattern in halt_indicators
        )
        if not has_indicator:
            return True, "No halt detected"

    return True, "Format validated"
