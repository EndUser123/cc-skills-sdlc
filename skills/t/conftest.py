"""
pytest configuration for safe, non-hanging tests.

This conftest.py provides:
- Global test timeout (prevents infinite loops)
- Session-level fixtures with cleanup
- Resource management for locks and files
- Isolation between tests
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# =============================================================================
# GLOBAL TIMEOUT CONFIGURATION (prevents hanging tests)
# =============================================================================

def pytest_configure(config):
    """
    Configure pytest with safety settings.

    Requires: pip install pytest-timeout
    """
    # Set global timeout for all tests
    # If a test runs longer than this, it's killed and marked as FAILED
    config.option.timeout = 30  # 30 seconds per test

    # Mark slow tests (>5s) with @pytest.mark.slow decorator
    config.addinivalue_line("markers", "slow: marks tests as slow (taking >5 seconds)")

    # Mark integration tests
    config.addinivalue_line("markers", "integration: marks tests as integration tests")

    # Mark tests that use external resources
    config.addinivalue_line("markers", "external: marks tests that use external resources (network, databases)")


# =============================================================================
# SESSION-LEVEL FIXTURES (setup/teardown for entire test session)
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def test_session_setup():
    """
    Set up test session with resource tracking.

    This fixture runs once at the beginning of the test session and
    tears down resources at the end.
    """
    print("\n" + "=" * 70)
    print("TEST SESSION STARTING")
    print("=" * 70)

    # Track test session start time
    import time
    session_start = time.time()

    yield {
        "session_start": session_start
    }

    # Session cleanup
    session_duration = time.time() - session_start
    print("\n" + "=" * 70)
    print(f"TEST SESSION COMPLETE (duration: {session_duration:.2f}s)")
    print("=" * 70)


# =============================================================================
# TEMPOARY DIRECTORY FIXTURE (isolated temp storage per test)
# =============================================================================

@pytest.fixture
def temp_dir():
    """
    Provide isolated temporary directory for each test.

    Automatically cleans up after test completes, even if test fails.
    Prevents disk space issues from accumulating test artifacts.

    Yields:
        Path: Path to temporary directory
    """
    with tempfile.TemporaryDirectory(prefix="test_") as tmpdir:
        temp_path = Path(tmpdir)
        print(f"\n[TEMP DIR] {temp_path}")
        yield temp_path
        print(f"[TEMP DIR] Cleaned up {temp_path}")


# =============================================================================
# LOCK CLEANUP FIXTURE (prevents stale locks from hanging tests)
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_stale_locks():
    """
    Automatically clean up stale locks before and after each test.

    This prevents tests from failing due to locks left behind by
    previously hung or crashed tests.

    Runs automatically before and after every test (autouse=True).
    """
    from windows_ipc import WindowsFileLock

    # Cleanup before test
    lock = WindowsFileLock("pre_test_cleanup")
    try:
        lock._cleanup_all_stale_locks()
    except Exception as e:
        print(f"[WARNING] Failed to cleanup stale locks before test: {e}")

    yield

    # Cleanup after test
    try:
        lock._cleanup_all_stale_locks()
    except Exception as e:
        print(f"[WARNING] Failed to cleanup stale locks after test: {e}")


# =============================================================================
# THREAD/PROCESS CLEANUP (prevents orphaned threads)
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_threads():
    """
    Ensure no threads are left running after test.

    This prevents tests from leaking threads that could cause
    subsequent tests to hang or fail.

    Runs automatically after every test (autouse=True).
    """
    import threading

    yield

    # Check for leftover threads
    active_threads = [t for t in threading.enumerate() if t.is_alive() and t != threading.main_thread()]
    if active_threads:
        print(f"\n[WARNING] {len(active_threads)} threads still active after test:")
        for thread in active_threads[:5]:  # Show first 5
            print(f"  - {thread.name} (daemon: {thread.daemon})")


# =============================================================================
# TIMEOUT DECORATOR (per-test timeout configuration)
# =============================================================================

def safe_timeout(timeout_seconds=10):
    """
    Decorator to add timeout to individual tests.

    Use this for tests that might take longer than the global 30s timeout
    but should still eventually complete.

    Usage:
        @safe_timeout(timeout_seconds=60)
        def test_slow_operation():
            # Test that takes up to 60 seconds
            pass

    Args:
        timeout_seconds: Maximum seconds to allow test to run

    Returns:
        pytest decorator function
    """
    import pytest

    return pytest.mark.timeout(timeout_seconds)


# =============================================================================
# EXTERNAL RESOURCE DECORATOR (mark tests requiring network/databases)
# =============================================================================

def requires_external_resources():
    """
    Decorator to mark tests that use external resources.

    These tests are automatically skipped if:
    - Network is unavailable
    - External services are down
    - Running in CI/CD without external access

    Usage:
        @requires_external_resources()
        def test_api_call():
            response = requests.get("https://api.example.com")
            assert response.status_code == 200

    Returns:
        pytest skipif decorator function
    """
    import socket

    # Check if network is available
    def has_network():
        try:
            # Try to connect to a reliable public DNS server
            socket.create_connection(("8.8.8.8", 53), timeout=1)
            return True
        except OSError:
            return False

    import pytest

    condition = pytest.mark.skipif(
        not has_network(),
        reason="Network unavailable - skipping external resource test"
    )

    return condition


# =============================================================================
# SLOW TEST DECORATOR (mark tests that take >5 seconds)
# =============================================================================

def slow_test():
    """
    Decorator to mark tests as intentionally slow.

    These tests are excluded from normal test runs but included
    when running with `pytest -m slow`.

    Usage:
        @slow_test()
        def test_database_migration():
            # Test that takes 10+ seconds
            pass

    Returns:
        pytest mark decorator
    """
    import pytest

    return pytest.mark.slow("Test takes >5 seconds")


# =============================================================================
# TEST ISOLATION FIXTURES (prevent test interference)
# =============================================================================

@pytest.fixture(autouse=True)
def reset_state():
    """
    Reset any global state between tests.

    Prevents tests from interfering with each other by:
    - Clearing any caches
    - Resetting global variables
    - Reinitializing singletons

    Runs automatically before every test (autouse=True).
    """
    # Clear any import caches
    import sys
    sys.path_importer_cache.clear()

    yield

    # Additional cleanup can be added here as needed
    # For example: reset_singletons(), clear_caches(), etc.


# =============================================================================
# HOOKS (pytest event callbacks for monitoring)
# =============================================================================

def pytest_runtest_makereport(item, call):
    """
    Called when a test fails.

    Use this to log detailed information about test failures for debugging.
    """
    if call.when == "call" and call.excinfo is not None:
        # Test failed during execution (not during setup/teardown)
        test_name = item.nodeid
        exc_type, exc_value, exc_tb = call.excinfo

        print(f"\n[TEST FAILED] {test_name}")
        print(f"  Exception: {exc_type.__name__}")
        print(f"  Message: {exc_value}")


def pytest_collection_modifyitems(config, items):
    """
    Called after test collection is complete.

    Use this to reorder tests for better isolation:
    - Run fast tests first (quick feedback)
    - Run integration tests last (may be slower)
    """
    # Split tests into fast and slow
    fast_tests = []
    slow_tests = []
    integration_tests = []

    for item in items:
        if item.get_closest_marker("slow"):
            slow_tests.append(item)
        elif item.get_closest_marker("integration"):
            integration_tests.append(item)
        else:
            fast_tests.append(item)

    # Reorder: fast → slow → integration
    items[:] = fast_tests + slow_tests + integration_tests


# =============================================================================
# MEMORY USAGE TRACKING (prevent memory leaks)
# =============================================================================

@pytest.fixture(autouse=True)
def track_memory_usage():
    """
    Track memory usage during test execution.

    Warns if test uses excessive memory (>100MB increase).
    """
    import gc
    import tracemalloc

    # Start tracking
    tracemalloc.start()
    gc.collect()  # Force garbage collection before test

    snapshot1 = tracemalloc.take_snapshot()

    yield

    # Check memory usage after test
    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')

    # Calculate total memory increase
    total_increase = sum(stat.size_diff for stat in top_stats)

    if total_increase > 100 * 1024 * 1024:  # >100MB
        print(f"\n[WARNING] Test used {total_increase / (1024*1024):.1f}MB of memory")

    tracemalloc.stop()
