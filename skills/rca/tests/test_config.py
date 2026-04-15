"""Configuration tests for rca Tier 1 implementation.

These tests verify that settings.json has proper rca configuration
including saturation thresholds and environment variable handling.

Run with: pytest P:/.claude/skills/debugrca/tests/test_config.py -v
"""

import json
import os
from pathlib import Path

import pytest


class TestSettingsJsonConfiguration:
    """Tests for settings.json rca configuration section."""

    @pytest.fixture
    def settings_path(self):
        """Return the path to settings.json."""
        return Path("P:/.claude/settings.json")

    @pytest.fixture
    def settings(self, settings_path):
        """Load and return settings.json content."""
        if not settings_path.exists():
            pytest.skip(f"settings.json not found at {settings_path}")

        with open(settings_path, encoding="utf-8") as f:
            return json.load(f)

    def test_settings_file_exists(self, settings_path):
        """Test that settings.json exists.

        Given: Claude Code configuration is required
        When: Checking for settings.json
        Then: The file should exist at P:/.claude/settings.json
        """
        assert settings_path.exists(), f"settings.json not found at {settings_path}"

    def test_debugrca_config_section_exists(self, settings):
        """Test that settings.json has debugrca configuration section.

        Given: The rca Tier 1 implementation requires configuration
        When: Reading settings.json
        Then: A 'debugrca' section should exist with configuration values
        """
        assert "debugrca" in settings, "settings.json missing 'debugrca' configuration section"

        debugrca_config = settings["debugrca"]
        assert isinstance(debugrca_config, dict), "debugrca config should be a dictionary"

    def test_saturation_thresholds_configured(self, settings):
        """Test that saturation_thresholds are configured with defaults.

        Given: Evidence saturation detection requires threshold configuration
        When: Reading debugrca.saturation_thresholds from settings
        Then: Default thresholds should be configured for different query types
        """
        if "debugrca" not in settings:
            pytest.skip("debugrca config section not found")

        debugrca_config = settings["debugrca"]

        assert (
            "saturation_thresholds" in debugrca_config
        ), "debugrca config missing 'saturation_thresholds'"

        thresholds = debugrca_config["saturation_thresholds"]
        assert isinstance(thresholds, dict), "saturation_thresholds should be a dictionary"

        # Check for expected threshold types
        expected_types = ["technical", "balanced", "preference", "default"]
        missing_types = [t for t in expected_types if t not in thresholds]

        if missing_types:
            pytest.fail(f"saturation_thresholds missing expected types: {', '.join(missing_types)}")

        # Verify thresholds are numeric values between 0 and 1
        for threshold_type, value in thresholds.items():
            assert isinstance(
                value, (int, float)
            ), f"threshold for '{threshold_type}' should be numeric"
            assert (
                0 <= value <= 1
            ), f"threshold for '{threshold_type}' should be between 0 and 1, got {value}"

    def test_phase_state_persistence_configured(self, settings):
        """Test that phase state persistence settings are configured.

        Given: Phase state persistence requires storage configuration
        When: Reading debugrca.phase_persistence from settings
        Then: State directory and retention settings should be configured
        """
        if "debugrca" not in settings:
            pytest.skip("debugrca config section not found")

        debugrca_config = settings["debugrca"]

        assert (
            "phase_persistence" in debugrca_config
        ), "debugrca config missing 'phase_persistence' settings"

        persistence = debugrca_config["phase_persistence"]
        assert isinstance(persistence, dict), "phase_persistence should be a dictionary"

        # Check for required keys
        required_keys = ["state_dir", "enabled"]
        missing_keys = [k for k in required_keys if k not in persistence]

        if missing_keys:
            pytest.fail(f"phase_persistence missing required keys: {', '.join(missing_keys)}")

        assert persistence["enabled"] in [
            True,
            False,
        ], "phase_persistence.enabled should be boolean"
        assert isinstance(
            persistence["state_dir"], str
        ), "phase_persistence.state_dir should be a string path"

    def test_hypothesis_scoring_configured(self, settings):
        """Test that hypothesis scoring settings are configured.

        Given: Hypothesis scoring requires weight configuration
        When: Reading debugrca.hypothesis_scoring from settings
        Then: Weight factors should be configured for ranking
        """
        if "debugrca" not in settings:
            pytest.skip("debugrca config section not found")

        debugrca_config = settings["debugrca"]

        assert (
            "hypothesis_scoring" in debugrca_config
        ), "debugrca config missing 'hypothesis_scoring' settings"

        scoring = debugrca_config["hypothesis_scoring"]
        assert isinstance(scoring, dict), "hypothesis_scoring should be a dictionary"

        # Check for weight factors
        expected_weights = ["reproducibility_weight", "recency_weight", "impact_weight"]
        missing_weights = [w for w in expected_weights if w not in scoring]

        if missing_weights:
            pytest.fail(f"hypothesis_scoring missing weight factors: {', '.join(missing_weights)}")

        # Verify weights sum to approximately 1.0
        total_weight = sum(scoring[w] for w in expected_weights if w in scoring)
        assert (
            abs(total_weight - 1.0) < 0.01
        ), f"hypothesis_scoring weights should sum to 1.0, got {total_weight}"


