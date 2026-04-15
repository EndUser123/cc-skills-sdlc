#!/usr/bin/env python3
"""Manual test runner to verify all test scenarios."""

import sys
import tempfile
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from checklists.hook_checklist import HookChecklist


def run_test(test_name, test_func):
    """Run a single test and report results."""
    try:
        test_func()
        print(f"✅ {test_name}")
        return True
    except AssertionError as e:
        print(f"❌ {test_name}: {e}")
        return False
    except Exception as e:
        print(f"❌ {test_name}: Unexpected error: {e}")
        return False


def test_hook_checklist_class_exists():
    """Test that HookChecklist class can be imported."""
    from checklists.hook_checklist import HookChecklist
    assert HookChecklist is not None


def test_hook_checklist_instantiation():
    """Test that HookChecklist can be instantiated."""
    checklist = HookChecklist()
    assert checklist is not None
    assert hasattr(checklist, 'verify_target')


def test_verify_target_returns_checklist_result():
    """Test that verify_target returns a ChecklistResult dict."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "test_hook.py"
        hook_file.write_text("# Test hook file")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert isinstance(result, dict)
        assert "status" in result
        assert "items_checked" in result
        assert "items_passed" in result
        assert "findings" in result


def test_verify_target_checks_hook_file_exists():
    """Test that verify_target checks if hook file exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "test_hook.py"
        hook_file.write_text("# Test hook file")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_checked"] >= 1
        assert "hook_file_exists" in str(result["findings"])


def test_verify_target_missing_hook_file():
    """Test that verify_target handles missing hook file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_existent = Path(tmp_dir) / "non_existent_hook.py"
        checklist = HookChecklist()
        result = checklist.verify_target(str(non_existent))

        assert result["status"] in ["fail", "partial"]
        assert result["items_passed"] < result["items_checked"]
        assert any("missing" in str(f).lower() or "not found" in str(f).lower()
                   for f in result["findings"])


def test_verify_target_detects_registration():
    """Test that verify_target detects hook registration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "registered_hook.py"
        hook_file.write_text("""
@register_hook("test_hook")
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_checked"] >= 2
        assert "registration" in str(result["findings"]).lower()


def test_verify_target_detects_missing_registration():
    """Test that verify_target detects missing registration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "unregistered_hook.py"
        hook_file.write_text("""
# Hook without registration
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_passed"] < result["items_checked"]
        assert any("registration" in str(f).lower() for f in result["findings"])


def test_verify_target_checks_router_config():
    """Test that verify_target checks router configuration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "router_configured_hook.py"
        hook_file.write_text("""
HOOK_PRIORITY = {"test_hook": 1.0}
HOOK_DISPATCH = {"test_hook": run_test_hook}

def run_test_hook(data: dict) -> dict:
    return {"continue": True}
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_checked"] >= 3
        assert "router" in str(result["findings"]).lower()


def test_verify_target_detects_missing_router_config():
    """Test that verify_target detects missing router config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "no_router_config_hook.py"
        hook_file.write_text("""
# Hook without router configuration
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_passed"] < result["items_checked"]
        assert any("router" in str(f).lower() for f in result["findings"])


def test_verify_target_checks_chain_completion():
    """Test that verify_target checks chain completion handler."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "chain_handler_hook.py"
        hook_file.write_text("""
def process_hook(data: dict) -> dict:
    result = run_hook_chain(data)
    return validate_chain_completion(result)
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_checked"] >= 4
        assert "chain" in str(result["findings"]).lower()


def test_verify_target_detects_missing_chain_handler():
    """Test that verify_target detects missing chain handler."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "no_chain_handler_hook.py"
        hook_file.write_text("""
# Hook without chain completion handler
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["items_passed"] < result["items_checked"]
        assert any("chain" in str(f).lower() for f in result["findings"])


def test_all_checks_pass_returns_pass_status():
    """Test that all checks passing returns 'pass' status."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "complete_hook.py"
        hook_file.write_text("""
@register_hook("complete_hook")
HOOK_PRIORITY = {"complete_hook": 1.0}
HOOK_DISPATCH = {"complete_hook": run_complete_hook}

def process_hook(data: dict) -> dict:
    result = run_hook_chain(data)
    return validate_chain_completion(result)
""")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["status"] == "pass"
        assert result["items_passed"] == result["items_checked"]


def test_some_checks_fail_returns_partial_status():
    """Test that some checks failing returns 'partial' status."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "incomplete_hook.py"
        hook_file.write_text("# Incomplete hook\n")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["status"] in ["partial", "fail"]
        assert result["items_passed"] < result["items_checked"]


def test_all_checks_fail_returns_fail_status():
    """Test that all checks failing returns 'fail' status."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_existent = Path(tmp_dir) / "non_existent.py"
        checklist = HookChecklist()
        result = checklist.verify_target(str(non_existent))

        assert result["status"] == "fail"
        assert result["items_passed"] == 0


def test_findings_include_specific_check_names():
    """Test that findings include specific check names."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "test_hook.py"
        hook_file.write_text("# Test hook")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        findings_text = str(result["findings"])
        assert any(term in findings_text.lower() for term in
                   ["hook_file_exists", "registration", "router", "chain"])


def test_findings_include_pass_fail_indicators():
    """Test that findings include pass/fail indicators."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        hook_file = Path(tmp_dir) / "test_hook.py"
        hook_file.write_text("# Test hook")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        findings_text = str(result["findings"])
        assert any(term in findings_text.lower() for term in
                   ["pass", "fail", "missing", "✅", "❌"])


def main():
    """Run all tests."""
    print("=" * 70)
    print("RUNNING ALL HOOK CHECKLIST TESTS")
    print("=" * 70)

    tests = [
        ("HookChecklist class exists", test_hook_checklist_class_exists),
        ("HookChecklist instantiation", test_hook_checklist_instantiation),
        ("verify_target returns ChecklistResult", test_verify_target_returns_checklist_result),
        ("verify_target checks hook file exists", test_verify_target_checks_hook_file_exists),
        ("verify_target handles missing hook file", test_verify_target_missing_hook_file),
        ("verify_target detects registration", test_verify_target_detects_registration),
        ("verify_target detects missing registration", test_verify_target_detects_missing_registration),
        ("verify_target checks router config", test_verify_target_checks_router_config),
        ("verify_target detects missing router config", test_verify_target_detects_missing_router_config),
        ("verify_target checks chain completion", test_verify_target_checks_chain_completion),
        ("verify_target detects missing chain handler", test_verify_target_detects_missing_chain_handler),
        ("All checks pass returns pass status", test_all_checks_pass_returns_pass_status),
        ("Some checks fail returns partial status", test_some_checks_fail_returns_partial_status),
        ("All checks fail returns fail status", test_all_checks_fail_returns_fail_status),
        ("Findings include specific check names", test_findings_include_specific_check_names),
        ("Findings include pass/fail indicators", test_findings_include_pass_fail_indicators),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        if run_test(test_name, test_func):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
