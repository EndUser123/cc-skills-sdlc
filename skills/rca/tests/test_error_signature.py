"""Error signature extraction and matching tests for rca.

These tests verify error signature pattern matching, hash generation,
and serialization for RCA workflow.

Run with: pytest P:/packages/rca/skill/tests/test_error_signature.py -v
"""

import pytest

from rca.error_signature import (
    FIX_TEMPLATES,
    SIGNATURE_DESCRIPTIONS,
    SIGNATURE_PATTERNS,
    ErrorSignature,
    ErrorSignatureExtractor,
    PatternFixRecord,
    SignatureMatch,
    extract_signature,
    match_to_pattern,
)


class TestErrorSignatureCreation:
    """Tests for creating error signatures from exceptions."""

    def test_create_signature_from_none_dict_access(self):
        """Test creating signature from None dict access error.

        Given: An error message indicating None dict access
        When: Creating an ErrorSignature
        Then: Signature should match null_dict_access pattern
        """
        error_message = "AttributeError: 'NoneType' object has no attribute '__getitem__'"
        signature = extract_signature(error_message)

        assert signature is not None, "Should extract signature from error"
        assert (
            signature.pattern_name == "null_dict_access"
        ), f"Expected 'null_dict_access', got '{signature.pattern_name}'"
        assert (
            signature.error_type == "AttributeError"
        ), f"Expected 'AttributeError', got '{signature.error_type}'"

    def test_create_signature_from_missing_import(self):
        """Test creating signature from missing import error.

        Given: An error message indicating missing module
        When: Creating an ErrorSignature
        Then: Signature should match missing_import pattern
        """
        error_message = "ModuleNotFoundError: No module named 'requests'"
        signature = extract_signature(error_message)

        assert signature is not None, "Should extract signature from error"
        assert (
            signature.pattern_name == "missing_import"
        ), f"Expected 'missing_import', got '{signature.pattern_name}'"
        assert (
            signature.error_type == "ModuleNotFoundError"
        ), f"Expected 'ModuleNotFoundError', got '{signature.error_type}'"

    def test_create_signature_from_file_not_found(self):
        """Test creating signature from file not found error.

        Given: An error message indicating file not found
        When: Creating an ErrorSignature
        Then: Signature should match file_not_found pattern
        """
        error_message = (
            "FileNotFoundError: [Errno 2] No such file or directory: '/path/to/file.txt'"
        )
        signature = extract_signature(error_message)

        assert signature is not None, "Should extract signature from error"
        assert (
            signature.pattern_name == "file_not_found"
        ), f"Expected 'file_not_found', got '{signature.pattern_name}'"
        assert (
            signature.error_type == "FileNotFoundError"
        ), f"Expected 'FileNotFoundError', got '{signature.error_type}'"

    def test_create_signature_from_unknown_error(self):
        """Test creating signature from unknown error pattern.

        Given: An error message that doesn't match any pattern
        When: Creating an ErrorSignature
        Then: Should return None
        """
        error_message = "CustomError: something unexpected happened"
        signature = extract_signature(error_message)

        assert signature is None, f"Expected None for unknown error, got {signature}"


class TestSignatureMatching:
    """Tests for matching similar error signatures."""

    def test_same_signature_different_locations(self):
        """Test that same error pattern gets same signature.

        Given: Two errors with same pattern but different locations
        When: Extracting signatures from both
        Then: Both should have the same pattern_name
        """
        error1 = """
Traceback (most recent call last):
  File "download_handler.py", line 127, in get_vtt
    options = yt_dlp_options["format"]
AttributeError: 'NoneType' object has no attribute '__getitem__'
"""

        error2 = """
Traceback (most recent call last):
  File "batch_downloader.py", line 85, in download
    videos = channel["videos"]
AttributeError: 'NoneType' object has no attribute '__getitem__'
"""

        sig1 = extract_signature(error1)
        sig2 = extract_signature(error2)

        assert sig1 is not None, "Should extract signature from error1"
        assert sig2 is not None, "Should extract signature from error2"
        assert (
            sig1.pattern_name == sig2.pattern_name
        ), f"Same pattern should have same signature: {sig1.pattern_name} != {sig2.pattern_name}"

    def test_different_patterns_different_signatures(self):
        """Test that different error patterns get different signatures.

        Given: Two errors with different patterns
        When: Extracting signatures from both
        Then: Both should have different pattern_names
        """
        error1 = "AttributeError: 'NoneType' object has no attribute '__getitem__'"
        error2 = "ModuleNotFoundError: No module named 'requests'"

        sig1 = extract_signature(error1)
        sig2 = extract_signature(error2)

        assert sig1 is not None, "Should extract signature from error1"
        assert sig2 is not None, "Should extract signature from error2"
        assert (
            sig1.pattern_name != sig2.pattern_name
        ), "Different patterns should have different signatures"

    def test_signature_matches_method(self):
        """Test ErrorSignature.matches() method.

        Given: An ErrorSignature instance
        When: Calling matches() with error messages
        Then: Should return True for matching messages, False otherwise
        """
        signature = ErrorSignature(pattern_name="null_dict_access", error_type="AttributeError")

        matching_message = "AttributeError: 'NoneType' object has no attribute '__getitem__'"
        non_matching_message = "ModuleNotFoundError: No module named 'requests'"

        assert signature.matches(matching_message), "Should match error message with same pattern"
        assert not signature.matches(
            non_matching_message
        ), "Should not match error message with different pattern"

    def test_extract_multiple_signatures(self):
        """Test extracting all matching signatures from error.

        Given: An error message that could match multiple patterns
        When: Calling extract_signatures()
        Then: Should return all matching signatures
        """
        error_message = "AttributeError: 'NoneType' object has no attribute '__getitem__'"
        signatures = ErrorSignatureExtractor.extract_signatures(error_message)

        assert len(signatures) > 0, "Should extract at least one signature"
        assert any(
            sig.pattern_name == "null_dict_access" for sig in signatures
        ), "Should include null_dict_access pattern"


