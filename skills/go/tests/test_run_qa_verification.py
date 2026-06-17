#!/usr/bin/env python3
"""Tests for /go QA verification bridge."""

import importlib.util
import json
import pathlib
import sys


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
RUN_QA = _load_module("go_run_qa_verification", PACKAGE / "scripts" / "run-qa-verification.py")


def test_default_skills_analysis_root_points_to_marketplace_plugin(monkeypatch):
    monkeypatch.delenv("SKILLS_ANALYSIS_ROOT", raising=False)
    fake_plugin = pathlib.Path("P:/tmp/plugins/cc-skills-sdlc/skills/go/scripts/run-qa-verification.py")
    fake_analysis = pathlib.Path("P:/tmp/plugins/cc-skills-analysis")
    monkeypatch.setattr(RUN_QA, "__file__", str(fake_plugin))
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: self == fake_analysis / "skills" / "gto" / "orchestrator.py")

    root = RUN_QA.resolve_skills_analysis_root()

    assert root.name == "cc-skills-analysis"
    assert root == fake_analysis


def test_import_gto_uses_resolved_root(monkeypatch, tmp_path):
    root = tmp_path / "cc-skills-analysis"
    gto = root / "skills" / "gto"
    agents = gto / "agents"
    agents.mkdir(parents=True)
    (gto / "orchestrator.py").write_text("def run(argv):\n    return 0\n", encoding="utf-8")
    (agents / "_quality_gates.py").write_text("def apply_quality_gates(*args, **kwargs):\n    return []\n", encoding="utf-8")
    monkeypatch.setenv("SKILLS_ANALYSIS_ROOT", str(root))
    for name in ["skills.gto.orchestrator", "skills.gto.agents._quality_gates"]:
        sys.modules.pop(name, None)

    gto_run, apply_gates = RUN_QA._import_gto()

    assert callable(gto_run)
    assert callable(apply_gates)


def test_should_skip_qa_for_design_and_planning_tasks(tmp_path):
    for task_type in ["design", "planning"]:
        run_id = f"run-{task_type}"
        (tmp_path / f"active-task_{run_id}.json").write_text(
            json.dumps({"task": {"task_type": task_type}}) + "\n",
            encoding="utf-8",
        )

        assert RUN_QA.should_skip_qa(tmp_path, run_id) is True


def test_should_not_skip_qa_for_missing_or_implementation_task(tmp_path):
    run_id = "run-impl"
    (tmp_path / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"task_type": "implementation"}}) + "\n",
        encoding="utf-8",
    )

    assert RUN_QA.should_skip_qa(tmp_path, run_id) is False
    assert RUN_QA.should_skip_qa(tmp_path, "missing") is False


def test_should_skip_qa_returns_false_for_malformed_task_json(tmp_path):
    run_id = "run-bad-json"
    (tmp_path / f"active-task_{run_id}.json").write_text("{bad json\n", encoding="utf-8")

    assert RUN_QA.should_skip_qa(tmp_path, run_id) is False


def test_map_findings_to_qa_status_ignores_resolved_high_findings():
    status, summary, gates = RUN_QA.map_findings_to_qa_status(
        [{"severity": "high", "status": "resolved", "metadata": {"escape_hatch": True}}]
    )

    assert status == "accept"
    assert summary == "accept"
    assert gates == {
        "escape_hatches": 0,
        "unverified_implementation_claims": 0,
        "mixed_substance": 0,
    }


def test_map_findings_to_qa_status_redo_on_unresolved_high():
    status, summary, gates = RUN_QA.map_findings_to_qa_status(
        [{"severity": "high", "status": "open", "metadata": {}}]
    )

    assert status == "redo"
    assert summary == "critical/high unresolved findings"
    assert gates["escape_hatches"] == 0


def test_map_findings_to_qa_status_accept_with_concerns_for_gate_metadata():
    status, summary, gates = RUN_QA.map_findings_to_qa_status(
        [
            {"severity": "medium", "status": "open", "metadata": {"escape_hatch": True}},
            {"severity": "low", "status": "open", "metadata": {"mixed_substance": True}},
            {"severity": "low", "status": "open", "metadata": {"unverified_implementation_claim": True}},
        ]
    )

    assert status == "accept-with-concerns"
    assert "accept-with-concerns" in summary
    assert gates == {
        "escape_hatches": 1,
        "unverified_implementation_claims": 1,
        "mixed_substance": 1,
    }


def test_run_dry_run_writes_accept_verdict(monkeypatch, tmp_path):
    monkeypatch.setattr(RUN_QA, "RUN_ID", "run-dry")
    monkeypatch.setattr(RUN_QA, "GO_STATE_DIR", tmp_path)

    assert RUN_QA.run(["--dry-run"]) == 0

    verdict = json.loads((tmp_path / "qa-verdict-run-dry.json").read_text(encoding="utf-8"))
    assert verdict["qa_status"] == "accept"
    assert verdict["summary"] == "dry-run mode"


def test_run_skips_design_task_before_importing_gto(monkeypatch, tmp_path):
    run_id = "run-design"
    monkeypatch.setattr(RUN_QA, "RUN_ID", run_id)
    monkeypatch.setattr(RUN_QA, "GO_STATE_DIR", tmp_path)
    (tmp_path / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"task_type": "design"}}) + "\n",
        encoding="utf-8",
    )

    def fail_import():
        raise AssertionError("skip path must not import GTO")

    monkeypatch.setattr(RUN_QA, "_import_gto", fail_import)

    assert RUN_QA.run([]) == 0
    verdict = json.loads((tmp_path / f"qa-verdict-{run_id}.json").read_text(encoding="utf-8"))
    assert verdict["qa_status"] == "skipped"
    assert verdict["task_type_skipped"] is True


