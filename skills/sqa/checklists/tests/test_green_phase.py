#!/usr/bin/env python3
"""GREEN phase verification - tests should pass now."""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from checklists.hook_checklist import HookChecklist


def test_basic_structure():
    """Test basic class structure."""
    print("\n1. Testing basic structure...")
    checklist = HookChecklist()
    assert checklist is not None
    assert hasattr(checklist, 'verify_target')
    print("   ✅ Basic structure OK")


def test_verify_target_returns_checklist_result():
    """Test that verify_target returns proper ChecklistResult."""
    print("\n2. Testing verify_target return type...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "test_hook.py"
        hook_file.write_text("# Test hook")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert isinstance(result, dict)
        assert "status" in result
        assert "items_checked" in result
        assert "items_passed" in result
        assert "findings" in result
        print(f"   ✅ Returns ChecklistResult: {result}")


def test_hook_file_exists_check():
    """Test hook file existence check."""
    print("\n3. Testing hook file exists check...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "test_hook.py"
        hook_file.write_text("# Test hook")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_checked"] >= 1
        assert "hook_file_exists" in str(result["findings"])
        print(f"   ✅ File exists check works: {result['findings'][0]}")


def test_missing_hook_file():
    """Test missing hook file handling."""
    print("\n4. Testing missing hook file...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        non_existent = Path(tmp_dir) / "non_existent.py"

        checklist = HookChecklist()
        result = checklist.verify_target(str(non_existent))

        assert result["status"] in ["fail", "partial"]
        assert result["items_passed"] < result["items_checked"]
        print(f"   ✅ Missing file handled: status={result['status']}")


def test_registration_detection():
    """Test registration pattern detection."""
    print("\n5. Testing registration detection...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Hook with registration
        hook_file = Path(tmp_dir) / "registered_hook.py"
        hook_file.write_text("""
@register_hook("test_hook")
def process_hook(data):
    return {"continue": True}
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_checked"] >= 2
        assert any("registration" in str(f).lower() for f in result["findings"])
        print(f"   ✅ Registration detected: {[f for f in result['findings'] if 'registration' in str(f).lower()]}")


def test_router_config_detection():
    """Test router configuration detection."""
    print("\n6. Testing router config detection...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "router_hook.py"
        hook_file.write_text("""
HOOK_PRIORITY = {"test_hook": 1.0}
HOOK_DISPATCH = {"test_hook": run_test_hook}
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_checked"] >= 3
        assert any("router" in str(f).lower() for f in result["findings"])
        print(f"   ✅ Router config detected: {[f for f in result['findings'] if 'router' in str(f).lower()]}")


def test_status_calculation():
    """Test status calculation."""
    print("\n7. Testing status calculation...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Complete hook
        complete_hook = Path(tmp_dir) / "complete.py"
        complete_hook.write_text("""
@register_hook("complete")
HOOK_PRIORITY = {"complete": 1.0}
HOOK_DISPATCH = {"complete": run_complete}
def validate_chain():
    pass
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(complete_hook))

        assert result["status"] in ["pass", "partial", "fail"]
        assert result["items_passed"] <= result["items_checked"]
        print(f"   ✅ Status calculation works: status={result['status']}, passed={result['items_passed']}/{result['items_checked']}")


def main():
    """Run all GREEN phase tests."""
    print("=" * 60)
    print("GREEN PHASE: Testing HookChecklist Implementation")
    print("=" * 60)

    tests = [
        test_basic_structure,
        test_verify_target_returns_checklist_result,
        test_hook_file_exists_check,
        test_missing_hook_file,
        test_registration_detection,
        test_router_config_detection,
        test_status_calculation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"GREEN PHASE Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