class TestSignatureHashGeneration:
    """Tests for generating consistent hash for signature."""

    def test_signature_hash_is_deterministic(self):
        """Test that signature hash is consistent for same signature.

        Given: The same ErrorSignature instance
        When: Calling signature_hash multiple times
        Then: Should return the same hash each time
        """
        signature = ErrorSignature(pattern_name="null_dict_access", error_type="AttributeError")

        hash1 = signature.signature_hash
        hash2 = signature.signature_hash

        assert hash1 == hash2, f"Hash should be deterministic: {hash1} != {hash2}"
        assert len(hash1) == 12, f"Hash should be 12 characters, got {len(hash1)}"

    def test_different_signatures_different_hashes(self):
        """Test that different signatures have different hashes.

        Given: Two different ErrorSignature instances
        When: Generating hashes for both
        Then: Hashes should be different
        """
        sig1 = ErrorSignature(pattern_name="null_dict_access", error_type="AttributeError")
        sig2 = ErrorSignature(pattern_name="missing_import", error_type="ModuleNotFoundError")

        hash1 = sig1.signature_hash
        hash2 = sig2.signature_hash

        assert (
            hash1 != hash2
        ), f"Different signatures should have different hashes: {hash1} == {hash2}"

    def test_hash_includes_pattern_and_error_type(self):
        """Test that hash includes both pattern_name and error_type.

        Given: Two signatures with same pattern but different error types
        When: Generating hashes for both
        Then: Hashes should be different
        """
        sig1 = ErrorSignature(pattern_name="missing_key", error_type="KeyError")
        sig2 = ErrorSignature(pattern_name="missing_key", error_type="AttributeError")

        hash1 = sig1.signature_hash
        hash2 = sig2.signature_hash

        assert hash1 != hash2, f"Hashes should differ when error_type differs: {hash1} == {hash2}"


