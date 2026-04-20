"""
Test for QUAL-003: Missing FileNotFoundError handling in load_contracts().

This test verifies that load_contracts() properly handles FileNotFoundError
when a non-existent contracts file path is provided.

Run with: pytest P:/.claude/skills/arch/tests/test_contracts_error_handling.py -v
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_templates import load_contracts


class TestLoadContractsFileNotFoundError:
    """Tests for FileNotFoundError handling in load_contracts()."""

    def test_load_contracts_missing_file_raises_error_with_helpful_message(
        self, tmp_path
    ):
        """
        Test that load_contracts raises FileNotFoundError with helpful message
        when contracts file does not exist.

        Given: A non-existent contracts file path
        When: load_contracts() is called
        Then: FileNotFoundError is raised with error message including file path

        QUAL-003: The function should handle FileNotFoundError gracefully with
        a helpful error message that includes the missing file path.
        """
        # Create a path to a non-existent file
        non_existent_path = tmp_path / "non_existent_contracts.yaml"

        # The test expects FileNotFoundError to be raised
        # with the file path included in the error message
        with pytest.raises(FileNotFoundError) as exc_info:
            load_contracts(non_existent_path)

        # Verify the error message includes the file path
        # Normalize paths for cross-platform comparison (Windows uses backslashes)
        error_message = str(exc_info.value)
        path_in_message = non_existent_path.name in error_message
        assert path_in_message, (
            f"Expected error message to include file name '{non_existent_path.name}', "
            f"but got: {error_message}"
        )

    def test_load_contracts_missing_file_helpful_error_content(self, tmp_path):
        """
        Test that load_contracts provides context about what went wrong.

        Given: A non-existent contracts file path (with generic filename)
        When: load_contracts() is called
        Then: FileNotFoundError provides helpful context about contracts

        QUAL-003: Error should indicate contracts file was not found.

        NOTE: Using generic filename 'missing.dat' to avoid false positives.
        Pytest creates test directories with names like 'test_load_contracts_*'
        which contain 'contract', so we must check the error message more carefully.

        This test FAILS because the current implementation just propagates
        the raw FileNotFoundError without adding helpful context about
        contracts/templates.
        """
        # Use a generic filename that doesn't contain 'template' or 'contracts'
        # Note: pytest may create directory names containing these words anyway
        non_existent_path = tmp_path / "missing.dat"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_contracts(non_existent_path)

        error_message = str(exc_info.value)

        # Verify the error contains the file name (path normalization for Windows)
        path_in_message = non_existent_path.name in error_message
        assert path_in_message, (
            f"Expected error message to include file name, got: {error_message}"
        )

        # Extract just the error text (not the path) to check for helpful context
        # Python's FileNotFoundError format: "[Errno 2] No such file or directory: 'path'"
        # We want to verify the implementation adds context BEFORE this standard message
        error_parts = error_message.split("'")
        error_text_only = error_parts[0] if error_parts else error_message

        # The error should mention "contracts" or "template" in the message itself
        # not just in the file path. This FAILS because current implementation
        # just propagates the raw FileNotFoundError.
        assert (
            "contract" in error_text_only.lower()
            or "template" in error_text_only.lower()
        ), (
            f"Expected helpful error message mentioning contracts/template, got: {error_message}"
        )
