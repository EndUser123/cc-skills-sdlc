#!/usr/bin/env python3
"""Select the first eligible task from the tasks file."""
import json, os, sys, datetime, pathlib

tasks_file = pathlib.Path(os.environ["GO_TASKS_FILE"])
state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]

if not tasks_file.exists():
    print(f"ERROR: tasks file not found at {tasks_file}", file=sys.stderr)
    sys.exit(1)

data = json.loads(tasks_file.read_text(encoding="utf-8"))
tasks = data.get("tasks", [])
allowed = {"ready", "queued", "approved"}

selected = None
for task in tasks:
    if task.get("status") in allowed:
        selected = task
        break

if not selected:
    print("ERROR: no actionable task found", file=sys.stderr)
    sys.exit(2)

payload = {
    "run_id": run_id,
    "terminal_id": terminal_id,
    "selected_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "task": selected,
}
out = state_dir / f"active-task_{run_id}.json"
tmp = out.with_suffix(".json.tmp")
tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp.replace(out)
print(f"Selected: {selected.get('id')} — {selected.get('title')}")
