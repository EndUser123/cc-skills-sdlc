"""Tests for the mutation-plan precondition system (Phase 6.8)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import requires_mutation_plan
from orchestrate import task_prompt


# ---------------------------------------------------------------------------
# requires_mutation_plan detection tests
# ---------------------------------------------------------------------------

class TestRequiresMutationPlan:
    """Keyword detection for mutation-heavy prompts."""

    def test_quarantine_sets_true(self):
        r = requires_mutation_plan("Phase 2: quarantine failing tests before editing")
        assert r is not None
        assert r["kinds"] == ["quarantine"]

    def test_git_mv_sets_move(self):
        r = requires_mutation_plan("git mv tests to _quarantine")
        assert r is not None
        assert "move" in r["kinds"]

    def test_git_rm_sets_delete(self):
        r = requires_mutation_plan("git rm the deprecated files")
        assert r is not None
        assert "delete" in r["kinds"]

    def test_cleanup_sets_delete(self):
        r = requires_mutation_plan("cleanup old log files")
        assert r is not None
        assert "delete" in r["kinds"]

    def test_normal_prompt_does_not(self):
        r = requires_mutation_plan("fix the hook gate json validation")
        assert r is None

    def test_trivial_does_not(self):
        r = requires_mutation_plan("say hi")
        assert r is None

    def test_empty_does_not(self):
        r = requires_mutation_plan("")
        assert r is None

    def test_multi_keyword_dedupes(self):
        r = requires_mutation_plan("git mv and quarantine the failing tests")
        assert r is not None
        # Should have quarantine and move, deduped
        assert "quarantine" in r["kinds"]
        assert "move" in r["kinds"]

    def test_has_reason_and_kinds(self):
        r = requires_mutation_plan("quarantine failing tests")
        assert r is not None
        assert "reason" in r
        assert "kinds" in r
        assert isinstance(r["kinds"], list)


# ---------------------------------------------------------------------------
# Active-task JSON wiring tests
# ---------------------------------------------------------------------------

class TestMutationPlanInActiveTask:
    """Verify requiresMutationPlan appears in active-task JSON when triggered."""

    def test_quarantine_sets_field(self, monkeypatch, tmp_path):
        """Quarantine prompt sets requiresMutationPlan=true in active-task."""
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        # We test the wiring by calling the detection + task_prompt path.
        # The full orchestrate.py entry point needs args, so we test the
        # detection function directly and verify task_prompt renders it.
        mp = requires_mutation_plan("Phase 2: quarantine failing tests")
        assert mp is not None
        # Simulate what load_or_create_task does
        task = {
            "task": {
                "title": "Phase 2: quarantine",
                "objective": "quarantine tests",
                "requiresMutationPlan": True,
                "mutationPlanReason": mp["reason"],
                "mutationPlanKinds": mp["kinds"],
            }
        }
        p = tmp_path / "active-task_test.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "MUTATION PLAN REQUIRED" in prompt

    def test_normal_no_field(self, monkeypatch, tmp_path):
        """Normal prompt does not include mutation plan section."""
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "fix hook gate",
                "objective": "fix json",
            }
        }
        p = tmp_path / "active-task_test.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "MUTATION PLAN REQUIRED" not in prompt


# ---------------------------------------------------------------------------
# Worker prompt rendering tests
# ---------------------------------------------------------------------------

class TestMutationPlanPromptRendering:
    """Worker prompt includes mutation-plan requirement only when field is true."""

    def test_renders_when_true(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "quarantine sweep",
                "objective": "move files",
                "requiresMutationPlan": True,
                "mutationPlanReason": "Prompt contains mutation keywords: quarantine",
                "mutationPlanKinds": ["quarantine"],
            }
        }
        p = tmp_path / "active-task_mp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "MUTATION PLAN REQUIRED" in prompt
        assert "mutation-plan_{phase_id}.json" in prompt
        assert "authoritative_source_output" in prompt
        assert "exempt_filter_result" in prompt
        assert "proposed_move_list" in prompt
        assert "permitted_fence" in prompt
        assert "rollback_command" in prompt
        assert "verification_commands" in prompt

    def test_no_render_when_false(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "fix hook",
                "objective": "fix",
                "requiresMutationPlan": False,
            }
        }
        p = tmp_path / "active-task_mp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "MUTATION PLAN REQUIRED" not in prompt

    def test_no_render_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "fix hook",
                "objective": "fix",
            }
        }
        p = tmp_path / "active-task_mp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "MUTATION PLAN REQUIRED" not in prompt

    def test_includes_reason_and_kinds(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "quarantine",
                "objective": "quarantine tests",
                "requiresMutationPlan": True,
                "mutationPlanReason": "Contains quarantine keyword",
                "mutationPlanKinds": ["quarantine", "move"],
            }
        }
        p = tmp_path / "active-task_mp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Contains quarantine keyword" in prompt
        assert "quarantine, move" in prompt

    def test_done_without_plan_warns(self, monkeypatch, tmp_path):
        """Worker prompt warns about DONE without mutation plan."""
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "quarantine",
                "objective": "quarantine tests",
                "requiresMutationPlan": True,
                "mutationPlanReason": "quarantine task",
                "mutationPlanKinds": ["quarantine"],
            }
        }
        p = tmp_path / "active-task_mp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "DONE is claimed but no valid mutation-plan" in prompt

    def test_trivial_unaffected(self, monkeypatch, tmp_path):
        """Trivial task has no mutation plan section."""
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "say hi",
                "objective": "greet",
            }
        }
        p = tmp_path / "active-task_mp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "MUTATION PLAN" not in prompt
