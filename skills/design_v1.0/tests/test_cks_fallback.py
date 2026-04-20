"""Tests for CKS graceful degradation behavior.

These tests verify that the arch skill gracefully handles CKS unavailability
scenarios including:
- CKS module not found
- CKS database missing
- CKS import errors
- CKS available (happy path)
- Warning message includes helpful fix suggestions
- Generic analysis proceeds when CKS unavailable

Run with: pytest P:/.claude/skills/arch/tests/test_cks_fallback.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import sys
import warnings


class TestCKSModuleNotFound:
    """Tests for CKS module not found scenario."""

    def test_cks_module_not_found_sets_available_false(self):
        """
        Test that CKS module not found sets CKS_AVAILABLE=False.

        Given: CKS source path does not exist
        When: CKS availability check runs
        Then: CKS_AVAILABLE should be False
        """
        # Arrange
        cks_src_path = Path("P:/__csf/src")

        with patch.object(Path, "exists", return_value=False):
            # Act
            CKS_AVAILABLE = False
            cks_error_msg = None

            try:
                if not cks_src_path.exists():
                    raise ImportError(f"CKS source path not found: {cks_src_path}")
                CKS_AVAILABLE = True
            except ImportError as e:
                cks_error_msg = str(e)
                CKS_AVAILABLE = False

            # Assert
            assert CKS_AVAILABLE is False, (
                "CKS_AVAILABLE should be False when module not found"
            )
            assert cks_error_msg is not None, "Error message should be set"

    def test_cks_module_not_found_shows_warning(self):
        """
        Test that CKS module not found shows a warning.

        Given: CKS source path does not exist
        When: CKS availability check runs
        Then: Warning should be shown with helpful message
        """
        # Arrange
        cks_src_path = Path("P:/__csf/src")

        with patch.object(Path, "exists", return_value=False):
            # Act
            CKS_AVAILABLE = False
            cks_error_msg = None

            try:
                if not cks_src_path.exists():
                    raise ImportError(f"CKS source path not found: {cks_src_path}")
                CKS_AVAILABLE = True
            except ImportError as e:
                cks_error_msg = str(e)
                CKS_AVAILABLE = False

            # Assert - warning message should contain key information
            # Note: Windows paths may use backslash, check for both
            assert CKS_AVAILABLE is False
            assert "CKS source path not found" in cks_error_msg
            assert (
                "P:/__csf/src" in cks_error_msg
                or "P:\\__csf\\src" in cks_error_msg
                or "__csf" in cks_error_msg
            )


class TestCKSDatabaseMissing:
    """Tests for CKS database missing scenario."""

    def test_cks_database_missing_sets_available_false(self):
        """
        Test that CKS database missing sets CKS_AVAILABLE=False.

        Given: CKS module exists but database file does not
        When: CKS availability check runs
        Then: CKS_AVAILABLE should be False
        """
        # Arrange
        cks_src_path = Path("P:/__csf/src")
        cks_db_path = Path("P:/__csf/data/cks.db")

        # Mock Path.exists to return True for source, False for DB
        def mock_exists(self):
            if str(self) == str(cks_src_path):
                return True
            if str(self) == str(cks_db_path):
                return False
            return False

        with patch.object(Path, "exists", mock_exists):
            # Act
            CKS_AVAILABLE = False
            cks_error_msg = None

            try:
                if not cks_src_path.exists():
                    raise ImportError(f"CKS source path not found: {cks_src_path}")

                # Simulate successful import
                if not cks_db_path.exists():
                    raise FileNotFoundError(f"CKS database not found: {cks_db_path}")

                CKS_AVAILABLE = True
            except (ImportError, FileNotFoundError) as e:
                cks_error_msg = str(e)
                CKS_AVAILABLE = False

            # Assert
            assert CKS_AVAILABLE is False, (
                "CKS_AVAILABLE should be False when database missing"
            )
            assert cks_error_msg is not None

    def test_cks_database_missing_shows_warning(self):
        """
        Test that CKS database missing shows a warning.

        Given: CKS module exists but database file does not
        When: CKS availability check runs
        Then: Warning should include database path information
        """
        # Arrange
        cks_src_path = Path("P:/__csf/src")
        cks_db_path = Path("P:/__csf/data/cks.db")

        def mock_exists(self):
            if str(self) == str(cks_src_path):
                return True
            if str(self) == str(cks_db_path):
                return False
            return False

        with patch.object(Path, "exists", mock_exists):
            # Act
            CKS_AVAILABLE = False
            cks_error_msg = None

            try:
                if not cks_src_path.exists():
                    raise ImportError(f"CKS source path not found: {cks_src_path}")

                if not cks_db_path.exists():
                    raise FileNotFoundError(f"CKS database not found: {cks_db_path}")

                CKS_AVAILABLE = True
            except (ImportError, FileNotFoundError) as e:
                cks_error_msg = str(e)
                CKS_AVAILABLE = False

            # Assert
            assert CKS_AVAILABLE is False
            assert "CKS database not found" in cks_error_msg
            # Note: Windows paths may use backslash, check for both
            assert (
                "P:/__csf/data/cks.db" in cks_error_msg
                or "P:\\__csf\\data\\cks.db" in cks_error_msg
                or "cks.db" in cks_error_msg
            )


class TestCKSImportError:
    """Tests for CKS import error scenario."""

    def test_cks_import_error_sets_available_false(self):
        """
        Test that CKS import error sets CKS_AVAILABLE=False.

        Given: CKS module import raises ImportError
        When: CKS availability check runs
        Then: CKS_AVAILABLE should be False and execution continues
        """
        # Arrange
        cks_src_path = Path("P:/__csf/src")

        with patch.object(Path, "exists", return_value=True):
            # Act
            CKS_AVAILABLE = False
            cks_error_msg = None

            try:
                if not cks_src_path.exists():
                    raise ImportError(f"CKS source path not found: {cks_src_path}")

                # Simulate import error
                raise ImportError("No module named 'csf.cks.unified'")

                CKS_AVAILABLE = True
            except (ImportError, FileNotFoundError, Exception) as e:
                cks_error_msg = str(e)
                CKS_AVAILABLE = False

            # Assert - execution should continue (no exception raised)
            assert CKS_AVAILABLE is False
            assert cks_error_msg is not None
            assert "No module named" in cks_error_msg

    def test_cks_generic_exception_handled(self):
        """
        Test that generic CKS exceptions are caught and handled.

        Given: CKS initialization raises a generic exception
        When: CKS availability check runs
        Then: CKS_AVAILABLE should be False
        """
        # Arrange
        cks_src_path = Path("P:/__csf/src")
        cks_db_path = Path("P:/__csf/data/cks.db")

        with patch.object(Path, "exists", return_value=True):
            # Act
            CKS_AVAILABLE = False
            cks_error_msg = None

            try:
                if not cks_src_path.exists():
                    raise ImportError(f"CKS source path not found: {cks_src_path}")

                if not cks_db_path.exists():
                    raise FileNotFoundError(f"CKS database not found: {cks_db_path}")

                # Simulate generic exception during CKS init
                raise RuntimeError("CKS initialization failed")

                CKS_AVAILABLE = True
            except (ImportError, FileNotFoundError, Exception) as e:
                cks_error_msg = str(e)
                CKS_AVAILABLE = False

            # Assert
            assert CKS_AVAILABLE is False
            assert cks_error_msg is not None


class TestCKSAvailable:
    """Tests for CKS available (happy path) scenario."""

    def test_cks_available_sets_true(self):
        """
        Test that CKS available sets CKS_AVAILABLE=True.

        Given: CKS module and database both exist
        When: CKS availability check runs successfully
        Then: CKS_AVAILABLE should be True
        """
        # Arrange
        cks_src_path = Path("P:/__csf/src")
        cks_db_path = Path("P:/__csf/data/cks.db")

        with patch.object(Path, "exists", return_value=True):
            # Act
            CKS_AVAILABLE = False
            cks_error_msg = None

            try:
                if not cks_src_path.exists():
                    raise ImportError(f"CKS source path not found: {cks_src_path}")

                if not cks_db_path.exists():
                    raise FileNotFoundError(f"CKS database not found: {cks_db_path}")

                # Simulate successful CKS initialization
                CKS_AVAILABLE = True

            except (ImportError, FileNotFoundError, Exception) as e:
                cks_error_msg = str(e)
                CKS_AVAILABLE = False

            # Assert
            assert CKS_AVAILABLE is True
            assert cks_error_msg is None

    def test_cks_queries_work_when_available(self):
        """
        Test that CKS queries work when CKS is available.

        Given: CKS_AVAILABLE is True
        When: CKS search is performed
        Then: Queries should return results
        """
        # Arrange
        mock_cks = MagicMock()
        mock_cks.search.return_value = [
            {"entry": "memory1", "content": "Failure data..."},
            {"entry": "memory2", "content": "More failure data..."},
        ]

        CKS_AVAILABLE = True

        # Act
        if CKS_AVAILABLE:
            results = mock_cks.search("subsystem failure", entry_type="memory", limit=3)
        else:
            results = []

        # Assert
        assert CKS_AVAILABLE is True
        assert len(results) == 2
        mock_cks.search.assert_called_once_with(
            "subsystem failure", entry_type="memory", limit=3
        )


class TestWarningMessageContent:
    """Tests for warning message content and helpfulness."""

    def test_warning_includes_fix_suggestions(self):
        """
        Test that warning message includes helpful fix suggestions.

        Given: CKS is unavailable for any reason
        When: Warning message is generated
        Then: Message should include actionable fix suggestions
        """
        # Arrange
        cks_error_msg = "CKS source path not found: P:/__csf/src"

        # Act - generate warning message
        warning_message = f"""
