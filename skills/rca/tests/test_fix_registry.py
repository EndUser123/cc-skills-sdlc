"""Tests for fix_registry module.

These tests verify the Fix Registry functionality for tracking attempted fixes
and their outcomes. Tests follow the requested structure for fix registry operations.

Run with: pytest P:/packages/rca/skill/tests/test_fix_registry.py -v
"""

import tempfile
from pathlib import Path

import pytest

from rca.fix_registry import (
    FixRecord,
    FixRegistry,
    StackTraceFingerprint,
)


class TestFixRegistryAddFix:
    """Tests for registering new fix attempts."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry for testing."""
        temp_dir = tempfile.mkdtemp()
        registry = FixRegistry(cache_dir=temp_dir)
        yield registry
        # Cleanup
        import shutil

        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_fingerprint(self):
        """Create a sample fingerprint for testing."""
        return StackTraceFingerprint(
            file_path="src/yt_fts/download/download_handler.py",
            line_number=127,
            error_type="AttributeError",
            function_name="get_vtt",
        )

    def test_fix_registry_add_fix(self, temp_registry, sample_fingerprint):
        """Test registering a new fix attempt.

        Given: A FixRegistry instance and error fingerprint
        When: Adding a new fix with description and metadata
        Then: The fix should be saved and retrievable
        """
        # Arrange
        fix_description = "Initialize yt_dlp_options before use"
        error_message = "AttributeError: 'NoneType' object has no attribute '__getitem__'"
        commit_hash = "abc123def"
        related_files = ["config.py", "settings.py"]

        # Act
        result = temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description=fix_description,
            verified=True,
            error_message=error_message,
            commit_hash=commit_hash,
            related_files=related_files,
        )

        # Assert
        assert result is True, "add_fix should return True on success"
        assert sample_fingerprint.fingerprint_hash in temp_registry._registry["fingerprints"]

        # Verify the stored data
        stored_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]
        assert stored_data["fix_description"] == fix_description
        assert stored_data["verified"] is True
        assert stored_data["error_message"] == error_message
        assert stored_data["commit_hash"] == commit_hash
        assert set(stored_data["related_files"]) == set(related_files)
        assert stored_data["times_seen"] == 1

    def test_fix_registry_add_fix_minimal(self, temp_registry, sample_fingerprint):
        """Test adding a fix with minimal required parameters.

        Given: A FixRegistry instance and error fingerprint
        When: Adding a fix with only required parameters
        Then: The fix should be saved with default values
        """
        # Act
        result = temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Simple fix description",
        )

        # Assert
        assert result is True
        stored_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]
        assert stored_data["fix_description"] == "Simple fix description"
        assert stored_data["verified"] is False  # Default value
        assert stored_data["times_seen"] == 1
        assert stored_data["related_files"] == []  # Default empty list


class TestFixRegistryUpdateOutcome:
    """Tests for updating fix outcomes."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry for testing."""
        temp_dir = tempfile.mkdtemp()
        registry = FixRegistry(cache_dir=temp_dir)
        yield registry
        # Cleanup
        import shutil

        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_fingerprint(self):
        """Create a sample fingerprint for testing."""
        return StackTraceFingerprint(
            file_path="src/yt_fts/download/download_handler.py",
            line_number=127,
            error_type="AttributeError",
            function_name="get_vtt",
        )

    def test_fix_registry_update_outcome_to_success(self, temp_registry, sample_fingerprint):
        """Test updating a fix outcome to success.

        Given: A fix registry with an existing unverified fix
        When: Updating the same fix with verified=True
        Then: The fix should be marked as verified and retain metadata
        """
        # Arrange - Add initial unverified fix
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Initial fix attempt",
            verified=False,
        )

        initial_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]
        assert initial_data["verified"] is False
        assert initial_data["times_seen"] == 1

        # Act - Update to verified
        result = temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Updated fix description",
            verified=True,
            commit_hash="def456",
        )

        # Assert
        assert result is True
        updated_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]

        # Should be marked as verified now
        assert updated_data["verified"] is True

        # Should have updated fix description (since verified=True)
        assert updated_data["fix_description"] == "Updated fix description"

        # Should have incremented times_seen
        assert updated_data["times_seen"] == 2

        # Should have commit hash
        assert updated_data["commit_hash"] == "def456"

        # Should have last_seen timestamp
        assert "last_seen" in updated_data
        assert len(updated_data["last_seen"]) > 0

    def test_fix_registry_update_outcome_to_failure(self, temp_registry, sample_fingerprint):
        """Test updating a fix outcome to failure.

        Given: A fix registry with an existing verified fix
        When: Updating with an unverified fix
        Then: The verified status should remain True (verified takes precedence)
        """
        # Arrange - Add verified fix
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Working fix",
            verified=True,
        )

        # Act - Try to update with unverified fix
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Attempted alternative fix",
            verified=False,
        )

        # Assert
        updated_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]

        # Verified status should remain True
        assert updated_data["verified"] is True

        # Fix description should NOT change (existing verified fix takes precedence)
        assert updated_data["fix_description"] == "Working fix"

        # Times seen should still increment
        assert updated_data["times_seen"] == 2

    def test_fix_registry_update_outcome_preserves_verified_on_reverify(
        self, temp_registry, sample_fingerprint
    ):
        """Test that re-verifying a fix preserves verified status.

        Given: A fix registry with a verified fix
        When: Updating again with verified=True
        Then: The fix should remain verified
        """
        # Arrange
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Original fix",
            verified=True,
            commit_hash="abc123",
        )

        # Act - Update again with verified=True
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Improved fix description",
            verified=True,
            commit_hash="xyz789",
        )

        # Assert
        updated_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]
        assert updated_data["verified"] is True
        assert updated_data["fix_description"] == "Improved fix description"
        assert updated_data["commit_hash"] == "xyz789"  # Should update commit hash


