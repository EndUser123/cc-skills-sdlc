#!/usr/bin/env python3
"""Completion Evidence Review — read-only post-implementation review.

Inspects the worker's completion report (claude-task-result / pi-review /
active-task), the git diff in the worktree, and existing evidence artifacts.
Emits completion-evidence-review_{run_id}.json with verdict + evidence table.

Verdict values:
  PASS                  - clean evidence packet, no gaps, no overclaim
  PASS WITH FOLLOW-UP   - non-blocking gaps; safe to mark done, log follow-ups
  REVISE                - blocking gap (revise before next review)
  BLOCK                 - overclaim, wrong layer, or hard failure
  INCOMPLETE            - missing required inputs (worker report missing/corrupt)

Read-only invariant:
  The reviewer inspects state but does NOT modify any tracked file. Safe
  validation commands (git status, git diff --stat, pytest --collect-only) are
  allowed; running real test suites is the orchestrator's job, not the
  reviewer's. Activation evidence is read from the existing artifacts the
  previous gates already wrote (e.g. .test-pass, .smoke, .cache-rebuild).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Terms that imply live / wired / production behavior; treating these as
# evidence-true without the matching artifact is overclaim.
_LIVE_BEHAVIOR_TERMS = frozenset({
    "live", "wired", "registered", "verified", "verified live",
    "shipped", "ship", "production", "available", "running", "active",
    "enforced", "deployed", "connected", "failover", "failover verified",
    "activation confirmed", "passed", "tests passed", "all tests pass",
})

# --- Claim-integrity discipline ------------------------------------------------
# Uncertainty terms that, in a high-risk verification context, let a report
# sound complete while the mechanism is not actually proven. Example: "commit
# → version bump likely auto-bumped to 1.0.183" is not a valid proof.
_UNCERTAINTY_TERMS = (
    "likely", "probably", "presumably", "apparently",
    "seems", "appears", "maybe", "i think", "i believe",
    "should be", "should work", "should now",
)
# High-risk claim contexts: an uncertainty term co-occurring in the SAME
# SENTENCE as one of these single-word tokens makes the claim load-bearing
# uncertain -> blocks a full COMPLETE verdict. Single tokens (not phrases) so
# the match survives the uncertainty word splitting a phrase ("hook likely ran"
# must still match the "hook" token).
_HIGH_RISK_CLAIM_CONTEXTS = (
    # completion / delivery
    "complete", "completed", "done", "fixed", "resolved",
    "shipped", "delivered", "finished",
    # verification artifacts
    "tests", "test", "rebuilt", "rebuild", "drift",
    "aligned", "alignment", "bumped", "version",
    # runtime / mechanism
    "live", "wired", "registered", "enforced", "deployed", "running",
    "hook", "fires", "fired", "executed",
    "routing", "dispatch", "router", "backend", "failover",
    "committed", "commit", "pushed", "propagat",
)
# Required replacement vocabulary for verification claims.
_CLAIM_INTEGRITY_FORMAT = (
    "PROVEN with evidence | INFERRED with basis+risk | "
    "UNVERIFIED with missing evidence | BLOCKED if required evidence missing"
)

# Files that constitute hook wiring — used by the wrong-layer detector.
_HOOK_FILE_MARKERS = (
    "hooks/Stop",
    "Stop_enforce_gate",
    "Stop.py",
    "hooks/PreToolUse",
    "PreToolUse.py",
    "go_delegation_enforce_PreToolUse",
    "hooks/hooks.json",
    "__lib/router.py",
    "settings.json",
    "hooks.json",
    "router.py",
)

# Verbs that mean broad/static analysis at runtime; these belong in preflight
# or report-gate, never inline in a Stop hook.
_BROAD_ANALYSIS_VERBS = (
    "pattern detection", "dry run", "dry-run", "refactor analysis",
    "cross-session state", "promotion policy", "recommendation",
    "heuristic classification", "broad analysis", "static analysis",
    "code review", "discovery merge",
)

# Trigger policy: surfaces that always require this review.
_ALWAYS_REVIEW_MARKERS = frozenset({
    "hook", "stop hook", "pretooluse", "posttooluse", "pre tool use",
    "post tool use", "sessionstart", "sessionend", "userpromptsubmit",
    "precompact", "notification",
    "identity", "dispatch", "router", "router.py",
    "settings.json", "hooks.json", "hooks/hooks.json",
    "plugin cache", "version-keyed cache", "cache rebuild", "plugin.json",
    "state dir", "go-sessions", "go_state_dir",
    "model", "model tier", "fallback", "failover", "pi", "agy",
    "telemetry", "metrics", "scrub",
})

# Tracking fields that, when missing on a new state/artifact, mean a reader
# has no writer to read from.
_TRACKING_PATH_HINTS = (
    "telemetry", "metrics", "stop_block", "anomaly",
    "completion-authority", "completion_evidence", "review_passes",
)

# Verdict severity for downgrade thresholds.
_BLOCKING_VERDICTS = {"REVISE", "BLOCK"}

# Conventional entry-point names invoked by runtime/CLI convention, not by an
# explicit Python call site. Exempt from the helper-without-caller check.
_ENTRY_POINT_NAMES = frozenset({
    "main", "run", "cli", "app", "__main__", "handle", "handler",
    "lambda_handler", "main_func", "entrypoint", "serve", "start",
})

# --- Review-boundary discipline ----------------------------------------------
# Surfaces whose change is load-bearing: a generic/misleading commit title or
# a cache/HEAD divergence here can hide a runtime/hook/orchestrator impact the
# way "chore(tests): update tests" once hid an orchestrate.py arg-shape fix.
_RUNTIME_LOAD_BEARING_MARKERS = (
    "skills/go/scripts/orchestrate.py",
    "skills/go/scripts/completion_evidence_review.py",
    "skills/go/hooks/",
    "/hooks/",            # any hook wiring
    "router.py",
    "__lib/router.py",
    "dispatch",           # routing/dispatch code
    "/state", "state_dir", "go-sessions", "session",
    "telemetry",
    "plugin.json", ".claude-plugin/", "hooks/hooks.json", "hooks.json",
)
# SKILL.md is load-bearing for behavior only when its hook frontmatter changes;
# a docs-only SKILL.md edit with a "docs:" title is appropriate, not risky.
_DOCS_LOAD_BEARING_MARKERS = (
    "SKILL.md",
)
# Conventional-commit prefixes that routinely understate runtime impact. A
# title is "generic" only when paired with a runtime load-bearing change.
_GENERIC_TITLE_RE = re.compile(
    r"^\s*(?:chore|docs|test|tests|style|refactor|build|ci|bump|misc)"
    r"(?:\([^)]+\))?\s*:",
    re.IGNORECASE,
)
# Generic maintenance bodies that carry no behavior-impact statement.
_GENERIC_BODY_MARKERS = (
    "update files", "update settings", "update tests", "update skill documentation",
    "maintenance update", "update python module",
)
# Surface nouns; if the commit body names one, a generic prefix is honest.
_TITLE_SURFACE_NOUNS = (
    "orchestrat", "hook", "router", "dispatch", "cache", "plugin", "version",
    "stop gate", "continuation", "completion", "telemetry", "routing", "session",
    "worktree", "arg-shape", "arg shape", "positional",
)


@dataclass
class EvidenceRow:
    """One row of the evidence table: claim / required / observed / verdict."""

    claim: str
    required_evidence: str
    observed_evidence: str
    verdict: str  # OK | WEAK | MISSING | OVERCLAIM
    note: str = ""


@dataclass
class ReviewResult:
    verdict: str  # PASS | PASS_WITH_FOLLOWUP | REVISE | BLOCK | INCOMPLETE
    run_id: str
    triggered: bool
    trigger_reason: str
    evidence: list[EvidenceRow] = field(default_factory=list)
    blocking_gaps: list[str] = field(default_factory=list)
    overclaims: list[str] = field(default_factory=list)
    recommended_next_action: str = ""
    commit_push_safe: bool = False
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "completion-evidence-review.v1",
            "verdict": self.verdict,
            "run_id": self.run_id,
            "triggered": self.triggered,
            "trigger_reason": self.trigger_reason,
            "evidence": [asdict(row) for row in self.evidence],
            "blocking_gaps": self.blocking_gaps,
            "overclaims": self.overclaims,
            "recommended_next_action": self.recommended_next_action,
            "commit_push_safe": self.commit_push_safe,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Trigger policy
# ---------------------------------------------------------------------------

def task_should_trigger(task: dict[str, Any]) -> tuple[bool, str]:
    """Return (should_run, reason) based on the active-task title/objective.

    Always for hook/gate/cache/plugin/routing/model/dispatch/state/session/
    telemetry tasks; always when the worker claimed live behavior; optional
    for small low-risk local edits.
    """
    if not task:
        return False, "no active-task record"

    title_obj = f"{task.get('title', '')} {task.get('objective', '')}".lower()
    task_type = (task.get("task_type") or "").lower()

    for marker in _ALWAYS_REVIEW_MARKERS:
        if marker in title_obj:
            return True, f"high-risk surface: {marker}"

    # Worker-claimed live behavior is always reviewed (the worker's report is
    # the claim; if the report says PASS on live behavior, this gate checks).
    return True, "always-review policy: default to running"


# ---------------------------------------------------------------------------
# Evidence readers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _worker_claim_text(state_dir: Path, run_id: str) -> str:
    """Pull the worker's own completion prose from claude-task-result or pi-review."""
    parts: list[str] = []
    for filename in (f"claude-task-result_{run_id}.json", f"pi-review_{run_id}.json"):
        data = _read_json(state_dir / filename)
        if not data:
            continue
        for key in ("summary", "verdict", "status", "reason", "notes"):
            value = data.get(key)
            if isinstance(value, str):
                parts.append(value)
        # pi-review can hold findings/warnings — concatenate short strings.
        for key in ("warnings", "findings", "critical_issues"):
            for item in data.get(key, []) or []:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str):
                            parts.append(v)
    # active-task summary
    active = _read_json(state_dir / f"active-task_{run_id}.json")
    task = active.get("task", active)
    for key in ("summary", "status", "title", "objective"):
        value = task.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def _evidence_artifact_present(state_dir: Path, run_id: str, kind: str) -> bool:
    """True if a verification artifact of the given kind exists for this run."""
    for pat in (f".{kind}*{run_id}*", f".{kind}_*", f"{kind}-{run_id}*"):
        if any(state_dir.glob(pat)):
            return True
    return False


