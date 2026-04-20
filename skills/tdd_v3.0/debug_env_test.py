#!/usr/bin/env python3
"""Debug script to check environment variable reading."""

import os
import sys
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from evidence_writer import (
    EVIDENCE_MANAGER_AVAILABLE,
    generate_evidence_artifact,
    is_evidence_tracking_enabled,
)

# Set environment variable
os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"
os.environ["TDD_EVIDENCE_DEBUG"] = "1"

# Check if it's enabled
enabled = is_evidence_tracking_enabled()
print(f"is_evidence_tracking_enabled() = {enabled}")
print(f"EVIDENCE_MANAGER_AVAILABLE = {EVIDENCE_MANAGER_AVAILABLE}")
print(f"Environment variable value: {os.environ.get('TDD_EVIDENCE_TRACKING_ENABLED')}")
print(f"Direct check: {os.environ.get('TDD_EVIDENCE_TRACKING_ENABLED', 'false').lower() == 'true'}")

# Try generating an artifact
temp_dir = Path("P:/__csf/temp_test")
temp_dir.mkdir(parents=True, exist_ok=True)

print("\nCalling generate_evidence_artifact with:")
print("  task_id='TEST-001'")
print("  phase='RED'")
print("  evidence={'test': 'data'}")
print(f"  skill_dir={temp_dir}")
print("  terminal_id='test_terminal'")

try:
    result = generate_evidence_artifact(
        task_id="TEST-001",
        phase="RED",
        evidence={"test": "data"},
        skill_dir=temp_dir,
        terminal_id="test_terminal"
    )
    print(f"\ngenerate_evidence_artifact() returned: {result}")
except Exception as e:
    print(f"\nException occurred: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
import shutil

if temp_dir.exists():
    shutil.rmtree(temp_dir)
