"""Tests for hook verification checklist.

These tests verify the HookChecklist class properly validates hook completeness:
- Hook file exists
- Hook registration present (decorator or registration)
- Router execution configuration
- Chain completion handler

Run with: pytest .claude/skills/verification/checklists/tests/test_hook_checklist.py -v
"""

from pathlib import Path

import pytest


class TestHookChecklistBasicStructure:
    """Tests for basic HookChecklist class structure."""

    def test_hook_checklist_class_exists(self):
        """Test that HookChecklist class can be imported."""
        # This will fail until we create the class
        from checklists.hook_checklist import HookChecklist
        assert HookChecklist is not None

    def test_hook_checklist_instantiation(self):
        """Test that HookChecklist can be instantiated."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        assert checklist is not None
        assert hasattr(checklist, 'verify_target')


class TestHookChecklistVerifyTarget:
    """Tests for verify_target() method behavior."""

    @pytest.fixture
    def sample_hook_path(self, tmp_path: Path) -> Path:
        """Create a sample hook file for testing."""
        hook_file = tmp_path / "test_hook.py"
        hook_file.write_text("""
# Test hook file
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")
        return hook_file

    def test_verify_target_returns_checklist_result(self, sample_hook_path):
        """Test that verify_target returns a ChecklistResult dict."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(sample_hook_path))

        assert isinstance(result, dict)
        assert "status" in result
        assert "items_checked" in result
        assert "items_passed" in result
        assert "findings" in result

    def test_verify_target_checks_hook_file_exists(self, sample_hook_path):
        """Test that verify_target checks if hook file exists."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(sample_hook_path))

        assert result["items_checked"] >= 1
        assert "hook_file_exists" in str(result["findings"])

    def test_verify_target_missing_hook_file(self, tmp_path: Path):
        """Test that verify_target handles missing hook file."""
        from checklists.hook_checklist import HookChecklist

        non_existent = tmp_path / "non_existent_hook.py"
        checklist = HookChecklist()
        result = checklist.verify_target(str(non_existent))

        assert result["status"] in ["fail", "partial"]
        assert result["items_passed"] < result["items_checked"]
        assert any("missing" in str(f).lower() for f in result["findings"])


class TestHookChecklistRegistrationCheck:
    """Tests for hook registration validation."""

    @pytest.fixture
    def registered_hook(self, tmp_path: Path) -> Path:
        """Create a hook with registration pattern."""
        hook_file = tmp_path / "registered_hook.py"
        hook_file.write_text("""
# Hook registered in router
@register_hook("test_hook")
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")
        return hook_file

    def test_verify_target_detects_registration(self, registered_hook):
        """Test that verify_target detects hook registration."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(registered_hook))

        assert result["items_checked"] >= 2
        assert "registration" in str(result["findings"]).lower()

    @pytest.fixture
    def unregistered_hook(self, tmp_path: Path) -> Path:
        """Create a hook without registration pattern."""
        hook_file = tmp_path / "unregistered_hook.py"
        hook_file.write_text("""
# Hook without registration
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")
        return hook_file

    def test_verify_target_detects_missing_registration(self, unregistered_hook):
        """Test that verify_target detects missing registration."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(unregistered_hook))

        assert result["items_passed"] < result["items_checked"]
        assert any("registration" in str(f).lower() for f in result["findings"])


class TestHookChecklistRouterConfiguration:
    """Tests for router execution configuration validation."""

    @pytest.fixture
    def hook_with_router_config(self, tmp_path: Path) -> Path:
        """Create a hook with router configuration."""
        hook_file = tmp_path / "router_configured_hook.py"
        hook_file.write_text("""
# Hook with router configuration
HOOK_PRIORITY = {"test_hook": 1.0}
HOOK_DISPATCH = {"test_hook": run_test_hook}

def run_test_hook(data: dict) -> dict:
    return {"continue": True}
""")
        return hook_file

    def test_verify_target_checks_router_config(self, hook_with_router_config):
        """Test that verify_target checks router configuration."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_with_router_config))

        assert result["items_checked"] >= 3
        assert "router" in str(result["findings"]).lower()

    @pytest.fixture
    def hook_without_router_config(self, tmp_path: Path) -> Path:
        """Create a hook without router configuration."""
        hook_file = tmp_path / "no_router_config_hook.py"
        hook_file.write_text("""
# Hook without router configuration
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")
        return hook_file

    def test_verify_target_detects_missing_router_config(self, hook_without_router_config):
        """Test that verify_target detects missing router config."""
        from checklabs.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_without_router_config))

        assert result["items_passed"] < result["items_checked"]
        assert any("router" in str(f).lower() for f in result["findings"])