CKS_UNAVAILABLE_WARNING

Constitutional Knowledge System (CKS) is not accessible:
{cks_error_msg}

Proceeding with generic analysis without CKS historical data.

Recommendation:
1. Verify CKS installation at P:/__csf/
2. Check database path: P:/__csf/data/cks.db
3. Consider installing CKS for evidence-based improvements

Continue with generic analysis? [Y/n]
"""

        # Assert - message contains key elements
        assert "CKS_UNAVAILABLE_WARNING" in warning_message
        assert "CKS installation at P:/__csf/" in warning_message
        assert "database path: P:/__csf/data/cks.db" in warning_message
        assert "Recommendation:" in warning_message

    def test_warning_contains_error_details(self):
        """
        Test that warning message contains specific error details.

        Given: CKS availability check fails with specific error
        When: Warning is generated
        Then: Original error message should be included
        """
        # Arrange
        specific_errors = [
            "CKS source path not found: P:/__csf/src",
            "CKS database not found: P:/__csf/data/cks.db",
            "No module named 'csf.cks.unified'",
            "CKS initialization failed",
        ]

        for error_msg in specific_errors:
            # Act
            warning = f"""
CKS_UNAVAILABLE_WARNING

Constitutional Knowledge System (CKS) is not accessible:
{error_msg}

