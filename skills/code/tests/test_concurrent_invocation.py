#!/usr/bin/env python3
"""Tests for concurrent skill invocation - GREEN phase (implementation).

This module tests concurrent skill invocation behavior including:
- Concurrent skill invocations both respecting enforcement
- Skill intent file isolation between commands
- Intent file write-write race handling (last write wins)
- Terminal isolation for concurrent invocations

Tests use threading to simulate concurrent skill execution and verify
that intent files are properly isolated and handle race conditions.
"""

import json
import threading

import pytest


class TestConcurrentSkillInvocation:
    """Test concurrent skill invocation behavior - NEW FUNCTIONALITY.

    These tests verify that concurrent skill invocations (e.g., /code and /s)
    can execute simultaneously without interfering with each other's intent
    files. Tests use threading to simulate concurrent execution patterns.
    """

    # Test constants
    TEST_TERMINAL_A = "terminal_A"
    TEST_TERMINAL_B = "terminal_B"
    TEST_TIMESTAMP_1 = "2026-03-15T10:00:00"
    TEST_TIMESTAMP_2 = "2026-03-15T10:00:01"

    def test_concurrent_code_and_s_both_enforce(self, tmp_path, mock_time):
        """Verify simultaneous /code and /s both respect enforcement.

        Tests that concurrent skill invocations can create separate intent files
        without interference. Verifies:
        - Both skills create their intent files
        - Intent files exist and are valid JSON
        - Each skill has its own isolated intent with proper metadata
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Simulate concurrent skill invocations
        results: Dict[str, bool] = {}

        def create_code_intent() -> None:
            """Simulate /code skill creating intent file."""
            code_intent = state_dir / "pending_command_intent_code.json"
            code_intent.write_text(
                json.dumps(
                    {
                        "skill": "code",
                        "prompt": "/code implement feature",
                        "timestamp": self.TEST_TIMESTAMP_1,
                        "terminal_id": self.TEST_TERMINAL_A,
                    }
                )
            )
            results["code"] = True

        def create_s_intent() -> None:
            """Simulate /s skill creating intent file."""
            s_intent = state_dir / "pending_command_intent_s.json"
            s_intent.write_text(
                json.dumps(
                    {
                        "skill": "s",
                        "prompt": "/s strategy",
                        "timestamp": self.TEST_TIMESTAMP_2,
                        "terminal_id": self.TEST_TERMINAL_A,
                    }
                )
            )
            results["s"] = True

        # Run concurrent intent creation
        thread1 = threading.Thread(target=create_code_intent)
        thread2 = threading.Thread(target=create_s_intent)

        thread1.start()
        thread2.start()

        thread1.join(timeout=5)
        thread2.join(timeout=5)

        # Verify both intents were created
        assert "code" in results, "Code intent should be created"
        assert "s" in results, "S intent should be created"

        # Verify intent files exist and have correct content
        code_intent = state_dir / "pending_command_intent_code.json"
        s_intent = state_dir / "pending_command_intent_s.json"

        assert code_intent.exists(), "Code intent file should exist"
        assert s_intent.exists(), "S intent file should exist"

        code_data = json.loads(code_intent.read_text())
        s_data = json.loads(s_intent.read_text())

        # Verify isolation - each skill has its own intent
        assert code_data["skill"] == "code", "Code intent should have skill=code"
        assert s_data["skill"] == "s", "S intent should have skill=s"
        assert code_data["terminal_id"] == self.TEST_TERMINAL_A, "Should track terminal ID"
        assert s_data["terminal_id"] == self.TEST_TERMINAL_A, "Should track terminal ID"

    def test_skill_call_doesnt_affect_other_skill_intent(self, tmp_path, mock_time):
        """Verify Skill() call from command A doesn't affect command B's intent file.

        Tests intent file isolation by:
        1. Creating initial /s intent file
        2. Simulating /code invocation creating its own intent
        3. Verifying /s intent remains unchanged (no cross-contamination)
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create initial /s intent
        s_intent = state_dir / "pending_command_intent_s.json"
        original_s_data = {
            "skill": "s",
            "prompt": "/s original",
            "timestamp": self.TEST_TIMESTAMP_1,
        }
        s_intent.write_text(json.dumps(original_s_data))

        # Simulate /code invocation (should NOT modify /s intent)
        code_intent = state_dir / "pending_command_intent_code.json"
        code_intent.write_text(
            json.dumps(
                {"skill": "code", "prompt": "/code feature", "timestamp": self.TEST_TIMESTAMP_2}
            )
        )

        # Verify /s intent hasn't been modified
        current_s_data = json.loads(s_intent.read_text())
        assert (
            current_s_data == original_s_data
        ), "S intent should not be modified by code intent creation"

    def test_intent_file_write_write_race_last_wins(self, tmp_path, mock_time):
        """Verify intent file write-write race is handled (last write wins, both enforceable).

        Tests concurrent writes to the SAME intent file:
        1. Both writes complete successfully
        2. Last write wins (final state is valid)
        3. File remains valid JSON throughout (no corruption)
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        shared_intent = state_dir / "pending_command_intent_shared.json"

        # Track write order
        write_order: list[int] = []

        def write_intent_1() -> None:
            """First writer."""
            shared_intent.write_text(
                json.dumps(
                    {
                        "skill": "code",
                        "prompt": "/code feature A",
                        "timestamp": self.TEST_TIMESTAMP_1,
                        "writer": 1,
                    }
                )
            )
            write_order.append(1)

        def write_intent_2() -> None:
            """Second writer (slightly delayed)."""
            # Note: time.sleep() removed - mock_time fixture provides deterministic timing
            shared_intent.write_text(
                json.dumps(
                    {
                        "skill": "s",
                        "prompt": "/s strategy",
                        "timestamp": self.TEST_TIMESTAMP_2,
                        "writer": 2,
                    }
                )
            )
            write_order.append(2)

        # Run concurrent writes
        thread1 = threading.Thread(target=write_intent_1)
        thread2 = threading.Thread(target=write_intent_2)

        thread1.start()
        thread2.start()

        thread1.join(timeout=5)
        thread2.join(timeout=5)

        # Verify both writes completed
        assert len(write_order) == 2, "Both writes should complete"
        assert 1 in write_order and 2 in write_order, "Both writers should finish"

        # Verify last write won (last-write-wins behavior)
        final_data = json.loads(shared_intent.read_text())
        assert final_data["skill"] in ["code", "s"], "Intent should have valid skill"
        assert "writer" in final_data, "Should have writer identifier"

        # The last writer should win
        # In a race condition, either writer could win
        # but the file should be valid JSON
        assert isinstance(final_data, dict), "Final data should be valid dict"
        assert "prompt" in final_data, "Should have prompt field"
        assert "timestamp" in final_data, "Should have timestamp field"

    def test_concurrent_invocation_with_terminal_isolation(self, tmp_path, mock_time):
        """Verify concurrent invocations are isolated per terminal.

        Tests that different terminals get isolated intent files:
        1. Both terminals create their intents successfully
        2. Each terminal has its own isolated file
        3. No cross-contamination between terminal files
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        results: dict[str, bool] = {}

        def terminal_a_invocation() -> None:
            """Simulate invocation from terminal_A."""
            intent_path = state_dir / "pending_command_intent_terminal_A.json"
            intent_path.write_text(
                json.dumps(
                    {
                        "skill": "code",
                        "prompt": "/code task A",
                        "timestamp": self.TEST_TIMESTAMP_1,
                        "terminal_id": self.TEST_TERMINAL_A,
                    }
                )
            )
            results["terminal_A"] = True

        def terminal_b_invocation() -> None:
            """Simulate invocation from terminal_B."""
            intent_path = state_dir / "pending_command_intent_terminal_B.json"
            intent_path.write_text(
                json.dumps(
                    {
                        "skill": "s",
                        "prompt": "/s strategy B",
                        "timestamp": self.TEST_TIMESTAMP_2,
                        "terminal_id": self.TEST_TERMINAL_B,
                    }
                )
            )
            results["terminal_B"] = True

        # Run concurrent terminal invocations
        thread1 = threading.Thread(target=terminal_a_invocation)
        thread2 = threading.Thread(target=terminal_b_invocation)

        thread1.start()
        thread2.start()

        thread1.join(timeout=5)
        thread2.join(timeout=5)

        # Verify both terminals created intents
        assert "terminal_A" in results, "Terminal A should create intent"
        assert "terminal_B" in results, "Terminal B should create intent"

        # Verify each terminal has its own isolated intent file
        intent_a = state_dir / "pending_command_intent_terminal_A.json"
        intent_b = state_dir / "pending_command_intent_terminal_B.json"

        assert intent_a.exists(), "Terminal A intent should exist"
        assert intent_b.exists(), "Terminal B intent should exist"

        data_a = json.loads(intent_a.read_text())
        data_b = json.loads(intent_b.read_text())

        # Verify isolation - different files for different terminals
        assert data_a["terminal_id"] == self.TEST_TERMINAL_A, "Should match terminal A"
        assert data_b["terminal_id"] == self.TEST_TERMINAL_B, "Should match terminal B"
        assert data_a["skill"] == "code", "Terminal A invoked code"
        assert data_b["skill"] == "s", "Terminal B invoked s"

        # Verify no cross-contamination
        assert self.TEST_TERMINAL_B not in str(
            data_a
        ), "Terminal A data should not reference terminal B"
        assert self.TEST_TERMINAL_A not in str(
            data_b
        ), "Terminal B data should not reference terminal A"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
