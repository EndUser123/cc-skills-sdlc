#!/usr/bin/env python3
"""Bounded adversarial falsification gate for /go.

Inserts between omission-audit (STEP 9.6) and _pr_artifacts_and_tail in
run_common_tail. For qualifying high-risk tasks, writes a run-scoped,
revision-bound request; the orchestrator emits SPAWN_FALSIFIER; the
main-loop Claude spawns an attacker Agent in a harness-created disposable
worktree; the attacker writes a structured result; the orchestrator resumes
with --falsification-resume, validates the binding, applies the verdict
policy, cleans the disposable worktree, and calls _pr_artifacts_and_tail
only when permitted.

/go remains the sole final completion authority. The falsifier may report
evidence and create disposable tests/mutations in the attack worktree only.
It must not edit the authoritative task worktree, write the PR-ready marker, mark the
task complete, commit, push, merge, or repair production code.

Opt out with GO_FALSIFICATION_SKIP=1.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Schema versions
# ---------------------------------------------------------------------------

REQUEST_SCHEMA = "go.falsification-request.v1"
RESULT_SCHEMA = "go.falsification-result.v1"

_VALID_VERDICTS = frozenset({
    "FALSIFIED",
    "NOT_FALSIFIED_WITHIN_BUDGET",
    "INCONCLUSIVE",
    "HARNESS_FAILURE",
    "BUDGET_EXHAUSTED",
})

# Default budget limits (env-overridable).
_DEFAULT_BUDGET = {
    "max_attempts": 1,
    "max_mutations": 10,
    "timeout_seconds": 120,
    "total_elapsed_seconds": 300,
    "max_files_writable": 50,
}

# High-risk surfaces that trigger falsification (mirrors completion_evidence_review's
# _HIGH_RISK_CLAIM_CONTEXTS + mechanism-change surfaces).
_FALSIFICATION_SURFACES = (
    "hook", "gate", "stop", "pretooluse", "posttooluse", "sessionstart",
    "sessionend", "router", "settings.json", "hooks.json", "plugin.json",
    "auth", "token", "cache", "release", "recovery", "failover", "fallback",
    "state", "session", "identity", "dispatch", "concurrency",
    "authorization", "permission", "security",
)

# Skip these task types / intents entirely.
_SKIP_TASK_TYPES = frozenset({"validation", "design", "planning"})
_SKIP_DOCS_HINTS = ("documentation", "readme", "changelog", "doc-only", "docs only")


# ---------------------------------------------------------------------------
# Routing — one deterministic function
# ---------------------------------------------------------------------------

def should_falsify(
    task: dict[str, Any],
    proposal: dict[str, Any] | None = None,
    changed_files: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Decide whether falsification is required for this task.

    Returns (required, reasons). Reasons are written to the routing artifact
    for inspectability.
    """
    reasons: list[str] = []

    # Env opt-out (can override the opt-in default below).
    if os.environ.get("GO_FALSIFICATION_SKIP", "").strip() == "1":
        reasons.append("GO_FALSIFICATION_SKIP=1 — opted out")
        return False, reasons

    # FALSIFICATION IS OFF BY DEFAULT. The runtime consumer (SPAWN_FALSIFIER
    # token handling in SKILL.md) is not yet complete. Set
    # GO_FALSIFICATION_ENABLE=1 to activate this gate. Remove this guard once
    # the full main-loop consumer contract is wired.
    if os.environ.get("GO_FALSIFICATION_ENABLE", "").strip() != "1":
        reasons.append("GO_FALSIFICATION_ENABLE not set — falsification disabled by default")
        return False, reasons

    inner = task.get("task", task) if isinstance(task, dict) else {}
    task_type = (inner.get("task_type") or "").lower()
    title = (inner.get("title") or "").lower()
    objective = (inner.get("objective") or "").lower()

    # Skip validation/design/planning tasks.
    if task_type in _SKIP_TASK_TYPES:
        reasons.append(f"task_type={task_type} — not an implementation task")
        return False, reasons

    # Skip docs-only hints.
    combined_text = f"{title} {objective}"
    if any(h in combined_text for h in _SKIP_DOCS_HINTS):
        reasons.append("documentation-only task — skip")
        return False, reasons

    # Check high-risk surfaces via word-boundary match on title + objective.
    import re
    surface_hits = []
    for marker in _FALSIFICATION_SURFACES:
        if re.search(r"\b" + re.escape(marker) + r"(s)?\b", combined_text):
            surface_hits.append(marker)

    # Check changed files for high-risk paths.
    if changed_files:
        for cf in changed_files:
            cf_lower = cf.lower()
            if any(s in cf_lower for s in ("hook", "gate", "stop", "router",
                                            "settings", "session", "auth",
                                            "cache", "state", "identity")):
                if "changed-file-surface" not in surface_hits:
                    surface_hits.append("changed-file-surface")
                break

    # Check proposal for mechanism_change or prompt_review_required.
    if proposal:
        mc = proposal.get("mechanism_change", {}) or {}
        if mc.get("extension_path") in ("NEW_MECHANISM_JUSTIFIED", "EXTEND_EXISTING"):
            surface_hits.append("mechanism-change")
        if proposal.get("prompt_review_required"):
            surface_hits.append("prompt-review-required")

    if surface_hits:
        reasons.append(f"high-risk surfaces: {sorted(set(surface_hits))}")
        return True, reasons

    # Default: skip.
    reasons.append("no high-risk surface detected — skip by default")
    return False, reasons


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def resolve_budget() -> dict[str, int]:
    """Resolve budget limits from env or defaults."""
    budget = {}
    for key, default in _DEFAULT_BUDGET.items():
        env_key = f"GO_FALSIFY_{key.upper()}"
        try:
            budget[key] = int(os.environ.get(env_key, default))
        except (ValueError, TypeError):
            budget[key] = default
    return budget


