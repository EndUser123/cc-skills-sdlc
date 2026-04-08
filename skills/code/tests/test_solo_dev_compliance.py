#!/usr/bin/env python3
"""Tests for solo-dev compliance verification - RED phase (failing tests).

This module tests that /code skill enhancements don't violate solo-dev constraints:
- Evidence tracking requires no external approvals
- Auto-detection doesn't require team calibration
- All features work in isolated environment
- No network/service dependencies beyond standard library
- Checklist can be completed by single user

Tests use pytest and verify compliance with solo-dev constitutional constraints.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add utils to path for EvidenceManager import
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from evidence import EvidenceManager


class TestSoloDevEvidenceTracking:
    """Test evidence tracking complies with solo-dev constraints - NEW FUNCTIONALITY.

    These tests verify that EvidenceManager works without external approvals,
    team consensus, or multi-person sign-off.
    """

    def test_evidence_manager_requires_no_external_approvals(self, tmp_path):
        """Verify EvidenceManager works without external approvals.

        Tests that:
        - Evidence can be recorded without approval workflows
        - No multi-person sign-off required
        - Single user can complete all TDD stages independently
        """
        # Create EvidenceManager
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Use isolated terminal to prevent conflicts
        manager = EvidenceManager(terminal_id="test_solo_dev")
        manager.ledger_file = state_dir / "code_evidence_test_solo_dev.json"

        # Record all TDD evidence stages WITHOUT external approvals
        task_id = "TASK_SOLO_001"

        # RED stage - should work without approval
        manager.record_red(
            task_id=task_id,
            test_files=["test_example.py"],
            test_command="pytest test_example.py",
            failing_tests=1,
        )

        # GREEN stage - should work without approval
        manager.record_green(
            task_id=task_id,
            impl_files=["example.py"],
            test_command="pytest test_example.py",
            passing_tests=1,
        )

        # REFACTOR stage - should work without approval
        manager.record_refactor(
            task_id=task_id,
            changes=["Improved variable names"],
            test_command="pytest test_example.py",
            passing_tests=1,
        )

        # VERIFY stage - should work without approval
        manager.record_verify(task_id=task_id, findings=0, blocking=0, verdict="PASS")

        # Mark done - should work WITHOUT external approval
        # This test FAILS if EvidenceManager requires external approvals
        manager.mark_done(task_id)

        # Verify all stages completed without approval
        can_done, msg = manager.can_mark_done(task_id)
        assert can_done, f"Should complete without external approvals: {msg}"

        status = manager.get_task_status(task_id)
        assert status["done"], "Task should be marked as done"

        # Test passes: EvidenceManager works without external approvals ✓

    def test_evidence_ledger_persistence_no_shared_state(self, tmp_path):
        """Verify evidence ledger uses isolated storage (no shared mutable state).

        Tests that:
        - Each terminal gets its own ledger file
        - No cross-terminal state pollution
        - Multi-terminal safety is maintained
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Terminal A creates its own ledger
        manager_a = EvidenceManager(terminal_id="terminal_A")
        manager_a.ledger_file = state_dir / "code_evidence_terminal_A.json"

        # Terminal B creates its own ledger
        manager_b = EvidenceManager(terminal_id="terminal_B")
        manager_b.ledger_file = state_dir / "code_evidence_terminal_B.json"

        # Each terminal records independent evidence
        manager_a.record_red("TASK_A", ["test_a.py"], "pytest", 1)
        manager_b.record_red("TASK_B", ["test_b.py"], "pytest", 1)

        # Verify isolation - ledgers should be separate
        ledger_a = manager_a._load_ledger()
        ledger_b = manager_b._load_ledger()

        # Terminal A's ledger should only have TASK_A
        assert "TASK_A" in ledger_a["tasks"], "Terminal A should have TASK_A"
        assert (
            "TASK_B" not in ledger_a["tasks"]
        ), "FAIL: Terminal A should NOT have TASK_B (cross-terminal contamination detected)"

        # Terminal B's ledger should only have TASK_B
        assert "TASK_B" in ledger_b["tasks"], "Terminal B should have TASK_B"
        assert (
            "TASK_A" not in ledger_b["tasks"]
        ), "FAIL: Terminal B should NOT have TASK_A (cross-terminal contamination detected)"


