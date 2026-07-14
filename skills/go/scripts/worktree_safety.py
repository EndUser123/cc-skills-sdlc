#!/usr/bin/env python3
"""Worktree Safety v1 — script-first task worktree lifecycle.

Provides task-scoped git worktree management with metadata, stale-base checks,
integration-sensitive file detection, and a dry-run cleanup helper.

Subcommands:
  start    — create a task branch + worktree + metadata
  status   — list active worktrees with git state
  precheck — assess merge readiness
  cleanup  — dry-run list (or --remove) stale worktrees

Exit codes: 0 = success, 1 = usage/refusal, 2 = gate-blocking (not used here).

Metadata lives at {state_dir}/worktree-tasks/{task_id}.json — outside tracked
source. No auto-merge, no auto-push, no auto-cleanup without --remove.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from run_context import go_worktree_creation_root, go_worktree_management_root

METADATA_SCHEMA = "worktree-task.v1"
METADATA_DIR_NAME = "worktree-tasks"

# Files whose modification in a shared tree risks clobbering concurrent work.
INTEGRATION_SENSITIVE = frozenset({
    "skills/go/scripts/orchestrate.py",
    "skills/go/SKILL.md",
    "skills/go/scripts/completion_evidence_review.py",
    "skills/go/scripts/omission_audit.py",
    "skills/go/scripts/preflight_propose.py",
    "skills/go/hooks/Stop_enforce_gate.py",
    "skills/go/tests/test_orchestrate_dispatch.py",
    ".claude-plugin/plugin.json",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git(repo: Path, *args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=timeout,
    )


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _metadata_dir(state_dir: Path) -> Path:
    return state_dir / METADATA_DIR_NAME


def _metadata_path(state_dir: Path, task_id: str) -> Path:
    return _metadata_dir(state_dir) / f"{task_id}.json"


def _list_metadata(state_dir: Path) -> list[dict]:
    d = _metadata_dir(state_dir)
    if not d.is_dir():
        return []
    results = []
    for f in sorted(d.glob("*.json")):
        if f.name.endswith(".precheck.json"):
            continue
        data = _read_json(f)
        if data:
            results.append(data)
    return results


def is_integration_sensitive(repo_relative_path: str) -> bool:
    """True if the path is an integration-sensitive file."""
    p = repo_relative_path.replace("\\", "/")
    return p in INTEGRATION_SENSITIVE


def _sensitive_touched(repo: Path, base: str) -> list[str]:
    """Return integration-sensitive files changed since base."""
    proc = _git(repo, "diff", "--name-only", base, "HEAD")
    if proc.returncode != 0:
        return []
    return [f.strip() for f in proc.stdout.splitlines()
            if f.strip() and is_integration_sensitive(f.strip())]


def _resolve_state_dir(cli_state_dir: str | None) -> Path:
    if cli_state_dir:
        return Path(cli_state_dir)
    env = os.environ.get("GO_STATE_DIR", "")
    if env:
        return Path(env)
    cwd = Path.cwd()
    terminal = os.environ.get("TERMINAL_ID", "default")
    return cwd / ".claude" / ".artifacts" / terminal / "go"


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> int:
    state_dir = _resolve_state_dir(args.state_dir)
    repo_root = Path(args.repo_root)
    task_id = args.task_id
    meta_path = _metadata_path(state_dir, task_id)

    # Duplicate check
    if meta_path.is_file():
        existing = _read_json(meta_path)
        if args.resume:
            if existing.get("status") != "active":
                print(f"ERROR: task {task_id} status is '{existing.get('status')}', not 'active'", file=sys.stderr)
                return 1
            print(f"resume: {existing['worktree_path']} (branch {existing['branch']})")
            return 0
        print(f"ERROR: task {task_id} already exists. Use --resume to re-enter.", file=sys.stderr)
        return 1

    canonical = args.canonical_branch
    branch = args.branch or f"wt/{task_id}"
    worktree_root = Path(args.worktree_root) if args.worktree_root else go_worktree_creation_root()
    worktree_path = worktree_root / task_id

    # Get base commit
    base_proc = _git(repo_root, "rev-parse", canonical)
    if base_proc.returncode != 0:
        print(f"ERROR: cannot resolve {canonical} in {repo_root}: {base_proc.stderr.strip()}", file=sys.stderr)
        return 1
    base_commit = base_proc.stdout.strip()

    intended = [f.strip() for f in args.intended_files.split(",")] if args.intended_files else []
    sensitive_intended = [f for f in intended if is_integration_sensitive(f)]

    if args.dry_run:
        print(f"[dry-run] git -C {repo_root} worktree add -b {branch} {worktree_path} {canonical}")
        print(f"[dry-run] metadata -> {meta_path}")
        print(f"[dry-run] base_commit={base_commit}")
        if sensitive_intended:
            print(f"WARNING: intended_files include integration-sensitive: {sensitive_intended}", file=sys.stderr)
        return 0

    # Real worktree creation
    proc = _git(repo_root, "worktree", "add", "-b", branch, str(worktree_path), canonical)
    if proc.returncode != 0:
        print(f"ERROR: git worktree add failed: {proc.stderr.strip()}", file=sys.stderr)
        return 1

    now = _now_iso()
    metadata = {
        "schema": METADATA_SCHEMA,
        "task_id": task_id,
        "title": args.title,
        "objective": args.objective or "",
        "branch": branch,
        "worktree_path": str(worktree_path),
        "base_commit": base_commit,
        "canonical_branch": canonical,
        "repo_root": str(repo_root),
        "owner_session": args.owner_session or "",
        "owner_run_id": "",
        "intended_files": intended,
        "integration_sensitive_files_touched": sensitive_intended,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "tests_run": None,
        "cache_version_decision": None,
        "cleanup_state": "none",
    }
    _write_json(meta_path, metadata)

    print(f"started: {task_id}")
    print(f"  worktree: {worktree_path}")
    print(f"  branch:   {branch}")
    print(f"  base:     {base_commit[:12]}")
    if sensitive_intended:
        print(f"WARNING: intended_files include integration-sensitive: {sensitive_intended}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    state_dir = _resolve_state_dir(args.state_dir)
    tasks = _list_metadata(state_dir)
    if args.task_id:
        tasks = [t for t in tasks if t.get("task_id") == args.task_id]

    results = []
    for t in tasks:
        wt = Path(t.get("worktree_path", ""))
        repo = Path(t.get("repo_root", "."))
        base = t.get("base_commit", "")
        canonical = t.get("canonical_branch", "main")

        dirty = False
        stale_base = False
        sensitive = []
        git_status = ""
        diff_stat = ""

        if wt.is_dir():
            sp = _git(wt, "status", "--short")
            git_status = sp.stdout.strip()
            dirty = bool(git_status)
            sensitive = _sensitive_touched(wt, base) if base else []
            dp = _git(wt, "diff", "--stat")
            diff_stat = dp.stdout.strip() if dp.returncode == 0 else ""

        if base and canonical:
            # Stale = canonical branch HEAD differs from base_commit (moved).
            cp = _git(repo, "rev-parse", canonical)
            if cp.returncode == 0 and cp.stdout.strip() != base:
                stale_base = True

        results.append({
            "task_id": t.get("task_id", ""),
            "status": t.get("status", ""),
            "branch": t.get("branch", ""),
            "worktree_path": str(wt),
            "dirty": dirty,
            "stale_base": stale_base,
            "sensitive_touched": sensitive,
            "git_status": git_status[:500],
            "diff_stat": diff_stat[:500],
        })

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No active task worktrees.")
        for r in results:
            flags = []
            if r["dirty"]: flags.append("DIRTY")
            if r["stale_base"]: flags.append("STALE-BASE")
            if r["sensitive_touched"]: flags.append("SENSITIVE")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  {r['task_id']} ({r['status']}){flag_str}")
            print(f"    branch: {r['branch']}")
            print(f"    worktree: {r['worktree_path']}")
            if r["sensitive_touched"]:
                print(f"    sensitive files: {r['sensitive_touched']}")
    return 0


# ---------------------------------------------------------------------------
# precheck
# ---------------------------------------------------------------------------

def cmd_precheck(args: argparse.Namespace) -> int:
    state_dir = _resolve_state_dir(args.state_dir)
    meta = _read_json(_metadata_path(state_dir, args.task_id))
    if not meta:
        print(f"ERROR: no metadata for task {args.task_id}", file=sys.stderr)
        return 1

    wt = Path(meta.get("worktree_path", ""))
    repo = Path(meta.get("repo_root", "."))
    base = meta.get("base_commit", "")
    canonical = meta.get("canonical_branch", "main")
    intended = meta.get("intended_files", [])

    if not wt.is_dir():
        print(f"ERROR: worktree path does not exist: {wt}", file=sys.stderr)
        return 1

    # Changed files since base
    changed_proc = _git(wt, "diff", "--name-only", base, "HEAD")
    changed = [f.strip() for f in changed_proc.stdout.splitlines() if f.strip()] if changed_proc.returncode == 0 else []

    diff_stat_proc = _git(wt, "diff", "--stat", base, "HEAD")
    diff_stat = diff_stat_proc.stdout.strip() if diff_stat_proc.returncode == 0 else ""

    sensitive = [f for f in changed if is_integration_sensitive(f)]

    # Upstream changes to intended files
    upstream_changed = []
    if intended and base:
        for f in intended:
            log_proc = _git(repo, "log", "--oneline", f"{base}..{canonical}", "--", f)
            if log_proc.returncode == 0 and log_proc.stdout.strip():
                upstream_changed.append(f)

    # Merge risk
    risk = "low"
    if sensitive or upstream_changed:
        risk = "high" if (sensitive and upstream_changed) else "medium"

    result = {
        "schema": "worktree-precheck.v1",
        "task_id": args.task_id,
        "changed_files": changed,
        "diff_stat": diff_stat[:1000],
        "sensitive_touched": sensitive,
        "upstream_changed_intended": upstream_changed,
        "merge_risk": risk,
        "ready_for_integration": risk == "low" or (risk == "medium" and not sensitive),
    }

    # Write precheck artifact
    precheck_path = _metadata_dir(state_dir) / f"{args.task_id}.precheck.json"
    _write_json(precheck_path, result)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"precheck: {args.task_id}")
        print(f"  changed files: {len(changed)}")
        print(f"  sensitive: {sensitive or 'none'}")
        print(f"  upstream conflicts: {upstream_changed or 'none'}")
        print(f"  merge risk: {risk}")
        print(f"  ready: {result['ready_for_integration']}")
    return 0


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------

def cmd_cleanup(args: argparse.Namespace) -> int:
    state_dir = _resolve_state_dir(args.state_dir)
    tasks = _list_metadata(state_dir)

    entries = []
    for t in tasks:
        wt = Path(t.get("worktree_path", ""))
        status = t.get("status", "unknown")
        dirty = False
        if wt.is_dir():
            sp = _git(wt, "status", "--short")
            dirty = bool(sp.stdout.strip())
        classification = "active" if status == "active" else ("dirty" if dirty else status)
        if dirty and status == "active":
            classification = "dirty-active"
        entries.append({
            "task_id": t.get("task_id", ""),
            "worktree_path": str(wt),
            "status": status,
            "dirty": dirty,
            "classification": classification,
        })

    # Check for unknown worktrees in git worktree list
    repo = Path(tasks[0].get("repo_root", ".")) if tasks else Path.cwd()
    wt_list_proc = _git(repo, "worktree", "list", "--porcelain")
    known_paths = {e["worktree_path"] for e in entries}
    if wt_list_proc.returncode == 0:
        for line in wt_list_proc.stdout.splitlines():
            if line.startswith("worktree "):
                p = line[len("worktree "):].strip()
                if p and p not in known_paths:
                    entries.append({
                        "task_id": "(unknown)",
                        "worktree_path": p,
                        "status": "unknown",
                        "dirty": False,
                        "classification": "unknown",
                    })

    if args.json:
        print(json.dumps(entries, indent=2))
    else:
        print(f"cleanup dry-run ({'--remove' if args.remove else 'list-only'}):")
        for e in entries:
            print(f"  [{e['classification']}] {e['task_id']}: {e['worktree_path']}")

    # Check for dirty-active before removing
    dirty_active = [e for e in entries if e["classification"] == "dirty-active"]
    if args.remove and dirty_active:
        print(f"ERROR: refusing to remove {len(dirty_active)} dirty-active worktree(s)", file=sys.stderr)
        for e in dirty_active:
            print(f"  {e['worktree_path']}", file=sys.stderr)
        return 1

    if args.remove:
        for e in entries:
            if e["classification"] in ("merged", "abandoned", "integrated"):
                wt = Path(e["worktree_path"])
                print(f"removing: {wt}")
                rp = _git(Path("."), "worktree", "remove", str(wt))
                if rp.returncode != 0:
                    print(f"  WARNING: {rp.stderr.strip()}", file=sys.stderr)

    print("Tip: run 'git worktree prune' separately to clean stale refs.")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worktree Safety v1")
    parser.add_argument("--state-dir", default=None, help="Override state directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Create a task worktree + metadata")
    p_start.add_argument("--task-id", required=True)
    p_start.add_argument("--title", required=True)
    p_start.add_argument("--objective", default="")
    p_start.add_argument("--repo-root", required=True)
    p_start.add_argument("--branch", default="")
    p_start.add_argument("--canonical-branch", default="main")
    p_start.add_argument("--intended-files", default="")
    p_start.add_argument("--worktree-root", default="")
    p_start.add_argument("--owner-session", default="")
    p_start.add_argument("--resume", action="store_true")
    p_start.add_argument("--dry-run", action="store_true")
    p_start.set_defaults(func=cmd_start)

    p_status = sub.add_parser("status", help="List active task worktrees")
    p_status.add_argument("--task-id", default="")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_precheck = sub.add_parser("precheck", help="Assess merge readiness")
    p_precheck.add_argument("--task-id", required=True)
    p_precheck.add_argument("--json", action="store_true")
    p_precheck.set_defaults(func=cmd_precheck)

    p_cleanup = sub.add_parser("cleanup", help="Dry-run worktree cleanup")
    p_cleanup.add_argument("--remove", action="store_true")
    p_cleanup.add_argument("--json", action="store_true")
    p_cleanup.set_defaults(func=cmd_cleanup)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Lifecycle primitive v1 -- shared idempotent worktree lifecycle contract
# ---------------------------------------------------------------------------
# Consolidates allocation, registration, inspection, terminal-marking, cleanup,
# quarantine, and reconciliation logic that was duplicated across
# orchestrate.py (pi-task worktrees), falsification_gate.py (attack worktrees),
# and worktree_safety.py (task worktrees).
#
# Every worktree-producing mechanism should use these same primitives.

LIFECYCLE_MANAGED_WORKTREE_ROOT = go_worktree_management_root()

LIFECYCLE_REGISTRY_DIR = "worktree-lifecycle"


def _lifecycle_registry(state_dir: Path | None = None) -> Path:
    base = state_dir if state_dir else _resolve_state_dir(None)
    return base / LIFECYCLE_REGISTRY_DIR


def _normalize_path(p: Path) -> str:
    return str(p.resolve())


def lifecycle_register(
    worktree_path: Path,
    branch: str,
    run_id: str,
    repo_root: Path,
    worktree_type: str,
    owner_session: str = "",
    owner_task: str = "",
    state_dir: Path | None = None,
) -> dict:
    reg = _lifecycle_registry(state_dir)
    reg.mkdir(parents=True, exist_ok=True)
    entry_id = run_id or branch.replace("/", "_")
    entry = {
        "schema": "worktree-lifecycle.v1",
        "entry_id": entry_id,
        "worktree_path": _normalize_path(worktree_path),
        "branch": branch,
        "run_id": run_id,
        "repo_root": _normalize_path(repo_root),
        "worktree_type": worktree_type,
        "owner_session": owner_session,
        "owner_task": owner_task,
        "status": "active",
        "cleanup_state": "none",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "quarantine_reason": "",
        "quarantine_expires_at": "",
    }
    _write_json(reg / f"{entry_id}.json", entry)
    return entry


def lifecycle_get_registration(run_id: str, state_dir: Path | None = None) -> dict:
    reg = _lifecycle_registry(state_dir)
    if not reg.is_dir():
        return {}
    for f in sorted(reg.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("run_id") == run_id or d.get("entry_id") == run_id:
                return d
        except (OSError, ValueError):
            continue
    return {}


def lifecycle_mark_terminal(
    run_id: str, cleanup_state: str, state_dir: Path | None = None
) -> dict:
    entry = lifecycle_get_registration(run_id, state_dir)
    if not entry:
        return {}
    entry["status"] = "terminal"
    entry["cleanup_state"] = cleanup_state
    entry["updated_at"] = _now_iso()
    reg = _lifecycle_registry(state_dir)
    _write_json(reg / f"{entry.get('entry_id', run_id)}.json", entry)
    return entry


def _get_active_worktree_git_metadata() -> dict:
    result = {}
    for repo_hint in ["P:", "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc"]:
        try:
            proc = subprocess.run(
                ["git", "-C", repo_hint, "worktree", "list", "--porcelain"],
                capture_output=True, text=True, timeout=15)
            if proc.returncode != 0:
                continue
        except (OSError, subprocess.SubprocessError):
            continue
        current_path = None
        for line in proc.stdout.splitlines():
            if line.startswith("worktree "):
                current_path = line[9:].strip()
            elif line.startswith("branch ") and current_path:
                result[current_path] = {"branch": line[7:].strip(), "head": "", "parent_repo": repo_hint}
            elif line.startswith("HEAD ") and current_path:
                if current_path in result:
                    result[current_path]["head"] = line[5:].strip()
    return result


def lifecycle_inspect_worktree(worktree_path: Path, repo_root: Path | None = None) -> dict:
    report = {"path": str(worktree_path), "exists_on_disk": False,
              "git_metadata_ok": False, "branch_registered": False,
              "branch_ref_exists": False, "dirty": False, "has_git_dir": False,
              "modified_paths": []}
    if worktree_path.is_dir():
        report["exists_on_disk"] = True
        dot_git = worktree_path / ".git"
        report["has_git_dir"] = dot_git.exists()
        p = _git(worktree_path, "status", "--porcelain")
        if p.returncode == 0:
            report["dirty"] = bool(p.stdout.strip())
            report["modified_paths"] = [l.strip() for l in p.stdout.splitlines() if l.strip()]
        if repo_root:
            p2 = _git(repo_root, "worktree", "list", "--porcelain")
            if p2.returncode == 0:
                report["git_metadata_ok"] = str(worktree_path) in p2.stdout
    return report


def lifecycle_clean_worktree(
    worktree_path: Path, repo_root: Path, run_id: str = "",
    state_dir: Path | None = None, *, branch_name: str = "",
) -> dict:
    report = {"worktree_path": str(worktree_path), "git_remove_ok": False,
              "branch_deleted": False, "git_pruned": False,
              "directory_removed": False, "lifecycle_registry_updated": False,
              "errors": []}
    wt = Path(worktree_path)
    rr = Path(repo_root)
    p = _git(rr, "worktree", "remove", "--force", str(wt))
    if p.returncode == 0:
        report["git_remove_ok"] = True
    else:
        report["errors"].append(f"git worktree remove: {p.stderr.strip()}")
    if wt.exists():
        try:
            shutil.rmtree(wt, ignore_errors=True)
            report["directory_removed"] = not wt.exists()
        except Exception as e:
            report["errors"].append(f"rmtree: {e}")
    if branch_name:
        bp = _git(rr, "branch", "-D", branch_name)
        if bp.returncode == 0:
            report["branch_deleted"] = True
    _git(rr, "worktree", "prune")
    report["git_pruned"] = True
    if run_id and state_dir:
        reg_entry = lifecycle_mark_terminal(run_id, "cleaned", state_dir)
        report["lifecycle_registry_updated"] = bool(reg_entry)
    return report


def lifecycle_quarantine(
    worktree_path: Path, run_id: str, reason: str, repo_root: Path,
    branch_name: str = "", state_dir: Path | None = None,
    *, expire_hours: int = 168,
) -> dict:
    reg = _lifecycle_registry(state_dir)
    if not reg.is_dir():
        reg.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    expiry = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=expire_hours)
              if expire_hours > 0 else "")
    entry = lifecycle_get_registration(run_id, state_dir) or {
        "schema": "worktree-lifecycle.v1",
        "entry_id": run_id or branch_name.replace("/", "_"),
        "worktree_path": _normalize_path(worktree_path),
        "branch": branch_name, "run_id": run_id,
        "repo_root": _normalize_path(repo_root),
        "worktree_type": "quarantined",
        "owner_session": "", "owner_task": "",
        "created_at": _now_iso(),
    }
    entry["status"] = "terminal"
    entry["cleanup_state"] = "preserved"
    entry["quarantine_reason"] = reason
    entry["quarantine_expires_at"] = expiry if isinstance(expiry, str) else expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
    entry["updated_at"] = _now_iso()
    _write_json(reg / f"{entry.get('entry_id', run_id)}.json", entry)
    return entry


MANAGED_WORKTREE_PREFIXES = frozenset({"falsify-", "pi-task-", "wt-"})


def _is_managed_worktree_dir(name: str) -> bool:
    return any(name.startswith(p) for p in MANAGED_WORKTREE_PREFIXES)


def lifecycle_reconcile(state_dir: Path | None = None, *, dry_run: bool = True) -> dict:
    reg_dir = _lifecycle_registry(state_dir)
    reg_entries = {}
    if reg_dir.is_dir():
        for f in reg_dir.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                wp = d.get("worktree_path", "")
                if wp:
                    reg_entries[wp] = d
            except (OSError, ValueError):
                pass
    managed_root = LIFECYCLE_MANAGED_WORKTREE_ROOT
    git_wt = _get_active_worktree_git_metadata()
    all_paths = set()
    if managed_root.is_dir():
        for d in managed_root.iterdir():
            if d.is_dir() and _is_managed_worktree_dir(d.name):
                all_paths.add(str(d.resolve()))
    for gp in git_wt:
        if any(Path(gp).name.startswith(p) for p in MANAGED_WORKTREE_PREFIXES):
            all_paths.add(str(Path(gp).resolve()))
    for rp in reg_entries:
        all_paths.add(str(Path(rp).resolve()))

    counts = {}
    entries = []
    for rp in sorted(all_paths):
        wp = Path(rp)
        on_disk = wp.is_dir()
        reg = reg_entries.get(rp, {})
        in_git = rp in git_wt
        wt_name = wp.name

        if not on_disk and in_git:
            cls = "ORPHAN_GIT_METADATA"
            reason = f"directory gone but {git_wt.get(rp,{}).get('parent_repo','?')} still registered"
        elif on_disk and not in_git and not reg:
            cls = "ORPHAN_DIRECTORY"
            reason = "unowned disk directory"
        elif on_disk and reg.get("cleanup_state") == "preserved" and reg.get("status") == "terminal":
            cls = "PRESERVED_FOR_REVIEW"
            reason = reg.get("quarantine_reason", "preserved")
        elif on_disk and reg.get("status") == "active":
            cls = "ACTIVE"
            reason = "registered active"
        elif on_disk and in_git and not reg:
            cls = "RECLAIMABLE"
            reason = "git-registered but unowned"
        elif on_disk and reg.get("cleanup_state") == "cleaned":
            cls = "CLEANUP_FAILED"
            reason = "registry says cleaned but directory present"
        elif on_disk and not in_git:
            cls = "ORPHAN_DIRECTORY"
            reason = "orphan"
        else:
            cls = "FOREIGN_OR_UNKNOWN"
            reason = ""

        counts[cls] = counts.get(cls, 0) + 1
        entries.append({
            "path": rp, "on_disk": on_disk, "git_registered": in_git,
            "lifecycle_registered": bool(reg), "classification": cls,
            "reason": reason, "branch": git_wt.get(rp, {}).get("branch", ""),
            "lifecycle_state": reg.get("cleanup_state", ""),
        })

    return {"entries": entries, "counts": counts}
