#!/usr/bin/env python3
"""
Windows-compatible file locking for multi-terminal safety.

Uses msvcrt.locking() for cross-process locking with PID-based stale lock detection.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

LockResult = Literal["acquired", "blocked", "error"]


@dataclass
class LockInfo:
    """Information stored in lock file for stale lock detection."""

    pid: int
    terminal_id: str
    acquired_at: str  # ISO timestamp

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> LockInfo | None:
        """Parse from JSON string."""
        try:
            data = json.loads(json_str)
            return cls(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None


class WindowsFileLock:
    """
    Windows-compatible file lock using msvcrt.locking().

    Usage:
        lock = WindowsFileLock("test_state_cache")
        if lock.acquire(timeout_ms=5000):
            try:
                data = lock.read_cache()
                # ... modify data ...
                lock.write_cache(data)
            finally:
                lock.release()

    Attributes:
        lock_name: Unique name for this lock
        cache_dir: Directory for lock files
        lock_file: Path to lock file
        cache_file: Path to cache JSON file
        _fd: File descriptor for lock (private)
    """

    def __init__(self, lock_name: str, cache_dir: str | None = None):
        """
        Initialize file lock.

        Args:
            lock_name: Unique name for this lock (e.g., "test_state_cache")
            cache_dir: Directory for lock files (default: temp)
        """
        self.lock_name = lock_name
        self.cache_dir = Path(cache_dir or tempfile.gettempdir()) / "csf_t_locks"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.lock_file = self.cache_dir / f"{lock_name}.lock"
        self.cache_file = self.cache_dir / f"{lock_name}.json"
        self._fd = None

    def acquire(
        self, timeout_ms: int = 5000, retry_interval_ms: int = 100
    ) -> LockResult:
        """
        Acquire lock with timeout and retry.

        Windows implementation:
            - Open lock file in write mode
            - Call msvcrt.locking(fd, LK_NBLCK, 1) for non-blocking lock
            - If fails, check for stale lock (PID not running)
            - Retry after interval until timeout

        Args:
            timeout_ms: Maximum time to wait (default: 5000ms)
            retry_interval_ms: Time between retries (default: 100ms)

        Returns:
            "acquired" if lock obtained
            "blocked" if timeout exceeded
            "error" if exception raised

        Examples:
            >>> lock = WindowsFileLock("test_basic")
            >>> result = lock.acquire(timeout_ms=5000)
            >>> result in ["acquired", "blocked", "error"]
            True
        """
        start_time = time.time()
        retry_interval_sec = retry_interval_ms / 1000.0

        # Get terminal ID from environment (Windows Terminal or fallback)
        terminal_id = os.environ.get("WT_SESSION") or os.environ.get("TERM") or f"pid-{os.getpid()}"

        while True:
            try:
                # Open lock file (create if doesn't exist)
                mode = os.O_RDWR | os.O_CREAT
                self._fd = os.open(self.lock_file, mode)

                # Try to acquire lock non-blocking
                try:
                    import msvcrt

                    # LK_NBLCK = non-blocking lock, LK_LOCK = blocking lock
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)

                    # Write lock info to separate metadata file (NOT the locked file descriptor)
                    # This prevents file descriptor state corruption that breaks msvcrt.locking()
                    lock_info = LockInfo(
                        pid=os.getpid(),
                        terminal_id=terminal_id,
                        acquired_at=datetime.now().isoformat(),
                    )
                    # Store metadata in separate JSON file alongside lock file
                    self.lock_file.with_suffix(".meta").write_text(lock_info.to_json())
                    return "acquired"

                except OSError:
                    # Lock failed - check if stale
                    os.close(self._fd)
                    self._fd = None

                    if self._is_stale_lock():
                        self._cleanup_stale_lock()
                        # Retry immediately after cleanup
                        continue

                    # Check timeout
                    elapsed_sec = time.time() - start_time
                    if elapsed_sec >= (timeout_ms / 1000.0):
                        return "blocked"

                    # Wait before retry
                    time.sleep(retry_interval_sec)
                    continue

            except Exception:
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except Exception:
                        pass
                    self._fd = None
                return "error"

    def release(self) -> bool:
        """
        Release the lock using msvcrt.locking(fd, LK_UNLCK, 1).

        Returns:
            True if release successful, False otherwise

        Examples:
            >>> lock = WindowsFileLock("test_basic")
            >>> lock.acquire(timeout_ms=5000)
            'acquired'
            >>> lock.release()
            True
        """
        if self._fd is None:
            return False

        try:
            import msvcrt

            # LK_UNLCK = unlock
            msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            os.close(self._fd)
            self._fd = None

            # Remove lock file
            if self.lock_file.exists():
                self.lock_file.unlink()

            return True

        except Exception:
            return False

    def read_cache(self) -> dict[str, Any]:
        """
        Read cached state JSON.

        Returns:
            Cached data dict, or empty dict if file missing/invalid

        Examples:
            >>> lock = WindowsFileLock("test_cache")
            >>> lock.acquire()
            'acquired'
            >>> data = lock.read_cache()
            >>> isinstance(data, dict)
            True
            >>> lock.release()
            True
        """
        if not self.cache_file.exists():
            return {}

        try:
            import json

            with open(self.cache_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def write_cache(self, data: dict[str, Any]) -> bool:
        """
        Write state to cache (atomic).

        Atomic write pattern:
            1. Write to temp file (.tmp)
            2. Rename temp file to cache file (atomic on Windows)

        Args:
            data: Dictionary to cache

        Returns:
            True if write successful, False otherwise

        Examples:
            >>> lock = WindowsFileLock("test_atomic")
            >>> lock.acquire()
            'acquired'
            >>> test_data = {"key": "value", "number": 42}
            >>> lock.write_cache(test_data)
            True
            >>> read_data = lock.read_cache()
            >>> read_data == test_data
            True
            >>> lock.release()
            True
        """
        try:
            import json

            temp_file = self.cache_file.with_suffix(".tmp")

            # Write to temp file
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)

            # Atomic rename (Windows requirement)
            temp_file.replace(self.cache_file)

            return True

        except (OSError, TypeError, ValueError):
            return False

    def _is_stale_lock(self) -> bool:
        """
        Check if lock file is stale (PID not running).

        Windows implementation:
            - Read LockInfo from separate .meta file (JSON format)
            - Use psutil.pid_exists(pid) to check if process running

        Returns:
            True if lock is stale, False otherwise

        Examples:
            >>> lock = WindowsFileLock("test_stale")
            >>> lock.acquire()
            'acquired'
            >>> lock.release()
            True
            >>> # Manually corrupt PID in metadata file
            >>> lock.lock_file.with_suffix(".meta").write_text('{"pid": 99999, "terminal_id": "test", "acquired_at": "2026-01-01"}')  # Non-existent PID
            >>> lock._is_stale_lock()
            True
        """
        if not self.lock_file.exists():
            return False

        # Read from separate metadata file (not the locked file descriptor)
        meta_file = self.lock_file.with_suffix(".meta")
        if not meta_file.exists():
            return True  # No metadata = stale

        try:
            content = meta_file.read_text().strip()
            if not content:
                return True

            # Try to parse LockInfo from JSON
            lock_info = LockInfo.from_json(content)
            if lock_info is None:
                return True  # Invalid content = stale

            # Check if PID exists
            try:
                import psutil

                return not psutil.pid_exists(lock_info.pid)
            except ImportError:
                # Fallback: Try to kill signal 0 to check PID
                try:
                    os.kill(lock_info.pid, 0)
                    return False  # PID exists
                except OSError:
                    return True  # PID doesn't exist

        except Exception:
            return True  # Any error = assume stale

        return False

    def _cleanup_stale_lock(self) -> None:
        """
        Clean up stale lock file and metadata.

        Removes both the lock file and the .meta metadata file if they exist.
        """
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
            # Also clean up metadata file
            meta_file = self.lock_file.with_suffix(".meta")
            if meta_file.exists():
                meta_file.unlink()
        except Exception:
            pass
