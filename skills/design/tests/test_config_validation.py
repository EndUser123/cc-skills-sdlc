"""
Test suite for load_arch_config() validation.

These tests verify the behavior of load_arch_config() function which:
1. Loads architecture configuration from multiple sources
2. Validates configuration values against schema
3. Merges configurations with precedence: env vars > project config > user config
4. Returns None when no config file exists

Run with: pytest P:/.claude/skills/arch/tests/test_config_validation.py -v
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path for importing config module
sys.path.insert(0, str(Path(__file__).parent.parent))


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


# Expected module path (implementation will be created in GREEN phase)
# from config import load_arch_config


class TestInvalidDomainValue:
    """Tests for invalid domain value validation."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_invalid_domain_value_raises_value_error(self, mock_read, mock_exists):
        """
        Test that invalid domain value raises ValueError.

        Given: A config file with invalid domain value
        When: load_arch_config() is called
        Then: ValueError is raised with descriptive message
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                "default_domain": "invalid_domain",
                "output_size": "normal",
                "evidence_level": "standard",
            }
        )

        # Act & Assert
        # Import will fail until function is implemented
        from config import load_arch_config

        with pytest.raises(ValueError) as exc_info:
            load_arch_config()

        assert "default_domain" in str(exc_info.value).lower()
        assert "invalid_domain" in str(exc_info.value)


class TestMissingRequiredField:
    """Tests for missing required field validation."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_missing_required_field_raises_value_error(self, mock_read, mock_exists):
        """
        Test that missing required field raises ValueError.

        Given: A config file missing required field 'default_domain'
        When: load_arch_config() is called
        Then: ValueError is raised with field name
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps({"output_size": "normal", "evidence_level": "standard"})

        # Act & Assert
        from config import load_arch_config

        with pytest.raises(ValueError) as exc_info:
            load_arch_config()

        assert (
            "default_domain" in str(exc_info.value).lower()
            or "required" in str(exc_info.value).lower()
        )


class TestMalformedJSON:
    """Tests for malformed JSON handling."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_malformed_json_raises_json_decode_error(self, mock_read, mock_exists):
        """
        Test that malformed JSON raises JSONDecodeError.

        Given: A config file with invalid JSON syntax
        When: load_arch_config() is called
        Then: JSONDecodeError is raised
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = '{default_domain": "python", invalid json}'

        # Act & Assert
        from config import load_arch_config

        with pytest.raises(json.JSONDecodeError):
            load_arch_config()


class TestValidConfig:
    """Tests for valid configuration loading."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_valid_config_returns_dict_with_default_domain(self, mock_read, mock_exists):
        """
        Test that valid config returns dict with default_domain.

        Given: A valid config file exists
        When: load_arch_config() is called
        Then: Returns dict with default_domain key
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps(
            {
                "default_domain": "python",
                "output_size": "normal",
                "evidence_level": "standard",
            }
        )

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        assert isinstance(result, dict)
        assert result["default_domain"] == "python"
        assert result["output_size"] == "normal"
        assert result["evidence_level"] == "standard"


class TestConfigPrecedence:
    """Tests for configuration precedence rules."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_project_config_overrides_user_config(self, mock_read, mock_exists):
        """
        Test that project config overrides user config.

        Given: Both user and project config files exist (no env vars set)
        When: load_arch_config() is called
        Then: Project config values take precedence over user config
        """
        # Arrange - First call checks project config, second checks user config
        mock_exists.side_effect = [True, True]
        # First read returns project config, second returns user config
        mock_read.side_effect = [
            json.dumps({"default_domain": "data-pipeline", "output_size": "large"}),
            json.dumps({"default_domain": "python", "output_size": "concise"}),
        ]

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        assert result["default_domain"] == "data-pipeline"  # Project wins
        assert result["output_size"] == "large"  # Project wins

    @patch.dict(os.environ, {"ARCH_DEFAULT_DOMAIN": "precedent"}, clear=True)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_env_var_overrides_config_files(self, mock_read, mock_exists):
        """
        Test that environment variable overrides config files.

        Given: Config files exist and ARCH_DEFAULT_DOMAIN env var is set
        When: load_arch_config() is called
        Then: Environment variable value takes precedence
        """
        # Arrange
        mock_exists.return_value = True
        mock_read.return_value = json.dumps({"default_domain": "python", "output_size": "normal"})

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        assert result["default_domain"] == "precedent"  # Env var wins

    @patch.dict(os.environ, {"ARCH_DEFAULT_DOMAIN": "auto"}, clear=True)
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_env_var_always_overrides_even_when_both_configs_have_different_values(
        self, mock_read, mock_exists
    ):
        """
        Test that env var ALWAYS overrides, even when both user and project configs exist
        with different values for the same key.

        Given: Both user and project configs exist with DIFFERENT default_domain values,
               and ARCH_DEFAULT_DOMAIN env var is set
        When: load_arch_config() is called
        Then: Environment variable value takes precedence (env var always wins)

        This tests that environment variables have highest priority regardless of
        user/project config values.
        """
        # Arrange - Both configs exist
        mock_exists.side_effect = [True, True]
        # First read returns project config, second returns user config
        mock_read.side_effect = [
            json.dumps({"default_domain": "data-pipeline"}),  # Project config
            json.dumps({"default_domain": "python"}),  # User config (different value)
        ]

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        # Env var "auto" wins, even though user and project configs have different values
        assert result["default_domain"] == "auto"


class TestMissingConfigFile:
    """Tests for missing configuration file handling."""

    @patch("pathlib.Path.exists")
    def test_missing_config_file_returns_none(self, mock_exists):
        """
        Test that missing config file returns None.

        Given: No config file exists
        When: load_arch_config() is called
        Then: Returns None
        """
        # Arrange
        mock_exists.return_value = False

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        assert result is None
