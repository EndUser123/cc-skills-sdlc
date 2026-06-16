#!/usr/bin/env python3
"""Tests for /go QA verification bridge."""

import importlib.util
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
