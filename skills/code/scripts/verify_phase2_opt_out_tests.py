#!/usr/bin/env python3
"""
Batch verification script for GoT/ToT opt-out flag tests across Phase 2 skills.

Runs pytest on all newly created test files and reports results.
"""

import subprocess
import sys
from pathlib import Path

# Phase 2 skills to verify
PHASE_2_SKILLS = [
    'cognitive-frameworks',
    'reflect',
    'evolve',
]

def run_tests(skill_name):
    """Run tests for a specific skill and return results."""
    test_path = Path(f'P:/.claude/skills/{skill_name}/tests/test_opt_out_flags.py')

    if not test_path.exists():
        return {
            'skill': skill_name,
            'status': 'SKIP',
            'reason': 'Test file not found',
            'tests_run': 0,
            'tests_failed': 0,
        }

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(test_path), '-v', '--tb=short'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=f'P:/.claude/skills/{skill_name}'
        )

        # Parse output to count tests
        output = result.stdout + result.stderr
        tests_run = output.count('PASSED') + output.count('FAILED')
        tests_passed = output.count('PASSED')
        tests_failed = output.count('FAILED')

        return {
            'skill': skill_name,
            'status': 'PASS' if result.returncode == 0 else 'FAIL',
            'tests_run': tests_run,
            'tests_passed': tests_passed,
            'tests_failed': tests_failed,
            'output': output[-500:] if len(output) > 500 else output,  # Last 500 chars
        }

    except subprocess.TimeoutExpired:
        return {
            'skill': skill_name,
            'status': 'TIMEOUT',
            'reason': 'Tests timed out after 30 seconds',
            'tests_run': 0,
            'tests_failed': 0,
        }
    except Exception as e:
        return {
            'skill': skill_name,
            'status': 'ERROR',
            'reason': str(e),
            'tests_run': 0,
            'tests_failed': 0,
        }


def main():
    """Run all Phase 2 tests and report results."""
    print("=" * 80)
    print("Phase 2 GoT/ToT Opt-Out Flag Tests - Batch Verification")
    print("=" * 80)
    print()

    results = []
    for skill in PHASE_2_SKILLS:
        print(f"Testing {skill}...", end=' ', flush=True)
        result = run_tests(skill)
        results.append(result)

        if result['status'] == 'PASS':
            print(f"✓ PASS ({result['tests_passed']} tests)")
        elif result['status'] == 'FAIL':
            print(f"✗ FAIL ({result['tests_failed']} failed)")
        elif result['status'] == 'SKIP':
            print(f"⊘ SKIP ({result['reason']})")
        else:
            print(f"⚠ {result['status']} ({result['reason']})")

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)

    total_skills = len(results)
    passed_skills = sum(1 for r in results if r['status'] == 'PASS')
    failed_skills = sum(1 for r in results if r['status'] == 'FAIL')
    skipped_skills = sum(1 for r in results if r['status'] == 'SKIP')

    total_tests = sum(r['tests_run'] for r in results)
    total_passed = sum(r.get('tests_passed', 0) for r in results)
    total_failed = sum(r.get('tests_failed', 0) for r in results)

    print(f"Skills: {passed_skills}/{total_skills} passed")
    print(f"Tests: {total_passed}/{total_tests} passed")

    if failed_skills > 0:
        print()
        print("Failed skills:")
        for result in results:
            if result['status'] == 'FAIL':
                print(f"  - {result['skill']}: {result['tests_failed']} failures")

    if skipped_skills > 0:
        print()
        print("Skipped skills:")
        for result in results:
            if result['status'] == 'SKIP':
                print(f"  - {result['skill']}: {result['reason']}")

    print()
    print("=" * 80)

    # Exit with error code if any tests failed
    sys.exit(0 if failed_skills == 0 else 1)


if __name__ == '__main__':
    main()
