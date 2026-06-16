"""
Wrapper for RED / GREEN / REFACTOR / MUTATION test execution.

All test execution MUST go through this script.

Phase semantics:
  red, green, refactor: drive the TDD lifecycle (init -> red -> green -> refactor -> validated).
  mutation:             runs alongside the lifecycle as a quality gate. It does NOT
                        advance session.phase. It writes a HMAC-signed MutationReceipt
                        that validate_tdd.py verifies like any other receipt.
"""

import sys
import os
import hashlib
import subprocess
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "__lib"))
from session_models import SessionState, PhaseReceipt, MutationReceipt  # type: ignore
from mutation_config import (  # type: ignore
    load_quality_gates,
    evaluate_mutation_run,
    QualityGatesError,
)
import sdlc_state

STATE_ROOT = sdlc_state.resolve_tdd_state_root()

# Allowed transitions:
#   init -> red
#   red  -> green
#   green -> refactor
# Mutation is a side-channel quality gate and is allowed from any state.
_LIFECYCLE_PHASES = ("red", "green", "refactor")
_ALLOWED_TRANSITIONS = {
    "red": ("init",),
    "green": ("red",),
    "refactor": ("green",),
}
# Phase after successful run (mutation does not advance the lifecycle)
_NEXT_PHASE = {
    "red": "green",
    "green": "refactor",
    "refactor": "refactor",
}

# Mutmut summary line: "N mutants: K killed, S survived, SK skipped, T timeout"
_MUTMUT_SUMMARY_RE = re.compile(
    r"(\d+)\s+mutants?:\s*(\d+)\s+killed,\s*(\d+)\s+survived,\s*"
    r"(\d+)\s+skipped,\s*(\d+)\s+timeout",
    re.IGNORECASE,
)


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


def _parse_mutmut_counts(output: str) -> dict:
    counts = {"killed": 0, "survived": 0, "skipped": 0, "timeout": 0, "no_tests": 0, "total": 0}
    m = _MUTMUT_SUMMARY_RE.search(output or "")
    if m:
        counts["total"] = int(m.group(1))
        counts["killed"] = int(m.group(2))
        counts["survived"] = int(m.group(3))
        counts["skipped"] = int(m.group(4))
        counts["timeout"] = int(m.group(5))
    return counts


def _run_mutation_phase(args, run_dir: Path, session: SessionState, current_cwd: Path) -> None:
    """Run mutmut, evaluate the gate, write a signed MutationReceipt.

    Does NOT advance session.phase. Exits with the gate's failure code if the
    module fails its target (when block_pr_on_failure is on).
    """
    if not args.module:
        print(
            "ERROR: --module <dotted.name> is required for --phase mutation.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        gates = load_quality_gates()
    except QualityGatesError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    runner = getattr(gates, "runner", "pytest -x --no-header -q")
    timeout_s = int(getattr(gates, "timeout_seconds", 600))

    cmd = [
        "mutmut", "run", "--use-coverage",
        "--runner", runner,
        "--target", args.module,
    ]
    started_at = _now_iso()
    print(f"[TDD] Running MUTATION phase… module='{args.module}' runner='{runner}'")

    proc = None
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False,
            cwd=str(current_cwd),
        )
        result_stdout = proc.stdout or ""
        result_stderr = proc.stderr or ""
    except FileNotFoundError:
        result_stdout = ""
        result_stderr = "mutmut not installed; run: pip install \"mutmut>=3.0,<4\""
    except subprocess.TimeoutExpired:
        result_stdout = ""
        result_stderr = f"mutmut timed out after {timeout_s}s"

    finished_at = _now_iso()

    stdout_log = run_dir / "mutation.stdout.log"
    stderr_log = run_dir / "mutation.stderr.log"
    stdout_log.write_text(result_stdout, encoding="utf-8")
    stderr_log.write_text(result_stderr, encoding="utf-8")

    stdout_hash = _sha256_file(stdout_log)
    stderr_hash = (
        _sha256_file(stderr_log) if stderr_log.stat().st_size > 0 else None
    )

    counts = _parse_mutmut_counts(result_stdout + "\n" + result_stderr)
    if proc is None and "mutmut not installed" in result_stderr:
        status = "blocked"
    elif proc is None and "timed out" in result_stderr:
        status = "timeout"
    else:
        verdict = evaluate_mutation_run(
            gates,
            args.module,
            killed=counts["killed"],
            survived=counts["survived"],
            skipped=counts["skipped"],
            timeout=counts["timeout"],
            no_tests=counts["no_tests"],
        )
        status = verdict["status"]

    target_score = gates.get_target(args.module)
    if counts["killed"] + counts["survived"] > 0:
        mutation_score = round(
            100.0 * counts["killed"] / (counts["killed"] + counts["survived"]), 2
        )
    else:
        mutation_score = None

    receipt = MutationReceipt(
        run_id=args.run_id,
        test_command=" ".join(cmd),
        cwd=str(current_cwd),
        exit_code=0 if proc is None else proc.returncode,
        started_at=started_at,
        finished_at=finished_at,
        stdout_path=stdout_log.name,
        stderr_path=stderr_log.name if stderr_hash else None,
        stdout_sha256=stdout_hash,
        stderr_sha256=stderr_hash,
        module=args.module,
        target_score=target_score,
        mutation_score=mutation_score,
        killed=counts["killed"],
        survived=counts["survived"],
        skipped=counts["skipped"],
        timeout=counts["timeout"],
        status=status,  # type: ignore[arg-type]
        signature="placeholder",
    )
    receipt.signature = receipt.compute_signature(session.hmac_secret)

    (run_dir / "mutation_receipt.json").write_text(
        receipt.model_dump_json(indent=2), encoding="utf-8"
    )

    # Lifecycle invariant: mutation MUST NOT advance session.phase.
    # We do not write back to session.json at all.

    print(
        f"[TDD] MUTATION complete. module='{args.module}' "
        f"killed={counts['killed']} survived={counts['survived']} "
        f"skipped={counts['skipped']} timeout={counts['timeout']} status={status}"
    )

    # Fail the process when the gate is configured to block the PR.
    block_on_failure = getattr(gates, "block_pr_on_failure", True)
    if status in {"failed", "timeout", "blocked"} and block_on_failure:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--phase",
        choices=["red", "green", "refactor", "mutation"],
        required=True,
    )
    parser.add_argument(
        "--module",
        type=str,
        help=(
            "Dotted module name (e.g. skill_guard.breadcrumb.inference). "
            "Required for --phase mutation; ignored otherwise."
        ),
    )
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

    # Mutation is a side-channel quality gate — run it on any session state and
    # do NOT advance session.phase.
    if args.phase == "mutation":
        _run_mutation_phase(args, run_dir, session, current_cwd)
        return

    if args.phase not in _LIFECYCLE_PHASES:
        print(f"ERROR: Unknown phase '{args.phase}'.", file=sys.stderr)
        sys.exit(2)

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

    # Advance phase monotonically (lifecycle phases only — mutation returns earlier).
    session.phase = _NEXT_PHASE[args.phase]  # type: ignore[assignment]
    session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    print(f"[TDD] {args.phase.upper()} complete. Exit code: {result.returncode}")


if __name__ == "__main__":
    main()