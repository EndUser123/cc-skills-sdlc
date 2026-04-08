"""Tests for config module (load_arch_config and ArchConfig).

Run with: pytest P:/packages/arch/skill/tests/test_config.py -v
"""

import json
import os
import tempfile
from pathlib import Path


from arch.skill.config import (
    VALID_DOMAINS,
    VALID_OUTPUT_SIZES,
    VALID_EVIDENCE_LEVELS,
    ArchConfig,
    clear_config_cache,
    load_arch_config,
)


class TestLoadArchConfigDefaults:
    """Tests for default config behavior when no config files exist."""

    def test_no_config_returns_default_domain(self):
        """When no config files, returns default_domain='auto'."""
        # Use temp directory to avoid config file interference
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                # Clear cache to ensure fresh load
                clear_config_cache()
                result = load_arch_config()
                assert result.is_success is True
                assert result.value.get("default_domain") == "auto"
                assert result.metadata["source"] == "default_fallback"
            finally:
                os.chdir(original_cwd)


class TestLoadArchConfigValidation:
    """Tests for config field validation."""

    def test_invalid_domain_raises_value_error(self, tmp_path):
        """Invalid domain in config raises ValueError."""
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(json.dumps({"default_domain": "invalid_domain"}))
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            clear_config_cache()
            result = load_arch_config()
            assert result.is_success is False
            assert result.error == "config_validation_error"
        finally:
            os.chdir(original_cwd)

    def test_missing_default_domain_raises_value_error(self, tmp_path):
        """Missing required default_domain raises ValueError."""
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(json.dumps({"output_size": "small"}))
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            clear_config_cache()
            result = load_arch_config()
            assert result.is_success is False
            assert result.error == "config_validation_error"
        finally:
            os.chdir(original_cwd)


class TestLoadArchConfigEnvOverride:
    """Tests for environment variable override."""

    def test_env_domain_overrides_config(self, tmp_path, monkeypatch):
        """ARCH_DEFAULT_DOMAIN env var overrides config file."""
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(json.dumps({"default_domain": "cli"}))
        monkeypatch.setenv("ARCH_DEFAULT_DOMAIN", "python")
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            clear_config_cache()
            result = load_arch_config()
            assert result.is_success is True
            assert result.value.get("default_domain") == "python"
        finally:
            os.chdir(original_cwd)


class TestValidDomains:
    """Tests for domain validation constants."""

    def test_valid_domains_contains_expected(self):
        """VALID_DOMAINS contains expected domains."""
        assert "python" in VALID_DOMAINS
        assert "cli" in VALID_DOMAINS
        assert "data-pipeline" in VALID_DOMAINS
        assert "precedent" in VALID_DOMAINS
        assert "auto" in VALID_DOMAINS

    def test_valid_output_sizes(self):
        """VALID_OUTPUT_SIZES contains expected values."""
        assert "normal" in VALID_OUTPUT_SIZES
        assert "small" in VALID_OUTPUT_SIZES
        assert "large" in VALID_OUTPUT_SIZES

    def test_valid_evidence_levels(self):
        """VALID_EVIDENCE_LEVELS contains expected values."""
        assert "standard" in VALID_EVIDENCE_LEVELS
        assert "high" in VALID_EVIDENCE_LEVELS
        assert "low" in VALID_EVIDENCE_LEVELS


class TestArchConfigClass:
    """Tests for ArchConfig class (Phase 4 duality)."""

    def test_arch_config_load_returns_arch_result(self):
        """ArchConfig.load() returns ArchResult."""
        config_manager = ArchConfig()
        result = config_manager.load()
        assert hasattr(result, "is_success")
        assert hasattr(result, "value")

    def test_arch_config_get_returns_default_when_no_key(self):
        """ArchConfig.get() returns default when key not found."""
        config_manager = ArchConfig()
        result = config_manager.get("nonexistent_key", "default_value")
        assert result == "default_value"

    def test_arch_config_get_returns_config_value(self):
        """ArchConfig.get() returns config value when key exists."""
        config_manager = ArchConfig()
        # default_domain should exist in config
        result = config_manager.get("default_domain")
        assert result is not None


class TestClearConfigCache:
    """Tests for config cache clearing."""

    def test_clear_config_cache_does_not_raise(self):
        """clear_config_cache() executes without error."""
        clear_config_cache()  # Should not raise

    def test_cache_clear_allows_fresh_load(self, tmp_path, monkeypatch):
        """Cache can be cleared and fresh load occurs."""
        config_file = tmp_path / ".archconfig.json"
        config_file.write_text(json.dumps({"default_domain": "python"}))
        monkeypatch.setenv("ARCH_DEFAULT_DOMAIN", "")
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            clear_config_cache()
            result1 = load_arch_config()
            assert result1.value.get("default_domain") == "python"
            # Modify config
            config_file.write_text(json.dumps({"default_domain": "cli"}))
            clear_config_cache()
            result2 = load_arch_config()
            assert result2.value.get("default_domain") == "cli"
        finally:
            os.chdir(original_cwd)