def _has_real_subprocess_evidence(state_dir: Path, run_id: str) -> bool:
    """True iff a subprocess or process-level evidence artifact exists.

    Synthetic unit-test artifacts alone (test-pass, .pytest artifacts) do not
    satisfy this requirement; we look for smoke, dispatch-result, or
    preflight-proposed markers showing a real call was made.
    """
    real_markers = (
        f"dispatch-result_{run_id}.json",
        f"claude-task-request_{run_id}.json",
        f"pi-review_{run_id}.json",
        f".smoke_{run_id}",
        f".cache-rebuild_{run_id}",
        f"preflight-proposed_{run_id}",
    )
    return any((state_dir / name).exists() for name in real_markers)


def _resolve_diff_base(worktree: Path) -> str:
    """Return the SHA (or ref) to use as the diff base for the worktree.

    Preference order:
      1) merge-base(HEAD, main) when the worktree is on a non-main branch
      2) merge-base(HEAD, master) as a fallback
      3) "HEAD" — same as the working tree (no committed history diff)
    """
    try:
        head_proc = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        head_branch = head_proc.stdout.strip() if head_proc.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        head_branch = ""
    if head_branch and head_branch not in ("main", "master"):
        for upstream in ("main", "master"):
            try:
                mb = subprocess.run(
                    ["git", "-C", str(worktree), "merge-base", "HEAD", upstream],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if mb.returncode == 0 and mb.stdout.strip():
                return mb.stdout.strip()
    return "HEAD"


def _git_diff_files(worktree: Path) -> tuple[list[str], str]:
    """Return (changed_paths, diff_stat_or_empty) for the worktree.

    Uses current-terminal git evidence (no latest-file reads). The diff is
    the union of:
      - working-tree vs index (`git diff`),
      - index vs HEAD (`git diff --cached`),
      - HEAD vs the merge-base with the upstream branch (when the worktree
        is on a non-main branch — the orchestrator's worktree shape).
    Empty list is benign when there is no diff; empty stat is returned when
    git is unavailable — callers must fail toward no claim.
    """
    all_files: set[str] = set()
    stat_chunks: list[str] = []
    # 1) working tree vs index
    for kind, name_flag in (("diff", "--name-only"), ("diff", "--stat")):
        try:
            proc = subprocess.run(
                ["git", "-C", str(worktree), kind, name_flag],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return [], ""
        if proc.returncode != 0:
            return [], ""
        if name_flag == "--name-only":
            all_files.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
        else:
            stat_chunks.append(proc.stdout)
    # 2) index vs HEAD
    for kind, extra, name_flag in (("diff", "--cached", "--name-only"), ("diff", "--cached", "--stat")):
        try:
            proc = subprocess.run(
                ["git", "-C", str(worktree), kind, extra, name_flag],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            continue
        if name_flag == "--name-only":
            all_files.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
        else:
            stat_chunks.append(proc.stdout)
    # 3) merge-base with upstream — but only when the upstream exists in this repo.
    base = _resolve_diff_base(worktree)
    if base != "HEAD":
        for kind, name_flag in (("diff", "--name-only"), ("diff", "--stat")):
            try:
                proc = subprocess.run(
                    ["git", "-C", str(worktree), kind, base, "HEAD", name_flag],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if proc.returncode != 0:
                continue
            if name_flag == "--name-only":
                all_files.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
            else:
                stat_chunks.append(proc.stdout)
    return sorted(all_files), "\n".join(stat_chunks)


def _file_diff(worktree: Path, rel: str, base: str) -> str:
    """Return the diff text for one file (vs base) or empty string on error."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree), "diff", base, "HEAD", "--", rel],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _declared_files_in_active_task(active: dict[str, Any]) -> list[str]:
    """Files the worker declared it modified (active-task.files_modified)."""
    task = active.get("task", active)
    declared = task.get("files_modified", [])
    return [item.get("path", "") for item in declared if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def _detect_live_claim_without_artifacts(
    claim_text: str, state_dir: Path, run_id: str, evidence: list[EvidenceRow]
) -> tuple[list[str], list[EvidenceRow]]:
    """Worker claimed live behavior but no smoke/cache/registration evidence."""
    if not claim_text:
        return [], evidence
    found_terms = sorted(
        t for t in _LIVE_BEHAVIOR_TERMS if re.search(rf"\b{re.escape(t)}\b", claim_text, re.I)
    )
    if not found_terms:
        return [], evidence

    # Need at least one of: smoke, cache-rebuild, dispatch-result, registration.
    has_smoke = _evidence_artifact_present(state_dir, run_id, "smoke")
    has_cache = _evidence_artifact_present(state_dir, run_id, "cache-rebuild")
    has_registration = (
        (state_dir / f"cache-rebuild_{run_id}.json").exists()
        or (state_dir / f".cache-rebuild_{run_id}").exists()
    )

    observed = (
        f"smoke={has_smoke} cache_rebuild={has_cache} registration_artifact={has_registration}"
    )
    if has_smoke or has_cache or has_registration:
        evidence.append(EvidenceRow(
            claim=f"worker claim: {', '.join(found_terms)}",
            required_evidence="smoke / cache-rebuild / registration artifact",
            observed_evidence=observed,
            verdict="OK",
            note="live claim has matching artifact",
        ))
        return [], evidence
    evidence.append(EvidenceRow(
        claim=f"worker claim: {', '.join(found_terms)}",
        required_evidence="smoke / cache-rebuild / registration artifact",
        observed_evidence=observed,
        verdict="OVERCLAIM",
        note="live claim without activation artifact",
    ))
    return [f"live claim missing activation artifact (terms: {found_terms})"], evidence


def _detect_wrong_layer_stop_hook_edits(
    changed_files: list[str], worktree: Path, base: str, evidence: list[EvidenceRow]
) -> tuple[list[str], list[EvidenceRow]]:
    """Stop hook files were modified AND broad analysis verbs were introduced."""
    stop_hooks_touched = [
        f for f in changed_files
        if any(marker in f for marker in _HOOK_FILE_MARKERS)
        and ("Stop" in f or "stop" in f or "router" in f)
    ]
    if not stop_hooks_touched:
        return [], evidence

    broad_violations: list[str] = []
    for path in stop_hooks_touched:
        text = _file_diff(worktree, path, base).lower()
        for verb in _BROAD_ANALYSIS_VERBS:
            if verb in text:
                broad_violations.append(f"{path}: +{verb}")

    if not broad_violations:
        evidence.append(EvidenceRow(
            claim=f"Stop-area file edits: {stop_hooks_touched}",
            required_evidence="no broad-analysis verbs added in Stop/router scope",
            observed_evidence=f"checked {len(stop_hooks_touched)} file(s); no broad verb introduced",
            verdict="OK",
            note="narrow verification logic only",
        ))
        return [], evidence
    evidence.append(EvidenceRow(
        claim=f"Stop-area file edits: {stop_hooks_touched}",
        required_evidence="narrow session-bound logic only (no pattern detection / dry run / refactor analysis in Stop.py)",
        observed_evidence=f"broad-verb violations: {broad_violations}",
        verdict="OVERCLAIM",
        note="wrong-layer contamination",
    ))
    return ["Stop hook contaminated with broad-analysis verbs: " + "; ".join(broad_violations)], evidence


def _is_untracked(worktree: Path, rel: str) -> bool:
    """True if rel is an untracked file in the worktree (porcelain '??')."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree), "status", "--porcelain", "--", rel],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    # First two chars are the XY status; "??" = untracked.
    return proc.stdout.startswith("?? ")


def _detect_helper_without_caller(
    changed_files: list[str], worktree: Path, base: str, evidence: list[EvidenceRow],
    declared_files: list[str] | None = None,
) -> tuple[list[str], list[EvidenceRow]]:
    """A new function/class was added to a changed file but no caller exists.

    Test files are excluded — their new test functions ARE the entry point.

    Caller search runs in two passes:
      1) `git grep` over tracked files (matches existing callers).
      2) Grep over the working tree, including untracked greenfield caller
         files. This closes the blind spot where both helper and caller are
         new and neither is yet tracked.
      3) Files explicitly declared in active-task.files_modified (the worker's
         own contract) are always searched, tracked or not.
    """
    if not changed_files:
        return [], evidence
    findings: list[str] = []
    declared_set = set(declared_files or [])
    for rel in changed_files:
        full = worktree / rel
        if not full.is_file() or not full.suffix == ".py":
            continue
        # Skip test files: their `def test_*` is the call site.
        if (
            "/test_" in rel.lower()
            or rel.lower().startswith("test_")
            or "/tests/" in rel
            or rel.endswith("_test.py")
        ):
            continue
        diff_text = _file_diff(worktree, rel, base)
        new_defs: list[str] = []
        if diff_text:
            for line in diff_text.splitlines():
                stripped = line[1:] if line.startswith("+") else ""
                for prefix in ("def ", "async def "):
                    if stripped.startswith(prefix):
                        rest = stripped[len(prefix):]
                        name = rest.split("(", 1)[0].strip()
                        if name and name.isidentifier():
                            new_defs.append(name)
                        break
        else:
            # No diff text: either no change, or an untracked greenfield file
            # (git diff doesn't see untracked files). For untracked files the
            # whole file is "added", so scan every def in the full content.
            if _is_untracked(worktree, rel):
                try:
                    body = full.read_text(encoding="utf-8")
                except OSError:
                    body = ""
                for line in body.splitlines():
                    stripped = line.lstrip()
                    for prefix in ("def ", "async def "):
                        if stripped.startswith(prefix):
                            rest = stripped[len(prefix):]
                            name = rest.split("(", 1)[0].strip()
                            if name and name.isidentifier():
                                new_defs.append(name)
                            break
        if not new_defs:
            continue
        for name in new_defs:
            if name in _ENTRY_POINT_NAMES:
                continue  # conventional entry point — invoked by runtime/CLI
            hits: list[str] = []
            # Pass 1: tracked files via git grep.
            try:
                grep = subprocess.run(
                    ["git", "-C", str(worktree), "grep", "-l", "-w", "-F", "--", name],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                hits.extend(h.strip() for h in grep.stdout.splitlines() if h.strip())
            except (OSError, subprocess.TimeoutExpired):
                pass
            # Pass 2: working-tree grep, including untracked files.
            try:
                wt_grep = subprocess.run(
                    ["grep", "-rlwF", "--include=*.py", "--", name, str(worktree)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                for h in wt_grep.stdout.splitlines():
                    h_stripped = h.strip()
                    if not h_stripped:
                        continue
                    # Normalize absolute paths back to repo-relative.
                    try:
                        rel_h = str(Path(h_stripped).resolve().relative_to(worktree.resolve()))
                    except ValueError:
                        rel_h = h_stripped
                    hits.append(rel_h)
            except (OSError, subprocess.TimeoutExpired):
                pass
            # Pass 3: any declared file (may not exist on disk yet).
            for df in declared_set:
                if df == rel or df.endswith("/" + rel):
                    continue
                df_full = worktree / df
                if df_full.is_file():
                    try:
                        text = df_full.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    if name in text:
                        hits.append(df)
            # Dedupe and filter self.
            hits = sorted(set(h for h in hits if h != rel and not h.endswith("/" + rel)))
            if not hits:
                findings.append(f"{rel}::{name} (no caller)")
    if not findings:
        evidence.append(EvidenceRow(
            claim="new helpers have runtime callers (or are tests)",
            required_evidence="git grep / working-tree grep finds >=1 caller for each new def",
            observed_evidence="checked all new defs across changed .py files (tracked + untracked + declared)",
            verdict="OK",
            note="",
        ))
        return [], evidence
    evidence.append(EvidenceRow(
        claim="new helpers have runtime callers",
        required_evidence="each new def has >=1 caller file",
        observed_evidence="uncalled: " + "; ".join(findings),
        verdict="MISSING",
        note="",
    ))
    return [f"helper without caller: {item}" for item in findings], evidence


def _detect_missing_writer_for_reader(
    changed_files: list[str], worktree: Path, base: str, evidence: list[EvidenceRow]
) -> tuple[list[str], list[EvidenceRow]]:
    """A new reader path exists but no writer emits data to that path.

    Writer-pattern is the one that produces data: write_text, write_json,
    json.dump, Path().write_text, or .touch(). A reader's own `open(...)` is
    NOT a writer of that target.
    """
    if not changed_files:
        return [], evidence
    findings: list[str] = []
    for rel in changed_files:
        full = worktree / rel
        if not full.is_file() or not full.suffix == ".py":
            continue
        diff_text = _file_diff(worktree, rel, base)
        if not diff_text:
            continue
        added_lines = [
            line[1:]
            for line in diff_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        added_text = "\n".join(added_lines)
        for hint in _TRACKING_PATH_HINTS:
            if hint not in added_text:
                continue
            try:
                grep = subprocess.run(
                    ["git", "-C", str(worktree), "grep", "-E", "-l",
                     rf"(write_text\([^)]*{hint}|write_json\([^)]*{hint}|json\.dump\([^)]*{hint}|\.touch\(\)|append_jsonl)"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                writers = [line.strip() for line in grep.stdout.splitlines() if line.strip()]
            except (OSError, subprocess.TimeoutExpired):
                writers = []
            if not writers:
                findings.append(f"{rel} reads '{hint}' but no writer emits it")
    if not findings:
        evidence.append(EvidenceRow(
            claim="new readers have matching writers",
            required_evidence="for each new reader of a tracking path, a writer exists",
            observed_evidence="checked tracking-path readers in changed files",
            verdict="OK",
            note="",
        ))
        return [], evidence
    evidence.append(EvidenceRow(
        claim="new readers have matching writers",
        required_evidence="writer present for each read tracking path",
        observed_evidence="; ".join(findings),
        verdict="MISSING",
        note="",
    ))
    return findings, evidence


def _detect_synthetic_only_failover_claim(
    changed_files: list[str], claim_text: str, evidence: list[EvidenceRow]
) -> tuple[list[str], list[EvidenceRow]]:
    """Worker claims failover/fallback works but no subprocess test exists."""
    if not claim_text:
        return [], evidence
    failover_terms = ("failover", "fallback", "model swap", "harness swap")
    lower = claim_text.lower()
    if not any(t in lower for t in failover_terms):
        return [], evidence
    # Heuristic: presence of `subprocess.run` or `run_script(` in changed files.
    has_subprocess = False
    for rel in changed_files:
        full = Path(rel)
        if not full.is_file():
            try:
                # Try to resolve under common worktree roots
                continue
            except OSError:
                continue
        try:
            text = full.read_text(encoding="utf-8")
        except OSError:
            continue
        if "subprocess.run" in text or "run_script(" in text:
            has_subprocess = True
            break
    # Test files: pytest or unittest.Mock without subprocess simulation is synthetic.
    synthetic_markers = sum(text_lower.count(t) for t in (
        "@patch", "MagicMock", "Mock(", "monkeypatch.setattr",
        "pytest.fixture", "def test_",
    ) for text_lower in [claim_text.lower()])
    if has_subprocess and synthetic_markers < 3:
        evidence.append(EvidenceRow(
            claim="failover/fallback behavior verified",
            required_evidence="subprocess invocation in changed code",
            observed_evidence="subprocess.run / run_script present in changed files",
            verdict="OK",
            note="",
        ))
        return [], evidence
    evidence.append(EvidenceRow(
        claim="failover/fallback behavior verified",
        required_evidence=">=1 subprocess or run_script call in changed files",
        observed_evidence=f"subprocess={has_subprocess} test-mock density={synthetic_markers}",
        verdict="MISSING",
        note="synthetic-only evidence (uncalibrated heuristic; REVISE not BLOCK)",
    ))
    return ["failover claim without subprocess evidence"], evidence


def _detect_layer_placement(
    changed_files: list[str], state_dir: Path, run_id: str, evidence: list[EvidenceRow]
) -> tuple[list[str], list[EvidenceRow]]:
    """Any new logic placed in a Stop hook that belongs in preflight/report-gate."""
    stop_hooks = [
        f for f in changed_files
        if ("Stop.py" in f or "Stop_enforce_gate" in f or "/router.py" in f)
    ]
    if not stop_hooks:
        return [], evidence
    # If task-prompt contains a broad verb and the worker edited a Stop hook,
    # that's a wrong-layer violation.
    active = _read_json(state_dir / f"active-task_{run_id}.json")
    task = active.get("task", active)
    title_obj = f"{task.get('title', '')} {task.get('objective', '')}".lower()
    if not any(verb in title_obj for verb in _BROAD_ANALYSIS_VERBS):
        return [], evidence
    evidence.append(EvidenceRow(
        claim="Stop-area file edited",
        required_evidence="narrow session-bound logic only",
        observed_evidence=f"broad-verb in title: {[v for v in _BROAD_ANALYSIS_VERBS if v in title_obj]}",
        verdict="OVERCLAIM",
        note="wrong layer: broad analysis belongs in preflight / report-gate",
    ))
    return ["wrong-layer: broad analysis in Stop hook (task prompt supports it)"], evidence


def _detect_cache_plugin_activation(
    changed_files: list[str], state_dir: Path, run_id: str, evidence: list[EvidenceRow]
) -> tuple[list[str], list[EvidenceRow]]:
    """Plugin/hook files changed: cache rebuild + activation evidence required."""
    risky = any(
        any(marker in f for marker in ("plugin.json", ".claude-plugin", "hooks/hooks.json", "router.py"))
        for f in changed_files
    )
    if not risky:
        return [], evidence
    has_cache = _evidence_artifact_present(state_dir, run_id, "cache-rebuild")
    cache_marker_text = "absent"
    if (state_dir / f"cache-rebuild_{run_id}.json").exists():
        cache_marker_text = "present:cache-rebuild.json"
    elif (state_dir / f".cache-rebuild_{run_id}").exists():
        cache_marker_text = "present:.cache-rebuild marker"
    if has_cache:
        evidence.append(EvidenceRow(
            claim="plugin/hook files changed",
            required_evidence="cache rebuild artifact (.cache-rebuild_{run_id} or cache-rebuild_{run_id}.json)",
            observed_evidence=cache_marker_text,
            verdict="OK",
            note="",
        ))
        return [], evidence
    evidence.append(EvidenceRow(
        claim="plugin/hook files changed",
        required_evidence="cache rebuild artifact",
        observed_evidence=cache_marker_text,
        verdict="MISSING",
        note="plugin cache stale; reload-plugins required",
    ))
    return ["plugin/hook changes without cache-rebuild evidence"], evidence


def _detect_multi_terminal_safety(
    changed_files: list[str], state_dir: Path, run_id: str, evidence: list[EvidenceRow]
) -> tuple[list[str], list[EvidenceRow]]:
    """State/registry changes must use session/terminal-scoped file names.

    Loose patterns like 'latest', 'state.json' at the repo root are red flags.
    """
    if not changed_files:
        return [], evidence
    bad_paths = []
    for rel in changed_files:
        if any(token in rel for token in ("latest", "current-state.json", "global-state.json")):
            bad_paths.append(rel)
        if rel.endswith("/state.json") and "/" not in rel[: rel.rfind("/state.json") + 1]:
            # Top-level state.json (root) is suspicious in multi-terminal contexts.
            bad_paths.append(rel)
    if not bad_paths:
        evidence.append(EvidenceRow(
            claim="state/registry writes are session/terminal-scoped",
            required_evidence="no top-level latest/global state writes",
            observed_evidence=f"checked {len(changed_files)} changed file(s)",
            verdict="OK",
            note="",
        ))
        return [], evidence
    evidence.append(EvidenceRow(
        claim="state/registry writes are session/terminal-scoped",
        required_evidence="no top-level latest/global state writes",
        observed_evidence=f"non-scoped paths: {bad_paths}",
        verdict="WEAK",
        note="multi-terminal pollution risk",
    ))
    return [f"non-scoped state path: {p}" for p in bad_paths], evidence


def _detect_report_overclaim(
    claim_text: str, evidence: list[EvidenceRow], blocking_gaps: list[str],
) -> tuple[list[str], list[str], list[EvidenceRow]]:
    """Surface every live-behavior term in the claim not already backed by an OK row."""
    if not claim_text:
        return [], blocking_gaps, evidence
    lower = claim_text.lower()
    findings: list[str] = []
    overclaim_summary: list[str] = []
    # Re-pull live terms
    live_terms = sorted(t for t in _LIVE_BEHAVIOR_TERMS if re.search(rf"\b{re.escape(t)}\b", lower))
    for term in live_terms:
        # OK evidence row for this term?
        already_ok = any(
            term in (row.claim or "")
            and row.verdict == "OK"
            for row in evidence
        )
        if not already_ok and term in {"live", "wired", "registered", "failover", "enforced", "deployed", "production"}:
            # These terms are too strong to let through without explicit OK row.
            overclaim_summary.append(term)
    if overclaim_summary:
        evidence.append(EvidenceRow(
            claim=f"unbacked live-behavior terms: {overclaim_summary}",
            required_evidence="OK row in evidence table for each live-behavior term",
            observed_evidence=f"text mentions {live_terms}",
            verdict="OVERCLAIM",
            note="report overclaim",
        ))
        findings.append("report overclaim: live-behavior terms unbacked: " + ",".join(overclaim_summary))
    return findings, overclaim_summary, evidence


# ---------------------------------------------------------------------------
# Review-boundary discipline: surface load-bearing auto-committed changes that
# a clean git status or a generic commit title would otherwise hide.
# ---------------------------------------------------------------------------

def _git_capture(worktree: Path, *args: str) -> str:
    """Run git in worktree, return stripped stdout. Fail-open ('') on error."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree), *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _classify_load_bearing(changed: list[str]) -> dict[str, list[str]]:
    """Split changed files into runtime vs docs load-bearing buckets."""
    runtime: list[str] = []
    docs: list[str] = []
    for rel in changed:
        if any(m in rel for m in _RUNTIME_LOAD_BEARING_MARKERS):
            runtime.append(rel)
        elif any(rel.endswith(m) or m in rel for m in _DOCS_LOAD_BEARING_MARKERS):
            docs.append(rel)
    return {"runtime": sorted(set(runtime)), "docs": sorted(set(docs))}


def _commit_title_understates(title: str, runtime_files: list[str]) -> bool:
    """True when a generic title pairs with a runtime load-bearing change.

    A conventional-commit prefix from the generic set (chore/docs/test/style...)
    on a change that touches runtime surfaces understates the impact — unless
    the body actually names the surface/behavior (orchestrator, hook, router,
    cache, plugin, dispatch, etc.), in which case the title is honest.
    """
    if not runtime_files or not title:
        return False
    subject = title.split("\n", 1)[0]
    if not _GENERIC_TITLE_RE.search(subject):
        return False
    body = title.lower()
    # Body names a runtime surface → honest despite generic prefix.
    if any(noun in body for noun in _TITLE_SURFACE_NOUNS):
        return False
    return True  # generic prefix, no surface named → understates


def _head_commit_info(worktree: Path) -> dict[str, object]:
    """Gather HEAD commit evidence: sha, title, name-only, stat. Fail-open."""
    sha = _git_capture(worktree, "rev-parse", "--short", "HEAD")
    if not sha:
        return {"available": False}
    title = _git_capture(worktree, "log", "-1", "--format=%s%n%n%b", "HEAD")
    name_only = _git_capture(worktree, "show", "--name-only", "--pretty=format:", "HEAD")
    stat = _git_capture(worktree, "show", "--stat", "--format=", "HEAD")
    return {
        "available": True,
        "sha": sha,
        "title": title,
        "name_only": [ln for ln in name_only.splitlines() if ln.strip()],
        "stat": stat,
    }


def _plugin_cache_root() -> Path:
    """Cache root for plugin version lookup. Env-overridable for tests."""
    return Path(os.environ.get("GO_PLUGIN_CACHE_ROOT", str(Path.home() / ".claude" / "plugins" / "cache" / "local")))


def _source_cache_head_alignment(worktree: Path, cache_affecting: list[str]) -> dict[str, object]:
    """Compare source / cache / HEAD for plugin/cache-affecting changes.

    Fail-open: if no plugin.json is resolvable, report 'not_applicable' rather
    than claiming alignment. Never asserts alignment without evidence.
    """
    if not cache_affecting:
        return {"applicable": False}
    pj = worktree / ".claude-plugin" / "plugin.json"
    if not pj.is_file():
        return {"applicable": True, "source_version": None, "note": "no .claude-plugin/plugin.json in worktree"}
    try:
        pj_data = json.loads(pj.read_text(encoding="utf-8"))
        source_version = pj_data.get("version")
        plugin_name = pj_data.get("name", "")
    except (OSError, ValueError):
        return {"applicable": True, "source_version": None, "note": "plugin.json unreadable"}
    # Working-tree vs HEAD cleanliness (cache-ahead-of-HEAD detection).
    # `git diff --quiet HEAD` exits 0 when clean, 1 when dirty.
    try:
        wt_proc = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--quiet", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        wt_clean = wt_proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        wt_clean = None  # unknown
    # Cache version lookup.
    cache_version = None
    cache_note = "no cache dir found"
    if plugin_name:
        croot = _plugin_cache_root() / plugin_name
        if croot.is_dir():
            versions = sorted(d.name for d in croot.iterdir() if d.is_dir())
            if versions:
                cache_version = versions[-1]
                cache_note = f"cache dir(s): {versions}"
    # Alignment is PROVEN only when versions match AND working tree == HEAD.
    # Unknown working-tree state → not proven (fail toward flagging).
    aligned = (
        source_version is not None
        and cache_version == source_version
        and wt_clean is True
    )
    return {
        "applicable": True,
        "source_version": source_version,
        "cache_version": cache_version,
        "cache_note": cache_note,
        "working_tree_clean_vs_head": wt_clean,
        "aligned": aligned,
    }


def _detect_review_boundary_risk(
    changed_files: list[str], worktree: Path, evidence: list[EvidenceRow],
) -> tuple[list[str], list[EvidenceRow]]:
    """Surface load-bearing changes that a clean status / generic title hides.

    Non-blocking (WEAK) by design: REVIEW_BOUNDARY_RISK is a follow-up flag,
    not a failure. Examines BOTH the working-tree diff AND the HEAD commit so
    an auto-commit cannot hide a load-bearing change behind `git status` clean.
    """
    # Consider HEAD commit's files too: after auto-commit the working tree is
    # clean and changed_files is empty, yet the load-bearing change is real.
    head = _head_commit_info(worktree)
    head_files = head.get("name_only", []) if isinstance(head.get("name_only"), list) else []
    surface_files = sorted(set(changed_files) | set(head_files))
    buckets = _classify_load_bearing(surface_files)
    runtime_files = buckets["runtime"]
    # Docs-only load-bearing (e.g. SKILL.md) is not a boundary risk on its own.
    if not runtime_files:
        return [], evidence

    title = ""
    sha = ""
    committed = False
    if head.get("available"):
        title = str(head.get("title", "")).strip()
        sha = str(head.get("sha", ""))
        committed = any(set(runtime_files) & set(head_files))
    understates = _commit_title_understates(title, runtime_files)

    cache_affecting = [
        f for f in runtime_files
        if any(m in f for m in ("plugin.json", ".claude-plugin/", "hooks/hooks.json", "hooks.json"))
    ]
    alignment = _source_cache_head_alignment(worktree, cache_affecting)

    risk = understates or (alignment.get("applicable") and alignment.get("aligned") is False)
    parts = [
        f"committed={committed}",
        f"sha={sha or '(uncommitted)'}",
        f"runtime_load_bearing={runtime_files}",
    ]
    if head.get("available"):
        stat = str(head.get("stat", ""))
        parts.append(f"git_show_stat={stat.splitlines()[:6]}")
    parts.append(f"title_understates_runtime_impact={understates}")
    if alignment.get("applicable"):
        parts.append(
            f"source/cache/HEAD aligned={alignment.get('aligned')} "
            f"(source={alignment.get('source_version')} cache={alignment.get('cache_version')} "
            f"wt_clean_vs_head={alignment.get('working_tree_clean_vs_head')})"
        )
    observed = " | ".join(parts)
    if risk:
        note = "REVIEW_BOUNDARY_RISK: load-bearing change present"
        if understates:
            note += "; commit title understates runtime impact — cite the behavior change"
        if alignment.get("applicable") and alignment.get("aligned") is False:
            note += "; source/cache/HEAD alignment unproven — show zero-drift evidence"
    else:
        note = "load-bearing change present and reviewable (title + alignment OK)"
    verdict = "WEAK" if risk else "OK"
    evidence.append(EvidenceRow(
        claim="load-bearing change reviewable (commit SHA + title + cache alignment)",
        required_evidence="commit SHA + git show --stat/--name-only + title matches behavior + source/cache/HEAD aligned",
        observed_evidence=observed,
        verdict=verdict,
        note=note,
    ))
    if risk:
        return ["REVIEW_BOUNDARY_RISK: load-bearing change with understated title or unproven alignment"], evidence
    return [], evidence


# ---------------------------------------------------------------------------
# Claim-integrity discipline: distinguish proven claims from inferred ones in
# the worker's verification language. An uncertainty term in a high-risk claim
# context is load_bearing_uncertainty -> blocks a full COMPLETE verdict.
# ---------------------------------------------------------------------------

def _split_sentences(text):
    """Coarse sentence splitter for claim scanning (newline + period + bang)."""
    if not text:
        return []
    chunks = re.split(r"(?:\n|(?<=[.!?])\s+)", text)
    return [c.strip() for c in chunks if c.strip()]


def classify_claim_integrity(claim_text):
    """Classify uncertainty in the claim text.

    Returns one dict per (uncertainty term, high-risk context) co-occurrence in
    a sentence. Each dict carries: term, context, sentence, tier
    (load_bearing_uncertainty | advisory_uncertainty). Advisory rows (no
    high-risk context) are returned but do NOT block -- callers filter on tier.
    """
    findings = []
    seen = set()
    for sentence in _split_sentences(claim_text):
        lower = sentence.lower()
        if "proven" in lower or "unverified" in lower or "inferred" in lower or "blocked" in lower:
            continue
        term_hits = [t for t in _UNCERTAINTY_TERMS if t in lower]
        if not term_hits:
            continue
        ctx_hits = [c for c in _HIGH_RISK_CLAIM_CONTEXTS if c in lower]
        for term in term_hits:
            for ctx in ctx_hits:
                key = (term, ctx)
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "term": term,
                    "context": ctx,
                    "tier": "load_bearing_uncertainty",
                    "sentence": sentence[:200],
                })
            if not ctx_hits:
                key = (term, "none")
                if key not in seen:
                    seen.add(key)
                    findings.append({
                        "term": term,
                        "context": "(none -- advisory)",
                        "tier": "advisory_uncertainty",
                        "sentence": sentence[:200],
                    })
    return findings


def _detect_claim_integrity_risk(claim_text, evidence):
    """Flag load-bearing uncertainty in high-risk verification claims.

    Blocking (-> REVISE): uncertainty term + high-risk context. The report must
    re-state the claim as PROVEN / INFERRED / UNVERIFIED / BLOCKED instead of
    hedging with 'likely'/'probably'/etc. Advisory uncertainty (no high-risk
    context, e.g. 'this likely belongs in Priority 4') is allowed.
    """
    classified = classify_claim_integrity(claim_text)
    load_bearing = [f for f in classified if f["tier"] == "load_bearing_uncertainty"]
    if not load_bearing:
        return [], evidence
    summary = ", ".join(sorted({"'" + f["term"] + "' / " + f["context"] for f in load_bearing}))
    evidence.append(EvidenceRow(
        claim="verification claims use honest evidence vocabulary",
        required_evidence=_CLAIM_INTEGRITY_FORMAT,
        observed_evidence="load_bearing_uncertainty co-occurrences: " + summary,
        verdict="WEAK",
        note=("Downgrade COMPLETE -> INCOMPLETE/PASS_WITH_BLOCKING_FOLLOWUP: "
              "replace hedged verification with PROVEN/INFERRED/UNVERIFIED/BLOCKED."),
    ))
    return [
        "CLAIM_INTEGRITY: load_bearing_uncertainty in high-risk claim (" + summary + ") "
        "-- re-state as PROVEN/INFERRED/UNVERIFIED/BLOCKED"
    ], evidence


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------

def _assemble_verdict(
    blocking_gaps: list[str],
    overclaims: list[str],
    evidence_rows: list[EvidenceRow],
    triggered: bool,
    worker_report_present: bool,
) -> tuple[str, bool, str]:
    """Return (verdict, commit_push_safe, recommended_next_action)."""
    if not worker_report_present:
        return "INCOMPLETE", False, (
            "Worker completion report missing or unreadable. Re-run with worker "
            "spawn or write claude-task-result/pi-review artifact before retrying."
        )
    if overclaims or any(r.verdict == "OVERCLAIM" for r in evidence_rows):
        return "BLOCK", False, (
            "Worker overclaim detected. Provide activation evidence (smoke, "
            "cache-rebuild, dispatch-result) before commit/push."
        )
    if blocking_gaps:
        # Hard promotion to BLOCK is reserved for wrong-layer contamination —
        # architectural drift where logic landed in the wrong layer. The
        # synthetic-failover detector is heuristic and uncalibrated; it yields
        # REVISE, not BLOCK. Activation / wrong-layer BLOCK requires
        # calibrated or unambiguous evidence.
        hard = any(
            ("wrong layer" in g.lower() or "contamination" in g.lower())
            for g in blocking_gaps
        )
        if hard:
            return "BLOCK", False, (
                "Hard failure detected (wrong-layer contamination). "
                "Revise before commit/push."
            )
        return "REVISE", False, (
            "Blocking gaps detected: " + "; ".join(blocking_gaps[:3])
            + " — fix and re-run review before commit/push."
        )
    weak = [r for r in evidence_rows if r.verdict == "WEAK"]
    if weak:
        return "PASS_WITH_FOLLOWUP", True, (
            "Safe to mark done. Non-blocking follow-ups: "
            + "; ".join(r.note or r.claim for r in weak[:3])
        )
    return "PASS", True, "Clean evidence packet. Safe to commit/push."


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def run_review(
    worktree: Path,
    state_dir: Path,
    run_id: str,
    trigger_signal: bool = True,
) -> ReviewResult:
    """Run the full review and return a ReviewResult.

    Reads only: state_dir + worktree contents + git outputs (current-terminal).
    Never writes to: tracked files. Writes ONLY completion-evidence-review_{run_id}.json
    in the state_dir (which is treated as run-scratch by /go).
    """
    generated_at = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )

    active = _read_json(state_dir / f"active-task_{run_id}.json")
    task = active.get("task", active)

    triggered, trigger_reason = task_should_trigger(task)
    if not triggered and not trigger_signal:
        return ReviewResult(
            verdict="PASS",
            run_id=run_id,
            triggered=False,
            trigger_reason=trigger_reason,
            evidence=[],
            recommended_next_action="Review skipped (low-risk task).",
            commit_push_safe=True,
            generated_at=generated_at,
        )

    # Skip review when worker report is missing entirely.
    worker_report_present = (
        (state_dir / f"claude-task-result_{run_id}.json").is_file()
        or (state_dir / f"pi-review_{run_id}.json").is_file()
        or bool((task.get("summary") or "").strip())
    )
    if not worker_report_present:
        return ReviewResult(
            verdict="INCOMPLETE",
            run_id=run_id,
            triggered=True,
            trigger_reason=trigger_reason or "worker report absent",
            evidence=[],
            blocking_gaps=["worker report missing"],
            overclaims=[],
            recommended_next_action=(
                "Worker completion report missing. Re-run after worker spawn "
                "or write claude-task-result/pi-review artifact."
            ),
            commit_push_safe=False,
            generated_at=generated_at,
        )

    # Pull data once.
    claim_text = _worker_claim_text(state_dir, run_id)
    changed_files, diff_stat = _git_diff_files(worktree)
    diff_base = _resolve_diff_base(worktree)
    declared = set(_declared_files_in_active_task(active))
    if declared:
        changed_files = sorted(set(changed_files) | declared)

    evidence: list[EvidenceRow] = []
    blocking_gaps: list[str] = []
    overclaim_list: list[str] = []

    # Sequential detectors; each returns updates to blocking_gaps/overclaims/evidence.
    overclaim_findings, evidence = _detect_live_claim_without_artifacts(
        claim_text, state_dir, run_id, evidence
    )
    overclaim_list.extend(overclaim_findings)
    blocking_gaps.extend(overclaim_findings)  # live without artifact = blocking

    layer_findings, evidence = _detect_wrong_layer_stop_hook_edits(changed_files, worktree, diff_base, evidence)
    blocking_gaps.extend(layer_findings)

    caller_findings, evidence = _detect_helper_without_caller(
        changed_files, worktree, diff_base, evidence,
        declared_files=sorted(declared) if declared else None,
    )
    blocking_gaps.extend(caller_findings)

    writer_findings, evidence = _detect_missing_writer_for_reader(changed_files, worktree, diff_base, evidence)
    blocking_gaps.extend(writer_findings)

    synth_findings, evidence = _detect_synthetic_only_failover_claim(changed_files, claim_text, evidence)
    blocking_gaps.extend(synth_findings)

    layer2_findings, evidence = _detect_layer_placement(changed_files, state_dir, run_id, evidence)
    blocking_gaps.extend(layer2_findings)

    cache_findings, evidence = _detect_cache_plugin_activation(changed_files, state_dir, run_id, evidence)
    blocking_gaps.extend(cache_findings)

    mt_findings, evidence = _detect_multi_terminal_safety(changed_files, state_dir, run_id, evidence)
    blocking_gaps.extend(mt_findings)

    report_findings, report_overclaims, evidence = _detect_report_overclaim(
        claim_text, evidence, blocking_gaps
    )
    overclaim_list.extend(report_overclaims)

    # Review-boundary discipline: advisory (WEAK). NOT added to blocking_gaps —
    # REVIEW_BOUNDARY_RISK surfaces as PASS_WITH_FOLLOWUP, not failure. Examines
    # HEAD commit too so an auto-commit can't hide a load-bearing change behind
    # a clean working tree.
    _boundary_findings, evidence = _detect_review_boundary_risk(
        changed_files, worktree, evidence
    )

    # Claim-integrity discipline: an uncertainty term ('likely'/'probably'/...)
    # co-occurring with a high-risk verification context is load_bearing →
    # blocks a full COMPLETE verdict (downgrade to REVISE).
    integrity_findings, evidence = _detect_claim_integrity_risk(claim_text, evidence)
    blocking_gaps.extend(integrity_findings)

    # Synthetic-failover findings are NOT auto-promoted to overclaims. The
    # detector is heuristic; it surfaces as blocking_gaps and yields REVISE
    # via _assemble_verdict. To upgrade to BLOCK or overclaim, combine with
    # activation-claim evidence (live_claim_without_artifacts) or require
    # calibrated corpus evidence.
    # if synth_findings:
    #     overclaim_list.extend(synth_findings)

    verdict, safe, action = _assemble_verdict(
        blocking_gaps, overclaim_list, evidence, triggered, worker_report_present
    )

    return ReviewResult(
        verdict=verdict,
        run_id=run_id,
        triggered=True,
        trigger_reason=trigger_reason or "always-review",
        evidence=evidence,
        blocking_gaps=blocking_gaps,
        overclaims=overclaim_list,
        recommended_next_action=action,
        commit_push_safe=safe,
        generated_at=generated_at,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Completion Evidence Review")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--worktree", default=None,
                        help="Optional worktree path; default is CWD")
    parser.add_argument("--skip-on-low-risk", action="store_true",
                        help="If the task is low-risk, skip review entirely.")
    args = parser.parse_args(argv)

    state_dir = Path(args.state_dir)
    run_id = args.run_id
    worktree = Path(args.worktree) if args.worktree else Path.cwd()

    result = run_review(
        worktree=worktree,
        state_dir=state_dir,
        run_id=run_id,
        trigger_signal=not args.skip_on_low_risk,
    )

    out_path = state_dir / f"completion-evidence-review_{run_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")

    # Also append-only log on the standard ledger.
    log_path = state_dir / f"completion-evidence-review_{run_id}.jsonl"
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": result.generated_at,
                "verdict": result.verdict,
                "commit_push_safe": result.commit_push_safe,
                "blocking_gaps_count": len(result.blocking_gaps),
                "overclaim_count": len(result.overclaims),
            }) + "\n")
    except OSError:
        pass

    # Stdout: one short line for orchestrator parsing. Non-blocking verdicts
    # remain decoupled from Stop_enforce_gate per requirements.
    print(f"completion_evidence_review verdict={result.verdict} commit_push_safe={result.commit_push_safe}")
    if result.verdict in _BLOCKING_VERDICTS:
        return 2
    if result.verdict == "INCOMPLETE":
        # Missing worker report is a hard gate: the review cannot authorize
        # completion without inputs to review, and .pr-ready must not be
        # touchable in that state. verify-task (Step 1) does NOT guarantee a
        # worker report exists, so INCOMPLETE is reachable and must block.
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
