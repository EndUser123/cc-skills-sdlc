#!/usr/bin/env python3
"""Test Windows file locking primitives."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from windows_ipc import WindowsFileLock


def test_acquire_release_basic() -> None:
    """Test basic lock acquire and release."""
    lock = WindowsFileLock("test_basic")
    assert lock.acquire(timeout_ms=5000) == "acquired"
    assert lock.release() is True


def test_stale_lock_detection() -> None:
    """Test detection and cleanup of stale locks."""
    lock = WindowsFileLock("test_stale")

    # Create a fake lock file (simulating a lock held by another process)
    lock.lock_file.touch()

    # Write fake metadata with non-existent PID
    lock.lock_file.with_suffix(".meta").write_text('{"pid": 99999, "terminal_id": "test", "acquired_at": "2026-01-01T00:00:00"}')

    # Should detect as stale (PID 99999 doesn't exist)
    assert lock._is_stale_lock() is True
    lock._cleanup_stale_lock()

    # Now acquire should work (stale lock was cleaned up)
    assert lock.acquire(timeout_ms=100) == "acquired"
    lock.release()


def test_atomic_cache_write() -> None:
    """Test atomic write to cache file."""
    lock = WindowsFileLock("test_atomic")
    lock.acquire(timeout_ms=5000)

    test_data = {"key": "value", "number": 42}
    assert lock.write_cache(test_data) is True

    # Verify data was written
    read_data = lock.read_cache()
    assert read_data == test_data

    lock.release()


def test_cache_interrupt_recovery() -> None:
    """Test cache recovery from interrupted write."""
    lock = WindowsFileLock("test_interrupt")
    lock.acquire(timeout_ms=5000)

    # Simulate interrupted write (partial temp file)
    temp_file = lock.cache_file.with_suffix(".tmp")
    temp_file.write_text('{"incomplete": "data"')

    # Cache read should handle corruption gracefully
    data = lock.read_cache()
    assert data == {}  # Empty dict on parse error

    lock.release()


if __name__ == "__main__":
    test_acquire_release_basic()
    print("✅ test_acquire_release_basic passed")

    test_stale_lock_detection()
    print("✅ test_stale_lock_detection passed")

    test_atomic_cache_write()
    print("✅ test_atomic_cache_write passed")

    test_cache_interrupt_recovery()
    print("✅ test_cache_interrupt_recovery passed")

    print("\nAll Windows IPC tests passed!")
