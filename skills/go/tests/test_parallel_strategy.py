"""Tests for parallel_strategy_for_task and worker prompt rendering."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import parallel_strategy_for_task
from orchestrate import task_prompt


class TestParallelStrategyDetection:

    def test_hook_task_recommends_evidence_test_critic(self):
        s = parallel_strategy_for_task("fix the Stop hook JSON validation failure")
        assert s["recommended"] is True
        names = {l["name"] for l in s["lanes"]}
        assert "evidence-scout" in names
        assert "test-designer" in names
        assert "critic" in names

    def test_routing_refactor_recommends_alternative_designer(self):
        s = parallel_strategy_for_task("refactor the routing architecture")
        assert s["recommended"] is True
        names = {l["name"] for l in s["lanes"]}
        assert "alternative-designer" in names

    def test_quarantine_recommends_parallel_analysis(self):
        s = parallel_strategy_for_task("Phase 2: quarantine failing tests")
        assert s["recommended"] is True
        names = {l["name"] for l in s["lanes"]}
        assert "evidence-scout" in names

    def test_quarantine_mutation_parent_only(self):
        s = parallel_strategy_for_task("Phase 2: quarantine failing tests")
        assert "parent-only" in s["mutationPolicy"]

    def test_trivial_no_parallelism(self):
        s = parallel_strategy_for_task("say hi")
        assert s["recommended"] is False
        assert s["lanes"] == []

    def test_trivial_typo_no_parallelism(self):
        s = parallel_strategy_for_task("fix typo in README")
        assert s["recommended"] is False

    def test_user_supplied_plan_recommends_parallel(self):
        s = parallel_strategy_for_task(
            "Phase 2: quarantine failing tests, Phase 3: dispatch manifest"
        )
        assert s["recommended"] is True

    def test_all_lanes_may_not_mutate(self):
        for prompt in [
            "fix the Stop hook JSON validation failure",
            "Phase 2: quarantine failing tests",
            "refactor the routing architecture",
            "review the /rca skill output",
        ]:
            s = parallel_strategy_for_task(prompt)
            for lane in s.get("lanes", []):
                assert lane["mayMutate"] is False, f"{lane['name']} mayMutate=True in '{prompt[:40]}'"

    def test_spawn_by_default_true_when_recommended(self):
        s = parallel_strategy_for_task("fix the Stop hook JSON validation failure")
        assert s["spawnByDefault"] is True

    def test_overhead_risk_present(self):
        s = parallel_strategy_for_task("fix the Stop hook JSON validation failure")
        assert s["overheadRisk"] in ("low", "low-medium", "medium")

    def test_empty_prompt_no_parallelism(self):
        s = parallel_strategy_for_task("")
        assert s["recommended"] is False


class TestParallelStrategyInActiveTask:

    def test_recommended_writes_to_task(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        ps = parallel_strategy_for_task("fix the Stop hook JSON validation failure")
        assert ps["recommended"] is True
        task = {"task": {"title": "fix hook", "objective": "fix"}}
        if ps.get("recommended"):
            task["task"]["parallelStrategy"] = ps
        assert "parallelStrategy" in task["task"]
        assert task["task"]["parallelStrategy"]["recommended"] is True

    def test_trivial_no_parallel_strategy(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        ps = parallel_strategy_for_task("say hi")
        assert ps["recommended"] is False
        task = {"task": {"title": "hi", "objective": "hi"}}
        if ps.get("recommended"):
            task["task"]["parallelStrategy"] = ps
        assert "parallelStrategy" not in task["task"]


class TestParallelStrategyPromptRendering:

    def test_renders_when_recommended(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "fix Stop hook",
                "objective": "fix JSON validation",
                "parallelStrategy": {
                    "recommended": True,
                    "mode": "analysis-parallel-mutation-serialized",
                    "lanes": [
                        {"name": "evidence-scout", "mayMutate": False,
                         "purpose": "map code paths", "output": "evidence ledger"},
                        {"name": "test-designer", "mayMutate": False,
                         "purpose": "propose tests", "output": "test plan"},
                    ],
                    "mutationPolicy": "serialized",
                    "overheadRisk": "low",
                },
            }
        }
        p = tmp_path / "active-task_ps.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Safe parallelism" in prompt
        assert "evidence-scout" in prompt
        assert "test-designer" in prompt
        assert "Parent owns final patch" in prompt
        assert "Do not let parallel agents mutate" in prompt

    def test_no_render_when_not_recommended(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {"task": {"title": "fix typo", "objective": "fix"}}
        p = tmp_path / "active-task_ps.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Safe parallelism" not in prompt

    def test_no_render_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {"task": {"title": "simple task", "objective": "do thing"}}
        p = tmp_path / "active-task_ps.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Safe parallelism" not in prompt
