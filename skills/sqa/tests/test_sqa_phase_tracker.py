"""Tests for SQA Phase Tracker PostToolUse hook."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from posttooluse.posttooluse_sqa_phase_tracker import (  # noqa: E402
    SQA_LAYER_TOOLS,
    SQAPhaseTrackerHook,
    _get_layer_for_tool,
    _get_layer_marker_path,
    _is_characteristic_tool,
    _is_sqa_invocation,
    _load_invocation_state,
    _save_invocation_state,
    write_layer_marker,
)

# Use a test state directory to avoid polluting real state
TEST_STATE_DIR: Path | None = None


@pytest.fixture(autouse=True)
def test_state_dir(tmp_path, monkeypatch):
    """Use isolated test state directory."""
    global TEST_STATE_DIR
    TEST_STATE_DIR = tmp_path / "sqa_phase"
    TEST_STATE_DIR.mkdir()
    monkeypatch.setenv("SQA_PHASE_TRACKER_STATE_DIR", str(TEST_STATE_DIR))
    # Reset terminal detection to known value
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test_terminal_123")
    yield TEST_STATE_DIR


class TestSQALayerToolsMapping:
    """Tests for SQA layer to tool mapping."""

    def test_all_layers_have_characteristic_tools(self):
        """All 7 SQA layers have at least one characteristic tool."""
        expected_layers = {
            "L1_SYNTACTIC",
            "L2_SEMANTIC",
            "L3_STRUCTURAL",
            "L4_REQUIREMENTS",
            "L5_SECURITY",
            "L6_PERFORMANCE",
            "L7_OPERATIONAL",
        }
        assert set(SQA_LAYER_TOOLS.keys()) == expected_layers
        for layer, tools in SQA_LAYER_TOOLS.items():
            assert len(tools) > 0, f"{layer} has no characteristic tools"

    def test_l1_characteristic_tools(self):
        assert SQA_LAYER_TOOLS["L1_SYNTACTIC"] == ["ruff", "mypy"]

    def test_l2_characteristic_tools(self):
        assert SQA_LAYER_TOOLS["L2_SEMANTIC"] == ["verify", "diagnose"]

    def test_l5_characteristic_tools(self):
        assert SQA_LAYER_TOOLS["L5_SECURITY"] == ["adversarial-security", "adversarial-performance"]

    def test_l7_characteristic_tools(self):
        assert SQA_LAYER_TOOLS["L7_OPERATIONAL"] == ["hook-audit", "hook-inventory"]


class TestIsSQAInvocation:
    """Tests for SQA invocation detection."""

    def test_orchestrator_python(self):
        assert _is_sqa_invocation("python orchestrator.py target") is True

    def test_sqa_command(self):
        assert _is_sqa_invocation("sqa run target") is True

    def test_csf_analyze(self):
        assert _is_sqa_invocation("csf-analyze target") is True

    def test_csf_batch(self):
        assert _is_sqa_invocation("csf-batch target") is True

    def test_non_sqa_command(self):
        assert _is_sqa_invocation("ruff check .") is False
        assert _is_sqa_invocation("git status") is False
        assert _is_sqa_invocation("pytest tests/") is False


class TestGetLayerForTool:
    """Tests for layer detection from tool commands."""

    def test_ruff(self):
        assert _get_layer_for_tool("ruff check .") == "L1_SYNTACTIC"

    def test_mypy(self):
        assert _get_layer_for_tool("mypy src/") == "L1_SYNTACTIC"

    def test_verify(self):
        assert _get_layer_for_tool("verify target") == "L2_SEMANTIC"

    def test_diagnose(self):
        assert _get_layer_for_tool("diagnose target") == "L2_SEMANTIC"

    def test_adversarial_security(self):
        assert _get_layer_for_tool("adversarial-security target") == "L5_SECURITY"

    def test_hook_audit(self):
        assert _get_layer_for_tool("hook-audit target") == "L7_OPERATIONAL"

    def test_unknown_tool(self):
        assert _get_layer_for_tool("ls -la") is None


class TestIsCharacteristicTool:
    """Tests for characteristic tool detection."""

    def test_ruff_is_char_for_l1(self):
        assert _is_characteristic_tool("L1_SYNTACTIC", "ruff check .") is True

    def test_mypy_is_char_for_l1(self):
        assert _is_characteristic_tool("L1_SYNTACTIC", "mypy src/") is True

    def test_verify_is_char_for_l2(self):
        assert _is_characteristic_tool("L2_SEMANTIC", "verify target") is True

    def test_ruff_not_char_for_l2(self):
        assert _is_characteristic_tool("L2_SEMANTIC", "ruff check .") is False

    def test_unknown_layer(self):
        assert _is_characteristic_tool("L99_UNKNOWN", "ruff check .") is False


class TestLayerMarker:
    """Tests for layer marker file read/write."""

    def test_write_and_read_marker(self, test_state_dir):
        """write_layer_marker creates marker that can be read back."""
        write_layer_marker("L3_STRUCTURAL")
        marker_path = _get_layer_marker_path()
        assert marker_path.exists()
        data = json.loads(marker_path.read_text())
        assert data["layer"] == "L3_STRUCTURAL"

    def test_write_none_clears_marker(self, test_state_dir):
        """write_layer_marker(None) clears the marker."""
        write_layer_marker("L1_SYNTACTIC")
        write_layer_marker(None)
        marker_path = _get_layer_marker_path()
        data = json.loads(marker_path.read_text())
        assert data["layer"] is None


class TestSQAPhaseTrackerHook:
    """Tests for SQAPhaseTrackerHook PostToolUse hook."""

    def test_tool_matcher_is_bash(self):
        """Hook only activates on Bash tool."""
        hook = SQAPhaseTrackerHook()
        assert hook.matches_tool("Bash") is True
        assert hook.matches_tool("Read") is False
        assert hook.matches_tool("Edit") is False

    def test_non_bash_returns_empty(self):
        """Non-Bash tools return empty dict."""
        hook = SQAPhaseTrackerHook()
        result = hook.process("Read", {"file_path": "foo.py"}, {})
        assert result == {}

    def test_sqa_invocation_resets_state(self, test_state_dir):
        """SQA invocation command resets invocation tracking state."""
        hook = SQAPhaseTrackerHook()
        # Pre-populate state
        state = {"sqa_active": True, "layers_invoked": {"L1": []}, "characteristic_invoked": ["L1"]}
        _save_invocation_state(state)
        # Send SQA invocation
        hook.process("Bash", {"command": "python orchestrator.py target"}, {})
        # Should reset state
        loaded = _load_invocation_state()
        assert loaded["sqa_active"] is True
        assert loaded["characteristic_invoked"] == []

    def test_characteristic_tool_tracked(self, test_state_dir):
        """Characteristic tool invocation is tracked."""
        hook = SQAPhaseTrackerHook()
        # Set up layer marker
        write_layer_marker("L1_SYNTACTIC")
        _save_invocation_state({"sqa_active": True, "layers_invoked": {}, "characteristic_invoked": set()})
        # Invoke characteristic tool
        result = hook.process("Bash", {"command": "ruff check ."}, {})
        assert result == {}
        loaded = _load_invocation_state()
        assert "L1_SYNTACTIC" in loaded["characteristic_invoked"]

    def test_non_characteristic_tool_not_tracked(self, test_state_dir):
        """Non-characteristic tool invocation is not tracked."""
        hook = SQAPhaseTrackerHook()
        write_layer_marker("L1_SYNTACTIC")
        _save_invocation_state({"sqa_active": True, "layers_invoked": {}, "characteristic_invoked": set()})
        result = hook.process("Bash", {"command": "ls -la"}, {})
        assert result == {}
        loaded = _load_invocation_state()
        assert "L1_SYNTACTIC" not in loaded["characteristic_invoked"]

    def test_no_warning_when_layer_has_tools(self, test_state_dir):
        """No warning when layer had characteristic tools."""
        hook = SQAPhaseTrackerHook()
        write_layer_marker("L1_SYNTACTIC")
        _save_invocation_state({
            "sqa_active": True,
            "layers_invoked": {},
            "characteristic_invoked": ["L1_SYNTACTIC"],
            "last_layer": "L1_SYNTACTIC",
        })
        # Switch to next layer
        write_layer_marker("L2_SEMANTIC")
        result = hook.process("Bash", {"command": "verify target"}, {})
        # No warning since L1 already had characteristic tools
        assert result == {}

    def test_default_enabled(self):
        """Hook is enabled by default."""
        hook = SQAPhaseTrackerHook()
        assert hook.enabled is True


class TestOnSQAComplete:
    """Tests for on_sqa_complete summary."""

    def test_no_warning_when_all_layers_have_tools(self, test_state_dir):
        """No warning when all layers had characteristic tools."""
        hook = SQAPhaseTrackerHook()
        _save_invocation_state({
            "sqa_active": True,
            "layers_invoked": {},
            "characteristic_invoked": set(SQA_LAYER_TOOLS.keys()),
            "last_layer": None,
        })
        result = hook.on_sqa_complete()
        assert result == {}

    def test_warning_for_missing_layers(self, test_state_dir):
        """Warning generated for layers without characteristic tools."""
        hook = SQAPhaseTrackerHook()
        _save_invocation_state({
            "sqa_active": True,
            "layers_invoked": {},
            "characteristic_invoked": ["L1_SYNTACTIC", "L2_SEMANTIC"],  # only L1 and L2 invoked
            "last_layer": None,
        })
        result = hook.on_sqa_complete()
        assert "injection" in result
        assert "L3_STRUCTURAL" in result["injection"]
        assert "L5_SECURITY" in result["injection"]

    def test_state_cleared_after_complete(self, test_state_dir):
        """State is reset after on_sqa_complete."""
        hook = SQAPhaseTrackerHook()
        _save_invocation_state({
            "sqa_active": True,
            "layers_invoked": {},
            "characteristic_invoked": [],
            "last_layer": None,
        })
        hook.on_sqa_complete()
        loaded = _load_invocation_state()
        assert loaded["sqa_active"] is False
