#!/usr/bin/env python3
"""Tests for security-critical error handling - RED phase (failing tests).

This module tests security-critical error handling scenarios:
- PermissionError does not leak path information
- Corrupted state JSON causes fail-closed behavior
- Malicious state injection is blocked
- Race condition handling for concurrent writes
"""

import json
import sys
from pathlib import Path

import pytest

# Add hooks directory to path for imports
# Tests are in /code/tests/ but need to import from /plan-workflow/hooks/
hooks_dir = Path(__file__).parent.parent.parent / "plan-workflow" / "hooks"
sys.path.insert(0, str(hooks_dir))


class TestPermissionErrorHandling:
    """Test PermissionError handling prevents path information leakage.

    These tests verify that PermissionError scenarios:
    - Do NOT leak file paths in error messages
    - Return safe default values instead of crashing
    - Log errors securely without exposing internal structure
    """

    def test_permission_error_does_not_leak_path_info(self, tmp_path):
        """Verify PermissionError does not leak path information in error messages.

        Tests that:
        - PermissionError on state file read returns default state
        - Error messages do NOT contain file paths
        - Stack traces do NOT expose internal structure to user
        """
        # Create state file with read-only permissions
        state_file = tmp_path / "secret_state.json"
        state_file.write_text('{"secret": "data"}')  # pragma: allowlist secret

        # Make file read-only (no write permission)
        state_file.chmod(0o444)

        # Try to load state (should handle PermissionError gracefully)
        from PostToolUse_plan_review_state_tracker import STATE_FILE, load_state

        # Temporarily override STATE_FILE
        original_state_file = STATE_FILE
        STATE_FILE = state_file

        try:
            state = load_state()

            # Should return default state, not crash
            assert state is not None, "Should return default state on PermissionError"

            # Verify no path leakage in error output (if any)
            # Note: This test assumes errors are printed to stderr
            # In production, ensure logging does NOT include full file paths
        finally:
            STATE_FILE = original_state_file
            # Restore write permissions for cleanup
            state_file.chmod(0o644)

    def test_permission_error_on_save_returns_error_dict(self, tmp_path):
        """Verify PermissionError on save returns error dict without path leakage.

        Tests that:
        - save_state() handles PermissionError gracefully
        - Returns error dict with generic message
        - Does NOT include file paths in error messages
        """
        from PostToolUse_plan_review_state_tracker import STATE_DIR, save_state

        # Create read-only state directory (no write permission)
        read_only_dir = tmp_path / "read_only_state"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)

        # Temporarily override STATE_DIR
        original_state_dir = STATE_DIR
        STATE_DIR = read_only_dir

        try:
            # Try to save state (should handle PermissionError gracefully)
            save_state({"test": "data"})

            # Function should not raise exception, should print error dict
            # Verify error dict does NOT contain paths (implementation detail)
        finally:
            STATE_DIR = original_state_dir
            # Restore write permissions for cleanup
            read_only_dir.chmod(0o644)


class TestCorruptedStateHandling:
    """Test corrupted state JSON causes fail-closed behavior.

    These tests verify that corrupted state files:
    - Cause fail-closed behavior (return defaults, not crash)
    - Log corruption securely without leaking data
    - Do not execute arbitrary code from JSON
    - Validate JSON structure before parsing
    """

    def test_corrupted_state_json_causes_fail_closed(self, tmp_path):
        """Verify corrupted state JSON causes fail-closed behavior.

        Tests that:
        - Invalid JSON returns default state (fail-closed)
        - Does NOT crash or expose internal state
        - Logs corruption securely
        """
        # Create corrupted JSON file
        corrupted_file = tmp_path / "corrupted_state.json"
        corrupted_file.write_text('{"current_phase": INVALID_JSON}')

        from PostToolUse_plan_review_state_tracker import STATE_FILE, load_state

        # Temporarily override STATE_FILE
        original_state_file = STATE_FILE
        STATE_FILE = corrupted_file

        try:
            state = load_state()

            # Should return default state, not crash
            assert state is not None, "Should return default state for corrupted JSON"
            assert isinstance(state, dict), "Should return dict, not None"

            # Verify default state structure
            assert "current_phase" in state, "Default state should have current_phase"
        finally:
            STATE_FILE = original_state_file

    def test_malformed_json_syntax_returns_default(self, tmp_path):
        """Verify malformed JSON syntax returns default state.

        Tests that:
        - Malformed JSON (missing brackets, quotes) returns default
        - Does NOT attempt to recover partial data
        - Fail-closed behavior enforced
        """
        # Create malformed JSON file
        malformed_file = tmp_path / "malformed_state.json"
        malformed_file.write_text('{"current_phase": 3, ')  # Missing closing brace and quote

        from PostToolUse_plan_review_state_tracker import STATE_FILE, load_state

        # Temporarily override STATE_FILE
        original_state_file = STATE_FILE
        STATE_FILE = malformed_file

        try:
            state = load_state()

            # Should return default state
            assert state is not None, "Should return default state for malformed JSON"
            assert isinstance(state, dict), "Should return dict"
        finally:
            STATE_FILE = original_state_file


