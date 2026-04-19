#!/usr/bin/env python3
"""Test result caching across sessions."""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_cache import TestCache, calculate_file_hash, calculate_test_key


def test_calculate_file_hash_consistency():
    """Test that same file produces same hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("print('hello world')")

        hash1 = calculate_file_hash(test_file)
        hash2 = calculate_file_hash(test_file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters


def test_calculate_file_hash_different_content():
    """Test that different files produce different hashes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "file1.py"
        file2 = Path(tmpdir) / "file2.py"

        file1.write_text("content A")
        file2.write_text("content B")

        hash1 = calculate_file_hash(file1)
        hash2 = calculate_file_hash(file2)

        assert hash1 != hash2


def test_calculate_file_hash_nonexistent():
    """Test that nonexistent file returns empty string."""
    nonexistent = Path("/nonexistent/file/that/does/not/exist.py")
    hash_result = calculate_file_hash(nonexistent)

    assert hash_result == ""


def test_calculate_test_key_test_file_only():
    """Test cache key calculation with test file only (no dependencies)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_module.py"
        test_file.write_text("def test_something():\n    assert True")

        key = calculate_test_key(test_file, [])

        # Should produce consistent SHA256 hash
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


def test_calculate_test_key_with_dependencies():
    """Test that cache key includes test file + dependencies."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_module.py"
        dep1 = Path(tmpdir) / "module.py"
        dep2 = Path(tmpdir) / "utils.py"

        test_file.write_text("test code")
        dep1.write_text("module code")
        dep2.write_text("utils code")

        # Key with dependencies
        key_with_deps = calculate_test_key(test_file, [dep1, dep2])

        # Key without dependencies should be different
        key_no_deps = calculate_test_key(test_file, [])

        assert key_with_deps != key_no_deps
        assert len(key_with_deps) == 64


def test_calculate_test_key_deterministic():
    """Test that same inputs produce same cache key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        dep = Path(tmpdir) / "dep.py"

        test_file.write_text("same test")
        dep.write_text("same dep")

        key1 = calculate_test_key(test_file, [dep])
        key2 = calculate_test_key(test_file, [dep])

        assert key1 == key2


def test_calculate_test_key_with_nonexistent_dependency():
    """Test that nonexistent dependency is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        nonexistent_dep = Path("/nonexistent/dep.py")

        test_file.write_text("test code")

        # Should not raise exception
        key = calculate_test_key(test_file, [nonexistent_dep])

        # Should still produce valid hash (just from test file)
        assert len(key) == 64


def test_cache_get_set():
    """Test storing and retrieving cache entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = TestCache(cache_path)

        test_key = "abc123"
        result_data = {"status": "passed", "tests_run": 5}

        # Set cache entry
        cache.set(
            test_key=test_key,
            result=result_data,
            dependencies=["module.py"],
            runtime_seconds=2.5,
        )

        # Get cache entry
        retrieved = cache.get(test_key)

        assert retrieved is not None
        assert retrieved["result"] == result_data
        assert retrieved["dependencies"] == ["module.py"]
        assert retrieved["runtime_seconds"] == 2.5
        assert "timestamp" in retrieved


def test_cache_get_missing():
    """Test that get returns None for missing key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = TestCache(cache_path)

        result = cache.get("nonexistent_key")

        assert result is None


def test_cache_set_increments_hits():
    """Test that set increments cache_hits counter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = TestCache(cache_path)

        test_key = "test_key"

        # First set
        cache.set(
            test_key=test_key,
            result={"status": "passed"},
            dependencies=[],
            runtime_seconds=1.0,
        )

        entry1 = cache.get(test_key)
        assert entry1["cache_hits"] == 1

        # Second set (should increment)
        cache.set(
            test_key=test_key,
            result={"status": "passed"},
            dependencies=[],
            runtime_seconds=1.0,
        )

        entry2 = cache.get(test_key)
        assert entry2["cache_hits"] == 2


def test_cache_persists_to_disk():
    """Test that cache is persisted and can be reloaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"

        # Create cache and add entry
        cache1 = TestCache(cache_path)
        cache1.set(
            test_key="persist_key",
            result={"tests": 10},
            dependencies=["a.py", "b.py"],
            runtime_seconds=5.0,
        )

        # Create new cache instance (should load from disk)
        cache2 = TestCache(cache_path)
        retrieved = cache2.get("persist_key")

        assert retrieved is not None
        assert retrieved["result"] == {"tests": 10}
        assert retrieved["dependencies"] == ["a.py", "b.py"]


