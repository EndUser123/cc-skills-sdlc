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
    """Pointer-bound, session-id-only, stale-immune Stop contract."""

    @pytest.fixture
    def gate_env(self, tmp_path, monkeypatch):
        """Set up pointer dir + state dir, patch ARTIFACTS_ROOT."""
        import go_continuation_gate as mod
        monkeypatch.setattr(mod, "ARTIFACTS_ROOT", tmp_path)
        sessions_dir = tmp_path / "go-sessions"
        sessions_dir.mkdir(parents=True)
        state_dir = tmp_path / "state" / "go"
        state_dir.mkdir(parents=True)
        return mod, sessions_dir, state_dir

    def _write_pointer(self, sessions_dir, session_id, state_dir, run_id="run1"):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        (sessions_dir / f"{session_id}.json").write_text(json.dumps({
            "go_state_dir": str(state_dir),
            "run_id": run_id,
            "updated_at": now,
        }), encoding="utf-8")

    def _write_task(self, state_dir, run_id="run1", title="t", status="selected"):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        (state_dir / f"active-task_{run_id}.json").write_text(json.dumps({
            "run_id": run_id, "session_id": "",
            "selected_at": now, "created_at": now, "updated_at": now, "state_version": 1,
            "task": {"title": title, "status": status},
        }), encoding="utf-8")

    def test_no_session_id_silent(self, gate_env):
        """No session_id in payload -> None (absent identity)."""
        mod, _, _ = gate_env
        assert mod.check_go_completion({}) is None
        assert mod.check_go_completion({"session_id": ""}) is None

    def test_no_pointer_silent(self, gate_env):
        """session_id with no pointer file -> None."""
        mod, _, _ = gate_env
        assert mod.check_go_completion({"session_id": "no-such-id"}) is None

    def test_matching_active_blocks(self, gate_env):
        """Pointer -> state dir -> active task (not done) -> BLOCK."""
        mod, sd, td = gate_env
        self._write_pointer(sd, "sess-aaa", td, "run1")
        self._write_task(td, "run1", title="fix hook gate")
        r = mod.check_go_completion({"session_id": "sess-aaa"})
        assert r is not None
        assert r["decision"] == "block"
        assert "continue:" in r["reason"]
        assert "fix hook gate" in r["reason"]

    def test_matching_done_silent(self, gate_env):
        """Pointer -> active task with .pr_ready -> None (done, silent)."""
        mod, sd, td = gate_env
        self._write_pointer(sd, "sess-aaa", td, "run1")
        self._write_task(td, "run1")
        (td / ".pr_ready_run1").touch()
        assert mod.check_go_completion({"session_id": "sess-aaa"}) is None

    def test_matching_done_status_silent(self, gate_env):
        """Pointer -> active task with status=completed -> None."""
        mod, sd, td = gate_env
        self._write_pointer(sd, "sess-aaa", td, "run1")
        self._write_task(td, "run1", status="completed")
        assert mod.check_go_completion({"session_id": "sess-aaa"}) is None

    def test_foreign_session_silent(self, gate_env):
        """Pointer for session X; payload carries session Y -> None."""
        mod, sd, td = gate_env
        self._write_pointer(sd, "sess-aaa", td, "run1")
        self._write_task(td, "run1")
        assert mod.check_go_completion({"session_id": "sess-bbb"}) is None

    def test_stale_pointer_silent(self, gate_env):
        """Pointer updated >6h ago -> None (abandoned run)."""
        mod, sd, td = gate_env
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        (sd / "sess-aaa.json").write_text(json.dumps({
            "go_state_dir": str(td), "run_id": "run1", "updated_at": old,
        }), encoding="utf-8")
        self._write_task(td, "run1")
        assert mod.check_go_completion({"session_id": "sess-aaa"}) is None

    def test_two_sessions_no_cross_block(self, gate_env):
        """Two concurrent sessions with separate pointers -> no cross-block."""
        mod, sd, td = gate_env
        # Session A: active (should block).
        td_a = td / "a"; td_a.mkdir()
        self._write_pointer(sd, "sess-A", td_a, "runA")
        self._write_task(td_a, "runA", title="session A work")
        # Session B: done (should be silent).
        td_b = td / "b"; td_b.mkdir()
        self._write_pointer(sd, "sess-B", td_b, "runB")
        self._write_task(td_b, "runB")
        (td_b / ".pr_ready_runB").touch()
        # Gate for session A blocks.
        r_a = mod.check_go_completion({"session_id": "sess-A"})
        assert r_a is not None and r_a["decision"] == "block"
        # Gate for session B is silent.
        assert mod.check_go_completion({"session_id": "sess-B"}) is None

    def test_blocked_refines_reason(self, gate_env):
        """.blocked_* present refines the 'continue:' reason string."""
        mod, sd, td = gate_env
        self._write_pointer(sd, "sess-aaa", td, "run1")
        self._write_task(td, "run1", title="deploy")
        (td / ".blocked_run1").touch()
        (td / "blocked_blocked_run1.json").write_text(
            json.dumps({"reason_code": "dispatch_failed"}), encoding="utf-8")
        r = mod.check_go_completion({"session_id": "sess-aaa"})
        assert r is not None and "dispatch_failed" in r["reason"]

    def test_no_env_identity_or_mtime_binding(self):
        """Grep gate source: no os.environ or mtime used for identity binding."""
        gate_src = Path(__file__).resolve().parent.parent / "scripts" / "go_continuation_gate.py"
        text = gate_src.read_text(encoding="utf-8")
        # No _terminal_id, no WT_SESSION, no env-based identity binding.
        assert "_terminal_id" not in text
        assert "WT_SESSION" not in text
        # ARTIFACTS_ROOT *location* override (GO_ARTIFACTS_ROOT) is allowed —
        # it selects where pointers live, not who the caller is. Identity
        # (session/terminal) must come from the payload, never from env.
        for identity_key in ("CLAUDE_SESSION_ID", "CLAUDE_AGENT_SESSION_ID"):
            assert identity_key not in text
        # No mtime-based selection.
        assert "st_mtime" not in text


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

    def test_no_unconditional_allow_print(self, run_gate):
        """Malformed/empty payload still emits nothing."""
        out, _, rc = run_gate(payload="")
        assert out == "" and rc == 0
        out, _, _ = run_gate(payload="not json")
        assert out == ""



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
        assert "Stop_enforce_gate" in text  # dormant gate not to revive
        assert "task #1053" in text or "#1053" in text

    def test_no_dead_gate_without_status(self):
        """Every G# row in the gate inventory carries an explicit Status."""
        inv = Path(__file__).resolve().parent.parent / "HOOK_GATE_INVENTORY.md"
        text = inv.read_text(encoding="utf-8")
        # Find table rows starting with "| G<n> |".
        import re
        rows = re.findall(r"^\|\s*(G\d+)\s*\|(.*)\|$", text, re.MULTILINE)
        assert rows, "no G# rows found in inventory"
        valid_statuses = ("live", "dormant-intentional",
                          "dormant-unverified", "deprecated")
        for gid, rest in rows:
            cells = [c.strip() for c in rest.split("|")]
            # cells: [path, status, reason, next_action]
            assert len(cells) >= 4, f"{gid} malformed row: {cells}"
            status = cells[1].strip("*`").strip().lower()
            assert any(status == v or status.startswith(v) for v in valid_statuses), (
                f"{gid} has unclassified status {status!r}; "
                f"must start with one of {valid_statuses}"
            )


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