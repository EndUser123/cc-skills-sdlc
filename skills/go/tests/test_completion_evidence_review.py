"""Tests for /go Completion Evidence Review.

Per the repo anti-mock policy: real imports of completion_evidence_review,
real subprocess git invocations against a tmp_path worktree, no Mock objects.
Each test reproduces a known failure mode the user catches post-PASS.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import completion_evidence_review as cer  # noqa: E402


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--quiet", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "test")


def _commit_all(path: Path, msg: str) -> None:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", msg)


def _make_active_task(state_dir: Path, run_id: str, **fields: object) -> dict:
    state_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "title": fields.get("title", "Update hook gate"),
        "objective": fields.get("objective", "Update hook gate"),
        "status": fields.get("status", "completed"),
        "summary": fields.get("summary", "Implementation finished."),
        "task_type": fields.get("task_type", "implementation"),
        "files_modified": fields.get("files_modified", []),
    }
    payload = {"task": task, "run_id": run_id}
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return task


def _make_claude_result(state_dir: Path, run_id: str, summary: str, status: str = "success") -> None:
    payload = {"run_id": run_id, "status": status, "summary": summary, "files_modified": []}
    (state_dir / f"claude-task-result_{run_id}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 1) helper exists but no caller → REVISE
# ---------------------------------------------------------------------------

def test_helper_exists_but_no_caller_triggers_revise(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-helper"
    worktree = tmp_path / "wt"
    _init_repo(worktree)

    # Seed main branch with a known file.
    (worktree / "lib.py").write_text("def keep():\n    return 1\n", encoding="utf-8")
    _commit_all(worktree, "init lib")
    _git(worktree, "checkout", "-q", "-b", "feature")
    (worktree / "lib.py").write_text(
        "def keep():\n    return 1\n\ndef brand_new_helper():\n    return 42\n",
        encoding="utf-8",
    )
    _commit_all(worktree, "add orphan helper")

    _make_active_task(
        state_dir, run_id,
        title="Add helper",
        objective="Add helper for re-use",
        summary="Added brand_new_helper; tests pass.",
        files_modified=[{"path": "lib.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation finished.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    assert result.verdict in {"REVISE", "BLOCK"}, result
    gap_text = " ".join(result.blocking_gaps)
    assert "brand_new_helper" in gap_text, gap_text


# ---------------------------------------------------------------------------
# 2) source-only claim of live behavior → REVISE/BLOCK
# ---------------------------------------------------------------------------

def test_source_only_live_claim_triggers_revise_or_block(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-live"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "plugin.json").write_text("{}\n", encoding="utf-8")
    _commit_all(worktree, "init")
    _git(worktree, "checkout", "-q", "-b", "feature")
    (worktree / "plugin.json").write_text("{}\n", encoding="utf-8")  # no actual change
    _commit_all(worktree, "noop")

    _make_active_task(
        state_dir, run_id,
        title="Fix dispatcher",
        objective="Make dispatcher wired and live",
        summary="Dispatcher is now wired and live in production.",
        task_type="implementation",
    )
    _make_claude_result(state_dir, run_id, "Live and wired; tests pass.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    # Live claim without smoke/cache artifact must downgrade to REVISE/BLOCK.
    assert result.verdict in {"REVISE", "BLOCK"}, result
    assert not result.commit_push_safe


# ---------------------------------------------------------------------------
# 3) wrong-layer Stop hook broad analysis → BLOCK
# ---------------------------------------------------------------------------

def test_stop_hook_broad_analysis_triggers_block(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-layer"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    stop_dir = worktree / "hooks"
    stop_dir.mkdir()
    (stop_dir / "Stop.py").write_text(
        "def main():\n    print('ok')\n", encoding="utf-8"
    )
    _commit_all(worktree, "init stop")
    _git(worktree, "checkout", "-q", "-b", "feature")
    # Broad-analysis verb introduced into Stop.py.
    (stop_dir / "Stop.py").write_text(
        "def pattern_detection():\n    return []\n\n"
        "def main():\n    pattern_detection()\n    print('ok')\n",
        encoding="utf-8",
    )
    _commit_all(worktree, "broaden stop hook")

    _make_active_task(
        state_dir, run_id,
        title="Add pattern detection to Stop hook",
        objective="Add pattern detection to Stop hook",
        summary="Pattern detection added to Stop.py.",
        files_modified=[{"path": "hooks/Stop.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation done; tests pass.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    assert result.verdict == "BLOCK", result
    assert not result.commit_push_safe
    layer_msgs = [g for g in result.blocking_gaps if "broad" in g.lower() or "stop" in g.lower()]
    assert layer_msgs, result.blocking_gaps


# ---------------------------------------------------------------------------
# 4) missing writer for reader path → REVISE
# ---------------------------------------------------------------------------

def test_missing_writer_for_reader_triggers_revise(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-writer"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "reader.py").write_text(
        "def load_telemetry():\n    return []\n", encoding="utf-8"
    )
    _commit_all(worktree, "init reader")
    _git(worktree, "checkout", "-q", "-b", "feature")
    # New reader line added; no writer anywhere in the repo.
    (worktree / "reader.py").write_text(
        "def load_telemetry():\n"
        "    import json\n"
        "    with open('telemetry_out.jsonl') as fh:\n"
        "        return [json.loads(l) for l in fh if l.strip()]\n",
        encoding="utf-8",
    )
    _commit_all(worktree, "add reader without writer")

    _make_active_task(
        state_dir, run_id,
        title="Add telemetry reader",
        objective="Read telemetry data for review",
        summary="Reader added.",
        files_modified=[{"path": "reader.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Reader added; ready.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    assert result.verdict in {"REVISE", "BLOCK"}, result
    assert any("writer" in g.lower() or "telemetry" in g.lower() for g in result.blocking_gaps), result.blocking_gaps


# ---------------------------------------------------------------------------
# 5) synthetic-only failover claim → BLOCK
# ---------------------------------------------------------------------------

def test_synthetic_only_failover_claim_triggers_block(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-failover"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "failover.py").write_text(
        "def choose_model():\n    return 'primary'\n", encoding="utf-8"
    )
    _commit_all(worktree, "init failover")
    _git(worktree, "checkout", "-q", "-b", "feature")
    # No subprocess / run_script invocation; only monkeypatch-heavy logic.
    (worktree / "failover.py").write_text(
        "from unittest.mock import patch, MagicMock\n\n"
        "def choose_model():\n"
        "    with patch('mod.A') as a, patch('mod.B') as b:\n"
        "        a.return_value = MagicMock()\n"
        "        return 'fallback'\n",
        encoding="utf-8",
    )
    _commit_all(worktree, "mock-only failover")

    _make_active_task(
        state_dir, run_id,
        title="Wire failover harness",
        objective="Wire failover harness with fallback",
        summary="Failover works; fallback verified.",
        files_modified=[{"path": "failover.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Failover verified; tests pass.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    assert result.verdict == "BLOCK", result
    assert not result.commit_push_safe


# ---------------------------------------------------------------------------
# 6) clean evidence packet → PASS
# ---------------------------------------------------------------------------

def test_clean_evidence_packet_passes(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-clean"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (worktree / "test_calc.py").write_text(
        "from calc import add\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    _commit_all(worktree, "init calc")
    _git(worktree, "checkout", "-q", "-b", "feature")
    (worktree / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n"
        "def sub(a, b):\n    return a - b\n",
        encoding="utf-8",
    )
    (worktree / "test_calc.py").write_text(
        "from calc import add, sub\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n\n"
        "def test_sub():\n    assert sub(5, 3) == 2\n",
        encoding="utf-8",
    )
    _commit_all(worktree, "extend calc")

    _make_active_task(
        state_dir, run_id,
        title="Extend calc helpers",
        objective="Extend calc helpers",
        summary="Implementation in progress; tests pass.",
        files_modified=[
            {"path": "calc.py", "change_type": "modified"},
            {"path": "test_calc.py", "change_type": "modified"},
        ],
    )
    _make_claude_result(state_dir, run_id, "Implementation in progress; tests pass.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    # No live-behavior claims, no broad verb, helpers all tested.
    assert result.verdict in {"PASS", "PASS_WITH_FOLLOWUP"}, result
    # And either it's clean PASS or non-blocking follow-up only.
    if result.verdict == "PASS_WITH_FOLLOWUP":
        assert all("weak" in (r.verdict or "").lower() or r.verdict == "WEAK" for r in result.evidence)


# ---------------------------------------------------------------------------
# 7) follow-up-only nonblocking gap → PASS WITH FOLLOW-UP
# ---------------------------------------------------------------------------

def test_followup_only_nonblocking_gap_yields_pass_with_followup(tmp_path):
    state_dir = tmp_path / "state"
    run_id = "run-followup"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "svc.py").write_text(
        "def serve():\n    return 'ok'\n", encoding="utf-8"
    )
    _commit_all(worktree, "init svc")
    _git(worktree, "checkout", "-q", "-b", "feature")
    # Write a top-level `state.json` -- multi-terminal risk (WEAK only).
    (worktree / "svc.py").write_text(
        "def serve():\n    return 'ok'\n\n"
        "def new_helper():\n    return serve()\n",
        encoding="utf-8",
    )
    (worktree / "state.json").write_text("{}\n", encoding="utf-8")
    _commit_all(worktree, "weak state path")

    _make_active_task(
        state_dir, run_id,
        title="Add helper",
        objective="Add helper for serve()",
        summary="Implementation in progress.",
        files_modified=[
            {"path": "svc.py", "change_type": "modified"},
            {"path": "state.json", "change_type": "created"},
        ],
    )
    _make_claude_result(state_dir, run_id, "Implementation in progress.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    # top-level state.json is WEAK (non-blocking). No live claim, no broad verb.
    assert result.verdict in {"PASS", "PASS_WITH_FOLLOWUP"}, result
    if result.verdict == "PASS_WITH_FOLLOWUP":
        assert result.commit_push_safe, result