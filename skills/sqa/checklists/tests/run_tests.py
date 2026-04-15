#!/usr/bin/env python3
"""Quick test runner to show RED phase failures."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

def test_import_fails():
    """Verify that HookChecklist import fails (RED phase)."""
    try:
        from checklists.hook_checklist import HookChecklist
        print("❌ RED PHASE FAILED: HookChecklist should not exist yet!")
        return False
    except ModuleNotFoundError as e:
        print("✅ RED PHASE CONFIRMED: HookChecklist module does not exist")
        print(f"   Error: {e}")
        return True

if __name__ == "__main__":
    success = test_import_fails()
    sys.exit(0 if success else 1)
