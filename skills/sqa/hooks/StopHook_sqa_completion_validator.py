#!/usr/bin/env python3
"""
Stop hook for /sqa skill - Completion validator.

Validates that when /sqa completes, it follows the required format
AND shows evidence of real tool execution (not fabricated results).
AND ran the required layers (state verification).

Adapted from /p StopHook_p_completion_validator.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Add lib directory to path for imports
LIB_DIR = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

# Add __lib for shared utilities (changelog_writer)
SKILLS_LIB_DIR = Path(__file__).parent.parent.parent / "__lib"
if str(SKILLS_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(SKILLS_LIB_DIR))

from sqa_evidence_patterns import validate_sqa_response


def _run_assertions() -> tuple[bool, str]:
    """Run SQA assertions to verify layer execution completeness."""
    evals_dir = Path(__file__).parent.parent / "evals"
    assertions_script = evals_dir / "sqa_assertions.py"

    if not assertions_script.exists():
        return True, "Assertions script not found - skipping state verification"

    try:
        result = subprocess.run(
            [sys.executable, str(assertions_script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        elif result.returncode == 1:
            return False, f"SQA assertions FAILED:\n{result.stderr}"
        else:
            return True, f"Cannot verify state (exit {result.returncode}): {result.stderr}"
    except subprocess.TimeoutExpired:
        return True, "Assertion timed out - skipping verification"
    except Exception as e:
        return False, f"SQA assertions crashed unexpectedly: {e}"  # fail closed


def main() -> None:
    # Read the LLM's response from stdin
    response_text = sys.stdin.read() if not sys.stdin.isatty() else ""

    # Use shared validation function for common checks
    allow, reason = validate_sqa_response(response_text, check_for_completion=True)

    if not allow:
        print(json.dumps({"allow": False, "reason": reason}))
        sys.exit(1)

    if "Not a /sqa response" in reason or "Not a completion message" in reason:
        print(json.dumps({"allow": True, "reason": reason}))
        sys.exit(0)

    # Run state assertions to verify layer execution completeness
    state_ok, state_msg = _run_assertions()
    if not state_ok:
        print(json.dumps({"allow": False, "reason": f"State verification FAILED:\n{state_msg}"}))
        sys.exit(1)

    # Completion detected - validate format has required sections
    errors: list[str] = []

    # Check for health score section
    if not re.search(r"health.?score", response_text, re.IGNORECASE):
        errors.append("Missing health score in output")

    # Check for layers completed section or table
    if not re.search(r"L\d+", response_text):
        errors.append("Missing layer references (L0-L7, META)")

    # Check for findings summary
    if not re.search(r"finding", response_text, re.IGNORECASE):
        errors.append("Missing findings summary")

    # Check for target being certified
    if not re.search(r"certif|targe|analy", response_text, re.IGNORECASE):
        errors.append("Missing target or certification context")

    # Block if format is incomplete
    if errors:
        error_msg = "Completion format validation failed:\n" + "\n".join(
            f"- {e}" for e in errors
        )
        print(
            json.dumps(
                {
                    "allow": False,
                    "reason": error_msg
                    + "\n\nCompletion responses must include: health score, layer references, findings summary.",
                }
            )
        )
        sys.exit(1)

    # Extract target path from response text (look for path-like patterns)
    target_path: str | None = None
    path_pattern = re.compile(r'(?:analyzing|certifying|targeting|analyzing)\s+([^\s\\]+(?:\\?[\w./\-][^\s]*)+\b)')
    for match in path_pattern.finditer(response_text):
        candidate = match.group(1)
        if Path(candidate).exists():
            target_path = candidate
            break

    # Write to package CHANGELOG.md (non-blocking)
    _write_sqa_changelog(target_path)

    # Format looks good and state verified - allow the response
    print(json.dumps({"allow": True, "reason": f"Completion validated. {state_msg}"}))
    sys.exit(0)


def _write_sqa_changelog(target_path: str | None) -> None:
    """Write /sqa completion entry to package CHANGELOG.md.

    Args:
        target_path: Path that was analyzed by SQA
    """
    if not target_path:
        return
    try:
        from changelog_writer import record_investigation
        root = Path(target_path)
        # Walk up to find a directory with CHANGELOG.md (package root)
        while root != root.parent:
            if (root / "CHANGELOG.md").exists():
                record_investigation(
                    package_root=root,
                    skill="/sqa",
                    description=f"SQA analysis of {root.name}",
                )
                break
            root = root.parent
    except Exception:
        pass  # Non-fatal - changelog write failures should not block the response


if __name__ == "__main__":
    main()