def test_cache_invalidate_by_dependency():
    """Test that invalidate removes entries depending on a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"

        # Create test file to hash
        dep_file = Path(tmpdir) / "dependency.py"
        dep_file.write_text("dependency content")

        # Calculate hash of dependency
        dep_hash = calculate_file_hash(dep_file)

        # Create cache with entries
        cache = TestCache(cache_path)
        cache.set(
            test_key="test1",
            result={"status": "passed"},
            dependencies=[dep_hash],  # Depends on this file
            runtime_seconds=1.0,
        )
        cache.set(
            test_key="test2",
            result={"status": "passed"},
            dependencies=["other_hash"],  # Different dependency
            runtime_seconds=1.0,
        )

        # Verify both entries exist
        assert cache.get("test1") is not None
        assert cache.get("test2") is not None

        # Invalidate by dependency file
        invalidated = cache.invalidate(dep_file)

        # Should invalidate 1 entry (test1)
        assert invalidated == 1
        assert cache.get("test1") is None
        assert cache.get("test2") is not None


def test_cache_invalidate_no_match():
    """Test that invalidate returns 0 when no entries match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = TestCache(cache_path)

        cache.set(
            test_key="test1",
            result={"status": "passed"},
            dependencies=["hash1", "hash2"],
            runtime_seconds=1.0,
        )

        # Try to invalidate with unrelated file
        unrelated_file = Path(tmpdir) / "unrelated.py"
        unrelated_file.write_text("unrelated content")

        invalidated = cache.invalidate(unrelated_file)

        assert invalidated == 0


def test_cache_get_stats_empty():
    """Test stats calculation for empty cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = TestCache(cache_path)

        stats = cache.get_stats()

        assert stats["total_entries"] == 0
        assert stats["total_hits"] == 0
        assert stats["total_time_saved_seconds"] == 0
        assert stats["average_time_saved_per_hit"] == 0


def test_cache_get_stats_with_entries():
    """Test stats calculation with multiple cache entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"
        cache = TestCache(cache_path)

        # Add multiple entries with different hit counts and runtimes
        cache.set(
            test_key="test1",
            result={"status": "passed"},
            dependencies=[],
            runtime_seconds=2.0,
        )
        cache.set(
            test_key="test2",
            result={"status": "passed"},
            dependencies=[],
            runtime_seconds=3.0,
        )

        # Increment hits for test1 twice more (total 3 hits)
        cache.set(
            test_key="test1",
            result={"status": "passed"},
            dependencies=[],
            runtime_seconds=2.0,
        )
        cache.set(
            test_key="test1",
            result={"status": "passed"},
            dependencies=[],
            runtime_seconds=2.0,
        )

        stats = cache.get_stats()

        assert stats["total_entries"] == 2
        # test1: 3 hits * 2.0s = 6.0s
        # test2: 1 hit * 3.0s = 3.0s
        # Total: 4 hits, 9.0s saved
        assert stats["total_hits"] == 4
        assert stats["total_time_saved_seconds"] == 9.0
        assert stats["average_time_saved_per_hit"] == 9.0 / 4


def test_cache_handles_corrupted_cache_file():
    """Test that corrupted cache file is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.json"

        # Write invalid JSON
        cache_path.write_text("{invalid json content")

        # Cache should still initialize (empty)
        cache = TestCache(cache_path)

        assert cache.cache == {}
        assert cache.get("any_key") is None


if __name__ == "__main__":
    test_calculate_file_hash_consistency()
    print("✅ test_calculate_file_hash_consistency passed")

    test_calculate_file_hash_different_content()
    print("✅ test_calculate_file_hash_different_content passed")

    test_calculate_file_hash_nonexistent()
    print("✅ test_calculate_file_hash_nonexistent passed")

    test_calculate_test_key_test_file_only()
    print("✅ test_calculate_test_key_test_file_only passed")

    test_calculate_test_key_with_dependencies()
    print("✅ test_calculate_test_key_with_dependencies passed")

    test_calculate_test_key_deterministic()
    print("✅ test_calculate_test_key_deterministic passed")

    test_calculate_test_key_with_nonexistent_dependency()
    print("✅ test_calculate_test_key_with_nonexistent_dependency passed")

    test_cache_get_set()
    print("✅ test_cache_get_set passed")

    test_cache_get_missing()
    print("✅ test_cache_get_missing passed")

    test_cache_set_increments_hits()
    print("✅ test_cache_set_increments_hits passed")

    test_cache_persists_to_disk()
    print("✅ test_cache_persists_to_disk passed")

    test_cache_invalidate_by_dependency()
    print("✅ test_cache_invalidate_by_dependency passed")

    test_cache_invalidate_no_match()
    print("✅ test_cache_invalidate_no_match passed")

    test_cache_get_stats_empty()
    print("✅ test_cache_get_stats_empty passed")

    test_cache_get_stats_with_entries()
    print("✅ test_cache_get_stats_with_entries passed")

    test_cache_handles_corrupted_cache_file()
    print("✅ test_cache_handles_corrupted_cache_file passed")

    print("\nAll test_cache tests passed!")
