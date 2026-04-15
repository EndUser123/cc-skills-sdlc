"""CKS integration tests for rca Tier 1 implementation.

These tests verify that the CKS (Constitutional Knowledge System) integration
works correctly for phase state persistence and semantic search.

Run with: pytest P:/.claude/skills/debugrca/tests/test_cks_integration.py -v
"""

import warnings
from pathlib import Path

import pytest


# Helper function to import CKS with deprecation warnings suppressed
def _import_cks():
    """Import CKS module with deprecation warnings suppressed."""
    import sys

    # The CKS stub is at P:/__csf/csf/cks/unified.py which redirects to the archive.
    # Add the csf directory to sys.path so 'from cks.unified import CKS' finds the stub.
    csf_dir = str(Path("P:/__csf/csf").resolve())
    if csf_dir not in sys.path:
        sys.path.insert(0, csf_dir)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        from cks.unified import CKS
    return CKS


class TestCKSImport:
    """Tests for CKS module import and availability."""

    def test_cks_unified_importable(self):
        """Test that CKS unified module can be imported.

        Given: CKS is the storage backend for rca phase state
        When: Attempting to import CKS from cks.unified
        Then: The import should succeed and CKS class should be available
        """
        try:
            # Add CSF src to path if needed
            import sys
            import warnings

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            # Suppress deprecation warnings during CKS import
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from cks.unified import CKS  # noqa: F401

            assert CKS is not None

        except ImportError as e:
            pytest.fail(f"Failed to import CKS from cks.unified: {e}")

    def test_cks_entry_types_includes_rca_phase_state(self):
        """Test that CKS VALID_ENTRY_TYPES includes rca_phase_state.

        Given: Phase state persistence uses a new entry type
        When: Checking CKS VALID_ENTRY_TYPES
        Then: 'rca_phase_state' should be included as a valid entry type
        """
        try:
            import sys

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            from cks.unified import VALID_ENTRY_TYPES  # noqa: F401

            assert (
                "rca_phase_state" in VALID_ENTRY_TYPES
            ), "VALID_ENTRY_TYPES should include 'rca_phase_state' for rca phase persistence"

        except (ImportError, AssertionError) as e:
            pytest.fail(f"rca_phase_state not in VALID_ENTRY_TYPES: {e}")


class TestCKSClientInstantiation:
    """Tests for CKS client instantiation and initialization."""

    def test_cks_client_can_be_instantiated(self):
        """Test that CKS client can be instantiated.

        Given: Phase state manager needs a CKS client
        When: Creating a CKS instance
        Then: The client should initialize successfully
        """
        try:
            import sys

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            from cks.unified import CKS

            # Try to instantiate with default settings
            cks = CKS()
            assert cks is not None
            assert hasattr(cks, "db_path")

        except Exception as e:
            pytest.fail(f"Failed to instantiate CKS client: {e}")

    def test_ks_client_with_custom_db_path(self):
        """Test that CKS client can be instantiated with custom db_path.

        Given: Phase state may use a separate database file
        When: Creating CKS with custom db_path
        Then: The client should initialize with the custom path
        """
        try:
            import sys
            import warnings
            from pathlib import Path

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            # Suppress deprecation warnings during CKS import
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from cks.unified import CKS

            custom_path = "P:/.claude/state/debugrca/phase_state.db"
            cks = CKS(db_path=custom_path)

            assert cks is not None
            # Normalize paths for comparison (Windows path differences)
            assert str(Path(cks.db_path)).replace("\\", "/") == custom_path.replace("\\", "/")

        except Exception as e:
            pytest.fail(f"Failed to instantiate CKS with custom path: {e}")

    def test_cks_client_context_manager(self):
        """Test that CKS client works as a context manager.

        Given: Phase state operations should use context management
        When: Using CKS with 'with' statement
        Then: The client should enter and exit cleanly
        """
        try:
            import sys

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            from cks.unified import CKS

            with CKS() as cks:
                assert cks is not None
                # Context manager should provide clean exit

        except Exception as e:
            pytest.fail(f"CKS context manager failed: {e}")


class TestCKSSemanticSearch:
    """Tests for CKS semantic search availability for evidence clustering."""

    def test_cks_search_semantic_method_exists(self):
        """Test that CKS has search_semantic method.

        Given: Evidence clustering uses semantic search
        When: Checking CKS for search_semantic method
        Then: The method should be available
        """
        try:
            import sys
            import warnings

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            # Suppress deprecation warnings during CKS import
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from cks.unified import CKS

            cks = CKS()
            assert hasattr(
                cks, "search_semantic"
            ), "CKS should have search_semantic method for evidence clustering"

        except Exception as e:
            pytest.fail(f"CKS search_semantic method not available: {e}")

    def test_cks_semantic_search_with_query(self):
        """Test that CKS semantic search accepts query parameter.

        Given: Evidence saturation detection requires semantic comparison
        When: Calling search_semantic with a test query
        Then: The method should accept the query and return results

        Note: This test uses a context manager to ensure proper cleanup
        of CKS resources. ResourceWarnings from symspellpy's internal
        database are suppressed as they originate from the library itself.
        """
        try:
            import sys
            import warnings

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            # Suppress deprecation warnings during CKS import
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from cks.unified import CKS

            # Suppress ResourceWarnings from symspellpy's internal database
            # These are library-internal and not under our control
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning)
                # Use context manager for proper resource cleanup
                with CKS() as cks:
                    results = cks.search_semantic("authentication error")

                    # Should return a list (possibly empty if no data)
                    assert isinstance(
                        results, list
                    ), "search_semantic should return a list of results"

        except Exception as e:
            pytest.fail(f"CKS semantic search failed: {e}")


