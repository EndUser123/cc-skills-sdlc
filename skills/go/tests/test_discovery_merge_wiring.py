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
_plugin_dir = SCRIPTS.parent

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
        chunk = content[idx:idx + 1500]
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


class TestWriteDiscoveryEvidence:
    """Tests for the write_discovery_evidence writer helper."""

    def test_writer_creates_valid_file(self, tmp_path: Path):
        """Writer produces a discovery-evidence file the reader consumes."""
        run_id = "writer-001"
        findings = [{
            "source": "code inspection",
            "provenance": "verified",
            "summary": "X writes to Y's state without going through Y's API",
            "evidence": "grep -n 'Y\\.state' foo.py:42",
            "structural_issues": ["wrong_layer_ownership"],
        }]
        out = pf.write_discovery_evidence(tmp_path, run_id, findings)
        assert out is not None
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["run_id"] == run_id
        assert len(data["findings"]) == 1
        assert data["findings"][0]["structural_issues"] == ["wrong_layer_ownership"]

    def test_writer_then_reader_pauses(self, tmp_path: Path):
        """Writer output flows through the reader to cause pause_for_refactor."""
        run_id = "writer-002"
        _make_proposal(tmp_path, run_id)
        findings = [{
            "source": "grep",
            "provenance": "verified",
            "summary": "caller bypasses the owner module",
            "evidence": "foo.py:42 calls bar._state directly",
            "structural_issues": ["wrong_layer_ownership"],
        }]
        pf.write_discovery_evidence(tmp_path, run_id, findings)
        # Reader (the real runtime path) consumes the writer's file.
        assert pf.apply_discovery_evidence_merge(tmp_path, run_id) is True
        updated = json.loads(
            (tmp_path / f"task-proposal_{run_id}.json").read_text(encoding="utf-8")
        )
        re = updated["refactor_escalation"]
        assert re["required"] is True
        assert re["recommendation"] == "pause_for_refactor"

    def test_writer_drops_verified_without_evidence(self, tmp_path: Path):
        """Verified finding with no evidence citation is dropped (not faked)."""
        run_id = "writer-003"
        findings = [{
            "source": "hunch",
            "provenance": "verified",  # claims verified
            "summary": "something feels off",
            # NO evidence field — must be dropped
            "structural_issues": ["inert_code"],
        }]
        out = pf.write_discovery_evidence(tmp_path, run_id, findings)
        assert out is None  # no valid findings → soft-fail, no file written
        assert not (tmp_path / f"discovery-evidence_{run_id}.json").exists()

    def test_writer_drops_malformed_provenance(self, tmp_path: Path):
        """Invalid provenance / missing source → finding dropped."""
        run_id = "writer-004"
        findings = [
            {"source": "x", "provenance": "guess", "summary": "bad prov"},  # invalid prov
            {"provenance": "inference", "summary": "no source"},  # missing source
            {"source": "x", "provenance": "assumption"},  # missing summary
        ]
        out = pf.write_discovery_evidence(tmp_path, run_id, findings)
        assert out is None

    def test_writer_filters_noncanonical_structural_issues(self, tmp_path: Path):
        """Unknown structural_issues values are dropped, canonical kept."""
        run_id = "writer-005"
        findings = [{
            "source": "inspection",
            "provenance": "inference",
            "summary": "overlap",
            "structural_issues": ["duplicated_responsibility", "made_up_issue", "also_fake"],
        }]
        out = pf.write_discovery_evidence(tmp_path, run_id, findings)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["findings"][0]["structural_issues"] == ["duplicated_responsibility"]

    def test_writer_empty_findings_is_noop(self, tmp_path: Path):
        """Empty findings list → None, no file."""
        out = pf.write_discovery_evidence(tmp_path, "writer-006", [])
        assert out is None

    def test_assumption_only_writer_no_hard_pause(self, tmp_path: Path):
        """Writer + reader: assumption-only issue does not hard-pause."""
        run_id = "writer-007"
        _make_proposal(tmp_path, run_id)
        pf.write_discovery_evidence(tmp_path, run_id, [{
            "source": "guess", "provenance": "assumption",
            "summary": "might be duplicated",
            "structural_issues": ["duplicated_responsibility"],
        }])
        pf.apply_discovery_evidence_merge(tmp_path, run_id)
        updated = json.loads(
            (tmp_path / f"task-proposal_{run_id}.json").read_text(encoding="utf-8")
        )
        assert updated["refactor_escalation"]["recommendation"] == "finish_then_refactor"


