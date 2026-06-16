#!/usr/bin/env python3
"""
run-qa-verification.py — GTO QA verdict integration for /go.

Consumes:
  - GTO orchestrator (direct import) + quality gates
  - task_type from active-task_{RUN_ID}.json (for routing-aware skip)

Emits:
  - qa-verdict-{RUN_ID}.json with qa_status, source, summary, gates, timestamp

qa_status mapping:
  accept              — no blocking findings, no gate violations
  accept-with-concerns — escape_hatches > 0 OR mixed_substance > 0 OR unverified_impl_claims > 0
  redo                — any critical/high unresolved findings
  error               — orchestrator crashed or produced no artifact
  skipped             — task_type in (design, planning)

Routing-aware skip:
  design/planning tasks skip QA entirely.

Returns:
  exit 0  — qa_status in (accept, accept-with-concerns, skipped)
  exit 1  — qa_status in (redo, error)
  exit 2  — missing RUN_ID
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

# ─── Paths ───────────────────────────────────────────────────────────────────────


def resolve_skills_analysis_root() -> Path:
    """Resolve the cc-skills-analysis plugin root used for GTO imports."""
    override = os.environ.get("SKILLS_ANALYSIS_ROOT", "").strip()
    if override:
        return Path(override)

    script_path = Path(__file__).resolve()
    plugin_root = script_path.parents[3]
    marketplace_plugins = plugin_root.parent
    candidates = [
        marketplace_plugins / "cc-skills-analysis",
        Path("P:/packages/cc-skills-analysis"),
    ]
    for candidate in candidates:
        if candidate.joinpath("skills", "gto", "orchestrator.py").exists():
            return candidate
    return candidates[0]


SKILLS_ANALYSIS = resolve_skills_analysis_root()

# State root for /go.
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


# ─── GTO import bridge ────────────────────────────────────────────────────────

def _import_gto() -> tuple[Any, Any]:
    """Import GTO orchestrator and quality gates.

    Adds SKILLS_ANALYSIS to sys.path so skills.gto is importable.
    Returns (orchestrator_run_fn, apply_quality_gates_fn).
    """
    root = str(resolve_skills_analysis_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from skills.gto.orchestrator import run as gto_run
    from skills.gto.agents._quality_gates import apply_quality_gates
    return gto_run, apply_quality_gates


# ─── Findings → QA status mapping ─────────────────────────────────────────────

def map_findings_to_qa_status(
    findings_data: list[dict[str, Any]],
) -> tuple[str, str, dict[str, int]]:
    """Map GTO findings to qa_status + summary + gate counts.

    Args:
        findings_data: list of finding dicts (from artifact JSON).

    Returns:
        (qa_status, summary_reason, gates) where gates has
        {escape_hatches, unverified_implementation_claims, mixed_substance}.
    """
    escape_hatches = 0
    unverified_impl = 0
    mixed_substance = 0
    has_critical = False

    for f in findings_data:
        status = f.get("status", "open")
        if status == "resolved":
            continue

        severity = (f.get("severity") or "").lower()
        if severity in ("critical", "high"):
            has_critical = True

        meta = f.get("metadata", {})
        if meta.get("escape_hatch"):
            escape_hatches += 1
        if meta.get("unverified_implementation_claim"):
            unverified_impl += 1
        if meta.get("mixed_substance"):
            mixed_substance += 1

    gates = {
        "escape_hatches": escape_hatches,
        "unverified_implementation_claims": unverified_impl,
        "mixed_substance": mixed_substance,
    }

    if has_critical:
        return "redo", "critical/high unresolved findings", gates
    if escape_hatches > 0 or mixed_substance > 0:
        return "accept-with-concerns", (
            f"accept-with-concerns ({escape_hatches} escape_hatches, "
            f"{mixed_substance} mixed_substance)"
        ), gates
    if unverified_impl > 0:
        return "accept-with-concerns", (
            f"accept-with-concerns ({unverified_impl} unverified_impl_claims)"
        ), gates

    return "accept", "accept", gates


# ─── Main ────────────────────────────────────────────────────────────────────

def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GTO QA verdict integration for go")
    parser.add_argument("--dry-run", action="store_true",
                        help="Emit dummy verdict without running GTO")
    parser.add_argument("--skill", default="go",
                        help="Skill name recorded in QA artifacts")
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
        print("[run-qa-verification] SKIP: design/planning task — qa_status=skipped", file=sys.stderr)
        return 0

    # ── Dry-run mode ────────────────────────────────────────────────────────
    if args.dry_run:
        dry_verdict = {
            "qa_status": "accept",
            "source": {"gto": None, "code_quality_gate": None},
            "summary": "dry-run mode",
            "timestamp": _iso_now(),
        }
        verdict_path = state_dir / f"qa-verdict-{RUN_ID}.json"
        verdict_path.write_text(json.dumps(dry_verdict, indent=2) + "\n", encoding="utf-8")
        return 0

    # ── Run GTO orchestrator directly ──────────────────────────────────────
    try:
        gto_run, apply_gates = _import_gto()
    except ImportError as e:
        print(f"[run-qa-verification] ERROR: cannot import GTO: {e}", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, f"GTO import failed: {e}")
        return 1

    env_terminal = TERMINAL_ID
    env_session = SESSION_ID

    try:
        rc = gto_run([
            "--terminal-id", env_terminal,
            "--session-id", env_session,
            "--root", str(SKILLS_ANALYSIS),
        ])
    except Exception as e:
        print(f"[run-qa-verification] ERROR: GTO orchestrator exception: {e}", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, f"orchestrator exception: {e}")
        return 1

    # ── Read artifact produced by orchestrator ──────────────────────────────
    artifacts_root = Path(os.environ.get(
        "CLAUDE_ARTIFACTS_ROOT", "P:/.claude/.artifacts",
    ))
    artifact_path = artifacts_root / env_terminal / "gto" / "outputs" / "artifact.json"

    if not artifact_path.exists():
        print(f"[run-qa-verification] ERROR: no artifact at {artifact_path}", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, f"no artifact produced (rc={rc})")
        return 1

    try:
        artifact_data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[run-qa-verification] ERROR: cannot parse artifact: {e}", file=sys.stderr)
        _write_error_verdict(state_dir, RUN_ID, f"unparseable artifact: {e}")
        return 1

    findings_data = artifact_data.get("findings", [])
    # Convert Finding objects (dataclass dicts) for gate counting
    findings_list = [f for f in findings_data if isinstance(f, dict)]

    # ── Map findings to QA verdict ──────────────────────────────────────────
    qa_status, summary, gates = map_findings_to_qa_status(findings_list)

    verdict = {
        "qa_status": qa_status,
        "source": {
            "gto": {
                "status": qa_status,
                "gates": gates,
                "findings_total": len(findings_list),
                "artifact_path": str(artifact_path),
            },
            "code_quality_gate": None,
        },
        "summary": summary,
        "timestamp": _iso_now(),
        "terminal_id": env_terminal,
        "task_type_skipped": False,
    }

    verdict_path = state_dir / f"qa-verdict-{RUN_ID}.json"
    verdict_path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print(
        f"[run-qa-verification] qa_status={qa_status} "
        f"esc={gates.get('escape_hatches', 0)} "
        f"unverified={gates.get('unverified_implementation_claims', 0)} "
        f"mixed={gates.get('mixed_substance', 0)} "
        f"— {summary}",
        file=sys.stderr,
    )

    if qa_status in ("accept", "accept-with-concerns", "skipped"):
        return 0
    return 1


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _iso_now() -> str:
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
