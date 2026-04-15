"""Tests for tool_checker.py module.

These tests verify tool availability detection for rca.

Run with: pytest P:/packages/rca/skill/tests/test_tool_checker.py -v
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Setup import path for rca package
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca import tool_checker


class TestDetectAvailableTools:
    """Tests for detect_available_tools function."""

    def test_returns_standard_tools_by_default(self):
        """Test that standard tools are returned when no mock is set.

        Given: No environment variables set
        When: Calling detect_available_tools
        Then: Should return standard tool set
        """
        tools = tool_checker.detect_available_tools()

        assert "Grep" in tools
        assert "Read" in tools
        assert "Bash" in tools
        assert "WebSearch" in tools

    def test_mock_tools_env_var_returns_mocked_set(self):
        """Test that DEBUGRCA_MOCK_TOOLS environment variable works.

        Given: DEBUGRCA_MOCK_TOOLS is set to "CustomTool,TestTool"
        When: Calling detect_available_tools
        Then: Should return exactly the mocked tools
        """
        with patch.dict(os.environ, {"DEBUGRCA_MOCK_TOOLS": "CustomTool,TestTool"}):
            tools = tool_checker.detect_available_tools()

            assert tools == {"CustomTool", "TestTool"}

    def test_mock_tools_empty_string_returns_empty_set(self):
        """Test that empty DEBUGRCA_MOCK_TOOLS returns empty set.

        Given: DEBUGRCA_MOCK_TOOLS is set to empty string
        When: Calling detect_available_tools
        Then: Should return empty set
        """
        with patch.dict(os.environ, {"DEBUGRCA_MOCK_TOOLS": ""}):
            tools = tool_checker.detect_available_tools()

            assert tools == set()

    def test_mock_tools_with_extra_whitespace(self):
        """Test that whitespace in mocked tools is trimmed.

        Given: DEBUGRCA_MOCK_TOOLS has spaces around tool names
        When: Calling detect_available_tools
        Then: Should trim whitespace from tool names
        """
        with patch.dict(os.environ, {"DEBUGRCA_MOCK_TOOLS": " Tool1 , Tool2 "}):
            tools = tool_checker.detect_available_tools()

            assert tools == {"Tool1", "Tool2"}


class TestGetMissingTools:
    """Tests for get_missing_tools function."""

    def test_all_required_tools_present_returns_empty_list(self):
        """Test that when all required tools are present, no tools are missing.

        Given: Available tools include all required tools
        When: Calling get_missing_tools
        Then: Should return empty list
        """
        available = {"Grep", "Read", "Bash", "WebSearch"}
        missing = tool_checker.get_missing_tools(available)

        assert missing == []

    def test_missing_required_tool_returns_tool_name(self):
        """Test that missing required tool is reported.

        Given: Grep is not in available tools
        When: Calling get_missing_tools
        Then: Should return list containing "Grep"
        """
        available = {"Read", "Bash", "WebSearch"}
        missing = tool_checker.get_missing_tools(available)

        assert "Grep" in missing

    def test_multiple_missing_tools_returns_all(self):
        """Test that multiple missing tools are all reported.

        Given: Grep and Read are both missing
        When: Calling get_missing_tools
        Then: Should return both tool names
        """
        available = {"Bash", "WebSearch"}
        missing = tool_checker.get_missing_tools(available)

        assert "Grep" in missing
        assert "Read" in missing
        assert len(missing) == 2

    def test_optional_tool_not_required_ignored(self):
        """Test that optional tools are not required.

        Given: WebSearch is optional (not required)
        When: Calling get_missing_tools
        Then: Should not report WebSearch as missing
        """
        # WebSearch is optional (REQUIRED_TOOLS["WebSearch"] = False)
        available = {"Grep", "Read", "Bash"}
        missing = tool_checker.get_missing_tools(available, local_only=False)

        assert "WebSearch" not in missing


class TestIsLocalOnlyMode:
    """Tests for is_local_only_mode function."""

    def test_no_env_var_returns_false(self):
        """Test that local_only mode is False when env var not set.

        Given: DEBUGRCA_LOCAL_ONLY is not set
        When: Calling is_local_only_mode
        Then: Should return False
        """
        with patch.dict(os.environ, {}, clear=True):
            result = tool_checker.is_local_only_mode()

            assert result is False

    def test_env_var_0_returns_false(self):
        """Test that DEBUGRCA_LOCAL_ONLY=0 returns False.

        Given: DEBUGRCA_LOCAL_ONLY is set to "0"
        When: Calling is_local_only_mode
        Then: Should return False
        """
        with patch.dict(os.environ, {"DEBUGRCA_LOCAL_ONLY": "0"}):
            result = tool_checker.is_local_only_mode()

            assert result is False

    def test_env_var_1_returns_true(self):
        """Test that DEBUGRCA_LOCAL_ONLY=1 returns True.

        Given: DEBUGRCA_LOCAL_ONLY is set to "1"
        When: Calling is_local_only_mode
        Then: Should return True
        """
        with patch.dict(os.environ, {"DEBUGRCA_LOCAL_ONLY": "1"}):
            result = tool_checker.is_local_only_mode()

            assert result is True

    def test_env_var_true_returns_true(self):
        """Test that DEBUGRCA_LOCAL_ONLY=true returns True.

        Given: DEBUGRCA_LOCAL_ONLY is set to "true"
        When: Calling is_local_only_mode
        Then: Should return True
        """
        with patch.dict(os.environ, {"DEBUGRCA_LOCAL_ONLY": "true"}):
            result = tool_checker.is_local_only_mode()

            assert result is True

    def test_env_var_yes_returns_true(self):
        """Test that DEBUGRCA_LOCAL_ONLY=yes returns True.

        Given: DEBUGRCA_LOCAL_ONLY is set to "yes"
        When: Calling is_local_only_mode
        Then: Should return True
        """
        with patch.dict(os.environ, {"DEBUGRCA_LOCAL_ONLY": "yes"}):
            result = tool_checker.is_local_only_mode()

            assert result is True

    def test_env_var_on_returns_true(self):
        """Test that DEBUGRCA_LOCAL_ONLY=on returns True.

        Given: DEBUGRCA_LOCAL_ONLY is set to "on"
        When: Calling is_local_only_mode
        Then: Should return True
        """
        with patch.dict(os.environ, {"DEBUGRCA_LOCAL_ONLY": "on"}):
            result = tool_checker.is_local_only_mode()

            assert result is True

    def test_env_var_case_insensitive(self):
        """Test that env var value is case-insensitive.

        Given: DEBUGRCA_LOCAL_ONLY is set to "TRUE" (uppercase)
        When: Calling is_local_only_mode
        Then: Should return True
        """
        with patch.dict(os.environ, {"DEBUGRCA_LOCAL_ONLY": "TRUE"}):
            result = tool_checker.is_local_only_mode()

            assert result is True


class TestCheckToolAvailability:
    """Tests for check_tool_availability function."""

    def test_all_tools_available_returns_available_true(self):
        """Test that when all required tools are present, returns available=True.

        Given: All required tools are available
        When: Calling check_tool_availability
        Then: Should return available=True
        """
        with patch.dict(os.environ, {}, clear=True):
            result = tool_checker.check_tool_availability()

            assert result["available"] is True
            assert result["missing"] == []
            assert "Grep" in result["tools"]
            assert result["mode"] == "full"

    def test_missing_tool_returns_available_false(self):
        """Test that missing tool returns available=False.

        Given: DEBUGRCA_MOCK_MISSING_TOOLS is set to "Grep"
        When: Calling check_tool_availability
        Then: Should return available=False with Grep in missing list
        """
        with patch.dict(os.environ, {"DEBUGRCA_MOCK_MISSING_TOOLS": "Grep"}):
            result = tool_checker.check_tool_availability()

            assert result["available"] is False
            assert "Grep" in result["missing"]

    def test_local_only_mode_detected(self):
        """Test that local only mode is detected and reflected.

        Given: DEBUGRCA_LOCAL_ONLY is set to "1"
        When: Calling check_tool_availability
        Then: Should return mode="local"
        """
        with patch.dict(os.environ, {"DEBUGRCA_LOCAL_ONLY": "1"}):
            result = tool_checker.check_tool_availability()

            assert result["mode"] == "local"

    def test_forced_error_raises_runtime_error(self):
        """Test that DEBUGRCA_FORCE_CHECK_ERROR raises RuntimeError.

        Given: DEBUGRCA_FORCE_CHECK_ERROR is set
        When: Calling check_tool_availability
        Then: Should raise RuntimeError
        """
        with patch.dict(os.environ, {"DEBUGRCA_FORCE_CHECK_ERROR": "1"}):
            with pytest.raises(RuntimeError, match="Forced check error"):
                tool_checker.check_tool_availability()

    def test_returns_sorted_tools_list(self):
        """Test that tools list is sorted alphabetically.

        Given: Multiple tools are available
        When: Calling check_tool_availability
        Then: Should return tools in sorted order
        """
        with patch.dict(os.environ, {}, clear=True):
            result = tool_checker.check_tool_availability()

            tools = result["tools"]
            assert tools == sorted(tools)

    def test_mock_missing_tools_overrides_detection(self):
        """Test that DEBUGRCA_MOCK_MISSING_TOOLS overrides actual detection.

        Given: DEBUGRCA_MOCK_MISSING_TOOLS is set
        When: Calling check_tool_availability
        Then: Should use mocked missing tools instead of detecting
        """
        with patch.dict(os.environ, {"DEBUGRCA_MOCK_MISSING_TOOLS": "Grep,Read"}):
            result = tool_checker.check_tool_availability()

            assert "Grep" in result["missing"]
            assert "Read" in result["missing"]
            assert result["available"] is False


class TestMain:
    """Tests for main CLI entry point."""

    def test_main_prints_json_and_exits_zero(self, capsys):
        """Test that main prints JSON and exits with 0 on success.

        Given: check_tool_availability succeeds
        When: Calling main
        Then: Should print JSON output and exit(0)
        """
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                tool_checker.main()

            assert exc_info.value.code == 0

            captured = capsys.readouterr()
            # Verify JSON output
            import json

            result = json.loads(captured.out)
            assert "available" in result
            assert "tools" in result

    def test_main_on_error_prints_error_json_and_exits_one(self, capsys):
        """Test that main prints error JSON and exits with 1 on exception.

        Given: check_tool_availability raises an exception
        When: Calling main
        Then: Should print error JSON and exit(1)
        """
        with patch(
            "rca.tool_checker.check_tool_availability", side_effect=RuntimeError("Test error")
        ):
            with pytest.raises(SystemExit) as exc_info:
                tool_checker.main()

            assert exc_info.value.code == 1

            captured = capsys.readouterr()
            # Verify error JSON output
            import json

            result = json.loads(captured.out)
            assert result["available"] is False
            assert "error" in result
            assert "Test error" in result["error"]
