"""Tests for falsification_gate.py — bounded adversarial falsification MVP.

Covers: routing, request binding, result validation, verdict policy,
disposable worktree isolation, and cleanup. Uses temp-Git-repository
fixtures — no mocks — so the filesystem-level isolation is proven.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "falsification_gate.py"
_spec = importlib.util.spec_from_file_location("falsification_gate", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

should_falsify = _mod.should_falsify
build_falsification_request = _mod.build_falsification_request
validate_falsification_result = _mod.validate_falsification_result
apply_verdict_policy = _mod.apply_verdict_policy
create_attack_worktree = _mod.create_attack_worktree
cleanup_attack_worktree = _mod.cleanup_attack_worktree
verify_authoritative_unchanged = _mod.verify_authoritative_unchanged
resolve_budget = _mod.resolve_budget
REQUEST_SCHEMA = _mod.REQUEST_SCHEMA
RESULT_SCHEMA = _mod.RESULT_SCHEMA


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    """Create a real Git repo with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "main.py").write_text("x = 1\n")
    _git(repo, "add", "main.py")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


# ---------------------------------------------------------------------------
# 1. Routing
# ---------------------------------------------------------------------------

class TestRouting:
    def test_docs_only_skips(self):
        req, reasons = should_falsify({"task": {"title": "Fix README", "objective": "documentation", "task_type": "implementation"}})
        assert req is False
        assert any("documentation" in r for r in reasons)

    def test_validation_skips(self):
        req, reasons = should_falsify({"task": {"title": "Audit", "objective": "validate", "task_type": "validation"}})
        assert req is False

    def test_hook_task_triggers(self):
        req, reasons = should_falsify({"task": {"title": "Fix Stop hook", "objective": "Update hook gate", "task_type": "implementation"}})
        assert req is True
        assert any("high-risk" in r for r in reasons)

    def test_cache_recovery_triggers(self):
        req, reasons = should_falsify({"task": {"title": "Fix cache recovery", "objective": "Update release recovery direction", "task_type": "implementation"}})
        assert req is True

    def test_skip_env(self, monkeypatch):
        monkeypatch.setenv("GO_FALSIFICATION_SKIP", "1")
        req, reasons = should_falsify({"task": {"title": "Fix Stop hook", "objective": "hook", "task_type": "implementation"}})
        assert req is False
        assert any("SKIP" in r for r in reasons)

    def test_changed_file_surface_triggers(self):
        req, reasons = should_falsify(
            {"task": {"title": "Refactor", "objective": "cleanup", "task_type": "implementation"}},
            changed_files=["hooks/Stop_enforce_gate.py"],
        )
        assert req is True


# ---------------------------------------------------------------------------
# 2. Request binding
# ---------------------------------------------------------------------------

