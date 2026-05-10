"""
Integration tests for load_arch_config() with real file I/O.

These tests verify the complete config loading workflow using REAL files,
not mocks. This addresses TEST-007: Missing integration test for complete
config loading workflow.

Unlike test_config_validation.py which mocks Path.exists() and Path.read_text(),
these tests create actual config files on disk and verify load_arch_config()
correctly loads them.

Run with: pytest P:\\\\\\.claude/skills/arch/tests/test_config_integration.py -v
"""

import json
import sys
from pathlib import Path

import pytest

# Add parent directory to path for importing config module
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLoadArchConfigWithRealFiles:
    """Integration tests for load_arch_config() with real file I/O."""

    def test_load_arch_config_with_real_files(self, tmp_path, monkeypatch):
        """
        Test complete config loading workflow with real files.

        This test creates actual config files in a temporary directory and
        verifies that load_arch_config() correctly loads them from disk.

        Given: A temporary directory with real .archconfig.json file
        When: load_arch_config() is called with cwd set to tmp_path
        Then: Returns dict with config values from the real file

        This is an INTEGRATION test - no mocking, real file I/O.
        """
        # Arrange - Create real config file in temp directory
        config_data = {
            "default_domain": "python",
            "output_size": "normal",
            "evidence_level": "standard",
        }

        config_file = tmp_path / ".archconfig.json"
        # Write REAL file to disk (no mocking)
        config_file.write_text(json.dumps(config_data))

        # Change cwd to tmp_path so load_arch_config finds our project config
        monkeypatch.chdir(tmp_path)

        # Clear any env vars that might interfere
        monkeypatch.delenv("ARCH_DEFAULT_DOMAIN", raising=False)
        monkeypatch.delenv("ARCH_OUTPUT_SIZE", raising=False)
        monkeypatch.delenv("ARCH_EVIDENCE_LEVEL", raising=False)

        # Act - Call load_arch_config with REAL file on disk
        from config import load_arch_config

        result = load_arch_config()

        # Assert - Verify the config was loaded correctly from the real file
        assert result is not None, "load_arch_config should return a dict when config file exists"
        assert isinstance(result, dict), "Result should be a dictionary"

        # Verify all expected keys are present
        assert "default_domain" in result, "Result should contain default_domain key"
        assert "output_size" in result, "Result should contain output_size key"
        assert "evidence_level" in result, "Result should contain evidence_level key"

        # Verify values match what was written to the real file
        assert (
            result["default_domain"] == "python"
        ), f"Expected default_domain='python', got '{result.get('default_domain')}'"
        assert (
            result["output_size"] == "normal"
        ), f"Expected output_size='normal', got '{result.get('output_size')}'"
        assert (
            result["evidence_level"] == "standard"
        ), f"Expected evidence_level='standard', got '{result.get('evidence_level')}'"

    def test_load_arch_config_no_files_returns_none(self, tmp_path, monkeypatch):
        """
        Test that load_arch_config returns None when no config files exist.

        Given: A temporary directory with NO .arch/config.json file
        When: load_arch_config() is called
        Then: Returns None

        This verifies the function handles missing files correctly with real I/O.
        """
        # Arrange - tmp_path is empty, no .arch directory
        monkeypatch.chdir(tmp_path)

        # Clear env vars
        monkeypatch.delenv("ARCH_DEFAULT_DOMAIN", raising=False)
        monkeypatch.delenv("ARCH_OUTPUT_SIZE", raising=False)
        monkeypatch.delenv("ARCH_EVIDENCE_LEVEL", raising=False)

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        assert result is None, "load_arch_config should return None when no config files exist"

    def test_load_arch_config_with_invalid_json_raises_error(self, tmp_path, monkeypatch):
        """
        Test that load_arch_config raises JSONDecodeError for malformed JSON.

        Given: A .archconfig.json file with invalid JSON
        When: load_arch_config() is called
        Then: Raises json.JSONDecodeError

        This verifies error handling with real malformed file.
        """
        # Arrange - Create config file with invalid JSON
        config_file = tmp_path / ".archconfig.json"
        # Write INVALID JSON to real file
        config_file.write_text('{"default_domain": "python", invalid json}')

        monkeypatch.chdir(tmp_path)

        # Clear env vars
        monkeypatch.delenv("ARCH_DEFAULT_DOMAIN", raising=False)
        monkeypatch.delenv("ARCH_OUTPUT_SIZE", raising=False)
        monkeypatch.delenv("ARCH_EVIDENCE_LEVEL", raising=False)

        # Act & Assert
        from config import load_arch_config
        import json

        with pytest.raises(json.JSONDecodeError):
            load_arch_config()

    def test_load_arch_config_precedence_with_real_files(self, tmp_path, monkeypatch):
        """
        Test config precedence with real files: project config overrides user config.

        This test creates BOTH user and project config files as real files
        and verifies that project config takes precedence.

        Given: Both user (~/.archconfig.json) and project (.archconfig.json) configs exist
        When: load_arch_config() is called
        Then: Project config values override user config values

        This is an INTEGRATION test - no mocking, real file I/O for BOTH configs.
        """
        # Arrange - Create user config directory structure
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        user_config_data = {
            "default_domain": "python",
            "output_size": "small",
            "evidence_level": "standard",
        }

        user_config_file = fake_home / ".archconfig.json"
        user_config_file.write_text(json.dumps(user_config_data))

        # Create project config directory structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        project_config_data = {
            "default_domain": "cli",  # Different from user config
            "output_size": "large",  # Different from user config
        }

        project_config_file = project_dir / ".archconfig.json"
        project_config_file.write_text(json.dumps(project_config_data))

        # Set up environment to point to our fake home directory
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))

        # Change cwd to project directory so project config is found
        monkeypatch.chdir(project_dir)

        # Clear any ARCH env vars that might interfere
        monkeypatch.delenv("ARCH_DEFAULT_DOMAIN", raising=False)
        monkeypatch.delenv("ARCH_OUTPUT_SIZE", raising=False)
        monkeypatch.delenv("ARCH_EVIDENCE_LEVEL", raising=False)

        # Act - Call load_arch_config with REAL files on disk
        from config import load_arch_config

        result = load_arch_config()

        # Assert - Project config should override user config
        assert result is not None, "load_arch_config should return a dict when config files exist"
        assert isinstance(result, dict), "Result should be a dictionary"

        # Project config values should win
        assert (
            result["default_domain"] == "cli"
        ), f"Expected default_domain='cli' from project config, got '{result.get('default_domain')}'"
        assert (
            result["output_size"] == "large"
        ), f"Expected output_size='large' from project config, got '{result.get('output_size')}'"

        # User config value should be preserved for non-overlapping key
        assert (
            result["evidence_level"] == "standard"
        ), f"Expected evidence_level='standard' from user config (preserved), got '{result.get('evidence_level')}'"

    def test_load_arch_config_with_invalid_domain_raises_error(self, tmp_path, monkeypatch):
        """
        Test that load_arch_config raises ValueError for invalid domain.

        Given: A .archconfig.json file with invalid default_domain value
        When: load_arch_config() is called
        Then: Raises ValueError with descriptive message

        This validates domain checking with real file I/O.
        """
        # Arrange - Create config file with invalid domain
        config_file = tmp_path / ".archconfig.json"
        # Write config with invalid domain to real file
        config_file.write_text(
            json.dumps(
                {
                    "default_domain": "invalid_domain_name",
                    "output_size": "normal",
                }
            )
        )

        monkeypatch.chdir(tmp_path)

        # Clear env vars
        monkeypatch.delenv("ARCH_DEFAULT_DOMAIN", raising=False)
        monkeypatch.delenv("ARCH_OUTPUT_SIZE", raising=False)
        monkeypatch.delenv("ARCH_EVIDENCE_LEVEL", raising=False)

        # Act & Assert
        from config import load_arch_config

        with pytest.raises(ValueError) as exc_info:
            load_arch_config()

        # Verify error message mentions the invalid domain
        error_msg = str(exc_info.value).lower()
        assert (
            "invalid_domain_name" in error_msg
        ), f"Error message should mention invalid domain 'invalid_domain_name', got: {exc_info.value}"
        assert (
            "default_domain" in error_msg or "invalid" in error_msg
        ), f"Error should mention default_domain or invalid, got: {exc_info.value}"
