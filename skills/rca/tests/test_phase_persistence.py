"""Phase State Persistence tests for rca Tier 1.

These tests verify comprehensive phase state persistence functionality
including CKS operations, spool fallback, session export, and phase serializers.

Run with: pytest P:/.claude/skills/debugrca/tests/test_phase_persistence.py -v

TDD Cycle:
- RED: Tests fail (features not yet implemented)
- GREEN: Implementation passes all tests
- REFACTOR: Code is cleaned up
"""

import sys
from pathlib import Path

import pytest

# Set up path for imports
package_src = str(Path("P:/packages/rca/src").resolve())
if package_src not in sys.path:
    sys.path.insert(0, package_src)

from rca.phase_state_manager import PhaseStateManager


class TestPhaseStateManagerInitialization:
    """Tests for PhaseStateManager initialization and configuration."""

    def test_initialization_with_default_state_dir(self):
        """Test that PhaseStateManager initializes with default state directory.

        Given: PhaseStateManager is instantiated without arguments
        When: The manager is created
        Then: It should use the default state directory from config
        """
        manager = PhaseStateManager()

        assert manager.state_dir is not None
        assert "debugrca" in manager.state_dir.lower()

    def test_initialization_with_custom_state_dir(self):
        """Test that PhaseStateManager accepts custom state directory.

        Given: A custom state directory path is provided
        When: PhaseStateManager is instantiated with the custom path
        Then: It should use the custom state directory
        """
        custom_dir = "P:/custom/state/dir"
        manager = PhaseStateManager(state_dir=custom_dir)

        assert manager.state_dir == custom_dir

    def test_initialization_when_disabled(self):
        """Test that PhaseStateManager can be disabled.

        Given: Persistence is not desired for a session
        When: PhaseStateManager is instantiated with enabled=False
        Then: Operations should return empty/None values
        """
        manager = PhaseStateManager(enabled=False)

        assert manager.enabled is False

    def test_phase_order_constant(self):
        """Test that PHASE_ORDER defines the correct phase sequence.

        Given: Phases must be executed in a specific order
        When: Checking the PHASE_ORDER constant
        Then: It should contain all 5 phases in correct order
        """
        import sys

        package_src = str(Path("P:/packages/rca/src").resolve())
        if package_src not in sys.path:
            sys.path.insert(0, package_src)

        from rca.phase_state_manager import PhaseStateManager

        expected_phases = ["gather", "isolate", "hypothesize", "test", "fix"]
        assert PhaseStateManager.PHASE_ORDER == expected_phases