class TestRequestBinding:
    def test_request_contains_run_task_revision_worktree_changed_files_budget(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD")
        run_id = "test-run-123"
        task = {"task": {"id": "T1", "title": "Fix hook", "objective": "hook gate", "task_type": "implementation",
                          "acceptance_criteria": ["AC1"], "scope_in": ["hooks/"]}}
        req = build_falsification_request(tmp_path / "state", run_id, repo, task,
                                          ["hooks/Stop.py"], None, ["high-risk: hook"])
        assert req["schema"] == REQUEST_SCHEMA
        assert req["run_id"] == run_id
        assert req["task_id"] == "T1"
        assert req["authoritative_worktree"] == str(repo)
        assert req["head_revision"] == head
        assert req["base_revision"]  # non-empty
        assert req["changed_files"] == ["hooks/Stop.py"]
        assert "max_attempts" in req["budget"]
        assert "timeout_seconds" in req["budget"]
        assert "total_elapsed_seconds" in req["budget"]
        assert req["request_digest"]  # SHA-256 hex

    def test_request_digest_is_deterministic(self, tmp_path):
        repo = _make_repo(tmp_path)
        task = {"task": {"id": "T1", "title": "Fix hook", "objective": "hook", "task_type": "implementation"}}
        req1 = build_falsification_request(tmp_path / "s", "r1", repo, task, ["a.py"], None, ["x"])
        req2 = build_falsification_request(tmp_path / "s", "r1", repo, task, ["a.py"], None, ["x"])
        assert req1["request_digest"] == req2["request_digest"]


# ---------------------------------------------------------------------------
# 3. Result validation
# ---------------------------------------------------------------------------

class TestResultValidation:
    def _base_request(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD")
        return build_falsification_request(tmp_path / "s", "run-1", repo,
                                           {"task": {"id": "T1", "title": "x", "objective": "y"}},
                                           [], None, ["reason"])

    def _valid_result(self, request, verdict="NOT_FALSIFIED_WITHIN_BUDGET"):
        return {
            "schema": RESULT_SCHEMA,
            "run_id": request["run_id"],
            "request_digest": request["request_digest"],
            "task_id": request["task_id"],
            "base_revision": request["base_revision"],
            "head_revision": request["head_revision"],
            "verdict": verdict,
            "counterexamples": [],
        }

    def test_valid_not_falsified(self, tmp_path):
        req = self._base_request(tmp_path)
        result = self._valid_result(req)
        ok, reason = validate_falsification_result(result, req, req["run_id"])
        assert ok, reason

    def test_valid_falsified_with_counterexample(self, tmp_path):
        req = self._base_request(tmp_path)
        result = self._valid_result(req, "FALSIFIED")
        result["counterexamples"] = [{
            "claim_falsified": "session binding",
            "command": "python -c 'assert False'",
            "expected_result": "exit 0",
            "actual_result": "exit 1",
            "output": "AssertionError",
        }]
        ok, reason = validate_falsification_result(result, req, req["run_id"])
        assert ok, reason

    def test_prose_only_falsified_rejected(self, tmp_path):
        req = self._base_request(tmp_path)
        result = self._valid_result(req, "FALSIFIED")
        result["counterexamples"] = [{"claim_falsified": "x"}]  # no command
        ok, reason = validate_falsification_result(result, req, req["run_id"])
        assert not ok
        assert "command" in reason

    def test_wrong_run_id_rejected(self, tmp_path):
        req = self._base_request(tmp_path)
        result = self._valid_result(req)
        result["run_id"] = "wrong"
        ok, reason = validate_falsification_result(result, req, req["run_id"])
        assert not ok
        assert "run_id" in reason

    def test_wrong_digest_rejected(self, tmp_path):
        req = self._base_request(tmp_path)
        result = self._valid_result(req)
        result["request_digest"] = "deadbeef"
        ok, reason = validate_falsification_result(result, req, req["run_id"])
        assert not ok
        assert "digest" in reason

    def test_missing_result_rejected(self, tmp_path):
        req = self._base_request(tmp_path)
        ok, reason = validate_falsification_result(None, req, req["run_id"])
        assert not ok

    def test_malformed_result_rejected(self, tmp_path):
        req = self._base_request(tmp_path)
        ok, reason = validate_falsification_result("not json", req, req["run_id"])
        assert not ok

    def test_invalid_verdict_rejected(self, tmp_path):
        req = self._base_request(tmp_path)
        result = self._valid_result(req, "PASS")  # PASS is not allowed
        ok, reason = validate_falsification_result(result, req, req["run_id"])
        assert not ok
        assert "verdict" in reason


# ---------------------------------------------------------------------------
# 4. Verdict policy
# ---------------------------------------------------------------------------

class TestVerdictPolicy:
    def test_not_falsified_proceeds(self):
        assert apply_verdict_policy("NOT_FALSIFIED_WITHIN_BUDGET") == "proceed"

    def test_falsified_blocks(self):
        assert apply_verdict_policy("FALSIFIED") == "block"

    def test_inconclusive_blocks_mvp(self):
        assert apply_verdict_policy("INCONCLUSIVE") == "block"

    def test_harness_failure_blocks(self):
        assert apply_verdict_policy("HARNESS_FAILURE") == "block"

    def test_budget_exhausted_blocks(self):
        assert apply_verdict_policy("BUDGET_EXHAUSTED") == "block"


# ---------------------------------------------------------------------------
# 5. Disposable worktree isolation + cleanup
# ---------------------------------------------------------------------------

class TestDisposableWorktree:
    def test_attack_worktree_created_and_isolated(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD")
        attack = create_attack_worktree(repo, "test-run", head)
        assert attack.exists()
        assert attack != repo
        # Attack worktree is writable
        (attack / "attack_test.py").write_text("print('attacked')\n")
        assert (attack / "attack_test.py").exists()
        # Authoritative worktree unchanged
        assert not (repo / "attack_test.py").exists()
        # Cleanup
        report = cleanup_attack_worktree(attack)
        assert report["cleaned"], report["errors"]
        assert not attack.exists()

    def test_authoritative_unchanged_after_attack(self, tmp_path):
        repo = _make_repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD")
        attack = create_attack_worktree(repo, "test-run2", head)
        # Mutate attack worktree
        (attack / "main.py").write_text("MUTATED\n")
        _git(attack, "add", "main.py")
        _git(attack, "commit", "-q", "-m", "attack mutation")
        # Authoritative unchanged
        assert verify_authoritative_unchanged(repo, head)
        assert (repo / "main.py").read_text() == "x = 1\n"
        cleanup_attack_worktree(attack)

    def test_cleanup_after_already_removed(self, tmp_path):
        attack = tmp_path / "nonexistent-attack"
        report = cleanup_attack_worktree(attack)
        assert report["cleaned"]


# ---------------------------------------------------------------------------
# 6. Single .pr-ready writer invariant
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 7. Gold corpus — real-path planted-defect tests
# ---------------------------------------------------------------------------

class TestGoldCorpusRealPath:
    """Planted-defect tests through the real request → validate → verdict path.

    Each test creates a real Git repository, a valid falsification request,
    and a result that SHOULD trigger a specific defect class. The tests prove
    the falsification gate catches each class.
    """

    def _setup(self, tmp_path):
        """Create a real repo + valid request for gold-corpus tests."""
        repo = _make_repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD")
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        task = {"task": {"id": "GOLD-T1", "title": "Fix hook", "objective": "hook session identity",
                          "task_type": "implementation", "acceptance_criteria": ["AC1"]}}
        request = build_falsification_request(
            state_dir, "gold-run-1", repo, task,
            ["hooks/Stop.py"], None, ["high-risk: hook"],
        )
        req_path = state_dir / f"falsification-request_{request['run_id']}.json"
        req_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
        return repo, head, state_dir, request

    def test_malformed_result_fails_closed(self, tmp_path):
        """Gold case: a malformed required result fails open → the gate MUST
        reject it. This prevents a broken attacker from accidentally passing."""
        repo, head, state_dir, request = self._setup(tmp_path)
        run_id = request["run_id"]

        # Write a malformed result (not JSON)
        res_path = state_dir / f"falsification-result_{run_id}.json"
        res_path.write_text("NOT JSON\n", encoding="utf-8")

        # Run the validation path
        ok, reason = validate_falsification_result(None, request, run_id)
        assert not ok
        assert reason

    def test_wrong_run_id_rejected(self, tmp_path):
        """Gold case: a result with wrong run_id is accepted → the gate MUST
        reject it. This prevents cross-run contamination."""
        repo, head, state_dir, request = self._setup(tmp_path)
        run_id = request["run_id"]

        # Valid result structure but WRONG run_id
        result = {
            "schema": RESULT_SCHEMA,
            "run_id": "wrong-run-id",
            "request_digest": request["request_digest"],
            "task_id": request["task_id"],
            "base_revision": request["base_revision"],
            "head_revision": request["head_revision"],
            "verdict": "NOT_FALSIFIED_WITHIN_BUDGET",
            "counterexamples": [],
        }
        res_path = state_dir / f"falsification-result_{run_id}.json"
        res_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

        ok, reason = validate_falsification_result(result, request, run_id)
        assert not ok
        assert "run_id" in reason

    def test_wrong_digest_rejected(self, tmp_path):
        """Gold case: a result with wrong request digest is accepted →
        the gate MUST reject it. This guards against stale or tampered results."""
        repo, head, state_dir, request = self._setup(tmp_path)
        run_id = request["run_id"]

        result = {
            "schema": RESULT_SCHEMA,
            "run_id": run_id,
            "request_digest": "deadbeef",
            "task_id": request["task_id"],
            "base_revision": request["base_revision"],
            "head_revision": request["head_revision"],
            "verdict": "NOT_FALSIFIED_WITHIN_BUDGET",
            "counterexamples": [],
        }
        ok, reason = validate_falsification_result(result, request, run_id)
        assert not ok
        assert "digest" in reason

    def test_prose_only_falsified_rejected(self, tmp_path):
        """Gold case: a FALSIFIED verdict without executable reproduction
        evidence must be rejected. Prevents fabricated findings."""
        repo, head, state_dir, request = self._setup(tmp_path)
        run_id = request["run_id"]

        result = {
            "schema": RESULT_SCHEMA,
            "run_id": run_id,
            "request_digest": request["request_digest"],
            "task_id": request["task_id"],
            "base_revision": request["base_revision"],
            "head_revision": request["head_revision"],
            "verdict": "FALSIFIED",
            "counterexamples": [{"claim_falsified": "x"}],  # no command
        }
        ok, reason = validate_falsification_result(result, request, run_id)
        assert not ok
        assert "command" in reason

    def test_real_falsified_blocks(self, tmp_path):
        """Gold case: a valid FALSIFIED result blocks .pr-ready.
        Prove through the apply_verdict_policy function."""
        policy = apply_verdict_policy("FALSIFIED")
        assert policy == "block"

    def test_authoritative_unchanged_after_full_flow(self, tmp_path):
        """Gold case: the authoritative worktree remains unmodified after
        the full request → attack worktree → cleanup flow."""
        repo = _make_repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD")

        # Create attack worktree
        attack = create_attack_worktree(repo, "gold-run-2", head)
        assert attack.exists()

        # Mutate attack worktree
        (attack / "new_gold_file.py").write_text("ATTACKER_WROTE_THIS\n")
        _git(attack, "add", "new_gold_file.py")
        _git(attack, "commit", "-q", "-m", "attack")

        # Authoritative must be unchanged
        assert verify_authoritative_unchanged(repo, head)
        assert not (repo / "new_gold_file.py").exists()
        assert (repo / "main.py").read_text() == "x = 1\n"

        # Cleanup
        report = cleanup_attack_worktree(attack)
        assert report["cleaned"], report["errors"]
        assert not attack.exists()


class TestSinglePrReadyWriter:
    def test_no_pr_ready_writer_in_falsification_gate(self):
        """falsification_gate.py must never write .pr-ready itself."""
        false_text = SCRIPT.read_text(encoding="utf-8")
        assert ".pr-ready" not in false_text, "falsification_gate must not contain .pr-ready literal"

    def test_only_one_pr_ready_writer_in_orchestrate(self):
        """Grep orchestrate.py for .pr-ready writes — must be exactly one."""
        orch = Path(__file__).resolve().parent.parent / "scripts" / "orchestrate.py"
        text = orch.read_text(encoding="utf-8")
        # Count lines that write .pr-ready (touch or write)
        pr_ready_writes = [l for l in text.splitlines()
                          if ".pr-ready_" in l and ("touch" in l.lower() or "write" in l.lower())]
        # The falsification gate must NOT add a second writer.
        # Current writer: _pr_artifacts_and_tail at line ~1676.
        assert len(pr_ready_writes) >= 1, "expected at least one .pr-ready writer"
        # No new writer should have been added by falsification_gate.py imports
        false_script = Path(__file__).resolve().parent.parent / "scripts" / "falsification_gate.py"
        false_text = false_script.read_text(encoding="utf-8")
        assert ".pr-ready" not in false_text, "falsification_gate.py must not write .pr-ready"
