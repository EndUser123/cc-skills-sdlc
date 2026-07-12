#!/usr/bin/env python3
"""Receipt-based completion verifier for /task verify and /task clean.

Replaces the old subject-based verify_completed.py (basename / commit-message /
pickaxe / grep), which produced false positives across the monorepo. This
verifier consults ONLY durable completion receipts written by task_receipt.py.

Buckets (deterministic):
    VERIFIED     -- receipt exists, evidence_class VERIFIED, repo matches,
                    and final_commit_sha (if any) is still reachable
    REVIEW       -- receipt exists with evidence_class REVIEW (committed but
                    no passing verification) -- NOT deletion-safe
    NO_EVIDENCE  -- no receipt for the task, OR receipt pertains to a
                    different repo (cross-terminal / cross-repo guard)
    STALE        -- receipt's final_commit_sha is no longer reachable in its
                    repo (history rewritten / commit gone) -- re-verify needed
    BLOCKED      -- receipt present but malformed / unreadable

Deletion rule (enforced by clean): ONLY exact task-linked VERIFIED receipts
authorize removal. status=completed alone NEVER authorizes deletion. Tasks
without VERIFIED receipts are left untouched with the exact reason.

Exit codes (deterministic):
    0 -- every queried task is VERIFIED (clean --apply: all candidates were VERIFIED)
    1 -- at least one task is not VERIFIED (REVIEW/NO_EVIDENCE/STALE/BLOCKED)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# File lock for concurrent-safe tracker access (same module the tracker hook uses).
try:
    from __lib.file_lock import FileLock
except ImportError:
    try:
        from file_lock import FileLock
    except ImportError:
        FileLock = None  # type: ignore[assignment,misc]

# Import the receipt store from the sibling module.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import task_receipt as receipt  # noqa: E402

BUCKETS = ("VERIFIED", "REVIEW", "NO_EVIDENCE", "STALE", "BLOCKED")

# Existing tracker persistence (the only task "database" is the native task list;
# this mirror is what /task reads for cross-terminal continuity).
# Shared state root, matching the tracker hook's _bootstrap.state_root().
# Cf. P:/packages/.claude-marketplace/plugins/cc-aca-observability/__lib/_bootstrap.py
_STATE_ROOT = Path(os.environ.get("CSF_STATE_DIR", "P:/.claude/state"))
TRACKER_DIR = Path(os.environ.get("TASK_STATE_DIR", str(_STATE_ROOT / "task_tracker")))


def _norm_repo(p) -> str:
    """Normalize a repo path for exact comparison (case-insensitive on Windows)."""
    if not p:
        return ""
    s = str(p).replace("\\", "/").rstrip("/")
    return s.lower()


def _sha_reachable_in(repo_path: str, sha: str | None) -> bool:
    if not sha:
        return True  # no sha recorded -- nothing to go stale
    return receipt.sha_reachable(sha, repo_path)


def _resolve_terminal_id() -> str:
    return os.environ.get("CLAUDE_TERMINAL_ID") or os.environ.get("WT_SESSION", "unknown")


def _detect_current_repo(repo_arg: str | None) -> str | None:
    if repo_arg:
        return repo_arg
    return receipt.git_toplevel(os.getcwd())


def verify_task(task_id: str, *, current_repo: str | None = None, terminal_id: str | None = None) -> tuple[str, str]:
    """Return (bucket, reason) for a single task id."""
    tid = terminal_id or _resolve_terminal_id()
    path = receipt.receipt_path(task_id, terminal_id=tid)
    if not path.exists():
        # Migration fallback: check legacy flat layout AND other terminal dirs.
        # For cross-terminal results, verify the stored terminal_id matches;
        # otherwise the path might be from another terminal's task with the
        # same numeric ID (SR-1 guard).
        candidates = receipt.receipt_path_any_terminal(task_id)
        if candidates:
            # Prefer the one matching the caller's terminal_id.
            match_path = None
            for cp in candidates:
                try:
                    r = json.loads(cp.read_text(encoding="utf-8"))
                    if r.get("terminal_id", "") == tid:
                        match_path = cp
                        break
                except (OSError, json.JSONDecodeError, ValueError):
                    continue
            path = match_path if match_path else path
            # If we found receipts but none matching the terminal_id, we still
            # don't have evidence for THIS terminal's task. The cross-repo guard
            # below will eventually block even cross-terminal ones, but the
            # correct block is NO_EVIDENCE (wrong terminal), not VERIFIED.
            # NO_EVIDENCE is returned when the receipt body doesn't load.
    file_exists = path.is_file()
    r = receipt.read_receipt(task_id)
    if r is None:
        # Distinguish malformed (file present but unreadable) from missing.
        if file_exists:
            return "BLOCKED", "receipt for %s is unreadable/malformed" % task_id
        return "NO_EVIDENCE", "no completion receipt for task %s" % task_id
    if not isinstance(r, dict) or "task_id" not in r or "evidence_class" not in r:
        return "BLOCKED", "receipt for %s is malformed" % task_id

    # Cross-repo / cross-terminal guard: a receipt from a different repo does
    # NOT constitute evidence for the task in the current repo.
    if current_repo:
        rec_repo = r.get("repo", "")
        if rec_repo and _norm_repo(rec_repo) != _norm_repo(current_repo):
            return (
                "NO_EVIDENCE",
                "receipt repo %s != current repo %s (cross-repo; not evidence)" % (rec_repo, current_repo),
            )

    final_sha = r.get("final_commit_sha")
    repo_for_check = r.get("repo") or current_repo or os.getcwd()
    if final_sha and not _sha_reachable_in(repo_for_check, final_sha):
        return "STALE", "final_commit_sha %s no longer reachable in %s" % (final_sha, repo_for_check)

    ev = r.get("evidence_class", "NO_EVIDENCE")
    if ev == "VERIFIED":
        return "VERIFIED", "receipt VERIFIED (%d changed files, %d verification cmds)" % (
            len(r.get("changed_files", [])), len(r.get("verification", [])))
    if ev == "REVIEW":
        return "REVIEW", "receipt REVIEW (committed but no passing verification)"
    return "NO_EVIDENCE", "receipt evidence_class=%s" % ev


def verify_many(task_ids, *, current_repo: str | None = None, terminal_id: str | None = None) -> dict:
    tid = terminal_id or _resolve_terminal_id()
    buckets = {b: [] for b in BUCKETS}
    detail = {}
    for t in task_ids:
        bucket, reason = verify_task(t, current_repo=current_repo, terminal_id=tid)
        buckets[bucket].append(t)
        detail[t] = {"bucket": bucket, "reason": reason}
    return {"buckets": buckets, "detail": detail}


def _render(report: dict) -> str:
    lines = []
    for b in BUCKETS:
        ids = report["buckets"][b]
        lines.append("%s: %d" % (b, len(ids)))
    lines.append("")
    for b in BUCKETS:
        ids = report["buckets"][b]
        if not ids:
            continue
        lines.append("=== %s (%d) ===" % (b, len(ids)))
        for tid in sorted(ids, key=lambda t: str(t)):
            lines.append("  #%s  %s" % (tid, report["detail"][tid]["reason"]))
    return "\n".join(lines)


# --- clean ------------------------------------------------------------------

def _remove_from_tracker(task_id: str, tracker_dir: Path) -> int:
    """Remove a task from tracker *_tasks.json mirror files. Uses the same
    FileLock the tracker hook holds, so concurrent TaskCreate/TaskUpdate during
    clean does not lose tasks (SR-3 fix)."""
    changed = 0
    if not tracker_dir.exists() or FileLock is None:
        return 0
    for f in tracker_dir.glob("*_tasks.json"):
        # Derive lock path matching the tracker hook's convention:
        #   lock_path = get_state_dir() / f"{safe_terminal_id}_tasks.lock"
        # The *_tasks.json file has the same stem.
        lock_path = f.with_suffix(".lock")
        try:
            with FileLock(str(lock_path), timeout=5.0):
                # Re-read INSIDE the lock — file may have changed since iteration.
                data = json.loads(f.read_text(encoding="utf-8"))
                tasks = data.get("tasks") if isinstance(data, dict) else None
                if not isinstance(tasks, dict) or task_id not in tasks:
                    continue
                tasks.pop(task_id, None)
                tmp = f.with_suffix(".%s.tmp" % os.getpid())
                tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
                os.replace(tmp, f)
                changed += 1
        except (OSError, json.JSONDecodeError, ValueError, TimeoutError):
            continue
    return changed


def cmd_clean(args) -> int:
    """Delete only VERIFIED-receipt tasks from the tracker mirror. Dry-run by default.

    Receipts are NEVER deleted. The native live task list cannot be removed via
    API (no TaskDelete exists), so clean operates on the tracker persistence
    mirror that /task reads for cross-terminal continuity.
    """
    candidates = [str(x) for x in args.task_ids]
    if args.from_stdin:
        candidates = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
    if not candidates:
        print("no candidate task ids provided", file=sys.stderr)
        return 1

    current_repo = _detect_current_repo(args.repo)
    report = verify_many(candidates, current_repo=current_repo)
    deletable = report["buckets"]["VERIFIED"]

    print("Candidates: %d" % len(candidates))
    for b in BUCKETS:
        print("  %s: %d" % (b, len(report["buckets"][b])))

    if not deletable:
        print("\nNo VERIFIED tasks -- nothing deleted. Tasks left untouched:")
        for b in BUCKETS:
            for tid in report["buckets"][b]:
                print("  #%s [%s] %s" % (tid, b, report["detail"][tid]["reason"]))
        return 1

    print("\nVERIFIED (deletion-safe): %s" % (", ".join("#" + t for t in sorted(deletable))))
    if not args.apply:
        print("\nDRY RUN -- re-run with --apply to remove these from the tracker mirror.")
        print("Receipts are preserved either way.")
        return 0 if not (report["buckets"]["REVIEW"] or report["buckets"]["NO_EVIDENCE"]
                         or report["buckets"]["STALE"] or report["buckets"]["BLOCKED"]) else 1

    removed_files = 0
    for tid in sorted(deletable):
        removed_files += _remove_from_tracker(tid, Path(args.tracker_dir))
    print("\nRemoved %d VERIFIED task(s) from %d tracker file(s). Receipts preserved."
          % (len(deletable), removed_files))
    # exit 0 only if every candidate was VERIFIED
    return 0 if not (report["buckets"]["REVIEW"] or report["buckets"]["NO_EVIDENCE"]
                     or report["buckets"]["STALE"] or report["buckets"]["BLOCKED"]) else 1


def cmd_verify(args) -> int:
    candidates = [str(x) for x in args.task_ids]
    if args.from_stdin:
        candidates = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
    if not candidates:
        # default: verify every receipt we have
        candidates = sorted(receipt.list_receipts().keys(), key=lambda t: str(t))
        if not candidates:
            print("NO_EVIDENCE: 0 (no receipts and no task ids given)")
            return 1
    current_repo = _detect_current_repo(args.repo)
    report = verify_many(candidates, current_repo=current_repo)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(_render(report))
    # exit 0 iff every queried task is VERIFIED
    non_verified = sum(len(report["buckets"][b]) for b in BUCKETS if b != "VERIFIED")
    return 0 if non_verified == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Receipt-based /task verifier")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="bucket task ids by receipt evidence")
    v.add_argument("task_ids", nargs="*", help="task ids (default: all receipts)")
    v.add_argument("--from-stdin", action="store_true", help="read task ids from stdin (one per line)")
    v.add_argument("--repo", help="current repo (default: git toplevel of cwd)")
    v.add_argument("--json", action="store_true", help="emit JSON")
    v.set_defaults(func=cmd_verify)
    c = sub.add_parser("clean", help="delete only VERIFIED-receipt tasks from the tracker mirror")
    c.add_argument("task_ids", nargs="*", help="candidate task ids")
    c.add_argument("--from-stdin", action="store_true")
    c.add_argument("--repo")
    c.add_argument("--tracker-dir", default=str(TRACKER_DIR))
    c.add_argument("--apply", action="store_true", help="actually remove (default: dry-run)")
    c.set_defaults(func=cmd_clean)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
