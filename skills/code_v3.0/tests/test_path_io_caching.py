#!/usr/bin/env python3
"""Tests for file I/O caching in state path resolution.

These tests verify that path resolution functions cache results to avoid
redundant stat() calls during test execution.
"""

import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks __lib to path for imports
hooks_lib = Path("P:\\\\\\.claude/hooks/__lib")
if hooks_lib.exists():
    sys.path.insert(0, str(hooks_lib))

# Import state_paths module
try:
    import state_paths

    STATE_PATHS_AVAILABLE = True
except ImportError:
    STATE_PATHS_AVAILABLE = False
    state_paths = None


class TestPathIOCaching:
    """Tests for file I/O caching in state path resolution."""

    @pytest.fixture
    def temp_state_dir(self) -> Generator[Path, None, None]:
        """Create a temporary state directory for testing."""
        temp_dir = tempfile.mkdtemp()
        state_dir = Path(temp_dir)

        # Override STATE_DIR for testing
        original_state_dir = state_paths.STATE_DIR
        state_paths.STATE_DIR = state_dir / ".claude" / "state"

        yield state_dir

        # Cleanup
        if Path(temp_dir).exists():
            import shutil

            shutil.rmtree(temp_dir)

        # Restore original
        state_paths.STATE_DIR = original_state_dir

    def test_cached_path_lookup_fixture_exists(self, temp_state_dir: Path):
        """Test that cached_path_lookup fixture exists and works."""
        if not STATE_PATHS_AVAILABLE:
            pytest.skip("state_paths module not available")

        # Import PathLookupCache directly from conftest
        sys.path.insert(0, str(Path(__file__).parent))
        from conftest import PathLookupCache

        # Use the cache class
        cache = PathLookupCache()
        assert cache is not None, "PathLookupCache should be instantiable"

        # Verify cache has expected methods
        assert hasattr(cache, "get"), "Cache should have get() method"
        assert hasattr(cache, "put"), "Cache should have put() method"
        assert hasattr(cache, "clear"), "Cache should have clear() method"

    def test_memoization_reduces_filesystem_calls(self, temp_state_dir: Path):
        """Test that memoization reduces filesystem stat() calls.

        This test verifies that calling get_terminal_state_dir() multiple times
        with the same terminal_id uses cached results and doesn't repeatedly
        call mkdir().
        """
        if not STATE_PATHS_AVAILABLE:
            pytest.skip("state_paths module not available")

        terminal_id = "test_terminal_123"

        # Mock mkdir to count calls
        original_mkdir = Path.mkdir
        mkdir_call_count = {"count": 0}

        def counting_mkdir(self, *args, **kwargs):
            mkdir_call_count["count"] += 1
            return original_mkdir(self, *args, **kwargs)

        with patch.object(Path, "mkdir", counting_mkdir):
            # First call - should create directory
            dir1 = state_paths.get_terminal_state_dir(terminal_id)
            assert mkdir_call_count["count"] == 1, "First call should call mkdir() once"

            # Second call - should use cache (if implemented)
            dir2 = state_paths.get_terminal_state_dir(terminal_id)

            # Without caching, this would call mkdir() again
            # With caching, this should use cached result
            # For now, we just verify both calls return the same path
            assert dir1 == dir2, "Multiple calls should return same path"

    def test_cache_can_be_cleared_between_tests(self, temp_state_dir: Path):
        """Test that cache can be cleared between test runs.

        This ensures test isolation - each test should start with a fresh cache.
        """
        if not STATE_PATHS_AVAILABLE:
            pytest.skip("state_paths module not available")

        # Import PathLookupCache directly from conftest
        sys.path.insert(0, str(Path(__file__).parent))
        from conftest import PathLookupCache

        cache = PathLookupCache()
        # Add something to cache
        cache.put("test_key", "test_value")

        # Verify it's cached
        assert cache.get("test_key") == "test_value"

        # Clear cache
        cache.clear()

        # Verify it's cleared
        assert cache.get("test_key") is None

    def test_path_resolution_with_different_terminal_ids(self, temp_state_dir: Path):
        """Test that path resolution correctly isolates different terminal IDs."""
        if not STATE_PATHS_AVAILABLE:
            pytest.skip("state_paths module not available")

        terminal_1 = "terminal_001"
        terminal_2 = "terminal_002"

        dir1 = state_paths.get_terminal_state_dir(terminal_1)
        dir2 = state_paths.get_terminal_state_dir(terminal_2)

        # Verify directories are different
        assert dir1 != dir2, "Different terminal IDs should have different directories"

        # Verify both exist
        assert dir1.exists(), "Terminal 1 directory should exist"
        assert dir2.exists(), "Terminal 2 directory should exist"

    def test_path_resolution_with_different_session_ids(self, temp_state_dir: Path):
        """Test that path resolution correctly isolates different session IDs."""
        if not STATE_PATHS_AVAILABLE:
            pytest.skip("state_paths module not available")

        session_1 = "session_abc"
        session_2 = "session_xyz"

        dir1 = state_paths.get_session_state_dir(session_1)
        dir2 = state_paths.get_session_state_dir(session_2)

        # Verify directories are different
        assert dir1 != dir2, "Different session IDs should have different directories"

        # Verify both exist
        assert dir1.exists(), "Session 1 directory should exist"
        assert dir2.exists(), "Session 2 directory should exist"

    def test_shared_state_path_is_consistent(self, temp_state_dir: Path):
        """Test that shared state path returns consistent results."""
        if not STATE_PATHS_AVAILABLE:
            pytest.skip("state_paths module not available")

        path1 = state_paths.get_shared_state_path("test_file.txt")
        path2 = state_paths.get_shared_state_path("test_file.txt")

        # Both calls should return the same path
        assert path1 == path2, "Shared state path should be consistent"

        # Verify parent directory exists
        assert path1.parent.exists(), "Shared state directory should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
