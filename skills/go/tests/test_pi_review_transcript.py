"""Tests for review_transcript.py — pi session transcript summarizer.

The summarizer extracts structure (tool calls, files, warnings) but does NOT
make gate decisions — that's the subagent's job.
"""

from __future__ import annotations

import json
import importlib.util
import pathlib
import sys


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
_REVIEW_TRANSCRIPT = _load_module(
    "go_pi_review_transcript",
    PACKAGE / "scripts" / "adapters" / "pi" / "review_transcript.py",
)
parse_transcript = _REVIEW_TRANSCRIPT.parse_transcript
extract_tool_events = _REVIEW_TRANSCRIPT.extract_tool_events
review = _REVIEW_TRANSCRIPT.review
_git_diff_name_only = _REVIEW_TRANSCRIPT._git_diff_name_only
_extract_text = _REVIEW_TRANSCRIPT._extract_text
_resolve_worktree = _REVIEW_TRANSCRIPT._resolve_worktree
_edits_target_path = _REVIEW_TRANSCRIPT._edits_target_path
_tool_args = _REVIEW_TRANSCRIPT._tool_args


def _make_session_header() -> str:
    return json.dumps({"type": "session", "version": 3, "id": "test"}) + "\n"


def _make_tool_call(name: str, arguments: dict, call_id: str = "call_1") -> str:
    return json.dumps({
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [{"type": "toolCall", "name": name, "arguments": arguments, "id": call_id}],
        },
    }) + "\n"


def _make_tool_result(
    tool_name: str, call_id: str = "call_1", is_error: bool = False, text: str = "ok"
) -> str:
    return json.dumps({
        "type": "message",
        "message": {
            "role": "toolResult",
            "toolName": tool_name,
            "toolCallId": call_id,
            "isError": is_error,
            "content": [{"type": "text", "text": text}],
        },
    }) + "\n"


class TestParseTranscript:
    def test_valid_jsonl(self, tmp_path: pathlib.Path) -> None:
        lines = [_make_session_header(), _make_tool_call("read", {"path": "a.py"})]
        result = parse_transcript(lines)
        assert len(result) == 2

    def test_skips_blank_and_invalid(self) -> None:
        lines = ["\n", "not json\n", json.dumps({"type": "session"}) + "\n"]
        result = parse_transcript(lines)
        assert len(result) == 1  # only the valid JSON


