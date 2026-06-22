#!/usr/bin/env python3
"""Test coverage-gate.py with real coverage.json."""

import os
import subprocess
import sys
from pathlib import Path

# Setup environment
test_dir = Path("test_coverage_gate")
state_dir = test_dir / "state"
state_dir.mkdir(parents=True, exist_ok=True)

env = os.environ.copy()
env["RUN_ID"] = "test-001"
env["GO_STATE_DIR"] = str(state_dir)

# Test 1: Happy path (50% coverage, should fail default 80% threshold)
print("Test 1: 50% coverage (should fail with default 80% threshold)")
result = subprocess.run(
    [sys.executable, "../scripts/coverage-gate.py", "--coverage-file", "coverage.json"],
    cwd=test_dir,
    env=env,
    capture_output=True,
    text=True
)
print(f"Exit code: {result.returncode}")
print(f"Stderr: {result.stderr}")
if result.returncode != 0:
    print("✓ PASS: Correctly fails on 50% < 80%")
else:
    print("✗ FAIL: Should have failed on 50% coverage")

# Test 2: Pass with lower threshold
print("\nTest 2: 50% coverage (should pass with 40% threshold)")
env["GO_COVERAGE_THRESHOLD"] = "40"
result = subprocess.run(
    [sys.executable, "../scripts/coverage-gate.py", "--coverage-file", "coverage.json"],
    cwd=test_dir,
    env=env,
    capture_output=True,
    text=True
)
print(f"Exit code: {result.returncode}")
print(f"Stderr: {result.stderr}")
if result.returncode == 0:
    print("✓ PASS: Correctly passes with 40% threshold")
else:
    print("✗ FAIL: Should have passed with 40% coverage")

# Test 3: Missing coverage file
print("\nTest 3: Missing coverage.json (should fail with helpful error)")
result = subprocess.run(
    [sys.executable, "../scripts/coverage-gate.py", "--coverage-file", "nonexistent.json"],
    cwd=test_dir,
    env=env,
    capture_output=True,
    text=True
)
print(f"Exit code: {result.returncode}")
print(f"Stderr: {result.stderr}")
if result.returncode != 0:
    print("✓ PASS: Correctly fails with missing file")
else:
    print("✗ FAIL: Should have failed with missing file")

# Test 4: Check artifact generation (from Test 2 which passed)
print("\nTest 4: Verify artifact generation")
artifact_path = state_dir / "coverage-gate-test-001.json"
verification_path = state_dir / "verification-result_test-001.json"
print(f"Artifact exists: {artifact_path.exists()}")
print(f"Verification result exists: {verification_path.exists()}")
if artifact_path.exists():
    print("✓ PASS: Artifact written")
else:
    print("✗ FAIL: Artifact not written")