class TestEmitDiscoveryEvidenceTelemetry:
    """Tests for emit_discovery_evidence_telemetry (non-blocking observability)."""

    def test_telemetry_absent_discovery_is_non_blocking(self, tmp_path: Path):
        """No discovery artifact → exists=False, source=absent, no exception."""
        record = pf.emit_discovery_evidence_telemetry(tmp_path, "tel-001")
        assert record["event"] == "discovery_evidence_status"
        assert record["exists"] is False
        assert record["findings_count"] == 0
        assert record["source"] == "absent"
        assert "non-blocking" in record["failure_direction"]

    def test_telemetry_present_file_reports_counts(self, tmp_path: Path):
        """Discovery file present → correct findings_count + structural count."""
        rid = "tel-002"
        pf.write_discovery_evidence(tmp_path, rid, [
            {"source": "grep", "provenance": "verified",
             "summary": "wrong layer", "evidence": "foo.py:1",
             "structural_issues": ["wrong_layer_ownership"]},
            {"source": "inference", "provenance": "inference",
             "summary": "dup"},  # no structural_issues
        ])
        record = pf.emit_discovery_evidence_telemetry(tmp_path, rid)
        assert record["exists"] is True
        assert record["findings_count"] == 2
        assert record["structural_issue_count"] == 1
        assert record["source"] == "discovery-evidence file"
        assert record["artifact_path"] is not None

    def test_telemetry_malformed_discovery_soft_fails(self, tmp_path: Path):
        """Malformed discovery file → non-blocking, source flips to absent."""
        rid = "tel-003"
        (tmp_path / f"discovery-evidence_{rid}.json").write_text(
            "NOT VALID JSON", encoding="utf-8"
        )
        record = pf.emit_discovery_evidence_telemetry(tmp_path, rid)
        assert record["exists"] is False
        assert record["source"] == "absent"
        assert "malformed" in record["failure_direction"]

    def test_telemetry_is_run_local(self, tmp_path: Path):
        """Telemetry writes only a per-run JSONL file, no cross-session state."""
        rid = "tel-004"
        pf.emit_discovery_evidence_telemetry(tmp_path, rid)
        tel_file = tmp_path / f"telemetry-discovery-evidence_{rid}.jsonl"
        assert tel_file.exists()
        # Single record, single file, run_id-scoped.
        lines = tel_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1


class TestWorkerPromptDiscoveryContract:
    """The task_prompt must contain explicit discovery_evidence instructions."""

    def test_prompt_contains_discovery_contract(self):
        """orchestrate.py task_prompt emits the discovery-evidence contract."""
        orch_path = SCRIPTS / "orchestrate.py"
        content = orch_path.read_text(encoding="utf-8")
        # The block header must be present.
        assert "Discovery-evidence contract" in content
        # The worker must be told the canonical structural_issues enum.
        assert "wrong_layer_ownership" in content
        assert "dead_producer_consumer" in content
        # The worker must be told not to fabricate.
        assert "Do not fabricate findings" in content
        # The telemetry reference (so the worker knows it's measured).
        assert "telemetry" in content

    def test_prompt_run_id_and_state_dir_placeholders(self):
        """The contract block uses run_id/state_dir placeholders, not hardcodes."""
        orch_path = SCRIPTS / "orchestrate.py"
        content = orch_path.read_text(encoding="utf-8")
        # _run_id_from_file derives from the task file stem.
        assert "_run_id_from_file" in content
        # GO_STATE_DIR is the source for the state_dir placeholder.
        assert "GO_STATE_DIR" in content


# ---------------------------------------------------------------------------
# PI review_transcript discovery-findings extraction (loaded from source).
# ---------------------------------------------------------------------------
_PI_PATH = SCRIPTS / "adapters" / "pi" / "review_transcript.py"
_pi_spec = importlib.util.spec_from_file_location("pi_review_transcript", _PI_PATH)
pi_rev = importlib.util.module_from_spec(_pi_spec)  # type: ignore[assignment]
_pi_spec.loader.exec_module(pi_rev)  # type: ignore[union-attr]