# ---------------------------------------------------------------------------
# Request payload
# ---------------------------------------------------------------------------

def build_falsification_request(
    state_dir: Path,
    run_id: str,
    worktree: Path,
    task: dict[str, Any],
    changed_files: list[str],
    proposal: dict[str, Any] | None,
    routing_reasons: list[str],
) -> dict[str, Any]:
    """Build the falsification request payload.

    The request is immutable after execution begins — validated by a stored
    SHA-256 digest that the result must echo back.
    """
    inner = task.get("task", task) if isinstance(task, dict) else {}
    budget = resolve_budget()

    # Capture the authoritative worktree's HEAD revision.
    try:
        head_rev = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head_rev = ""

    try:
        base_rev = subprocess.run(
            ["git", "-C", str(worktree), "merge-base", "HEAD", "main"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if not base_rev:
            base_rev = head_rev
    except (OSError, subprocess.SubprocessError):
        base_rev = head_rev

    # Capture authoritative state for content-binding (Phases 4-5).
    # The attacked contents = HEAD + staged diff + unstaged diff.
    try:
        staged_proc = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--cached"],
            capture_output=True, text=True, timeout=10,
        )
        staged_diff = staged_proc.stdout if staged_proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        staged_diff = ""

    try:
        unstaged_proc = subprocess.run(
            ["git", "-C", str(worktree), "diff"],
            capture_output=True, text=True, timeout=10,
        )
        unstaged_diff = unstaged_proc.stdout if unstaged_proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        unstaged_diff = ""

    # Compute a content tree digest covering HEAD + all diffs.
    content_digest_input = head_rev + base_rev + staged_diff + unstaged_diff
    for cf in sorted(changed_files):
        content_digest_input += cf
    content_digest = hashlib.sha256(content_digest_input.encode("utf-8")).hexdigest()

    payload: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "run_id": run_id,
        "task_id": inner.get("id", inner.get("task_id", "")),
        "title": inner.get("title", ""),
        "objective": inner.get("objective", ""),
        "acceptance_criteria": inner.get("acceptance_criteria", []),
        "done_when": inner.get("done_when", ""),
        "scope_in": inner.get("scope_in", []),
        "scope_out": inner.get("scope_out", []),
        "forbidden_files": inner.get("forbidden_files", []),
        "authoritative_worktree": str(worktree),
        "base_revision": base_rev,
        "head_revision": head_rev,
        # Content binding (Phase 4): captures the exact state under attack.
        "staged_diff_digest": hashlib.sha256((staged_diff or "").encode("utf-8")).hexdigest() if staged_diff else "",
        "unstaged_diff_digest": hashlib.sha256((unstaged_diff or "").encode("utf-8")).hexdigest() if unstaged_diff else "",
        "content_digest": content_digest,
        "changed_files": changed_files,
        "routing_reasons": routing_reasons,
        "risk_classification": "high" if routing_reasons else "low",
        "budget": budget,
        "result_path": str(state_dir / f"falsification-result_{run_id}.json"),
        "agent_contract": {
            "tools": ["Read", "Grep", "Glob", "Bash"],
            "read_only_authoritative": True,
            "output_artifact": f"falsification-result_{run_id}.json",
            "output_schema": RESULT_SCHEMA,
        },
    }

    # Compute and store digest for immutability validation.
    digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["request_digest"] = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    return payload


