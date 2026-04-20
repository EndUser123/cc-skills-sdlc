"""
Characterization tests for partial config merging behavior in load_arch_config().

These tests CAPTURE CURRENT BEHAVIOR of partial config merging.

The existing implementation at config.py line 88 uses dictionary unpacking:
    config = {**user_config, **project_config}

This correctly handles partial merging:
1. Keys from project_config override matching keys in user_config (project wins)
2. Keys from user_config that don't exist in project_config are preserved

This addresses TEST-001: Missing partial config merging test.
These tests verify that the partial merge logic works as intended.

Run with: pytest P:/.claude/skills/arch/tests/test_config_merging.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch


# Add parent directory to path for importing config module
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPartialConfigMerging:
    """Tests for partial config merging behavior."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_partial_merge_project_overrides_user_preserves_others(self, mock_read, mock_exists):
        """
        Test that partial merge correctly overrides matching keys while preserving non-overlapping user keys.

        Given: User config has {'default_domain': 'python', 'output_size': 'small'}
              Project config has {'default_domain': 'cli'} (only one key)
        When: load_arch_config() is called
        Then: Merged result has:
              - default_domain='cli' (project wins for overlapping key)
              - output_size='small' (user preserved for non-overlapping key)
        """
        # Arrange
        # First call checks project config, second checks user config
        mock_exists.side_effect = [True, True]
        # First read returns project config (partial), second returns user config
        mock_read.side_effect = [
            json.dumps({"default_domain": "cli"}),  # Project config: only default_domain
            json.dumps(
                {"default_domain": "python", "output_size": "small"}
            ),  # User config: both keys
        ]

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        # Project config should override the overlapping key
        assert result["default_domain"] == "cli", (
            f"Expected default_domain='cli' from project config, "
            f"but got '{result.get('default_domain')}'"
        )

        # User config value should be preserved for non-overlapping key
        assert result["output_size"] == "small", (
            f"Expected output_size='small' from user config (preserved), "
            f"but got '{result.get('output_size')}'"
        )

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_partial_merge_multiple_keys_from_user_preserved(self, mock_read, mock_exists):
        """
        Test that partial merge preserves all non-overlapping keys from user config.

        Given: User config has {'default_domain': 'python', 'output_size': 'small', 'evidence_level': 'high'}
              Project config has {'default_domain': 'cli'} (only one key)
        When: load_arch_config() is called
        Then: Merged result has:
              - default_domain='cli' (project wins)
              - output_size='small' (user preserved)
              - evidence_level='high' (user preserved)
        """
        # Arrange
        mock_exists.side_effect = [True, True]
        mock_read.side_effect = [
            json.dumps({"default_domain": "cli"}),  # Project config: only default_domain
            json.dumps(
                {
                    "default_domain": "python",
                    "output_size": "small",
                    "evidence_level": "high",
                }
            ),  # User config: all three keys
        ]

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert
        assert result["default_domain"] == "cli"
        assert result["output_size"] == "small"
        assert result["evidence_level"] == "high"

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_partial_merge_user_has_subset_project_has_superset(self, mock_read, mock_exists):
        """
        Test partial merge where user config has fewer keys than project config.

        Given: User config has {'default_domain': 'python'} (only one key)
              Project config has {'default_domain': 'cli', 'output_size': 'large'}
        When: load_arch_config() is called
        Then: Merged result has both keys from project config
        """
        # Arrange
        mock_exists.side_effect = [True, True]
        mock_read.side_effect = [
            json.dumps(
                {"default_domain": "cli", "output_size": "large"}
            ),  # Project config: both keys
            json.dumps({"default_domain": "python"}),  # User config: only default_domain
        ]

        # Act
        from config import load_arch_config

        result = load_arch_config()

        # Assert - project config completely overrides user
        assert result["default_domain"] == "cli"
        assert result["output_size"] == "large"
