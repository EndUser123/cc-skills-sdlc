"""Tests for delegation mutation-authority enforcement (goal req. 1-6).

Layer map:
  - unit: gate decision logic over synthetic payloads + state-dir fixtures
    (tests/test_delegation_enforce.py::TestGateDecision), harness branch guard
    (TestHarnessBranchGuard). Proves the policy->decision transform.
  - direct invocation (TestDirectInvocation): runs the hook as a real
    subprocess with a real state-dir fixture and a real session pointer. This
    is the boundary proof — proves the hook reads stdin, resolves the pointer,
    reads the proposal, and emits the correct deny JSON shape / silent allow.
    A unit test cannot fake success at this boundary.
  - what neither layer proves: that CC actually fires the frontmatter-registered
    hook on every tool call during a live /go session. That is a CC loader
    concern; the frontmatter wiring is verified by grep, and a live /reload
    + manual Edit attempt is the final acceptance step (documented in the
    report).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parent.parent / "hooks"
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_HOOKS))
sys.path.insert(0, str(_SCRIPTS))

import go_delegation_enforce_PreToolUse as gate  # noqa: E402
from adapters.pi import harness as pi_harness  # noqa: E402

HOOK = _HOOKS / "go_delegation_enforce_PreToolUse.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _proposal(worker="claude_subagent", advisory="claude_subagent", scope=None):
    return {
        "run_id": "r1",
        "delegation_policy": {
            "worker": worker,
            "advisory_reviewer": advisory,
            "worker_scope": scope or [],
            "worker_enforcement": "path-bound" if scope else "type-bound",
        },
    }


def _state(tmp_path, mode, proposal):
    state = tmp_path / "state"
    state.mkdir()
    (state / "task-proposal_r1.json").write_text(json.dumps(proposal), encoding="utf-8")
    if mode == "advisory":
        (state / ".delegation-advisory_r1").touch()
    elif mode == "worker":
        (state / ".delegation-worker_r1").touch()
    return state


def _wire(monkeypatch, state):
    """Bypass pointer resolution; point the gate straight at `state`."""
    monkeypatch.setattr(gate, "_read_pointer",
                        lambda sid: {"go_state_dir": str(state), "run_id": "r1"})
    monkeypatch.setattr(gate, "_resolve_state_dir",
                        lambda ptr: state if ptr else None)


def _decide(monkeypatch, capsys, state, payload):
    rc = gate._decide({**payload, "session_id": "s1"})
    out = capsys.readouterr().out.strip()
    return rc, out


# ---------------------------------------------------------------------------
# Unit: gate decision logic
# ---------------------------------------------------------------------------

class TestGateDecision:
    def test_advisory_edit_denied(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "advisory", _proposal())
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "src/x.py"}})
        assert rc == 0
        assert json.loads(out)["permissionDecision"] == "deny"
        assert "ADVISORY" in json.loads(out)["permissionDecisionReason"]

    def test_advisory_read_allowed_silent(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "advisory", _proposal())
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Read", "tool_input": {"file_path": "src/x.py"}})
        assert rc == 0 and out == ""

    def test_advisory_bash_shared_state_denied(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "advisory", _proposal())
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}})
        assert json.loads(out)["permissionDecision"] == "deny"

    def test_worker_in_scope_allowed(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "worker", _proposal(scope=["src/auth.py", "src/auth/"]))
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "src/auth/login.py"}})
        assert rc == 0 and out == ""  # silent allow

    def test_worker_out_of_scope_denied(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "worker", _proposal(scope=["src/auth.py"]))
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "src/other.py"}})
        assert json.loads(out)["permissionDecision"] == "deny"
        assert "worker_scope" in json.loads(out)["permissionDecisionReason"]

    def test_worker_type_bound_no_scope_allows_in_worktree(self, tmp_path, monkeypatch, capsys):
        # Empty scope -> type-bound: Edit allowed (no path claim), Bash shared-state still denied.
        state = _state(tmp_path, "worker", _proposal(scope=[]))
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "any.py"}})
        assert rc == 0 and out == ""

    def test_local_fast_bash_shared_state_denied(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "worker", _proposal(worker="local_fast"))
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Bash", "tool_input": {"command": "git commit -am x"}})
        assert json.loads(out)["permissionDecision"] == "deny"
        assert "local_fast" in json.loads(out)["permissionDecisionReason"]

    def test_pi_ccr_direct_edit_denied(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "worker", _proposal(worker="pi_ccr"))
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "any.py"}})
        assert json.loads(out)["permissionDecision"] == "deny"
        assert "pi_ccr" in json.loads(out)["permissionDecisionReason"]

    def test_claude_main_worker_allowed(self, tmp_path, monkeypatch, capsys):
        state = _state(tmp_path, "worker", _proposal(worker="claude_main"))
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "any.py"}})
        assert rc == 0 and out == ""

    def test_no_marker_silent_allow(self, tmp_path, monkeypatch, capsys):
        # No delegation marker -> not in a gated phase -> inert.
        state = _state(tmp_path, "none", _proposal())
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "any.py"}})
        assert rc == 0 and out == ""

    def test_no_proposal_silent_allow(self, tmp_path, monkeypatch, capsys):
        # Marker present but proposal missing (run predates policy) -> inert.
        state = tmp_path / "state"; state.mkdir()
        (state / ".delegation-advisory_r1").touch()
        _wire(monkeypatch, state)
        rc, out = _decide(monkeypatch, capsys, state,
                          {"tool_name": "Edit", "tool_input": {"file_path": "any.py"}})
        assert rc == 0 and out == ""

    def test_no_session_silent_allow(self, tmp_path, monkeypatch, capsys):
        # No session_id at all -> not a /go session.
        rc = gate._decide({"tool_name": "Edit", "tool_input": {"file_path": "x"}, "session_id": ""})
        assert rc == 0
        assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# Unit: harness branch guard
# ---------------------------------------------------------------------------

class TestHarnessBranchGuard:
    def test_worktree_branch_extract(self, tmp_path):
        wt = tmp_path / "wt"; (wt / ".git").mkdir(parents=True)
        (wt / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        assert pi_harness._worktree_branch(wt) == "main"
        (wt / ".git" / "HEAD").write_text("ref: refs/heads/feat/x\n", encoding="utf-8")
        assert pi_harness._worktree_branch(wt) == "x"

    def test_main_branch_refuses_spawn(self, tmp_path, monkeypatch):
        wt = tmp_path / "wt"; (wt / ".git").mkdir(parents=True)
        (wt / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        state = tmp_path / "state"; state.mkdir()

        def _no_spawn(*a, **kw):
            raise AssertionError("subprocess.run must not be called on main branch")
        monkeypatch.setattr(pi_harness.subprocess, "run", _no_spawn)

        result = pi_harness.run_pi_harness(
            worktree=wt, state_dir=state, run_id="r1",
            pi_model="any-model", prompt="do the task",
        )
        # Blocked marker written; result is a failure; spawn never happened.
        assert (state / ".blocked_r1").exists()
        assert result is not None

    def test_feature_branch_proceeds_to_spawn(self, tmp_path, monkeypatch):
        wt = tmp_path / "wt"; (wt / ".git").mkdir(parents=True)
        (wt / ".git" / "HEAD").write_text("ref: refs/heads/feat/auth\n", encoding="utf-8")
        state = tmp_path / "state"; state.mkdir()

        class _FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""
        spawned = {"called": False}

        def _spawn(*a, **kw):
            spawned["called"] = True
            return _FakeProc()
        monkeypatch.setattr(pi_harness.subprocess, "run", _spawn)

        pi_harness.run_pi_harness(
            worktree=wt, state_dir=state, run_id="r2",
            pi_model="any-model", prompt="do the task",
        )
        assert spawned["called"] is True


# ---------------------------------------------------------------------------
# Direct invocation (boundary proof) — real subprocess + real pointer file
# ---------------------------------------------------------------------------

class TestDirectInvocation:
    SID = "deleg-test-direct-sid"

    def _setup_real_pointer(self, tmp_path, mode):
        state = tmp_path / "state"; state.mkdir()
        proposal = _proposal(scope=["src/auth.py", "src/auth/"])
        (state / "task-proposal_r1.json").write_text(json.dumps(proposal), encoding="utf-8")
        if mode == "advisory":
            (state / ".delegation-advisory_r1").touch()
        elif mode == "worker":
            (state / ".delegation-worker_r1").touch()
        ptr_dir = Path("P:/.claude/.artifacts/go-sessions")
        ptr_dir.mkdir(parents=True, exist_ok=True)
        ptr = ptr_dir / f"{self.SID}.json"
        ptr.write_text(json.dumps({
            "go_state_dir": str(state), "run_id": "r1",
            "updated_at": "2099-01-01T00:00:00Z",
        }), encoding="utf-8")
        return state, ptr

    def _run(self, payload):
        p = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload), capture_output=True, text=True,
        )
        return p.stdout.strip(), p.returncode

    def test_advisory_edit_denies_via_real_path(self, tmp_path):
        state, ptr = self._setup_real_pointer(tmp_path, "advisory")
        try:
            out, rc = self._run({"tool_name": "Edit",
                                 "tool_input": {"file_path": "src/auth.py"},
                                 "session_id": self.SID})
            assert rc == 0
            decision = json.loads(out)
            assert decision["permissionDecision"] == "deny"
        finally:
            ptr.unlink(missing_ok=True)

    def test_advisory_read_silent_via_real_path(self, tmp_path):
        state, ptr = self._setup_real_pointer(tmp_path, "advisory")
        try:
            out, rc = self._run({"tool_name": "Read",
                                 "tool_input": {"file_path": "src/auth.py"},
                                 "session_id": self.SID})
            assert rc == 0 and out == ""
        finally:
            ptr.unlink(missing_ok=True)

    def test_worker_in_scope_silent_via_real_path(self, tmp_path):
        state, ptr = self._setup_real_pointer(tmp_path, "worker")
        try:
            out, rc = self._run({"tool_name": "Edit",
                                 "tool_input": {"file_path": "src/auth/login.py"},
                                 "session_id": self.SID})
            assert rc == 0 and out == ""
        finally:
            ptr.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Freshness regression: stale advisory artifact rejected (goal req. 5)
# ---------------------------------------------------------------------------

class TestAdvisoryFreshnessRejection:
    def test_stale_prompt_hash_raises(self):
        from preflight_propose import assert_advisory_fresh
        artifact = {"run_id": "r1", "prompt_hash": "old", "diff_hash": None}
        with pytest.raises(ValueError, match="prompt_hash"):
            assert_advisory_fresh(artifact, "r1", "new")
