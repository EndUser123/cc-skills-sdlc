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
    # Hardening budgets (Part 2): command count is enforced inside
    # run_constrained_command; file-count + aggregate bytes are enforced at
    # resume time via measure_attack_worktree_writes.
    "max_commands": 20,
    "max_aggregate_bytes": 10 * 1024 * 1024,  # 10 MiB across the attack worktree
    "output_byte_cap": 1 * 1024 * 1024,  # 1 MiB per captured command stream
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
    session_id: str = "",
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
        "session_id": session_id or "",
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
        # Agent identity (Part 3): requested policy + UNAVAILABLE sentinels.
        # The main-loop Claude fills actual fields at spawn time.
        "agent_identity": default_agent_identity("advisory", session_id),
    }

    # Compute and store digest for immutability validation.
    digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["request_digest"] = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    return payload


# ---------------------------------------------------------------------------

# (Old git-apply-based materialize_authoritative_state removed: it was broken
# on Windows because the diff round-tripped through Python text mode, which
# converts LF->CRLF and corrupts the patch -> "patch does not apply". The
# active implementation below is copy-based and digest-proven.)

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
    *,
    ledger: list | None = None,
    attack_worktree: str | None = None,
) -> tuple[bool, str]:
    """Validate that a falsification result matches its request binding.

    Returns (valid, reason). Invalid results fail closed.

    When ``ledger`` and ``attack_worktree`` are provided (resume path), each
    FALSIFIED counterexample must additionally pass execution-provenance
    verification: it must reference a real ledger entry with correct
    run/request/worktree binding whose recorded command and output match the
    claim. Without harness evidence, the counterexample is rejected.
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
            # Execution provenance (Part 1): when a ledger is available, the
            # counterexample must be backed by a real command execution with
            # correct run/request/worktree binding. No ledger => no trust.
            if ledger is not None and attack_worktree is not None:
                pok, preason = verify_counterexample_provenance(
                    ce, ledger, request, expected_run_id, attack_worktree)
                if not pok:
                    return False, f"counterexample {i} provenance rejected: {preason}"

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

# ---------------------------------------------------------------------------
# Part 1: Constrained command runner + append-only run-scoped command ledger
# ---------------------------------------------------------------------------
# Every accepted FALSIFIED counterexample must reference a ledger entry that
# proves its reproduction command actually executed inside the declared attack
# worktree. The validator rejects counterexamples whose command/output cannot
# be matched to a ledger entry with correct run/request/worktree binding.

LEDGER_SCHEMA = "go.falsification-command-ledger.v1"

# Output captured per command is capped (default 1 MiB per stream).
_OUTPUT_BYTE_CAP_DEFAULT = 1 * 1024 * 1024


def ledger_path(state_dir, run_id: str) -> Path:
    """Path to the append-only command ledger for a run."""
    return Path(state_dir) / f"falsification-command-ledger_{run_id}.jsonl"


def load_ledger(state_dir, run_id: str) -> list:
    """Load all ledger entries for a run (append-only JSONL)."""
    p = ledger_path(state_dir, run_id)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest() if b else hashlib.sha256(b"").hexdigest()


def run_constrained_command(
    state_dir,
    run_id: str,
    request: dict,
    attack_worktree,
    command: str,
    *,
    timeout: float,
    budget_state: dict,
    shell: bool = True,
) -> dict:
    """Run one reproduction command inside the attack worktree under budget.

    Enforces: cwd == attack_worktree (resolved), per-command timeout,
    command-count budget. Captures bounded stdout/stderr to artifact files and
    appends an immutable ledger entry. Mutates budget_state in place
    (commands_run, bytes_written). Returns the ledger entry dict.

    On command-count exhaustion or a missing attack worktree, returns an entry
    with rejected set and ran=False (no subprocess spawned).
    """
    state_dir = Path(state_dir)
    aw = Path(attack_worktree).resolve()
    entry_no = len(load_ledger(state_dir, run_id)) + 1
    entry_id = f"{run_id}-cmd-{entry_no:04d}"
    base = {
        "schema": LEDGER_SCHEMA,
        "entry_id": entry_id,
        "run_id": run_id,
        "request_digest": request.get("request_digest", "") if isinstance(request, dict) else "",
        "attack_worktree": str(aw),
        "cwd": str(aw),
        "command": command,
        "shell": shell,
        "ran": False,
        "completed": False,
        "timed_out": False,
        "exit_code": None,
    }

    # Budget: command count.
    max_commands = int(budget_state.get("max_commands", 0) or 0)
    if max_commands and budget_state.get("commands_run", 0) >= max_commands:
        base["rejected"] = "command_count_exhausted"
        return base

    if not aw.is_dir():
        base["rejected"] = "attack_worktree_missing"
        return base

    budget_state["commands_run"] = budget_state.get("commands_run", 0) + 1
    cap = int(budget_state.get("output_byte_cap", _OUTPUT_BYTE_CAP_DEFAULT))

    start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    stdout_b = b""
    stderr_b = b""
    timed_out = False
    exit_code = None
    try:
        proc = subprocess.run(
            command if shell else [command],
            cwd=str(aw),
            shell=shell,
            capture_output=True,
            timeout=timeout,
        )
        exit_code = proc.returncode
        stdout_b = (proc.stdout or b"")
        stderr_b = (proc.stderr or b"")
        if isinstance(stdout_b, str):
            stdout_b = stdout_b.encode("utf-8", "replace")
        if isinstance(stderr_b, str):
            stderr_b = stderr_b.encode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = e.stdout or b""
        err = e.stderr or b""
        if isinstance(out, str):
            out = out.encode("utf-8", "replace")
        if isinstance(err, str):
            err = err.encode("utf-8", "replace")
        stdout_b = out
        stderr_b = err
        exit_code = None
    except (OSError, subprocess.SubprocessError) as e:
        stderr_b = str(e).encode("utf-8", "replace")
        exit_code = -1
    duration_ms = int((time.time() - t0) * 1000)
    end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    stdout_b = stdout_b[:cap]
    stderr_b = stderr_b[:cap]

    stdout_art = state_dir / f"falsification-cmd-stdout_{run_id}_{entry_no:04d}.bin"
    stderr_art = state_dir / f"falsification-cmd-stderr_{run_id}_{entry_no:04d}.bin"
    try:
        stdout_art.write_bytes(stdout_b)
        stderr_art.write_bytes(stderr_b)
    except OSError:
        pass

    entry = dict(base)
    entry.update({
        "ran": True,
        "completed": (not timed_out) and exit_code is not None,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "start_ts": start_iso,
        "end_ts": end_iso,
        "duration_ms": duration_ms,
        "timeout_seconds": timeout,
        "stdout_digest": _sha_bytes(stdout_b),
        "stderr_digest": _sha_bytes(stderr_b),
        "stdout_bytes": len(stdout_b),
        "stderr_bytes": len(stderr_b),
        "stdout_artifact": str(stdout_art),
        "stderr_artifact": str(stderr_art),
    })

    # Append-only ledger.
    try:
        with ledger_path(state_dir, run_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    budget_state["bytes_written"] = budget_state.get("bytes_written", 0) + len(stdout_b) + len(stderr_b)
    return entry


def verify_counterexample_provenance(
    counterexample: dict,
    ledger: list,
    request: dict,
    run_id: str,
    attack_worktree,
) -> tuple:
    """Verify a FALSIFIED counterexample is backed by a real ledger entry.

    Returns (ok, reason). Rejects when:
      - no ledger_entry_id referenced;
      - referenced entry absent;
      - run_id / request_digest / attack_worktree binding mismatches;
      - claimed command differs from recorded command;
      - referenced command never completed (timed out);
      - claimed output inconsistent with the recorded artifact.
    """
    if not isinstance(counterexample, dict):
        return False, "counterexample is not a dict"
    eid = counterexample.get("ledger_entry_id", "")
    if not eid:
        return False, "counterexample missing ledger_entry_id - no execution evidence"
    entry = None
    for e in ledger:
        if isinstance(e, dict) and e.get("entry_id") == eid:
            entry = e
            break
    if entry is None:
        return False, f"ledger entry {eid} not found - fabricated command"
    # Binding: run.
    if entry.get("run_id") != run_id:
        return False, f"ledger entry run_id mismatch: {entry.get('run_id')} != {run_id}"
    # Binding: request.
    exp_digest = request.get("request_digest", "") if isinstance(request, dict) else ""
    if exp_digest and entry.get("request_digest") != exp_digest:
        return False, "ledger entry request_digest mismatch (foreign request)"
    # Binding: attack worktree (resolved identity).
    aw_resolved = str(Path(attack_worktree).resolve())
    if entry.get("attack_worktree") != aw_resolved:
        return False, "ledger entry attack_worktree mismatch (foreign worktree)"
    # Command must match.
    if entry.get("command") != counterexample.get("command"):
        return False, "claimed command differs from recorded command"
    # Must have completed.
    if not entry.get("completed"):
        return False, "referenced command did not complete (timed out)"
    # Output consistency.
    claimed_output = (counterexample.get("output") or "")
    if claimed_output:
        recorded = ""
        try:
            recorded = Path(entry.get("stdout_artifact", "")).read_text(encoding="utf-8", errors="replace")
        except OSError:
            recorded = ""
        try:
            recorded += "\n" + Path(entry.get("stderr_artifact", "")).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        claimed_digest = counterexample.get("output_digest", "")
        if claimed_digest:
            if claimed_digest != entry.get("stdout_digest"):
                return False, "claimed output_digest inconsistent with recorded stdout"
        else:
            if claimed_output.strip() not in recorded:
                return False, "claimed output not present in recorded artifact"
    return True, "provenance verified"


# ---------------------------------------------------------------------------
# Part 2: Attack-worktree write measurement (file-count + aggregate bytes)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Part 4: Session-pointer terminalization
# ---------------------------------------------------------------------------
# A terminal falsification verdict (FALSIFIED, or fail-closed
# INCONCLUSIVE/HARNESS_FAILURE/BUDGET_EXHAUSTED) must not leave G4/G5 in a
# continuation loop. The session pointer written during task selection is
# removed IFF it points at this exact run_id + go_state_dir. Foreign or newer
# pointers are never touched. Fail-silent on stale/foreign/missing state.

def _artifacts_root() -> Path:
    return Path(os.environ.get("GO_ARTIFACTS_ROOT", str(Path.home() / ".claude" / ".artifacts")))


def terminalize_session_pointer(session_id: str, run_id: str, go_state_dir) -> dict:
    """Remove the session pointer for (session_id) iff it binds to this exact
    run_id + go_state_dir. Never touches foreign or newer pointers.

    Returns a report dict. Fail-silent (no raise) on any error.
    """
    report = {"terminalized": False, "reason": "", "path": "",
              "matched_run_id": False, "matched_state_dir": False}
    if not session_id or not run_id:
        report["reason"] = "missing session_id or run_id"
        return report
    ptr = _artifacts_root() / "go-sessions" / f"{session_id}.json"
    report["path"] = str(ptr)
    if not ptr.is_file():
        report["reason"] = "pointer absent (already terminalized or never written)"
        report["terminalized"] = True
        return report
    try:
        data = json.loads(ptr.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report["reason"] = "pointer unreadable - leaving untouched (foreign state)"
        return report
    same_run = data.get("run_id") == run_id
    same_state = str(data.get("go_state_dir", "")) == str(go_state_dir)
    report["matched_run_id"] = same_run
    report["matched_state_dir"] = same_state
    if not (same_run and same_state):
        report["reason"] = "pointer is foreign or newer - not touched"
        return report
    try:
        ptr.unlink()
        report["terminalized"] = True
        report["reason"] = "terminalized (exact run + state match)"
    except OSError as e:
        report["reason"] = f"unlink failed: {e}"
    return report


# ---------------------------------------------------------------------------
# Agent identity (Part 3): default block recorded when the runtime exposes
# nothing. The main-loop Claude fills actual fields at spawn time.
# ---------------------------------------------------------------------------

def default_agent_identity(requested_model_policy: str = "advisory",
                           parent_session_id: str = "") -> dict:
    """Return an agent_identity block with UNAVAILABLE_FROM_RUNTIME sentinels
    for fields the harness cannot introspect from a Bash-invoked orchestrator."""
    return {
        "requested_model_policy": requested_model_policy,
        "actual_model": "UNAVAILABLE_FROM_RUNTIME",
        "effort": "UNAVAILABLE_FROM_RUNTIME",
        "agent_type": "UNAVAILABLE_FROM_RUNTIME",
        "parent_session_id": parent_session_id or "UNAVAILABLE_FROM_RUNTIME",
        "model_matches_implementing_model": "UNAVAILABLE_FROM_RUNTIME",
    }


# ---------------------------------------------------------------------------
# Transactional, digest-proven materialization (Windows-safe, copy-based)
# ---------------------------------------------------------------------------
# git apply is unreliable on Windows when the diff is round-tripped through
# Python text mode (LF->CRLF corruption -> "patch does not apply"). Instead of
# trusting git apply, we copy the exact authoritative working-tree bytes for
# every changed file into the attack worktree, then PROVE equality by content
# digest. A failed transfer never permits attacker execution: the orchestrator
# fails closed before SPAWN_FALSIFIER when digest_match is False.


def _safe_join(base: Path, rel: str) -> Path | None:
    """Resolve rel under base, rejecting path traversal and symlink escape."""
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel or rel == ".":
        return None
    target = (base / rel).resolve()
    try:
        base_r = base.resolve()
    except OSError:
        return None
    try:
        target.relative_to(base_r)
    except ValueError:
        return None
    return target


def _authoritative_changed_files(authoritative_worktree: Path) -> list[str]:
    """Enumerate every changed path (staged + unstaged + untracked) relative to
    HEAD. Returns sorted unique list."""
    aw = Path(authoritative_worktree)
    files: set[str] = set()
    for args in (["diff", "--name-only", "HEAD"],
                 ["ls-files", "--others", "--exclude-standard"]):
        try:
            pr = subprocess.run(["git", "-C", str(aw)] + args,
                                capture_output=True, text=True, timeout=15)
            if pr.returncode == 0:
                for ln in pr.stdout.splitlines():
                    ln = ln.strip()
                    if ln:
                        files.add(ln)
        except (OSError, subprocess.SubprocessError):
            pass
    return sorted(files)


def _file_content_sha(path: Path) -> str:
    """SHA-256 of a file's raw bytes, or '<absent>' if missing."""
    try:
        if not path.is_file() or path.is_symlink():
            # Symlinks are not transferred (escape risk); treat as absent.
            return "<absent>"
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "<absent>"


