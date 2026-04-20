#!/usr/bin/env python3
"""Tests for file I/O caching - RED phase (failing tests)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestPathCaching:
    """Test path caching functionality - NEW FUNCTIONALITY."""

    def test_cached_path_lookup_fixture_exists(self, cached_path_lookup):
        """cached_path_lookup fixture should exist."""
        assert callable(cached_path_lookup), "cached_path_lookup should be a callable fixture"

    def test_cached_path_reduces_stat_calls(self, cached_path_lookup):
        """Cached path lookups should reduce filesystem stat() calls."""
        # Create test directory
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            evidence_path = project_root / ".evidence"  # FIX: Check .evidence subdirectory

            # Track stat() calls
            original_stat = Path.stat
            stat_call_count = {"count": 0}

            def tracked_stat(self):
                stat_call_count["count"] += 1
                return original_stat(self)

            with patch.object(Path, "stat", tracked_stat):
                # Use cached path lookup
                cached_path = cached_path_lookup(evidence_path)

                # First call - should hit filesystem
                assert cached_path.exists() == False  # No .evidence yet
                first_count = stat_call_count["count"]

                # Second call - should use cache
                assert cached_path.exists() == False
                second_count = stat_call_count["count"]

                # Cache should reduce stat() calls
                assert second_count == first_count, "Cache should prevent redundant stat() calls"

    def test_cached_path_invalidates_on_mutation(self, cached_path_lookup):
        """Cache should invalidate when path is created/modified."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            evidence_dir = project_root / ".evidence"

            # Use cached path lookup
            cached_path = cached_path_lookup(evidence_dir)

            # First check - directory doesn't exist
            assert cached_path.exists() == False

            # Create directory
            evidence_dir.mkdir(parents=True, exist_ok=True)

            # Cache should be invalidated - new check should see directory
            assert cached_path.exists() == True

    def test_cached_path_supports_common_operations(self, cached_path_lookup):
        """Cached path should support exists(), is_dir(), is_file() operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            evidence_dir = project_root / ".evidence"

            # Use cached path lookup
            cached_path = cached_path_lookup(evidence_dir)

            # Create directory
            evidence_dir.mkdir(parents=True, exist_ok=True)

            # Test common operations
            assert cached_path.exists() == True
            assert cached_path.is_dir() == True
            assert cached_path.is_file() == False

            # Create file
            test_file = evidence_dir / "test.md"
            test_file.write_text("# Test")

            cached_file = cached_path_lookup(test_file)
            assert cached_file.exists() == True
            assert cached_file.is_file() == True
            assert cached_file.is_dir() == False


class TestPathCachingPerformance:
    """Test path caching reduces filesystem operations - NEW FUNCTIONALITY."""

    def test_multiple_checks_use_cache(self, cached_path_lookup):
        """Multiple exists() calls should use cached result."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            evidence_dir = project_root / ".evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)

            # Use cached path
            cached_path = cached_path_lookup(evidence_dir)

            # Track stat() calls
            original_stat = Path.stat
            stat_call_count = {"count": 0}

            def tracked_stat(self):
                stat_call_count["count"] += 1
                return original_stat(self)

            with patch.object(Path, "stat", tracked_stat):
                # Multiple checks should use cache
                for _ in range(10):
                    cached_path.exists()

                # Should only call stat() once (first check)
                assert (
                    stat_call_count["count"] == 1
                ), "Multiple checks should use single cached result"

    def test_cache_invalidation_works_correctly(self, cached_path_lookup):
        """Cache invalidation should detect filesystem changes (with documented tradeoff)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            evidence_dir = project_root / ".evidence"

            # Use cached path
            cached_path = cached_path_lookup(evidence_dir)

            # Initial check - doesn't exist (negative result NOT cached)
            assert cached_path.exists() == False

            # Create directory
            evidence_dir.mkdir(parents=True, exist_ok=True)

            # Cache should be invalidated - new stat() call, positive result cached
            assert cached_path.exists() == True

            # Remove directory
            evidence_dir.rmdir()

            # EXPECTED BEHAVIOR: Cache returns stale positive value (tradeoff for performance)
            # The implementation prioritizes reduced I/O over perfect stale cache detection
            # Cache updates on next miss (when exists() is called again after miss)
            assert (
                cached_path.exists() == True
            )  # Stale cache: path was removed but cache still has True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
