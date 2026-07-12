#!/usr/bin/env python3
"""Durable completion-receipt store for the /task skill.

A completion receipt is deterministic, file-based evidence keyed by task ID. It
replaces the old subject-based verifier (basename / commit-message / pickaxe /
grep matches) which produced false positives across the monorepo.

Receipts are NOT a second task database -- the native task list (TaskCreate /
TaskUpdate / TaskList / TaskGet) remains the only task store. A receipt is
evidence metadata about how a task was completed.

Storage location (approved runtime state, NOT the skill/package dir):
    P:/.claude/state/task_receipts/{task_id}.json
overridable via TASK_RECEIPT_DIR (kept in sync with the done-evidence gate).

Receipt schema (receipt_version 1):
    task_id, terminal_id, session_id, repo, worktree, baseline_commit,
    final_commit_sha, changed_files[], verification[{command,exit_code,output_tail}],
    evidence_class (VERIFIED|REVIEW|NO_EVIDENCE), timestamp, verifier

Evidence classification:
    VERIFIED    -- at least one verification command exited 0
    REVIEW      -- no verification command, but a final_commit_sha was captured
    NO_EVIDENCE -- neither

Receipts are preserved after task deletion -- nothing here ever deletes a receipt.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

RECEIPT_VERSION = 1
DEFAULT_RECEIPT_DIR = Path(os.path.expanduser("~/.claude/state/task_receipts"))


def receipt_dir() -> Path:
    env = os.environ.get("TASK_RECEIPT_DIR")
    return Path(env) if env else DEFAULT_RECEIPT_DIR


def _safe_task_id(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(task_id)) or "unknown"


def receipt_path(task_id: str) -> Path:
    return receipt_dir() / f"{_safe_task_id(task_id)}.json"


def _git(args, cwd, timeout=10):
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def git_toplevel(cwd) -> str:
    return _git(["rev-parse", "--show-toplevel"], cwd) or str(Path(cwd).resolve())


def git_head(cwd):
    return _git(["rev-parse", "HEAD"], cwd) or None


def is_worktree(cwd) -> bool:
    common = _git(["rev-parse", "--git-common-dir"], cwd)
    gitdir = _git(["rev-parse", "--git-dir"], cwd)
    return bool(common and gitdir and common != gitdir)


def changed_files(cwd, baseline) -> list:
    files = []
    if baseline:
        out = _git(["diff", "--name-only", baseline + "..HEAD"], cwd)
        files.extend([l for l in out.splitlines() if l.strip()])
    out = _git(["status", "--porcelain"], cwd)
    for line in out.splitlines():
        if len(line) > 3:
            path = line[3:].strip().strip('"')
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip().strip('"')
            if path:
                files.append(path)
    seen = set()
    unique = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def sha_reachable(sha, cwd) -> bool:
    """True if sha is reachable in the repo (still present). Returncode-based:
    `git cat-file -e` prints nothing on success, so stdout cannot be used."""
    if not sha:
        return False
    try:
        r = subprocess.run(["git", "cat-file", "-e", sha + "^{commit}"],
                           capture_output=True, text=True, timeout=8, cwd=str(cwd))
        return r.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def run_verification(commands, cwd) -> list:
    results = []
    for cmd in commands:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300, cwd=str(cwd))
            tail = (r.stdout + r.stderr)[-800:]
            results.append({"command": cmd, "exit_code": r.returncode, "output_tail": tail})
        except (subprocess.SubprocessError, OSError) as exc:
            results.append({"command": cmd, "exit_code": -1, "output_tail": "<runner error: %s>" % exc})
    return results


def classify(verification: list, final_sha) -> str:
    if verification and any(v.get("exit_code") == 0 for v in verification):
        return "VERIFIED"
    if final_sha:
        return "REVIEW"
    return "NO_EVIDENCE"


def write_receipt(task_id, *, terminal_id="", session_id="", repo=None,
                  verify_commands=None, baseline=None, no_verify=False, final_sha=None) -> dict:
    repo_path = str(repo) if repo else os.getcwd()
    top = git_toplevel(repo_path)
    sha = final_sha or git_head(repo_path)
    base = baseline or ""
    changed = changed_files(repo_path, base or None)
    cmds = [] if no_verify else (verify_commands or [])
    verification = run_verification(cmds, repo_path) if cmds else []
    receipt = {
        "receipt_version": RECEIPT_VERSION,
        "task_id": str(task_id),
        "terminal_id": terminal_id,
        "session_id": session_id,
        "repo": top,
        "worktree": is_worktree(repo_path),
        "baseline_commit": base or None,
        "final_commit_sha": sha,
        "changed_files": changed,
        "verification": verification,
        "evidence_class": classify(verification, sha),
        "timestamp": datetime.now(UTC).isoformat(),
        "verifier": "task_receipt.py v%s" % RECEIPT_VERSION,
    }
    d = receipt_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = receipt_path(task_id)
    tmp = path.with_suffix(".%s.tmp" % os.getpid())
    tmp.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return receipt


def read_receipt(task_id):
    path = receipt_path(task_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def has_receipt(task_id) -> bool:
    try:
        return receipt_path(task_id).is_file()
    except OSError:
        return False


def list_receipts() -> dict:
    out = {}
    d = receipt_dir()
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(r, dict) and r.get("task_id"):
                out[str(r["task_id"])] = r
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return out


def _cmd_write(args):
    receipt = write_receipt(
        args.task_id, terminal_id=args.terminal_id, session_id=args.session_id,
        repo=args.repo, verify_commands=args.verify, baseline=args.baseline,
        no_verify=args.no_verify)
    print(json.dumps({"status": "written", "task_id": receipt["task_id"],
                      "evidence_class": receipt["evidence_class"],
                      "receipt_path": str(receipt_path(args.task_id)),
                      "changed_files": len(receipt["changed_files"])}, indent=2))
    return 0


def _cmd_read(args):
    r = read_receipt(args.task_id)
    if r is None:
        print("MISSING: no receipt for task %s" % args.task_id, file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2))
    return 0


def _cmd_has(args):
    return 0 if has_receipt(args.task_id) else 1


def _cmd_list(args):
    receipts = list_receipts()
    if not receipts:
        print("(no receipts)")
        return 0
    for tid in sorted(receipts, key=lambda t: str(t)):
        r = receipts[tid]
        print("#%s [%s] %s" % (tid, r.get("evidence_class", "?"), r.get("repo", "?")))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Durable completion-receipt store")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="capture evidence and write a receipt")
    w.add_argument("--task-id", required=True)
    w.add_argument("--repo", help="repo path (default cwd)")
    w.add_argument("--terminal-id", default=os.environ.get("CLAUDE_TERMINAL_ID", ""))
    w.add_argument("--session-id", default="")
    w.add_argument("--verify", action="append", default=[], help="verification command (repeatable)")
    w.add_argument("--baseline", help="baseline commit sha (if available)")
    w.add_argument("--no-verify", action="store_true")
    w.set_defaults(func=_cmd_write)
    r = sub.add_parser("read", help="print a receipt")
    r.add_argument("--task-id", required=True)
    r.set_defaults(func=_cmd_read)
    h = sub.add_parser("has", help="exit 0 if receipt exists, 1 otherwise")
    h.add_argument("--task-id", required=True)
    h.set_defaults(func=_cmd_has)
    l = sub.add_parser("list", help="list all receipts")
    l.set_defaults(func=_cmd_list)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
