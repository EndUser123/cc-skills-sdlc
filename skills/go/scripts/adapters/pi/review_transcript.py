#!/usr/bin/env python3
"""Summarize pi session transcript for subagent review.

Reads the JSONL session file from a pi --print run, extracts tool calls
and results, and produces a structured summary. Does NOT make gate
decisions — the subagent handles reasoning about quality.

Usage:
    Set GO_STATE_DIR and RUN_ID env vars.
    Reads pi-transcript_{RUN_ID}.jsonl from GO_STATE_DIR (or latest
    from GO_STATE_DIR/pi-sessions/).
    Writes pi-review_{RUN_ID}.json summary.

Always exits 0 (unless transcript not found). Gate decisions are
delegated to the Agent subagent in Step 2.5.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any


def parse_transcript(lines: list[str]) -> list[dict[str, Any]]:
    """Parse JSONL lines into message list."""
    messages: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def extract_tool_events(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract tool call/result pairs from transcript."""
    events: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("type") != "message":
            continue
        inner = msg.get("message", {})
        role = inner.get("role")

        if role == "assistant":
            for content in inner.get("content", []):
                if content.get("type") == "toolCall":
                    events.append({
                        "role": "toolCall",
                        "name": content.get("name", ""),
                        "arguments": content.get("arguments", {}),
                        "id": content.get("id", ""),
                    })

        if role == "toolResult":
            events.append({
                "role": "toolResult",
                "toolName": inner.get("toolName", ""),
                "isError": inner.get("isError", False),
                "content": inner.get("content", []),
                "toolCallId": inner.get("toolCallId", ""),
            })

    return events


def review(
    transcript_path: pathlib.Path,
    task: dict[str, Any],
) -> dict[str, Any]:
    """Summarize a pi transcript for subagent review.

    Returns dict with: warnings, tool_summary, files_read, files_written,
    total_tool_calls, transcript_tail, transcript_path.
    """
    text = transcript_path.read_text(encoding="utf-8")
    messages = parse_transcript(text.splitlines())
    events = extract_tool_events(messages)

    warnings: list[str] = []
    files_read: list[str] = []
    files_written: list[str] = []
    tool_errors: list[str] = []
    tool_counts: dict[str, int] = {}

    for event in events:
        name = event.get("name", "") or event.get("toolName", "")
        tool_counts[name] = tool_counts.get(name, 0) + 1

        if event["role"] == "toolCall":
            args = event.get("arguments", {})
            if name == "read":
                path = args.get("path", "")
                if path:
                    files_read.append(path)
            elif name == "write":
                path = args.get("path", "")
                if path:
                    files_written.append(path)
            elif name == "edit":
                path = args.get("path", "")
                if path:
                    files_written.append(path)

        if event["role"] == "toolResult":
            if event.get("isError"):
                tool_errors.append(f"{name}: {_extract_text(event.get('content', []))}")

    total_calls = sum(tool_counts.values())

    if files_written and not files_read:
        warnings.append("BLIND_WRITE: files written without any reads first")

    if total_calls > 50:
        warnings.append(f"EXCESSIVE_CALLS: {total_calls} tool calls (possible loop)")

    if not files_written:
        warnings.append("NO_FILES_WRITTEN: pi did not write any files")

    if tool_errors:
        warnings.append(f"TOOL_ERRORS: {len(tool_errors)} tool errors: {tool_errors[:3]}")

    forbidden = task.get("forbidden_files", [])
    for f in files_written:
        for ff in forbidden:
            if ff in f:
                warnings.append(f"FORBIDDEN_FILE: pi modified forbidden file '{f}'")

    scope_in = task.get("scope_in", [])
    if scope_in:
        touched = set(files_read + files_written)
        untouched = [f for f in scope_in if not any(f in t for t in touched)]
        if untouched:
            warnings.append(f"SCOPE_UNTOUCHED: scope_in files not read: {untouched[:3]}")

    # Extract last 20 lines as tail for subagent context
    all_lines = text.splitlines()
    tail = "\n".join(all_lines[-20:])

    return {
        "warnings": warnings,
        "tool_summary": tool_counts,
        "files_read": files_read,
        "files_written": files_written,
        "total_tool_calls": total_calls,
        "transcript_tail": tail,
        "transcript_path": str(transcript_path),
        "total_lines": len(all_lines),
    }


def _extract_text(content: list[dict[str, Any]]) -> str:
    """Extract text from a content array."""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "; ".join(parts)[:200]


def main() -> None:
    state_dir = pathlib.Path(os.environ.get("GO_STATE_DIR", ""))
    run_id = os.environ.get("RUN_ID", "unknown")

    # Find transcript: either named file or latest session
    transcript = state_dir / f"pi-transcript_{run_id}.jsonl"
    if not transcript.exists():
        session_dir = state_dir / "pi-sessions"
        if session_dir.exists():
            jsonl_files = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if jsonl_files:
                transcript = jsonl_files[0]

    if not transcript.exists():
        print(f"ERROR: no transcript found for run {run_id}", file=sys.stderr)
        sys.exit(1)

    # Load task for scope/forbidden checks
    task_file = state_dir / f"active-task_{run_id}.json"
    task: dict[str, Any] = {}
    if task_file.exists():
        data = json.loads(task_file.read_text(encoding="utf-8"))
        task = data.get("task", data)

    result = review(transcript, task)

    # Write summary
    out = state_dir / f"pi-review_{run_id}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)

    print(f"SUMMARY: {out}")
    if result["warnings"]:
        print(f"  {len(result['warnings'])} signals: {result['warnings']}")
    else:
        print("  no signals detected")


if __name__ == "__main__":
    main()