class TestCKSPhaseStateStorage:
    """Tests for CKS-based phase state persistence."""

    def test_save_phase_state_to_cks(self):
        """Test that phase state can be saved to CKS.

        Given: Phase output needs to be persisted
        When: Saving phase state to CKS with entry_type='rca_phase_state'
        Then: The state should be stored and retrievable
        """
        try:
            import sys

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            from cks.unified import CKS
            from rca.phase_state_manager import PhaseStateManager

            state_manager = PhaseStateManager()

            # Test data for phase 1 (Gather)
            phase_output = {
                "phase": "gather",
                "evidence": ["Error in auth module", "Stack trace shows timeout"],
                "clusters": [["auth error", "timeout"]],
            }

            # Save the phase state
            state_id = state_manager.save(
                phase="gather",
                output=phase_output,
                session_id="test-session-123",
            )

            assert state_id is not None, "save() should return a state_id"
            assert isinstance(state_id, str), "state_id should be a string"

        except (ImportError, AttributeError, TypeError) as e:
            pytest.fail(f"Failed to save phase state to CKS: {e}")

    def test_restore_phase_state_from_cks(self):
        """Test that phase state can be restored from CKS.

        Given: A phase state was previously saved
        When: Restoring the phase state using state_id
        Then: The original state should be retrieved
        """
        try:
            import sys
            import warnings

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            # Filter CKS deprecation warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from cks.unified import CKS

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            from rca.phase_state_manager import PhaseStateManager

            state_manager = PhaseStateManager()

            # First, save a phase state
            phase_output = {
                "phase": "isolate",
                "patterns": ["Pattern A", "Pattern B"],
                "cluster_count": 2,
            }

            state_id = state_manager.save(
                phase="isolate",
                output=phase_output,
                session_id="test-session-456",
            )

            # Then, restore it
            restored_state = state_manager.restore(state_id)

            assert restored_state is not None, "restore() should return the state"
            assert restored_state["phase"] == "isolate", "restored phase should match"
            assert restored_state["patterns"] == [
                "Pattern A",
                "Pattern B",
            ], "restored patterns should match"

        except (ImportError, AttributeError, TypeError) as e:
            pytest.fail(f"Failed to restore phase state from CKS: {e}")

    def test_list_phases_for_session(self):
        """Test that all phases for a session can be listed.

        Given: Multiple phases have been completed in a session
        When: Listing phases for a session_id
        Then: All completed phases should be returned in order
        """
        try:
            import sys
            import warnings

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            # Filter CKS deprecation warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from cks.unified import CKS

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            from rca.phase_state_manager import PhaseStateManager

            state_manager = PhaseStateManager()
            session_id = "test-session-list"

            # Save multiple phases
            state_manager.save(phase="gather", output={"evidence": []}, session_id=session_id)
            state_manager.save(phase="isolate", output={"patterns": []}, session_id=session_id)
            state_manager.save(
                phase="hypothesize", output={"hypotheses": []}, session_id=session_id
            )

            # List phases
            phases = state_manager.list_phases(session_id)

            assert isinstance(phases, list), "list_phases() should return a list"
            assert len(phases) == 3, "should have 3 phases"
            assert phases == ["gather", "isolate", "hypothesize"], "phases should be in order"

        except (ImportError, AttributeError, TypeError) as e:
            pytest.fail(f"Failed to list phases from CKS: {e}")

    def test_get_resume_point(self):
        """Test that next phase to execute can be determined.

        Given: A session with some completed phases
        When: Getting the resume point for the session
        Then: The next uncompleted phase should be returned
        """
        try:
            import sys
            import warnings

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            # Filter CKS deprecation warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                from cks.unified import CKS

            package_src = str(Path("P:/packages/rca/src").resolve())
            if package_src not in sys.path:
                sys.path.insert(0, package_src)

            # Try lowercase import first, fall back to uppercase
            from rca.phase_state_manager import PhaseStateManager

            state_manager = PhaseStateManager()
            session_id = "test-session-resume"

            # Complete first two phases
            state_manager.save(phase="gather", output={"evidence": []}, session_id=session_id)
            state_manager.save(phase="isolate", output={"patterns": []}, session_id=session_id)

            # Get resume point
            resume_phase = state_manager.get_resume_point(session_id)

            assert (
                resume_phase == "hypothesize"
            ), "resume point should be next phase after completed ones"

        except (ImportError, AttributeError, TypeError) as e:
            pytest.fail(f"Failed to get resume point: {e}")


class TestCKSEntryTypeValidation:
    """Tests for CKS entry type validation for rca."""

    def test_rca_phase_state_is_valid_entry_type(self):
        """Test that 'rca_phase_state' is recognized as valid CKS entry type.

        Given: Phase state uses a custom entry type
        When: Validating the entry type against CKS
        Then: 'rca_phase_state' should be a valid entry type
        """
        try:
            import sys

            csf_src = str(Path("P:/__csf/csf").resolve())
            if csf_src not in sys.path:
                sys.path.insert(0, csf_src)

            from cks.unified import VALID_ENTRY_TYPES

            assert (
                "rca_phase_state" in VALID_ENTRY_TYPES
            ), "rca_phase_state must be a valid CKS entry type"

        except (ImportError, AssertionError) as e:
            pytest.fail(f"rca_phase_state entry type validation failed: {e}")
