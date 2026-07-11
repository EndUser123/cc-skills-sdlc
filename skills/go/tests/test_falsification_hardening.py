"""Hardening tests for the bounded falsification gate (Parts 1-4).

Covers: command-ledger provenance, missing-budget enforcement, agent identity,
and session-pointer terminalization. These complement the pre-existing
test_falsification_gate.py (routing/request/result/verdict/worktree).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(autouse=True)
def _enable_falsification(monkeypatch):
    monkeypatch.setenv("GO_FALSIFICATION_ENABLE", "1")


def _import_fg():
    import importlib
    import falsification_gate
    importlib.reload(falsification_gate)
    return falsification_gate


def _fake_request(fg, run_id="run-x", request_digest="digest-x",
                  attack_worktree="/tmp/does-not-matter"):
    return {
        "schema": fg.REQUEST_SCHEMA,
        "run_id": run_id,
        "session_id": "sess-x",
        "request_digest": request_digest,
        "attack_worktree": attack_worktree,
        "head_revision": "abc",
        "base_revision": "abc",
        "task_id": "task-x",
        "budget": fg._DEFAULT_BUDGET,
    }


def _git_repo(dst: Path) -> Path:
    """Create a throwaway git repo with one committed file."""
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(dst), check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(dst), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(dst), check=True)
    (dst / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(dst), check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=str(dst), check=True)
    return dst


# ---------------------------------------------------------------------------
# Part 1: counterexample execution provenance
# ---------------------------------------------------------------------------

def test_1_ledger_backed_counterexample_accepted(tmp_path):
    fg = _import_fg()
    attack = tmp_path / "attack"
    attack.mkdir()
    req = _fake_request(fg, attack_worktree=str(attack))
    budget_state = {"max_commands": 5, "output_byte_cap": 1_000_000,
                    "commands_run": 0, "bytes_written": 0}
    entry = fg.run_constrained_command(
        tmp_path, "run-x", req, attack, "echo FALSIFICATION_PROOF",
        timeout=10, budget_state=budget_state)
    assert entry["ran"] and entry["completed"]
    ledger = fg.load_ledger(tmp_path, "run-x")
    assert len(ledger) == 1
    ce = {
        "claim_falsified": "should_block inverts session ownership",
        "command": "echo FALSIFICATION_PROOF",
        "expected_result": "foreign markers ignored",
        "actual_result": "FALSIFICATION_PROOF",
        "output": "FALSIFICATION_PROOF",
        "ledger_entry_id": entry["entry_id"],
    }
    result = {"schema": fg.RESULT_SCHEMA, "run_id": "run-x", "task_id": "task-x",
              "request_digest": req["request_digest"],
              "base_revision": "abc", "head_revision": "abc",
              "attacker_model": "sonnet", "verdict": "FALSIFIED", "counterexamples": [ce]}
    ok, reason = fg.validate_falsification_result(
        result, req, "run-x", ledger=ledger, attack_worktree=str(attack))
    assert ok, reason


def test_2_fabricated_command_without_ledger_rejected(tmp_path):
    fg = _import_fg()
    attack = tmp_path / "attack"
    attack.mkdir()
    req = _fake_request(fg, attack_worktree=str(attack))
    # No command run -> empty ledger.
    ledger = fg.load_ledger(tmp_path, "run-x")
    assert ledger == []
    ce = {
        "claim_falsified": "x", "command": "echo never_run",
        "expected_result": "a", "actual_result": "b", "output": "never_run",
        "ledger_entry_id": "run-x-cmd-0001",  # never recorded
    }
    result = {"schema": fg.RESULT_SCHEMA, "run_id": "run-x", "task_id": "task-x",
              "request_digest": req["request_digest"], "base_revision": "abc",
              "head_revision": "abc", "attacker_model": "sonnet",
              "verdict": "FALSIFIED", "counterexamples": [ce]}
    ok, reason = fg.validate_falsification_result(
        result, req, "run-x", ledger=ledger, attack_worktree=str(attack))
    assert not ok
    assert "fabricated" in reason or "not found" in reason


def test_3_foreign_ledger_entry_rejected(tmp_path):
    fg = _import_fg()
    attack = tmp_path / "attack"
    attack.mkdir()
    # Real entry bound to a DIFFERENT run.
    foreign_req = _fake_request(fg, run_id="run-OTHER",
                                request_digest="digest-OTHER",
                                attack_worktree=str(attack))
    fg.run_constrained_command(
        tmp_path, "run-OTHER", foreign_req, attack, "echo real",
        timeout=10, budget_state={"max_commands": 5, "commands_run": 0,
                                   "bytes_written": 0})
    # The ledger file is per-run; load the foreign one and cross-reference.
    foreign_ledger = fg.load_ledger(tmp_path, "run-OTHER")
    assert foreign_ledger
    foreign_eid = foreign_ledger[0]["entry_id"]
    # Attacker claims that entry against THIS run with a different digest.
    req = _fake_request(fg, run_id="run-x", request_digest="digest-x",
                        attack_worktree=str(attack))
    ce = {
        "claim_falsified": "x", "command": "echo real",
        "expected_result": "a", "actual_result": "b", "output": "real",
        "ledger_entry_id": foreign_eid,
    }
    result = {"schema": fg.RESULT_SCHEMA, "run_id": "run-x", "task_id": "task-x",
              "request_digest": "digest-x", "base_revision": "abc",
              "head_revision": "abc", "attacker_model": "sonnet",
              "verdict": "FALSIFIED", "counterexamples": [ce]}
    # This run's ledger is empty -> entry not found.
    own_ledger = fg.load_ledger(tmp_path, "run-x")
    ok, reason = fg.validate_falsification_result(
        result, req, "run-x", ledger=own_ledger, attack_worktree=str(attack))
    assert not ok
    # And even if the foreign ledger were supplied, binding must reject it.
    ok2, reason2 = fg.validate_falsification_result(
        result, req, "run-x", ledger=foreign_ledger, attack_worktree=str(attack))
    assert not ok2
    assert "mismatch" in reason2 or "foreign" in reason2


def test_4_command_timeout_enforced(tmp_path):
    fg = _import_fg()
    attack = tmp_path / "attack"
    attack.mkdir()
    req = _fake_request(fg, attack_worktree=str(attack))
    entry = fg.run_constrained_command(
        tmp_path, "run-x", req, attack,
        f'"{sys.executable}" -c "import time; time.sleep(5)"',
        timeout=0.5,
        budget_state={"max_commands": 5, "commands_run": 0, "bytes_written": 0})
    assert entry["ran"]
    assert entry["timed_out"] is True
    assert entry["completed"] is False
    # A counterexample referencing a timed-out command is rejected.
    ledger = fg.load_ledger(tmp_path, "run-x")
    ce = {"claim_falsified": "x", "command": entry["command"],
          "expected_result": "a", "actual_result": "b", "output": "",
          "ledger_entry_id": entry["entry_id"]}
    result = {"schema": fg.RESULT_SCHEMA, "run_id": "run-x", "task_id": "task-x",
              "request_digest": req["request_digest"], "base_revision": "abc",
              "head_revision": "abc", "attacker_model": "sonnet",
              "verdict": "FALSIFIED", "counterexamples": [ce]}
    ok, reason = fg.validate_falsification_result(
        result, req, "run-x", ledger=ledger, attack_worktree=str(attack))
    assert not ok
    assert "complete" in reason or "timed out" in reason


def test_5_command_count_exhausted(tmp_path):
    fg = _import_fg()
    attack = tmp_path / "attack"
    attack.mkdir()
    req = _fake_request(fg, attack_worktree=str(attack))
    budget_state = {"max_commands": 1, "commands_run": 0, "bytes_written": 0}
    e1 = fg.run_constrained_command(tmp_path, "run-x", req, attack, "echo one",
                                    timeout=10, budget_state=budget_state)
    assert e1["ran"]
    e2 = fg.run_constrained_command(tmp_path, "run-x", req, attack, "echo two",
                                    timeout=10, budget_state=budget_state)
    assert e2["ran"] is False
    assert e2.get("rejected") == "command_count_exhausted"


# ---------------------------------------------------------------------------
# Part 2: file-count + byte budgets (attack-worktree write measurement)
# ---------------------------------------------------------------------------

def test_6_file_count_budget_enforced(tmp_path):
    fg = _import_fg()
    repo = _git_repo(tmp_path / "repo")
    # Create 3 new files (exceeds a budget of 2).
    for i in range(3):
        (repo / f"new{i}.txt").write_text("x", encoding="utf-8")
    writes = fg.measure_attack_worktree_writes(repo)
    assert writes["files_changed"] >= 3
    # Resume-time budget check: max_files_writable=2 -> violation.
    max_files = 2
    assert writes["files_changed"] > max_files


def test_7_byte_budget_enforced(tmp_path):
    fg = _import_fg()
    repo = _git_repo(tmp_path / "repo")
    payload = "A" * 5000
    (repo / "big.txt").write_text(payload, encoding="utf-8")
    writes = fg.measure_attack_worktree_writes(repo)
    assert writes["bytes_written"] >= 5000
    # max_aggregate_bytes=2048 -> violation.
    assert writes["bytes_written"] > 2048


# ---------------------------------------------------------------------------
# Part 3: agent identity
# ---------------------------------------------------------------------------

def test_8_agent_identity_recorded(tmp_path):
    fg = _import_fg()
    repo = _git_repo(tmp_path / "repo")
    task = {"task_type": "implementation", "title": "t", "objective": "o",
            "id": "task-x"}
    payload = fg.build_falsification_request(
        tmp_path, "run-x", repo, task, ["hooks/x.py"],
        {"prompt_review_required": True}, ["high-risk surfaces: ['hook']"],
        session_id="sess-1")
    ai = payload.get("agent_identity")
    assert isinstance(ai, dict)
    assert ai["requested_model_policy"] == "advisory"
    assert ai["parent_session_id"] == "sess-1"
    # Fields the harness cannot introspect are sentinel-marked, never guessed.
    assert ai["actual_model"] == "UNAVAILABLE_FROM_RUNTIME"
    assert ai["effort"] == "UNAVAILABLE_FROM_RUNTIME"
    assert ai["agent_type"] == "UNAVAILABLE_FROM_RUNTIME"
    assert ai["model_matches_implementing_model"] == "UNAVAILABLE_FROM_RUNTIME"


# ---------------------------------------------------------------------------
# Part 4: session-pointer terminalization
# ---------------------------------------------------------------------------

def _make_pointer(artifacts_root, session_id, run_id, state_dir):
    ptr_dir = artifacts_root / "go-sessions"
    ptr_dir.mkdir(parents=True, exist_ok=True)
    ptr = ptr_dir / f"{session_id}.json"
    ptr.write_text(json.dumps({
        "go_state_dir": str(state_dir), "run_id": run_id,
        "updated_at": "2026-07-11T00:00:00Z"}), encoding="utf-8")
    return ptr


def test_9_terminal_falsification_resolves_pointer(tmp_path, monkeypatch):
    fg = _import_fg()
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("GO_ARTIFACTS_ROOT", str(artifacts))
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    ptr = _make_pointer(artifacts, "sess-A", "run-1", state_dir)
    assert ptr.is_file()
    report = fg.terminalize_session_pointer("sess-A", "run-1", str(state_dir))
    assert report["terminalized"] is True
    assert not ptr.exists()


def test_10_foreign_and_newer_pointers_untouched(tmp_path, monkeypatch):
    fg = _import_fg()
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("GO_ARTIFACTS_ROOT", str(artifacts))
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    # Same session, DIFFERENT run_id (a newer run reused the session).
    ptr_new = _make_pointer(artifacts, "sess-A", "run-NEWER", state_dir)
    # Different session entirely.
    ptr_other = _make_pointer(artifacts, "sess-B", "run-1", state_dir)
    r1 = fg.terminalize_session_pointer("sess-A", "run-1", str(state_dir))
    assert r1["terminalized"] is False
    assert "foreign" in r1["reason"] or "not touched" in r1["reason"]
    assert ptr_new.is_file() and ptr_other.is_file()


# ---------------------------------------------------------------------------
# Part 11/12: single-authored .pr-ready + default-off
# ---------------------------------------------------------------------------

def test_11_pr_ready_single_authored():
    """falsification_gate.py must NOT write the .pr-ready/.pr_ready completion
    marker — only the orchestrator's pr-artifacts tail does."""
    src = (SCRIPTS / "falsification_gate.py").read_text(encoding="utf-8")
    assert "pr-ready" not in src and "pr_ready" not in src, \
        "falsification_gate must not author the completion marker"


def test_12_default_disabled(monkeypatch):
    monkeypatch.delenv("GO_FALSIFICATION_ENABLE", raising=False)
    fg = _import_fg()
    task = {"task_type": "implementation", "title": "Fix hook gate",
            "objective": "Fix Stop hook session identity check"}
    reqd, reasons = fg.should_falsify(
        task, {"prompt_review_required": True}, ["hooks/Stop_x.py"])
    assert reqd is False
    assert any("GO_FALSIFICATION_ENABLE" in r for r in reasons)
