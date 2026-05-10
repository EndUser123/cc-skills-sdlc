"""
Test for PERF-004: load_arch_config() caching in config.py

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
Run with: pytest P:\\\\\\.claude/skills/arch/tests/test_config_caching.py -v

Purpose: Verify that load_arch_config() implements caching to minimize
file system checks. Currently, the function checks file existence on
every call without caching.

Issue: PERF-004 - load_arch_config() checks file existence every call without cache
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

import sys

# Add the .claude directory to path for package imports
claude_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(claude_path))

from skill.config import load_arch_config, clear_config_cache


@pytest.fixture(autouse=True)
def clear_cache_before_each_test():
    """Clear the config cache before each test to ensure isolation."""
    clear_config_cache()
    yield
    clear_config_cache()


class TestLoadArchConfigCacheImplementation:
    """
    Tests for the EXPECTED caching implementation.

    These tests will FAIL until caching is properly implemented.
    They document the target behavior for the GREEN phase.
    """

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory with .arch/config.json for testing."""
        arch_dir = tmp_path / ".arch"
        arch_dir.mkdir()
        config_file = arch_dir / "config.json"
        config_file.write_text(json.dumps({"default_domain": "python", "output_size": "normal"}))
        return tmp_path

    def test_cached_call_should_not_check_file_existence(self, temp_config_dir: Path):
        """
        Test that cached calls don't check file existence.

        Given: load_arch_config() has been called once (cached)
        When: Calling load_arch_config() again with same file paths
        Then: Should NOT call Path.exists() (use cached result)

        This test will FAIL until caching is implemented.
        """
        # Arrange - Track Path.exists() calls
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            with patch("pathlib.Path.read_text") as mock_read:
                mock_read.return_value = json.dumps(
                    {"default_domain": "python", "output_size": "normal"}
                )

                # Act - First call (should check)
                result1 = load_arch_config()
                first_call_count = mock_exists.call_count

                # Act - Second call (should use cache, NOT check)
                result2 = load_arch_config()
                second_call_count = mock_exists.call_count

                # Assert - Second call should NOT have checked file existence
                assert first_call_count >= 2, "First call should check paths"
                assert (
                    second_call_count == first_call_count
                ), "Second call should use cache, no additional exists() calls"
                assert result1 == result2

    def test_cache_invalidation_on_mtime_change(self, tmp_path: Path):
        """
        Test that cache invalidates when file modification time changes.

        Given: load_arch_config() has been called and result cached
        When: File mtime changes and load_arch_config() is called again
        Then: Should reload file (cache invalidated) and return new value

        TEST-ARCH-005: Verifies config cache invalidation works correctly.
        Cache is implemented with mtime tracking in config.py.
        """
        import json
        import time

        # Create a config file
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(json.dumps({"default_domain": "python"}))

        # Change to temp directory so config file is found
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Clear cache to start fresh
            clear_config_cache()

            # First call - should load from file
            result1 = load_arch_config()
            assert result1 is not None, "First call should return config"
            assert result1["default_domain"] == "python"

            # Modify file - wait for mtime change (filesystem granularity)
            time.sleep(0.05)  # Ensure mtime is different
            config_file.write_text(json.dumps({"default_domain": "cli"}))

            # Second call - should detect mtime change and reload
            result2 = load_arch_config()
            assert result2 is not None, "Second call should return config"
            assert (
                result2["default_domain"] == "cli"
            ), "Cache should be invalidated and new value loaded"
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
