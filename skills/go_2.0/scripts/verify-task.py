#!/usr/bin/env python3
"""Run verification commands from task contract and record results."""
import json, os, subprocess, pathlib, datetime, sys

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

task_path = state_dir / f"active-task_{run_id}.json"
if not task_path.exists():
    print("ERROR: no active task", file=sys.stderr)
    sys.exit(1)

payload = json.loads(task_path.read_text(encoding="utf-8"))
commands = payload["task"].get("verification_commands", [])

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
        f.write(proc.stdout or "")
        if proc.stderr:
            f.write("\n[stderr]\n")
            f.write(proc.stderr)
        f.write(f"\n[exit_code] {proc.returncode}\n\n")
        if proc.returncode != 0:
            all_ok = False
        command_results.append({
            "command": cmd, "exit_code": proc.returncode,
            "passed": proc.returncode == 0
        })

summary = {
    "run_id": run_id,
    "verified": all_ok,
    "verified_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "commands": command_results
}
summary_path.write_text(json.dumps(summary, indent=2) + "\n")
sys.exit(0 if all_ok else 4)