class TestFixRegistryGetFixHistory:
    """Tests for retrieving fix history for issues."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry with populated data."""
        temp_dir = tempfile.mkdtemp()
        registry = FixRegistry(cache_dir=temp_dir)

        # Add multiple fixes for the same error
        fp1 = StackTraceFingerprint(
            file_path="download_handler.py",
            line_number=127,
            error_type="AttributeError",
            function_name="get_vtt",
        )
        registry.add_fix(fp1, "Fix attempt 1", verified=False)
        registry.add_fix(fp1, "Fix attempt 2", verified=True, commit_hash="abc123")

        # Add a different error
        fp2 = StackTraceFingerprint(
            file_path="batch_downloader.py",
            line_number=85,
            error_type="KeyError",
            function_name="process",
        )
        registry.add_fix(fp2, "Check key exists", verified=True)

        yield registry
        # Cleanup
        import shutil

        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_fingerprint(self):
        """Create a sample fingerprint matching the first fix."""
        return StackTraceFingerprint(
            file_path="download_handler.py",
            line_number=127,
            error_type="AttributeError",
            function_name="get_vtt",
        )

    def test_fix_registry_get_fix_history_exact_match(self, temp_registry, sample_fingerprint):
        """Test retrieving fix history for an exact fingerprint match.

        Given: A registry with multiple fix records
        When: Looking up a fix by exact fingerprint
        Then: Should return the FixRecord with complete history
        """
        # Act
        fix_record = temp_registry.get_fix(sample_fingerprint)

        # Assert
        assert fix_record is not None, "Should find the fix record"
        assert isinstance(fix_record, FixRecord)

        # Verify the fix details
        assert fix_record.fix_description == "Fix attempt 2"  # Latest verified fix
        assert fix_record.verified is True
        assert fix_record.times_seen == 2  # Seen twice (two add_fix calls)
        assert fix_record.commit_hash == "abc123"

        # Verify fingerprint details
        assert fix_record.fingerprint.file_path == "download_handler.py"
        assert fix_record.fingerprint.error_type == "AttributeError"
        assert fix_record.fingerprint.line_number == 127

    def test_fix_registry_get_fix_history_not_found(self, temp_registry):
        """Test retrieving fix history for non-existent fingerprint.

        Given: A registry with existing fixes
        When: Looking up a fingerprint that doesn't exist
        Then: Should return None
        """
        # Arrange
        unknown_fp = StackTraceFingerprint(
            file_path="nonexistent.py",
            line_number=999,
            error_type="ValueError",
            function_name="unknown",
        )

        # Act
        fix_record = temp_registry.get_fix(unknown_fp)

        # Assert
        assert fix_record is None, "Should return None for unknown fingerprint"

    def test_fix_registry_get_fix_history_returns_complete_record(
        self, temp_registry, sample_fingerprint
    ):
        """Test that get_fix returns a complete FixRecord with all fields.

        Given: A registry with a comprehensive fix record
        When: Retrieving the fix record
        Then: All FixRecord fields should be populated
        """
        # Act
        fix_record = temp_registry.get_fix(sample_fingerprint)

        # Assert - Verify all expected fields exist
        assert fix_record is not None
        assert hasattr(fix_record, "fingerprint")
        assert hasattr(fix_record, "fix_description")
        assert hasattr(fix_record, "applied_at")
        assert hasattr(fix_record, "verified")
        assert hasattr(fix_record, "times_seen")
        assert hasattr(fix_record, "last_seen")
        assert hasattr(fix_record, "error_message")
        assert hasattr(fix_record, "commit_hash")
        assert hasattr(fix_record, "related_files")

        # Verify values are not None for populated fields
        assert fix_record.fingerprint is not None
        assert fix_record.fix_description is not None
        assert fix_record.applied_at is not None
        assert fix_record.times_seen > 0
        assert fix_record.last_seen is not None


