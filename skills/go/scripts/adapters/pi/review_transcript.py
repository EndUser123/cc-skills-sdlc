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


def _tool_args(msg: dict[str, Any]) -> dict[str, Any]:
    """Extract tool arguments from any of the keys pi/llama-cpp emits.

    Real pi streams use ``args``; older harnesses / tests use ``input`` or
    ``arguments``. Pick whichever is present and non-empty.
    """
    for key in ("args", "input", "arguments"):
        value = msg.get(key)
        if isinstance(value, dict) and value:
            return value
    return {}


def _edits_target_path(args: dict[str, Any]) -> str | None:
    """Return the filesystem path an ``edit``/``write`` tool-call targets.

    Real pi emits ``edit`` calls with ``edits=[{oldText, newText}]`` and the
    file path at the top level (``args.path``). Older harnesses put the
    path directly in arguments. A bare ``path`` with no payload (empty
    ``edits`` / no ``content``) is treated as *no change* and returns None —
    an edit tool-call that carries no diff did not write anything.

    Note: the authoritative ``files_written`` source remains the task
    worktree's ``git diff --name-only`` (see ``review``); this helper only
    supplies the transcript-derived fallback signal.
    """
    path = args.get("path")
    has_path = isinstance(path, str) and bool(path)
    has_payload = False
    for key in ("edits", "content", "newText", "oldText"):
        value = args.get(key)
        if value:  # non-empty list / non-empty string
            has_payload = True
            break
    if not has_payload:
        # Fall back to per-edit path inside an ``edits`` list (rare shape).
        edits = args.get("edits")
        if isinstance(edits, list) and edits:
            first = edits[0]
            if isinstance(first, dict):
                inner_path = first.get("path")
                if isinstance(inner_path, str) and inner_path:
                    return inner_path
        return None
    return path if has_path else None