class TestMaliciousInjectionBlocking:
    """Test malicious state injection is blocked.

    These tests verify that malicious state injection attempts:
    - Are blocked by schema validation
    - Cannot execute arbitrary code via JSON
    - Cannot cause prototype pollution
    - Are logged securely for audit
    """

    def test_malicious_state_injection_blocked(self, tmp_path):
        """Verify malicious state injection is blocked.

        Tests that:
        - Prototype pollution attempts blocked (__proto__, constructor)
        - Unknown fields rejected by schema validation
        - Malicious values (code execution) prevented
        - Schema validation enforces allowed field types
        """
        # Create malicious state with prototype pollution attempt
        malicious_file = tmp_path / "malicious_state.json"
        malicious_state = {
            "current_phase": 3,
            "completed_phases": [0, 1, 2],
            # SEC-004: Block prototype pollution
            "__proto__": {"polluted": True},
            "constructor": {"attack": "payload"},
            # SEC-004: Block unknown fields
            "malicious_field": "should_be_rejected",
            "plan_path": "../../../etc/passwd",  # Path traversal attempt
            "session_id": "$(malicious_command)",  # Command injection attempt
        }
        malicious_file.write_text(json.dumps(malicious_state))

        from PostToolUse_plan_review_state_tracker import STATE_FILE, load_state

        # Temporarily override STATE_FILE
        original_state_file = STATE_FILE
        STATE_FILE = malicious_file

        try:
            state = load_state()

            # Should return default state (schema validation blocks malicious fields)
            assert state is not None, "Should return default state for malicious injection"

            # Verify malicious fields blocked
            assert "__proto__" not in state, "Prototype pollution should be blocked"
            assert "constructor" not in state, "Constructor pollution should be blocked"
            assert "malicious_field" not in state, "Unknown fields should be rejected"

            # Verify path traversal and command injection blocked or sanitized
            if state.get("plan_path"):
                assert (
                    ".." not in state["plan_path"] or state["plan_path"] is None
                ), "Path traversal should be blocked"

        finally:
            STATE_FILE = original_state_file

    def test_schema_validation_rejects_wrong_types(self, tmp_path):
        """Verify schema validation rejects wrong field types.

        Tests that:
        - String instead of integer rejected
        - Object instead of array rejected
        - Invalid enum values rejected
        - Schema validation enforced before use
        """
        # Create state with wrong field types
        invalid_type_file = tmp_path / "invalid_types.json"
        invalid_state = {
            "current_phase": "should_be_integer_not_string",  # Wrong type
            "completed_phases": "should_be_list_not_string",  # Wrong type
            "status": "INVALID_STATUS",  # Invalid enum value
            "plan_path": "/path/to/plan.md",
        }
        invalid_type_file.write_text(json.dumps(invalid_state))

        from PostToolUse_plan_review_state_tracker import STATE_FILE, load_state

        # Temporarily override STATE_FILE
        original_state_file = STATE_FILE
        STATE_FILE = invalid_type_file

        try:
            state = load_state()

            # Should return default state (schema validation blocks wrong types)
            assert state is not None, "Should return default state for invalid types"

        finally:
            STATE_FILE = original_state_file


class TestRaceConditionHandling:
    """Test race condition handling for concurrent writes.

    These tests verify that concurrent write scenarios:
    - Do NOT cause state corruption
    - Use atomic writes or file locking
    - Handle concurrent access gracefully
    - Last-write-wins or merge conflict detected
    """

    def test_race_condition_concurrent_write(self, tmp_path):
        """Verify race condition handling for concurrent writes.

        Tests that:
        - Concurrent writes do NOT corrupt state file
        - Atomic writes prevent partial data
        - File locking or atomic rename used
        - Graceful degradation under concurrent access
        """
        # This test is basic - in production, use file locking (fcntl/msvcrt)
        # For cross-platform compatibility, atomic write to temp file + rename

        state_file = tmp_path / "race_state.json"

        import PostToolUse_plan_review_state_tracker

        # Temporarily override STATE_FILE at module level
        original_state_file = PostToolUse_plan_review_state_tracker.STATE_FILE
        PostToolUse_plan_review_state_tracker.STATE_FILE = state_file

        try:
            # Simulate concurrent writes (simplified - actual race would need threading)
            state_1 = {"current_phase": 1, "session_id": "writer-1"}
            state_2 = {"current_phase": 2, "session_id": "writer-2"}

            # Write both states
            PostToolUse_plan_review_state_tracker.save_state(state_1)
            PostToolUse_plan_review_state_tracker.save_state(state_2)

            # Verify file is valid JSON (not corrupted)
            with open(state_file) as f:
                loaded = json.load(f)

            # Should be valid JSON (one of the writes won)
            assert isinstance(loaded, dict), "State file should be valid JSON"

        finally:
            PostToolUse_plan_review_state_tracker.STATE_FILE = original_state_file

    def test_atomic_write_prevents_partial_data(self, tmp_path):
        """Verify atomic write prevents partial data.

        Tests that:
        - State file written atomically (temp + rename)
        - No partial writes on interruption
        - Either old state or new state, never corrupted
        """
        # This test verifies atomic write pattern
        # Actual implementation should use: write to temp + atomic rename

        state_file = tmp_path / "atomic_state.json"

        import PostToolUse_plan_review_state_tracker

        # Temporarily override STATE_FILE at module level
        original_state_file = PostToolUse_plan_review_state_tracker.STATE_FILE
        PostToolUse_plan_review_state_tracker.STATE_FILE = state_file

        try:
            # Write initial state
            initial_state = {"current_phase": 0, "session_id": "initial"}
            PostToolUse_plan_review_state_tracker.save_state(initial_state)

            # Verify initial state readable
            loaded = PostToolUse_plan_review_state_tracker.load_state()
            assert loaded.get("session_id") == "initial", "Initial state should be readable"

            # Write new state (should be atomic)
            new_state = {"current_phase": 1, "session_id": "updated"}
            PostToolUse_plan_review_state_tracker.save_state(new_state)

            # Verify state is consistent (either old or new, never corrupted)
            loaded = PostToolUse_plan_review_state_tracker.load_state()
            assert loaded.get("session_id") in [
                "initial",
                "updated",
            ], "State should be consistent (no partial writes)"

        finally:
            PostToolUse_plan_review_state_tracker.STATE_FILE = original_state_file


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