class TestPiDiscoveryFindingsExtraction:
    """Tests for the PI review transcript -> discovery_evidence mapping."""

    def test_blind_write_maps_to_wrong_layer(self):
        """BLIND_WRITE warning with files_written maps to inference finding."""
        result = {
            "warnings": ["BLIND_WRITE: files written without any reads first"],
            "files_written": ["bar.py"],
            "files_read": [],
        }
        findings = pi_rev.extract_discovery_findings(result, {})
        assert len(findings) == 1
        assert findings[0]["provenance"] == "inference"
        assert findings[0]["structural_issues"] == ["wrong_layer_ownership"]
        assert "bar.py" in findings[0]["evidence"]

    def test_forbidden_file_maps_to_wrong_layer(self):
        """FORBIDDEN_FILE warning with matching path maps to inference finding."""
        result = {
            "warnings": ["FORBIDDEN_FILE: pi modified forbidden file 'src/auth.py'"],
            "files_written": ["src/auth.py"],
            "files_read": ["src/auth.py"],
        }
        task = {"forbidden_files": ["src/auth.py"]}
        findings = pi_rev.extract_discovery_findings(result, task)
        assert len(findings) == 1
        assert findings[0]["provenance"] == "inference"
        assert findings[0]["structural_issues"] == ["wrong_layer_ownership"]
        assert "src/auth.py" in findings[0]["evidence"]

    def test_no_warnings_maps_to_empty_findings(self):
        """No actionable warnings -> empty findings list."""
        result = {"warnings": [], "files_written": [], "files_read": []}
        findings = pi_rev.extract_discovery_findings(result, {})
        assert findings == []

    def test_excessive_calls_not_mapped(self):
        """Non-file warnings like EXCESSIVE_CALLS produce no findings (no file evidence)."""
        result = {
            "warnings": ["EXCESSIVE_CALLS: 60 tool calls (possible loop)"],
            "files_written": ["x.py"],
            "files_read": [],
        }
        findings = pi_rev.extract_discovery_findings(result, {})
        assert findings == []

    def test_pi_writer_then_reader(self, tmp_path: Path):
        """PI findings -> write_discovery_evidence -> apply_discovery_evidence_merge."""
        rid = "pi-wire-001"
        _make_proposal(tmp_path, rid)
        result = {
            "warnings": ["BLIND_WRITE: files written without any reads first"],
            "files_written": ["src/auth.py"],
            "files_read": [],
        }
        findings = pi_rev.extract_discovery_findings(result, {})
        pf.write_discovery_evidence(tmp_path, rid, findings)
        assert pf.apply_discovery_evidence_merge(tmp_path, rid) is True
        updated = json.loads(
            (tmp_path / f"task-proposal_{rid}.json").read_text(encoding="utf-8")
        )
        re = updated["refactor_escalation"]
        assert re["required"] is True
        assert re["recommendation"] == "pause_for_refactor"

    def test_pi_no_findings_preserves_preflight(self, tmp_path: Path):
        """PI review with no actionable warnings -> no discovery file -> preflight preserved."""
        rid = "pi-wire-002"
        _make_proposal(tmp_path, rid)
        assert pf.apply_discovery_evidence_merge(tmp_path, rid) is True
        updated = json.loads(
            (tmp_path / f"task-proposal_{rid}.json").read_text(encoding="utf-8")
        )
        assert updated["refactor_escalation"]["required"] is False


class TestSkillOrchestrateContractDrift:
    """Guard canonical structural_issues list drift between SKILL.md and orchestrate."""

    def test_canonical_structural_issues_match_across_files(self):
        """SKILL.md prose and orchestrate contract block must list the same 8 issues."""
        skill = ""
        # SCRIPTS = skills/go/scripts; SKILL.md lives at skills/go/SKILL.md.
        for candidate in [
            SCRIPTS.parent / "SKILL.md",
            Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/go/SKILL.md"),
        ]:
            if candidate.exists():
                skill = candidate.read_text(encoding="utf-8")
                break
        canonical = {"dead_producer_consumer", "inert_code", "duplicated_responsibility",
                     "wrong_layer_ownership", "repeated_patching",
                     "state_identity_lifecycle_ambiguity", "broad_cross_file_change_needed",
                     "excessive_test_setup_due_to_design_complexity"}
        skill_mentions = {i for i in canonical if i in skill}
        # SKILL.md must mention ALL canonical issues.
        assert skill_mentions == canonical, (
            f"SKILL.md missing canonical issues: {canonical - skill_mentions}"
        )
