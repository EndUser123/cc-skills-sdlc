#!/usr/bin/env python3
"""Quick verification test for TASK-021 EvidenceManager integration."""

import os
import sys
import tempfile
from pathlib import Path

# Add tdd skill to path
tdd_skill_path = Path(__file__).parent.parent / "tdd" / "lib"
sys.path.insert(0, str(tdd_skill_path))

# Add code utils to path
code_utils_path = Path(__file__).parent.parent / "code" / "utils"
sys.path.insert(0, str(code_utils_path))

# Import after path setup
from evidence import EvidenceManager
from evidence_writer import generate_evidence_artifact


def test_evidence_manager_integration():
    """Verify EvidenceManager.record_tdd_evidence() is called correctly."""

    print("Testing EvidenceManager integration...")

    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Enable evidence tracking
        os.environ["TDD_EVIDENCE_TRACKING_ENABLED"] = "true"

        # Create EvidenceManager directly
        terminal_id = "test_terminal"
        manager = EvidenceManager(terminal_id)

        # Test record_tdd_evidence() method
        task_id = "TEST-001"
        phase = "RED"
        evidence = {"test_files": ["test_feature.py"], "failing_tests": 1}

        print(f"Recording evidence for {task_id} {phase}...")
        manager.record_tdd_evidence(task_id, phase, evidence)

        # Verify ledger file exists
        ledger_file = manager.ledger_file
        assert ledger_file.exists(), f"Ledger file not created: {ledger_file}"

        # Load and verify ledger content
        import json

        ledger_data = json.loads(ledger_file.read_text())

        assert task_id in ledger_data["tasks"], f"Task {task_id} not in ledger"
        assert phase in ledger_data["tasks"][task_id]["evidence"], f"Phase {phase} not in evidence"
        assert ledger_data["tasks"][task_id]["evidence"][phase][
            "completed"
        ], "Evidence not marked complete"
        assert (
            ledger_data["tasks"][task_id]["evidence"][phase]["failing_tests"] == 1
        ), "Evidence data incorrect"

        print("✓ EvidenceManager.record_tdd_evidence() works correctly")
        print(f"✓ Ledger file created at: {ledger_file}")

        # Test generate_evidence_artifact() integration
        print("\nTesting generate_evidence_artifact() integration...")

        red_evidence = generate_evidence_artifact(
            task_id="TEST-002",
            phase="RED",
            evidence={"test_files": ["test.py"], "failing_tests": 1},
            skill_dir=temp_path,
            terminal_id="integration_test",
        )

        assert red_evidence is not None, "generate_evidence_artifact() returned None"
        assert red_evidence.exists(), f"Evidence file not created: {red_evidence}"

        print(f"✓ generate_evidence_artifact() created: {red_evidence}")

        # Verify fallback mode (no terminal_id)
        print("\nTesting markdown fallback mode...")

        green_evidence = generate_evidence_artifact(
            task_id="TEST-003",
            phase="GREEN",
            evidence={"implementation": "Feature implemented"},
            skill_dir=temp_path,
            terminal_id=None,  # Should trigger fallback
        )

        assert green_evidence is not None, "Fallback mode returned None"
        assert green_evidence.exists(), f"Fallback markdown not created: {green_evidence}"
        assert green_evidence.suffix == ".md", "Fallback should create markdown file"

        print(f"✓ Fallback mode works correctly: {green_evidence}")

    print("\n✅ All TASK-021 integration tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_evidence_manager_integration()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
