#!/usr/bin/env python3
"""go qa-status — Daily QA triage command.

Reads qa-verdict-{RUN_ID}.json files from GO_STATE_DIR and prints a human summary.

Usage:
    go qa-status                          # Scan all recent RUN_IDs in GO_STATE_DIR
    go qa-status --run-id RUN_ID        # Focus on specific RUN_ID
    go qa-status --days 7               # Show last N days (default: 7)
    go qa-status --limit 20              # Max verdicts to show (default: 20)
    go qa-status --verbose               # Show full summary text per verdict
    go qa-status --json                 # Emit raw JSON list to stdout

Reads from: $GO_STATE_DIR/qa-verdict-{RUN_ID}.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GO_STATE_DIR = Path(os.environ.get("GO_STATE_DIR", ".claude/.artifacts/temp/go"))
TERMINAL_ID = os.environ.get("TERMINAL_ID", "unknown")
DEFAULT_DAYS = 7
DEFAULT_LIMIT = 20

STATUS_COLORS = {
    "accept": "92",
    "accept-with-concerns": "93",
    "redo": "91",
    "error": "91",
    "skipped": "90",
    "unknown": "90",
}
STATUS_LABELS = {
    "accept": "PASS",
    "accept-with-concerns": "WARN",
    "redo": "FAIL",
    "error": "ERR",
    "skipped": "SKIP",
    "unknown": "????",
}


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _age_days(ts: str) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("+00:00", "Z").replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except ValueError:
        return None


def _format_gates(gates: dict[str, int]) -> str:
    parts = []
    for k, label in [("escape_hatches", "esc"), ("unverified_implementation_claims", "unver"), ("mixed_substance", "mixed"), ("downgraded_absent_signal", "down")]:
        v = gates.get(k, 0)
        if v:
            parts.append(f"{label}={v}")
    return ", ".join(parts) if parts else "clean"


def _render(path: Path, verbose: bool) -> str | None:
    v = _load(path)
    if not v:
        return None

    qa_status = v.get("qa_status", "unknown")
    label = STATUS_LABELS.get(qa_status, "????")
    code = STATUS_COLORS.get(qa_status, "90")
    ts = v.get("timestamp", "")
    days = _age_days(ts)
    age_str = f"{days:.1f}d ago" if days is not None else (ts[:19] if ts else "?")

    gto = v.get("source", {}).get("gto") or {}
    gates = gto.get("gates", {})
    findings = gto.get("findings_total", 0)
    runner_timing = v.get("runner_timing_s", 0)
    summary = v.get("summary", "")

    run_id = path.stem.replace("qa-verdict-", "")
    status_colored = _c(f"[{label}]", code)
    age_colored = _c(age_str, "90")

    gates_str = _format_gates(gates)
    parts = [status_colored, age_colored, run_id[:8], f"find={findings}"]
    if gates_str != "clean":
        parts.append(gates_str)
    if runner_timing:
        parts.append(f"{runner_timing:.1f}s")
    line = " ".join(parts)
    if verbose and summary:
        line += f" — {summary[:100]}"
    return line


def _scan(state_dir: Path, days: int, limit: int) -> list[tuple[Path, dict[str, Any]]]:
    if not state_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    results = []
    for p in sorted(state_dir.glob("qa-verdict-*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            if p.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        v = _load(p)
        if v is not None:
            results.append((p, v))
        if len(results) >= limit:
            break
    return results


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="go qa-status — daily QA triage")
    parser.add_argument("--run-id", default="", help="Specific RUN_ID to show")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"Days to scan (default: {DEFAULT_DAYS})")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Max verdicts (default: {DEFAULT_LIMIT})")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args(argv)

    state_dir = GO_STATE_DIR

    if args.json:
        results = _scan(state_dir, args.days, args.limit)
        out = [{"run_id": p.stem.replace("qa-verdict-", ""), **v} for p, v in results]
        print(json.dumps(out, indent=2))
        return 0

    terminal = TERMINAL_ID.split("_")[-1][:8] if "_" in TERMINAL_ID else TERMINAL_ID[:8]
    sep = _c("─" * 72, "90")
    print(sep)
    print(_c(f"  go qa-status  terminal={terminal}  days={args.days}  limit={args.limit}", "90"))
    print(sep)
    print()

    if args.run_id:
        line = _render(state_dir / f"qa-verdict-{args.run_id}.json", args.verbose)
        print(f"  {line if line else _c('(not found)', '90')}")
        return 0

    results = _scan(state_dir, args.days, args.limit)
    if not results:
        print(_c("  (no qa-verdict files found)", "90"))
        return 0

    groups: dict[str, list] = {s: [] for s in STATUS_LABELS}
    for p, v in results:
        qa = v.get("qa_status", "unknown")
        if qa not in groups:
            groups[qa] = []
        groups[qa].append((p, v))

    total = len(results)
    parts = []
    for status, label in STATUS_LABELS.items():
        cnt = len(groups.get(status, []))
        if cnt:
            parts.append(_c(f"{label}={cnt}", STATUS_COLORS.get(status, "90")))
    print(f"  {_c('Total:', '90')} {total}  {'  '.join(parts)}")
    print()

    for status in ("accept", "accept-with-concerns", "skipped", "redo", "error", "unknown"):
        items = groups.get(status, [])
        if not items:
            continue
        code = STATUS_COLORS.get(status, "90")
        label = STATUS_LABELS.get(status, status.upper()[:4])
        print(_c(f"  {label} ({len(items)})", code))
        for p, _ in items:
            line = _render(p, args.verbose)
            if line:
                print(f"    {line}")
        print()

    print(_c(f"  state_dir: {state_dir}", "90"))
    return 0


if __name__ == "__main__":
    sys.exit(run())