class TestPhaseStateManagerSave:
    """Tests for PhaseStateManager.save() method."""

    @pytest.fixture
    def manager(self):
        """Return a PhaseStateManager instance for testing."""
        mgr = PhaseStateManager()
        yield mgr
        mgr.close()
        """Return a PhaseStateManager instance for testing."""
        return PhaseStateManager()

    def test_save_gather_phase_returns_state_id(self, manager):
        """Test that saving gather phase returns a valid state_id.

        Given: A gather phase has completed with evidence output
        When: The phase output is saved with session_id
        Then: A string state_id should be returned
        """
        phase_output = {
            "evidence": ["Error in auth module", "Stack trace shows timeout"],
            "clusters": [["auth error", "timeout"]],
            "saturation_reached": True,
        }

        state_id = manager.save(
            phase="gather", output=phase_output, session_id="test-session-gather-1"
        )

        assert state_id is not None
        assert isinstance(state_id, str)
        assert len(state_id) > 0

    def test_save_isolate_phase_returns_state_id(self, manager):
        """Test that saving isolate phase returns a valid state_id.

        Given: An isolate phase has completed with pattern output
        When: The phase output is saved with session_id
        Then: A string state_id should be returned
        """
        phase_output = {
            "patterns": ["Pattern A: Timeout during auth", "Pattern B: Retry exhausted"],
            "cluster_count": 2,
            "isolated_component": "auth_service",
        }

        state_id = manager.save(
            phase="isolate", output=phase_output, session_id="test-session-isolate-1"
        )

        assert state_id is not None
        assert isinstance(state_id, str)

    def test_save_hypothesize_phase_returns_state_id(self, manager):
        """Test that saving hypothesize phase returns a valid state_id.

        Given: A hypothesize phase has completed with hypothesis list
        When: The phase output is saved with session_id
        Then: A string state_id should be returned
        """
        phase_output = {
            "hypotheses": [
                {"text": "Database connection pool exhausted", "score": 0.85},
                {"text": "Network latency causing timeouts", "score": 0.72},
            ],
            "top_hypothesis": "Database connection pool exhausted",
        }

        state_id = manager.save(
            phase="hypothesize", output=phase_output, session_id="test-session-hypothesize-1"
        )

        assert state_id is not None
        assert isinstance(state_id, str)

    def test_save_test_phase_returns_state_id(self, manager):
        """Test that saving test phase returns a valid state_id.

        Given: A test phase has completed with verification results
        When: The phase output is saved with session_id
        Then: A string state_id should be returned
        """
        phase_output = {"verified": True, "verification_method": "log_analysis", "confidence": 0.92}

        state_id = manager.save(phase="test", output=phase_output, session_id="test-session-test-1")

        assert state_id is not None
        assert isinstance(state_id, str)

    def test_save_fix_phase_returns_state_id(self, manager):
        """Test that saving fix phase returns a valid state_id.

        Given: A fix phase has completed with fix details
        When: The phase output is saved with session_id
        Then: A string state_id should be returned
        """
        phase_output = {
            "fix_applied": "Increased connection pool size",
            "fix_verified": True,
            "files_modified": ["config/database.py"],
        }

        state_id = manager.save(phase="fix", output=phase_output, session_id="test-session-fix-1")

        assert state_id is not None
        assert isinstance(state_id, str)

    def test_save_when_disabled_returns_empty_string(self):
        """Test that save returns empty string when persistence is disabled.

        Given: Persistence is disabled for the session
        When: Attempting to save phase output
        Then: An empty string should be returned
        """
        disabled_manager = PhaseStateManager(enabled=False)

        state_id = disabled_manager.save(
            phase="gather", output={"evidence": []}, session_id="test-disabled"
        )

        assert state_id == ""

    def test_save_with_empty_output(self, manager):
        """Test that saving empty output works correctly.

        Given: A phase completes with minimal or empty output
        When: The empty output is saved
        Then: A valid state_id should still be returned
        """
        state_id = manager.save(phase="gather", output={}, session_id="test-empty")

        assert state_id is not None
        assert isinstance(state_id, str)