def compute_authoritative_tree_digest(authoritative_worktree) -> str:
    """Digest over (path + content-sha) of every changed file in the
    authoritative worktree. This is the exact content the attacker must see."""
    aw = Path(authoritative_worktree)
    files = _authoritative_changed_files(aw)
    h = hashlib.sha256()
    for rel in files:
        csha = _file_content_sha(aw / rel)
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(csha.encode("ascii"))
        h.update(b"\x00")
    return h.hexdigest()


def materialize_authoritative_state(
    authoritative_worktree: Path,
    attack_path: Path,
    head_revision: str,
    scope_in: list[str] | None = None,
) -> dict[str, Any]:
    """Transactionally copy authoritative working-tree state into the attack
    worktree and PROVE it by content digest.

    Copy-based (no git apply): for every changed file, copy the authoritative
    bytes (or delete if absent). Untracked files copied the same way. Symlinks
    and path-traversal targets are rejected. The final attack-tree digest of
    the changed set MUST equal the authoritative digest, otherwise the report
    records digest_match=False and the orchestrator must fail closed.
    """
    auth = Path(authoritative_worktree)
    attack = Path(attack_path)
    report: dict[str, Any] = {
        "method": "copy",
        "staged_applied": False,
        "unstaged_applied": False,
        "untracked_copied": 0,
        "copied": [],
        "deleted": [],
        "rejected": [],
        "errors": [],
        "files_in_scope": 0,
        "expected_digest": "",
        "actual_digest": "",
        "digest_match": False,
    }
    files = _authoritative_changed_files(auth)
    report["files_in_scope"] = len(files)

    for rel in files:
        src = _safe_join(auth, rel)
        dst = _safe_join(attack, rel)
        if src is None or dst is None:
            report["rejected"].append(rel)
            continue
        src_exists = src.is_file() and not src.is_symlink()
        if src_exists:
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
                report["copied"].append(rel)
            except OSError as e:
                report["errors"].append(f"copy {rel}: {e}")
        else:
            # Authoritative file was deleted (or is a symlink we refuse).
            try:
                if dst.exists():
                    dst.unlink()
                report["deleted"].append(rel)
            except OSError as e:
                report["errors"].append(f"delete {rel}: {e}")

    report["staged_applied"] = True
    report["unstaged_applied"] = True
    report["untracked_copied"] = len([r for r in report["copied"]
                                      if r not in _head_tracked_set(auth)])

    expected = compute_authoritative_tree_digest(auth)
    actual = _attack_changed_digest(attack, files)
    report["expected_digest"] = expected
    report["actual_digest"] = actual
    report["digest_match"] = (expected == actual) and not report["errors"]
    return report


