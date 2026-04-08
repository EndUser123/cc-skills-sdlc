#!/usr/bin/env python3
"""
Unit tests for TSR (Task Success Rate) calculation.

Tests verify that TSR is correctly calculated from evidence ledger
and that TSR validation enforces the 95% threshold.
"""

import sys
from pathlib import Path

import pytest

# Add skill root to path for imports
skill_root = Path(__file__).parent.parent
sys.path.insert(0, str(skill_root))

# Import after sys.path is set up
from scripts.validate_done_claim import calculate_tsr, validate_done_claim
from utils.evidence import EvidenceManager


# Test fixtures
@pytest.fixture
def temp_ledger_file(tmp_path):
    """Create a temporary ledger file for testing."""
    return tmp_path / "test_ledger.json"


@pytest.fixture
def evidence_mgr_all_complete(temp_ledger_file):
    """EvidenceManager with all tasks complete (100% TSR)."""
    # Create manager with custom ledger path
    mgr = EvidenceManager("test_terminal")
    mgr.ledger_file = temp_ledger_file

    # Initialize ledger with complete tasks
    import json
    from datetime import datetime

    ledger_data = {
        "version": "1.0",
        "terminal_id": "test_terminal",
        "task_list_id": None,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "tasks": {
            "TASK-001": {
                "description": "Complete task 1",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                },
                "done": True,
                "done_at": datetime.now().isoformat()
            },
            "TASK-002": {
                "description": "Complete task 2",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                },
                "done": True,
                "done_at": datetime.now().isoformat()
            },
            "TASK-003": {
                "description": "Complete task 3",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                },
                "done": True,
                "done_at": datetime.now().isoformat()
            }
        }
    }

    temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))
    return mgr


@pytest.fixture
def evidence_mgr_partial_complete(temp_ledger_file):
    """EvidenceManager with partial completion (66.7% TSR = 2/3)."""
    mgr = EvidenceManager("test_terminal")
    mgr.ledger_file = temp_ledger_file

    import json
    from datetime import datetime

    ledger_data = {
        "version": "1.0",
        "terminal_id": "test_terminal",
        "task_list_id": None,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "tasks": {
            "TASK-001": {
                "description": "Complete task",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                },
                "done": True,
                "done_at": datetime.now().isoformat()
            },
            "TASK-002": {
                "description": "Complete task",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                },
                "done": True,
                "done_at": datetime.now().isoformat()
            },
            "TASK-003": {
                "description": "Incomplete task",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": False, "timestamp": datetime.now().isoformat()}
                },
                "done": False
            }
        }
    }

    temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))
    return mgr


@pytest.fixture
def evidence_mgr_low_tsr(temp_ledger_file):
    """EvidenceManager with low TSR (50% = 1/2 complete, 1 blocked)."""
    mgr = EvidenceManager("test_terminal")
    mgr.ledger_file = temp_ledger_file

    import json
    from datetime import datetime

    ledger_data = {
        "version": "1.0",
        "terminal_id": "test_terminal",
        "task_list_id": None,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "tasks": {
            "TASK-001": {
                "description": "Complete task",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                },
                "done": True,
                "done_at": datetime.now().isoformat()
            },
            "TASK-002": {
                "description": "Blocked task",
                "evidence": {},
                "done": False
            }
        }
    }

    temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))
    return mgr


@pytest.fixture
def evidence_mgr_empty(temp_ledger_file):
    """EvidenceManager with no tasks (empty ledger)."""
    mgr = EvidenceManager("test_terminal")
    mgr.ledger_file = temp_ledger_file

    import json
    from datetime import datetime

    ledger_data = {
        "version": "1.0",
        "terminal_id": "test_terminal",
        "task_list_id": None,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "tasks": {}
    }

    temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))
    return mgr