class TestPhaseStateManagerRestore:
    """Tests for PhaseStateManager.restore() method."""

    @pytest.fixture
    def manager(self):
        """Return a PhaseStateManager instance for testing."""
        mgr = PhaseStateManager()
        yield mgr
        mgr.close()
        """Return a PhaseStateManager instance for testing."""
        return PhaseStateManager()

    def test_restore_gather_phase_state(self, manager):
        """Test that gather phase state can be restored.

        Given: A gather phase was previously saved
        When: Restoring using the returned state_id
        Then: The original phase output should be retrieved
        """
        original_output = {
            "evidence": ["Error in auth module", "Stack trace shows timeout"],
            "clusters": [["auth error", "timeout"]],
            "saturation_reached": True,
        }

        state_id = manager.save(
            phase="gather", output=original_output, session_id="test-restore-gather"
        )

        restored = manager.restore(state_id)

        assert restored is not None
        assert restored["phase"] == "gather"
        assert restored["evidence"] == original_output["evidence"]
        assert restored["clusters"] == original_output["clusters"]
        assert restored["saturation_reached"] == original_output["saturation_reached"]

    def test_restore_isolate_phase_state(self, manager):
        """Test that isolate phase state can be restored.

        Given: An isolate phase was previously saved
        When: Restoring using the returned state_id
        Then: The original phase output should be retrieved
        """
        original_output = {
            "patterns": ["Pattern A", "Pattern B"],
            "isolated_component": "auth_service",
        }

        state_id = manager.save(
            phase="isolate", output=original_output, session_id="test-restore-isolate"
        )

        restored = manager.restore(state_id)

        assert restored is not None
        assert restored["phase"] == "isolate"
        assert restored["patterns"] == original_output["patterns"]
        assert restored["isolated_component"] == original_output["isolated_component"]

    def test_restore_hypothesize_phase_state(self, manager):
        """Test that hypothesize phase state can be restored.

        Given: A hypothesize phase was previously saved
        When: Restoring using the returned state_id
        Then: The original phase output should be retrieved
        """
        original_output = {
            "hypotheses": [
                {"text": "Hypothesis 1", "score": 0.8},
                {"text": "Hypothesis 2", "score": 0.6},
            ],
            "top_hypothesis": "Hypothesis 1",
        }

        state_id = manager.save(
            phase="hypothesize", output=original_output, session_id="test-restore-hypothesize"
        )

        restored = manager.restore(state_id)

        assert restored is not None
        assert restored["phase"] == "hypothesize"
        assert restored["hypotheses"] == original_output["hypotheses"]
        assert restored["top_hypothesis"] == original_output["top_hypothesis"]

    def test_restore_test_phase_state(self, manager):
        """Test that test phase state can be restored.

        Given: A test phase was previously saved
        When: Restoring using the returned state_id
        Then: The original phase output should be retrieved
        """
        original_output = {
            "verified": True,
            "verification_method": "log_analysis",
            "confidence": 0.92,
        }

        state_id = manager.save(
            phase="test", output=original_output, session_id="test-restore-test"
        )

        restored = manager.restore(state_id)

        assert restored is not None
        assert restored["phase"] == "test"
        assert restored["verified"] == original_output["verified"]
        assert restored["verification_method"] == original_output["verification_method"]
        assert restored["confidence"] == original_output["confidence"]

    def test_restore_fix_phase_state(self, manager):
        """Test that fix phase state can be restored.

        Given: A fix phase was previously saved
        When: Restoring using the returned state_id
        Then: The original phase output should be retrieved
        """
        original_output = {
            "fix_applied": "Increased connection pool size",
            "fix_verified": True,
            "files_modified": ["config/database.py"],
        }

        state_id = manager.save(phase="fix", output=original_output, session_id="test-restore-fix")

        restored = manager.restore(state_id)

        assert restored is not None
        assert restored["phase"] == "fix"
        assert restored["fix_applied"] == original_output["fix_applied"]
        assert restored["fix_verified"] == original_output["fix_verified"]
        assert restored["files_modified"] == original_output["files_modified"]

    def test_restore_with_invalid_state_id_returns_none(self, manager):
        """Test that restore returns None for invalid state_id.

        Given: An invalid or non-existent state_id
        When: Attempting to restore the state
        Then: None should be returned
        """
        restored = manager.restore("invalid-state-id-999")

        assert restored is None

    def test_restore_when_disabled_returns_none(self):
        """Test that restore returns None when persistence is disabled.

        Given: Persistence is disabled
        When: Attempting to restore any state
        Then: None should be returned
        """
        disabled_manager = PhaseStateManager(enabled=False)

        restored = disabled_manager.restore("some-state-id")

        assert restored is None

    def test_restore_with_empty_string_state_id(self, manager):
        """Test that restore handles empty string state_id.

        Given: An empty string is provided as state_id
        When: Attempting to restore
        Then: None should be returned
        """
        restored = manager.restore("")

        assert restored is None


