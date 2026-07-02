#!/usr/bin/env python3
"""Tests for the canonical /go dispatch contract."""

import importlib.util
import json
import os
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
_ROOT = PACKAGE.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from enforce.stop_gate import evaluate_gates, load_config_for_skill


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


def test_common_tail_records_skipped_simplify_before_review_and_qa(monkeypatch, tmp_path):
    calls = []

    def fake_run_script(script, args, state_dir, run_id, **kwargs):
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
        "review-passes.py",
        "run-qa-verification.py",
        "mutation-gate.py",
        "pr-artifacts.py",
        "loop-check.py",
    ]
    status = tmp_path.joinpath("simplify-status_run1.md").read_text()
    assert "SKIPPED" in status
    assert "GO_SIMPLIFY_COMMAND" in status


def test_common_tail_runs_configured_simplify_command(monkeypatch, tmp_path):
    calls = []
    commands = []

    def fake_run_script(script, args, state_dir, run_id, **kwargs):
        calls.append(pathlib.Path(script).name)
        return 0

    def fake_subprocess_run(command, **kwargs):
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 0, stdout=" src/app.py | 2 +\n", stderr="")
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="simplified\n", stderr="")

    monkeypatch.setenv("GO_SIMPLIFY_COMMAND", "python simplify.py")
    monkeypatch.setattr(_ORCHESTRATE, "run_script", fake_run_script)
    monkeypatch.setattr(_ORCHESTRATE.subprocess, "run", fake_subprocess_run)

    assert _ORCHESTRATE.run_common_tail(tmp_path, tmp_path, "run1") is True
    assert commands == ["python simplify.py"]
    assert calls == [
        "verify-task.py",
        "review-passes.py",
        "run-qa-verification.py",
        "mutation-gate.py",
        "pr-artifacts.py",
        "loop-check.py",
    ]
    status = tmp_path.joinpath("simplify-status_run1.md").read_text()
    assert "PASS" in status
    assert "python simplify.py" in status


def test_common_tail_blocks_when_git_diff_fails(monkeypatch, tmp_path):
    def fake_run_script(script, args, state_dir, run_id, **kwargs):
        return 0

    def fake_subprocess_run(command, **kwargs):
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 128, stdout="", stderr="fatal: not a git repo")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(_ORCHESTRATE, "run_script", fake_run_script)
    monkeypatch.setattr(_ORCHESTRATE.subprocess, "run", fake_subprocess_run)

    assert _ORCHESTRATE.run_common_tail(tmp_path, tmp_path, "run-diff-fail") is False


def test_create_worktree_blocks_when_git_worktree_add_fails(monkeypatch, tmp_path):
    def fake_subprocess_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 128, stdout="", stderr="fatal: branch exists")

    monkeypatch.setattr(_ORCHESTRATE.subprocess, "run", fake_subprocess_run)

    try:
        _ORCHESTRATE.create_worktree("pi", tmp_path, "run1")
        assert False, "Expected worktree creation failure"
    except RuntimeError as exc:
        assert "git worktree add failed" in str(exc)


def test_create_worktree_names_include_run_id_suffix(monkeypatch, tmp_path):
    captured = {}

    def fake_subprocess_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(_ORCHESTRATE.subprocess, "run", fake_subprocess_run)

    worktree = _ORCHESTRATE.create_worktree("pi", tmp_path, "run-abcdef123456")

    assert "abcdef12" in str(worktree)
    assert "abcdef12" in captured["command"][4]
    assert "abcdef12" in captured["command"][5]


def test_ensure_runtime_env_generates_nonconstant_run_id(monkeypatch):
    monkeypatch.delenv("RUN_ID", raising=False)
    monkeypatch.delenv("GO_RUN_ID", raising=False)
    monkeypatch.delenv("GO_STATE_DIR", raising=False)
    monkeypatch.setenv("TERMINAL_ID", "test-terminal")

    _, run_id = _ORCHESTRATE.ensure_runtime_env("pi")

    assert run_id
    assert run_id != "run"
    assert len(run_id) >= 8
    assert pathlib.Path(_ORCHESTRATE.os.environ["GO_STATE_DIR"]).is_absolute()