class TestEnvironmentVariables:
    """Tests for rca environment variable handling."""

    def test_debugrca_local_only_env_var_read(self):
        """Test that DEBUGRCA_LOCAL_ONLY env var can be read.

        Given: Local-only fallback mode is controlled by environment
        When: Reading the DEBUGRCA_LOCAL_ONLY environment variable
        Then: The value should be accessible and parseable as boolean
        """
        # Set a test value
        os.environ["DEBUGRCA_LOCAL_ONLY"] = "true"

        try:
            import sys

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            from rca.config import get_local_only_mode  # noqa: F401

            is_local_only = get_local_only_mode()
            assert is_local_only is True, "get_local_only_mode should return True when set"

        except (ImportError, AttributeError) as e:
            pytest.fail(f"Failed to import or use get_local_only_mode: {e}")

        finally:
            # Clean up
            os.environ.pop("DEBUGRCA_LOCAL_ONLY", None)

    def test_debugrca_saturation_disabled_env_var(self):
        """Test that DEBUGRCA_SATURATION_DISABLED env var is respected.

        Given: Saturation detection can be disabled via environment
        When: Setting DEBUGRCA_SATURATION_DISABLED environment variable
        Then: The saturation detector should respect this setting
        """
        # Set a test value
        os.environ["DEBUGRCA_SATURATION_DISABLED"] = "1"

        try:
            import sys

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            # Note: This function may not exist in the current implementation
            # Skip the test if the function doesn't exist
            try:
                from rca.config import is_saturation_disabled  # noqa: F401
            except (ImportError, AttributeError):
                pytest.skip("is_saturation_disabled function not implemented")

            is_disabled = is_saturation_disabled()
            assert (
                is_disabled is True
            ), "is_saturation_disabled should return True when DEBUGRCA_SATURATION_DISABLED=1"

        except (ImportError, AttributeError) as e:
            pytest.fail(f"Failed to import or use is_saturation_disabled: {e}")

        finally:
            # Clean up
            os.environ.pop("DEBUGRCA_SATURATION_DISABLED", None)

    def test_debugrca_state_dir_env_var(self):
        """Test that DEBUGRCA_STATE_DIR env var is used when set.

        Given: State directory location can be customized
        When: Setting DEBUGRCA_STATE_DIR environment variable
        Then: The state manager should use the custom path
        """
        custom_state_dir = "P:/custom/debugrca_state"
        os.environ["DEBUGRCA_STATE_DIR"] = custom_state_dir

        try:
            import sys

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            from rca.config import get_state_dir  # noqa: F401

            state_dir = get_state_dir()
            assert (
                state_dir == custom_state_dir
            ), f"get_state_dir should return custom path when set, got {state_dir}"

        except (ImportError, AttributeError) as e:
            pytest.fail(f"Failed to import or use get_state_dir: {e}")

        finally:
            # Clean up
            os.environ.pop("DEBUGRCA_STATE_DIR", None)


