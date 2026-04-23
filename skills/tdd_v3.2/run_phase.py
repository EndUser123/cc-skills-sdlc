"""
Wrapper for RED / GREEN / REFACTOR test execution.

All test execution MUST go through this script.
"""

import sys
import os
import hashlib
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_models import SessionState, PhaseReceipt  # type: ignore


def _resolve_state_root() -> Path:
    """Resolve STATE_ROOT, routing workspace root to .claude/.claude-state/tdd/.

    When cwd is the workspace root (P:\\), .claude/ exists and is the canonical
    home for Claude Code state. This prevents dot-directories at workspace root.
    """
    cwd = Path(os.getcwd()).resolve()
    # Workspace root detection: cwd.name == '' means we're at a drive root
    # and .claude existence confirms it's the Claude Code workspace root
    if cwd.name == "" and (cwd / ".claude").exists():
        return cwd / ".claude" / ".claude-state" / "tdd"
    return cwd / ".claude-state" / "tdd"


STATE_ROOT = _resolve_state_root()

# Allowed transitions:
#   init -> red
#   red  -> green
#   green -> refactor
_ALLOWED_TRANSITIONS = {
    "red": ("init",),
    "green": ("red",),
    "refactor": ("green",),
}
# Phase after successful run
_NEXT_PHASE = {
    "red": "green",
    "green": "refactor",
    "refactor": "refactor",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=["red", "green", "refactor"], required=True)
    parser.add_argument(
        "--override-cmd",
        type=str,
        help="Override default test command (e.g. 'pytest tests/foo.py')",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Test timeout in seconds (default: 120)",
    )
    args = parser.parse_args()

    run_dir = STATE_ROOT / args.run_id
    session_path = run_dir / "session.json"

    if not session_path.exists():
        print(
            "ERROR: session.json not found. Run generate_context.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    session = SessionState.model_validate_json(
        session_path.read_text(encoding="utf-8")
    )

    # Relaxed CWD constraint for Monorepo support (must be sub-path of session cwd)
    current_cwd = Path(os.getcwd()).resolve()
    session_cwd = Path(session.cwd).resolve()
    try:
        # Python 3.9+ has is_relative_to
        if not current_cwd.is_relative_to(session_cwd):
            raise ValueError
    except AttributeError:
        # Fallback manual check if needed
        if session_cwd not in current_cwd.parents and current_cwd != session_cwd:
            print(
                f"ERROR: Execution CWD ({current_cwd}) must remain within session "
                f"tree ({session_cwd}).",
                file=sys.stderr,
            )
            sys.exit(1)
    except ValueError:
        print(
            f"ERROR: Execution CWD ({current_cwd}) must remain within session "
            f"tree ({session_cwd}).",
            file=sys.stderr,
        )
        sys.exit(1)

    if session.phase not in _ALLOWED_TRANSITIONS[args.phase]:
        print(
            f"ERROR: Cannot run {args.phase.upper()} when session is in phase "
            f"'{session.phase}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    actual_command = args.override_cmd if args.override_cmd else session.test_command
    started_at = _now_iso()
    print(f"[TDD] Running {args.phase.upper()} phase… with '{actual_command}'")

    try:
        result = subprocess.run(
            actual_command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(current_cwd),
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: Test command timed out after {args.timeout} seconds.",
            file=sys.stderr,
        )
        sys.exit(1)

    finished_at = _now_iso()

    stdout_log = run_dir / f"{args.phase}.stdout.log"
    stderr_log = run_dir / f"{args.phase}.stderr.log"
    stdout_log.write_text(result.stdout, encoding="utf-8")
    stderr_log.write_text(result.stderr, encoding="utf-8")

    stdout_hash = _sha256_file(stdout_log)
    stderr_hash = _sha256_file(stderr_log) if stderr_log.stat().st_size > 0 else None

    receipt = PhaseReceipt(
        phase=args.phase,  # type: ignore[arg-type]
        run_id=args.run_id,
        test_command=actual_command,
        cwd=str(current_cwd),
        exit_code=result.returncode,
        started_at=started_at,
        finished_at=finished_at,
        stdout_path=stdout_log.name,
        stderr_path=stderr_log.name if stderr_hash else None,
        stdout_sha256=stdout_hash,
        stderr_sha256=stderr_hash,
        signature="placeholder",
    )
    # Sign after building content
    receipt.signature = receipt.compute_signature(session.hmac_secret)

    (run_dir / f"{args.phase}_receipt.json").write_text(
        receipt.model_dump_json(indent=2), encoding="utf-8"
    )

    # Advance phase monotonically
    session.phase = _NEXT_PHASE[args.phase]  # type: ignore[assignment]
    session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    print(f"[TDD] {args.phase.upper()} complete. Exit code: {result.returncode}")


if __name__ == "__main__":
    main()