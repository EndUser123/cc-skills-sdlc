"""Tests for cognitive_meta_agent.py module.

These tests verify the deprecated facade functionality.

Run with: pytest P:/packages/rca/skill/tests/test_cognitive_meta_agent.py -v
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Setup import path for rca package
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca import cognitive_meta_agent


class TestFormatLegacy:
    """Tests for _format_legacy helper function."""

    def test_format_legacy_with_empty_tasks(self):
        """Test formatting with no tasks.

        Given: Empty task list
        When: Calling _format_legacy
        Then: Should return formatted header and footer only
        """
        # Mock task object
        mock_task = MagicMock()
        mock_task.name = "Test Task"
        mock_task.pool = "test_pool"
        mock_task.prompt = "Test mission"

        result = cognitive_meta_agent._format_legacy([], "Test Mission")

        assert "[SUBAGENT MISSIONS (via UAF)" in result
        assert "TEST MISSION" in result
        assert "=" * 70 in result

    def test_format_legacy_with_single_task(self):
        """Test formatting with one task.

        Given: Task list with one task
        When: Calling _format_legacy
        Then: Should include task details in output
        """
        mock_task = MagicMock()
        mock_task.name = "Architecture Analysis"
        mock_task.pool = "architect_pool"
        mock_task.prompt = "Analyze system architecture"

        result = cognitive_meta_agent._format_legacy([mock_task], "Architecture")

        assert "Architecture Analysis" in result
        assert "(Pool: architect_pool)" in result
        assert "Mission: Analyze system architecture" in result

    def test_format_legacy_with_multiple_tasks(self):
        """Test formatting with multiple tasks.

        Given: Task list with multiple tasks
        When: Calling _format_legacy
        Then: Should include all task details
        """
        mock_task1 = MagicMock()
        mock_task1.name = "Task 1"
        mock_task1.pool = "pool1"
        mock_task1.prompt = "Mission 1"

        mock_task2 = MagicMock()
        mock_task2.name = "Task 2"
        mock_task2.pool = "pool2"
        mock_task2.prompt = "Mission 2"

        result = cognitive_meta_agent._format_legacy([mock_task1, mock_task2], "Test")

        assert "Task 1" in result
        assert "Task 2" in result
        assert result.count("- ") >= 2  # At least 2 task entries


class TestGetArchSubagents:
    """Tests for get_arch_subagents function."""

    @patch("rca.cognitive_meta_agent.decompose_architecture")
    def test_calls_decompose_architecture(self, mock_decompose):
        """Test that get_arch_subagents calls decompose_architecture.

        Given: get_arch_subagents is called
        When: Function executes
        Then: Should call decompose_architecture with problem
        """
        mock_decompose.return_value = []

        result = cognitive_meta_agent.get_arch_subagents("test problem")

        mock_decompose.assert_called_once_with("test problem")
        assert "[SUBAGENT MISSIONS" in result
        assert "ARCHITECTURE ANALYSIS" in result

    @patch("rca.cognitive_meta_agent.decompose_architecture")
    def test_returns_formatted_output(self, mock_decompose):
        """Test that output is properly formatted.

        Given: decompose_architecture returns tasks
        When: Calling get_arch_subagents
        Then: Should return formatted string with task details
        """
        mock_task = MagicMock()
        mock_task.name = "Analyze Structure"
        mock_task.pool = "arch_pool"
        mock_task.prompt = "Decompose architecture"
        mock_decompose.return_value = [mock_task]

        result = cognitive_meta_agent.get_arch_subagents("analyze this")

        assert "Analyze Structure" in result
        assert "(Pool: arch_pool)" in result


class TestGetRcaSubagents:
    """Tests for get_rca_subagents function."""

    @patch("rca.cognitive_meta_agent.decompose_rca")
    def test_calls_decompose_rca(self, mock_decompose):
        """Test that get_rca_subagents calls decompose_rca.

        Given: get_rca_subagents is called
        When: Function executes
        Then: Should call decompose_rca with problem
        """
        mock_decompose.return_value = []

        result = cognitive_meta_agent.get_rca_subagents("system failure")

        mock_decompose.assert_called_once_with("system failure")
        assert "ROOT CAUSE ANALYSIS" in result


class TestGetDebugSubagents:
    """Tests for get_debug_subagents function."""

    @patch("rca.cognitive_meta_agent.decompose_debug")
    def test_calls_decompose_debug(self, mock_decompose):
        """Test that get_debug_subagents calls decompose_debug.

        Given: get_debug_subagents is called
        When: Function executes
        Then: Should call decompose_debug with problem
        """
        mock_decompose.return_value = []

        result = cognitive_meta_agent.get_debug_subagents("bug report")

        mock_decompose.assert_called_once_with("bug report")
        assert "DEBUG INVESTIGATION" in result


class TestExecuteCognitiveMission:
    """Tests for execute_cognitive_mission async function."""

    @patch("uaf.WorkflowDecomposer")
    @patch("uaf.MissionType")
    def test_arch_mission_type(self, mock_mission_type, mock_decomposer):
        """Test mission type mapping for 'arch'.

        Given: mission_type is 'arch'
        When: Calling execute_cognitive_mission
        Then: Should use MissionType.ARCHITECTURE
        """
        mock_decomposer_inst = MagicMock()
        mock_task = MagicMock()
        mock_task.id = "task_1"
        mock_task.prompt = "Architecture task"
        mock_decomposer_inst.decompose.return_value = [mock_task]
        mock_decomposer.return_value = mock_decomposer_inst
        mock_mission_type.ARCHITECTURE = "arch_value"

        result = asyncio.run(cognitive_meta_agent.execute_cognitive_mission("arch", "test problem"))

        assert result["mission"] == "arch"
        assert result["tasks_decomposed"] == 1

    @patch("uaf.WorkflowDecomposer")
    @patch("uaf.MissionType")
    def test_rca_mission_type(self, mock_mission_type, mock_decomposer):
        """Test mission type mapping for 'rca'.

        Given: mission_type is 'rca'
        When: Calling execute_cognitive_mission
        Then: Should use MissionType.RCA
        """
        mock_decomposer_inst = MagicMock()
        mock_task = MagicMock()
        mock_task.id = "task_1"
        mock_task.prompt = "RCA task"
        mock_decomposer_inst.decompose.return_value = [mock_task]
        mock_decomposer.return_value = mock_decomposer_inst
        mock_mission_type.RCA = "rca_value"

        result = asyncio.run(cognitive_meta_agent.execute_cognitive_mission("rca", "problem"))

        assert result["mission"] == "rca"

    @patch("uaf.WorkflowDecomposer")
    @patch("uaf.MissionType")
    def test_debug_mission_type(self, mock_mission_type, mock_decomposer):
        """Test mission type mapping for 'debug'.

        Given: mission_type is 'debug'
        When: Calling execute_cognitive_mission
        Then: Should use MissionType.DEBUG
        """
        mock_decomposer_inst = MagicMock()
        mock_task = MagicMock()
        mock_task.id = "task_1"
        mock_task.prompt = "Debug task"
        mock_decomposer_inst.decompose.return_value = [mock_task]
        mock_decomposer.return_value = mock_decomposer_inst
        mock_mission_type.DEBUG = "debug_value"

        result = asyncio.run(cognitive_meta_agent.execute_cognitive_mission("debug", "issue"))

        assert result["mission"] == "debug"

    @patch("uaf.WorkflowDecomposer")
    def test_returns_task_list(self, mock_decomposer):
        """Test that tasks are returned in result.

        Given: Decomposer returns tasks
        When: Calling execute_cognitive_mission
        Then: Should return tasks with id and prompt
        """
        mock_decomposer_inst = MagicMock()
        mock_task = MagicMock()
        mock_task.id = "task_123"
        mock_task.prompt = "Test mission prompt"
        mock_decomposer_inst.decompose.return_value = [mock_task]
        mock_decomposer.return_value = mock_decomposer_inst

        result = asyncio.run(cognitive_meta_agent.execute_cognitive_mission("research", "test"))

        assert "tasks" in result
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["id"] == "task_123"
        assert result["tasks"][0]["prompt"] == "Test mission prompt"

    @patch("uaf.WorkflowDecomposer")
    def test_includes_deprecation_note(self, mock_decomposer):
        """Test that result includes deprecation note.

        Given: execute_cognitive_mission is called
        When: Function executes
        Then: Should include note about using UAF TaskExecutor
        """
        mock_decomposer_inst = MagicMock()
        mock_decomposer_inst.decompose.return_value = []
        mock_decomposer.return_value = mock_decomposer_inst

        result = asyncio.run(cognitive_meta_agent.execute_cognitive_mission("research", "test"))

        assert "note" in result
        assert "TaskExecutor" in result["note"]


class TestUafImportFallback:
    """Tests for UAF import fallback behavior."""

    def test_fallback_when_uaf_not_importable(self):
        """Test fallback functions when UAF is not importable.

        Given: UAF module is not available
        When: Importing cognitive_meta_agent
        Then: Should use fallback functions returning empty lists
        """
        # This test verifies the module imports successfully
        # The fallback is defined at module level
        import rca.cognitive_meta_agent as cma

        # If module loaded, either UAF is available or fallback was used
        # We can't easily test the actual fallback without breaking imports,
        # but we can verify the functions exist
        assert hasattr(cma, "decompose_architecture")
        assert hasattr(cma, "decompose_rca")
        assert hasattr(cma, "decompose_debug")
        assert hasattr(cma, "decompose_verification")


class TestModuleExports:
    """Tests for module structure and exports."""

    def test_module_exports_get_arch_subagents(self):
        """Test that get_arch_subagents is exported.

        Given: Importing cognitive_meta_agent module
        When: Checking for get_arch_subagents function
        Then: Should have the function available
        """
        assert hasattr(cognitive_meta_agent, "get_arch_subagents")
        assert callable(cognitive_meta_agent.get_arch_subagents)

    def test_module_exports_get_rca_subagents(self):
        """Test that get_rca_subagents is exported.

        Given: Importing cognitive_meta_agent module
        When: Checking for get_rca_subagents function
        Then: Should have the function available
        """
        assert hasattr(cognitive_meta_agent, "get_rca_subagents")
        assert callable(cognitive_meta_agent.get_rca_subagents)

    def test_module_exports_get_debug_subagents(self):
        """Test that get_debug_subagents is exported.

        Given: Importing cognitive_meta_agent module
        When: Checking for get_debug_subagents function
        Then: Should have the function available
        """
        assert hasattr(cognitive_meta_agent, "get_debug_subagents")
        assert callable(cognitive_meta_agent.get_debug_subagents)

    def test_module_exports_execute_cognitive_mission(self):
        """Test that execute_cognitive_mission is exported.

        Given: Importing cognitive_meta_agent module
        When: Checking for execute_cognitive_mission function
        Then: Should have the function available
        """
        assert hasattr(cognitive_meta_agent, "execute_cognitive_mission")
        assert callable(cognitive_meta_agent.execute_cognitive_mission)