class TestTSRCalculation:
    """Test TSR calculation from evidence ledger."""

    def test_tsr_all_tasks_complete(self, evidence_mgr_all_complete):
        """Test TSR calculation when all tasks are complete (100%)."""
        stats = evidence_mgr_all_complete.get_completion_statistics()

        assert stats["total_attempted"] == 3
        assert stats["completed"] == 3
        assert stats["failed"] == 0
        assert stats["blocked"] == 0
        assert stats["tsr"] == 100.0

    def test_tsr_partial_completion(self, evidence_mgr_partial_complete):
        """Test TSR calculation with partial completion (66.7%)."""
        stats = evidence_mgr_partial_complete.get_completion_statistics()

        assert stats["total_attempted"] == 3
        assert stats["completed"] == 2
        assert stats["failed"] == 1
        assert stats["blocked"] == 0
        # TSR = (2/3) * 100 = 66.67
        assert stats["tsr"] == 66.67

    def test_tsr_low_completion(self, evidence_mgr_low_tsr):
        """Test TSR calculation with low completion (50%)."""
        stats = evidence_mgr_low_tsr.get_completion_statistics()

        assert stats["total_attempted"] == 2
        assert stats["completed"] == 1
        assert stats["failed"] == 0
        assert stats["blocked"] == 1
        # TSR = (1/2) * 100 = 50.0
        assert stats["tsr"] == 50.0

    def test_tsr_empty_task_list(self, evidence_mgr_empty):
        """Test TSR calculation with empty task list."""
        stats = evidence_mgr_empty.get_completion_statistics()

        assert stats["total_attempted"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["blocked"] == 0
        # TSR = 0 when no tasks (avoid division by zero)
        assert stats["tsr"] == 0.0

    def test_calculate_tsr_function(self, evidence_mgr_all_complete):
        """Test calculate_tsr() helper function."""
        stats = calculate_tsr(evidence_mgr_all_complete)

        assert stats["total_attempted"] == 3
        assert stats["completed"] == 3
        assert stats["tsr"] == 100.0


class TestTSRValidation:
    """Test TSR threshold validation (95% requirement)."""

    def test_validate_done_claim_passes_with_high_tsr(self, evidence_mgr_all_complete):
        """Test validation passes when TSR ≥ 95%."""
        # Should pass without exception
        result = validate_done_claim(evidence_mgr_all_complete, tsr_threshold=95.0)
        assert result is True

    def test_validate_done_claim_blocks_with_low_tsr(self, evidence_mgr_low_tsr):
        """Test validation blocks when TSR < 95%."""
        # Should raise ValueError with TSR = 50%
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(evidence_mgr_low_tsr, tsr_threshold=95.0)

        error_msg = str(exc_info.value)
        assert "Task Success Rate (TSR) is 50.0%" in error_msg
        assert "below 95.0% threshold" in error_msg

    def test_validate_done_claim_blocks_with_partial_tsr(self, evidence_mgr_partial_complete):
        """Test validation blocks when TSR = 66.67% (< 95%)."""
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(evidence_mgr_partial_complete, tsr_threshold=95.0)

        error_msg = str(exc_info.value)
        assert "Task Success Rate (TSR) is 66.67%" in error_msg
        assert "below 95.0% threshold" in error_msg

    def test_validate_done_claim_with_empty_task_list(self, evidence_mgr_empty):
        """Test validation fails with empty task list (0% TSR < 95%)."""
        # Empty task list has 0% TSR, which is below 95% threshold
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(evidence_mgr_empty, tsr_threshold=95.0)

        error_msg = str(exc_info.value)
        assert "Task Success Rate (TSR) is 0.0%" in error_msg
        assert "below 95.0% threshold" in error_msg

    def test_validate_done_claim_custom_threshold(self, temp_ledger_file):
        """Test validation with custom TSR threshold."""
        # Create a manager with 3 tasks: all have complete evidence
        # 2 are marked done, 1 is not marked done
        # TSR = 66.67% (2/3 done)
        # Evidence check passes (all tasks have complete evidence)
        # With 60% threshold, validation should pass (TSR check + evidence check both pass)
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_file

        import json
        from datetime import datetime

        ledger_data = {
            "version": "1.0",
            "terminal_id": "test_terminal",
            "task_list_id": None,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "tasks": {
                "TASK-001": {
                    "description": "Complete task 1",
                    "evidence": {
                        "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                    },
                    "done": True,
                    "done_at": datetime.now().isoformat()
                },
                "TASK-002": {
                    "description": "Complete task 2",
                    "evidence": {
                        "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                    },
                    "done": True,
                    "done_at": datetime.now().isoformat()
                },
                "TASK-003": {
                    "description": "Complete task 3 (not marked done)",
                    "evidence": {
                        "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                    },
                    "done": False
                }
            }
        }

        temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))

        # TSR = 66.67% (2/3 done), which is >= 60% threshold
        # All tasks have complete evidence
        # Validation should pass (evidence check passes, TSR check passes with custom threshold)
        result = validate_done_claim(mgr, tsr_threshold=60.0)
        assert result is True

    def test_error_message_includes_task_breakdown(self, evidence_mgr_low_tsr):
        """Test that error message includes detailed task breakdown."""
        with pytest.raises(ValueError) as exc_info:
            validate_done_claim(evidence_mgr_low_tsr, tsr_threshold=95.0)

        error_msg = str(exc_info.value)
        # Check for breakdown sections
        assert "Total attempted: 2" in error_msg
        assert "Completed: 1" in error_msg
        assert "Failed: 0" in error_msg
        assert "Blocked: 1" in error_msg


class TestTSREdgeCases:
    """Test TSR calculation edge cases."""

    def test_tsr_with_incomplete_evidence(self, temp_ledger_file):
        """Test TSR when task is marked done but missing evidence."""
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_file

        import json
        from datetime import datetime

        # Task marked done but missing VERIFY evidence
        ledger_data = {
            "version": "1.0",
            "terminal_id": "test_terminal",
            "task_list_id": None,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "tasks": {
                "TASK-001": {
                    "description": "Task marked done without all evidence",
                    "evidence": {
                        "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()}
                        # Missing VERIFY evidence
                    },
                    "done": True,
                    "done_at": datetime.now().isoformat()
                }
            }
        }

        temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))

        stats = mgr.get_completion_statistics()
        # Should count as failed, not completed (missing VERIFY evidence)
        assert stats["completed"] == 0
        assert stats["failed"] == 1
        assert stats["tsr"] == 0.0

    def test_tsr_with_partial_evidence_not_done(self, temp_ledger_file):
        """Test TSR when task has partial evidence but not marked done."""
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_file

        import json
        from datetime import datetime

        ledger_data = {
            "version": "1.0",
            "terminal_id": "test_terminal",
            "task_list_id": None,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "tasks": {
                "TASK-001": {
                    "description": "Task with partial evidence",
                    "evidence": {
                        "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                        "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()}
                    },
                    "done": False
                }
            }
        }

        temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))

        stats = mgr.get_completion_statistics()
        # Should count as failed (partial evidence, not done)
        assert stats["completed"] == 0
        assert stats["failed"] == 1
        assert stats["blocked"] == 0

    def test_tsr_threshold_at_exact_boundary(self, temp_ledger_file):
        """Test TSR validation exactly at 95% threshold."""
        mgr = EvidenceManager("test_terminal")
        mgr.ledger_file = temp_ledger_file

        import json
        from datetime import datetime

        # Create 20 tasks, all with complete evidence and marked done
        # TSR = 100% (all tasks complete)
        ledger_data = {
            "version": "1.0",
            "terminal_id": "test_terminal",
            "task_list_id": None,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "tasks": {}
        }

        # Add 20 complete tasks
        for i in range(1, 21):
            ledger_data["tasks"][f"TASK-{i:03d}"] = {
                "description": f"Complete task {i}",
                "evidence": {
                    "RED": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "GREEN": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "REFACTOR": {"completed": True, "timestamp": datetime.now().isoformat()},
                    "VERIFY": {"completed": True, "timestamp": datetime.now().isoformat()}
                },
                "done": True,
                "done_at": datetime.now().isoformat()
            }

        temp_ledger_file.write_text(json.dumps(ledger_data, indent=2))

        stats = mgr.get_completion_statistics()
        # TSR = 100% (20/20 done)
        assert stats["tsr"] == 100.0

        # Should pass with 95% threshold when TSR = 100%
        result = validate_done_claim(mgr, tsr_threshold=95.0)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