def _head_tracked_set(repo: Path) -> set[str]:
    try:
        pr = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD"],
                            capture_output=True, text=True, timeout=15)
        if pr.returncode == 0:
            return set(pr.stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        pass
    return set()


def _attack_changed_digest(attack: Path, files: list[str]) -> str:
    """Digest over (path + content-sha) of the same file set in the attack
    worktree, for equality comparison with the authoritative digest."""
    h = hashlib.sha256()
    for rel in files:
        csha = _file_content_sha(attack / rel)
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(csha.encode("ascii"))
        h.update(b"\x00")
    return h.hexdigest()


def capture_materialization_baseline(attack_worktree) -> dict[str, Any]:
    """Snapshot the attack worktree state immediately after materialization,
    BEFORE the Agent runs. The resume path measures attacker writes as the
    delta from this baseline so the legitimate materialized diff does NOT
    consume the attacker mutation budget."""
    aw = Path(attack_worktree)
    changed = _authoritative_changed_files(aw)
    snapshot: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for rel in changed:
        snapshot[rel] = _file_content_sha(aw / rel)
        try:
            sizes[rel] = (aw / rel).stat().st_size
        except OSError:
            sizes[rel] = 0
    return {
        "baseline_files": sorted(snapshot.keys()),
        "baseline_digests": snapshot,
        "baseline_sizes": sizes,
        "baseline_digest": hashlib.sha256(
            "".join(f"{k}\x00{v}\x00" for k, v in sorted(snapshot.items())).encode("utf-8")
        ).hexdigest(),
    }


def measure_attacker_writes(attack_worktree, baseline: dict[str, Any]) -> dict[str, Any]:
    """Measure attacker-induced writes as the DELTA from the post-materialization
    baseline. Files present in the materialized diff (legitimate implementation
    under review) consume ZERO attacker budget. Only Agent-created files and
    Agent edits to materialized files (content changed vs baseline) count.

    Returns {files_changed, bytes_written, files[], method}.
    """
    aw = Path(attack_worktree)
    baseline_digests = (baseline or {}).get("baseline_digests", {}) if isinstance(baseline, dict) else {}
    baseline_files = set(baseline_digests.keys())

    current = _authoritative_changed_files(aw)
    current_digests: dict[str, str] = {}
    for rel in current:
        current_digests[rel] = _file_content_sha(aw / rel)

    attacker_files: list[str] = []
    total_bytes = 0
    # New files the Agent created (not in baseline).
    for rel in sorted(set(current_digests) - baseline_files):
        p = aw / rel
        if p.is_file():
            attacker_files.append(rel)
            try:
                total_bytes += p.stat().st_size
            except OSError:
                pass
    # Agent-edited materialized files (content differs from baseline).
    # For modified files, only charge the delta (net new bytes) so the
    # legitimate materialized content does not consume attacker budget.
    for rel in sorted(baseline_files & set(current_digests)):
        if current_digests[rel] != baseline_digests.get(rel):
            p = aw / rel
            if p.is_file():
                attacker_files.append(rel)
                try:
                    current_size = p.stat().st_size
                    # Estimate the materialized baseline size from the first
                    # measurement before agent touches anything.
                    bl_sha = baseline_digests.get(rel, "")
                    # We stored the baseline size alongside the digest in
                    # capture_materialization_baseline.
                    bl_size = (baseline.get("baseline_sizes", {}).get(rel, 0)
                               if isinstance(baseline, dict) else 0)
                    # Charge only the delta relative to materialized baseline.
                    total_bytes += max(0, current_size - bl_size)
                except OSError:
                    total_bytes += 0
    return {
        "files_changed": len(attacker_files),
        "bytes_written": total_bytes,
        "files": attacker_files,
        "method": "delta-from-materialization-baseline",
    }
