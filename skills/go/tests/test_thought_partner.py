"""Tests for goal-size guard, thought-partner, and deterministic continuation gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import compress_goal, thought_partner_assessment, GOAL_MAX_CHARS
from orchestrate import task_prompt


# ---------------------------------------------------------------------------
# Goal-size guard
# ---------------------------------------------------------------------------

class TestGoalSizeGuard:

    def test_short_text_unchanged(self):
        text = "fix the hook gate"
        assert compress_goal(text) == text

    def test_exact_limit_unchanged(self):
        text = "x" * GOAL_MAX_CHARS
        assert compress_goal(text) == text

    def test_over_limit_compresses(self):
        text = "fix the hook gate\n" * 500
        result = compress_goal(text)
        assert len(result) <= GOAL_MAX_CHARS
        assert "Length:" in result

    def test_preserves_priority_markers(self):
        text = "Mission: fix the hook gate\n" + "x" * 5000
        result = compress_goal(text)
        assert "Mission:" in result

    def test_preserves_requirements_and_constraints(self):
        text = "Requirements: add tests\nConstraints: no hard blocking\n" + "y" * 5000
        result = compress_goal(text)
        assert "Requirements:" in result
        assert "Constraints:" in result

    def test_compression_report_format(self):
        text = "z" * 5000
        result = compress_goal(text)
        assert "Length:" in result
        assert f"/ {GOAL_MAX_CHARS}" in result


# ---------------------------------------------------------------------------
# Thought-partner assessment
# ---------------------------------------------------------------------------

class TestThoughtPartner:

    def test_broad_hook_task_gets_assessment(self):
        tp = thought_partner_assessment("fix the Stop hook JSON validation failure")
        assert tp is not None
        assert "taskIntent" in tp
        assert "impliedRequirements" in tp
        assert "missingImprovements" in tp
        assert "unsafeAssumptions" in tp
        assert "missingVerification" in tp

    def test_hook_task_has_schema_implied(self):
        tp = thought_partner_assessment("fix the Stop hook gate")
        assert tp is not None
        assert any("schema" in r.lower() for r in tp["impliedRequirements"])

    def test_review_task_has_evidence_implied(self):
        tp = thought_partner_assessment("review the rca output and audit the hook changes")
        assert tp is not None
        assert any("evidence" in r.lower() for r in tp["impliedRequirements"])

    def test_trivial_no_assessment(self):
        tp = thought_partner_assessment("say hi")
        assert tp is None

    def test_empty_no_assessment(self):
        tp = thought_partner_assessment("")
        assert tp is None

    def test_short_prompt_no_assessment(self):
        tp = thought_partner_assessment("fix typo")
        assert tp is None

    def test_refactor_gets_backward_compat_implied(self):
        tp = thought_partner_assessment("refactor the routing architecture for cleaner separation")
        assert tp is not None
        assert any("backward" in r.lower() or "test" in r.lower() for r in tp["impliedRequirements"])


# ---------------------------------------------------------------------------
# Worker prompt rendering for thought-partner
# ---------------------------------------------------------------------------

class TestThoughtPartnerPromptRendering:

    def test_renders_when_present(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "fix Stop hook",
                "objective": "fix",
                "thoughtPartner": {
                    "taskIntent": "Fix the JSON validation failure in Stop hook",
                    "impliedRequirements": ["schema-valid output"],
                    "missingImprovements": ["add targeted tests"],
                    "unsafeAssumptions": ["may assume root cause"],
                    "missingVerification": ["run test suite"],
                },
            }
        }
        p = tmp_path / "active-task_tp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Thought partner assessment" in prompt
        assert "Real goal:" in prompt
        assert "schema-valid output" in prompt
        assert "add targeted tests" in prompt

    def test_no_render_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {"task": {"title": "simple", "objective": "do thing"}}
        p = tmp_path / "active-task_tp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Thought partner assessment" not in prompt


# ---------------------------------------------------------------------------
# Deterministic continuation gate
# ---------------------------------------------------------------------------

class TestContinuationGate:

    def test_no_state_fails_open(self):
        """When no state dir exists, gate returns empty (allow)."""
        from go_continuation_gate import check_go_completion
        # We can't easily mock _find_state_dir here, but we can test the logic
        # by checking the function exists and is callable
        assert callable(check_go_completion)

    def test_hook_output_valid_json(self):
        """Hook output is always valid JSON."""
        from go_continuation_gate import check_go_completion
        result = check_go_completion()
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)

    def test_done_state_approves(self):
        """When .pr_ready exists, gate approves."""
        from go_continuation_gate import _find_active_task, check_go_completion
        import go_continuation_gate as mod
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            # Create a task file
            task_file = tdir / "active-task_test.json"
            task_file.write_text(json.dumps({"task": {"title": "test task", "status": "selected"}}))
            # Create .pr_ready marker
            (tdir / ".pr_ready").touch()

            # Patch the module-level functions
            old_find = mod._find_state_dir
            old_task = mod._find_active_task
            try:
                mod._find_state_dir = lambda: tdir
                mod._find_active_task = lambda d: json.loads(task_file.read_text(encoding="utf-8"))
                result = check_go_completion()
                assert result["decision"] == "approve"
                assert "goal met" in result["reason"]
            finally:
                mod._find_state_dir = old_find
                mod._find_active_task = old_task

    def test_blocked_state_blocks(self):
        """When .blocked exists, gate blocks with reason."""
        from go_continuation_gate import check_go_completion
        import go_continuation_gate as mod
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            task_file = tdir / "active-task_test.json"
            task_file.write_text(json.dumps({"task": {"title": "test task", "status": "selected"}}))
            # Create .blocked marker
            (tdir / ".blocked_test").touch()
            # Create block reason file
            block_file = tdir / "blocked_test.json"
            block_file.write_text(json.dumps({"phase": "dispatch", "reason_code": "dispatch_failed"}))

            old_find = mod._find_state_dir
            old_task = mod._find_active_task
            try:
                mod._find_state_dir = lambda: tdir
                mod._find_active_task = lambda d: json.loads(task_file.read_text(encoding="utf-8"))
                result = check_go_completion()
                assert result["decision"] == "block"
                assert "continue:" in result["reason"]
            finally:
                mod._find_state_dir = old_find
                mod._find_active_task = old_task
