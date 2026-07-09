"""Tests for the high-risk completion-verifier (Step 9.7).

Real-boundary: exercises the orchestrator helpers (_completion_verify_gate,
_completion_verify_request_payload, _apply_completion_verify_result) and the
--completion-verify-resume branch against real tmp state dirs. run_script is
mocked only where it gates the tail (pr-artifacts/loop-check) — the verifier
machinery itself is exercised for real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import orchestrate as orch  # noqa: E402


def _write_active(state_dir: Path, run_id: str, *, title: str, **extra) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    task = {"title": title, "objective": title, "summary": "done", **extra}
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": task, "run_id": run_id}), encoding="utf-8"
    )


def test_highrisk_task_writes_request_and_pauses(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-hr"
    _write_active(state_dir, run_id, title="Update hook router dispatch",
                  acceptance_criteria=["router fires on Stop"],
                  scope_in=["hooks/Stop.py"])
    res = orch._completion_verify_gate(tmp_path, state_dir, run_id)
    assert res == "pause", res
    req = state_dir / f"completion-verify-request_{run_id}.json"
    assert req.is_file(), "high-risk must write a request artifact"
    payload = json.loads(req.read_text(encoding="utf-8"))
    assert payload["schema"] == "completion-verify-request.v1"
    assert payload["run_id"] == run_id
    assert payload["acceptance_criteria"] == ["router fires on Stop"]
    assert payload["calibration_mode"] == "advisory"
    assert payload["agent_contract"]["tools"] == ["Read", "Grep", "Glob", "Bash"]
    assert payload["agent_contract"]["read_only"] is True
    assert (state_dir / f".completion-verify-pending_{run_id}").is_file()


def test_lowrisk_task_skips_verifier(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    run_id = "run-lr"
    _write_active(state_dir, run_id, title="Extend calc helpers")
    # Make any title report low-risk (the marker set is expanded by other work).
    monkeypatch.setattr(orch, "_completion_verify_gate", None)  # no-op, replaced below
    monkeypatch.setattr("completion_evidence_review.task_should_trigger",
                        lambda _t: (False, "test-stub-low-risk"))
    res = orch._completion_verify_gate(tmp_path, state_dir, run_id)
    assert res == "skip", res
    assert not (state_dir / f"completion-verify-request_{run_id}.json").exists()
    assert not (state_dir / f".completion-verify-pending_{run_id}").exists()


def test_skip_env_disables_gate(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-skipenv"
    _write_active(state_dir, run_id, title="Update hook router dispatch")
    monkey = pytest.MonkeyPatch()
    monkey.setenv("GO_COMPLETION_VERIFY_SKIP", "1")
    try:
        assert orch._completion_verify_gate(tmp_path, state_dir, run_id) == "skip"
    finally:
        monkey.undo()


def test_resume_proceed_runs_tail(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    run_id = "run-proceed"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"completion-verify-result_{run_id}.json").write_text(json.dumps({
        "schema": "completion-verifier.v1", "run_id": run_id, "verdict": "PROCEED",
        "addressed": ["a"], "omitted": [], "uncertain": [], "evidence": [],
        "calibration_mode": "advisory",
    }), encoding="utf-8")
    (state_dir / f".completion-verify-pending_{run_id}").touch()

    monkeypatch.setenv("GO_STATE_DIR", str(state_dir))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("TERMINAL_ID", "t-proceed")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "t-proceed")
    monkeypatch.setattr(orch, "run_script", lambda *a, **k: 0)
    args = orch.parse_args(["--completion-verify-resume", run_id])
    out = orch.orchestrate(args)
    assert out == "<promise>PR_READY</promise>", out
    assert not (state_dir / f".completion-verify-pending_{run_id}").exists()
    ledger = (state_dir / "completion-verify-ledger.jsonl").read_text(encoding="utf-8")
    assert "PROCEED" in ledger


def test_resume_advisory_revise_does_not_block(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    run_id = "run-advise"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"completion-verify-result_{run_id}.json").write_text(json.dumps({
        "schema": "completion-verifier.v1", "run_id": run_id,
        "verdict": "ADVISORY_REVISE",
        "addressed": [], "omitted": ["criterion Z dropped"],
        "uncertain": [], "evidence": [], "calibration_mode": "advisory",
    }), encoding="utf-8")
    monkeypatch.setenv("GO_STATE_DIR", str(state_dir))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("TERMINAL_ID", "t-advise")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "t-advise")
    monkeypatch.setattr(orch, "run_script", lambda *a, **k: 0)
    args = orch.parse_args(["--completion-verify-resume", run_id])
    out = orch.orchestrate(args)
    assert out == "<promise>PR_READY</promise>", (
        "ADVISORY_REVISE must not block .pr-ready in calibration mode"
    )
    adv = state_dir / f".completion-verify-advisory_{run_id}"
    assert adv.is_file(), "advisory omissions must be surfaced to state"
    assert "criterion Z dropped" in adv.read_text(encoding="utf-8")


def test_resume_missing_result_fails_closed(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    run_id = "run-missing"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f".completion-verify-pending_{run_id}").touch()
    monkeypatch.setenv("GO_STATE_DIR", str(state_dir))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("TERMINAL_ID", "t-missing")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "t-missing")
    monkeypatch.setattr(orch, "run_script", lambda *a, **k: 0)
    args = orch.parse_args(["--completion-verify-resume", run_id])
    out = orch.orchestrate(args)
    assert out == "<promise>BLOCKED</promise>", out
    assert (state_dir / f".blocked_{run_id}").is_file()


def test_resume_malformed_result_does_not_crash_and_records_ledger(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    run_id = "run-malformed"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"completion-verify-result_{run_id}.json").write_text(
        "not json", encoding="utf-8"
    )
    monkeypatch.setenv("GO_STATE_DIR", str(state_dir))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("TERMINAL_ID", "t-malformed")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "t-malformed")
    monkeypatch.setattr(orch, "run_script", lambda *a, **k: 0)
    args = orch.parse_args(["--completion-verify-resume", run_id])
    orch.orchestrate(args)
    ledger = (state_dir / "completion-verify-ledger.jsonl").read_text(encoding="utf-8")
    assert "malformed_result" in ledger


def test_request_payload_carries_mechanical_review_verdict(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-payload"
    _write_active(state_dir, run_id, title="Update hook router dispatch",
                  acceptance_criteria=["x"])
    (state_dir / f"completion-evidence-review_{run_id}.json").write_text(json.dumps({
        "verdict": "PASS", "evidence": [{"claim": "c", "verdict": "OK"}],
    }), encoding="utf-8")
    payload = orch._completion_verify_request_payload(state_dir, run_id)
    assert payload["mechanical_review_verdict"] == "PASS"
    assert payload["mechanical_review_evidence"][0]["claim"] == "c"
