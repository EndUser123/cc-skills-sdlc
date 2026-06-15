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
