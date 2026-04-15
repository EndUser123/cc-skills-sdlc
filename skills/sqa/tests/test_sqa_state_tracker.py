"""Tests for SQA state tracker persistence and concurrent access."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.sqa_state_tracker import (
    SQAState,
    LayerState,
    init_state,
    load_state,
    record_layer_complete,
    record_halt,
    clear_state,
    _get_state_path,
    _write_state,
)


class TestStatePersistence:
    """Test state persistence across writes and reads."""

    def test_init_state_creates_file(self, tmp_path):
        """Test that init_state writes a valid state file."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            state = init_state(target="P:/test", halt_on="HIGH")

            # Verify state structure
            assert state.target == "P:/test"
            assert state.halt_on == "HIGH"
            assert "L0" in state.layers
            assert "META" in state.layers  # Off-by-one fix
            assert len(state.layers) == 9  # L0-L7 + META

            # Verify file was written
            path = _get_state_path(state.session_id)
            assert path.exists()

            # Verify file can be loaded
            loaded = load_state(state.session_id)
            assert loaded is not None
            assert loaded.target == state.target
            assert len(loaded.layers) == 9

    def test_record_layer_complete_updates_file(self, tmp_path):
        """Test that recording layer completion updates state file."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            state = init_state(target="P:/test")

            # Record L1 completion
            updated = record_layer_complete("L1", findings=5)
            assert updated.layers["L1"].ran is True
            assert updated.layers["L1"].findings == 5

            # Verify persisted
            reloaded = load_state(state.session_id)
            assert reloaded.layers["L1"].ran is True
            assert reloaded.layers["L1"].findings == 5

    def test_record_halt_updates_file(self, tmp_path):
        """Test that recording halt updates state file."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            state = init_state(target="P:/test")

            # Record halt at L2
            updated = record_halt("L2")
            assert updated.halt_triggered_at == "L2"
            assert updated.layers["L2"].halt_triggered is True

            # Verify persisted
            reloaded = load_state(state.session_id)
            assert reloaded.halt_triggered_at == "L2"
            assert reloaded.layers["L2"].halt_triggered is True

    def test_clear_state_removes_file(self, tmp_path):
        """Test that clear_state removes the state file."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            state = init_state(target="P:/test")
            path = _get_state_path(state.session_id)
            assert path.exists()

            clear_state(state.session_id)
            assert not path.exists()


class TestStateCorruptionHandling:
    """Test state file corruption and error handling."""

    def test_load_missing_file_returns_none(self, tmp_path):
        """Test that loading non-existent file returns None."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            result = load_state(session_id="nonexistent")
            assert result is None

    def test_load_corrupt_json_returns_none(self, tmp_path):
        """Test that loading corrupt JSON returns None with logging."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            # Create a corrupt file
            path = tmp_path / "sqa_state_current.json"
            path.write_text("{invalid json")

            result = load_state()
            assert result is None  # Should not raise, just return None

    def test_load_invalid_schema_returns_none(self, tmp_path):
        """Test that loading valid JSON with invalid schema returns None."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            # Create a file with invalid schema
            path = tmp_path / "sqa_state_current.json"
            path.write_text(json.dumps({"invalid": "schema"}))

            result = load_state()
            assert result is None


class TestTerminalIsolation:
    """Test terminal-scoped state isolation."""

    def test_terminal_id_creates_separate_dirs(self, tmp_path):
        """Test that different terminal IDs create separate directories."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            with patch.dict(os.environ, {"CLAUDE_TERMINAL_ID": "term1"}):
                path1 = _get_state_path()
                assert "terminal_term1" in str(path1)

            with patch.dict(os.environ, {"CLAUDE_TERMINAL_ID": "term2"}):
                path2 = _get_state_path()
                assert "terminal_term2" in str(path2)

            # Paths should be different
            assert path1.parent != path2.parent

    def test_terminal_id_sanitization(self, tmp_path):
        """Test that terminal IDs are sanitized to prevent path traversal."""
        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            # Test with dangerous characters
            with patch.dict(os.environ, {"CLAUDE_TERMINAL_ID": "../../etc/traversal"}):
                path = _get_state_path()
                # Should sanitize to safe chars only
                assert "terminal_" in str(path)
                assert ".." not in str(path)


class TestConcurrentAccess:
    """Test concurrent write safety with file locking."""

    def test_concurrent_write_does_not_corrupt(self, tmp_path):
        """Test that concurrent writes don't corrupt state file."""
        try:
            from filelock import FileLock
        except ImportError:
            pytest.skip("filelock not available")

        with patch("lib.sqa_state_tracker.STATE_DIR", tmp_path):
            state = init_state(target="P:/test")

            # Simulate concurrent writes
            import threading

            results = []

            def write_layer(layer_name):
                try:
                    updated = record_layer_complete(layer_name, findings=1)
                    results.append(updated.layers[layer_name].ran)
                except Exception as e:
                    results.append(e)

            threads = [
                threading.Thread(target=write_layer, args=("L1",)),
                threading.Thread(target=write_layer, args=("L2",)),
                threading.Thread(target=write_layer, args=("L3",)),
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All writes should succeed
            assert len(results) == 3
            assert all(isinstance(r, bool) for r in results)

            # Final state should be valid JSON
            path = _get_state_path(state.session_id)
            data = json.loads(path.read_text())
            assert "layers" in data