# ---------------------------------------------------------------------------
# Disposable attack worktree
# ---------------------------------------------------------------------------

def create_attack_worktree(
    authoritative_worktree: Path,
    run_id: str,
    head_revision: str,
    scope_in: list[str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Create a disposable Git worktree from the authoritative worktree's HEAD,
    then materialize the full authoritative state (staged, unstaged, untracked).

    Uses a Git worktree (not a clone) because:
    - it's instant (no file copy);
    - it shares the object database (no disk waste);
    - it's isolated (separate working tree, separate branch);
    - it can be removed with `git worktree remove --force`.

    Returns (attack_path, materialization_report).
    The attacker may mutate the attack worktree. The authoritative worktree
    is never writable. Without this materialization, the attacker would receive
    HEAD-only code — missing uncommitted changes that are under review.
    """
    worktree_root = Path(os.environ.get("GO_WORKTREE_ROOT", "P:/worktrees"))
    ts = int(time.time())
    attack_path = worktree_root / f"falsify-{ts}-{run_id[:8]}"
    branch = f"falsify/{run_id[:8]}"

    # Resolve the repo root for the authoritative worktree.
    try:
        repo_root = subprocess.run(
            ["git", "-C", str(authoritative_worktree), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        repo_root = str(authoritative_worktree)

    proc = subprocess.run(
        ["git", "-C", repo_root, "worktree", "add", "-b", branch, "-f",
         str(attack_path), head_revision or "HEAD"],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to create attack worktree: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    # Materialize the full authoritative state (staged, unstaged, untracked).
    mat_report = materialize_authoritative_state(
        authoritative_worktree, attack_path, head_revision, scope_in,
    )
    return attack_path, mat_report


def cleanup_attack_worktree(attack_path: Path) -> dict[str, Any]:
    """Remove the disposable attack worktree and its branch.

    Returns a cleanup report dict: {cleaned: bool, errors: [str]}.
    """
    report: dict[str, Any] = {"cleaned": False, "errors": [], "path": str(attack_path)}
    if not attack_path.exists():
        report["cleaned"] = True
        report["note"] = "already removed"
        return report

    # Find the repo root to remove the worktree via git.
    try:
        repo_root = subprocess.run(
            ["git", "-C", str(attack_path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        repo_root = None

    if repo_root:
        proc = subprocess.run(
            ["git", "-C", repo_root, "worktree", "remove", "--force", str(attack_path)],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            report["errors"].append(f"worktree remove: {proc.stderr.strip()}")

    # If the worktree dir still exists, force-remove it.
    if attack_path.exists():
        try:
            shutil.rmtree(attack_path, ignore_errors=True)
        except OSError as e:
            report["errors"].append(f"rmtree: {e}")

    # Prune the worktree registration.
    if repo_root:
        subprocess.run(
            ["git", "-C", repo_root, "worktree", "prune"],
            capture_output=True, timeout=10,
        )

    report["cleaned"] = not attack_path.exists()
    return report


def verify_authoritative_unchanged(
    authoritative_worktree: Path,
    head_revision: str,
    expected_staged_digest: str = "",
    expected_unstaged_digest: str = "",
) -> dict[str, Any]:
    """Verify the authoritative worktree was not modified.

    Checks HEAD, staged diff, and unstaged diff. Returns a report dict with
    per-check results so the caller can surface exactly what changed.
    """
    report: dict[str, Any] = {"ok": True, "head_match": False, "staged_match": True,
                               "unstaged_match": True, "digests": {}}

    # HEAD check.
    try:
        current_head = subprocess.run(
            ["git", "-C", str(authoritative_worktree), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        current_head = ""
    report["head_match"] = bool(current_head and current_head == head_revision)
    report["digests"]["head"] = current_head[:12] if current_head else ""

    # Staged diff digest.
    if expected_staged_digest:
        try:
            sp = subprocess.run(
                ["git", "-C", str(authoritative_worktree), "diff", "--cached"],
                capture_output=True, text=True, timeout=10,
            )
            current_staged = sp.stdout if sp.returncode == 0 else ""
            import hashlib as _hl
            actual = _hl.sha256(current_staged.encode("utf-8")).hexdigest()
            report["staged_match"] = actual == expected_staged_digest
        except (OSError, subprocess.SubprocessError):
            report["staged_match"] = False

    # Unstaged diff digest.
    if expected_unstaged_digest:
        try:
            up = subprocess.run(
                ["git", "-C", str(authoritative_worktree), "diff"],
                capture_output=True, text=True, timeout=10,
            )
            current_unstaged = up.stdout if up.returncode == 0 else ""
            import hashlib as _hl
            actual = _hl.sha256(current_unstaged.encode("utf-8")).hexdigest()
            report["unstaged_match"] = actual == expected_unstaged_digest
        except (OSError, subprocess.SubprocessError):
            report["unstaged_match"] = False

    report["ok"] = report["head_match"] and report["staged_match"] and report["unstaged_match"]
    return report


# ---------------------------------------------------------------------------
# Result validation
# ---------------------------------------------------------------------------

def validate_falsification_result(
    result: dict[str, Any],
    request: dict[str, Any],
    expected_run_id: str,
) -> tuple[bool, str]:
    """Validate that a falsification result matches its request binding.

    Returns (valid, reason). Invalid results fail closed.
    """
    if not isinstance(result, dict):
        return False, "result is not a JSON object"

    schema = result.get("schema", "")
    if schema != RESULT_SCHEMA:
        return False, f"schema mismatch: expected {RESULT_SCHEMA}, got {schema}"

    # Run ID binding.
    result_run_id = result.get("run_id", "")
    if result_run_id != expected_run_id:
        return False, f"run_id mismatch: expected {expected_run_id}, got {result_run_id}"

    # Request digest binding.
    expected_digest = request.get("request_digest", "")
    result_digest = result.get("request_digest", "")
    if expected_digest and result_digest != expected_digest:
        return False, f"request_digest mismatch: expected {expected_digest}, got {result_digest}"

    # Revision binding.
    for field in ("base_revision", "head_revision"):
        if request.get(field) and result.get(field, "") != request[field]:
            return False, f"{field} mismatch: expected {request[field]}, got {result.get(field)}"

    # Task ID binding.
    if request.get("task_id") and result.get("task_id", "") != request["task_id"]:
        return False, f"task_id mismatch"

    # Verdict must be a known value.
    verdict = result.get("verdict", "")
    if verdict not in _VALID_VERDICTS:
        return False, f"verdict '{verdict}' not in {sorted(_VALID_VERDICTS)}"

    # FALSIFIED requires at least one counterexample with executable reproduction.
    if verdict == "FALSIFIED":
        counterexamples = result.get("counterexamples", [])
        if not counterexamples:
            return False, "FALSIFIED verdict requires at least one counterexample"
        for i, ce in enumerate(counterexamples):
            if not isinstance(ce, dict):
                return False, f"counterexample {i} is not a dict"
            command = ce.get("command", "")
            if not command:
                return False, f"counterexample {i} missing 'command' — prose-only claims rejected"
            expected = ce.get("expected_result", "")
            actual = ce.get("actual_result", "")
            if not expected or not actual:
                return False, f"counterexample {i} missing expected/actual result"
            claim = ce.get("claim_falsified", "")
            if not claim:
                return False, f"counterexample {i} missing claim_falsified"

    return True, "valid"


# ---------------------------------------------------------------------------
# Verdict policy
# ---------------------------------------------------------------------------

def apply_verdict_policy(verdict: str) -> str:
    """Apply the MVP completion policy to a falsification verdict.

    Returns: 'proceed' | 'block' | 'advisory'.
    - proceed: the completion marker may be written
    - block: the completion marker must NOT be written; hard-block
    - advisory: proceed but record advisory
    """
    if verdict == "NOT_FALSIFIED_WITHIN_BUDGET":
        return "proceed"
    if verdict == "FALSIFIED":
        return "block"
    # MVP: INCONCLUSIVE, HARNESS_FAILURE, BUDGET_EXHAUSTED all fail closed.
    return "block"


# ---------------------------------------------------------------------------
# CLI (called by orchestrate.py)
# ---------------------------------------------------------------------------

def main() -> int:
    """Not invoked directly by the orchestrator — it imports the functions.
    Kept for manual diagnostic use."""
    print("falsification_gate.py — imported by orchestrate.py, not run directly.")
    print(f"Schema: {REQUEST_SCHEMA} / {RESULT_SCHEMA}")
    print(f"Verdicts: {sorted(_VALID_VERDICTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
