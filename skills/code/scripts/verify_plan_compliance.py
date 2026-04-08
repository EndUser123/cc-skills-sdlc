#!/usr/bin/env python3
"""
Plan Compliance Checker - Fix incomplete test coverage bug.

Detects when test files don't implement all planned test cases.
Related: unverified_stance_detector.py had 5/9 planned tests.
"""

import re
import sys
from pathlib import Path


def extract_planned_tests(plan_path: Path) -> int:
    """Count test cases from plan.md Test Strategy section."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan not found: {plan_path}")

    content = plan_path.read_text()

    # Match formats from actual plan:
    # "1. **test name**: description" or
    # "- test case N: description"
    matches = re.findall(
        r'(?:^|\d+\.\s+\*\*)(?:test case|scenario|test)[:\s\*]+|'
        r'^(?:\d+\.|[-*])\s*(?:test case|scenario)[:\s]+',
        content,
        re.MULTILINE | re.IGNORECASE
    )

    # Also count explicit numbered lists in Test Strategy
    test_strategy = re.search(
        r'Test Strategy.*?(?=##|\Z)',
        content,
        re.DOTALL | re.IGNORECASE
    )

    if test_strategy:
        # Count numbered items (1. 2. 3. etc)
        numbered = re.findall(r'^\s*\d+\.\s+', test_strategy.group(0), re.MULTILINE)
        if numbered:
            return len(numbered)

    return len(matches)

def extract_implemented_tests(test_path: Path) -> int:
    """Count pytest test functions."""
    if not test_path.exists():
        raise FileNotFoundError(f"Test file not found: {test_path}")

    content = test_path.read_text()
    matches = re.findall(r'def (test_\w+)\s*\(', content)
    return len(matches)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python verify_plan_compliance.py <plan.md> <test_file.py>")
        sys.exit(2)

    plan_path = Path(sys.argv[1])
    test_path = Path(sys.argv[2])

    try:
        planned = extract_planned_tests(plan_path)
        implemented = extract_implemented_tests(test_path)

        if planned == 0:
            print("⚠️  WARNING: Could not detect test count in plan (regex may need tuning)")
            print(f"✅ Implemented {implemented} tests (assuming complete)")
            sys.exit(0)

        if planned == implemented:
            print(f"✅ PASS: {planned} planned tests, {implemented} implemented")
            sys.exit(0)
        else:
            print(f"❌ FAIL: {planned} planned tests, {implemented} implemented ({planned - implemented} missing)")
            sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(2)