def test_run_writes_error_verdict_when_gto_import_fails(monkeypatch, tmp_path):
    run_id = "run-import-fail"
    monkeypatch.setattr(RUN_QA, "RUN_ID", run_id)
    monkeypatch.setattr(RUN_QA, "GO_STATE_DIR", tmp_path)
    monkeypatch.setattr(RUN_QA, "_import_gto", lambda: (_ for _ in ()).throw(ImportError("missing gto")))

    assert RUN_QA.run([]) == 1

    verdict = json.loads((tmp_path / f"qa-verdict-{run_id}.json").read_text(encoding="utf-8"))
    assert verdict["qa_status"] == "error"
    assert "missing gto" in verdict["summary"]


def test_run_writes_error_verdict_when_gto_raises(monkeypatch, tmp_path):
    run_id = "run-gto-raises"
    monkeypatch.setattr(RUN_QA, "RUN_ID", run_id)
    monkeypatch.setattr(RUN_QA, "GO_STATE_DIR", tmp_path)

    def raise_gto(argv):
        raise RuntimeError("gto exploded")

    monkeypatch.setattr(RUN_QA, "_import_gto", lambda: (raise_gto, lambda *args, **kwargs: []))

    assert RUN_QA.run([]) == 1

    verdict = json.loads((tmp_path / f"qa-verdict-{run_id}.json").read_text(encoding="utf-8"))
    assert verdict["qa_status"] == "error"
    assert "gto exploded" in verdict["summary"]


def test_run_writes_error_verdict_when_gto_artifact_missing(monkeypatch, tmp_path):
    run_id = "run-missing-artifact"
    monkeypatch.setattr(RUN_QA, "RUN_ID", run_id)
    monkeypatch.setattr(RUN_QA, "TERMINAL_ID", "term-missing")
    monkeypatch.setattr(RUN_QA, "SESSION_ID", "session")
    monkeypatch.setattr(RUN_QA, "GO_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(RUN_QA, "SKILLS_ANALYSIS", tmp_path / "analysis")
    monkeypatch.setenv("CLAUDE_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(RUN_QA, "_import_gto", lambda: (lambda argv: 0, lambda *args, **kwargs: []))

    assert RUN_QA.run([]) == 1

    verdict = json.loads((tmp_path / "state" / f"qa-verdict-{run_id}.json").read_text(encoding="utf-8"))
    assert verdict["qa_status"] == "error"
    assert "no artifact produced" in verdict["summary"]


def test_run_writes_error_verdict_when_gto_artifact_is_malformed(monkeypatch, tmp_path):
    run_id = "run-bad-artifact"
    terminal_id = "term-bad-artifact"
    artifacts_root = tmp_path / "artifacts"
    artifact_path = artifacts_root / terminal_id / "gto" / "outputs" / "artifact.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("{bad json\n", encoding="utf-8")
    monkeypatch.setattr(RUN_QA, "RUN_ID", run_id)
    monkeypatch.setattr(RUN_QA, "TERMINAL_ID", terminal_id)
    monkeypatch.setattr(RUN_QA, "SESSION_ID", "session")
    monkeypatch.setattr(RUN_QA, "GO_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(RUN_QA, "SKILLS_ANALYSIS", tmp_path / "analysis")
    monkeypatch.setenv("CLAUDE_ARTIFACTS_ROOT", str(artifacts_root))
    monkeypatch.setattr(RUN_QA, "_import_gto", lambda: (lambda argv: 0, lambda *args, **kwargs: []))

    assert RUN_QA.run([]) == 1

    verdict = json.loads((tmp_path / "state" / f"qa-verdict-{run_id}.json").read_text(encoding="utf-8"))
    assert verdict["qa_status"] == "error"
    assert "unparseable artifact" in verdict["summary"]


def test_run_maps_gto_artifact_to_verdict(monkeypatch, tmp_path):
    run_id = "run-gto"
    terminal_id = "term-gto"
    artifacts_root = tmp_path / "artifacts"
    artifact_path = artifacts_root / terminal_id / "gto" / "outputs" / "artifact.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "severity": "low",
                        "status": "open",
                        "metadata": {"unverified_implementation_claim": True},
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(RUN_QA, "RUN_ID", run_id)
    monkeypatch.setattr(RUN_QA, "TERMINAL_ID", terminal_id)
    monkeypatch.setattr(RUN_QA, "SESSION_ID", "session")
    monkeypatch.setattr(RUN_QA, "GO_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(RUN_QA, "SKILLS_ANALYSIS", tmp_path / "analysis")
    monkeypatch.setenv("CLAUDE_ARTIFACTS_ROOT", str(artifacts_root))
    monkeypatch.setattr(RUN_QA, "_import_gto", lambda: (lambda argv: 0, lambda *args, **kwargs: []))

    assert RUN_QA.run([]) == 0

    verdict = json.loads((tmp_path / "state" / f"qa-verdict-{run_id}.json").read_text(encoding="utf-8"))
    assert verdict["qa_status"] == "accept-with-concerns"
    assert verdict["source"]["gto"]["findings_total"] == 1