class TestSignatureSerialization:
    """Tests for serializing and deserializing signatures."""

    def test_signature_match_to_dict(self):
        """Test converting SignatureMatch to dictionary.

        Given: A SignatureMatch instance
        When: Calling to_dict()
        Then: Should return dictionary with all fields
        """
        signature = ErrorSignature(pattern_name="null_dict_access", error_type="AttributeError")
        match = SignatureMatch(
            signature=signature,
            confidence=0.9,
            matched_text="AttributeError: 'NoneType'",
            suggested_fix="Use dict.get(key, default)",
        )

        result = match.to_dict()

        assert isinstance(result, dict), "to_dict() should return a dictionary"
        assert (
            result["pattern_name"] == "null_dict_access"
        ), f"Expected 'null_dict_access', got {result['pattern_name']}"
        assert (
            result["error_type"] == "AttributeError"
        ), f"Expected 'AttributeError', got {result['error_type']}"
        assert result["confidence"] == 0.9, f"Expected confidence 0.9, got {result['confidence']}"
        assert (
            result["matched_text"] == "AttributeError: 'NoneType'"
        ), f"Expected matched text, got {result['matched_text']}"
        assert (
            result["suggested_fix"] == "Use dict.get(key, default)"
        ), f"Expected fix template, got {result['suggested_fix']}"

    def test_pattern_fix_record_to_dict(self):
        """Test converting PatternFixRecord to dictionary.

        Given: A PatternFixRecord instance
        When: Calling to_dict()
        Then: Should return dictionary with all fields
        """
        signature = ErrorSignature(pattern_name="null_dict_access", error_type="AttributeError")
        record = PatternFixRecord(
            signature=signature,
            fix_description="Add None check before dict access",
            fix_template="if dict is not None: dict.get(key)",
            code_diff="- dict[key]\n+ dict.get(key, default)",
            applied_count=3,
            locations_seen=["file1.py:10", "file2.py:20"],
            first_seen="2024-01-01",
            last_seen="2024-01-15",
            verified=True,
        )

        result = record.to_dict()

        assert isinstance(result, dict), "to_dict() should return a dictionary"
        assert (
            result["pattern_name"] == "null_dict_access"
        ), f"Expected 'null_dict_access', got {result['pattern_name']}"
        assert (
            result["applied_count"] == 3
        ), f"Expected applied_count 3, got {result['applied_count']}"
        assert (
            len(result["locations_seen"]) == 2
        ), f"Expected 2 locations, got {len(result['locations_seen'])}"
        assert result["verified"] is True, f"Expected verified=True, got {result['verified']}"

    def test_pattern_fix_record_from_dict(self):
        """Test creating PatternFixRecord from dictionary.

        Given: A dictionary with PatternFixRecord data
        When: Calling PatternFixRecord.from_dict()
        Then: Should create PatternFixRecord with correct fields
        """
        data = {
            "pattern_name": "null_dict_access",
            "error_type": "AttributeError",
            "fix_description": "Add None check",
            "fix_template": "if dict is not None: dict.get(key)",
            "code_diff": "- dict[key]\n+ dict.get(key, default)",
            "applied_count": 5,
            "locations_seen": ["file1.py:10", "file2.py:20", "file3.py:30"],
            "first_seen": "2024-01-01",
            "last_seen": "2024-01-15",
            "verified": True,
        }

        record = PatternFixRecord.from_dict(data)

        assert (
            record.signature.pattern_name == "null_dict_access"
        ), f"Expected 'null_dict_access', got {record.signature.pattern_name}"
        assert (
            record.signature.error_type == "AttributeError"
        ), f"Expected 'AttributeError', got {record.signature.error_type}"
        assert record.applied_count == 5, f"Expected applied_count 5, got {record.applied_count}"
        assert (
            len(record.locations_seen) == 3
        ), f"Expected 3 locations, got {len(record.locations_seen)}"
        assert record.verified is True, f"Expected verified=True, got {record.verified}"

    def test_pattern_fix_record_roundtrip(self):
        """Test that serialization roundtrip preserves data.

        Given: A PatternFixRecord instance
        When: Converting to dict and back
        Then: Should preserve all fields
        """
        original = PatternFixRecord(
            signature=ErrorSignature(
                pattern_name="missing_import", error_type="ModuleNotFoundError"
            ),
            fix_description="Install missing module",
            fix_template="pip install {module}",
            code_diff="+ import requests",
            applied_count=1,
            locations_seen=["app.py:5"],
            first_seen="2024-02-01",
            last_seen="2024-02-01",
            verified=False,
        )

        # Serialize
        data = original.to_dict()

        # Deserialize
        restored = PatternFixRecord.from_dict(data)

        # Verify all fields match
        assert (
            restored.signature.pattern_name == original.signature.pattern_name
        ), "pattern_name should match"
        assert (
            restored.signature.error_type == original.signature.error_type
        ), "error_type should match"
        assert restored.fix_description == original.fix_description, "fix_description should match"
        assert restored.fix_template == original.fix_template, "fix_template should match"
        assert restored.code_diff == original.code_diff, "code_diff should match"
        assert restored.applied_count == original.applied_count, "applied_count should match"
        assert restored.locations_seen == original.locations_seen, "locations_seen should match"
        assert restored.first_seen == original.first_seen, "first_seen should match"
        assert restored.last_seen == original.last_seen, "last_seen should match"
        assert restored.verified == original.verified, "verified should match"