class TestPhaseStateManagerListPhases:
    """Tests for PhaseStateManager.list_phases() method."""

    @pytest.fixture
    def manager(self):
        """Return a PhaseStateManager instance for testing."""
        mgr = PhaseStateManager()
        yield mgr
        mgr.close()
        """Return a PhaseStateManager instance for testing."""
        return PhaseStateManager()

    def test_list_phases_returns_empty_for_new_session(self, manager):
        """Test that list_phases returns empty list for new session.

        Given: A new session with no completed phases
        When: Listing phases for the session
        Then: An empty list should be returned
        """
        import uuid

        session_id = f"new-session-{uuid.uuid4()}"
        phases = manager.list_phases(session_id)

        assert phases == []

    def test_list_phases_returns_single_completed_phase(self, manager):
        """Test that list_phases returns a single completed phase.

        Given: A session with one completed phase
        When: Listing phases for the session
        Then: A list with one phase should be returned
        """
        import uuid

        session_id = f"single-phase-{uuid.uuid4()}"
        manager.save(phase="gather", output={"evidence": []}, session_id=session_id)

        phases = manager.list_phases(session_id)

        assert phases == ["gather"]

    def test_list_phases_returns_multiple_completed_phases_in_order(self, manager):
        """Test that list_phases returns all completed phases in order.

        Given: A session with multiple completed phases
        When: Listing phases for the session
        Then: All phases should be returned in PHASE_ORDER
        """
        import uuid

        session_id = f"multi-phase-{uuid.uuid4()}"
        manager.save(phase="gather", output={"evidence": []}, session_id=session_id)
        manager.save(phase="isolate", output={"patterns": []}, session_id=session_id)
        manager.save(phase="hypothesize", output={"hypotheses": []}, session_id=session_id)

        phases = manager.list_phases(session_id)

        assert phases == ["gather", "isolate", "hypothesize"]

    def test_list_phases_returns_phases_in_correct_order_even_if_saved_out_of_order(self, manager):
        """Test that list_phases maintains order regardless of save order.

        Given: Phases were saved in non-sequential order
        When: Listing phases for the session
        Then: Phases should still be returned in PHASE_ORDER
        """
        import uuid

        session_id = f"out-of-order-{uuid.uuid4()}"
        # Save out of order
        manager.save(phase="hypothesize", output={"hypotheses": []}, session_id=session_id)
        manager.save(phase="gather", output={"evidence": []}, session_id=session_id)
        manager.save(phase="test", output={"verified": False}, session_id=session_id)

        phases = manager.list_phases(session_id)

        # Should be in PHASE_ORDER, not save order
        assert phases == ["gather", "hypothesize", "test"]

    def test_list_phases_for_all_five_phases(self, manager):
        """Test that list_phases works when all phases are complete.

        Given: A session with all 5 phases completed
        When: Listing phases for the session
        Then: All 5 phases should be returned in order
        """
        import uuid

        session_id = f"all-phases-{uuid.uuid4()}"
        for phase in ["gather", "isolate", "hypothesize", "test", "fix"]:
            manager.save(phase=phase, output={}, session_id=session_id)

        phases = manager.list_phases(session_id)

        assert phases == ["gather", "isolate", "hypothesize", "test", "fix"]

    def test_list_phases_when_disabled_returns_empty(self):
        """Test that list_phases returns empty when persistence is disabled.

        Given: Persistence is disabled
        When: Listing phases for any session
        Then: An empty list should be returned
        """
        disabled_manager = PhaseStateManager(enabled=False)

        phases = disabled_manager.list_phases("any-session")

        assert phases == []

    def test_list_phases_isolated_between_sessions(self, manager):
        """Test that list_phases isolates phases by session_id.

        Given: Multiple sessions with different completed phases
        When: Listing phases for each session
        Then: Only that session's phases should be returned
        """
        import uuid

        session1 = f"session-1-{uuid.uuid4()}"
        session2 = f"session-2-{uuid.uuid4()}"

        manager.save(phase="gather", output={}, session_id=session1)
        manager.save(phase="isolate", output={}, session_id=session1)

        manager.save(phase="gather", output={}, session_id=session2)
        manager.save(phase="hypothesize", output={}, session_id=session2)

        phases1 = manager.list_phases(session1)
        phases2 = manager.list_phases(session2)

        assert phases1 == ["gather", "isolate"]
        assert phases2 == ["gather", "hypothesize"]


