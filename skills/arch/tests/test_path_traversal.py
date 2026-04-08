#!/usr/bin/env python3
"""
Path Traversal Vulnerability Tests for SEC-001.

Security Issue: resolve_template_path() does NOT validate template_name input
for path traversal attacks like "../", absolute paths, null bytes, etc.

These tests document the VULNERABLE behavior of the current implementation.
The function only checks for empty/whitespace strings but allows:
- "../" sequences (directory traversal)
- Absolute paths (bypass resource directory)
- Null bytes (potential string truncation attacks)
- URL-encoded sequences

Run with: pytest P:/.claude/skills/arch/tests/test_path_traversal.py -v

Expected: All tests FAIL because the function does NOT validate these inputs
          (this is the RED phase - documenting the vulnerability)

Security Fix: In GREEN phase, add input validation to reject malicious inputs.
"""

import pytest
import sys
from pathlib import Path

# Add the parent directory to the path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from cross_platform_paths import resolve_template_path


class TestPathTraversalVulnerability:
    """
    Tests for path traversal vulnerabilities in resolve_template_path().

    SECURITY ISSUE (SEC-001): The function currently does NOT validate
    template_name for path traversal attacks. These tests document the
    vulnerable behavior.

    Current Behavior (VULNERABLE):
    - Path traversal sequences like "../" are allowed
    - Absolute paths bypass the resource directory
    - Null bytes are not filtered
    - URL-encoded sequences are not decoded/validated

    Expected Behavior (AFTER FIX):
    - All malicious inputs should raise ValueError
    - Only safe template names should be accepted
    """

    # -------------------------------------------------------------------------
    # Test Case 1: Double-dot attack (../)
    # -------------------------------------------------------------------------

    def test_path_traversal_with_double_dot_attack(self):
        """
        Test that "../" path traversal attacks are REJECTED.

        Given: A template_name containing "../" directory traversal sequence
        When: Calling resolve_template_path("../../../etc/passwd")
        Then: Should raise ValueError (SECURITY: reject path traversal)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts "../../../etc/passwd" and returns it in the path
        - This allows escaping the resources directory

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError for path traversal sequences

        Security Impact: HIGH - allows reading arbitrary files
        """
        # Arrange
        malicious_template = "../../../etc/passwd"

        # Act & Assert
        # This SHOULD raise ValueError but currently DOESN'T (vulnerable)
        with pytest.raises(ValueError, match=r"(path traversal|traversal|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    def test_path_traversal_single_double_dot(self):
        """
        Test that simple "../" path traversal is REJECTED.

        Given: A template_name containing "../"
        When: Calling resolve_template_path("../secret")
        Then: Should raise ValueError (SECURITY: reject path traversal)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts "../secret" without validation

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError
        """
        # Arrange
        malicious_template = "../secret"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(path traversal|traversal|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    def test_path_traversal_double_dot_in_middle(self):
        """
        Test that "../" in the middle of path is REJECTED.

        Given: A template_name with "../" in the middle
        When: Calling resolve_template_path("templates/../../etc/passwd")
        Then: Should raise ValueError (SECURITY: reject path traversal)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts complex traversal sequences

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError
        """
        # Arrange
        malicious_template = "templates/../../etc/passwd"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(path traversal|traversal|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    # -------------------------------------------------------------------------
    # Test Case 2: Absolute path attack
    # -------------------------------------------------------------------------

    def test_path_traversal_with_absolute_path(self):
        """
        Test that absolute paths are REJECTED.

        Given: A template_name with absolute path
        When: Calling resolve_template_path("/etc/passwd")
        Then: Should raise ValueError (SECURITY: reject absolute paths)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts "/etc/passwd" and returns it
        - This bypasses the resources directory entirely

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError for absolute paths

        Security Impact: HIGH - allows accessing any file on the system
        """
        # Arrange
        malicious_template = "/etc/passwd"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(absolute path|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    def test_path_traversal_windows_absolute_path(self):
        """
        Test that Windows absolute paths are REJECTED.

        Given: A template_name with Windows absolute path
        When: Calling resolve_template_path("C:\\Windows\\System32\\config")
        Then: Should raise ValueError (SECURITY: reject absolute paths)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts Windows drive letters

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError for drive-letter paths
        """
        # Arrange
        malicious_template = "C:\\Windows\\System32\\config"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(absolute path|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    def test_path_traversal_p_drive_absolute_path(self):
        """
        Test that P:/ drive absolute paths are REJECTED.

        Given: A template_name with P:/ absolute path
        When: Calling resolve_template_path("P:/__csf/data/secret")
        Then: Should raise ValueError (SECURITY: reject absolute paths)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts P:/ drive paths

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError
        """
        # Arrange
        malicious_template = "P:/__csf/data/secret"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(absolute path|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    # -------------------------------------------------------------------------
    # Test Case 3: Null byte attack
    # -------------------------------------------------------------------------

    def test_path_traversal_with_null_byte(self):
        """
        Test that null bytes are REJECTED.

        Given: A template_name containing null byte
        When: Calling resolve_template_path("fast\x00.md")
        Then: Should raise ValueError (SECURITY: reject null bytes)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts null bytes
        - Null bytes can truncate strings in C-based systems

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError for null bytes

        Security Impact: MEDIUM - potential string truncation attacks
        CVE Reference: CVE-2006-2073 (similar vulnerability in PHP)
        """
        # Arrange
        malicious_template = "fast\x00.md"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(null byte|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    def test_path_traversal_null_byte_with_traversal(self):
        """
        Test that null bytes combined with traversal are REJECTED.

        Given: A template_name with null byte and traversal
        When: Calling resolve_template_path("../../etc\x00/passwd")
        Then: Should raise ValueError (SECURITY: reject null bytes)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts complex attacks with null bytes

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError
        """
        # Arrange
        malicious_template = "../../etc\x00/passwd"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(null byte|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    # -------------------------------------------------------------------------
    # Test Case 4: URL encoding attack
    # -------------------------------------------------------------------------

    def test_path_traversal_with_url_encoding(self):
        """
        Test that URL-encoded traversal sequences are REJECTED.

        Given: A template_name with URL-encoded "../" (%2e%2e%2f)
        When: Calling resolve_template_path("fast%2e%2e%2fsecret")
        Then: Should raise ValueError (SECURITY: reject URL-encoded traversal)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts URL-encoded sequences
        - These may be decoded by other parts of the system

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError for URL-encoded traversal patterns
        - Should either decode and validate, or reject encoded input

        Security Impact: MEDIUM - bypasses naive filters
        """
        # Arrange
        malicious_template = "fast%2e%2e%2fsecret"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(url.*encoded|encoded|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    def test_path_traversal_with_double_encoded(self):
        """
        Test that double-encoded traversal is REJECTED.

        Given: A template_name with double-encoded "%252e%252e%252f"
        When: Calling resolve_template_path("safe%252e%252e%252fetc")
        Then: Should raise ValueError (SECURITY: reject encoded traversal)

        CURRENT BEHAVIOR (VULNERABLE):
        - The function accepts multiple encoding layers

        EXPECTED BEHAVIOR (AFTER FIX):
        - Should raise ValueError
        """
        # Arrange
        malicious_template = "safe%252e%252e%252fetc"

        # Act & Assert
        with pytest.raises(ValueError, match=r"(url.*encoded|encoded|invalid|unsafe)"):
            resolve_template_path(malicious_template)

    # -------------------------------------------------------------------------
    # Test Case 5: Valid inputs (should still work after fix)
    # -------------------------------------------------------------------------

    def test_valid_template_name_still_works(self):
        """
        Test that valid template names still work after security fix.

        Given: A legitimate template_name
        When: Calling resolve_template_path("fast")
        Then: Should return the correct template path

        This test ensures the security fix doesn't break legitimate usage.
        """
        # Arrange
        valid_template = "fast"

        # Act
        result = resolve_template_path(valid_template)

        # Assert
        assert result == "/.claude/skills/arch/resources/fast.md"
        assert ".." not in result
        assert result.startswith("/.claude/skills/arch/resources/")

    def test_valid_template_with_hyphen(self):
        """
        Test that valid templates with hyphens work.

        Given: A template_name with hyphens (valid)
        When: Calling resolve_template_path("data-pipeline")
        Then: Should return the correct template path

        Hyphens are valid in template names but "../" and similar are not.
        """
        # Arrange
        valid_template = "data-pipeline"

        # Act
        result = resolve_template_path(valid_template)

        # Assert
        assert result == "/.claude/skills/arch/resources/data-pipeline.md"
        assert ".." not in result


# -------------------------------------------------------------------------
# Test helper function to document vulnerability
# -------------------------------------------------------------------------

def test_security_vulnerability_documentation():
    """
    Documentation test for SEC-001 path traversal vulnerability.

    This test summarizes the security issue and expected fix.

    VULNERABILITY SUMMARY:
    ----------------------
    File: cross_platform_paths.py
    Function: resolve_template_path(template_name: str)
    Line: ~118

    CURRENT VALIDATION (Insufficient):
        if not template_name or not template_name.strip():
            raise ValueError(...)

    MISSING VALIDATION:
    - No check for "../" directory traversal
    - No check for absolute paths ("/" or drive letters)
    - No check for null bytes (\x00)
    - No check for URL-encoded sequences (%2e%2e%2f)

    RECOMMENDED FIX:
    1. Add validation for ".." in template_name
    2. Add validation for path separators (/, \\) at start
    3. Add validation for null bytes
    4. Consider URL-decode before validation OR reject % characters
    5. Use a whitelist of allowed characters (a-z, 0-9, -, _)

    CVSS SCORE (Estimate): 7.5 (HIGH)
    - Attack Vector: Network (if template_name from web input)
    - Attack Complexity: Low
    - Privileges Required: None
    - User Interaction: None
    - Impact: High (confidentiality breach)
    """
    # This test is documentation only
    # It documents the security issue for developers
    assert True, "Documentation test - see docstring for vulnerability details"


class TestWindowsSpecificPathTraversal:
    """
    TEST-ARCH-009: Windows-specific path traversal edge cases.

    Tests for Windows-specific path formats that could bypass validation:
    - UNC paths (\\server\share)
    - Drive-relative paths (C:file.txt)
    - Reserved device names (CON, PRN, NUL, AUX, COM1-9, LPT1-9)

    These tests verify that resolve_template_path() properly handles
    Windows-specific edge cases that could be used for path traversal attacks.
    """

    def test_windows_unc_path_should_be_rejected(self):
        """
        Test that Windows UNC paths are REJECTED.

        Given: A template_name containing Windows UNC path (\\\\server\\share\\file)
        When: resolve_template_path() is called
        Then: Should raise ValueError

        UNC paths allow accessing network shares and bypass local directory restrictions.
        Format: \\\\server\\share\\path or //server/path

        Security Fix: The function should detect and reject UNC path patterns.
        """
        # Test various UNC path formats
        unc_paths = [
            "\\\\localhost\\share\\template",
            "\\\\127.0.0.1\\c$\\windows\\system32",
            "//server/share/file",
            "\\\\\\?\\C:\\Windows\\System32",  # Extended-length path
        ]

        for unc_path in unc_paths:
            with pytest.raises(ValueError, match=r"(Invalid|template|path)"):
                resolve_template_path(unc_path)

    def test_windows_drive_relative_path_should_be_rejected(self):
        """
        Test that Windows drive-relative paths are REJECTED.

        Given: A template_name containing drive-relative path (C:file.txt)
        When: resolve_template_path() is called
        Then: Should raise ValueError

        Drive-relative paths reference files relative to the current directory
        on a specific drive, bypassing resource directory restrictions.

        Security Fix: The function should detect and reject drive letter patterns.
        """
        drive_relative_paths = [
            "C:template.md",
            "D:file.txt",
            "E:\\Windows\\System32\\config",
            "C:/Windows/System32",
        ]

        for path in drive_relative_paths:
            with pytest.raises(ValueError, match=r"(Invalid|template|path)"):
                resolve_template_path(path)

    def test_windows_reserved_device_names_documentation(self):
        """
        DOCUMENTATION TEST: Windows reserved device names are NOT currently validated.

        TEST-ARCH-009: This test documents that resolve_template_path() does NOT
        reject Windows reserved device names (CON, PRN, NUL, AUX, COM1-9, LPT1-9).

        CURRENT BEHAVIOR (VULNERABLE):
        - Reserved device names are accepted without validation
        - On Windows, these names could access system devices
        - On Unix, they pass through as ordinary names

        SECURITY GAP:
        Windows reserves specific device names that could be used for device
        access attacks. The function should validate against these names.

        Reserved Names:
        - CON, PRN, NUL, AUX
        - COM1-9 (serial ports)
        - LPT1-9 (parallel ports)
        - Also reserved with extensions: CON.txt, NUL.md, etc.

        This test documents the security gap for future fix.
        """
        reserved_names = [
            "CON", "PRN", "NUL", "AUX",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
            "CON.txt",  # Reserved names with extensions are also reserved
            "NUL.md",
        ]

        # SECURITY GAP: These names are NOT currently rejected
        # This test documents the vulnerability - it PASSES because the function
        # does NOT validate against Windows reserved device names
        for name in reserved_names:
            # The function should reject these, but currently doesn't
            # This is a security gap documented by TEST-ARCH-009
            try:
                result = resolve_template_path(name)
                # If we get here, the name was accepted (security gap)
                # This test documents that behavior
            except ValueError as e:
                # If ValueError is raised, check if it's specifically for reserved names
                # Currently, this is NOT expected (no reserved name validation)
                if "reserved" in str(e).lower():
                    # Good - reserved names are being rejected
                    pass
                else:
                    # Different error - allow it
                    pass

    def test_windows_absolute_paths_should_be_rejected(self):
        """
        Test that Windows absolute paths are REJECTED.

        Given: A template_name containing Windows absolute path
        When: resolve_template_path() is called
        Then: Should raise ValueError

        Windows absolute paths can bypass resource directory restrictions.

        Security Fix: The function should detect and reject absolute path patterns.
        """
        absolute_paths = [
            "C:\\Windows\\System32\\config",
            "D:/Program Files/Application/config",
            "C:\\\\Windows\\\\System32",  # Double backslashes
        ]

        for path in absolute_paths:
            with pytest.raises(ValueError, match=r"(Invalid|template|path)"):
                resolve_template_path(path)

    def test_valid_template_names_still_work(self):
        """
        Test that valid template names still work after security fixes.

        Given: Legitimate template names
        When: resolve_template_path() is called
        Then: Should NOT raise ValueError

        This ensures security fixes don't break legitimate use cases.
        """
        valid_names = [
            "fast",
            "deep",
            "python",
            "data-pipeline",
            "cli-template",
            "my-custom-template",
            "template_v2",
        ]

        for name in valid_names:
            # Should not raise ValueError for valid names
            try:
                result = resolve_template_path(name)
                # We don't check the exact result since it depends on file existence
                # Just verify it doesn't raise ValueError for invalid input
            except ValueError as e:
                if "Invalid" in str(e) or "template" in str(e).lower():
                    pytest.fail(f"Valid template name '{name}' was rejected: {e}")
                # Re-raise if it's a different ValueError (e.g., file not found)
                raise
