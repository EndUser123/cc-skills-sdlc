#!/usr/bin/env python3
"""Test result caching across sessions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file contents."""
    try:
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return ""


def calculate_test_key(test_file: Path, dependencies: list[Path]) -> str:
    """
    Calculate cache key for a test based on test file + dependencies.

    Returns: SHA256 hash of combined content
    """
    hasher = hashlib.sha256()

    # Hash test file itself
    try:
        hasher.update(test_file.read_bytes())
    except Exception:
        pass

    # Hash all dependencies (modules it tests)
    for dep in dependencies:
        try:
            hasher.update(dep.read_bytes())
        except Exception:
            pass

    return hasher.hexdigest()


class TestCache:
    """Cache test results across sessions."""

    def __init__(self, cache_path: Path = Path(".test_cache.json")):
        self.cache_path = cache_path
        self.cache: dict[str, Any] = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        """Load existing cache or return empty."""
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            self.cache_path.write_text(json.dumps(self.cache, indent=2))
        except Exception:
            pass

    def get(self, test_key: str) -> dict[str, Any] | None:
        """Get cached test result if available."""
        return self.cache.get(test_key)

    def set(
        self,
        test_key: str,
        result: dict[str, Any],
        dependencies: list[str],
        runtime_seconds: float,
    ) -> None:
        """Store test result in cache."""
        self.cache[test_key] = {
            "result": result,
            "dependencies": dependencies,
            "runtime_seconds": runtime_seconds,
            "timestamp": datetime.now().isoformat(),
            "cache_hits": self.cache.get(test_key, {}).get("cache_hits", 0) + 1,
        }
        self._save_cache()

    def invalidate(self, file_path: Path) -> int:
        """
        Invalidate all cached tests that depend on this file.

        Returns: Number of cache entries invalidated
        """
        file_hash = calculate_file_hash(file_path)
        invalidated = 0

        for key, entry in list(self.cache.items()):
            if file_hash in entry.get("dependencies", []):
                del self.cache[key]
                invalidated += 1

        if invalidated > 0:
            self._save_cache()

        return invalidated

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.cache)
        total_hits = sum(e.get("cache_hits", 0) for e in self.cache.values())
        total_time_saved = sum(
            e.get("runtime_seconds", 0) * e.get("cache_hits", 0) for e in self.cache.values()
        )

        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "total_time_saved_seconds": total_time_saved,
            "average_time_saved_per_hit": total_time_saved / total_hits if total_hits > 0 else 0,
        }