class TestSignatureProperties:
    """Tests for ErrorSignature properties."""

    def test_description_property(self):
        """Test ErrorSignature.description property.

        Given: An ErrorSignature instance
        When: Accessing description property
        Then: Should return human-readable description
        """
        signature = ErrorSignature(pattern_name="null_dict_access", error_type="AttributeError")

        description = signature.description

        assert isinstance(description, str), "description should be a string"
        assert len(description) > 0, "description should not be empty"
        assert "dict" in description.lower(), f"Description should mention dict: {description}"

    def test_fix_template_property(self):
        """Test ErrorSignature.fix_template property.

        Given: An ErrorSignature instance
        When: Accessing fix_template property
        Then: Should return fix template
        """
        signature = ErrorSignature(pattern_name="null_dict_access", error_type="AttributeError")

        fix_template = signature.fix_template

        assert isinstance(fix_template, str), "fix_template should be a string"
        assert len(fix_template) > 0, "fix_template should not be empty"
        assert (
            "get" in fix_template.lower() or "none" in fix_template.lower()
        ), f"Fix template should suggest solution: {fix_template}"

    def test_unknown_pattern_description(self):
        """Test description for unknown pattern.

        Given: An ErrorSignature with unknown pattern_name
        When: Accessing description property
        Then: Should return pattern_name as fallback
        """
        signature = ErrorSignature(pattern_name="unknown_pattern", error_type="Error")

        description = signature.description

        assert (
            description == "unknown_pattern"
        ), f"Expected fallback to pattern_name, got {description}"

    def test_unknown_pattern_fix_template(self):
        """Test fix_template for unknown pattern.

        Given: An ErrorSignature with unknown pattern_name
        When: Accessing fix_template property
        Then: Should return generic fix message
        """
        signature = ErrorSignature(pattern_name="unknown_pattern", error_type="Error")

        fix_template = signature.fix_template

        assert isinstance(fix_template, str), "fix_template should be a string"
        assert len(fix_template) > 0, "fix_template should not be empty"


class TestMatchToPattern:
    """Tests for match_to_pattern() function."""

    def test_match_to_pattern_returns_match(self):
        """Test match_to_pattern with matching error.

        Given: An error message that matches a pattern
        When: Calling match_to_pattern()
        Then: Should return SignatureMatch with confidence
        """
        error_message = "AttributeError: 'NoneType' object has no attribute '__getitem__'"
        match = match_to_pattern(error_message)

        assert match is not None, "Should return a match"
        assert isinstance(match, SignatureMatch), "Should return SignatureMatch instance"
        assert match.confidence > 0, "Should have confidence > 0"
        assert len(match.matched_text) > 0, "Should have matched_text"
        assert len(match.suggested_fix) > 0, "Should have suggested_fix"

    def test_match_to_pattern_with_unknown_error(self):
        """Test match_to_pattern with unknown error.

        Given: An error message that doesn't match any pattern
        When: Calling match_to_pattern()
        Then: Should return None
        """
        error_message = "CustomError: something unexpected"
        match = match_to_pattern(error_message)

        assert match is None, f"Should return None for unknown error, got {match}"

    def test_match_confidence_for_specific_patterns(self):
        """Test that specific patterns get higher confidence.

        Given: Error messages for specific patterns
        When: Calling match_to_pattern()
        Then: Should return higher confidence (0.9) for specific patterns
        """
        specific_errors = [
            "AttributeError: 'NoneType' object has no attribute '__getitem__'",
            "ModuleNotFoundError: No module named 'requests'",
            "FileNotFoundError: [Errno 2] No such file or directory",
            "ConnectionError: Failed to establish connection",
            "RuntimeError: Set changed size during iteration",
        ]

        for error_msg in specific_errors:
            match = match_to_pattern(error_msg)
            if match:
                assert (
                    match.confidence == 0.9
                ), f"Specific pattern should have confidence 0.9, got {match.confidence}"


class TestSignaturePatterns:
    """Tests for signature pattern definitions."""

    def test_all_patterns_have_descriptions(self):
        """Test that all defined patterns have descriptions.

        Given: The SIGNATURE_PATTERNS dictionary
        When: Checking SIGNATURE_DESCRIPTIONS
        Then: All patterns should have corresponding descriptions
        """
        for pattern_name in SIGNATURE_PATTERNS.keys():
            assert (
                pattern_name in SIGNATURE_DESCRIPTIONS
            ), f"Pattern '{pattern_name}' missing description"

    def test_all_patterns_have_fix_templates(self):
        """Test that all defined patterns have fix templates.

        Given: The SIGNATURE_PATTERNS dictionary
        When: Checking FIX_TEMPLATES
        Then: All patterns should have corresponding fix templates
        """
        for pattern_name in SIGNATURE_PATTERNS.keys():
            assert pattern_name in FIX_TEMPLATES, f"Pattern '{pattern_name}' missing fix template"

    def test_patterns_are_valid_regex(self):
        """Test that all pattern strings are valid regex.

        Given: The SIGNATURE_PATTERNS dictionary
        When: Compiling each pattern
        Then: All patterns should be valid regex
        """
        import re

        for pattern_name, pattern in SIGNATURE_PATTERNS.items():
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Pattern '{pattern_name}' has invalid regex: {e}")