class TestExtractToolEvents:
    def test_extracts_read_and_write(self) -> None:
        messages = [
            json.loads(_make_tool_call("read", {"path": "src/a.py"}, "c1")),
            json.loads(_make_tool_result("read", "c1", text="contents")),
            json.loads(_make_tool_call("write", {"path": "src/b.py", "content": "x"}, "c2")),
            json.loads(_make_tool_result("write", "c2", text="ok")),
        ]
        events = extract_tool_events(messages)
        assert len(events) == 4
        assert events[0]["name"] == "read"
        assert events[2]["name"] == "write"

    def test_ignores_non_tool_content(self) -> None:
        msg = {"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]}}
        events = extract_tool_events([msg])
        assert events == []

    def test_extracts_pi_json_mode_tool_events(self) -> None:
        messages = [
            {
                "type": "tool_execution_start",
                "toolName": "read",
                "input": {"path": "src/a.py"},
                "id": "c1",
            },
            {
                "type": "tool_execution_start",
                "toolName": "edit",
                "input": {"path": "src/a.py", "old": "x", "new": "y"},
                "id": "c2",
            },
            {
                "type": "tool_execution_result",
                "toolName": "edit",
                "id": "c2",
                "isError": False,
                "content": [{"type": "text", "text": "ok"}],
            },
        ]

        events = extract_tool_events(messages)

        assert events[0]["role"] == "toolCall"
        assert events[0]["name"] == "read"
        assert events[1]["name"] == "edit"
        assert events[2]["role"] == "toolResult"


class TestReview:
    def test_clean_transcript_no_warnings(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            _make_session_header()
            + _make_tool_call("read", {"path": "src/a.py"}, "c1")
            + _make_tool_result("read", "c1")
            + _make_tool_call("write", {"path": "src/a.py", "content": "fixed"}, "c2")
            + _make_tool_result("write", "c2")
        )
        result = review(transcript, {})
        assert result["warnings"] == []
        assert "src/a.py" in result["files_read"]
        assert "src/a.py" in result["files_written"]
        assert "transcript_tail" in result
        assert "total_lines" in result
        assert "transcript_path" in result

    def test_blind_write_detected(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            _make_session_header()
            + _make_tool_call("write", {"path": "src/a.py", "content": "x"}, "c1")
            + _make_tool_result("write", "c1")
        )
        result = review(transcript, {})
        assert any("BLIND_WRITE" in w for w in result["warnings"])

    def test_no_files_written_detected(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            _make_session_header()
            + _make_tool_call("read", {"path": "src/a.py"}, "c1")
            + _make_tool_result("read", "c1")
        )
        result = review(transcript, {})
        assert any("NO_FILES_WRITTEN" in w for w in result["warnings"])

    def test_forbidden_file_detected(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            _make_session_header()
            + _make_tool_call("read", {"path": "src/a.py"}, "c1")
            + _make_tool_result("read", "c1")
            + _make_tool_call("write", {"path": "secrets.env", "content": "key=val"}, "c2")
            + _make_tool_result("write", "c2")
        )
        task = {"forbidden_files": ["secrets.env"]}
        result = review(transcript, task)
        assert any("FORBIDDEN_FILE" in w for w in result["warnings"])

    def test_excessive_calls_warning(self, tmp_path: pathlib.Path) -> None:
        lines = [_make_session_header()]
        for i in range(55):
            cid = f"c{i}"
            lines.append(_make_tool_call("read", {"path": f"f{i}.py"}, cid))
            lines.append(_make_tool_result("read", cid))
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("".join(lines))
        result = review(transcript, {})
        assert any("EXCESSIVE_CALLS" in w for w in result["warnings"])

    def test_tool_errors_reported(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            _make_session_header()
            + _make_tool_call("write", {"path": "a.py", "content": "x"}, "c1")
            + _make_tool_result("write", "c1", is_error=True, text="permission denied")
        )
        result = review(transcript, {})
        assert any("TOOL_ERRORS" in w for w in result["warnings"])

    def test_scope_untouched_warning(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            _make_session_header()
            + _make_tool_call("read", {"path": "other.py"}, "c1")
            + _make_tool_result("read", "c1")
            + _make_tool_call("write", {"path": "other.py", "content": "x"}, "c2")
            + _make_tool_result("write", "c2")
        )
        task = {"scope_in": ["target.py"]}
        result = review(transcript, task)
        assert any("SCOPE_UNTOUCHED" in w for w in result["warnings"])

    def test_edit_counts_as_write(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            _make_session_header()
            + _make_tool_call("read", {"path": "a.py"}, "c1")
            + _make_tool_result("read", "c1")
            + _make_tool_call("edit", {"path": "a.py", "old": "x", "new": "y"}, "c2")
            + _make_tool_result("edit", "c2")
        )
        result = review(transcript, {})
        assert "a.py" in result["files_written"]

    def test_pi_json_mode_events_count_as_read_and_write(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "session", "id": "sess"}) + "\n"
            + json.dumps({"type": "tool_execution_start", "toolName": "read", "input": {"path": "a.py"}}) + "\n"
            + json.dumps({"type": "tool_execution_start", "toolName": "edit", "input": {"path": "a.py"}}) + "\n",
            encoding="utf-8",
        )

        result = review(transcript, {})

        assert result["warnings"] == []
        assert "a.py" in result["files_read"]
        assert "a.py" in result["files_written"]

    def test_real_pi_args_key_with_edits_list(self, tmp_path: pathlib.Path) -> None:
        """Real pi/llama-cpp emits ``args`` (not ``input``) and ``edit`` calls
        carry ``args.edits=[{oldText,newText}]`` with the file path at
        ``args.path``. This shape caused the historic NO_FILES_WRITTEN false
        negative."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "session", "id": "sess"}) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "read",
                "toolCallId": "c1",
                "args": {"path": "/repo/SKILL.md", "offset": 0, "limit": 200},
            }) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "edit",
                "toolCallId": "c2",
                "args": {
                    "path": "/repo/SKILL.md",
                    "edits": [{
                        "oldText": "old row\n",
                        "newText": "old row\nnew row\n",
                    }],
                },
            }) + "\n",
            encoding="utf-8",
        )

        result = review(transcript, {})

        assert not any("NO_FILES_WRITTEN" in w for w in result["warnings"]), result["warnings"]
        assert "/repo/SKILL.md" in result["files_written"], result["files_written"]
        assert "/repo/SKILL.md" in result["files_read"], result["files_read"]

    def test_transcript_claiming_edit_without_worktree_diff_still_no_files_written(
        self, tmp_path: pathlib.Path
    ) -> None:
        """A transcript that *claims* an edit but the task worktree has no
        real diff must still produce ``NO_FILES_WRITTEN``. Transcript prose
        is not authoritative for an edit that has not landed on disk."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "session", "id": "sess"}) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "edit",
                "toolCallId": "c2",
                "args": {"path": "/tmp/nonexistent/SKILL.md", "edits": []},
            }) + "\n",
            encoding="utf-8",
        )

        # Empty path -> no worktree_diff_paths, transcript path also absent.
        worktree = tmp_path / "empty_repo"
        worktree.mkdir()
        result = review(transcript, {}, worktree=str(worktree))

        assert any("NO_FILES_WRITTEN" in w for w in result["warnings"]), result["warnings"]

    def test_worktree_diff_authority_overrides_transcript_claim(
        self, tmp_path: pathlib.Path
    ) -> None:
        """When the transcript says NO write but the worktree's git diff vs
        HEAD shows a real change, the diff wins. This is the LOCAL_ORNITH
        regression: the edit really happened on disk; the transcript parser
        must not veto it."""
        # Set up a temporary git repo with one committed file, then modify it
        # on disk (uncommitted). No transcript tool-call events for the edit.
        repo = tmp_path / "repo"
        repo.mkdir()
        import subprocess

        def run(args, cwd=str(repo)):
            return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)

        run(["git", "init", "--quiet", "-b", "main"])
        run(["git", "config", "user.email", "t@t"])
        run(["git", "config", "user.name", "t"])
        (repo / "SKILL.md").write_text("original line\n", encoding="utf-8")
        run(["git", "add", "SKILL.md"])
        run(["git", "commit", "--quiet", "-m", "initial"])
        # Modify on disk without committing.
        (repo / "SKILL.md").write_text("original line\nnew line\n", encoding="utf-8")

        transcript = tmp_path / "transcript.jsonl"
        # Transcript carries ONLY read events — no edit events at all. The
        # authoritative write signal is the worktree diff.
        transcript.write_text(
            json.dumps({"type": "session", "id": "sess"}) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "read",
                "toolCallId": "c1",
                "args": {"path": str(repo / "SKILL.md")},
            }) + "\n",
            encoding="utf-8",
        )

        result = review(transcript, {}, worktree=str(repo))

        assert not any("NO_FILES_WRITTEN" in w for w in result["warnings"]), result["warnings"]
        assert result["_worktree_resolved"] == str(repo)
        assert "SKILL.md" in result["files_written"]
        # The transcript tool_calls did not include any edit, so
        # _transcript_files_written is empty — proving the diff is the
        # source of truth, not the transcript.
        assert result["_transcript_files_written"] == []
        assert result["files_written"] == result["_worktree_diff_paths"]

    def test_no_worktree_no_change_keeps_no_files_written_warning(self, tmp_path: pathlib.Path) -> None:
        """Without a worktree AND with no edit events, the warning must
        still fire (existing behavior). Ensures the override is opt-in."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "session", "id": "sess"}) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "read",
                "toolCallId": "c1",
                "args": {"path": "a.py"},
            }) + "\n",
            encoding="utf-8",
        )

        result = review(transcript, {})  # no worktree

        assert any("NO_FILES_WRITTEN" in w for w in result["warnings"])

    def test_unresolvable_worktree_emits_worktree_diff_unavailable(
        self, tmp_path: pathlib.Path
    ) -> None:
        """When the worktree path is given but is not a real git checkout,
        the reviewer must surface ``WORKTREE_DIFF_UNAVAILABLE`` rather than
        silently reporting no writes."""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "session", "id": "sess"}) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "edit",
                "toolCallId": "c2",
                "args": {"path": "x", "edits": []},
            }) + "\n",
            encoding="utf-8",
        )

        # Pass a path that is not a directory.
        result = review(transcript, {}, worktree=str(tmp_path / "no_such_path"))

        # No worktree resolved -> no override, transcript's edit-with-no-args
        # path is empty -> NO_FILES_WRITTEN still fires (expected: no evidence
        # the edit actually landed).
        assert any("NO_FILES_WRITTEN" in w for w in result["warnings"])

    def test_resolve_worktree_requires_existing_dir_and_manifest(self, tmp_path: pathlib.Path) -> None:
        """_resolve_worktree returns None when no manifest OR when the path
        doesn't resolve to a directory."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        # No manifest -> None
        assert _resolve_worktree(state_dir, "missing_run") is None
        # Manifest points at a non-existent dir -> None
        manifest = state_dir / "worktree-run1.json"
        manifest.write_text(json.dumps({"worktree": str(tmp_path / "nope")}), encoding="utf-8")
        assert _resolve_worktree(state_dir, "run1") is None
        # Manifest with a real dir -> returns the path
        good_dir = tmp_path / "real_worktree"
        good_dir.mkdir()
        manifest.write_text(json.dumps({"worktree": str(good_dir)}), encoding="utf-8")
        assert _resolve_worktree(state_dir, "run1") == str(good_dir)

    def test_preserved_ornith_transcript_replay_detects_skill_md(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Faithful replay of the real LOCAL_ORNITH transcript shape, paired
        with a worktree that contains the SKILL.md edit, must classify
        the run as 'wrote files' (no NO_FILES_WRITTEN warning) and must
        resolve scope_in against the diff."""
        # Real transcript is large; ship an excerpt that contains the
        # edit-event shape AND the bash-verify tail that pi emits.
        transcript = tmp_path / "ornith-transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "session", "id": "ornith"}) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "read",
                "toolCallId": "r1",
                "args": {"path": "/worktree/SKILL.md", "offset": 0, "limit": 200},
            }) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "edit",
                "toolCallId": "e1",
                "args": {
                    "path": "/worktree/SKILL.md",
                    "edits": [{
                        "oldText": "| `GLM-5.2` | `zai/glm-5.2` | Z.ai |\n\n`GO_MODEL_OVERRIDE`",
                        "newText": "| `GLM-5.2` | `zai/glm-5.2` | Z.ai |\n| `LOCAL_ORNITH` | `llama-cpp/ornith-1.0-9b` | local |\n| `OPENCODE_DEEPSEEK` | `opencode-go/deepseek-v4-flash` | OpenCode |\n\n`GO_MODEL_OVERRIDE`",
                    }],
                },
            }) + "\n"
            + json.dumps({
                "type": "tool_execution_start",
                "toolName": "bash",
                "toolCallId": "b1",
                "args": {"command": "python -c \"assert 'LOCAL_ORNITH' in open('SKILL.md').read()\" && echo OK"},
            }) + "\n",
            encoding="utf-8",
        )

        # Create a real worktree-like repo with the edit on disk.
        repo = tmp_path / "ornith_worktree"
        repo.mkdir()
        import subprocess
        run = lambda *a: subprocess.run(a, cwd=str(repo), capture_output=True, text=True, timeout=10)
        run("git", "init", "--quiet", "-b", "main")
        run("git", "config", "user.email", "t@t")
        run("git", "config", "user.name", "t")
        (repo / "SKILL.md").write_text(
            "| `M3` | `minimax/MiniMax-M3` | MiniMax |\n"
            "| `GLM-5.2` | `zai/glm-5.2` | Z.ai |\n\n"
            "`GO_MODEL_OVERRIDE` bypasses classification and is passed through as the pi model flag.\n",
            encoding="utf-8",
        )
        run("git", "add", "SKILL.md")
        run("git", "commit", "--quiet", "-m", "init")
        (repo / "SKILL.md").write_text(
            "| `M3` | `minimax/MiniMax-M3` | MiniMax |\n"
            "| `GLM-5.2` | `zai/glm-5.2` | Z.ai |\n"
            "| `LOCAL_ORNITH` | `llama-cpp/ornith-1.0-9b` | local |\n"
            "| `OPENCODE_DEEPSEEK` | `opencode-go/deepseek-v4-flash` | OpenCode |\n\n"
            "`GO_MODEL_OVERRIDE` bypasses classification and is passed through as the pi model flag.\n",
            encoding="utf-8",
        )

        result = review(transcript, {}, worktree=str(repo))

        assert not any("NO_FILES_WRITTEN" in w for w in result["warnings"]), result["warnings"]
        assert not any("SCOPE_UNTOUCHED" in w for w in result["warnings"]), result["warnings"]
        assert "SKILL.md" in result["files_written"]
