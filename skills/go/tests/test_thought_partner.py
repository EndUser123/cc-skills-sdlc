"""Tests for goal-size guard, thought-partner, and deterministic continuation gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preflight_propose import compress_goal, thought_partner_assessment, plan_review, GOAL_MAX_CHARS
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
    """Strict Stop-hook contract: block prints JSON; allow/done/no-state print nothing."""

    def test_no_state_returns_none(self):
        """No /go state dir -> None (main prints nothing)."""
        from go_continuation_gate import check_go_completion
        result = check_go_completion()
        assert result is None

    def test_blocked_returns_block_dict(self):
        """Work remaining -> {"decision":"block",...}; never approve/empty."""
        import go_continuation_gate as mod
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "active-task_test.json").write_text(
                json.dumps({"task": {"title": "test task", "status": "selected"}})
            )
            (tdir / ".blocked_test").touch()
            (tdir / "blocked_blocked_test.json").write_text(
                json.dumps({"phase": "dispatch", "reason_code": "dispatch_failed"})
            )
            old = mod._find_state_dir
            try:
                mod._find_state_dir = lambda: tdir
                result = mod.check_go_completion()
                assert isinstance(result, dict)
                assert result["decision"] == "block"
                assert "continue:" in result["reason"]
                assert result["decision"] != "approve"
            finally:
                mod._find_state_dir = old

    def test_done_returns_none(self):
        """Completion marker (.pr_ready) -> None (main prints nothing, NOT approve)."""
        import go_continuation_gate as mod
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "active-task_test.json").write_text(
                json.dumps({"task": {"title": "test task", "status": "selected"}})
            )
            (tdir / ".pr_ready").touch()
            old = mod._find_state_dir
            try:
                mod._find_state_dir = lambda: tdir
                assert mod.check_go_completion() is None
            finally:
                mod._find_state_dir = old


class TestContinuationGateContract:
    """Mechanical checks: stdout shape through the real registered command path."""

    @pytest.fixture
    def run_gate(self):
        import subprocess
        gate = Path(__file__).resolve().parent.parent / "scripts" / "go_continuation_gate.py"
        def _run(payload="{}"):
            p = subprocess.run(
                [sys.executable, str(gate)],
                input=payload, capture_output=True, text=True,
            )
            return p.stdout, p.stderr, p.returncode
        return _run

    def test_no_state_emits_empty_stdout(self, run_gate):
        """No /go state -> exactly empty stdout (never {})."""
        out, err, rc = run_gate()
        assert out == "", f"expected empty stdout, got {out!r}"
        assert rc == 0

    def test_never_emits_approve_or_empty_object(self, run_gate):
        """Allow path must never print {} or {"decision":"approve"}."""
        out, _, _ = run_gate()
        assert out.strip() not in ("{}", '{"decision": "approve"}', '{"decision":"approve"}')

    def test_block_emits_valid_block_json(self, tmp_path, monkeypatch):
        """When state shows work remaining, stdout is valid block JSON."""
        import go_continuation_gate as mod
        sd = tmp_path / "go"
        sd.mkdir()
        (sd / "active-task_t.json").write_text(
            json.dumps({"task": {"title": "t", "status": "selected"}})
        )
        (sd / ".blocked_t").touch()
        (sd / "blocked_blocked_t.json").write_text(
            json.dumps({"phase": "dispatch", "reason_code": "dispatch_failed"})
        )
        monkeypatch.setattr(mod, "_find_state_dir", lambda: sd)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main()
        out = buf.getvalue()
        parsed = json.loads(out)  # must be valid JSON
        assert parsed["decision"] == "block"
        assert "continue:" in parsed["reason"]


# ---------------------------------------------------------------------------
# Goal compression: footer-included length
# ---------------------------------------------------------------------------

class TestGoalCompressionFooter:

    def test_compressed_with_footer_fits_limit(self):
        text = "Mission: fix everything\n" + "x" * 5000
        result = compress_goal(text)
        assert len(result) <= GOAL_MAX_CHARS
        assert "Length:" in result

    def test_compressed_preserves_constraints(self):
        text = "Do not touch Stop.py\nConstraints: no hard blocking\n" + "y" * 5000
        result = compress_goal(text)
        assert "Do not" in result
        assert "Constraints:" in result

    def test_compressed_preserves_do_not_rules(self):
        text = "Do not edit production files\nDo not break tests\n" + "z" * 5000
        result = compress_goal(text)
        assert "Do not" in result


# ---------------------------------------------------------------------------
# Plan review
# ---------------------------------------------------------------------------

class TestPlanReview:

    def test_multi_phase_plan_detected(self):
        pr = plan_review(
            "Phase 1: quarantine failing tests, Phase 2: create dispatch manifest, "
            "Phase 3: run verification"
        )
        assert pr is not None
        assert pr["planProvided"] is True
        assert len(pr["planImprovements"]) > 0

    def test_no_plan_returns_none(self):
        pr = plan_review("fix the hook gate")
        assert pr is None

    def test_plan_with_shared_files(self):
        pr = plan_review(
            "Phase 1: update orchestrate.py, Phase 2: modify Stop.py, Phase 3: test"
        )
        assert pr is not None
        assert len(pr["sharedFileConflicts"]) > 0

    def test_plan_missing_rollback(self):
        pr = plan_review(
            "Phase 1: quarantine tests, Phase 2: create manifest, Phase 3: run verify"
        )
        assert pr is not None
        assert len(pr["missingRollback"]) > 0

    def test_plan_missing_tests(self):
        pr = plan_review(
            "Phase 1: move files, Phase 2: update config, Phase 3: clean up"
        )
        assert pr is not None
        assert len(pr["missingTests"]) > 0


# ---------------------------------------------------------------------------
# Plan review prompt rendering
# ---------------------------------------------------------------------------

class TestPlanReviewPromptRendering:

    def test_renders_when_present(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {
            "task": {
                "title": "multi-phase task",
                "objective": "execute plan",
                "planReview": {
                    "planProvided": True,
                    "planImprovements": ["add verification step"],
                    "sharedFileConflicts": [],
                    "missingTests": ["add regression test"],
                    "missingRollback": [],
                },
            }
        }
        p = tmp_path / "active-task_pr.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Plan improvements:" in prompt
        assert "add verification step" in prompt
        assert "Missing tests:" in prompt


# ---------------------------------------------------------------------------
# Hook-work contract prompt rendering
# ---------------------------------------------------------------------------

class TestHookWorkContractRendering:

    def test_renders_for_hook_task(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {"task": {"title": "fix the Stop hook JSON validation", "objective": "fix"}}
        p = tmp_path / "active-task_hwc.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Hook-work contract" in prompt
        assert "dispatch surface" in prompt
        assert "prints NOTHING" in prompt or "print NOTHING" in prompt

    def test_no_render_for_non_hook_task(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {"task": {"title": "add a config option", "objective": "add"}}
        p = tmp_path / "active-task_noop.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Hook-work contract" not in prompt


# ---------------------------------------------------------------------------
# Continuation policy + native /goal warning + cache-drift + direct-entry docs
# ---------------------------------------------------------------------------

class TestContinuationPolicyRendering:

    def test_warning_renders_for_state_expressible_goal(self, monkeypatch, tmp_path):
        """State-expressible completion goal -> native /goal warning renders."""
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {"task": {"title": "run to completion", "objective": "finish"}}
        p = tmp_path / "active-task_cp.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Continuation policy" in prompt
        assert "Do NOT pair native /goal" in prompt or "Do not pair native /goal" in prompt
        assert "deterministic gate" in prompt

    def test_no_warning_for_non_completion_task(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        task = {"task": {"title": "rename a variable", "objective": "rename"}}
        p = tmp_path / "active-task_nc.json"
        json.dump(task, p.open("w"))
        prompt = task_prompt(p)
        assert "Continuation policy" not in prompt

    def test_policy_documented_in_skill_md(self):
        skill = Path(__file__).resolve().parent.parent / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        assert "Continuation Policy" in text
        assert "tier-2 review/critic" in text
        assert "Do not pair native" in text or "Do NOT pair native" in text


class TestCacheDriftAndDirectEntry:

    def test_cache_drift_zero(self):
        """Source plugin.json version must equal the installed cache version."""
        plugin_json = Path(
            "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/.claude-plugin/plugin.json"
        )
        src_version = json.loads(plugin_json.read_text(encoding="utf-8"))["version"]
        cache_root = Path("C:/Users/brsth/.claude/plugins/cache/local/cc-skills-sdlc")
        if cache_root.exists():
            cache_versions = [p.name for p in cache_root.iterdir() if p.is_dir()]
            assert src_version in cache_versions, (
                f"cache drift: source={src_version}, cache has {cache_versions}"
            )
            # No stale versions beside the current one.
            assert cache_versions == [src_version], (
                f"stale cache dirs remain: {cache_versions}"
            )

    def test_direct_entry_exception_documented(self):
        """CLAUDE.md documents the direct-entry exception + dormant gate warning."""
        claude_md = Path(
            "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/CLAUDE.md"
        )
        text = claude_md.read_text(encoding="utf-8")
        assert "Direct-entry exception" in text
        assert "Stop[3]" in text
        assert "temporary" in text or "pending dispatch reconciliation" in text
        assert "Stop_enforce_gate" in text  # dormant gate not to revive
        assert "task #1053" in text or "#1053" in text


# ---------------------------------------------------------------------------
# Continuation gate: registration check
# ---------------------------------------------------------------------------

class TestContinuationGateRegistration:

    def test_gate_script_exists(self):
        gate_path = Path(__file__).resolve().parent.parent / "scripts" / "go_continuation_gate.py"
        assert gate_path.exists()

    def test_gate_registered_in_settings(self):
        settings_path = Path("P:/.claude/settings.json")
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            stop = data.get("hooks", {}).get("Stop", [])
            gate_cmd = "go_continuation_gate.py"
            found = any(
                gate_cmd in h.get("command", "")
                for entry in stop
                for h in entry.get("hooks", [])
            )
            assert found, "go_continuation_gate.py not registered in settings.json Stop hooks"