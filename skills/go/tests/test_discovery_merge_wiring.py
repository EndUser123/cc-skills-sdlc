"""Tests for apply_discovery_evidence_merge wiring and runtime behavior.

Covers:
- apply_discovery_evidence_merge reads proposal + discovery_evidence and writes back
- Malformed discovery_evidence fails soft (returns False, proposal unchanged)
- Absent discovery_evidence preserves preflight result (returns True, no write)
- orchestrate.py imports apply_discovery_evidence_merge (wiring proof)
- Stop_enforce_gate.py has no refactor/pattern/dry-run logic (boundary check)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module under test — load from source to avoid cache-side effects.
# ---------------------------------------------------------------------------

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_plugin_dir = SCRIPTS.parent.parent

# Stub classify_complexity so preflight_propose can import.
if "classify_complexity" not in sys.modules:
    import types

    _cc = types.ModuleType("classify_complexity")
    _cc.classify_model_affinity = lambda *a, **kw: "T2"  # type: ignore[attr-defined]
    sys.modules["classify_complexity"] = _cc  # type: ignore[assignment]

_spec = importlib.util.spec_from_file_location(
    "preflight_propose", SCRIPTS / "preflight_propose.py"
)
pf = importlib.util.module_from_spec(_spec)  # type: ignore[assignment]
_spec.loader.exec_module(pf)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proposal(tmp: Path, run_id: str, *, refactor_required: bool = False) -> Path:
    proposal = {
        "rewrittenGoal": "Fix a bug in the router",
        "task_intent": "implement",
        "execution_tier": "local_surgical",
        "refactor_escalation": {
            "required": refactor_required,
            "trigger_evidence": ["dead producer consumer"] if refactor_required else [],
        },
        "pattern_candidates": [],
        "dry_run_trigger": {"triggered": False},
        "layer_placement": {"verdict": "not_applicable"},
        "mixed_work_status": "partial_readonly_done",
        "decision_advisory": {"recommendation": "Proceed"},
        "report_gate": {},
        "plain_english_report": pf.build_plain_english_report({
            "mixed_work_status": "partial_readonly_done",
            "decision_advisory": {"recommendation": "Proceed"},
            "report_gate": {},
            "task_intent": "implement",
        }),
    }
    path = tmp / f"task-proposal_{run_id}.json"
    path.write_text(json.dumps(proposal), encoding="utf-8")
    return path


def _make_discovery(tmp: Path, run_id: str, *, findings: list[dict]) -> Path:
    path = tmp / f"discovery-evidence_{run_id}.json"
    path.write_text(json.dumps({"findings": findings}), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestApplyDiscoveryEvidenceMerge:
    """Tests for apply_discovery_evidence_merge."""

    def test_verified_wrong_layer_pauses(self, tmp_path: Path):
        """Verified wrong_layer_ownership → pause_for_refactor."""
        run_id = "test-merge-001"
        _make_proposal(tmp_path, run_id)
        _make_discovery(tmp_path, run_id, findings=[{
            "provenance": "verified",
            "source": "code inspection",
            "structural_issues": ["wrong_layer_ownership"],
        }])

        result = pf.apply_discovery_evidence_merge(tmp_path, run_id)
        assert result is True

        updated = json.loads(
            (tmp_path / f"task-proposal_{run_id}.json").read_text(encoding="utf-8")
        )
        re = updated["refactor_escalation"]
        assert re["required"] is True
        assert re["recommendation"] == "pause_for_refactor"
        assert any(d["issue"] == "wrong_layer_ownership" for d in re["discovery_issues"])

    def test_assumption_only_no_hard_pause(self, tmp_path: Path):
        """Assumption-only issue → finish_then_refactor, NOT pause_for_refactor."""
        run_id = "test-merge-002"
        _make_proposal(tmp_path, run_id)
        _make_discovery(tmp_path, run_id, findings=[{
            "provenance": "assumption",
            "source": "inference",
            "structural_issues": ["duplicated_responsibility"],
        }])

        result = pf.apply_discovery_evidence_merge(tmp_path, run_id)
        assert result is True

        updated = json.loads(
            (tmp_path / f"task-proposal_{run_id}.json").read_text(encoding="utf-8")
        )
        re = updated["refactor_escalation"]
        assert re["recommendation"] == "finish_then_refactor"

    def test_absent_discovery_preserves_preflight(self, tmp_path: Path):
        """No discovery-evidence file → proposal unchanged, returns True."""
        run_id = "test-merge-003"
        _make_proposal(tmp_path, run_id)

        result = pf.apply_discovery_evidence_merge(tmp_path, run_id)
        assert result is True

        # Proposal should be unchanged (no discovery file existed).
        updated = json.loads(
            (tmp_path / f"task-proposal_{run_id}.json").read_text(encoding="utf-8")
        )
        assert updated["refactor_escalation"]["required"] is False

    def test_malformed_discovery_fails_soft(self, tmp_path: Path):
        """Malformed discovery file → returns True (non-blocking), proposal unchanged."""
        run_id = "test-merge-004"
        _make_proposal(tmp_path, run_id)
        # Write invalid JSON as discovery file.
        (tmp_path / f"discovery-evidence_{run_id}.json").write_text(
            "NOT VALID JSON{{{", encoding="utf-8"
        )

        result = pf.apply_discovery_evidence_merge(tmp_path, run_id)
        assert result is True  # soft-fail: non-blocking, preflight result preserved

        # Proposal should be unchanged.
        updated = json.loads(
            (tmp_path / f"task-proposal_{run_id}.json").read_text(encoding="utf-8")
        )
        assert updated["refactor_escalation"]["required"] is False

    def test_no_proposal_file_returns_true(self, tmp_path: Path):
        """No proposal file → soft skip, returns True."""
        result = pf.apply_discovery_evidence_merge(tmp_path, "no-such-run")
        assert result is True

    def test_worker_result_fallback(self, tmp_path: Path):
        """Discovery in claude-task-result file (fallback path) merges correctly."""
        run_id = "test-merge-005"
        _make_proposal(tmp_path, run_id)
        # Write discovery_evidence inside the worker result file.
        result_data = {
            "status": "success",
            "discovery_evidence": {
                "findings": [{
                    "provenance": "verified",
                    "source": "runtime",
                    "structural_issues": ["wrong_layer_ownership"],
                }]
            },
        }
        (tmp_path / f"claude-task-result_{run_id}.json").write_text(
            json.dumps(result_data), encoding="utf-8"
        )

        result = pf.apply_discovery_evidence_merge(tmp_path, run_id)
        assert result is True

        updated = json.loads(
            (tmp_path / f"task-proposal_{run_id}.json").read_text(encoding="utf-8")
        )
        assert updated["refactor_escalation"]["required"] is True
        assert updated["refactor_escalation"]["recommendation"] == "pause_for_refactor"


class TestOrchestrateWiring:
    """Prove orchestrate.py imports and calls apply_discovery_evidence_merge."""

    def test_import_exists(self):
        """orchestrate.py imports apply_discovery_evidence_merge."""
        orch_path = SCRIPTS / "orchestrate.py"
        content = orch_path.read_text(encoding="utf-8")
        assert "apply_discovery_evidence_merge" in content
        assert "_apply_discovery_merge" in content

    def test_call_in_claude_resume_path(self):
        """_apply_discovery_merge is called in the claude_resume path."""
        orch_path = SCRIPTS / "orchestrate.py"
        content = orch_path.read_text(encoding="utf-8")
        # Find the claude_resume block — should contain the merge call.
        idx = content.find('if getattr(args, "claude_resume", ""):')
        assert idx > 0, "claude_resume block not found"
        # The merge call should be within ~500 chars of the claude_resume block.
        chunk = content[idx:idx + 800]
        assert "_apply_discovery_merge" in chunk

    def test_call_in_pi_path(self):
        """_apply_discovery_merge is called in the pi dispatch path."""
        orch_path = SCRIPTS / "orchestrate.py"
        content = orch_path.read_text(encoding="utf-8")
        idx = content.find('if args.dispatch == "pi":')
        assert idx > 0, "pi dispatch block not found"
        chunk = content[idx:idx + 500]
        assert "_apply_discovery_merge" in chunk


class TestStopBoundary:
    """Stop_enforce_gate.py must not contain refactor/pattern/dry-run logic."""

    def test_no_forbidden_symbols(self):
        gate_path = _plugin_dir / "hooks" / "Stop_enforce_gate.py"
        if not gate_path.exists():
            pytest.skip("Stop_enforce_gate.py not found at expected path")
        content = gate_path.read_text(encoding="utf-8")
        forbidden = [
            "_KNOWN_FAILURE_SHAPES",
            "_PATTERN_DB",
            "refactor_escalation",
            "structural_issues",
            "_DRY_RUN_TRIGGERS",
        ]
        for sym in forbidden:
            assert sym not in content, f"Stop_enforce_gate.py contains {sym}"
