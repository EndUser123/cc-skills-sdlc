#!/usr/bin/env python3
"""Check if more eligible tasks remain after the selected one."""
import json, os, pathlib

tasks_file = pathlib.Path(os.environ["GO_TASKS_FILE"])
state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

selected = json.loads((state_dir / f"active-task_{run_id}.json").read_text(encoding="utf-8"))["task"]
selected_id = selected.get("id")
data = json.loads(tasks_file.read_text(encoding="utf-8"))
tasks = data.get("tasks", [])
allowed = {"ready", "queued", "approved"}

seen_selected = False
remaining = False
for task in tasks:
    if task.get("id") == selected_id:
        seen_selected = True
        continue
    if seen_selected and task.get("status") in allowed:
        remaining = True
        break

print("<promise>MORE_TASKS_IN_PLAN</promise>" if remaining else "<promise>ALL_TASKS_COMPLETE</promise>")
