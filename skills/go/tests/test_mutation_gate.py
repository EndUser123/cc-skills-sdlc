#!/usr/bin/env python3
"""Tests for /go mutation gate runtime."""

import importlib.util
import json
import pathlib
import sys
from types import SimpleNamespace

import jsonschema


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
MUTATION_GATE = _load_module("go_mutation_gate", PACKAGE / "scripts" / "mutation-gate.py")


def _write_active_task(state_dir: pathlib.Path, run_id: str) -> None:
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"id": "TASK-1", "title": "Mutation gate"}}) + "\n",
        encoding="utf-8",
    )


def test_mutation_gate_skips_without_selected_modules(monkeypatch, tmp_path):
    run_id = "run-skip"
    _write_active_task(tmp_path, run_id)
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("TERMINAL_ID", "term-1")
    monkeypatch.delenv("GO_MUTATION_MODULES", raising=False)
    monkeypatch.setattr(MUTATION_GATE, "load_quality_gates", lambda: None)

    assert MUTATION_GATE.main([]) == 0

    gate = json.loads((tmp_path / f"mutation-gate-{run_id}.json").read_text(encoding="utf-8"))
    verification = json.loads((tmp_path / f"verification-result_{run_id}.json").read_text(encoding="utf-8"))
    assert gate["status"] == "skipped"
    assert gate["reason"] == "no_mutation_targets"
    assert verification["mutation"]["status"] == "not-run"
    assert verification["mutation"]["receipt_path"].endswith(f"mutation-gate-{run_id}.json")
    assert verification["status"] == "passed"
    schema = json.loads((PACKAGE / "schemas" / "verification-result.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(verification)


def test_mutation_gate_blocks_failed_explicit_module(monkeypatch, tmp_path):
    run_id = "run-fail"
    _write_active_task(tmp_path, run_id)
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("TERMINAL_ID", "term-1")
    monkeypatch.setenv("GO_MUTATION_MODULES", "pkg.critical")
    monkeypatch.setattr(
        MUTATION_GATE,
        "load_quality_gates",
        lambda: SimpleNamespace(
            get_module_gate=lambda module: SimpleNamespace(tier="critical"),
            list_critical_modules=lambda: ["pkg.critical"],
            block_pr_on_failure=True,
        ),
    )
    monkeypatch.setattr(
        MUTATION_GATE,
        "run_mutation_for_module",
        lambda module, project_root=None: SimpleNamespace(
            module=module,
            status="failed",
            target_score=80,
            mutation_score=50.0,
            killed=5,
            survived=5,
            skipped=0,
            timeout=0,
        ),
    )

    assert MUTATION_GATE.main([]) == 1

    gate = json.loads((tmp_path / f"mutation-gate-{run_id}.json").read_text(encoding="utf-8"))
    verification = json.loads((tmp_path / f"verification-result_{run_id}.json").read_text(encoding="utf-8"))
    blocked = json.loads((tmp_path / f"blocked_{run_id}.json").read_text(encoding="utf-8"))
    assert gate["status"] == "failed"
    assert gate["modules"][0]["module"] == "pkg.critical"
    assert verification["mutation"]["status"] == "failed"
    assert verification["mutation"]["receipt_path"].endswith(f"mutation-gate-{run_id}.json")
    assert verification["status"] == "failed"
    assert blocked["reason_code"] == "mutation_failed"
    assert (tmp_path / f".blocked_{run_id}").exists()