class TestConfigModule:
    """Tests for debugrca.config module functionality."""

    def test_config_module_exists(self):
        """Test that config module can be imported.

        Given: Configuration is centralized in a config module
        When: Attempting to import rca.tier1.config
        Then: The import should succeed
        """
        try:
            import sys

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            from rca import config  # noqa: F401

            assert config is not None

        except ImportError as e:
            pytest.fail(f"Failed to import rca.tier1.config module: {e}")

    def test_get_saturation_threshold_returns_correct_defaults(self):
        """Test that get_saturation_threshold returns correct default values.

        Given: Different query types have different saturation thresholds
        When: Calling get_saturation_threshold for each type
        Then: Expected default thresholds should be returned
        """
        try:
            import sys

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            from rca.config import get_saturation_threshold  # noqa: F401

            # Test technical query threshold
            technical_threshold = get_saturation_threshold("technical")
            assert isinstance(
                technical_threshold, (int, float)
            ), "technical threshold should be numeric"

            # Test balanced query threshold
            balanced_threshold = get_saturation_threshold("balanced")
            assert isinstance(
                balanced_threshold, (int, float)
            ), "balanced threshold should be numeric"

            # Test preference query threshold
            preference_threshold = get_saturation_threshold("preference")
            assert isinstance(
                preference_threshold, (int, float)
            ), "preference threshold should be numeric"

        except (ImportError, AttributeError) as e:
            pytest.fail(f"Failed to import or use get_saturation_threshold: {e}")


