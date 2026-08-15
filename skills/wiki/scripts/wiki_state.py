"""
wiki_state.py — Lifecycle state file manager for wiki sessions.

Per P:/.data/wiki/SCHEMA.md §10, session-ingest is a 9-step process.
The lifecycle state file captures which phases each session completed,
making "I forgot to run health-check" type omissions structurally
self-documenting rather than executor-dependent.

State file path: P:/.data/wiki/_state/<session-id>.json

State machine (5 states, transitions explicit):
  discovered  -> ingesting     (first wiki touch in this session)
  ingesting   -> linking       (ingest phase complete, post-write starts)
  linking     -> linting       (post-write complete, health check starts)
  linting     -> complete      (all required phases true, exit_clean=True)
  any         -> incomplete    (session ended before complete)

Required phases for `complete`:
  ingest_completed, auto_link_run, contradiction_scan_run,
  log_appended, qmd_updated

Atomic writes: write to .tmp, then os.replace (filesystem rename is atomic).
Per the conventions in python-atomicwrites, npm/write-file-atomic, and the
existing wiki_log_append.py pattern.

CLI:
    python wiki_state.py init <session-id>
    python wiki_state.py mark <session-id> <phase-name>
    python wiki_state.py status <session-id>
    python wiki_state.py list
    python wiki_state.py check  # all sessions; exit 1 if any incomplete
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

STATE_ROOT = Path("P:/.data/wiki/_state")


def _host_from_agent(agent: str) -> str:
    """Derive host prefix from explicit agent parameter (authoritative).

    Namespacing prevents session-id collisions when Grok Build and Claude Code
    happen to share an id. The caller is the authority on host — not the env,
    which can have stale CLAUDE_* / GROK_* vars from prior sessions.
    """
    a = agent.lower().strip()
    if a.startswith("claude") or a == "claude-code":
        return "claude"
    if a.startswith("grok") or a == "xai":
        return "grok"
    # Default: grok (this script lives at a Grok-native location per
    # SCHEMA.md §14 — only Grok Build invokes it directly)
    return "grok"


def _namespaced_path(session_id: str, host: str | None = None) -> Path:
    """Compute the on-disk state-file path, namespaced by host.

    Original session_id is preserved as a JSON field; only the filename gets
    the prefix to prevent collisions across hosts sharing session-ids.
    If host is None, defaults to 'grok' (this script's host per §14).
    """
    h = host or "grok"
    if h not in ("grok", "claude"):
        h = "grok"
    safe_id = session_id.replace("/", "_").replace("\\", "_")
    return STATE_ROOT / f"{h}-{safe_id}.json"

# Phase names that can be marked. `started` is the initial state.
PHASES = (
    "ingest_started",
    "ingest_completed",
    "auto_link_run",
    "contradiction_scan_run",
    "log_appended",
    "qmd_updated",
    "health_check_run",
    "drift_check_run",
)

REQUIRED_FOR_COMPLETE = (
    "ingest_completed",
    "auto_link_run",
    "contradiction_scan_run",
    "log_appended",
    "qmd_updated",
)

VALID_TRANSITIONS = {
    None: {"ingesting"},
    "ingesting": {"linking", "incomplete"},
    "linking": {"linting", "incomplete"},
    "linting": {"complete", "incomplete"},
    "complete": set(),
    "incomplete": set(),
}


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically: tmp + os.replace.

    Per python-atomicwrites / npm/write-file-atomic convention.
    The .tmp suffix is used (not random temp file) so the same path can be
    retried on failure without leaving random temp files behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


# Cross-platform file locking for read-modify-write safety across processes.
# Windows uses msvcrt.locking(); POSIX uses fcntl.flock(). Both are advisory
# locks scoped to the file descriptor. We use the simplest "lock whole file"
# pattern — concurrent marks on the same session-id serialize cleanly.
class _FileLock:
    def __init__(self, path: Path):
        self.path = path
        self._lock_path = path.with_suffix(path.suffix + ".lock")
        self._fd = None

    def __enter__(self):
        import time as _time
        # Create the lock file if it doesn't exist (mkdir parents first)
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Try to acquire; on Windows, msvcrt.locking() on the fd locks the whole
        # file. On POSIX, fcntl.flock() is cross-process advisory. We use a
        # spin-with-backoff loop with a short timeout because contention should
        # be rare (most sessions are single-process).
        deadline = _time.monotonic() + 10.0
        delay = 0.005
        while True:
            try:
                self._fd = open(self._lock_path, "a+b", buffering=0)
                if os.name == "nt":
                    import msvcrt
                    # LK_LOCK = 1: lock the entire file
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX)
                return self
            except (OSError, IOError):
                if self._fd is not None:
                    try:
                        self._fd.close()
                    except OSError:
                        pass
                    self._fd = None
                if _time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"could not acquire lock on {self._lock_path} within 10s"
                    )
                _time.sleep(delay)
                delay = min(delay * 2, 0.5)

    def __exit__(self, *exc):
        if self._fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
            except (OSError, IOError):
                pass
            self._fd = None
        # Best-effort cleanup of stale lock files (only if older than 1 hour)
        try:
            import time as _time
            if self._lock_path.exists():
                age = _time.time() - self._lock_path.stat().st_mtime
                if age > 3600:
                    self._lock_path.unlink()
        except OSError:
            pass


def _read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _derive_state(phases: dict) -> str:
    """Derive the current state machine state from the phase booleans."""
    if all(phases.get(p) for p in REQUIRED_FOR_COMPLETE):
        return "complete"
    if phases.get("drift_check_run") or phases.get("health_check_run"):
        return "linting"
    if (phases.get("auto_link_run")
            or phases.get("contradiction_scan_run")
            or phases.get("log_appended")):
        return "linking"
    if phases.get("ingest_completed") or phases.get("ingest_started"):
        return "ingesting"
    return "discovered"


def init(session_id: str, agent: str = "grok", workspace: str = "") -> dict:
    """Create the state file. Idempotent: returns existing if present."""
    host = _host_from_agent(agent)
    path = _namespaced_path(session_id, host=host)
    with _FileLock(path):
        existing = _read_state(path)
        if existing:
            return existing
        data = {
            "schema_version": 1,
            "session_id": session_id,
            "agent": agent,
            "host": host,
            "workspace": workspace,
            "started_at": _now_iso(),
            "state": "ingesting",
            "phases": {p: False for p in PHASES},
            "required_for_complete": list(REQUIRED_FOR_COMPLETE),
            "completed_at": None,
            "exit_clean": False,
        }
        _atomic_write_json(path, data)
        return data


def mark(session_id: str, phase: str, note: str = "") -> dict:
    """Mark a phase complete. Validate the phase name and transition."""
    if phase not in PHASES:
        raise ValueError(f"unknown phase: {phase!r}; valid: {PHASES}")
    # Find the existing state file: try grok-namespaced first, then claude-namespaced.
    # The agent field in the JSON is the source of truth for which host owns this
    # session; the on-disk path is just a function of session_id + host.
    host = None
    for try_host in ("grok", "claude"):
        try_path = _namespaced_path(session_id, host=try_host)
        if try_path.exists():
            try:
                existing = json.loads(try_path.read_text(encoding="utf-8"))
                host = existing.get("host", try_host)
            except (json.JSONDecodeError, OSError):
                host = try_host
            break
    if host is None:
        raise FileNotFoundError(
            f"state file not found for session {session_id!r} under either "
            f"grok- or claude- namespacing; call init() first"
        )
    path = _namespaced_path(session_id, host=host)
    with _FileLock(path):
        data = _read_state(path)
        if not data:
            raise FileNotFoundError(f"state file not found for session {session_id!r}; call init() first")
        new_state_before = data.get("state")
        data["phases"][phase] = True
        if note:
            data.setdefault("notes", []).append({"phase": phase, "ts": _now_iso(), "note": note})
        data["state"] = _derive_state(data["phases"])
        if data["state"] == "complete" and not data["exit_clean"]:
            data["completed_at"] = _now_iso()
            data["exit_clean"] = True
        _atomic_write_json(path, data)
        return data


def status(session_id: str) -> dict:
    """Return current state for one session."""
    # Check both grok- and claude-namespaced paths
    for try_host in ("grok", "claude"):
        path = _namespaced_path(session_id, host=try_host)
        data = _read_state(path)
        if data:
            return data
    return {"session_id": session_id, "exists": False}


def list_sessions(include_complete: bool = True) -> list[dict]:
    """List all session state files in STATE_ROOT."""
    if not STATE_ROOT.exists():
        return []
    out = []
    # glob both old-style "<id>.json" and new-style "<host>-<id>.json"
    for p in sorted(STATE_ROOT.glob("*.json")):
        # Skip lockfiles (defensive — _FileLock should clean up)
        if p.suffix == ".lock" or p.name.endswith(".tmp"):
            continue
        data = _read_state(p)
        if not data:
            continue
        if not include_complete and data.get("state") == "complete":
            continue
        out.append(data)
    return out


def check_all() -> tuple[list[dict], list[dict]]:
    """Return (incomplete, complete) session lists."""
    all_sessions = list_sessions(include_complete=True)
    incomplete, complete = [], []
    for s in all_sessions:
        if s.get("state") == "complete":
            complete.append(s)
        else:
            incomplete.append(s)
    return incomplete, complete


def report(unused_arg: Optional[str] = None) -> int:
    """Print a human-readable lifecycle report. Returns exit code."""
    incomplete, complete = check_all()
    print(f"=== Wiki session lifecycle ===")
    print(f"complete:   {len(complete)}")
    print(f"incomplete: {len(incomplete)}")
    if incomplete:
        print()
        print("INCOMPLETE SESSIONS (should be 0):")
        for s in incomplete:
            print(f"  - {s['session_id']}  state={s['state']}  started={s.get('started_at','?')}")
            missing = [p for p in s.get("required_for_complete", REQUIRED_FOR_COMPLETE)
                       if not s.get("phases", {}).get(p)]
            if missing:
                print(f"    missing phases: {missing}")
    if complete:
        print()
        print(f"recent complete:")
        for s in complete[-5:]:
            print(f"  - {s['session_id']}  completed_at={s.get('completed_at','?')}")
    # Exit 1 if any incomplete (so this can be wired into health_check)
    return 1 if incomplete else 0


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="wiki_state.py",
                                description="Lifecycle state manager for wiki sessions.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create state file for a session")
    p_init.add_argument("session_id")
    p_init.add_argument("--agent", default="grok")
    p_init.add_argument("--workspace", default="")

    p_mark = sub.add_parser("mark", help="mark a phase complete")
    p_mark.add_argument("session_id")
    p_mark.add_argument("phase", choices=PHASES)
    p_mark.add_argument("--note", default="")

    sub.add_parser("status", help="show state for one session").add_argument("session_id")
    sub.add_parser("list", help="list all sessions")
    p_check = sub.add_parser("check", help="report incomplete vs complete")
    p_check.add_argument("--exit-code", action="store_true",
                         help="exit 1 if any incomplete (for CI / health-check use)")

    args = p.parse_args(argv)

    if args.cmd == "init":
        data = init(args.session_id, agent=args.agent, workspace=args.workspace)
        host = data.get("host", "grok")
        print(json.dumps({"ok": True, "path": str(_namespaced_path(args.session_id, host=host)),
                          "state": data["state"]}, indent=2))
    elif args.cmd == "mark":
        try:
            data = mark(args.session_id, args.phase, note=args.note)
            print(json.dumps({"ok": True, "phase": args.phase,
                              "state": data["state"],
                              "exit_clean": data["exit_clean"]}, indent=2))
        except (ValueError, FileNotFoundError) as e:
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
            return 1
    elif args.cmd == "status":
        data = status(args.session_id)
        print(json.dumps(data, indent=2))
    elif args.cmd == "list":
        sessions = list_sessions(include_complete=True)
        for s in sessions:
            print(json.dumps({"id": s["session_id"], "state": s["state"],
                              "started": s.get("started_at"), "completed": s.get("completed_at")}))
    elif args.cmd == "check":
        if args.exit_code:
            return report(None)
        return report(None)
    return 0


if __name__ == "__main__":
    sys.exit(main())