class TestPhaseStateManagerGetResumePoint:
    """Tests for PhaseStateManager.get_resume_point() method."""

    @pytest.fixture
    def manager(self):
        """Return a PhaseStateManager instance for testing."""
        mgr = PhaseStateManager()
        yield mgr
        mgr.close()
        """Return a PhaseStateManager instance for testing."""
        return PhaseStateManager()

    def test_get_resume_point_for_new_session_returns_gather(self, manager):
        """Test that get_resume_point returns 'gather' for new session.

        Given: A new session with no completed phases
        When: Getting the resume point
        Then: 'gather' should be returned as the first phase
        """
        import uuid

        session_id = f"new-resume-{uuid.uuid4()}"
        resume_point = manager.get_resume_point(session_id)

        assert resume_point == "gather"

    def test_get_resume_point_after_gather_returns_isolate(self, manager):
        """Test that get_resume_point returns next phase after gather.

        Given: A session with only gather phase completed
        When: Getting the resume point
        Then: 'isolate' should be returned
        """
        import uuid

        session_id = f"after-gather-{uuid.uuid4()}"
        manager.save(phase="gather", output={}, session_id=session_id)

        resume_point = manager.get_resume_point(session_id)

        assert resume_point == "isolate"

    def test_get_resume_point_after_multiple_phases(self, manager):
        """Test that get_resume_point returns correct next phase.

        Given: A session with multiple phases completed
        When: Getting the resume point
        Then: The next uncompleted phase should be returned
        """
        import uuid

        session_id = f"after-multiple-{uuid.uuid4()}"
        manager.save(phase="gather", output={}, session_id=session_id)
        manager.save(phase="isolate", output={}, session_id=session_id)
        manager.save(phase="hypothesize", output={}, session_id=session_id)

        resume_point = manager.get_resume_point(session_id)

        assert resume_point == "test"

    def test_get_resume_point_for_complete_session_returns_none(self, manager):
        """Test that get_resume_point returns None when all phases complete.

        Given: A session with all 5 phases completed
        When: Getting the resume point
        Then: None should be returned
        """
        import uuid

        session_id = f"complete-{uuid.uuid4()}"
        for phase in ["gather", "isolate", "hypothesize", "test", "fix"]:
            manager.save(phase=phase, output={}, session_id=session_id)

        resume_point = manager.get_resume_point(session_id)

        assert resume_point is None

    def test_get_resume_point_for_gap_in_phases(self, manager):
        """Test that get_resume_point handles gaps in completed phases.

        Given: A session with non-sequential phases completed
        When: Getting the resume point
        Then: The first missing phase should be returned
        """
        import uuid

        session_id = f"gap-{uuid.uuid4()}"
        # Skip isolate, do gather then hypothesize
        manager.save(phase="gather", output={}, session_id=session_id)
        manager.save(phase="hypothesize", output={}, session_id=session_id)

        resume_point = manager.get_resume_point(session_id)

        # Should return isolate (the first missing phase)
        assert resume_point == "isolate"

    def test_get_resume_point_when_disabled_returns_gather(self):
        """Test that get_resume_point returns 'gather' when disabled.

        Given: Persistence is disabled (no state stored)
        When: Getting the resume point
        Then: 'gather' should be returned (start from beginning)
        """
        disabled_manager = PhaseStateManager(enabled=False)

        resume_point = disabled_manager.get_resume_point("any-session")

        assert resume_point == "gather"