class TestFixRegistryDuplicateDetection:
    """Tests for detecting duplicate fix attempts."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry for testing."""
        temp_dir = tempfile.mkdtemp()
        registry = FixRegistry(cache_dir=temp_dir)
        yield registry
        # Cleanup
        import shutil

        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_fingerprint(self):
        """Create a sample fingerprint for testing."""
        return StackTraceFingerprint(
            file_path="src/yt_fts/download/download_handler.py",
            line_number=127,
            error_type="AttributeError",
            function_name="get_vtt",
        )

    def test_fix_registry_duplicate_detection_same_fingerprint(
        self, temp_registry, sample_fingerprint
    ):
        """Test detecting duplicate fix attempts for the same fingerprint.

        Given: A registry with an existing fix
        When: Adding the same fix again
        Then: Should update existing record instead of creating duplicate
        """
        # Arrange - Add initial fix
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Initial fix",
            verified=False,
        )

        initial_count = len(temp_registry._registry["fingerprints"])
        initial_data = temp_registry._registry["fingerprints"][
            sample_fingerprint.fingerprint_hash
        ].copy()

        # Act - Try to add same fix again
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Same fix attempt",
            verified=False,
        )

        # Assert
        final_count = len(temp_registry._registry["fingerprints"])
        assert final_count == initial_count, "Should not create new entry"

        # Should have updated the existing record
        updated_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]
        assert updated_data["times_seen"] == initial_data["times_seen"] + 1
        assert updated_data["last_seen"] != initial_data["last_seen"]

    def test_fix_registry_duplicate_detection_different_fingerprints(self, temp_registry):
        """Test that different fingerprints create separate records.

        Given: A registry with an existing fix
        When: Adding a fix for a different fingerprint
        Then: Should create a new separate record
        """
        # Arrange
        fp1 = StackTraceFingerprint(
            file_path="file1.py",
            line_number=10,
            error_type="AttributeError",
            function_name="func1",
        )
        temp_registry.add_fix(fp1, "Fix for file1")

        # Act - Add different fingerprint
        fp2 = StackTraceFingerprint(
            file_path="file2.py",
            line_number=20,
            error_type="KeyError",
            function_name="func2",
        )
        temp_registry.add_fix(fp2, "Fix for file2")

        # Assert
        assert len(temp_registry._registry["fingerprints"]) == 2
        assert fp1.fingerprint_hash in temp_registry._registry["fingerprints"]
        assert fp2.fingerprint_hash in temp_registry._registry["fingerprints"]

    def test_fix_registry_duplicate_detection_similar_fingerprints(self, temp_registry):
        """Test that similar but different fingerprints create separate records.

        Given: A registry with an existing fix
        When: Adding a fix for a similar fingerprint (different line number)
        Then: Should create a new separate record
        """
        # Arrange
        fp1 = StackTraceFingerprint(
            file_path="download_handler.py",
            line_number=127,
            error_type="AttributeError",
            function_name="get_vtt",
        )
        temp_registry.add_fix(fp1, "Fix for line 127")

        # Act - Add similar fingerprint (different line)
        fp2 = StackTraceFingerprint(
            file_path="download_handler.py",
            line_number=128,  # Different line
            error_type="AttributeError",
            function_name="get_vtt",
        )
        temp_registry.add_fix(fp2, "Fix for line 128")

        # Assert
        assert len(temp_registry._registry["fingerprints"]) == 2
        assert fp1.fingerprint_hash != fp2.fingerprint_hash
        assert fp1.fingerprint_hash in temp_registry._registry["fingerprints"]
        assert fp2.fingerprint_hash in temp_registry._registry["fingerprints"]

    def test_fix_registry_duplicate_detection_increments_times_seen(
        self, temp_registry, sample_fingerprint
    ):
        """Test that duplicate attempts increment the times_seen counter.

        Given: A registry with an existing fix
        When: Adding the same fix multiple times
        Then: Each attempt should increment times_seen counter
        """
        # Arrange - Add initial fix
        temp_registry.add_fix(
            fingerprint=sample_fingerprint,
            fix_description="Initial fix",
        )

        initial_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]
        assert initial_data["times_seen"] == 1

        # Act - Add same fix 3 more times
        for i in range(3):
            temp_registry.add_fix(
                fingerprint=sample_fingerprint,
                fix_description=f"Attempt {i+2}",
            )

        # Assert
        final_data = temp_registry._registry["fingerprints"][sample_fingerprint.fingerprint_hash]
        assert final_data["times_seen"] == 4  # 1 initial + 3 attempts