class TestHookChecklistChainCompletion:
    """Tests for chain completion handler validation."""

    @pytest.fixture
    def hook_with_chain_handler(self, tmp_path: Path) -> Path:
        """Create a hook with chain completion handler."""
        hook_file = tmp_path / "chain_handler_hook.py"
        hook_file.write_text("""
# Hook with chain completion handler
def process_hook(data: dict) -> dict:
    result = run_hook_chain(data)
    return validate_chain_completion(result)
""")
        return hook_file

    def test_verify_target_checks_chain_completion(self, hook_with_chain_handler):
        """Test that verify_target checks chain completion handler."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_with_chain_handler))

        assert result["items_checked"] >= 4
        assert "chain" in str(result["findings"]).lower()

    @pytest.fixture
    def hook_without_chain_handler(self, tmp_path: Path) -> Path:
        """Create a hook without chain completion handler."""
        hook_file = tmp_path / "no_chain_handler_hook.py"
        hook_file.write_text("""
# Hook without chain completion handler
def process_hook(data: dict) -> dict:
    return {"continue": True}
""")
        return hook_file

    def test_verify_target_detects_missing_chain_handler(self, hook_without_chain_handler):
        """Test that verify_target detects missing chain handler."""
        from checklists.hook_checklist import HookChecklist

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_without_chain_handler))

        assert result["items_passed"] < result["items_checked"]
        assert any("chain" in str(f).lower() for f in result["findings"])


class TestHookChecklistResultStatus:
    """Tests for ChecklistResult status calculation."""

    def test_all_checks_pass_returns_pass_status(self, tmp_path: Path):
        """Test that all checks passing returns 'pass' status."""
        from checklists.hook_checklist import HookChecklist

        # Create a complete hook file
        hook_file = tmp_path / "complete_hook.py"
        hook_file.write_text("""
# Complete hook with all components
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

    def test_some_checks_fail_returns_partial_status(self, tmp_path: Path):
        """Test that some checks failing returns 'partial' status."""
        from checklists.hook_checklist import HookChecklist

        # Create incomplete hook file
        hook_file = tmp_path / "incomplete_hook.py"
        hook_file.write_text("# Incomplete hook\n")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        assert result["status"] in ["partial", "fail"]
        assert result["items_passed"] < result["items_checked"]

    def test_all_checks_fail_returns_fail_status(self, tmp_path: Path):
        """Test that all checks failing returns 'fail' status."""
        from checklists.hook_checklist import HookChecklist

        non_existent = tmp_path / "non_existent.py"
        checklist = HookChecklist()
        result = checklist.verify_target(str(non_existent))

        assert result["status"] == "fail"
        assert result["items_passed"] == 0


class TestHookChecklistEvidenceCollection:
    """Tests for evidence collection in findings."""

    def test_findings_include_specific_check_names(self, tmp_path: Path):
        """Test that findings include specific check names."""
        from checklists.hook_checklist import HookChecklist

        hook_file = tmp_path / "test_hook.py"
        hook_file.write_text("# Test hook")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        # Findings should mention specific checks
        findings_text = str(result["findings"])
        assert any(term in findings_text.lower() for term in
                   ["hook_file_exists", "registration", "router", "chain"])

    def test_findings_include_pass_fail_indicators(self, tmp_path: Path):
        """Test that findings include pass/fail indicators."""
        from checklists.hook_checklist import HookChecklist

        hook_file = tmp_path / "test_hook.py"
        hook_file.write_text("# Test hook")

        checklist = HookChecklist()
        result = checklist.verify_target(str(hook_file))

        # Findings should indicate pass/fail
        findings_text = str(result["findings"])
        assert any(term in findings_text.lower() for term in
                   ["pass", "fail", "missing", "ok", "error"])
