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
# 5) synthetic-only failover claim → REVISE (calibration-required: uncalibrated
# heuristic surfaces as blocking_gap, not overclaim; yields REVISE, not BLOCK)
# ---------------------------------------------------------------------------

def test_synthetic_only_failover_claim_triggers_revise(tmp_path):
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
        title="Implement harness swap path",
        objective="Implement harness swap path",
        summary="Implemented the harness swap path.",
        files_modified=[{"path": "failover.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Harness swap implemented.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    # Uncalibrated heuristic -> REVISE, not BLOCK. BLOCK requires calibrated
    # or unambiguous evidence (wrong-layer contamination or activation
    # overclaim with matching artifact absence).
    assert result.verdict == "REVISE", result
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
# 7b) greenfield helper + greenfield caller (both untracked) → PASS
# ---------------------------------------------------------------------------

def test_greenfield_helper_with_greenfield_caller_passes(tmp_path):
    """A new helper called only by a new, untracked caller must not false-REVISE.

    Regression: earlier the detector used git grep which only searches tracked
    files; pure-additive work hit false REVISE/BLOCK.
    """
    state_dir = tmp_path / "state"
    run_id = "run-greenfield"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    # Seed repo with one empty commit so we have a base.
    (worktree / "readme.md").write_text("# project\n", encoding="utf-8")
    _commit_all(worktree, "init")
    # New helper + new caller, both UNTRACKED. Caller references the helper.
    (worktree / "svc.py").write_text(
        "def new_helper():\n    return 1\n", encoding="utf-8"
    )
    (worktree / "cli.py").write_text(
        "from svc import new_helper\n\ndef main():\n    return new_helper()\n",
        encoding="utf-8",
    )

    _make_active_task(
        state_dir, run_id,
        title="Add greenfield helper",
        objective="Add greenfield helper + caller",
        summary="Implementation in progress.",
        files_modified=[
            {"path": "svc.py", "change_type": "created"},
            {"path": "cli.py", "change_type": "created"},
        ],
    )
    _make_claude_result(state_dir, run_id, "Implementation in progress.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    # No live-behavior claim, no broad verb, caller declared in active-task and
    # found by the working-tree grep over untracked files.
    assert result.verdict in {"PASS", "PASS_WITH_FOLLOWUP"}, result
    assert all(
        "new_helper" not in g
        for g in result.blocking_gaps
    ), f"false REVISE on greenfield caller: {result.blocking_gaps}"


# ---------------------------------------------------------------------------
# 7c) greenfield helper with NO caller at all → still REVISE
# ---------------------------------------------------------------------------

def test_greenfield_helper_without_caller_still_revise(tmp_path):
    """Sanity: orphan greenfield helper (no caller anywhere) still REVISE."""
    state_dir = tmp_path / "state"
    run_id = "run-orphan-greenfield"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "readme.md").write_text("# project\n", encoding="utf-8")
    _commit_all(worktree, "init")
    (worktree / "orphan.py").write_text(
        "def truly_orphan_helper():\n    return 42\n", encoding="utf-8"
    )
    _make_active_task(
        state_dir, run_id,
        title="Add helper",
        objective="Add helper",
        summary="Implementation in progress.",
        files_modified=[{"path": "orphan.py", "change_type": "created"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation in progress.")
    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    assert result.verdict in {"REVISE", "BLOCK"}, result
    assert any("truly_orphan_helper" in g for g in result.blocking_gaps), result.blocking_gaps


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
    (worktree / "cli.py").write_text(
        "from svc import serve\n\ndef main():\n    return serve()\n",
        encoding="utf-8",
    )
    _commit_all(worktree, "init svc")
    _git(worktree, "checkout", "-q", "-b", "feature")
    # New helper IS called from cli.py; only the top-level `state.json` is weak.
    (worktree / "svc.py").write_text(
        "def serve():\n    return 'ok'\n\n"
        "def new_helper():\n    return serve()\n",
        encoding="utf-8",
    )
    (worktree / "cli.py").write_text(
        "from svc import serve, new_helper\n\ndef main():\n    return new_helper() or serve()\n",
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
            {"path": "cli.py", "change_type": "modified"},
            {"path": "state.json", "change_type": "created"},
        ],
    )
    _make_claude_result(state_dir, run_id, "Implementation in progress.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    # top-level state.json is WEAK (non-blocking). No live claim, no broad verb.
    assert result.verdict in {"PASS", "PASS_WITH_FOLLOWUP"}, result
    if result.verdict == "PASS_WITH_FOLLOWUP":
        assert result.commit_push_safe, result


# ---------------------------------------------------------------------------
# 7d) INCOMPLETE (missing worker report) must block .pr-ready
# ---------------------------------------------------------------------------

def test_incomplete_blocks_on_missing_worker_report(tmp_path):
    """No claude-task-result, no pi-review, no active-task summary -> INCOMPLETE
    must exit 2 so run_common_tail returns False before .pr-ready."""
    state_dir = tmp_path / "state"
    run_id = "run-incomplete"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    _commit_all(worktree, "init")
    # active-task with NO summary and NO report files.
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"title": "X", "objective": "X"}, "run_id": run_id}),
        encoding="utf-8",
    )

    script = SCRIPTS / "completion_evidence_review.py"
    proc = subprocess.run(
        [sys.executable, str(script),
         "--worktree", str(worktree),
         "--state-dir", str(state_dir),
         "--run-id", run_id],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2, (
        f"INCOMPLETE must exit 2 to block .pr-ready; got {proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
    assert "INCOMPLETE" in proc.stdout


# ---------------------------------------------------------------------------
# 8) CLI boundary: orchestrator arg shape must not trip argparse
# ---------------------------------------------------------------------------

def test_cli_accepts_orchestrator_arg_shape(tmp_path):
    """The orchestrator calls: completion_evidence_review.py --worktree WT
    --state-dir SD --run-id RID. Argparse must accept this (regression:
    positional worktree previously exit-2'd every /go run at Step 9.5)."""
    state_dir = tmp_path / "state"
    run_id = "run-cli"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    _commit_all(worktree, "init")
    _make_active_task(state_dir, run_id, title="Calc", objective="Calc",
                      summary="Implementation in progress.")
    _make_claude_result(state_dir, run_id, "Implementation in progress.")

    script = SCRIPTS / "completion_evidence_review.py"
    # Exact shape used by orchestrate.py:run_common_tail Step 9.5.
    proc = subprocess.run(
        [sys.executable, str(script),
         "--worktree", str(worktree),
         "--state-dir", str(state_dir),
         "--run-id", run_id],
        capture_output=True, text=True,
    )
    assert proc.returncode != 2 or "unrecognized arguments" not in proc.stderr, proc.stderr
    assert "usage:" not in proc.stderr, proc.stderr
    out = state_dir / f"completion-evidence-review_{run_id}.json"
    assert out.is_file(), "reviewer must emit its artifact on the orchestrator arg shape"


# ---------------------------------------------------------------------------
# Review-boundary discipline (goal: surface load-bearing auto-committed
# changes that a clean git status or a generic commit title would hide).
# Each test exercises the real run_review path against a tmp_path git worktree.
# ---------------------------------------------------------------------------

def _boundary_row(result):
    """Find the review-boundary evidence row, if any."""
    for row in result.evidence:
        if "load-bearing change reviewable" in row.claim:
            return row
    return None


def test_load_bearing_orchestrate_change_with_generic_title_flagged(tmp_path):
    """orchestrate.py changed + generic 'chore(tests):' title → REVIEW_BOUNDARY_RISK."""
    state_dir = tmp_path / "state"
    run_id = "rb-generic"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    orch = worktree / "skills" / "go" / "scripts" / "orchestrate.py"
    orch.parent.mkdir(parents=True, exist_ok=True)
    orch.write_text("def run():\n    return 1\n", encoding="utf-8")
    _commit_all(worktree, "init")
    _git(worktree, "checkout", "-q", "-b", "feature")
    orch.write_text("def run():\n    return 2\n", encoding="utf-8")
    _commit_all(worktree, "chore(tests): update tests\n\n## WHY\nMaintenance update required.")

    _make_active_task(
        state_dir, run_id,
        title="Fix orchestrator arg shape",
        objective="Fix orchestrator arg shape",
        summary="Implementation finished.",
        files_modified=[{"path": "skills/go/scripts/orchestrate.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation finished.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _boundary_row(result)
    assert row is not None, f"boundary row missing: {[r.claim for r in result.evidence]}"
    assert row.verdict == "WEAK", row
    assert "REVIEW_BOUNDARY_RISK" in row.note, row.note
    assert "understates" in row.observed_evidence.lower() or "true" in row.observed_evidence.lower(), row.observed_evidence


def test_tests_only_change_with_generic_title_not_flagged(tmp_path):
    """A tests-only change carries no load-bearing surface → no boundary row."""
    state_dir = tmp_path / "state"
    run_id = "rb-testsonly"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    (worktree / "calc.py").write_text("def add(a,b): return a+b\n", encoding="utf-8")
    (worktree / "test_calc.py").write_text("def test_add(): assert True\n", encoding="utf-8")
    _commit_all(worktree, "init")
    _git(worktree, "checkout", "-q", "-b", "feature")
    (worktree / "test_calc.py").write_text("def test_add(): assert True\ndef test_more(): assert 1\n", encoding="utf-8")
    _commit_all(worktree, "chore(tests): update tests\n\n## WHY\nMaintenance update required.")

    _make_active_task(
        state_dir, run_id,
        title="Extend tests",
        objective="Extend tests",
        summary="Implementation finished.",
        files_modified=[{"path": "test_calc.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation finished.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _boundary_row(result)
    assert row is None, f"tests-only change must not produce a boundary row: {row}"


def test_hook_change_requires_commit_sha_and_git_show_evidence(tmp_path):
    """A hook change must surface commit SHA + git show --stat evidence."""
    state_dir = tmp_path / "state"
    run_id = "rb-hook"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    hooks = worktree / "skills" / "go" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "Stop_enforce_gate.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    _commit_all(worktree, "init")
    _git(worktree, "checkout", "-q", "-b", "feature")
    (hooks / "Stop_enforce_gate.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    _commit_all(worktree, "fix(stop): narrow completion-authority downgrade for shipping claims\n\n## WHY\nStop FP.")

    _make_active_task(
        state_dir, run_id,
        title="Narrow Stop hook",
        objective="Narrow Stop hook",
        summary="Implementation finished.",
        files_modified=[{"path": "skills/go/hooks/Stop_enforce_gate.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation finished.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _boundary_row(result)
    assert row is not None, "hook change must produce a boundary row"
    obs = row.observed_evidence
    # Specific title (fix:) → not understating; still must carry SHA + stat.
    assert "sha=" in obs and "(uncommitted)" not in obs, obs
    assert "git_show_stat=" in obs, obs
    assert "Stop_enforce_gate.py" in obs, obs


def test_clean_git_status_alone_insufficient_after_autocommit(tmp_path):
    """After auto-commit the working tree is clean, but the load-bearing change
    is still in HEAD and must still be surfaced (not hidden by clean status)."""
    state_dir = tmp_path / "state"
    run_id = "rb-clean"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    orch = worktree / "skills" / "go" / "scripts" / "orchestrate.py"
    orch.parent.mkdir(parents=True, exist_ok=True)
    orch.write_text("def run():\n    return 1\n", encoding="utf-8")
    _commit_all(worktree, "init")
    _git(worktree, "checkout", "-q", "-b", "feature")
    orch.write_text("def run():\n    return 2\n", encoding="utf-8")
    _commit_all(worktree, "chore(tests): update tests\n\n## WHY\nMaintenance update.")
    # Working tree is now CLEAN — auto-commit captured the change.
    clean = _git(worktree, "status", "--porcelain")
    assert clean.stdout.strip() == "", "precondition: working tree clean"

    _make_active_task(
        state_dir, run_id,
        title="Fix orchestrator",
        objective="Fix orchestrator",
        summary="Implementation finished.",
        files_modified=[{"path": "skills/go/scripts/orchestrate.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation finished.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _boundary_row(result)
    assert row is not None, "clean status must NOT hide a committed load-bearing change"
    assert "committed=True" in row.observed_evidence, row.observed_evidence


def test_cache_alignment_evidence_required_for_plugin_change(tmp_path, monkeypatch):
    """A plugin.json (cache-affecting) change with no matching cache version →
    alignment unproven → REVIEW_BOUNDARY_RISK flagged."""
    cache_root = tmp_path / "cache" / "local"
    monkeypatch.setenv("GO_PLUGIN_CACHE_ROOT", str(cache_root))
    state_dir = tmp_path / "state"
    run_id = "rb-cache"
    worktree = tmp_path / "wt"
    _init_repo(worktree)
    pj_dir = worktree / ".claude-plugin"
    pj_dir.mkdir(parents=True, exist_ok=True)
    (pj_dir / "plugin.json").write_text(
        json.dumps({"name": "test-plugin", "version": "1.0.0"}), encoding="utf-8"
    )
    _commit_all(worktree, "init")
    _git(worktree, "checkout", "-q", "-b", "feature")
    (pj_dir / "plugin.json").write_text(
        json.dumps({"name": "test-plugin", "version": "1.0.1"}), encoding="utf-8"
    )
    _commit_all(worktree, "chore: bump version\n\n## WHY\nMaintenance update.")
    # NOTE: cache_root has NO test-plugin dir → cache_version=None → not aligned.

    _make_active_task(
        state_dir, run_id,
        title="Bump plugin",
        objective="Bump plugin version",
        summary="Implementation finished.",
        files_modified=[{"path": ".claude-plugin/plugin.json", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, "Implementation finished.")

    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _boundary_row(result)
    assert row is not None, "plugin/cache change must produce a boundary row"
    assert row.verdict == "WEAK", row
    assert "aligned=False" in row.observed_evidence, row.observed_evidence
    assert "alignment unproven" in row.note, row.note


# ---------------------------------------------------------------------------
# Claim-integrity discipline (goal: distinguish proven claims from inferred
# ones; 'likely' in a high-risk verification context blocks full COMPLETE).
# ---------------------------------------------------------------------------

def _integrity_row(result):
    for row in result.evidence:
        if "honest evidence vocabulary" in row.claim:
            return row
    return None


def _ci_worktree_with_orchestrate(tmp_path, commit_msg, report_text):
    """Shared fixture: a worktree with a load-bearing orchestrate.py change so
    run_review is triggered, plus a worker report carrying the claim text."""
    state_dir = tmp_path / "state"
    run_id = "ci-" + commit_msg[:6].replace(" ", "").replace(":", "")
    worktree = tmp_path / ("wt-" + run_id)
    _init_repo(worktree)
    orch = worktree / "skills" / "go" / "scripts" / "orchestrate.py"
    orch.parent.mkdir(parents=True, exist_ok=True)
    orch.write_text("def run():\n    return 1\n", encoding="utf-8")
    _commit_all(worktree, "init")
    _git(worktree, "checkout", "-q", "-b", "feature")
    orch.write_text("def run():\n    return 2\n", encoding="utf-8")
    _commit_all(worktree, commit_msg)
    _make_active_task(
        state_dir, run_id,
        title="Fix orchestrator arg shape",
        objective="Fix orchestrator arg shape",
        summary=report_text,
        files_modified=[{"path": "skills/go/scripts/orchestrate.py", "change_type": "modified"}],
    )
    _make_claude_result(state_dir, run_id, report_text)
    return state_dir, run_id, worktree


def test_cache_likely_rebuilt_in_high_risk_report_flagged(tmp_path):
    report = "Implementation complete. The cache was likely rebuilt after the bump."
    state_dir, run_id, worktree = _ci_worktree_with_orchestrate(tmp_path, "fix: bump", report)
    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _integrity_row(result)
    assert row is not None, "'likely' + 'cache rebuilt' must produce a claim-integrity row"
    assert row.verdict == "WEAK", row
    assert "load_bearing_uncertainty" in row.observed_evidence, row.observed_evidence
    # Downgrade COMPLETE → not PASS.
    assert result.verdict != "PASS", result
    assert any("CLAIM_INTEGRITY" in g for g in result.blocking_gaps), result.blocking_gaps


def test_advisory_uncertainty_language_allowed(tmp_path):
    """'this likely belongs in Priority 4' has no high-risk context → allowed."""
    report = "Implementation finished. This likely belongs in Priority 4 follow-up."
    state_dir, run_id, worktree = _ci_worktree_with_orchestrate(tmp_path, "fix: x", report)
    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _integrity_row(result)
    assert row is None, f"advisory uncertainty must NOT produce a row: {row}"
    assert "CLAIM_INTEGRITY" not in " ".join(result.blocking_gaps), result.blocking_gaps


def test_honest_replacement_vocabulary_passes(tmp_path):
    """'proven'/'unverified' replacement wording is honest → passes."""
    report = ("Source/cache line match PROVEN via normalized diff. "
              "Rebuild mechanism UNVERIFIED — no propagation trace captured.")
    state_dir, run_id, worktree = _ci_worktree_with_orchestrate(tmp_path, "fix: y", report)
    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _integrity_row(result)
    assert row is None, f"honest vocabulary must NOT be flagged: {row}"


def test_hook_likely_ran_blocks_live_hook_claim(tmp_path):
    report = "Done. The hook likely ran during the last session."
    state_dir, run_id, worktree = _ci_worktree_with_orchestrate(tmp_path, "fix: z", report)
    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _integrity_row(result)
    assert row is not None, "'likely' + 'hook ran' must block the live-hook claim"
    assert "load_bearing_uncertainty" in row.observed_evidence, row.observed_evidence
    assert result.verdict != "PASS", result


def test_tests_likely_cover_blocks_tests_passed_claim(tmp_path):
    report = "Fixed. The tests likely cover this change."
    state_dir, run_id, worktree = _ci_worktree_with_orchestrate(tmp_path, "fix: w", report)
    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    row = _integrity_row(result)
    assert row is not None, "'likely' + 'tests' must block the tests-passed claim"
    assert "load_bearing_uncertainty" in row.observed_evidence, row.observed_evidence
    assert result.verdict != "PASS", result


def test_evidence_backed_wording_passes(tmp_path):
    report = ("Verified: the artifact exists at the registered path (evidence: "
              "Read of the dispatch file at line 42). The run completed.")
    state_dir, run_id, worktree = _ci_worktree_with_orchestrate(tmp_path, "fix: v", report)
    result = cer.run_review(worktree=worktree, state_dir=state_dir, run_id=run_id)
    # No uncertainty term in a high-risk context → no claim-integrity row.
    row = _integrity_row(result)
    assert row is None, f"evidence-backed wording must not be flagged: {row}"