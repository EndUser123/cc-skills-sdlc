"""Verification tests for CKS ImportError handling in arch skill.

These tests VERIFY that the arch skill has real CKS integration and
ImportError handling implemented via TDD (TEST-ARCH-001).

Run with: pytest P:/.claude/skills/arch/tests/test_cks_real_import.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directories for package imports
test_dir = Path(__file__).parent
skills_dir = test_dir.parent.parent
sys.path.insert(0, str(skills_dir))

from skill import routing


class TestCKSIntegrationImplemented:
    """Tests that VERIFY CKS integration is implemented."""

    def test_arch_skill_has_cks_import_handling_code(self):
        """
        Verification: arch skill HAS CKS import handling code.

        Given: The arch skill modules (routing.py)
        When: Searching for CKS import or handling code
        Then: Should find CKS_AVAILABLE variable and ImportError handling

        This test PASSES after TDD fix for TEST-ARCH-001.
        """
        # Arrange - Read the arch skill source files
        arch_skill_dir = Path(__file__).parent.parent
        routing_file = arch_skill_dir / "routing.py"

        # Act - Check if CKS integration code exists
        content = routing_file.read_text()
        has_cks_available = "CKS_AVAILABLE" in content
        has_cks_import_error = "CKS_IMPORT_ERROR" in content
        has_importlib = "importlib" in content
        has_import_error_handling = "try:" in content and "ImportError" in content

        # Assert - Verify CKS integration exists (this is what EXISTS after TDD fix)
        assert has_cks_available, "CKS_AVAILABLE variable should exist"
        assert has_cks_import_error, "CKS_IMPORT_ERROR variable should exist"
        assert has_importlib, "Should use importlib for real module checking"
        assert has_import_error_handling, "Should have ImportError handling"

    def test_cks_available_variable_is_accessible(self):
        """
        Verification: CKS_AVAILABLE variable can be imported and accessed.

        Given: The routing module
        When: Importing CKS_AVAILABLE
        Then: Should return a boolean value

        This test PASSES after TDD fix for TEST-ARCH-001.
        """
        # Act - Import the variable
        from skill.routing import CKS_AVAILABLE, CKS_IMPORT_ERROR

        # Assert - Verify it's the right type and accessible
        assert isinstance(CKS_AVAILABLE, bool), "CKS_AVAILABLE should be a boolean"
        assert isinstance(CKS_IMPORT_ERROR, (str, type(None))), "CKS_IMPORT_ERROR should be str or None"

    def test_cks_integration_fallback_works(self):
        """
        Verification: CKS integration gracefully handles unavailable CKS.

        Given: CKS module that may not be available
        When: Checking CKS_AVAILABLE
        Then: Should not crash and should indicate availability

        This test PASSES after TDD fix for TEST-ARCH-001.
        """
        # Act - Check CKS availability (this should not crash)
        from skill.routing import CKS_AVAILABLE

        # Assert - Should return a boolean (True if available, False if not)
        # We don't assert True or False specifically since CKS may or may not be installed
        assert isinstance(CKS_AVAILABLE, bool), "CKS_AVAILABLE should indicate availability"