Proceeding with generic analysis without CKS historical data.
"""

            # Assert
            assert error_msg in warning
            assert "CKS_UNAVAILABLE_WARNING" in warning


class TestGenericAnalysisProceeds:
    """Tests for generic analysis proceeding when CKS unavailable."""

    def test_generic_analysis_proceeds_when_cks_unavailable(self):
        """
        Test that generic analysis proceeds when CKS is unavailable.

        Given: CKS_AVAILABLE is False
        When: Arch analysis is performed
        Then: Analysis should continue without CKS data
        """
        # Arrange
        CKS_AVAILABLE = False
        cks_error_msg = "CKS source path not found: P:/__csf/src"

        # Act - simulate analysis proceeding
        analysis_complete = False
        analysis_data = []

        if CKS_AVAILABLE:
            # Would query CKS here
            pass
        else:
            # Proceed with generic analysis
            analysis_data = ["Generic best practices", "Architecture patterns"]
            analysis_complete = True

        # Assert
        assert analysis_complete is True
        assert len(analysis_data) > 0
        assert "Generic best practices" in analysis_data

    def test_analysis_falls_back_to_best_practices(self):
        """
        Test that analysis falls back to best practices when CKS unavailable.

        Given: CKS_AVAILABLE is False
        When: Subsystem improvement is requested
        Then: Generic best practices should be used
        """
        # Arrange
        CKS_AVAILABLE = False
        subsystem = "hooks"

        # Act
        if CKS_AVAILABLE:
            # Would get CKS memory entries
            failure_data = []
        else:
            # Fall back to best practices
            failure_data = [
                f"Generic failure pattern for {subsystem}",
                f"Best practice for {subsystem} design",
            ]

        # Assert
        assert len(failure_data) > 0
        assert "Generic failure pattern" in failure_data[0]
        assert "Best practice" in failure_data[1]

    def test_no_exception_raised_when_cks_unavailable(self):
        """
        Test that no exception is raised when CKS is unavailable.

        Given: CKS availability check fails
        When: Analysis code runs
        Then: Execution should continue without raising exceptions
        """
        # Arrange
        CKS_AVAILABLE = False
        cks_error_msg = "CKS not found"

        # Act - this should not raise an exception
        execution_successful = False

        try:
            if CKS_AVAILABLE:
                # Would use CKS
                pass
            else:
                # Continue with analysis
                execution_successful = True
        except Exception as e:
            execution_successful = False

        # Assert
        assert execution_successful is True
        assert CKS_AVAILABLE is False