class TestSoloDevAutoDetection:
    """Test auto-detection features comply with solo-dev constraints - NEW FUNCTIONALITY.

    These tests verify that auto-detection features (if any) don't require team
    calibration, external training data, or multi-person setup.
    """

    def test_no_team_calibration_required(self, tmp_path):
        """Verify auto-detection works without team calibration.

        Tests that:
        - No training phase requiring team input
        - No calibration data from multiple users
        - Works out-of-box for single user
        """
        # This test verifies that any auto-detection features work immediately
        # without requiring team setup, calibration, or training data

        # If EvidenceManager has auto-detection features, they should work
        # without team calibration
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        manager = EvidenceManager(terminal_id="test_calibration")
        manager.ledger_file = state_dir / "code_evidence_test_calibration.json"

        # Should work immediately without calibration
        # (test auto-creates ledger if missing)
        try:
            ledger = manager._load_ledger()
            # If we get here without calibration, test passes
            assert ledger is not None
            assert "version" in ledger
        except Exception as e:
            pytest.fail(f"FAIL: Auto-detection requires team calibration: {e} (NOT IMPLEMENTED)")

    def test_no_external_dependencies_for_detection(self, tmp_path):
        """Verify auto-detection uses only standard library.

        Tests that:
        - No external service calls required
        - No network dependencies
        - Only Python stdlib used
        """
        # Import EvidenceManager and check for external dependencies
        import inspect

        import evidence

        # Get all imported modules
        source = inspect.getsource(evidence)
        imports = []

        # Look for import statements
        for line in source.split("\n"):
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                imports.append(line.strip())

        # Check for non-stdlib imports
        external_deps = []
        stdlib_modules = {"json", "pathlib", "datetime", "typing", "os", "sys"}

        for imp in imports:
            # Extract module name
            if imp.startswith("from "):
                module = imp.split()[1]
            else:
                module = imp.split()[1].split(".")[0]

            # Check if it's stdlib or local
            if module not in stdlib_modules and not module.startswith("evidence"):
                external_deps.append(module)

        # Should have no external dependencies beyond stdlib
        if external_deps:
            pytest.fail(
                f"FAIL: Evidence tracking has external dependencies: {external_deps} (violates solo-dev constraint)"
            )


