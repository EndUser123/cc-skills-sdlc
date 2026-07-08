#!/usr/bin/env python3
"""Final Omission Audit - read-only post-implementation review (STEP 9.6).

Runs AFTER completion_evidence_review (STEP 9.5) and BEFORE pr-artifacts. It
reuses that gate's EvidenceRow schema + verdict vocabulary instead of inventing
a new one. The audit adds four things CER does not:

  1. Completion-authority ladder L0..L5, derived from observed artifacts
     (worker report -> source inspection -> tests -> real entrypoint ->
     runtime/cache -> original symptom closed). The verdict wording is
     downgraded when the worker's claim exceeds the evidence (req. 4).
  2. Commit-boundary packet: classify every dirty/untracked file as
     mine_for_this_task | parallel_session_or_unrelated | generated against the
     orchestrator's declared changed-files set. Any non-owned dirty file =>
     commit_boundary_risk (req. 5).
  3. Mechanism-change contract audit: when mechanism_change.required and a
     new gate/telemetry/routing/state/artifact was added, verify the worker
     filled writer/storage/reader/authority/freshness/failure_behavior/
     live_acceptance_evidence from source (req. 6).
  4. Dry-run simplification surface: the 6 questions (req. 7). Dead-code /
     writer-reader checks are delegated to CER (already run); this gate
     surfaces the simplification questions for the surfaces it triggers on.

Read-only invariant: inspects state + git, never mutates a tracked file.
Exits 2 on REVISE/BLOCK/INCOMPLETE (mirrors CER main()).
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Reuse the sibling gate's schema + constants - do not duplicate.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from completion_evidence_review import (  # noqa: E402
    EvidenceRow,
    _LIVE_BEHAVIOR_TERMS,
    _BLOCKING_VERDICTS,
)

_AUTHORITY_LEVELS = (
    "L0_asserted_by_worker",
    "L1_source_inspected",
    "L2_tests_passed",
    "L3_real_entrypoint_smoked",
    "L4_runtime_or_cache_verified",
    "L5_original_symptom_confirmed_closed",
)

_OMISSION_FIELDS = (
    "what_was_proven",
    "what_was_not_proven",
    "what_was_inferred",
    "stale_state_risks",
    "commit_boundary_risks",
    "cache_runtime_risks",
    "writer_reader_wiring_risks",
    "synthetic_vs_live_evidence",
    "what_would_falsify_pass",
    "recommended_next_verification",
)

# Claim wording that requires the matching authority tier or higher.
# (claim_substring, min_level_index, cannot_claim_wording)
_DOWNGRADE_RULES = (
    ("runtime", 3, "cannot claim runtime-delivered (needs >= L3 real-entrypoint smoke)"),
    ("cache", 4, "cannot claim cache-delivered (needs >= L4 runtime/cache verification)"),
    ("live", 4, "cannot claim live success (needs >= L4 runtime evidence)"),
    ("failover", 4, "cannot claim failover proven (needs >= L4 runtime evidence)"),
    ("fixed", 5, "cannot claim fixed (needs >= L5 original-symptom confirmed closed)"),
    ("complete", 5, "cannot claim complete (needs >= L5 original-symptom confirmed closed)"),
    ("shipped", 4, "cannot claim shipped/available/enforced (needs >= L4 + reader/backend path)"),
)

# Dry-run simplification questions (req. 7). The audit records whether the task
# touched a simplification surface; CER covers dead-code + writer-reader.
_DRY_RUN_QUESTIONS = (
    "can this be smaller?",
    "can an existing mechanism be extended instead?",
    "is any new artifact format necessary?",
    "are writer and reader connected? (delegated to completion_evidence_review)",
    "is any code dead or inert? (delegated to completion_evidence_review)",
    "are tests at the real entry point?",
)


@dataclass
class AuditResult:
    verdict: str  # PASS | PASS_WITH_FOLLOWUP | REVISE | BLOCK | INCOMPLETE | NOT_TRIGGERED
    run_id: str
    triggered: bool
    trigger_reason: str
    completion_authority_level: str = _AUTHORITY_LEVELS[0]
    evidence: list[EvidenceRow] = field(default_factory=list)
    omission_audit: dict[str, Any] = field(default_factory=dict)
    commit_boundary_packet: dict[str, Any] = field(default_factory=dict)
    blocking_gaps: list[str] = field(default_factory=list)
    overclaims: list[str] = field(default_factory=list)
    recommended_next_action: str = ""
    commit_push_safe: bool = False
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "omission-audit.v1",
            "verdict": self.verdict,
            "run_id": self.run_id,
            "triggered": self.triggered,
            "trigger_reason": self.trigger_reason,
            "completion_authority_level": self.completion_authority_level,
            "evidence": [row.__dict__ for row in self.evidence],
            "omission_audit": self.omission_audit,
            "commit_boundary_packet": self.commit_boundary_packet,
            "blocking_gaps": self.blocking_gaps,
            "overclaims": self.overclaims,
            "recommended_next_action": self.recommended_next_action,
            "commit_push_safe": self.commit_push_safe,
            "generated_at": self.generated_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _git(args: list[str], cwd: Path) -> str:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        r = subprocess.run(
            ["git"] + args, capture_output=True, text=True, cwd=str(cwd),
            creationflags=flags, timeout=20,
        )
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _worker_claim_text(state_dir: Path, run_id: str) -> str:
    """Best-effort text of the worker's completion claim."""
    for name in (f"claude-task-result_{run_id}.json", f"pi-review_{run_id}.json"):
        data = _read_json(state_dir / name)
        for k in ("summary", "report", "verdict_text", "output"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return ""


def _owned_files(state_dir: Path, run_id: str) -> set[str]:
    """Files the orchestrator declares this task touched."""
    owned: set[str] = set()
    diff = _read_json(state_dir / f"diff-summary_{run_id}.json")
    for k in ("files", "changed_files", "name_only"):
        v = diff.get(k)
        if isinstance(v, list):
            owned.update(str(f) for f in v)
    res = _read_json(state_dir / f"claude-task-result_{run_id}.json")
    for k in ("files_touched", "files_written", "scope_in"):
        v = res.get(k)
        if isinstance(v, list):
            owned.update(str(f) for f in v)
    return owned


def _derive_authority_level(
    state_dir: Path, run_id: str, proposal: dict[str, Any], evidence: list[EvidenceRow]
) -> str:
    """Highest authority tier supported by observed artifacts (L0..L5)."""
    level = 0  # L0
    reasons = []
    if (state_dir / f"claude-task-result_{run_id}.json").exists() or (
        state_dir / f"pi-review_{run_id}.json"
    ).exists():
        level = 1
        reasons.append("worker/source artifact present")
    if (state_dir / f".verified_{run_id}").exists():
        level = max(level, 2)
        reasons.append(".verified present (tests passed)")
    cer = _read_json(state_dir / f"completion-evidence-review_{run_id}.json")
    if cer.get("verdict") in ("PASS", "PASS_WITH_FOLLOWUP"):
        level = max(level, 3)
        reasons.append("completion_evidence_review passed (real-entrypoint review ran)")
    cer_rows = cer.get("evidence") or []
    if any(
        isinstance(r, dict)
        and r.get("verdict") == "OK"
        and any(t in (r.get("claim", "") + r.get("required_evidence", "")).lower()
                for t in ("cache", "runtime", "registered", "live", "wired"))
        for r in cer_rows
    ) or (state_dir / f".coverage-passed_{run_id}").exists():
        level = max(level, 4)
        reasons.append("runtime/cache evidence OK (or .coverage-passed present)")
    gate = proposal.get("report_gate") or {}
    if gate.get("confirm_closed_passes"):
        level = 5
        reasons.append("closure_check.confirm_closed_passes (original symptom confirmed)")
    evidence.append(EvidenceRow(
        claim="completion authority level",
        required_evidence="artifacts rising through L0..L5",
        observed_evidence=_AUTHORITY_LEVELS[level] + " (" + ("; ".join(reasons) or "worker report only") + ")",
        verdict="OK" if level >= 2 else "WEAK",
    ))
    return _AUTHORITY_LEVELS[level]


def _classify_commit_boundary(
    worktree: Path, owned: set[str], evidence: list[EvidenceRow]
) -> tuple[dict[str, Any], list[str]]:
    """Fresh git status -> per-file ownership classification (req. 5)."""
    out = _git(["status", "--porcelain", "--untracked-files=all"], worktree)
    files: list[dict[str, str]] = []
    for line in out.splitlines():
        if len(line) < 4 or "D" in line[:2]:  # skip deletions (auto-commit-safe)
            continue
        raw = line[3:].strip()
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        path = raw.strip().strip('"')
        if not path:
            continue
        if path in owned or any(path.startswith(o.rstrip("/") + "/") for o in owned if o):
            cls = "mine_for_this_task"
        elif path.endswith((".pyc", ".log")) or "__pycache__" in path or ".tmp" in path:
            cls = "generated"
        else:
            cls = "parallel_session_or_unrelated"
        files.append({"path": path, "classification": cls})
    non_owned = [f for f in files if f["classification"] == "parallel_session_or_unrelated"]
    packet = {
        "dirty_files": files,
        "mine_for_this_task": [f["path"] for f in files if f["classification"] == "mine_for_this_task"],
        "not_owned": [f["path"] for f in non_owned],
        "auto_commit_could_bundle_unrelated": bool(non_owned),
        "explicit_pathspec_commit_required": bool(non_owned),
    }
    evidence.append(EvidenceRow(
        claim="commit boundary safe (no unrelated dirty work)",
        required_evidence="every dirty/untracked file owned by this task",
        observed_evidence=str(len(files)) + " dirty file(s); " + str(len(non_owned)) + " not owned by this task",
        verdict="OK" if not non_owned else "MISSING",
        note="no broad git add; commit owned files via explicit pathspecs",
    ))
    if non_owned:
        names = ", ".join(f["path"] for f in non_owned[:5])
        return packet, ["commit_boundary_risk: " + str(len(non_owned)) + " dirty file(s) not owned by this task (auto-commit could bundle them): " + names]
    return packet, []


def _audit_mechanism_contract(
    proposal: dict[str, Any], evidence: list[EvidenceRow]
) -> list[str]:
    mc = proposal.get("mechanism_change") or {}
    if not (mc.get("required") and mc.get("extension_path") in (
        "CLARIFY_EXISTING", "EXTEND_EXISTING", "SIMPLIFY_EXISTING", "NEW_MECHANISM_JUSTIFIED"
    )):
        return []
    missing = [f for f in
               ("writer", "storage", "reader", "authority", "freshness",
                "failure_behavior", "live_acceptance_evidence")
               if not mc.get(f)]
    evidence.append(EvidenceRow(
        claim="mechanism-change contract filled from source",
        required_evidence="writer/storage/reader/authority/freshness/failure_behavior/live_acceptance_evidence",
        observed_evidence=("all fields populated" if not missing else "missing: " + ", ".join(missing)),
        verdict="OK" if not missing else "MISSING",
    ))
    if missing:
        return ["mechanism_change contract incomplete: missing " + ", ".join(missing)]
    return []


def _dry_run_simplification(proposal: dict[str, Any], evidence: list[EvidenceRow]) -> None:
    """Record the 6 simplification questions when a simplification surface fired.

    Dead-code + writer-reader checks are delegated to completion_evidence_review
    (STEP 9.5, already run). This gate surfaces the questions so the report
    answers them; it does not invoke /refactor.
    """
    gate = proposal.get("report_gate") or {}
    if not gate.get("dry_run_simplification_required"):
        return
    evidence.append(EvidenceRow(
        claim="dry-run simplification audit answered",
        required_evidence="6 questions answered (smaller / extend-existing / new-format / writer-reader / dead-code / real-entrypoint-tests)",
        observed_evidence="surface triggered; questions surfaced in omission_audit; dead-code + writer-reader delegated to completion_evidence_review",
        verdict="WEAK",
        note="; ".join(_DRY_RUN_QUESTIONS),
    ))


def _detect_overclaims(claim_text: str, level_idx: int) -> list[str]:
    """Downgrade: claim wording that exceeds the derived authority tier."""
    if not claim_text:
        return []
    lower = claim_text.lower()
    overclaims = []
    for term, min_idx, wording in _DOWNGRADE_RULES:
        if term in lower and level_idx < min_idx:
            overclaims.append("'" + term + "' claim - " + wording)
    return overclaims


def run_audit(
    state_dir: Path, run_id: str, worktree: Path | None = None,
) -> AuditResult:
    worktree = worktree or Path.cwd()
    ts = _now()
    proposal = _read_json(state_dir / ("task-proposal_" + run_id + ".json"))
    gate = proposal.get("report_gate") or {}
    triggered = bool(gate.get("omission_audit_required"))
    if not triggered:
        return AuditResult(
            verdict="NOT_TRIGGERED", run_id=run_id, triggered=False,
            trigger_reason="report_gate.omission_audit_required is false",
            generated_at=ts, commit_push_safe=True,
        )

    evidence: list[EvidenceRow] = []
    blocking: list[str] = []

    level = _derive_authority_level(state_dir, run_id, proposal, evidence)
    level_idx = _AUTHORITY_LEVELS.index(level)

    cb_packet, cb_gaps = _classify_commit_boundary(
        worktree, _owned_files(state_dir, run_id), evidence
    )
    blocking.extend(cb_gaps)
    blocking.extend(_audit_mechanism_contract(proposal, evidence))
    _dry_run_simplification(proposal, evidence)

    claim_text = _worker_claim_text(state_dir, run_id)
    overclaims = _detect_overclaims(claim_text, level_idx)

    if overclaims:
        verdict = "BLOCK"
    elif blocking:
        verdict = "REVISE"
    elif any(r.verdict == "WEAK" for r in evidence):
        verdict = "PASS_WITH_FOLLOWUP"
    else:
        verdict = "PASS"

    omission = {f: None for f in _OMISSION_FIELDS}
    omission["completion_authority_level"] = level
    omission["synthetic_vs_live_evidence"] = (
        "claims require >= L4 runtime evidence; derived level is " + level
    )
    omission["what_was_proven"] = (
        "completion authority reached " + level
        + ("; commit boundary clean" if not cb_gaps else "; COMMIT BOUNDARY NOT CLEAN")
    )
    omission["what_was_not_proven"] = "; ".join(overclaims) or (
        "no overclaim detected at the derived authority level"
    )
    omission["commit_boundary_risks"] = (
        str(len(cb_packet["not_owned"])) + " not-owned dirty file(s); "
        "auto_commit_could_bundle_unrelated=" + str(cb_packet["auto_commit_could_bundle_unrelated"])
    )
    omission["what_would_falsify_pass"] = (
        "a claim term appearing at a lower authority tier than this audit derived, "
        "or a dirty file not owned by this task that auto-commit could bundle"
    )
    if overclaims or cb_gaps:
        omission["recommended_next_verification"] = (
            "raise completion-authority to L5 (confirm original symptom closed) before "
            "claiming fixed/complete; commit only owned files via explicit pathspecs"
        )
    else:
        omission["recommended_next_verification"] = "none - authority and boundary align with claims"

    commit_push_safe = verdict in ("PASS", "PASS_WITH_FOLLOWUP")
    return AuditResult(
        verdict=verdict, run_id=run_id, triggered=True,
        trigger_reason="report_gate.omission_audit_required (high-risk report)",
        completion_authority_level=level,
        evidence=evidence, omission_audit=omission,
        commit_boundary_packet=cb_packet,
        blocking_gaps=blocking, overclaims=overclaims,
        recommended_next_action=(
            overclaims[0] if overclaims
            else (blocking[0] if blocking else "authority and boundary align with claims")
        ),
        commit_push_safe=commit_push_safe, generated_at=ts,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Final Omission Audit")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--worktree", default=None)
    args = parser.parse_args(argv)

    state_dir = Path(args.state_dir)
    worktree = Path(args.worktree) if args.worktree else Path.cwd()
    result = run_audit(state_dir=state_dir, run_id=args.run_id, worktree=worktree)

    out_path = state_dir / ("omission-audit_" + args.run_id + ".json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    log_path = state_dir / ("omission-audit_" + args.run_id + ".jsonl")
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": result.generated_at, "verdict": result.verdict,
                "completion_authority_level": result.completion_authority_level,
                "commit_push_safe": result.commit_push_safe,
                "blocking_gaps_count": len(result.blocking_gaps),
                "overclaim_count": len(result.overclaims),
            }) + "\n")
    except OSError:
        pass
    (state_dir / (".omission-audited_" + args.run_id)).touch()
    print("omission_audit verdict=" + result.verdict
          + " authority=" + result.completion_authority_level
          + " commit_push_safe=" + str(result.commit_push_safe))
    if result.verdict in _BLOCKING_VERDICTS or result.verdict == "INCOMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
