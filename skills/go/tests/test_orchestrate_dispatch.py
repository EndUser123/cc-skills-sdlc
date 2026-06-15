#!/usr/bin/env python3
"""Tests for the canonical /go dispatch contract."""

import importlib.util
import json
import pathlib
import subprocess
import sys


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
_ORCHESTRATE = _load_module("go_orchestrate", PACKAGE / "scripts" / "orchestrate.py")


def test_default_dispatch_is_pi(monkeypatch):
    monkeypatch.delenv("GO_DISPATCH", raising=False)

    args = _ORCHESTRATE.parse_args([])

    assert args.dispatch == "pi"


def test_env_dispatch_is_fallback(monkeypatch):
    monkeypatch.setenv("GO_DISPATCH", "claude")

    args = _ORCHESTRATE.parse_args([])

    assert args.dispatch == "claude"


def test_cli_dispatch_overrides_env(monkeypatch):
    monkeypatch.setenv("GO_DISPATCH", "claude")

    args = _ORCHESTRATE.parse_args(["--dispatch", "pi"])

    assert args.dispatch == "pi"


def test_invalid_env_dispatch_falls_back_to_pi(monkeypatch):
    monkeypatch.setenv("GO_DISPATCH", "invalid")

    args = _ORCHESTRATE.parse_args([])

    assert args.dispatch == "pi"


def test_script_path_resolves_inside_go_skill():
    select_task = _ORCHESTRATE.script_path("scripts", "select-task.py")
    resolve_model = _ORCHESTRATE.script_path("scripts", "adapters", "pi", "resolve_model.py")

    assert select_task.exists()
    assert resolve_model.exists()
    assert select_task.parts[-3:] == ("go", "scripts", "select-task.py")
    assert resolve_model.parts[-5:] == ("go", "scripts", "adapters", "pi", "resolve_model.py")


def test_common_tail_runs_simplify_before_review_and_qa(monkeypatch, tmp_path):
    calls = []

    def fake_run_script(script, args, state_dir, run_id):
        calls.append(pathlib.Path(script).name)
        return 0

    def fake_subprocess_run(command, **kwargs):
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 0, stdout=" src/app.py | 2 +\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(_ORCHESTRATE, "run_script", fake_run_script)
    monkeypatch.setattr(_ORCHESTRATE.subprocess, "run", fake_subprocess_run)

    assert _ORCHESTRATE.run_common_tail(tmp_path, tmp_path, "run1") is True
    assert calls == [
        "verify-task.py",
        "validate_go_contracts.py",
        "review-passes.py",
        "run-qa-verification.py",
        "pr-artifacts.py",
        "loop-check.py",
    ]


def test_create_worktree_blocks_when_git_worktree_add_fails(monkeypatch, tmp_path):
    def fake_subprocess_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 128, stdout="", stderr="fatal: branch exists")

    monkeypatch.setattr(_ORCHESTRATE.subprocess, "run", fake_subprocess_run)

    try:
        _ORCHESTRATE.create_worktree("pi", tmp_path, "run1")
        assert False, "Expected worktree creation failure"
    except RuntimeError as exc:
        assert "git worktree add failed" in str(exc)


def test_ensure_runtime_env_generates_nonconstant_run_id(monkeypatch):
    monkeypatch.delenv("RUN_ID", raising=False)
    monkeypatch.delenv("GO_RUN_ID", raising=False)
    monkeypatch.delenv("GO_STATE_DIR", raising=False)
    monkeypatch.setenv("TERMINAL_ID", "test-terminal")

    _, run_id = _ORCHESTRATE.ensure_runtime_env("pi")

    assert run_id
    assert run_id != "run"
    assert len(run_id) >= 8


def test_orchestrate_returns_blocked_when_worktree_creation_fails(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--prompt", "do work"])

    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "run1")

    def fail_worktree(dispatch, state_dir, run_id):
        raise RuntimeError("git worktree add failed")

    monkeypatch.setattr(_ORCHESTRATE, "create_worktree", fail_worktree)

    assert _ORCHESTRATE.orchestrate(args) == "<promise>BLOCKED</promise>"


def test_orchestrate_claude_dispatch_blocks_without_worker(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--dispatch", "claude", "--prompt", "do work"])

    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "run-claude")
    monkeypatch.setattr(_ORCHESTRATE, "create_worktree", lambda dispatch, state_dir, run_id: tmp_path / "worker")

    assert _ORCHESTRATE.orchestrate(args) == "<promise>BLOCKED</promise>"

    result = json.loads((tmp_path / "dispatch-result_run-claude.json").read_text(encoding="utf-8"))
    assert result["dispatch"] == "claude"
    assert result["status"] == "unsupported-automated-dispatch"
    assert not (tmp_path / ".dispatched_run-claude").exists()


def test_orchestrate_local_dispatch_skips_worktree_and_worker(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--dispatch", "local", "--prompt", "verify only"])
    calls = []

    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "run-local")

    def fail_worktree(dispatch, state_dir, run_id):
        raise AssertionError("local dispatch must not create a worktree")

    def fake_run_common_tail(worktree, state_dir, run_id):
        calls.append((worktree, state_dir, run_id))
        return True

    monkeypatch.setattr(_ORCHESTRATE, "create_worktree", fail_worktree)
    monkeypatch.setattr(_ORCHESTRATE, "run_common_tail", fake_run_common_tail)

    assert _ORCHESTRATE.orchestrate(args) == "<promise>PR_READY</promise>"
    assert calls == [(pathlib.Path.cwd(), tmp_path, "run-local")]

    result = json.loads((tmp_path / "dispatch-result_run-local.json").read_text(encoding="utf-8"))
    assert result["dispatch"] == "local"
    assert result["status"] == "skipped-worker"