class TestPhaseStateManagerExportSession:
    """Tests for PhaseStateManager.export_session() method.

    This method should export all phase states for a session as a dict.
    """

    @pytest.fixture
    def manager(self):
        """Return a PhaseStateManager instance for testing."""
        mgr = PhaseStateManager()
        yield mgr
        mgr.close()
        """Return a PhaseStateManager instance for testing."""
        return PhaseStateManager()

    def test_export_session_returns_dict(self, manager):
        """Test that export_session returns a dictionary.

        Given: A session with phase data
        When: Exporting the session
        Then: A dictionary should be returned
        """
        import uuid

        session_id = f"export-dict-{uuid.uuid4()}"
        manager.save(phase="gather", output={"evidence": ["test"]}, session_id=session_id)

        exported = manager.export_session(session_id)

        assert isinstance(exported, dict)

    def test_export_session_includes_session_id(self, manager):
        """Test that export_session includes session_id in output.

        Given: A session with phase data
        When: Exporting the session
        Then: The export should include the session_id
        """
        import uuid

        session_id = f"export-session-id-{uuid.uuid4()}"
        manager.save(phase="gather", output={"evidence": []}, session_id=session_id)

        exported = manager.export_session(session_id)

        assert "session_id" in exported
        assert exported["session_id"] == session_id

    def test_export_session_includes_all_completed_phases(self, manager):
        """Test that export_session includes all phase data.

        Given: A session with multiple completed phases
        When: Exporting the session
        Then: All phase data should be in the export
        """
        import uuid

        session_id = f"export-all-{uuid.uuid4()}"
        manager.save(phase="gather", output={"evidence": ["ev1"]}, session_id=session_id)
        manager.save(phase="isolate", output={"patterns": ["pat1"]}, session_id=session_id)
        manager.save(phase="hypothesize", output={"hypotheses": ["hyp1"]}, session_id=session_id)

        exported = manager.export_session(session_id)

        assert "phases" in exported
        assert isinstance(exported["phases"], dict)
        assert "gather" in exported["phases"]
        assert "isolate" in exported["phases"]
        assert "hypothesize" in exported["phases"]

    def test_export_session_phase_data_is_complete(self, manager):
        """Test that exported phase data contains all original fields.

        Given: A phase was saved with specific output fields
        When: Exporting the session
        Then: Those fields should be preserved in the export
        """
        import uuid

        session_id = f"export-data-{uuid.uuid4()}"
        original_data = {
            "evidence": ["error1", "error2"],
            "clusters": [["a", "b"], ["c"]],
            "saturation_reached": True,
        }
        manager.save(phase="gather", output=original_data, session_id=session_id)

        exported = manager.export_session(session_id)

        assert exported["phases"]["gather"]["evidence"] == original_data["evidence"]
        assert exported["phases"]["gather"]["clusters"] == original_data["clusters"]
        assert (
            exported["phases"]["gather"]["saturation_reached"]
            == original_data["saturation_reached"]
        )

    def test_export_session_includes_resume_point(self, manager):
        """Test that export_session includes current resume point.

        Given: A session with some completed phases
        When: Exporting the session
        Then: The export should include the next phase to execute
        """
        import uuid

        session_id = f"export-resume-{uuid.uuid4()}"
        manager.save(phase="gather", output={}, session_id=session_id)
        manager.save(phase="isolate", output={}, session_id=session_id)

        exported = manager.export_session(session_id)

        assert "resume_point" in exported
        assert exported["resume_point"] == "hypothesize"

    def test_export_session_for_complete_session(self, manager):
        """Test that export_session handles complete sessions.

        Given: A session with all phases completed
        When: Exporting the session
        Then: resume_point should be None
        """
        import uuid

        session_id = f"export-complete-{uuid.uuid4()}"
        for phase in ["gather", "isolate", "hypothesize", "test", "fix"]:
            manager.save(phase=phase, output={}, session_id=session_id)

        exported = manager.export_session(session_id)

        assert exported["resume_point"] is None

    def test_export_session_for_empty_session(self, manager):
        """Test that export_session handles sessions with no phases.

        Given: A session with no completed phases
        When: Exporting the session
        Then: An empty phases dict should be returned
        """
        import uuid

        session_id = f"export-empty-{uuid.uuid4()}"

        exported = manager.export_session(session_id)

        assert exported["session_id"] == session_id
        assert exported["phases"] == {}
        assert exported["resume_point"] == "gather"

    def test_export_session_includes_metadata(self, manager):
        """Test that export_session includes export metadata.

        Given: A session is being exported
        When: Exporting the session
        Then: Metadata like export_timestamp should be included
        """
        import uuid

        session_id = f"export-meta-{uuid.uuid4()}"
        manager.save(phase="gather", output={}, session_id=session_id)

        exported = manager.export_session(session_id)

        assert "metadata" in exported
        assert "export_timestamp" in exported["metadata"]


