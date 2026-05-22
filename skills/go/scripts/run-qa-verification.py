#!/usr/bin/env python3
"""
run-qa-verification.py — GTO QA verdict integration for go/go-ef/go-pi.

Consumes:
  - GTO quality runner verdict JSON from gto_quality_runner.py
  - task_type from active-task_{RUN_ID}.json (for routing-aware skip)

Emits:
  - qa-verdict-{RUN_ID}.json with qa_status, source, summary, gates, timestamp

qa_status mapping:
  accept          — all gates 0, status == accept
  accept-with-concerns — escape_hatches > 0 OR mixed_substance > 0 OR unverified_impl_claims > 0
  redo            — GTO status in (revise-before-use, revise, reject, blocked)
  error           — runner crashed or produced unparseable output
  skipped         — task_type in (design, planning)

Routing-aware skip:
  design/planning tasks skip QA entirely — these are规划设计不需要代码质量验证

Returns:
  exit 0  — qa_status in (accept, accept-with-concerns, skipped)
  exit 1  — qa_status in (redo, error)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ─── Paths ───────────────────────────────────────────────────────────────────────

SKILLS_ANALYSIS = Path(os.environ.get(
    "SKILLS_ANALYSIS_ROOT",
    "P:/packages/cc-skills-analysis"
))

PYTHON = sys.executable

GTO_QUALITY_RUNNER = SKILLS_ANALYSIS / "skills" / "gto" / "__dev__" / "gto_quality_runner.py"

# State root for go/go-ef/go-pi is the same convention
GO_STATE_DIR = Path(os.environ.get("GO_STATE_DIR", Path.home() / ".claude" / ".artifacts" / "temp" / "go"))
TERMINAL_ID = os.environ.get("TERMINAL_ID", "unknown")
RUN_ID = os.environ.get("RUN_ID", os.environ.get("GO_RUN_ID", ""))
SESSION_ID = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID", "")

# ─── Routing-aware skip ───────────────────────────────────────────────────────

SKIP_TASK_TYPES = {"design", "planning"}


def should_skip_qa(state_dir: Path, run_id: str) -> bool:
    """Check if task_type warrants skipping QA."""
    task_file = state_dir / f"active-task_{run_id}.json"
    if not task_file.exists():
        return False
    try:
        payload = json.loads(task_file.read_text(encoding="utf-8"))
        task = payload.get("task", payload)
        task_type = task.get("task_type", "implementation")
        return task_type in SKIP_TASK_TYPES
    except (json.JSONDecodeError, OSError):
        return False


# ─── GTO verdict parsing ──────────────────────────────────────────────────────

FINALVERDICT_ACCEPT = {"accept", "accept-with-small-fixes"}
FINALVERDICT_REVISE = {"revise-before-use", "revise"}
FINALVERDICT_BLOCK = {"reject", "blocked"}


def parse_gto_runner_output(raw_stdout: str) -> dict[str, Any] | None:
    """Parse JSON from gto_quality_runner.py stdout.

    gto_quality_runner emits the full verdict dict as JSON on stdout.
    Returns None if raw_stdout is not valid JSON.
    """
    raw_stdout = raw_stdout.strip()
    if not raw_stdout:
        return None
    try:
        return json.loads(raw_stdout)
    except json.JSONDecodeError:
        return None


def map_gto_to_qa_status(gto_data: dict[str, Any]) -> tuple[str, str]:
    """Map GTO quality runner output to qa_status + summary.

    Handles both legacy single-skill output (verdict/gates/findings top-level)
    and new multi-variant output (final_status at top, variants{gto,gto_v2} nested).
    Returns (qa_status, summary_reason).
    """
    # New multi-variant schema: final_status at top, variants nested
    final_status = gto_data.get("final_status", "")
    variants = gto_data.get("variants", {})

    if final_status and variants:
        # Multi-variant: aggregate across all variants
        all_statuses = []
        total_esc = 0
        total_unverified = 0
        total_mixed = 0

        for name, v in variants.items():
            ver = v.get("verifier", {})
            s = ver.get("status", "unknown")
            all_statuses.append(s)
            gates = ver.get("gates", {})
            total_esc += gates.get("escape_hatches", 0)
            total_unverified += gates.get("unverified_implementation_claims", 0)
            total_mixed += gates.get("mixed_substance", 0)

        # Use the worst status as final GTO status
        if any(s in FINALVERDICT_BLOCK for s in all_statuses):
            gto_status = FINALVERDICT_BLOCK.pop()  # get last one
        elif any(s == "revise-before-use" for s in all_statuses):
            gto_status = "revise-before-use"
        elif any(s == "accept-with-small-fixes" for s in all_statuses):
            gto_status = "accept-with-small-fixes"
        else:
            gto_status = "accept"

        escape_hatches = total_esc
        unverified_impl = total_unverified
        mixed_substance = total_mixed
    else:
        # Legacy single-skill schema
        verdict: dict[str, Any] = gto_data.get("verdict", {})
        gates: dict[str, Any] = gto_data.get("gates", {})

        gto_status = verdict.get("status", "unknown")
        escape_hatches = gates.get("escape_hatches", 0)
        unverified_impl = gates.get("unverified_implementation_claims", 0)
        mixed_substance = gates.get("mixed_substance", 0)

    if gto_status in FINALVERDICT_BLOCK:
        return "redo", f"GTO blocked: {gto_status}"
    if gto_status in FINALVERDICT_REVISE:
        return "redo", f"GTO revise-before-use: {gto_status}"
    if escape_hatches > 0 or mixed_substance > 0:
        return "accept-with-concerns", (
            f"accept-with-concerns ({escape_hatches} escape_hatches, "
            f"{mixed_substance} mixed_substance)"
        )
    if unverified_impl > 0:
        return "accept-with-concerns", (
            f"accept-with-concerns ({unverified_impl} unverified_impl_claims)"
        )
    if gto_status in FINALVERDICT_ACCEPT:
        return "accept", f"accept ({gto_status})"

    return "accept-with-concerns", f"unknown GTO status '{gto_status}' — treating as concerns"


# ─── Main ────────────────────────────────────────────────────────────────────

def run(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="GTO QA verdict integration for go")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse existing verdict without running GTO runner")
    parser.add_argument("--skill", default="go",
                        help="Skill variant (go, go-ef, go-pi)")
    args = parser.parse_args(argv)

    if not RUN_ID:
        print("ERROR: RUN_ID not set", file=sys.stderr)
        return 2

    state_dir = GO_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)

    # ── Routing-aware skip ──────────────────────────────────────────────────
    if should_skip_qa(state_dir, RUN_ID):
        verdict_path = state_dir / f"qa-verdict-{RUN_ID}.json"
        skipped_verdict = {
            "qa_status": "skipped",
            "source": {"gto": None, "code_quality_gate": None},
            "summary": "task_type is design/planning — QA skipped",
            "timestamp": _iso_now(),
            "task_type_skipped": True,
        }
        verdict_path.write_text(json.dumps(skipped_verdict, indent=2) + "\n", encoding="utf-8")
        print(f"[run-qa-verification] SKIP: design/planning task — qa_status=skipped", file=sys.stderr)
        return 0

    # ── Run GTO quality runner ────────────────────────────────────────────
    if args.dry_run:
        # Just emit a dummy verdict for testing
        dry_verdict = {
            "qa_status": "accept",
            "source": {"gto": None, "code_quality_gate": None},
            "summary": "dry-run mode",
            "timestamp": _iso_now(),
        }
        verdict_path = state_dir / f"qa-verdict-{RUN_ID}.json"
        verdict_path.write_text(json.dumps(dry_verdict, indent=2) + "\n", encoding="utf-8")
        return 0

    env = {
        **os.environ,
        "CLAUDE_SESSION_ID": SESSION_ID,
        "CLAUDE_ARTIFACTS_ROOT": os.environ.get("CLAUDE_ARTIFACTS_ROOT", "P:/.claude/.artifacts"),
    }

    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            [PYTHON, str(GTO_QUALITY_RUNNER), "--variant", "both", "--no-pytest", "--json-output"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(SKILLS_ANALYSIS),
            env=env,
        )
        runner_s = time.perf_counter() - t0
    except subprocess.TimeoutExpired:
        print(f"[run-qa-verification] ERROR: GTO runner timed out after 300s", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, "GTO runner timed out after 180s")
        return 1
    except Exception as e:
        print(f"[run-qa-verification] ERROR: runner exception: {e}", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, str(e))
        return 1

    if result.returncode not in (0, 1):
        # Runner crashed — gto_quality_runner returns 0 for accept, 1 for revise
        # Treat non-0/1 as error
        print(f"[run-qa-verification] ERROR: runner exit {result.returncode}: {result.stderr[:300]}", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, f"runner exit {result.returncode}")
        return 1

    # Parse stdout for verdict data
    gto_data = parse_gto_runner_output(result.stdout)
    if gto_data is None:
        print(f"[run-qa-verification] ERROR: could not parse runner output", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, "unparseable runner output")
        return 1

    qa_status, summary = map_gto_to_qa_status(gto_data)

    # Extract data from both old (legacy) and new (multi-variant) schemas
    final_status = gto_data.get("final_status", "")
    variants = gto_data.get("variants", {})

    if final_status and variants:
        # New multi-variant schema
        all_gates = {}
        all_findings = {}
        for name, v in variants.items():
            ver = v.get("verifier", {})
            g = ver.get("gates", {})
            for k, val in g.items():
                all_gates[k] = all_gates.get(k, 0) + val
            fi = ver.get("findings_total", 0)
            all_findings[name] = fi
        gates = all_gates
        findings_total = sum(all_findings.values())
        source_status = final_status
    else:
        # Legacy single-skill schema
        gates = gto_data.get("gates", {})
        findings_total = gto_data.get("findings", {}).get("total", 0)
        source_status = gto_data.get("verdict", {}).get("status", "")

    verdict = {
        "qa_status": qa_status,
        "source": {
            "gto": {
                "status": source_status,
                "final_status": final_status or None,
                "gates": gates,
                "findings_total": findings_total,
            },
            "code_quality_gate": None,
        },
        "summary": summary,
        "timestamp": _iso_now(),
        "runner_timing_s": round(runner_s, 2),
        "gto_session_id": gto_data.get("session_id"),
        "terminal_id": gto_data.get("terminal_id"),
        "task_type_skipped": False,
    }

    verdict_path = state_dir / f"qa-verdict-{RUN_ID}.json"
    verdict_path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    # Log to stderr for terminal visibility
    print(
        f"[run-qa-verification] qa_status={qa_status} "
        f"esc={gates.get('escape_hatches', 0)} "
        f"unverified={gates.get('unverified_implementation_claims', 0)} "
        f"mixed={gates.get('mixed_substance', 0)} "
        f"runner={round(runner_s, 1)}s — {summary}",
        file=sys.stderr,
    )

    # Exit code: 0 for accept/accept-with-concerns/skipped, 1 for redo/error
    if qa_status in ("accept", "accept-with-concerns", "skipped"):
        return 0
    return 1


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _iso_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_error_verdict(state_dir: Path, run_id: str, error_reason: str) -> None:
    verdict = {
        "qa_status": "error",
        "source": {"gto": None, "code_quality_gate": None},
        "summary": f"error: {error_reason}",
        "timestamp": _iso_now(),
        "task_type_skipped": False,
    }
    (state_dir / f"qa-verdict-{run_id}.json").write_text(
        json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(run())