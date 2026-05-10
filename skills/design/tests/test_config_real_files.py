"""
Integration tests using real .archconfig.json files.

These tests use actual config files (not environment variables) to verify
config file loading works correctly. This complements the environment variable
tests and ensures full integration coverage.

Run with: pytest P:\\\\\\packages/arch/skill/tests/test_config_real_files.py -v

Purpose: Verify config file loading without ARCH_* env vars set (Action 6b)
Issue: Tests should fail appropriately when config files are malformed (Action 6c)
"""

import json
import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path for importing config module
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import clear_config_cache, load_arch_config


@pytest.fixture(autouse=True)
def clean_arch_env_vars():
    """Ensure no ARCH_* environment variables interfere with tests."""
    env_backup = {}
    for key in list(os.environ.keys()):
        if key.startswith("ARCH_"):
            env_backup[key] = os.environ.pop(key)

    yield

    for key, value in env_backup.items():
        os.environ[key] = value


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the config cache before each test to ensure isolation."""
    clear_config_cache()
    yield
    clear_config_cache()


class TestRealConfigFileLoading:
    """
    Tests for loading config from actual .archconfig.json files.

    This test class verifies Action 6a: Create tests that use actual .archconfig.json files
    """

    def test_load_valid_project_config_file(self, tmp_path: Path):
        """
        Test loading a valid project config file.

        Given: A valid .archconfig.json file exists in the current directory
        When: load_arch_config() is called
        Then: Should return the config dict with correct values

        This test verifies Action 6a part 1: Valid config files load correctly
        """
        # Arrange - Create a valid config file
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(
            json.dumps(
                {"default_domain": "python", "output_size": "large", "evidence_level": "high"}
            )
        )

        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Act - Load config
            result = load_arch_config()

            # Assert - Should return valid config
            assert result is not None
            assert result["default_domain"] == "python"
            assert result["output_size"] == "large"
            assert result["evidence_level"] == "high"
        finally:
            os.chdir(original_cwd)

    def test_load_config_without_env_vars(self, tmp_path: Path):
        """
        Test loading config file when no ARCH_* env vars are set.

        Given: A valid .archconfig.json file exists and NO ARCH_* env vars are set
        When: load_arch_config() is called
        Then: Should return config from file only (no env var overrides)

        This test verifies Action 6b: Test config file loading without ARCH_* env vars set
        """
        # Arrange - Create config file and ensure no ARCH_* env vars
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(
            json.dumps({"default_domain": "data-pipeline", "output_size": "normal"})
        )

        # Verify no ARCH_* env vars are set (clean_arch_env_vars fixture ensures this)
        arch_vars = {k: v for k, v in os.environ.items() if k.startswith("ARCH_")}
        assert len(arch_vars) == 0, "No ARCH_* env vars should be set for this test"

        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Act - Load config without env vars
            result = load_arch_config()

            # Assert - Should return config from file only
            assert result is not None
            assert result["default_domain"] == "data-pipeline"
            assert result["output_size"] == "normal"
        finally:
            os.chdir(original_cwd)

    def test_malformed_json_fails_appropriately(self, tmp_path: Path):
        """
        Test that malformed JSON in config file fails appropriately.

        Given: A .archconfig.json file with malformed JSON exists
        When: load_arch_config() is called
        Then: Should raise json.JSONDecodeError

        This test verifies Action 6c part 1: Malformed JSON causes appropriate failure
        """
        # Arrange - Create malformed JSON file
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text('{"default_domain": "python", invalid json}')

        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Act & Assert - Should raise JSONDecodeError
            with pytest.raises(json.JSONDecodeError):
                load_arch_config()
        finally:
            os.chdir(original_cwd)

    def test_missing_required_field_fails_appropriately(self, tmp_path: Path):
        """
        Test that missing required field fails appropriately.

        Given: A .archconfig.json file missing required field 'default_domain'
        When: load_arch_config() is called
        Then: Should raise ValueError with descriptive message

        This test verifies Action 6c part 2: Missing required fields cause appropriate failure
        """
        # Arrange - Create config file missing required field
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(json.dumps({"output_size": "large"}))

        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Act & Assert - Should raise ValueError
            with pytest.raises(ValueError) as exc_info:
                load_arch_config()

            # Assert error message mentions missing field
            assert "default_domain" in str(exc_info.value).lower()
            assert (
                "required" in str(exc_info.value).lower()
                or "missing" in str(exc_info.value).lower()
            )
        finally:
            os.chdir(original_cwd)

    def test_invalid_domain_value_fails_appropriately(self, tmp_path: Path):
        """
        Test that invalid domain value fails appropriately.

        Given: A .archconfig.json file with invalid default_domain value
        When: load_arch_config() is called
        Then: Should raise ValueError with descriptive message

        This test verifies Action 6c part 3: Invalid values cause appropriate failure
        """
        # Arrange - Create config file with invalid domain
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(json.dumps({"default_domain": "invalid_domain"}))

        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Act & Assert - Should raise ValueError
            with pytest.raises(ValueError) as exc_info:
                load_arch_config()

            # Assert error message mentions invalid domain
            assert "default_domain" in str(exc_info.value).lower()
            assert "invalid" in str(exc_info.value).lower()
        finally:
            os.chdir(original_cwd)

    def test_invalid_output_size_value_fails_appropriately(self, tmp_path: Path):
        """
        Test that invalid output_size value fails appropriately.

        Given: A .archconfig.json file with invalid output_size value
        When: load_arch_config() is called
        Then: Should raise ValueError with descriptive message

        This test verifies Action 6c part 4: Invalid output_size causes appropriate failure
        """
        # Arrange - Create config file with invalid output_size
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(
            json.dumps({"default_domain": "python", "output_size": "invalid_size"})
        )

        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Act & Assert - Should raise ValueError
            with pytest.raises(ValueError) as exc_info:
                load_arch_config()

            # Assert error message mentions invalid output_size
            assert "output_size" in str(exc_info.value).lower()
            assert "invalid" in str(exc_info.value).lower()
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
