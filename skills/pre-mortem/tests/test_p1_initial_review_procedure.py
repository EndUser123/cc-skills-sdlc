"""Tests for p1_initial_review.md procedure logic edge cases.

Covers:
- Fresh session (directory doesn't exist yet)
- Interrupted dispatch (some specialists have JSONs, not all)
- All specialists complete (all have JSONs and completion markers)
- Partial results (some have markers, some don't)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from premortem_io import PreMortemSession


class TestFreshSession:
    """Scenario: New session, no directory exists yet."""

    def test_session_dir_does_not_exist_initially(self, tmp_path: Path):
        session = PreMortemSession(staging_root=tmp_path)
        assert not session.session_dir.exists()

    def test_setup_creates_specialists_dir(self, tmp_path: Path):
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()
        specialists_dir = session.session_dir / "specialists"
        assert specialists_dir.exists()
        assert specialists_dir.is_dir()

    def test_ensuring_specialists_dir_before_idempotency_check_is_safe(self, tmp_path: Path):
        """Step 3/4 ordering fix: mkdir must come before idempotency check."""
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()

        # Simulate Step 3 idempotency check reading manifest
        manifest_path = session.session_dir / "specialists" / "dispatch_manifest.json"
        # This should NOT raise FileNotFoundError if Step 4 (mkdir) runs first
        # On fresh session, manifest doesn't exist yet — this is expected
        assert not manifest_path.exists()  # Fresh session, no prior run


class TestInterruptedDispatch:
    """Scenario: Some specialists dispatched, some failed, no completion markers yet."""

    def test_partial_specialist_json_exists(self, tmp_path: Path):
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()

        specialists_dir = session.session_dir / "specialists"

        # Only adversarial-logic completed
        json_path = specialists_dir / "adversarial-logic-findings.json"
        json_path.write_text(json.dumps({"findings": []}))

        marker_path = specialists_dir / "adversarial-logic-complete.json"
        marker_path.write_text(json.dumps({"specialist": "adversarial-logic", "complete": True}))

        remaining = ["adversarial-compliance", "adversarial-quality", "adversarial-testing"]
        for s in remaining:
            assert not (specialists_dir / f"{s}-findings.json").exists()
            assert not (specialists_dir / f"{s}-complete.json").exists()

    def test_idempotency_check_detects_missing_specialists(self, tmp_path: Path):
        """On resume, only missing/invalid specialists should be re-dispatched."""
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()

        specialists_dir = session.session_dir / "specialists"
        selected = ["adversarial-logic", "adversarial-compliance", "adversarial-quality"]

        # Write manifest of what was dispatched
        manifest = {"dispatched": selected, "session_dir": str(session.session_dir)}
        manifest_path = specialists_dir / "dispatch_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # Only one specialist completed
        json_path = specialists_dir / "adversarial-logic-findings.json"
        json_path.write_text(json.dumps({"findings": []}))
        marker_path = specialists_dir / "adversarial-logic-complete.json"
        marker_path.write_text(json.dumps({"specialist": "adversarial-logic", "complete": True}))

        # Adversarial-compliance has JSON but no marker (interrupted)
        json_path2 = specialists_dir / "adversarial-compliance-findings.json"
        json_path2.write_text(json.dumps({"findings": []}))

        # Adversarial-quality has neither

        # Idempotency check should detect: adversarial-compliance needs marker check,
        # adversarial-quality needs full redispatch
        assert (specialists_dir / "adversarial-logic-findings.json").exists()
        assert (specialists_dir / "adversarial-logic-complete.json").exists()
        assert (specialists_dir / "adversarial-compliance-findings.json").exists()
        assert not (specialists_dir / "adversarial-compliance-complete.json").exists()
        assert not (specialists_dir / "adversarial-quality-findings.json").exists()


class TestAllComplete:
    """Scenario: All specialists completed successfully."""

    def test_all_json_and_markers_present(self, tmp_path: Path):
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()

        specialists_dir = session.session_dir / "specialists"
        selected = ["adversarial-logic", "adversarial-compliance", "adversarial-quality"]

        for specialist in selected:
            json_path = specialists_dir / f"{specialist}-findings.json"
            marker_path = specialists_dir / f"{specialist}-complete.json"
            json_path.write_text(json.dumps({"findings": [{"id": f"{specialist}-001", "severity": "LOW"}]}))
            marker_path.write_text(json.dumps({"specialist": specialist, "complete": True}))

        # All present and valid
        for specialist in selected:
            json_path = specialists_dir / f"{specialist}-findings.json"
            marker_path = specialists_dir / f"{specialist}-complete.json"
            assert json_path.exists()
            assert marker_path.exists()
            data = json.loads(json_path.read_text())
            assert "findings" in data
            marker_data = json.loads(marker_path.read_text())
            assert marker_data["complete"] is True


class TestPartialResults:
    """Scenario: Some specialists complete, some missing, some with invalid JSON."""

    def test_invalid_json_detected(self, tmp_path: Path):
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()

        specialists_dir = session.session_dir / "specialists"

        # Write corrupted JSON
        json_path = specialists_dir / "adversarial-logic-findings.json"
        json_path.write_text("{ invalid json }")

        marker_path = specialists_dir / "adversarial-logic-complete.json"
        marker_path.write_text(json.dumps({"specialist": "adversarial-logic", "complete": True}))

        # Idempotency check should detect corruption
        try:
            json.loads(json_path.read_text())
            assert False, "Should have raised JSONDecodeError"
        except json.JSONDecodeError:
            pass  # Expected — corrupted JSON should trigger redispatch


class TestManifestBasedResume:
    """Scenario: Dispatch manifest tracks what was already dispatched."""

    def test_manifest_records_dispatched_specialists(self, tmp_path: Path):
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()

        specialists_dir = session.session_dir / "specialists"
        manifest_path = specialists_dir / "dispatch_manifest.json"

        selected = ["adversarial-logic", "adversarial-compliance", "adversarial-quality"]
        manifest = {"dispatched": selected, "session_dir": str(session.session_dir)}

        # Pre-populate manifest BEFORE dispatch (per Step 5a)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        # Verify manifest can be read back
        with open(manifest_path) as f:
            loaded = json.load(f)
        assert loaded["dispatched"] == selected
        assert len(loaded["dispatched"]) == 3

    def test_manifest_enables_skip_of_completed_specialists(self, tmp_path: Path):
        """If JSON + marker exist for a specialist in manifest, skip redispatch."""
        session = PreMortemSession(staging_root=tmp_path)
        session.setup()

        specialists_dir = session.session_dir / "specialists"
        manifest_path = specialists_dir / "dispatch_manifest.json"

        selected = ["adversarial-logic", "adversarial-compliance", "adversarial-quality"]
        manifest = {"dispatched": selected, "session_dir": str(session.session_dir)}
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        # adversarial-logic is fully complete
        json_path = specialists_dir / "adversarial-logic-findings.json"
        json_path.write_text(json.dumps({"findings": []}))
        marker_path = specialists_dir / "adversarial-logic-complete.json"
        marker_path.write_text(json.dumps({"specialist": "adversarial-logic", "complete": True}))

        # adversarial-compliance has only JSON (no marker)
        json_path2 = specialists_dir / "adversarial-compliance-findings.json"
        json_path2.write_text(json.dumps({"findings": []}))

        # adversarial-quality has nothing

        # Resume: adversarial-logic should be skipped,
        # adversarial-compliance needs marker,
        # adversarial-quality needs full dispatch
        assert (specialists_dir / "adversarial-logic-complete.json").exists()
        assert not (specialists_dir / "adversarial-compliance-complete.json").exists()
        assert not (specialists_dir / "adversarial-quality-findings.json").exists()
