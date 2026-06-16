#!/usr/bin/env python3
"""Select and claim the highest-priority eligible task from the tasks file."""
import json, os, sys, datetime, pathlib, time

tasks_file = pathlib.Path(os.environ.get("GO_TASKS_FILE", ".claude/tasks/tasks.json")).resolve()
state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ["TERMINAL_ID"]
lock_file = tasks_file.with_suffix(tasks_file.suffix + ".lock")

if not tasks_file.exists():
    print(f"ERROR: tasks file not found at {tasks_file}", file=sys.stderr)
    sys.exit(1)

def _priority_value(task):
    raw = str(task.get("priority", "P999")).strip().upper()
    if raw.startswith("P") and raw[1:].isdigit():
        return int(raw[1:])
    return 999


def _acquire_lock():
    try:
        return os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        ttl = int(os.environ.get("GO_TASK_LOCK_TTL_SECONDS", "3600"))
        try:
            age = time.time() - lock_file.stat().st_mtime
        except OSError:
            age = 0
        if age > ttl:
            try:
                lock_file.unlink()
                return os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                pass
        print(f"ERROR: tasks file is locked at {lock_file}", file=sys.stderr)
        sys.exit(3)


fd = _acquire_lock()

try:
    with os.fdopen(fd, "w", encoding="utf-8") as lock:
        lock.write(f"{run_id}\n")

    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    allowed = {"ready", "queued", "approved"}

    selected_index = None
    selected = None
    selected_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    candidates = [
        (index, task)
        for index, task in enumerate(tasks)
        if task.get("status") in allowed
    ]
    if candidates:
        selected_index, source_task = sorted(candidates, key=lambda item: (_priority_value(item[1]), item[0]))[0]
        selected = dict(source_task)
        selected["status"] = "selected"
        selected["selected_by"] = run_id
        selected["selected_at"] = selected_at

    if not selected:
        print("ERROR: no actionable task found", file=sys.stderr)
        sys.exit(2)

    payload = {
        "run_id": run_id,
        "terminal_id": terminal_id,
        "selected_at": selected_at,
        "source": "tasks-file",
        "source_ref": str(tasks_file),
        "task": selected,
    }
    out = state_dir / f"active-task_{run_id}.json"
    tmp = out.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(out)
    except OSError as exc:
        print(f"ERROR: failed to write active task artifact: {exc}", file=sys.stderr)
        sys.exit(4)

    tasks[selected_index] = selected
    tasks_tmp = tasks_file.with_suffix(tasks_file.suffix + ".tmp")
    try:
        tasks_tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tasks_tmp.replace(tasks_file)
    except OSError as exc:
        try:
            out.unlink()
        except FileNotFoundError:
            pass
        print(f"ERROR: failed to claim task in queue: {exc}", file=sys.stderr)
        sys.exit(4)
    print(f"Selected: {selected.get('id')} - {selected.get('title')}")
finally:
    try:
        lock_file.unlink()
    except FileNotFoundError:
        pass
