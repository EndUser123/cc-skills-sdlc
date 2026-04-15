"""Pytest configuration for rca tests.

This conftest.py configures the test environment to import from the
rca package (src/rca/).
"""

import os
import sys
import warnings
from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure pytest with rca package imports.

    This ensures that 'from rca' imports work from the package.
    """
    # Add package src to path for imports
    package_src = str(Path("P:/packages/rca/src").resolve())
    if package_src not in sys.path:
        sys.path.insert(0, package_src)

    # Add CSF src for CKS imports
    csf_src = str(Path("P:/__csf/src").resolve())
    if csf_src not in sys.path:
        sys.path.insert(0, csf_src)

    # Filter CKS deprecation warnings (old import path)
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=".*Direct 'from src.cks' imports deprecated.*",
    )

    # Filter ResourceWarning for unclosed database connections in tests
    warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed database.*")

    # Filter PytestUnraisableExceptionWarning for unclosed database connections
    warnings.filterwarnings(
        "ignore",
        category=Warning,
        message=".*Exception ignored while finalizing database connection.*",
    )


@pytest.fixture(autouse=True)
def reset_test_environment():
    """Auto-use fixture that resets environment for each test.

    This ensures that tests don't interfere with each other by
    cleaning up environment variables and state.
    """
    # Save original env vars
    original_env = {}
    env_keys = ["DEBUGRCA_STATE_DIR", "DEBUGRCA_LOCAL_ONLY", "DEBUGRCA_SATURATION_DISABLED"]
    for key in env_keys:
        original_env[key] = os.environ.get(key)

    yield

    # Restore original env vars
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def phase_state_manager():
    """Fixture that provides a PhaseStateManager with proper cleanup.

    Use this fixture in tests to automatically clean up CKS connections.
    """
    from rca.phase_state_manager import PhaseStateManager

    manager = PhaseStateManager()
    yield manager
    # Cleanup: close CKS connection
    manager.close()


@pytest.fixture
def cks_client():
    """Fixture that provides a CKS client with proper cleanup.

    Use this fixture in tests that need direct CKS access.
    """
    csf_src = str(Path("P:/__csf/src").resolve())
    if csf_src not in sys.path:
        sys.path.insert(0, csf_src)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        from cks.unified import CKS

    client = CKS(db_path="P:/packages/rca/skill/tests/test_db.db")
    yield client
    client.close()
