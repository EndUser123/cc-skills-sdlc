"""Tests for the Final Omission Audit (STEP 9.6) + report-gate wiring.

Real subprocess git against tmp_path worktrees — no Mock for the git boundary,
mirroring test_completion_evidence_review.py. state_dir is kept SEPARATE from
the code worktree (as the real orchestrator does), so state artifacts never
appear in the worktree's git status.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Load omission_audit
_oa_spec = importlib.util.spec_from_file_location("oa", SCRIPTS / "omission_audit.py")
oa = importlib.util.module_from_spec(_oa_spec)
sys.modules["oa"] = oa
_oa_spec.loader.exec_module(oa)

# Load preflight_propose (for the report-gate generate_proposal test)
_pf_spec = importlib.util.spec_from_file_location("pf", SCRIPTS / "preflight_propose.py")
pf = importlib.util.module_from_spec(_pf_spec)
sys.modules["pf"] = pf
_pf_spec.loader.exec_module(pf)


def _init_repo(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for a in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
              ["git", "config", "user.name", "t"]):
        subprocess.run(a, cwd=str(d), check=True)


def _write(d: Path, rel: str, content: str = "x") -> None:
    p = d / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _state_fixture(state: Path, rid: str, gate: dict, owned: list[str],
                   claim: str = "done", cer_verdict: str = "PASS",
                   cer_rows: list | None = None) -> None:
    (state / f"task-proposal_{rid}.json").write_text(
        json.dumps({"report_gate": gate}), encoding="utf-8")
    (state / f"diff-summary_{rid}.json").write_text(
        json.dumps({"files": owned}), encoding="utf-8")
    (state / f"completion-evidence-review_{rid}.json").write_text(
        json.dumps({"verdict": cer_verdict, "evidence": cer_rows or []}), encoding="utf-8")
    (state / f".verified_{rid}").touch()
    (state / f"claude-task-result_{rid}.json").write_text(
        json.dumps({"summary": claim}), encoding="utf-8")


class TestAuthorityLadder:
    """L0..L5 derivation from observed artifacts."""

    def test_l0_when_only_worker_report(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "auth-1"
        (state / f"task-proposal_{rid}.json").write_text(
            json.dumps({"report_gate": {"omission_audit_required": True}}), encoding="utf-8")
        (state / f"claude-task-result_{rid}.json").write_text(
            json.dumps({"summary": "done"}), encoding="utf-8")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.triggered is True
        assert r.completion_authority_level == "L1_source_inspected"

    def test_l5_when_closure_passes(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "auth-5"
        _state_fixture(state, rid,
                       gate={"omission_audit_required": True, "confirm_closed_passes": True},
                       owned=["a.py"])
        _write(wt, "a.py")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.completion_authority_level == "L5_original_symptom_confirmed_closed"


class TestVerdictDowngrade:
    """Req. 4: claim wording downgrades when evidence is missing."""

    def test_fixed_claim_at_l3_blocks(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "dn-1"
        _state_fixture(state, rid,
                       gate={"omission_audit_required": True, "confirm_closed_passes": False},
                       owned=["a.py"], claim="all fixed and shipped live")
        _write(wt, "a.py")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.verdict == "BLOCK"
        assert r.completion_authority_level == "L3_real_entrypoint_smoked"
        joined = " ".join(r.overclaims).lower()
        assert "fixed" in joined and "live" in joined and "shipped" in joined

    def test_fixed_claim_at_l5_passes(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "dn-2"
        _state_fixture(state, rid,
                       gate={"omission_audit_required": True, "confirm_closed_passes": True},
                       owned=["a.py"], claim="the bug is fixed")
        _write(wt, "a.py")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.verdict == "PASS"
        assert r.overclaims == []


class TestCommitBoundaryPacket:
    """Req. 5: classify dirty files; non-owned => commit_boundary_risk."""

    def test_parallel_dirty_file_revises(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "cb-1"
        _state_fixture(state, rid,
                       gate={"omission_audit_required": True, "confirm_closed_passes": True},
                       owned=["skills/go/scripts/foo.py"])
        _write(wt, "skills/go/scripts/foo.py")     # owned
        _write(wt, "skills/refactor/parallel.py")  # NOT owned
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.verdict == "REVISE"
        assert "skills/refactor/parallel.py" in r.commit_boundary_packet["not_owned"]
        assert "skills/go/scripts/foo.py" in r.commit_boundary_packet["mine_for_this_task"]
        assert r.commit_boundary_packet["auto_commit_could_bundle_unrelated"] is True

    def test_clean_owned_tree_passes(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "cb-2"
        _state_fixture(state, rid,
                       gate={"omission_audit_required": True, "confirm_closed_passes": True},
                       owned=["a.py"])
        _write(wt, "a.py")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.verdict == "PASS"
        assert r.commit_boundary_packet["not_owned"] == []


class TestMechanismChangeContract:
    """Req. 6: required contract fields must be filled when extending machinery."""

    def test_missing_contract_fields_revise(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "mc-1"
        (state / f"task-proposal_{rid}.json").write_text(json.dumps({
            "report_gate": {"omission_audit_required": True, "confirm_closed_passes": True},
            "mechanism_change": {
                "required": True, "extension_path": "EXTEND_EXISTING",
                "writer": None, "storage": None, "reader": None, "authority": None,
                "freshness": None, "failure_behavior": None, "live_acceptance_evidence": None,
            },
        }), encoding="utf-8")
        (state / f"diff-summary_{rid}.json").write_text(json.dumps({"files": ["a.py"]}), encoding="utf-8")
        (state / f"completion-evidence-review_{rid}.json").write_text(
            json.dumps({"verdict": "PASS", "evidence": []}), encoding="utf-8")
        (state / f".verified_{rid}").touch()
        (state / f"claude-task-result_{rid}.json").write_text(
            json.dumps({"summary": "done"}), encoding="utf-8")
        _write(wt, "a.py")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.verdict == "REVISE"
        assert any("mechanism_change contract incomplete" in g for g in r.blocking_gaps)

    def test_filled_contract_fields_pass(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "mc-2"
        full = {k: "filled" for k in
                ("writer", "storage", "reader", "authority", "freshness",
                 "failure_behavior", "live_acceptance_evidence")}
        (state / f"task-proposal_{rid}.json").write_text(json.dumps({
            "report_gate": {"omission_audit_required": True, "confirm_closed_passes": True},
            "mechanism_change": {"required": True, "extension_path": "EXTEND_EXISTING", **full},
        }), encoding="utf-8")
        (state / f"diff-summary_{rid}.json").write_text(json.dumps({"files": ["a.py"]}), encoding="utf-8")
        (state / f"completion-evidence-review_{rid}.json").write_text(
            json.dumps({"verdict": "PASS", "evidence": []}), encoding="utf-8")
        (state / f".verified_{rid}").touch()
        (state / f"claude-task-result_{rid}.json").write_text(
            json.dumps({"summary": "done"}), encoding="utf-8")
        _write(wt, "a.py")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.verdict == "PASS"


class TestTriggerPolicy:
    def test_not_triggered_when_gate_false(self, tmp_path):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "nt-1"
        (state / f"task-proposal_{rid}.json").write_text(
            json.dumps({"report_gate": {"omission_audit_required": False}}), encoding="utf-8")
        r = oa.run_audit(state_dir=state, run_id=rid, worktree=wt)
        assert r.verdict == "NOT_TRIGGERED"
        assert r.triggered is False
        assert r.commit_push_safe is True


class TestReportGateWiring:
    """Real report-gate path: generate_proposal sets the new fields."""

    def test_high_risk_prompt_sets_omission_audit_required(self):
        out = pf.generate_proposal(
            "fix the Stop hook to detect lazy workarounds in the router cache",
            "rg-1", "tid-rg")
        rg = out["report_gate"]
        assert rg["omission_audit_required"] is True
        assert rg["commit_boundary_required"] is True
        assert rg["dry_run_simplification_required"] is True
        assert rg["completion_authority_level"] == "L0_asserted_by_worker"
        per = out["plain_english_report"]
        assert "omission_audit" in per["section_order"]
        assert set(per["omission_audit"].keys()) >= {
            "what_was_proven", "what_was_not_proven", "what_was_inferred",
            "stale_state_risks", "commit_boundary_risks", "cache_runtime_risks",
            "writer_reader_wiring_risks", "synthetic_vs_live_evidence",
            "what_would_falsify_pass", "recommended_next_verification",
        }

    def test_low_risk_prompt_omits_audit_section(self):
        out = pf.generate_proposal(
            "add a one-line docstring to helper function foo", "rg-2", "tid-rg")
        rg = out["report_gate"]
        assert rg["omission_audit_required"] is False
        # commit_boundary still required for implement tasks, but no audit section
        assert "omission_audit" not in out["plain_english_report"]

    def test_mechanism_change_contract_fields_present(self):
        out = pf.generate_proposal(
            "investigate the hook dispatch router state lifecycle and telemetry",
            "rg-3", "tid-rg")
        mc = out["mechanism_change"]
        for f in ("writer", "storage", "reader", "authority", "freshness",
                  "failure_behavior", "live_acceptance_evidence"):
            assert f in mc


class TestCLIBoundary:
    def test_main_exits_2_on_block(self, tmp_path, capsys, monkeypatch):
        state, wt = tmp_path / "state", tmp_path / "wt"
        state.mkdir(); _init_repo(wt)
        rid = "cli-1"
        _state_fixture(state, rid,
                       gate={"omission_audit_required": True, "confirm_closed_passes": False},
                       owned=["a.py"], claim="all fixed and live")
        _write(wt, "a.py")
        rc = oa.main(["--state-dir", str(state), "--run-id", rid, "--worktree", str(wt)])
        assert rc == 2
        assert (state / f"omission-audit_{rid}.json").exists()
        assert (state / f".omission-audited_{rid}").exists()
