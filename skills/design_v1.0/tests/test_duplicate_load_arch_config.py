"""
Test for QUAL-001: Duplicate load_arch_config in config.py and routing.py

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
Run with: pytest P:/.claude/skills/arch/tests/test_duplicate_load_arch_config.py -v

Purpose: Verify that routing.load_arch_config imports from config.py
instead of duplicating implementation (DRY principle violation).
"""

import inspect
import pytest
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path

# Add the .claude directory to path for package imports
claude_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(claude_path))

from skill import config
from skill import routing


class TestLoadArchConfigNotDuplicated:
    """Tests verifying load_arch_config is NOT duplicated across modules."""

    def test_routing_imports_load_arch_config_from_config(self):
        """
        Test that routing.load_arch_config is the SAME function object as config.load_arch_config.

        Given: Both config.py and routing.py are imported
        When: Comparing the function objects
        Then: They should be the SAME object (not duplicate implementations)

        This verifies that routing.py imports from config.py rather than duplicating.
        """
        # The function objects should be identical (same memory address)
        # This fails currently because routing.py has its own implementation
        assert routing.load_arch_config is config.load_arch_config, (
            "routing.load_arch_config should be the SAME function object as "
            "config.load_arch_config (imported, not duplicated)"
        )

    def test_only_one_load_arch_config_implementation(self):
        """
        Test that only ONE implementation of load_arch_config exists.

        Given: The arch skill modules
        When: Inspecting the source code of both modules
        Then: Only config.py should contain the implementation

        This checks that routing.py doesn't have its own implementation.
        """
        # Get source code of both modules
        config_source = inspect.getsource(config)
        routing_source = inspect.getsource(routing)

        # Both modules should have "load_arch_config" in their source
        # (routing.py should import it, config.py should define it)
        assert "load_arch_config" in config_source
        assert "load_arch_config" in routing_source

        # routing.py should IMPORT from config, not define its own
        # Check for import pattern like: from config import load_arch_config
        # or: from .config import load_arch_config (with or without other imports)
        has_import = any(
            pattern in routing_source
            for pattern in [
                "from config import load_arch_config",
                "from .config import load_arch_config",
                "from ..config import load_arch_config",
                "from .config import VALID_DOMAINS, load_arch_config",
                "from .config import load_arch_config, VALID_DOMAINS",
            ]
        )

        # This will fail if routing.py has its own implementation
        assert has_import, (
            "routing.py should import load_arch_config from config.py, "
            "not define its own implementation"
        )

        # Additionally verify routing.py doesn't have "def load_arch_config"
        has_def = "def load_arch_config" in routing_source
        assert not has_def, (
            "routing.py should NOT define its own load_arch_config function. "
            "It should import from config.py to follow DRY principle."
        )

    def test_load_arch_config_function_identity_same_result(self):
        """
        Test that calling routing.load_arch_config and config.load_arch_config
        return the SAME results (because they're the same function).

        Given: Both modules are imported
        When: Calling routing.load_arch_config() and config.load_arch_config()
        Then: Results should be identical (same object, same behavior)

        This ensures behavioral equivalence even if someone tries to "fix"
        the duplication by making the implementations match.
        """
        # Mock the environment to prevent actual config loading
        with patch.dict("os.environ", {}, clear=True):
            # Mock Path.exists() to return False (no config files)
            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = False

                # Call both functions
                config_result = config.load_arch_config()
                routing_result = routing.load_arch_config()

                # Results should be identical
                assert routing_result is config_result, (
                    "routing.load_arch_config() should return the same result as "
                    "config.load_arch_config() (same function = same result)"
                )

    def test_load_arch_config_same_signature(self):
        """
        Test that both functions have the EXACT same signature.

        Given: Both config.py and routing.py have load_arch_config
        When: Inspecting their function signatures
        Then: Signatures should be identical

        If they're the same function (imported), this passes trivially.
        If they're duplicates with different signatures, this catches it.
        """
        config_sig = inspect.signature(config.load_arch_config)
        routing_sig = inspect.signature(routing.load_arch_config)

        assert str(config_sig) == str(routing_sig), (
            f"Signatures don't match: "
            f"config.load_arch_config{config_sig} != "
            f"routing.load_arch_config{routing_sig}"
        )

    def test_load_arch_config_same_docstring(self):
        """
        Test that both functions have the EXACT same docstring.

        Given: Both config.py and routing.py have load_arch_config
        When: Inspecting their docstrings
        Then: Docstrings should be identical

        If routing.py imports from config, docstrings match automatically.
        If routing.py has its own copy, docstrings may drift over time.
        """
        config_doc = inspect.getdoc(config.load_arch_config)
        routing_doc = inspect.getdoc(routing.load_arch_config)

        assert config_doc == routing_doc, (
            f"Docstrings don't match.\n"
            f"config.py:\n{config_doc}\n\n"
            f"routing.py:\n{routing_doc}"
        )


class TestLoadArchConfigBehavioralEquivalence:
    """Tests verifying behavioral equivalence if separate implementations exist."""

    @pytest.fixture
    def mock_config_env(self):
        """Fixture providing mocked environment for config tests."""
        with patch.dict("os.environ", {"ARCH_DEFAULT_DOMAIN": "python"}, clear=False):
            yield

    def test_environment_override_both_behave_same(self, mock_config_env):
        """
        Test that both functions handle environment variables identically.

        Given: ARCH_DEFAULT_DOMAIN environment variable is set
        When: Calling both load_arch_config functions
        Then: Both should return config with domain from environment

        This catches behavioral drift between duplicate implementations.
        """
        config_result = config.load_arch_config()
        routing_result = routing.load_arch_config()

        # Both should return the same dict structure
        assert config_result == routing_result, (
            f"Environment handling differs:\n"
            f"config.load_arch_config() = {config_result}\n"
            f"routing.load_arch_config() = {routing_result}"
        )

    def test_none_config_both_behave_same(self):
        """
        Test that both functions return None when no config exists.

        Given: No config files and no environment variables
        When: Calling both load_arch_config functions
        Then: Both should return None

        This catches behavioral drift in edge cases.
        """
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = False

                config_result = config.load_arch_config()
                routing_result = routing.load_arch_config()

                assert config_result is None and routing_result is None, (
                    f"None handling differs:\n"
                    f"config.load_arch_config() = {config_result}\n"
                    f"routing.load_arch_config() = {routing_result}"
                )

    @pytest.mark.skip(
        reason="Obsolete: routing.load_arch_config now imports from config.load_arch_config. "
        "Both functions are identical, so behavioral equivalence is guaranteed by import."
    )
    def test_invalid_domain_raises_same_error(self):
        """
        Test that both functions raise the same error for invalid domain.

        Given: ARCH_DEFAULT_DOMAIN is set to an invalid value
        When: Calling both load_arch_config functions
        Then: Both should raise ValueError with same message pattern

        NOTE: This test is now obsolete since routing.load_arch_config imports
        directly from config.load_arch_config. Behavioral equivalence is guaranteed
        by the import itself.
        """
        # Test implementation removed - kept for documentation
        pass