def extract_tool_events(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract tool call/result pairs from transcript."""
    events: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("type") == "tool_execution_start":
            arguments = _tool_args(msg)
            events.append({
                "role": "toolCall",
                "name": msg.get("toolName", msg.get("tool", "")),
                "arguments": arguments,
                "id": msg.get("id", msg.get("toolCallId", "")),
            })
            continue

        if msg.get("type") == "tool_execution_result":
            events.append({
                "role": "toolResult",
                "toolName": msg.get("toolName", msg.get("tool", "")),
                "isError": msg.get("isError", msg.get("is_error", False)),
                "content": msg.get("content", []),
                "toolCallId": msg.get("toolCallId", msg.get("id", "")),
            })
            continue

        if msg.get("type") != "message":
            continue
        inner = msg.get("message", {})
        role = inner.get("role")

        if role == "assistant":
            for content in inner.get("content", []):
                if content.get("type") == "toolCall":
                    arguments = content.get("arguments") or {}
                    events.append({
                        "role": "toolCall",
                        "name": content.get("name", ""),
                        "arguments": arguments,
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
    worktree: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Summarize a pi transcript for subagent review.

    Returns dict with: warnings, tool_summary, files_read, files_written,
    total_tool_calls, transcript_tail, transcript_path.

    Authority for ``files_written`` (highest first):
        1. ``git -C <worktree> diff --name-only HEAD`` — actual filesystem state.
        2. Tool-call ``args.path`` / ``args.edits[].path`` from the transcript.
        3. ``input.path`` / ``arguments.path`` legacy keys (back-compat).

    When ``worktree`` resolves to a real git worktree, the diff result
    *replaces* the transcript-derived list rather than merging with it —
    transcript prose alone is not authoritative for an edit that has or has
    not landed on disk. ``files_read`` still derives from tool-call args
    (the transcript is the only signal for what the model *attempted* to
    read); we do not claim a read against an un-touched worktree file.
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
            args = event.get("arguments", {}) or {}
            if name == "read":
                path = args.get("path", "")
                if path:
                    files_read.append(path)
            elif name in ("write", "edit"):
                path = _edits_target_path(args)
                if path:
                    files_written.append(path)

        if event["role"] == "toolResult":
            if event.get("isError"):
                tool_errors.append(f"{name}: {_extract_text(event.get('content', []))}")

    # Worktree-diff override: when a worktree path is provided AND resolves to
    # a real git worktree, trust the diff as the authoritative write set.
    # Transcript-derived paths are preserved under _transcript_files_written
    # so the caller can inspect both signals.
    worktree_str = str(worktree) if worktree else None
    worktree_resolved: pathlib.Path | None = None
    if worktree_str:
        candidate = pathlib.Path(worktree_str)
        if candidate.is_dir():
            worktree_resolved = candidate

    transcript_files_written = list(files_written)
    worktree_diff_paths: list[str] = []
    if worktree_resolved is not None:
        rc, diff_paths = _git_diff_name_only(worktree_resolved)
        if rc == 0:
            worktree_diff_paths = diff_paths
            if worktree_diff_paths:
                files_written = list(worktree_diff_paths)
        elif rc != 0:
            warnings.append(
                f"WORKTREE_DIFF_UNAVAILABLE: 'git -C {worktree_resolved} diff --name-only HEAD' failed (rc={rc}); "
                "using transcript-derived files_written as fallback"
            )

    total_calls = sum(tool_counts.values())

    if files_written and not files_read:
        # Worktree-diff authority suppresses BLIND_WRITE when the read path
        # simply wasn't captured in the transcript (the on-disk edit may
        # still be correct). Only flag when the worker also never read the
        # file in the transcript.
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
        "_transcript_files_written": transcript_files_written,
        "_worktree_diff_paths": worktree_diff_paths,
        "_worktree_resolved": str(worktree_resolved) if worktree_resolved else None,
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


def _resolve_worktree(state_dir: pathlib.Path, run_id: str) -> str | None:
    """Read the worktree path written by ``orchestrate.create_worktree``.

    Returns the path string when the artifact exists AND the worktree
    resolves to an existing directory; otherwise None (the reviewer will
    fall back to transcript-only detection and emit
    ``WORKTREE_DIFF_UNAVAILABLE`` if a follow-on git invocation fails —
    never silently substitutes the parent repo).
    """
    manifest = state_dir / f"worktree-{run_id}.json"
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    worktree = data.get("worktree") if isinstance(data, dict) else None
    if not isinstance(worktree, str) or not worktree:
        return None
    if not pathlib.Path(worktree).is_dir():
        return None
    return worktree


def _git_diff_name_only(worktree: pathlib.Path) -> tuple[int, list[str]]:
    """Return ``(returncode, sorted-changed-paths)`` for the worktree's diff vs HEAD.

    Uses ``git -C <worktree>`` so the worktree's own repo root is the target
    (submodule-aware: returns nothing if the worktree isn't a valid git
    checkout). Falls back to an empty list on non-zero exit rather than
    raising — callers interpret rc != 0 as "diff unavailable".
    """
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return (124, [])
    if proc.returncode != 0:
        return (proc.returncode, [])
    paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return (0, paths)




def extract_discovery_findings(review_result: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
    """Map evidence-backed pi-review warnings into discovery_evidence findings.

    Only warnings with concrete file-path evidence are mapped, and only to
    ``wrong_layer_ownership`` with provenance ``inference`` -- we infer possible
    wrong-layer write behavior from the worker's file I/O, not from verified
    code-inspection. This never fabricates structural issues: a process warning
    with no file evidence is dropped, and provenance is always ``inference``
    (never ``verified``, which would require code-level proof).

    Returns a findings list ready for write_discovery_evidence().
    """
    warnings: list[str] = review_result.get("warnings", [])
    files_written: list[str] = review_result.get("files_written", [])
    warning_text = " ".join(warnings)
    findings: list[dict[str, Any]] = []

    # BLIND_WRITE: wrote without reading first -> infers wrong layer (no read
    # of the owner module before mutating). Evidence: the written paths.
    if "BLIND_WRITE" in warning_text and files_written:
        findings.append({
            "source": "pi transcript review (blind write)",
            "provenance": "inference",
            "summary": (
                "pi worker wrote files without reading them first -- possible "
                "wrong-layer mutation (no read of the owner module before edit)"
            ),
            "evidence": "files written without prior read: " + ", ".join(files_written[:5]),
            "structural_issues": ["wrong_layer_ownership"],
        })

    # FORBIDDEN_FILE: modified a file outside the declared scope -> infers
    # wrong layer (touched a layer the task is not authorized to mutate).
    forbidden = task.get("forbidden_files", []) or []
    violated = [f for f in files_written if any(ff in f for ff in forbidden)]
    if violated:
        findings.append({
            "source": "pi transcript review (forbidden-file write)",
            "provenance": "inference",
            "summary": (
                "pi worker modified files outside the declared scope -- possible "
                "wrong-layer mutation (touched a forbidden layer)"
            ),
            "evidence": "forbidden files modified: " + ", ".join(violated[:5]),
            "structural_issues": ["wrong_layer_ownership"],
        })

    return findings

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

    result = review(transcript, task, worktree=_resolve_worktree(state_dir, run_id))

    # Write summary
    out = state_dir / f"pi-review_{run_id}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)

    # Map evidence-backed warnings into discovery_evidence so the existing
    # apply_discovery_evidence_merge reader (called in orchestrate.py after
    # dispatch_pi) can escalate. Soft-fail: if no findings or the writer is
    # unavailable, nothing is written and the reader preserves preflight.
    # Multi-terminal safe: uses run_id-scoped paths.
    _DE_IMPORT_ERR = (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError)
    _DE_WRITE_ERR = (OSError, IOError)
    try:
        _scripts_dir = str(pathlib.Path(__file__).resolve().parents[2])
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)
        import importlib
        _pf = importlib.import_module("preflight_propose")
        findings = extract_discovery_findings(result, task)
        if findings:
            written = _pf.write_discovery_evidence(state_dir, run_id, findings)
            if written is not None:
                print(f"  discovery-evidence: {written} ({len(findings)} finding(s))")
    except _DE_IMPORT_ERR as exc:
        _record_writer_error(state_dir, run_id, "import_error", exc)
    except _DE_WRITE_ERR as exc:
        _record_writer_error(state_dir, run_id, "write_error", exc)
    except Exception as exc:
        _record_writer_error(state_dir, run_id, "unexpected_error", exc)

    print(f"SUMMARY: {out}")
    if result["warnings"]:
        print(f"  {len(result['warnings'])} signals: {result['warnings']}")
    else:
        print("  no signals detected")


def _record_writer_error(state_dir: pathlib.Path, run_id: str, error_type: str, exc: Exception) -> None:
    """Run-local, non-blocking telemetry for discovery-evidence write failures.

    Writes a single JSONL record to state_dir/telemetry-discovery-evidence-error_{run_id}.jsonl.
    The run is never blocked by a telemetry write failure.
    """
    import json as _json, time as _time
    record = {
        "event": "discovery_evidence_writer_error",
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "run_id": run_id,
        "state_dir": str(state_dir),
        "dispatch_source": "pi_review_transcript",
        "error_type": error_type,
        "error_message": str(exc)[:500],
        "failure_direction": "non-blocking",
    }
    try:
        err_path = state_dir / f"telemetry-discovery-evidence-error_{run_id}.jsonl"
        with err_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record) + "\n")
    except Exception:
        pass  # telemetry failure never blocks the run


if __name__ == "__main__":
    main()