def test_prompt_task_gets_default_verification_command(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--prompt", "fix parser"])
    monkeypatch.setenv("GO_DEFAULT_VERIFICATION_COMMANDS", "python -m pytest -q;ruff check .")

    task = _ORCHESTRATE.load_or_create_task(args, tmp_path, "run-verify")

    assert task is not None
    active = json.loads((tmp_path / "active-task_run-verify.json").read_text(encoding="utf-8"))
    assert active["task"]["verification_commands"] == ["python -m pytest -q", "ruff check ."]


def test_tasks_argument_is_used_for_queue_selection(monkeypatch, tmp_path):
    tasks_file = tmp_path / "custom-tasks.json"
    tasks_file.write_text(
        json.dumps(
            {
                "version": "1.0",
                "tasks": [
                    {
                        "id": "CUSTOM-1",
                        "title": "Custom queue task",
                        "objective": "Use the custom task file",
                        "status": "ready",
                        "priority": "P1",
                        "scope_in": ["src/custom.py"],
                        "scope_out": [],
                        "forbidden_files": [],
                        "acceptance_criteria": ["custom queue used"],
                        "verification_commands": ["python -m pytest tests/test_custom.py"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    args = _ORCHESTRATE.parse_args(["--tasks", str(tasks_file)])
    monkeypatch.delenv("GO_TASKS_FILE", raising=False)
    monkeypatch.setenv("TERMINAL_ID", "test-terminal")

    task = _ORCHESTRATE.load_or_create_task(args, tmp_path, "run-custom-tasks")

    assert task is not None
    assert task.task_id == "CUSTOM-1"
    active = json.loads((tmp_path / "active-task_run-custom-tasks.json").read_text(encoding="utf-8"))
    assert active["source_ref"] == str(tasks_file.resolve())


def test_plan_argument_creates_task_from_plan_file(monkeypatch, tmp_path):
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(
        "# Harden parser\n\n- Add regression coverage\n- Verify with `python -m pytest skills/go/tests -q`\n",
        encoding="utf-8",
    )
    args = _ORCHESTRATE.parse_args(["--plan", str(plan_file)])
    monkeypatch.setenv("GO_DEFAULT_VERIFICATION_COMMANDS", "python -m pytest skills/go/tests -q")

    task = _ORCHESTRATE.load_or_create_task(args, tmp_path, "run-plan")

    assert task is not None
    assert task.task_id == "plan-run-plan"
    assert task.title == "Harden parser"
    assert task.source == "plan-md"
    assert task.scope_in == []
    assert task.verification_commands == ["python -m pytest skills/go/tests -q"]
    active = json.loads((tmp_path / "active-task_run-plan.json").read_text(encoding="utf-8"))
    assert active["source_ref"] == str(plan_file.resolve())


def test_prompt_task_can_require_explicit_verification(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--prompt", "fix parser"])
    monkeypatch.delenv("GO_DEFAULT_VERIFICATION_COMMANDS", raising=False)
    monkeypatch.setenv("GO_REQUIRE_EXPLICIT_VERIFICATION", "1")

    task = _ORCHESTRATE.load_or_create_task(args, tmp_path, "run-missing-verify")

    assert task is None
    blocked = json.loads((tmp_path / "blocked_run-missing-verify.json").read_text(encoding="utf-8"))
    assert blocked["reason_code"] == "missing_verification_commands"


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

    def fail_worktree(dispatch, state_dir, run_id):
        raise AssertionError("unsupported claude dispatch must not create a worktree")

    monkeypatch.setattr(_ORCHESTRATE, "create_worktree", fail_worktree)

    assert _ORCHESTRATE.orchestrate(args) == "<promise>BLOCKED</promise>"

    result = json.loads((tmp_path / "dispatch-result_run-claude.json").read_text(encoding="utf-8"))
    assert result["dispatch"] == "claude"
    assert result["status"] == "unsupported-automated-dispatch"
    assert not (tmp_path / ".dispatched_run-claude").exists()


def test_dispatch_claude_writes_blocked_contract(tmp_path):
    assert _ORCHESTRATE.dispatch_claude(tmp_path, "run-claude-helper") is False

    result = json.loads((tmp_path / "dispatch-result_run-claude-helper.json").read_text(encoding="utf-8"))
    assert result == {
        "dispatch": "claude",
        "status": "unsupported-automated-dispatch",
        "reason": "Claude dispatch has no non-interactive worker implementation in this orchestrator.",
    }
    assert (tmp_path / ".blocked_run-claude-helper").exists()


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
    assert (tmp_path / ".worktree-ready_run-local").exists()
    assert (tmp_path / ".coded_run-local").exists()
    assert (tmp_path / ".task-selected_run-local").exists()


def test_run_script_passes_absolute_state_env_and_worktree_cwd(monkeypatch, tmp_path):
    captured = {}
    script = tmp_path / "helper.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(_ORCHESTRATE.subprocess, "run", fake_run)

    rc = _ORCHESTRATE.run_script(script, [], tmp_path, "run-env", cwd=worktree)

    assert rc == 0
    assert captured["cwd"] == worktree
    assert captured["env"]["RUN_ID"] == "run-env"
    assert captured["env"]["GO_STATE_DIR"] == str(tmp_path.resolve())
    assert captured["env"]["WORKTREE"] == str(worktree.resolve())


def test_common_tail_passes_qa_dry_run_when_requested(monkeypatch, tmp_path):
    qa_args = None

    def fake_run_script(script, args, state_dir, run_id, **kwargs):
        nonlocal qa_args
        name = pathlib.Path(script).name
        if name == "run-qa-verification.py":
            qa_args = args
        return 0

    monkeypatch.setenv("GO_QA_DRY_RUN", "1")
    monkeypatch.setattr(_ORCHESTRATE, "run_script", fake_run_script)
    monkeypatch.setattr(
        _ORCHESTRATE.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    assert _ORCHESTRATE.run_common_tail(tmp_path, tmp_path, "run-qa-dry") is True
    assert qa_args == ["--dry-run"]


def test_common_tail_runs_mutation_gate_before_pr_artifacts(monkeypatch, tmp_path):
    calls = []

    def fake_run_script(script, args, state_dir, run_id, **kwargs):
        calls.append(pathlib.Path(script).name)
        if pathlib.Path(script).name == "mutation-gate.py":
            (state_dir / f"mutation-gate-{run_id}.json").write_text(
                json.dumps({"status": "skipped"}) + "\n",
                encoding="utf-8",
            )
        return 0

    monkeypatch.setattr(_ORCHESTRATE, "run_script", fake_run_script)
    monkeypatch.setattr(
        _ORCHESTRATE.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    assert _ORCHESTRATE.run_common_tail(tmp_path, tmp_path, "run-mutation") is True
    assert calls.index("mutation-gate.py") < calls.index("pr-artifacts.py")
    assert (tmp_path / ".mutation-passed_run-mutation").exists()


def test_common_tail_blocks_when_mutation_gate_fails(monkeypatch, tmp_path):
    calls = []

    def fake_run_script(script, args, state_dir, run_id, **kwargs):
        name = pathlib.Path(script).name
        calls.append(name)
        if name == "mutation-gate.py":
            return 1
        return 0

    monkeypatch.setattr(_ORCHESTRATE, "run_script", fake_run_script)
    monkeypatch.setattr(
        _ORCHESTRATE.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    assert _ORCHESTRATE.run_common_tail(tmp_path, tmp_path, "run-mutation-fail") is False
    assert "pr-artifacts.py" not in calls


def test_loop_check_skips_when_tasks_file_missing(tmp_path):
    script = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "loop-check.py"
    env = os.environ.copy()
    env.pop("GO_TASKS_FILE", None)
    env["GO_STATE_DIR"] = str(tmp_path)
    env["RUN_ID"] = "run-loop"

    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "ALL_TASKS_COMPLETE" in result.stdout
    assert "Traceback" not in result.stderr


def test_local_dispatch_outputs_satisfy_stop_gate(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--dispatch", "local", "--prompt", "verify config"])
    run_id = "run-local-stop"

    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("TERMINAL_ID", "test-local-stop")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "test-local-stop")

    def fake_run_script(script, args, state_dir, current_run_id, **kwargs):
        name = pathlib.Path(script).name
        if name == "verify-task.py":
            (state_dir / f"verification-summary_{current_run_id}.json").write_text(
                json.dumps({"verified": True}) + "\n",
                encoding="utf-8",
            )
        elif name == "run-qa-verification.py":
            (state_dir / f"qa-verdict-{current_run_id}.json").write_text(
                json.dumps({"qa_status": "skipped"}) + "\n",
                encoding="utf-8",
            )
        elif name == "pr-artifacts.py":
            (state_dir / f"task-result_{current_run_id}.json").write_text(
                json.dumps({"status": "pr_ready"}) + "\n",
                encoding="utf-8",
            )
            (state_dir / f"pr-title_{current_run_id}.txt").write_text("Title\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(_ORCHESTRATE, "run_script", fake_run_script)
    monkeypatch.setattr(
        _ORCHESTRATE.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    assert _ORCHESTRATE.orchestrate(args) == "<promise>PR_READY</promise>"

    env = {
        "RUN_ID": run_id,
        "CLAUDE_TERMINAL_ID": "test-local-stop",
        "GO_STATE_DIR": str(tmp_path),
    }
    exit_code, message = evaluate_gates("go", load_config_for_skill("go"), env)

    assert exit_code == 0
    assert message == ""


# ---------------------------------------------------------------------------
# --preflight-only: proposal-only mode (phase 1, reversible)
# ---------------------------------------------------------------------------


def test_preflight_only_writes_proposal_and_marker(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--preflight-only", "--prompt", "fix the parser to handle None in foo.py"])
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "run-pf-ok")
    monkeypatch.setenv("TERMINAL_ID", "tid-pf")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "tid-pf")

    summary = _ORCHESTRATE.orchestrate(args)

    assert "preflight OK" in summary
    proposal = json.loads((tmp_path / "task-proposal_run-pf-ok.json").read_text(encoding="utf-8"))
    assert proposal["runid"] == "run-pf-ok"
    # run_context.canonical_terminal_id_from_env() prefixes non-'console_' values,
    # so the env-set plain id gets normalized to "console_tid-pf".
    assert proposal["terminalid"] == "console_tid-pf"
    assert proposal["source"] == "cli-preflight"
    assert proposal["originalPrompt"] == "fix the parser to handle None in foo.py"
    # rewrite strips the politeness prefix; originalPrompt keeps it for the audit trail.
    assert "parser" in proposal["rewrittenGoal"]
    assert proposal["suggestedDispatch"] in ("pi", "local", "claude")
    assert isinstance(proposal["localEligible"], bool)
    assert isinstance(proposal["requiresApproval"], bool)
    assert isinstance(proposal["verificationSuggestions"], list)
    assert (tmp_path / ".preflight-proposed_run-pf-ok").exists()
    # main() honors the preflight exit-code carrier; success path stays 0.
    assert _ORCHESTRATE._preflight_exit_code == 0


def test_preflight_only_does_not_write_active_task_or_dispatch(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--preflight-only", "--prompt", "fix parser"])
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "run-pf-side")
    monkeypatch.setenv("TERMINAL_ID", "tid-side")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "tid-side")

    # Fail loudly if any dispatch / common-tail path is touched.
    def forbid(*_args, **_kwargs):
        raise AssertionError("preflight-only must not call load_or_create_task / dispatch / common-tail")

    monkeypatch.setattr(_ORCHESTRATE, "load_or_create_task", forbid)
    monkeypatch.setattr(_ORCHESTRATE, "create_worktree", forbid)
    monkeypatch.setattr(_ORCHESTRATE, "dispatch_local", forbid)
    monkeypatch.setattr(_ORCHESTRATE, "dispatch_claude", forbid)
    monkeypatch.setattr(_ORCHESTRATE, "run_common_tail", forbid)

    _ORCHESTRATE.orchestrate(args)

    # active-task must NOT exist (the whole point of preflight).
    assert not list(tmp_path.glob("active-task_*.json"))
    # No dispatch / common-tail markers.
    assert not (tmp_path / ".dispatched_run-pf-side").exists()
    assert not (tmp_path / ".coded_run-pf-side").exists()
    assert not (tmp_path / ".verified_run-pf-side").exists()
    assert not (tmp_path / ".qa-passed_run-pf-side").exists()
    # The proposal + phase marker ARE written (proves preflight ran).
    assert (tmp_path / "task-proposal_run-pf-side.json").exists()
    assert (tmp_path / ".preflight-proposed_run-pf-side").exists()


def test_preflight_only_without_prompt_blocks_with_sentinel(monkeypatch, tmp_path):
    args = _ORCHESTRATE.parse_args(["--preflight-only"])
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "run-pf-miss")
    monkeypatch.setenv("TERMINAL_ID", "tid-miss")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "tid-miss")

    summary = _ORCHESTRATE.orchestrate(args)

    assert "BLOCKED" in summary
    assert "missing --prompt" in summary
    blocked = json.loads((tmp_path / "blocked_preflight_run-pf-miss.json").read_text(encoding="utf-8"))
    assert blocked["reason_code"] == "missing_prompt"
    assert (tmp_path / ".preflight-failed_run-pf-miss").exists()
    # No proposal was written.
    assert not (tmp_path / "task-proposal_run-pf-miss.json").exists()
    # Exit-code carrier set to non-zero (so main() returns 2).
    assert _ORCHESTRATE._preflight_exit_code == _ORCHESTRATE._PREFLIGHT_FAIL_RC == 2


def test_preflight_only_is_terminal_and_run_scoped(monkeypatch, tmp_path):
    """Two preflight invocations under different RUN_IDs write distinct artifacts."""
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("TERMINAL_ID", "tid-scope")
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "tid-scope")

    for i, rid in enumerate(("run-A", "run-B")):
        monkeypatch.setenv("RUN_ID", rid)
        args = _ORCHESTRATE.parse_args(["--preflight-only", "--prompt", f"task {i}"])
        _ORCHESTRATE.orchestrate(args)
        assert (tmp_path / f"task-proposal_{rid}.json").exists()
        assert (tmp_path / f".preflight-proposed_{rid}").exists()

    # No cross-contamination: each proposal's runid matches its invocation.
    a = json.loads((tmp_path / "task-proposal_run-A.json").read_text(encoding="utf-8"))
    b = json.loads((tmp_path / "task-proposal_run-B.json").read_text(encoding="utf-8"))
    assert a["runid"] == "run-A" and b["runid"] == "run-B"


def test_non_preflight_prompt_path_unchanged(monkeypatch, tmp_path):
    """Sanity: omitting --preflight-only still goes through the normal flow."""
    args = _ORCHESTRATE.parse_args(["--dispatch", "local", "--prompt", "verify only"])
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("RUN_ID", "run-normal")

    def fail_worktree(dispatch, state_dir, run_id):
        raise AssertionError("local dispatch must not create a worktree")

    tail_calls: list[str] = []

    def fake_tail(worktree, state_dir, run_id):
        tail_calls.append(run_id)
        return True

    monkeypatch.setattr(_ORCHESTRATE, "create_worktree", fail_worktree)
    monkeypatch.setattr(_ORCHESTRATE, "run_common_tail", fake_tail)

    assert _ORCHESTRATE.orchestrate(args) == "<promise>PR_READY</promise>"
    assert tail_calls == ["run-normal"]
    # Preflight artifacts must NOT exist (normal path).
    assert not (tmp_path / "task-proposal_run-normal.json").exists()
    assert not (tmp_path / ".preflight-proposed_run-normal").exists()
