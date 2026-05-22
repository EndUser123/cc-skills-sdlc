#!/usr/bin/env python3
"""Run verification commands from task contract and record results.

Structured output format: each command result includes [FACT]/[INFERENCE]/
[RECOMMENDATION] blocks for evidence-tier tracing — matching the
llm_behavior_contract format from the transcript analysis.
"""
import json, os, subprocess, pathlib, datetime, sys

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]


def _check_scope_drift(task: dict, state_dir: pathlib.Path, f) -> list[str]:
    """Check if actual file changes match scope_in expectations.

    Compares task.scope_in against git diff --name-only in the worktree.
    Flags files in scope_in that show no changes (possible spec drift).
    """
    findings = []
    scope_in = task.get("scope_in", [])
    if not scope_in:
        return findings

    worktree = os.environ.get("WORKTREE", "")
    if not worktree:
        return findings

    try:
        proc = subprocess.run(
            ["git", "-C", worktree, "diff", "--name-only", "HEAD~1", "HEAD"],
            shell=False, text=True, capture_output=True
        )
        if proc.returncode != 0:
            return findings

        changed = set(proc.stdout.strip().splitlines())
        for scoped in scope_in:
            matched = any(scoped in f or f.endswith(scoped) for f in changed)
            if not matched and changed:
                findings.append(
                    f"'{scoped}' listed in scope_in but no changes detected — possible spec drift"
                )
    except Exception:
        pass

    return findings


task_path = state_dir / f"active-task_{run_id}.json"
if not task_path.exists():
    print("ERROR: no active task", file=sys.stderr)
    sys.exit(1)

payload = json.loads(task_path.read_text(encoding="utf-8"))
task = payload.get("task", payload)
commands = task.get("verification_commands", [])

results_path = state_dir / f"verification-results_{run_id}.txt"
summary_path = state_dir / f"verification-summary_{run_id}.json"

if not commands:
    results_path.write_text("No verification commands supplied.\n", encoding="utf-8")
    summary = {
        "run_id": run_id, "verified": False,
        "reason": "missing_verification_commands", "commands": []
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    sys.exit(3)

all_ok = True
command_results = []

with results_path.open("w", encoding="utf-8") as f:
    for cmd in commands:
        f.write(f"$ {cmd}\n")
        f.write("=" * 80 + "\n")
        proc = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        # Write raw output
        f.write(stdout)
        if stderr:
            f.write("\n[stderr]\n")
            f.write(stderr)
        f.write(f"\n[exit_code] {proc.returncode}\n\n")

        passed = proc.returncode == 0
        if not passed:
            all_ok = False

        # Structured evidence blocks
        f.write("[FACT] ")
        if passed:
            f.write(f"Command succeeded: {cmd}\n")
            f.write(f"  exit_code={proc.returncode}\n")
        else:
            f.write(f"Command FAILED: {cmd}\n")
            f.write(f"  exit_code={proc.returncode}\n")
            if stderr:
                evidence = stderr[:200].replace("\n", " ")
                f.write(f"  stderr_evidence: {evidence}\n")

        if passed:
            f.write("[INFERENCE] Exit code 0 indicates the verification check passed.\n")
        else:
            f.write("[INFERENCE] Non-zero exit code indicates a verification failure. ")
            f.write("This may indicate a regression or an incomplete implementation.\n")

        f.write("\n")
        command_results.append({
            "command": cmd, "exit_code": proc.returncode,
            "passed": passed
        })

    # Gap discovery: check scope_in vs actual changed files
    gap_findings = _check_scope_drift(task, state_dir, f)
    if gap_findings:
        f.write("\n" + "=" * 80 + "\n")
        f.write("[FACT] Scope drift analysis run\n")
        for g in gap_findings:
            f.write(f"  gap: {g}\n")

# Write summary JSON
summary = {
    "run_id": run_id,
    "verified": all_ok,
    "verified_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "commands": command_results
}
summary_path.write_text(json.dumps(summary, indent=2) + "\n")
sys.exit(0 if all_ok else 4)