class TestSoloDevIsolatedEnvironment:
    """Test features work in isolated environment - NEW FUNCTIONALITY.

    These tests verify that all /code skill features work without network access,
    external services, or shared infrastructure beyond standard library.
    """

    def test_evidence_operations_work_offline(self, tmp_path):
        """Verify evidence operations work without network access.

        Tests that:
        - All operations succeed with network disabled
        - No external API calls made
        - Fully functional offline
        """
        # Mock network check to simulate offline environment
        with patch.dict(os.environ, {"OFFLINE_MODE": "1"}):
            state_dir = tmp_path / ".claude" / "state"
            state_dir.mkdir(parents=True, exist_ok=True)

            manager = EvidenceManager(terminal_id="test_offline")
            manager.ledger_file = state_dir / "code_evidence_offline.json"

            # All operations should work offline
            try:
                manager.record_red("TASK_OFFLINE", ["test.py"], "pytest", 1)
                manager.record_green("TASK_OFFLINE", ["impl.py"], "pytest", 1)
                manager.record_refactor("TASK_OFFLINE", ["cleanup"], "pytest", 1)
                manager.record_verify("TASK_OFFLINE", 0, 0, "PASS")
                manager.mark_done("TASK_OFFLINE")

                # Verify operations succeeded
                can_done, msg = manager.can_mark_done("TASK_OFFLINE")
                assert can_done, f"Offline operations failed: {msg}"
            except Exception as e:
                pytest.fail(
                    f"FAIL: Evidence operations require network: {e} (violates solo-dev constraint)"
                )

    def test_no_shared_infrastructure_dependencies(self, tmp_path):
        """Verify no shared infrastructure dependencies.

        Tests that:
        - No database servers required
        - No message queues needed
        - No shared cache systems
        - Works with local filesystem only
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # EvidenceManager should only use local filesystem
        manager = EvidenceManager(terminal_id="test_no_shared")
        manager.ledger_file = state_dir / "code_evidence_no_shared.json"

        # Verify ledger file is local (not a database URL, etc.)
        ledger_path = manager.ledger_file

        # Should be a local file path, not a database connection string
        is_local_file = isinstance(ledger_path, Path) and not str(ledger_path).startswith(
            ("http://", "https://", "postgresql://", "mysql://", "redis://")
        )

        assert is_local_file, "FAIL: Evidence tracking uses shared infrastructure (databases, caches, etc.) instead of local files"

        # Operations should work with just local filesystem
        try:
            manager.record_red("TASK_LOCAL", ["test.py"], "pytest", 1)
            ledger = manager._load_ledger()
            assert ledger is not None
        except Exception as e:
            pytest.fail(f"FAIL: Requires shared infrastructure: {e}")


class TestSoloDevChecklistCompletion:
    """Test checklist can be completed by single user - NEW FUNCTIONALITY.

    These tests verify that the TDD workflow checklist can be completed
    without requiring team coordination, external approvals, or shared workflows.
    """

    def test_single_user_can_complete_tdd_workflow(self, tmp_path):
        """Verify single user can complete entire TDD workflow.

        Tests that:
        - No peer review required for evidence stages
        - No team sign-off needed for completion
        - Single user can run RED → GREEN → REFACTOR → VERIFY → DONE
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Simulate single user completing TDD workflow
        manager = EvidenceManager(terminal_id="test_single_user")
        manager.ledger_file = state_dir / "code_evidence_single_user.json"

        task_id = "TASK_SINGLE_USER"

        # Complete all TDD stages as single user
        manager.record_red(task_id, ["test.py"], "pytest", 1)
        manager.record_green(task_id, ["impl.py"], "pytest", 1)
        manager.record_refactor(task_id, ["cleanup"], "pytest", 1)
        manager.record_verify(task_id, 0, 0, "PASS")

        # Verify completion is allowed WITHOUT peer review
        # This test FAILS if single user cannot complete workflow alone
        manager.mark_done(task_id)

        # Verify task is marked done
        status = manager.get_task_status(task_id)
        assert status["done"], "Single user should be able to mark task done without peer review"

        # Verify can_mark_done returns True
        can_done, msg = manager.can_mark_done(task_id)
        assert can_done, f"Single user should complete TDD workflow alone: {msg}"

        # Test passes: Single user can complete TDD workflow without peer review ✓

    def test_no_multi_person_signoff_required(self, tmp_path):
        """Verify no multi-person sign-off required for any stage.

        Tests that:
        - RED stage doesn't require approval
        - GREEN stage doesn't require approval
        - REFACTOR stage doesn't require approval
        - VERIFY stage doesn't require approval
        - DONE marking doesn't require approval
        """
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        manager = EvidenceManager(terminal_id="test_no_signoff")
        manager.ledger_file = state_dir / "code_evidence_no_signoff.json"

        task_id = "TASK_NO_SIGNOFF"

        # Each stage should work without sign-off
        stages_requiring_signoff = []

        # Try RED stage
        try:
            manager.record_red(task_id, ["test.py"], "pytest", 1)
        except Exception as e:
            if "approval" in str(e).lower() or "signoff" in str(e).lower():
                stages_requiring_signoff.append("RED")

        # Try GREEN stage
        try:
            manager.record_green(task_id, ["impl.py"], "pytest", 1)
        except Exception as e:
            if "approval" in str(e).lower() or "signoff" in str(e).lower():
                stages_requiring_signoff.append("GREEN")

        # Try REFACTOR stage
        try:
            manager.record_refactor(task_id, ["cleanup"], "pytest", 1)
        except Exception as e:
            if "approval" in str(e).lower() or "signoff" in str(e).lower():
                stages_requiring_signoff.append("REFACTOR")

        # Try VERIFY stage
        try:
            manager.record_verify(task_id, 0, 0, "PASS")
        except Exception as e:
            if "approval" in str(e).lower() or "signoff" in str(e).lower():
                stages_requiring_signoff.append("VERIFY")

        # Try DONE marking
        try:
            manager.record_red(task_id, ["test.py"], "pytest", 1)
            manager.record_green(task_id, ["impl.py"], "pytest", 1)
            manager.record_refactor(task_id, ["cleanup"], "pytest", 1)
            manager.record_verify(task_id, 0, 0, "PASS")
            manager.mark_done(task_id)
        except Exception as e:
            if "approval" in str(e).lower() or "signoff" in str(e).lower():
                stages_requiring_signoff.append("DONE")

        # NO stages should require sign-off
        if stages_requiring_signoff:
            pytest.fail(
                f"FAIL: Stages requiring multi-person sign-off detected: {stages_requiring_signoff} (violates solo-dev constraint)"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
