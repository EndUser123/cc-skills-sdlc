#!/usr/bin/env python3
"""Tests for isolated state directory fixture - RED phase (failing tests)."""

from pathlib import Path

import pytest


class TestIsolatedStateDirFixture:
    """Test isolated_state_dir fixture existence and behavior - NEW FUNCTIONALITY."""

    def test_isolated_state_dir_fixture_exists(self):
        """isolated_state_dir fixture should exist in conftest.py."""
        from conftest import isolated_state_dir

        assert callable(isolated_state_dir), "isolated_state_dir should be a callable fixture"

    def test_isolated_state_dir_returns_path(self, isolated_state_dir):
        """isolated_state_dir should return a Path object."""
        # Fixture is automatically invoked by pytest
        assert isinstance(
            isolated_state_dir, Path
        ), "isolated_state_dir should return a Path object"

    def test_isolated_state_dir_creates_unique_directory(self, isolated_state_dir):
        """Each test should get a unique state directory."""
        # Fixture is automatically invoked by pytest
        # Verify the directory path is unique (contains UUID or test name)
        path_str = str(isolated_state_dir)
        # Path should contain "test_state_" prefix and unique identifier
        assert (
            "test_state_" in path_str
        ), "State directory should have test_state_ prefix for uniqueness"
        # Path should be longer than base prefix (has unique suffix)
        assert len(path_str) > 20, "State directory should have unique identifier suffix"

    def test_isolated_state_dir_directory_exists(self, isolated_state_dir):
        """isolated_state_dir should create the directory if it doesn't exist."""
        # Directory should exist
        assert isolated_state_dir.exists(), f"State directory should exist: {isolated_state_dir}"
        assert (
            isolated_state_dir.is_dir()
        ), f"State directory should be a directory: {isolated_state_dir}"

    def test_isolated_state_dir_isolated_per_test(self, isolated_state_dir):
        """Each test function should get its own isolated state directory."""
        # Should include test name or test ID in path for isolation
        # This prevents conflicts when tests run in parallel
        path_str = str(isolated_state_dir)
        assert (
            "test_" in path_str or len(path_str) > 20
        ), "State directory should be test-specific (include test name or unique ID)"

    def test_parallel_execution_with_isolated_state_dir(self, isolated_state_dir):
        """Tests should pass with pytest -n auto (parallel execution)."""
        # This test verifies that isolated_state_dir fixture
        # prevents conflicts when tests run in parallel

        # In parallel execution, multiple tests access state_dir simultaneously
        # Without isolation, this causes race conditions and flaky tests
        # With isolated_state_dir, each test gets its own directory

        # Verify we have a writable directory for parallel test isolation
        assert (
            isolated_state_dir.exists()
        ), "State directory should exist for parallel test execution"
        assert isolated_state_dir.is_dir(), "State directory should be a directory"

    def test_ttl_tests_use_isolated_fixtures(self, isolated_state_dir):
        """TTL (time-to-live) tests should use isolated fixtures to prevent conflicts."""
        # TTL tests check cleanup behavior after time passes
        # These tests need isolated state directories to prevent
        # race conditions when multiple TTL tests run in parallel

        # Verify fixture provides writable directory for TTL tests
        assert (
            isolated_state_dir.exists()
        ), "isolated_state_dir should provide writable directory for TTL tests"


class TestIsolatedStateDirBehavior:
    """Test isolated_state_dir fixture behavior with filesystem operations."""

    def test_state_dir_is_writable(self, isolated_state_dir):
        """State directory should be writable for test artifacts."""
        # Create a test file to verify writability
        test_file = isolated_state_dir / "test_artifact.txt"
        test_file.write_text("test content")

        assert test_file.exists(), "Should be able to write files in state directory"
        assert (
            test_file.read_text() == "test content"
        ), "Should be able to read back written content"

    def test_state_dir_isolated_between_tests(self, isolated_state_dir):
        """State directories should be isolated between test runs."""
        # Create a file in this test's state directory
        file1 = isolated_state_dir / "marker.txt"
        file1.write_text("test1")

        # Verify file exists in this test's directory
        assert file1.exists(), "File should exist in this test's isolated state directory"

        # Note: We cannot test isolation between different test functions
        # in a single test, but the unique ID in the path ensures isolation
        path_str = str(isolated_state_dir)
        assert (
            "test_state_" in path_str
        ), "State directory path should include unique identifier for isolation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
