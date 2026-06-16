#!/usr/bin/env python3
"""Tests for the mutation phase added to run_phase.py.

These tests do not shell out to mutmut. They cover:

1. _parse_mutmut_counts — regex extraction of killed/survived/skipped/timeout.
2. CLI argument parsing accepts the new --phase mutation + --module flag.
3. The mutation handler writes a HMAC-signed MutationReceipt and never
   advances session.phase (the lifecycle invariant).
"""

import os
import sys
import json
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "__lib__"))

# Imported lazily inside tests so the missing quality_gates.json does not
# blow up module import.
run_phase = None


def _import_run_phase():
    global run_phase
    if run_phase is None:
        import importlib
        run_phase = importlib.import_module("run_phase")
    return run_phase


def test_parse_mutmut_counts_full_line() -> None:
    rp = _import_run_phase()
    out = "12 mutants: 7 killed, 3 survived, 1 skipped, 1 timeout"
    counts = rp._parse_mutmut_counts(out)
    assert counts == {
        "killed": 7, "survived": 3, "skipped": 1, "timeout": 1,
        "no_tests": 0, "total": 12,
    }


def test_parse_mutmut_counts_returns_zeros_when_no_match() -> None:
    rp = _import_run_phase()
    counts = rp._parse_mutmut_counts("no mutants here")
    assert counts == {
        "killed": 0, "survived": 0, "skipped": 0, "timeout": 0,
        "no_tests": 0, "total": 0,
    }


def test_parse_mutmut_counts_case_insensitive() -> None:
    rp = _import_run_phase()
    out = "5 MUTANTS: 3 Killed, 1 Survived, 0 Skipped, 1 Timeout"
    counts = rp._parse_mutmut_counts(out)
    assert counts["killed"] == 3
    assert counts["survived"] == 1
    assert counts["skipped"] == 0
    assert counts["timeout"] == 1
    assert counts["total"] == 5


def test_parse_mutmut_counts_handles_empty_string() -> None:
    rp = _import_run_phase()
    counts = rp._parse_mutmut_counts("")
    assert counts["total"] == 0


def test_cli_accepts_mutation_phase() -> None:
    """The --phase choice list now includes 'mutation'."""
    rp = _import_run_phase()
    # Inspect the parser's phase choices by reading the source.
    src = Path(str(rp.__file__)).read_text(encoding="utf-8")
    assert '"mutation"' in src
    assert "choices=[\"red\", \"green\", \"refactor\", \"mutation\"]" in src


def test_cli_module_arg_dispatches_to_mutation_handler(tmp_path: Path) -> None:
    """--phase mutation with --module routes to _run_mutation_phase."""
    rp = _import_run_phase()

    # run_phase.main() looks for STATE_ROOT/<run-id>/session.json
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "session.json").write_text("{}", encoding="utf-8")

    g_path = tmp_path / "qg.json"
    g_path.write_text(json.dumps({
        "version": 1,
        "default_mutation_score": 60,
        "critical_path_mutation_score": 80,
        "tool": {
            "name": "mutmut", "version": ">=3.0,<4",
            "coverage_guided": True,
            "runner": "pytest -x", "timeout_seconds": 30,
        },
        "modules": {},
    }), encoding="utf-8")

    captured = {}

    def fake_handler(*_all):
        captured["args"] = _all[0]

    real_session = _import_run_phase().SessionState(
        run_id="run-1", mode="feature", task="t", cwd=str(tmp_path),
        test_command="pytest", hmac_secret="secret",
    )

    with mock.patch.dict(os.environ, {"CLAUDE_QUALITY_GATES": str(g_path)}):
        with mock.patch.object(rp, "STATE_ROOT", tmp_path):
            with mock.patch.object(rp, "SessionState") as ss_cls:
                ss_cls.model_validate_json.return_value = real_session
                with mock.patch.object(rp, "_run_mutation_phase", side_effect=fake_handler) as mh:
                    with mock.patch.object(sys, "argv", [
                        "run_phase.py", "--run-id", "run-1",
                        "--phase", "mutation",
                        "--module", "skill_guard.breadcrumb.inference",
                    ]):
                        with mock.patch("os.getcwd", return_value=str(tmp_path)):
                            rp.main()

    assert mh.called, "mutation phase must dispatch to _run_mutation_phase"
    assert captured["args"].phase == "mutation"
    assert captured["args"].module == "skill_guard.breadcrumb.inference"


def test_mutation_handler_never_advances_session_phase(tmp_path: Path) -> None:
    """The lifecycle invariant: session.phase must not change after mutation."""
    rp = _import_run_phase()
    from session_models import SessionState  # type: ignore

    # Minimal session state (do not write to disk).
    session = SessionState(
        run_id="run-1",
        mode="feature",
        task="t",
        cwd=str(tmp_path),
        test_command="pytest",
        hmac_secret="secret",
    )
    original_phase = session.phase

    # Build an argparse-like args object.
    args = mock.MagicMock()
    args.module = "skill_guard.breadcrumb.inference"
    args.run_id = "run-1"

    # Fake mutmut output: all killed, score above any reasonable target.
    fake_completed = mock.MagicMock(
        stdout="20 mutants: 19 killed, 1 survived, 0 skipped, 0 timeout\n",
        stderr="",
        returncode=0,
    )
    # Build a tiny quality_gates.json inline so load_quality_gates() succeeds.
    g_path = tmp_path / "qg.json"
    g_path.write_text(json.dumps({
        "version": 1,
        "default_mutation_score": 60,
        "critical_path_mutation_score": 80,
        "tool": {
            "name": "mutmut",
            "version": ">=3.0,<4",
            "coverage_guided": True,
            "runner": "pytest -x --no-header -q",
            "timeout_seconds": 30,
        },
        "enforcement": {
            "block_pr_on_failure": True,
            "waiver_required_below_target": True,
            "treat_equivalent_mutants_under_threshold_as_pass": True,
        },
        "modules": {
            "skill_guard.breadcrumb.inference": {
                "tier": "critical",
                "target": 80,
                "skip_equivalent_threshold": 15,
            },
        },
    }), encoding="utf-8")

    with mock.patch.dict(os.environ, {"CLAUDE_QUALITY_GATES": str(g_path)}):
        with mock.patch.object(rp.subprocess, "run", return_value=fake_completed):
            rp._run_mutation_phase(args, tmp_path, session, tmp_path)

    # Lifecycle invariant: phase is untouched.
    assert session.phase == original_phase

    # Receipt was written and verifies.
    receipt_path = tmp_path / "mutation_receipt.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["module"] == "skill_guard.breadcrumb.inference"
    assert receipt["status"] == "passed"
    assert receipt["killed"] == 19
    assert receipt["survived"] == 1
    assert receipt["target_score"] == 80


def test_mutation_receipt_models_accept_waived_status(tmp_path: Path) -> None:
    """Waived mutation runs are valid receipts, not schema failures."""
    from session_models import MutationReceipt, MutationReceiptRef  # type: ignore

    ref = MutationReceiptRef(
        receipt_path="mutation_receipt.json",
        module="skill_guard.breadcrumb.inference",
        status="waived",
    )
    assert ref.status == "waived"

    receipt = MutationReceipt(
        run_id="run-1",
        test_command="mutmut run",
        cwd=str(tmp_path),
        exit_code=0,
        started_at="2026-06-16T00:00:00Z",
        finished_at="2026-06-16T00:00:01Z",
        stdout_path="stdout.txt",
        stdout_sha256="abc",
        module="skill_guard.breadcrumb.inference",
        status="waived",
        signature="placeholder",
    )
    assert receipt.status == "waived"