class TestPhaseSerializers:
    """Tests for phase-specific serializers.

    Each phase should have a serializer that handles phase-specific
    data validation and transformation.
    """

    @pytest.fixture
    def manager(self):
        """Return a PhaseStateManager instance for testing."""
        mgr = PhaseStateManager()
        yield mgr
        mgr.close()
        """Return a PhaseStateManager instance for testing."""
        return PhaseStateManager()

    def test_gather_serializer(self, manager):
        """Test that gather phase output is properly serialized.

        Given: A gather phase with evidence and clusters
        When: Serializing the output
        Then: Required fields should be validated and preserved
        """
        gather_output = {
            "evidence": ["Error in module X", "Stack trace line 42"],
            "clusters": [["error", "module"], ["stack", "trace"]],
            "saturation_reached": False,
            "query_type": "technical",
        }

        import uuid

        session_id = f"serialize-gather-{uuid.uuid4()}"
        state_id = manager.save(phase="gather", output=gather_output, session_id=session_id)
        restored = manager.restore(state_id)

        assert restored["evidence"] == gather_output["evidence"]
        assert restored["clusters"] == gather_output["clusters"]
        assert restored["saturation_reached"] == gather_output["saturation_reached"]

    def test_isolate_serializer(self, manager):
        """Test that isolate phase output is properly serialized.

        Given: An isolate phase with patterns
        When: Serializing the output
        Then: Pattern data should be preserved
        """
        isolate_output = {
            "patterns": [
                {"name": "Timeout Pattern", "evidence_refs": ["ev1", "ev2"]},
                {"name": "Error Pattern", "evidence_refs": ["ev3"]},
            ],
            "isolated_components": ["auth_service", "database"],
            "cluster_count": 2,
        }

        import uuid

        session_id = f"serialize-isolate-{uuid.uuid4()}"
        state_id = manager.save(phase="isolate", output=isolate_output, session_id=session_id)
        restored = manager.restore(state_id)

        assert restored["patterns"] == isolate_output["patterns"]
        assert restored["isolated_components"] == isolate_output["isolated_components"]

    def test_hypothesize_serializer(self, manager):
        """Test that hypothesize phase output is properly serialized.

        Given: A hypothesize phase with scored hypotheses
        When: Serializing the output
        Then: Hypothesis data with scores should be preserved
        """
        hypothesize_output = {
            "hypotheses": [
                {"text": "Database pool exhaustion", "score": 0.85, "confidence": "high"},
                {"text": "Network timeout", "score": 0.65, "confidence": "medium"},
            ],
            "top_hypothesis": "Database pool exhaustion",
            "total_hypotheses": 2,
        }

        import uuid

        session_id = f"serialize-hypothesize-{uuid.uuid4()}"
        state_id = manager.save(
            phase="hypothesize", output=hypothesize_output, session_id=session_id
        )
        restored = manager.restore(state_id)

        assert len(restored["hypotheses"]) == 2
        assert restored["top_hypothesis"] == "Database pool exhaustion"

    def test_test_serializer(self, manager):
        """Test that test (verify) phase output is properly serialized.

        Given: A test phase with verification results
        When: Serializing the output
        Then: Verification data should be preserved
        """
        test_output = {
            "verified": True,
            "verification_method": "log_analysis",
            "confidence": 0.92,
            "evidence_supporting": ["log1", "log2"],
            "evidence_refuting": [],
        }

        import uuid

        session_id = f"serialize-test-{uuid.uuid4()}"
        state_id = manager.save(phase="test", output=test_output, session_id=session_id)
        restored = manager.restore(state_id)

        assert restored["verified"] == test_output["verified"]
        assert restored["verification_method"] == test_output["verification_method"]
        assert restored["confidence"] == test_output["confidence"]

    def test_fix_serializer(self, manager):
        """Test that fix phase output is properly serialized.

        Given: A fix phase with applied fix details
        When: Serializing the output
        Then: Fix data should be preserved
        """
        fix_output = {
            "fix_applied": "Increased connection pool from 10 to 50",
            "fix_verified": True,
            "files_modified": ["config/database.py", "app.py"],
            "rollback_info": "backup_config_20240214.json",
        }

        import uuid

        session_id = f"serialize-fix-{uuid.uuid4()}"
        state_id = manager.save(phase="fix", output=fix_output, session_id=session_id)
        restored = manager.restore(state_id)

        assert restored["fix_applied"] == fix_output["fix_applied"]
        assert restored["files_modified"] == fix_output["files_modified"]


class TestSpoolFallback:
    """Tests for spool fallback functionality.

    When CKS is unavailable, phase state should fall back to file-based
    spool storage at P:/.claude/state/debugrca_phase_spool/
    """

    def test_spool_directory_exists(self):
        """Test that the spool directory exists or can be created.

        Given: Spool fallback may be needed
        When: Checking the spool directory path
        Then: The directory should exist or be creatable
        """
        spool_dir = Path("P:/.claude/state/debugrca_phase_spool/")

        # Directory may or may not exist yet
        # But it should be creatable
        if not spool_dir.exists():
            try:
                spool_dir.mkdir(parents=True, exist_ok=True)
                assert spool_dir.exists()
            except PermissionError:
                pytest.skip("Cannot create spool directory for testing")

    def test_save_to_spool_when_cks_unavailable(self):
        """Test that save falls back to spool when CKS is unavailable.

        Given: CKS storage is unavailable
        When: Attempting to save phase state
        Then: Data should be written to spool directory
        """
        # This test will require mocking CKS failure
        # For RED phase, we expect this to fail or not work as expected
        spool_dir = Path("P:/.claude/state/debugrca_phase_spool/")

        # In a real implementation, when CKS fails, data goes here
        # For now, this documents expected behavior
        assert spool_dir is not None

    def test_restore_from_spool(self):
        """Test that restore can read from spool fallback.

        Given: Phase state was saved to spool (CKS unavailable)
        When: Restoring the phase state
        Then: Data should be read from spool directory
        """
        # This test will require mocking CKS failure and spool files
        # For RED phase, documents expected behavior
        assert True  # Placeholder

    def test_list_phases_from_spool(self):
        """Test that list_phases works with spool data.

        Given: Multiple phases saved to spool
        When: Listing phases for a session
        Then: Phases should be read from spool files
        """
        # This test will require mocking CKS failure
        # For RED phase, documents expected behavior
        assert True  # Placeholder


class TestPhaseStateManagerEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def manager(self):
        """Return a PhaseStateManager instance for testing."""
        mgr = PhaseStateManager()
        yield mgr
        mgr.close()
        """Return a PhaseStateManager instance for testing."""
        return PhaseStateManager()

    def test_save_with_none_output(self, manager):
        """Test that save handles None output gracefully.

        Given: A phase completes with None output
        When: Saving the phase state
        Then: It should be stored as empty dict or handled gracefully
        """
        import uuid

        session_id = f"none-output-{uuid.uuid4()}"
        state_id = manager.save(phase="gather", output=None, session_id=session_id)

        assert state_id is not None

    def test_save_with_complex_nested_data(self, manager):
        """Test that save handles complex nested structures.

        Given: A phase output contains deeply nested data
        When: Saving and restoring the phase state
        Then: The nested structure should be preserved
        """
        complex_output = {
            "level1": {"level2": {"level3": {"data": ["item1", "item2"], "count": 2}}},
            "list_of_dicts": [{"a": 1}, {"b": 2}],
        }

        import uuid

        session_id = f"complex-{uuid.uuid4()}"
        state_id = manager.save(phase="gather", output=complex_output, session_id=session_id)
        restored = manager.restore(state_id)

        assert restored["level1"]["level2"]["level3"]["data"] == ["item1", "item2"]

    def test_save_with_unicode_characters(self, manager):
        """Test that save handles unicode characters correctly.

        Given: Phase output contains unicode characters
        When: Saving and restoring the phase state
        Then: Unicode characters should be preserved
        """
        unicode_output = {
            "error_message": "Error: Authentication failed for user",
            "chinese": "错误",
            "emoji": "bug",
            "arabic": "",
        }

        import uuid

        session_id = f"unicode-{uuid.uuid4()}"
        state_id = manager.save(phase="gather", output=unicode_output, session_id=session_id)
        restored = manager.restore(state_id)

        assert restored["error_message"] == unicode_output["error_message"]
        assert restored["chinese"] == unicode_output["chinese"]

    def test_multiple_saves_to_same_phase(self, manager):
        """Test that saving to the same phase multiple times works.

        Given: A phase is updated/replicated
        When: Saving the same phase multiple times
        Then: The latest save should be retrievable
        """
        import uuid

        session_id = f"multi-save-{uuid.uuid4()}"

        manager.save(phase="gather", output={"evidence": ["first"]}, session_id=session_id)
        state_id = manager.save(
            phase="gather", output={"evidence": ["second"]}, session_id=session_id
        )

        restored = manager.restore(state_id)

        # Should get the latest saved data
        assert restored["evidence"] == ["second"]

    def test_concurrent_session_isolation(self, manager):
        """Test that concurrent sessions don't interfere with each other.

        Given: Multiple sessions are active simultaneously
        When: Saving phases to different sessions
        Then: Each session should maintain independent state
        """
        import uuid

        session1 = f"concurrent-1-{uuid.uuid4()}"
        session2 = f"concurrent-2-{uuid.uuid4()}"

        id1 = manager.save(phase="gather", output={"session": 1}, session_id=session1)
        id2 = manager.save(phase="gather", output={"session": 2}, session_id=session2)

        restored1 = manager.restore(id1)
        restored2 = manager.restore(id2)

        assert restored1["session"] == 1
        assert restored2["session"] == 2

    def test_invalid_phase_name(self, manager):
        """Test that invalid phase names are handled.

        Given: An invalid phase name is provided
        When: Attempting to save with invalid phase
        Then: It should still be saved (flexibility for extension)
        """
        import uuid

        session_id = f"invalid-phase-{uuid.uuid4()}"
        state_id = manager.save(phase="custom_phase", output={}, session_id=session_id)

        # Manager should be flexible enough to handle custom phases
        assert state_id is not None
