"""Pytest configuration for arch skill tests."""

import importlib.util
import sys
from pathlib import Path

# Import pytest first
import pytest

# Add parent directory to path for imports
# Tests are in skill/tests/, so parent.parent is skill/
# We import directly from skill.* modules, not skills.arch.*
skill_dir = Path(__file__).parent.parent
sys.path.insert(0, str(skill_dir))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (slower, may use file system)"
    )


@pytest.fixture(autouse=True)
def clear_config_cache_between_tests():
    """
    Clear the config cache before each test.

    PERF-004 added caching to load_arch_config() which causes test isolation
    issues when the cache persists between tests. This fixture ensures the
    cache is cleared before each test runs.

    Uses clear_config_cache() function from config module for proper isolation.
    Defensive import: try config module, fall back to direct import if needed.
    """
    try:
        # Try importing from config (when skill_dir is first in sys.path)
        from config import clear_config_cache
    except ImportError:
        # Fall back to direct module import (handles root conftest path conflicts)
        import importlib
        import sys
        from pathlib import Path

        # Find and import the correct config module
        skill_config_path = Path(__file__).parent.parent / "config.py"
        if skill_config_path.exists():
            spec = importlib.util.spec_from_file_location("skill_config", skill_config_path)
            skill_config = importlib.util.module_from_spec(spec)
            sys.modules["skill_config"] = skill_config
            spec.loader.exec_module(skill_config)
            clear_config_cache = skill_config.clear_config_cache
        else:
            # Module not found, skip cache clearing (no-op)
            def clear_config_cache():
                pass

    # Use the cache clearing function
    clear_config_cache()
    yield
    clear_config_cache()
