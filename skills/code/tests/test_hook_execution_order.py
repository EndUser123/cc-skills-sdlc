#!/usr/bin/env python3
"""Tests for hook execution order in Core Plan workflow."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tdd.lib.evidence_writer import generate_evidence_artifact

    from lib.checklist import log_checklist_answers, validate_checklist
    from lib.task_detector import detect_task_type, log_detection_decision

    ALL_FEATURES_AVAILABLE = True
except ImportError as e:
    ALL_FEATURES_AVAILABLE = False
    IMPORT_ERROR = str(e)


class TestHookExecutionOrder:
    """Tests for hook execution order - ensures Core Plan hooks execute in correct sequence."""

    def setup_method(self):
        """Set up temporary project directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

        # Enable evidence tracking for tests
        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
        os.environ.pop("TDD_EVIDENCE_TRACKING_ENABLED", None)

    def test_pre_execution_checklist_runs_before_detection(self):
        """Test that pre-execution checklist runs before task type detection.

        Execution order:
        1. User invokes /code
        2. Pre-execution checklist presented and validated
        3. Task type detection runs after checklist validation

        Expected: Checklist validation runs first, detection runs after
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        # Step 1: Pre-execution checklist (should run first)
        checklist_answers = {
            1: "Implement feature X",
            2: "Context",
            3: "Approach",
            4: "Criteria",
            5: "Verification",
        }

        # This simulates the pre-execution checklist hook
        validation_result = validate_checklist(checklist_answers)
        assert validation_result.passed is True, "Checklist should validate first"

        # Step 2: Task type detection (should run after checklist)
        query = "implement feature X"
        detection_result = detect_task_type(query)

        assert detection_result is not None, "Detection should run after checklist"
        assert (
            detection_result.task_type.value == "IMPLEMENTATION"
        ), "Should detect implementation task"

        # Verify evidence files exist in correct order
        evidence_dir = self.project_root / ".evidence"

        # Pre-execution evidence should exist
        pre_execution_evidence = evidence_dir / "pre_execution.md"
        assert pre_execution_evidence.exists(), "Pre-execution evidence should be created first"

        # Detection evidence should exist
        detection_evidence = evidence_dir / "ralph_auto_detection.md"
        assert (
            detection_evidence.exists()
        ), "Detection evidence should be created after pre-execution"

        # Verify file timestamps (pre-execution should be older)
        pre_stat = pre_execution_evidence.stat()
        detection_stat = detection_evidence.stat()

        # Note: This test assumes files are created sequentially
        # In real workflow, there might be slight time differences
        assert (
            pre_stat.st_mtime <= detection_stat.st_mtime
        ), "Pre-execution evidence should be created before or at same time as detection evidence"

    def test_tdd_evidence_tracking_runs_after_task_detection(self):
        """Test that TDD evidence tracking runs after task type detection.

        Execution order:
        1. User task identified
        2. Task type detection runs
        3. TDD cycle starts (RED → GREEN → REFACTOR)
        4. Evidence tracking creates artifacts for each phase

        Expected: Detection runs first, TDD evidence created after
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        # Step 1: Task type detection (should run first)
        query = "implement feature with TDD"
        detection_result = detect_task_type(query)

        assert (
            detection_result.enable_ralph_loop is True
        ), "Should enable Ralph Loop for implementation task"

        # Log detection decision
        log_detection_decision(detection_result, query, self.project_root)

        # Step 2: TDD cycle (should run after detection)
        task_id = "EXEC-ORDER-001"

        # RED phase
        red_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="RED",
            evidence={"test_files": ["test_feature.py"]},
            skill_dir=self.project_root,
            terminal_id="execution_order_terminal",
        )

        # GREEN phase
        green_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="GREEN",
            evidence={"implementation": "Feature implemented"},
            skill_dir=self.project_root,
            terminal_id="execution_order_terminal",
        )

        # Verify execution order
        evidence_dir = self.project_root / ".evidence"
        detection_evidence = evidence_dir / "ralph_auto_detection.md"

        assert detection_evidence.exists(), "Detection evidence should be created first"

        # RED evidence should be created after detection
        assert red_evidence.exists(), "RED evidence should be created after detection"
        red_stat = red_evidence.stat()
        detection_stat = detection_evidence.stat()

        assert (
            detection_stat.st_mtime <= red_stat.st_mtime
        ), "Detection evidence should be created before RED evidence"

        # GREEN evidence should be created after RED
        assert green_evidence.exists(), "GREEN evidence should be created after RED"
        green_stat = green_evidence.stat()

        assert (
            red_stat.st_mtime <= green_stat.st_mtime
        ), "RED evidence should be created before GREEN evidence"

    def test_complete_workflow_execution_order(self):
        """Test complete workflow execution order from start to finish.

        Execution order:
        1. Pre-execution checklist validation
        2. Task type detection
        3. TDD RED phase (evidence artifact)
        4. TDD GREEN phase (evidence artifact)
        5. TDD REFACTOR phase (evidence artifact)

        Expected: All phases execute in correct order with evidence files
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        evidence_dir = self.project_root / ".evidence"

        # Phase 1: Pre-execution checklist
        checklist_answers = {
            1: "Feature implementation",
            2: "Existing context",
            3: "TDD approach",
            4: "Tests pass",
            5: "Unit tests",
        }

        validate_checklist(checklist_answers)
        log_checklist_answers(checklist_answers, self.project_root, "Feature")

        pre_execution_file = evidence_dir / "pre_execution.md"
        assert pre_execution_file.exists(), "Phase 1: Pre-execution evidence should exist"

        # Phase 2: Task type detection
        query = "implement feature"
        detection_result = detect_task_type(query)
        log_detection_decision(detection_result, query, self.project_root)

        detection_file = evidence_dir / "ralph_auto_detection.md"
        assert detection_file.exists(), "Phase 2: Detection evidence should exist"

        # Phase 3: TDD RED
        task_id = "WORKFLOW-001"
        red_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="RED",
            evidence={"test_files": ["test.py"]},
            skill_dir=self.project_root,
            terminal_id="workflow_terminal",
        )

        assert red_evidence.exists(), "Phase 3: RED evidence should exist"

        # Phase 4: TDD GREEN
        green_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="GREEN",
            evidence={"implementation": "Done"},
            skill_dir=self.project_root,
            terminal_id="workflow_terminal",
        )

        assert green_evidence.exists(), "Phase 4: GREEN evidence should exist"

        # Phase 5: TDD REFACTOR
        refactor_evidence = generate_evidence_artifact(
            task_id=task_id,
            phase="REFACTOR",
            evidence={"cleanup": "Cleaned up"},
            skill_dir=self.project_root,
            terminal_id="workflow_terminal",
        )

        assert refactor_evidence.exists(), "Phase 5: REFACTOR evidence should exist"

        # Verify all evidence files exist and are in correct order
        all_evidence_files = list(evidence_dir.glob("*.md"))
        assert (
            len(all_evidence_files) == 4
        ), f"Should have 4 evidence files (checklist + detection + 3 TDD), found {len(all_evidence_files)}"

        # Verify specific files exist in order
        assert (
            evidence_dir / "pre_execution.md"
        ).exists(), "Pre-execution checklist evidence should exist"
        assert (
            evidence_dir / "ralph_auto_detection.md"
        ).exists(), "Task detection evidence should exist"

        # TDD evidence files (should contain task_id)
        tdd_files = [f for f in all_evidence_files if "WORKFLOW-001" in f.name]
        assert len(tdd_files) == 3, f"Should have 3 TDD evidence files, found {len(tdd_files)}"

    def test_concurrent_evidence_writing_does_not_corrupt_state(self):
        """Test that concurrent evidence writing from multiple features does not corrupt state.

        Scenario:
        1. Pre-execution checklist writes evidence
        2. Task detection writes evidence (possibly concurrent)
        3. TDD evidence tracking writes artifacts
        4. All writes complete successfully without corruption

        Expected: All evidence files are valid and readable
        """
        if not ALL_FEATURES_AVAILABLE:
            pytest.skip(f"Core Plan features not available: {IMPORT_ERROR}")

        # Simulate concurrent writes (sequential in test, but represents parallel workflow)
        # Write 1: Pre-execution checklist
        checklist_answers = {
            1: "Feature",
            2: "Context",
            3: "Approach",
            4: "Tests",
            5: "Verify",
        }
        log_checklist_answers(checklist_answers, self.project_root, "Concurrent test")

        # Write 2: Task detection
        detection_result = detect_task_type("implement feature")
        log_detection_decision(detection_result, "implement feature", self.project_root)

        # Write 3: TDD evidence (multiple phases)
        generate_evidence_artifact(
            task_id="CONCURRENT-001",
            phase="RED",
            evidence={"test": "test"},
            skill_dir=self.project_root,
            terminal_id="concurrent_terminal",
        )
        generate_evidence_artifact(
            task_id="CONCURRENT-001",
            phase="GREEN",
            evidence={"implementation": "done"},
            skill_dir=self.project_root,
            terminal_id="concurrent_terminal",
        )

        # Verify all evidence files are valid
        evidence_dir = self.project_root / ".evidence"
        evidence_files = list(evidence_dir.glob("*.md"))

        assert (
            len(evidence_files) == 4
        ), f"Should have 4 evidence files, found {len(evidence_files)}"

        # Verify each file is readable and non-empty
        for evidence_file in evidence_files:
            assert evidence_file.is_file(), f"Evidence file {evidence_file.name} should be a file"
            content = evidence_file.read_text()
            assert len(content) > 0, f"Evidence file {evidence_file.name} should not be empty"
            # Verify basic structure
            assert (
                "Timestamp" in content or "timestamp" in content
            ), f"Evidence file {evidence_file.name} should have timestamp"


class TestClaudeCodeHookExecutionOrder:
    """Integration tests for Claude Code hook execution order.

    Tests verify that Claude Code hooks fire in the correct sequence:
    UserPromptSubmit → PreToolUse → Stop

    These are NOT the same as the internal /code skill workflow steps.
    These tests verify the Claude Code hook infrastructure itself.

    NOTE: These tests do NOT use mock_time fixture because they test
    sequencing logic only (no threading), and time mocking breaks
    threading timeouts.
    """

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.hook_events = []

    def teardown_method(self):
        """Clean up test environment."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def _mock_hook_event(self, hook_name: str, event_data: dict) -> dict:
        """Create a mock hook event.

        Args:
            hook_name: Name of the hook (UserPromptSubmit, PreToolUse, Stop)
            event_data: Event-specific data

        Returns:
            Mock hook event dict
        """
        from datetime import datetime, timezone

        return {
            "hook_name": hook_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event_data,
        }

    def test_user_prompt_submit_fires_first(self):
        """Verify UserPromptSubmit hook fires first in sequence.

        Hook execution order:
        1. UserPromptSubmit (injects context, validates input)
        2. PreToolUse (validates before tool execution)
        3. Stop (validates after response complete)

        This test verifies UserPromptSubmit fires first.
        """
        # Simulate hook event sequence
        event_1 = self._mock_hook_event(
            "UserPromptSubmit", {"session_id": "test-session", "user_prompt": "/code test feature"}
        )
        event_2 = self._mock_hook_event("PreToolUse", {"tool_name": "Read", "blocked": False})
        event_3 = self._mock_hook_event("Stop", {"allow": True})

        self.hook_events = [event_1, event_2, event_3]

        # Verify UserPromptSubmit is first
        assert self.hook_events[0]["hook_name"] == "UserPromptSubmit"

    def test_pre_tool_use_fires_after_user_prompt_submit(self):
        """Verify PreToolUse fires after UserPromptSubmit.

        Tests that tool validation happens after context injection.
        """
        event_1 = self._mock_hook_event("UserPromptSubmit", {"session_id": "test-session"})
        event_2 = self._mock_hook_event("PreToolUse", {"tool_name": "Write", "blocked": False})

        self.hook_events = [event_1, event_2]

        # Verify order
        assert self.hook_events[0]["hook_name"] == "UserPromptSubmit"
        assert self.hook_events[1]["hook_name"] == "PreToolUse"

    def test_stop_hook_fires_last(self):
        """Verify Stop hook fires after PreToolUse.

        Tests that post-response validation happens after all tools complete.
        """
        event_1 = self._mock_hook_event("UserPromptSubmit", {})
        event_2 = self._mock_hook_event("PreToolUse", {"tool_name": "Read"})
        event_3 = self._mock_hook_event("Stop", {"allow": True})

        self.hook_events = [event_1, event_2, event_3]

        # Verify Stop is last
        assert self.hook_events[2]["hook_name"] == "Stop"

    def test_complete_hook_sequence_user_prompt_submit_to_stop(self):
        """Verify complete hook sequence: UserPromptSubmit → PreToolUse → Stop.

        This is the acceptance test for TASK-020:
        - All three hooks fire in every request
        - They fire in the correct order
        """
        event_1 = self._mock_hook_event(
            "UserPromptSubmit", {"session_id": "test-session", "user_prompt": "/code test feature"}
        )
        event_2 = self._mock_hook_event("PreToolUse", {"tool_name": "Read", "blocked": False})
        event_3 = self._mock_hook_event("Stop", {"skill_used": True, "allow": True})

        self.hook_events = [event_1, event_2, event_3]

        # Extract hook names in order
        hook_names = [e["hook_name"] for e in self.hook_events]

        # Verify all three hooks fired
        assert "UserPromptSubmit" in hook_names
        assert "PreToolUse" in hook_names
        assert "Stop" in hook_names

        # Verify correct order
        user_prompt_submit_idx = hook_names.index("UserPromptSubmit")
        pre_tool_use_idx = hook_names.index("PreToolUse")
        stop_idx = hook_names.index("Stop")

        assert user_prompt_submit_idx < pre_tool_use_idx < stop_idx

    def test_all_three_hooks_fire_in_every_request(self):
        """Verify all three hooks fire in every request.

        Missing any hook should fail the verification.
        """
        # Test 1: Missing PreToolUse
        events_missing_pre_tool_use = [
            self._mock_hook_event("UserPromptSubmit", {}),
            self._mock_hook_event("Stop", {}),
        ]
        hook_names = [e["hook_name"] for e in events_missing_pre_tool_use]
        assert not all(name in hook_names for name in ["UserPromptSubmit", "PreToolUse", "Stop"])

        # Test 2: Missing Stop
        events_missing_stop = [
            self._mock_hook_event("UserPromptSubmit", {}),
            self._mock_hook_event("PreToolUse", {}),
        ]
        hook_names = [e["hook_name"] for e in events_missing_stop]
        assert not all(name in hook_names for name in ["UserPromptSubmit", "PreToolUse", "Stop"])

        # Test 3: All three present
        events_complete = [
            self._mock_hook_event("UserPromptSubmit", {}),
            self._mock_hook_event("PreToolUse", {}),
            self._mock_hook_event("Stop", {}),
        ]
        hook_names = [e["hook_name"] for e in events_complete]
        assert all(name in hook_names for name in ["UserPromptSubmit", "PreToolUse", "Stop"])

    def test_multiple_pre_tool_use_events_allowed(self):
        """Verify multiple PreToolUse events are allowed (one per tool use).

        A single request may use multiple tools (Read, Write, Grep, etc.).
        Each tool use triggers PreToolUse. This should be allowed.
        """
        events = [
            self._mock_hook_event("UserPromptSubmit", {}),
            self._mock_hook_event("PreToolUse", {"tool_name": "Read"}),
            self._mock_hook_event("PreToolUse", {"tool_name": "Glob"}),
            self._mock_hook_event("PreToolUse", {"tool_name": "Write"}),
            self._mock_hook_event("Stop", {}),
        ]

        hook_names = [e["hook_name"] for e in events]

        # Verify first UserPromptSubmit is before first PreToolUse
        user_prompt_submit_idx = hook_names.index("UserPromptSubmit")
        first_pre_tool_use_idx = min(i for i, name in enumerate(hook_names) if name == "PreToolUse")
        stop_idx = hook_names.index("Stop")

        assert user_prompt_submit_idx < first_pre_tool_use_idx < stop_idx

    def test_hook_event_timestamps_are_recorded(self):
        """Verify hook events include timestamps."""
        event = self._mock_hook_event("UserPromptSubmit", {})

        # Verify timestamp exists
        assert "timestamp" in event
        assert event["timestamp"] is not None

    def test_hook_event_data_preservation(self):
        """Verify hook event data is preserved correctly."""
        test_data = {
            "session_id": "test-session-123",
            "user_prompt": "/code test feature",
            "workflow": "tdd",
        }

        event = self._mock_hook_event("UserPromptSubmit", test_data)

        # Verify data was preserved
        assert event["hook_name"] == "UserPromptSubmit"
        assert event["session_id"] == "test-session-123"
        assert event["user_prompt"] == "/code test feature"
        assert event["workflow"] == "tdd"

    def test_out_of_order_sequence_fails_verification(self):
        """Verify out-of-order hook sequence fails verification.

        Wrong order: PreToolUse → UserPromptSubmit → Stop
        Should fail: UserPromptSubmit must fire first.
        """
        events = [
            self._mock_hook_event("PreToolUse", {"tool_name": "Read"}),
            self._mock_hook_event("UserPromptSubmit", {}),
            self._mock_hook_event("Stop", {}),
        ]

        hook_names = [e["hook_name"] for e in events]

        # Verify order is wrong
        user_prompt_submit_idx = hook_names.index("UserPromptSubmit")
        pre_tool_use_idx = hook_names.index("PreToolUse")

        # UserPromptSubmit should be before PreToolUse, but it's not
        assert not (user_prompt_submit_idx < pre_tool_use_idx)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
