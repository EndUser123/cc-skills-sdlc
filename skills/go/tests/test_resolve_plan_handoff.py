"""Tests for the bare-invocation plan-handoff resolver (TASK-000).

Layer map:
  - unit (TestCandidateFilter): parses synthetic plan fixtures, proves the
    candidate preconditions (status, unresolved_blockers, go_next_task presence)
    and the single/multiple/none branching.
  - direct invocation (TestDirectInvocation): runs resolve_plan_handoff.py as a
    real subprocess with a temp plans dir, proves the exit-code contract
    (0 bind / 2 ambiguous / 3 fall-through) and the active-task artifact shape.
"""
from __future__ import annotations

import os
import json
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resolve_plan_handoff.py"


READY = textwrap.dedent(
    """
    ---
    status: implementation-ready
    unresolved_blockers: 0
    go_next_task:
      task_id: {tid}
      title: {title}
      objective: {objective}
      verification_commands: pytest -q, python -c "pass"
      priority: P2
    ---
    # {title}
    """
).strip() + "\n"


def _write_plan(dir_: Path, name: str, tid: str, title: str = "t", objective: str = "do it") -> Path:
    p = dir_ / name
    text = READY.format(tid=tid, title=title, objective=objective)
    p.write_text(text, encoding="utf-8")
    import hashlib

    (p.with_suffix(p.suffix + ".evidence-gate.json")).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "plan_path": str(p.resolve()),
                "plan_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "verdict": "PASS",
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# importable unit tests (parse logic)
# ---------------------------------------------------------------------------


def _import_resolver(plans_dir: Path, state_dir: Path, run_id: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location("rph_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # patch module-level paths
    mod.PLANS_DIR = plans_dir
    mod.STATE_DIR = state_dir
    mod.RUN_ID = run_id
    mod.TERMINAL_ID = "unit"
    return mod


def test_candidate_filter_requires_ready_status(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "---\nstatus: in-review\nunresolved_blockers: 0\ngo_next_task:\n  task_id: T1\n  objective: x\n---\n# a\n",
        encoding="utf-8",
    )
    mod = _import_resolver(tmp_path, tmp_path, "r1")
    assert mod._candidate_plans() == []


def test_candidate_filter_requires_zero_blockers(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "---\nstatus: implementation-ready\nunresolved_blockers: 1\ngo_next_task:\n  task_id: T1\n  objective: x\n---\n# a\n",
        encoding="utf-8",
    )
    mod = _import_resolver(tmp_path, tmp_path, "r1")
    assert mod._candidate_plans() == []


def test_candidate_filter_requires_go_next_task(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "---\nstatus: implementation-ready\nunresolved_blockers: 0\n---\n# a\n",
        encoding="utf-8",
    )
    mod = _import_resolver(tmp_path, tmp_path, "r1")
    assert mod._candidate_plans() == []


def test_candidate_filter_requires_objective(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "---\nstatus: implementation-ready\nunresolved_blockers: 0\ngo_next_task:\n  task_id: T1\n---\n# a\n",
        encoding="utf-8",
    )
    mod = _import_resolver(tmp_path, tmp_path, "r1")
    assert mod._candidate_plans() == []


def test_candidate_filter_accepts_valid(tmp_path: Path) -> None:
    _write_plan(tmp_path, "a.md", "T-1")
    mod = _import_resolver(tmp_path, tmp_path, "r1")
    cands = mod._candidate_plans()
    assert len(cands) == 1
    plan_path, flat, gnt = cands[0]
    assert gnt["task_id"] == "T-1"
    assert gnt["title"] == "t"
    assert flat["status"] == "implementation-ready"


def test_freshest_wins_on_mtime(tmp_path: Path) -> None:
    import time

    _write_plan(tmp_path, "old.md", "T-OLD")
    time.sleep(0.05)
    _write_plan(tmp_path, "new.md", "T-NEW")
    mod = _import_resolver(tmp_path, tmp_path, "r1")
    cands = mod._candidate_plans()
    # sorted newest-first; the freshest plan is first
    assert cands[0][2]["task_id"] == "T-NEW"


def test_build_task_splits_verification_commands(tmp_path: Path) -> None:
    _write_plan(tmp_path, "a.md", "T-1")
    mod = _import_resolver(tmp_path, tmp_path, "r1")
    _, _, gnt = mod._candidate_plans()[0]
    task = mod._build_task(gnt)
    assert task["verification_commands"] == ['pytest -q', 'python -c "pass"']
    assert task["priority"] == "P2"
    assert task["task_type"] == "implementation"


# ---------------------------------------------------------------------------
# direct invocation (subprocess) — exit-code contract + artifact shape
# ---------------------------------------------------------------------------


def _run_resolver(plans_dir: Path, state_dir: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["GO_PLANS_DIR"] = str(plans_dir)
    env["GO_STATE_DIR"] = str(state_dir)
    env["RUN_ID"] = "rid-" + uuid.uuid4().hex[:8]
    env["TERMINAL_ID"] = "di"
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.strip(), env["RUN_ID"]


def test_no_candidate_returns_3(tmp_path: Path) -> None:
    plans = tmp_path / "plans"
    plans.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    rc, out, _ = _run_resolver(plans, state)
    assert rc == 3
    assert "no implementation-ready" in out


def test_single_candidate_binds_and_writes_active_task(tmp_path: Path) -> None:
    plans = tmp_path / "plans"
    plans.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    _write_plan(plans, "p.md", "T-BIND", title="bind me", objective="bind obj")
    rc, out, rid = _run_resolver(plans, state)
    assert rc == 0
    assert "bound T-BIND" in out
    active = state / f"active-task_{rid}.json"
    assert active.exists()
    import json

    payload = json.loads(active.read_text(encoding="utf-8"))
    assert payload["source"] == "plan-handoff"
    assert payload["task"]["id"] == "T-BIND"
    assert payload["task"]["title"] == "bind me"
    assert payload["task"]["objective"] == "bind obj"
    assert payload["plan_binding"]["selected_task_id"] == "T-BIND"
    assert payload["plan_binding"]["plan_path"].endswith("p.md")


def test_multiple_candidates_pause_with_exit_2(tmp_path: Path) -> None:
    plans = tmp_path / "plans"
    plans.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    _write_plan(plans, "p1.md", "T-1")
    _write_plan(plans, "p2.md", "T-2")
    rc, out, rid = _run_resolver(plans, state)
    assert rc == 2
    assert "disambiguate" in out
    paused = state / f".paused_{rid}"
    assert paused.exists()
    import json

    paused_payload = json.loads(paused.read_text(encoding="utf-8"))
    assert paused_payload["reason"] == "multiple_plan_candidates"
    assert len(paused_payload["candidates"]) == 2


def test_active_task_is_not_written_on_fall_through(tmp_path: Path) -> None:
    plans = tmp_path / "plans"
    plans.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    # ready plan but no go_next_task → not a candidate → exit 3, no active-task
    (plans / "x.md").write_text(
        "---\nstatus: implementation-ready\nunresolved_blockers: 0\n---\n# x\n",
        encoding="utf-8",
    )
    rc, out, rid = _run_resolver(plans, state)
    assert rc == 3
    assert not (state / f"active-task_{rid}.json").exists()
