#!/usr/bin/env python3
"""Tests for go-pi orchestrate.py."""
import importlib.util, json, pathlib, sys


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PACKAGE = pathlib.Path("P:/packages/cc-skills-sdlc/skills/go-pi")
_ORCHESTRATE = _load_module("orchestrate", PACKAGE / "scripts" / "orchestrate.py")


TaskContract = _ORCHESTRATE.TaskContract
PiModelInfo = _ORCHESTRATE.PiModelInfo
TranscriptVerdict = _ORCHESTRATE.TranscriptVerdict
phase_marker = _ORCHESTRATE.phase_marker


class TestTaskContract:
    def test_from_active_task_minimal(self):
        data = {"task": {"id": "t1", "title": "Test", "objective": "Do it"}}
        tc = TaskContract.from_active_task(data)
        assert tc.task_id == "t1"
        assert tc.title == "Test"
        assert tc.source == "unknown"

    def test_from_active_task_full(self):
        data = {
            "run_id": "abc",
            "source": "cli",
            "task": {
                "id": "t2",
                "title": "Full task",
                "objective": "Do it well",
                "scope_in": ["src/"],
                "scope_out": ["test/"],
                "acceptance_criteria": ["works"],
                "verification_commands": ["pytest"],
                "forbidden_files": ["secrets.py"],
            },
        }
        tc = TaskContract.from_active_task(data)
        assert tc.task_id == "t2"
        assert tc.scope_in == ["src/"]
        assert tc.verification_commands == ["pytest"]
        assert tc.forbidden_files == ["secrets.py"]


class TestPiModelInfo:
    def test_load(self, tmp_path):
        p = tmp_path / "pi-model_rundata.json"
        p.write_text(json.dumps({
            "classifier_model": "M27",
            "tier": "fast",
            "pi_model": "minimax/MiniMax-M2.7",
        }))
        info = PiModelInfo.load(p)
        assert info.pi_model == "minimax/MiniMax-M2.7"
        assert info.classifier_model == "M27"


class TestTranscriptVerdict:
    def test_from_subagent_json_pass(self):
        text = '{"verdict": "PASS", "reason": "done", "critical_issues": []}'
        v = TranscriptVerdict.from_subagent_json(text)
        assert v.verdict == "PASS"

    def test_from_subagent_json_fail(self):
        text = '{"verdict": "FAIL", "reason": "no files written", "critical_issues": ["NO_FILES_WRITTEN"]}'
        v = TranscriptVerdict.from_subagent_json(text)
        assert v.verdict == "FAIL"
        assert "NO_FILES_WRITTEN" in v.critical_issues


class TestPhaseMarker:
    def test_touch_creates_file(self, tmp_path):
        p = phase_marker(tmp_path, "verified", "run123")
        assert p.exists()
        assert p.name == ".verified_run123"


class TestOrchestrateModule:
    def test_orchestrate_module_exports(self):
        assert hasattr(_ORCHESTRATE, "TaskContract")
        assert hasattr(_ORCHESTRATE, "PiModelInfo")
        assert hasattr(_ORCHESTRATE, "TranscriptVerdict")
        assert hasattr(_ORCHESTRATE, "orchestrate")
        assert hasattr(_ORCHESTRATE, "main")