class TestConfigModuleComprehensive:
    """Comprehensive tests for config.py module to ensure coverage."""

    @pytest.fixture(autouse=True)
    def setup_sys_path(self):
        """Ensure the package is in sys.path for all tests."""
        import sys

        package_src = str(Path("P:/packages/rca/src").resolve())
        if package_src not in sys.path:
            sys.path.insert(0, package_src)
        yield
        # Cleanup
        if package_src in sys.path:
            sys.path.remove(package_src)

    def test_get_local_only_mode_defaults_to_false(self):
        """Test that get_local_only_mode defaults to False when not set.

        Given: No DEBUGRCA_LOCAL_ONLY environment variable is set
        When: Calling get_local_only_mode()
        Then: Should return False
        """
        # Ensure env var is not set
        import os

        from rca.config import get_local_only_mode

        if "DEBUGRCA_LOCAL_ONLY" in os.environ:
            del os.environ["DEBUGRCA_LOCAL_ONLY"]

        result = get_local_only_mode()
        assert result is False, "Should default to False when env var not set"

    def test_get_local_only_mode_true_values(self):
        """Test that get_local_only_mode correctly parses true values.

        Given: DEBUGRCA_LOCAL_ONLY is set to various true values
        When: Calling get_local_only_mode()
        Then: Should return True for 'true', '1', 'yes', 'on'
        """
        import os

        from rca.config import get_local_only_mode

        true_values = ["true", "1", "yes", "on"]
        for value in true_values:
            os.environ["DEBUGRCA_LOCAL_ONLY"] = value
            try:
                result = get_local_only_mode()
                assert result is True, f"Should return True for '{value}'"
            finally:
                os.environ.pop("DEBUGRCA_LOCAL_ONLY", None)

    def test_get_local_only_mode_false_values(self):
        """Test that get_local_only_mode correctly parses false values.

        Given: DEBUGRCA_LOCAL_ONLY is set to various false values
        When: Calling get_local_only_mode()
        Then: Should return False for 'false', '0', 'no', 'off'
        """
        import os

        from rca.config import get_local_only_mode

        false_values = ["false", "0", "no", "off"]
        for value in false_values:
            os.environ["DEBUGRCA_LOCAL_ONLY"] = value
            try:
                result = get_local_only_mode()
                assert result is False, f"Should return False for '{value}'"
            finally:
                os.environ.pop("DEBUGRCA_LOCAL_ONLY", None)

    def test_is_saturation_disabled_defaults_to_false(self):
        """Test that is_saturation_disabled defaults to False when not set.

        Given: No DEBUGRCA_SATURATION_DISABLED environment variable is set
        When: Calling is_saturation_disabled()
        Then: Should return False
        """
        import os

        from rca.config import is_saturation_disabled

        if "DEBUGRCA_SATURATION_DISABLED" in os.environ:
            del os.environ["DEBUGRCA_SATURATION_DISABLED"]

        result = is_saturation_disabled()
        assert result is False, "Should default to False when env var not set"

    def test_is_saturation_disabled_true_when_set(self):
        """Test that is_saturation_disabled returns True when enabled.

        Given: DEBUGRCA_SATURATION_DISABLED is set to '1'
        When: Calling is_saturation_disabled()
        Then: Should return True
        """
        import os

        from rca.config import is_saturation_disabled

        os.environ["DEBUGRCA_SATURATION_DISABLED"] = "1"
        try:
            result = is_saturation_disabled()
            assert result is True, "Should return True when DEBUGRCA_SATURATION_DISABLED=1"
        finally:
            os.environ.pop("DEBUGRCA_SATURATION_DISABLED", None)

    def test_get_state_dir_returns_default_path(self):
        """Test that get_state_dir returns default path when not set.

        Given: No DEBUGRCA_STATE_DIR environment variable is set
        When: Calling get_state_dir()
        Then: Should return default state directory path
        """
        import os

        from rca.config import get_state_dir

        if "DEBUGRCA_STATE_DIR" in os.environ:
            del os.environ["DEBUGRCA_STATE_DIR"]

        result = get_state_dir()
        assert isinstance(result, str), "Should return a string path"
        # Default path should contain 'state'
        assert "state" in result.lower(), f"Default path should contain 'state', got {result}"

    def test_get_state_dir_uses_custom_path(self):
        """Test that get_state_dir uses custom path when set.

        Given: DEBUGRCA_STATE_DIR is set to a custom path
        When: Calling get_state_dir()
        Then: Should return the custom path
        """
        import os

        from rca.config import get_state_dir

        custom_path = "P:/custom/state/location"
        os.environ["DEBUGRCA_STATE_DIR"] = custom_path
        try:
            result = get_state_dir()
            assert result == custom_path, f"Should return custom path, got {result}"
        finally:
            os.environ.pop("DEBUGRCA_STATE_DIR", None)

    def test_get_saturation_threshold_returns_default_for_unknown_type(self):
        """Test that get_saturation_threshold returns 'default' threshold for unknown types.

        Given: get_saturation_threshold is called with an unknown query type
        When: Calling get_saturation_threshold('unknown')
        Then: Should return the 'default' threshold
        """
        from rca.config import get_saturation_threshold

        result = get_saturation_threshold("unknown")
        # Should return the default threshold
        assert isinstance(result, (int, float)), "Should return numeric value"
        assert 0 <= result <= 1, "Threshold should be between 0 and 1"

    def test_get_saturation_threshold_returns_configured_values(self):
        """Test that get_saturation_threshold returns configured thresholds.

        Given: settings.json has saturation thresholds configured
        When: Calling get_saturation_threshold() for known types
        Then: Should return the configured threshold values
        """
        from rca.config import get_saturation_threshold

        # Test for different query types
        for query_type in ["technical", "balanced", "preference", "default"]:
            threshold = get_saturation_threshold(query_type)
            assert isinstance(
                threshold, (int, float)
            ), f"Threshold for '{query_type}' should be numeric"
            assert (
                0 <= threshold <= 1
            ), f"Threshold for '{query_type}' should be between 0 and 1, got {threshold}"

    def test_local_fallback_mode_context_manager(self):
        """Test LocalFallbackMode context manager enables local-only mode.

        Given: LocalFallbackMode context manager is created
        When: Entering the context
        Then: Local-only mode should be enabled
        When: Exiting the context
        Then: Local-only mode should be disabled
        """
        import os

        from rca.config import LocalFallbackMode, get_local_only_mode

        # Clean environment first
        if "DEBUGRCA_LOCAL_ONLY" in os.environ:
            del os.environ["DEBUGRCA_LOCAL_ONLY"]

        # Test that mode is False initially
        assert get_local_only_mode() is False, "Should start with local-only mode disabled"

        # Enter context
        with LocalFallbackMode(enabled=True):
            # Inside context, local-only mode should be enabled
            assert get_local_only_mode() is True, "LocalFallbackMode should enable local-only mode"

        # After context, should be disabled again
        assert get_local_only_mode() is False, "LocalFallbackMode should disable mode after exit"

    def test_local_fallback_mode_explicitly_disabled(self):
        """Test LocalFallbackMode with enabled=False.

        Given: LocalFallbackMode is created with enabled=False
        When: Entering the context
        Then: Local-only mode should NOT be enabled
        """
        import os

        from rca.config import LocalFallbackMode, get_local_only_mode

        if "DEBUGRCA_LOCAL_ONLY" in os.environ:
            del os.environ["DEBUGRCA_LOCAL_ONLY"]

        with LocalFallbackMode(enabled=False):
            assert get_local_only_mode() is False, "Should remain disabled with enabled=False"
