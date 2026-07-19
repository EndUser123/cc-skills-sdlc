"""Tests for wiki_ingest.py — post-write pipeline orchestrator.

Subprocess calls are exercised via real `python -c` commands where deterministic;
pipeline ordering tests monkeypatch `run_subprocess` and `step_verify` to isolate
the orchestration logic.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import wiki_ingest as wi


# ---------- step_verify ----------

class TestStepVerify:
    def test_returns_error_when_page_missing(self, tmp_path):
        page = tmp_path / "nonexistent.md"
        result = wi.step_verify(page)
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_returns_error_when_page_empty(self, tmp_path):
        page = tmp_path / "empty.md"
        page.write_text("", encoding="utf-8")
        result = wi.step_verify(page)
        assert result["ok"] is False
        assert "empty" in result["error"]

    def test_returns_error_when_only_whitespace(self, tmp_path):
        page = tmp_path / "ws.md"
        page.write_text("   \n\n  \n", encoding="utf-8")
        result = wi.step_verify(page)
        assert result["ok"] is False

    def test_returns_error_when_no_frontmatter_title(self, tmp_path):
        page = tmp_path / "no-title.md"
        page.write_text("---\nsummary: no title here\n---\nbody\n", encoding="utf-8")
        result = wi.step_verify(page)
        assert result["ok"] is False
        assert "title" in result["error"]

    def test_returns_error_when_no_frontmatter_at_all(self, tmp_path):
        page = tmp_path / "no-fm.md"
        page.write_text("just body, no frontmatter\n", encoding="utf-8")
        result = wi.step_verify(page)
        assert result["ok"] is False
        assert "title" in result["error"]

    def test_returns_ok_with_size_when_valid(self, tmp_path):
        page = tmp_path / "valid.md"
        page.write_text('---\ntitle: Valid Page\nsummary: x\n---\nbody content\n',
                        encoding="utf-8")
        result = wi.step_verify(page)
        assert result["ok"] is True
        assert result["size"] > 0


# ---------- run_subprocess (real commands) ----------

class TestRunSubprocess:
    def test_returns_ok_for_successful_command(self):
        result = wi.run_subprocess(
            [sys.executable, "-c", "print('hello')"], timeout=10
        )
        assert result["ok"] is True
        assert result["exit"] == 0
        assert "hello" in result["stdout_tail"]

    def test_returns_not_ok_for_failing_command(self):
        result = wi.run_subprocess(
            [sys.executable, "-c", "import sys; sys.exit(2)"], timeout=10
        )
        assert result["ok"] is False
        assert result["exit"] == 2

    def test_returns_error_for_nonexistent_binary(self):
        result = wi.run_subprocess(
            ["nonexistent-binary-xyz-12345"], timeout=5
        )
        assert result["ok"] is False
        assert "not found" in result["error"].lower() or "error" in result["error"].lower()

    def test_returns_timeout_error(self):
        # Command that sleeps longer than the timeout
        result = wi.run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(5)"], timeout=1
        )
        assert result["ok"] is False
        assert "timeout" in result["error"].lower()

    def test_stdout_tail_is_truncated(self):
        # Generate lots of output and verify it's truncated
        result = wi.run_subprocess(
            [sys.executable, "-c", "print('x' * 1000)"], timeout=10
        )
        assert result["ok"] is True
        assert len(result["stdout_tail"]) <= 303  # 300 char cap + newline slack


# ---------- pipeline ordering ----------

class TestPipelineOrdering:
    def _make_valid_page(self, tmp_path):
        page = tmp_path / "valid.md"
        page.write_text('---\ntitle: Valid\nsummary: x\n---\nbody\n', encoding="utf-8")
        return page

    def test_verify_failure_skips_remaining_steps(self, tmp_path, monkeypatch):
        # Point at a missing page
        missing = tmp_path / "missing.md"
        call_order = []
        def fake_run(cmd, timeout):
            call_order.append(cmd[0] if cmd else "?")
            return {"ok": True, "exit": 0, "stdout_tail": "", "stderr_tail": ""}
        monkeypatch.setattr(wi, "run_subprocess", fake_run)
        rc = wi.main(["--post-write", str(missing)])
        assert rc == 1
        # No subprocess calls should have happened
        assert call_order == []

    def test_skip_qmd_skips_step2_only(self, tmp_path, monkeypatch):
        page = self._make_valid_page(tmp_path)
        called_commands = []
        def fake_run(cmd, timeout):
            called_commands.append(cmd)
            return {"ok": True, "exit": 0, "stdout_tail": "", "stderr_tail": ""}
        monkeypatch.setattr(wi, "run_subprocess", fake_run)
        rc = wi.main(["--post-write", str(page), "--skip-qmd"])
        # Step 2 (qmd) should not appear in called commands
        for cmd in called_commands:
            assert "qmd" not in cmd or cmd[0] != "qmd"
        # Other steps should still have been called
        # (auto-link uses 'python', contradiction uses 'python', log_append uses 'python')
        python_calls = [c for c in called_commands if c[0] == sys.executable or c[0] == "python"]
        assert len(python_calls) >= 2  # at least auto-link + log-append

    def test_overall_failure_when_any_step_fails(self, tmp_path, monkeypatch):
        page = self._make_valid_page(tmp_path)
        def fake_run(cmd, timeout):
            # Simulate qmd failing
            if cmd[0] == "qmd":
                return {"ok": False, "exit": 1, "stdout_tail": "", "stderr_tail": "fail"}
            return {"ok": True, "exit": 0, "stdout_tail": "", "stderr_tail": ""}
        monkeypatch.setattr(wi, "run_subprocess", fake_run)
        rc = wi.main(["--post-write", str(page)])
        assert rc == 1  # overall failure

    def test_overall_success_when_all_steps_pass(self, tmp_path, monkeypatch):
        page = self._make_valid_page(tmp_path)
        def fake_run(cmd, timeout):
            return {"ok": True, "exit": 0, "stdout_tail": "", "stderr_tail": ""}
        monkeypatch.setattr(wi, "run_subprocess", fake_run)
        rc = wi.main(["--post-write", str(page), "--skip-qmd"])
        assert rc == 0

    def test_remaining_steps_run_after_failure(self, tmp_path, monkeypatch, capsys):
        page = self._make_valid_page(tmp_path)
        called = []
        def fake_run(cmd, timeout):
            called.append(cmd[0])
            # First python call (auto-link) fails; later ones succeed
            if "wiki_after_write" in " ".join(cmd):
                return {"ok": False, "exit": 1, "stdout_tail": "", "stderr_tail": "fail"}
            return {"ok": True, "exit": 0, "stdout_tail": "", "stderr_tail": ""}
        monkeypatch.setattr(wi, "run_subprocess", fake_run)
        wi.main(["--post-write", str(page), "--skip-qmd"])
        # Even though auto-link failed, contradiction + log_append should still run
        # (we can't easily filter by script name from cmd[0] alone, but we can check
        # that we got multiple python calls — at least 2 of the 3 python steps ran)
        python_call_count = sum(1 for c in called if c in (sys.executable, "python"))
        assert python_call_count >= 2


# ---------- CLI ----------

class TestCLI:
    def test_help_works(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            wi.main(["--help"])
        assert exc_info.value.code == 0

    def test_missing_post_write_arg_errors(self):
        with pytest.raises(SystemExit) as exc_info:
            wi.main([])
        assert exc_info.value.code == 2  # argparse error code

    def test_output_is_valid_json(self, tmp_path, monkeypatch):
        page = tmp_path / "p.md"
        page.write_text('---\ntitle: T\n---\n', encoding="utf-8")
        monkeypatch.setattr(wi, "run_subprocess",
                            lambda cmd, timeout: {"ok": True, "exit": 0,
                                                  "stdout_tail": "", "stderr_tail": ""})
        # Capture stdout
        import io
        captured = io.StringIO()
        orig_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = wi.main(["--post-write", str(page), "--skip-qmd"])
        finally:
            sys.stdout = orig_stdout
        out = captured.getvalue()
        data = json.loads(out)  # must not raise
        assert "ok" in data
        assert "page" in data
        assert "steps" in data
        assert set(data["steps"].keys()) == {
            "1_verify", "2_qmd_update", "3_auto_link",
            "4_contradiction", "5_log_append"
        }
