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


def _is_approval_gated(task):
    """A task that needs explicit director approval before /go will auto-select it.

    Reuses the existing ``approved`` status as the approval signal: a gated task
    (requires_approval: true) becomes selectable only once its status is flipped
    to ``approved``. This is the plan-level pause marker — /go runs to completion
    and pauses ONLY on these (plus BLOCKED / MAX_ATTEMPTS), never on an ad-hoc
    "should I continue?" judgment.
    """
    return bool(task.get("requires_approval")) and task.get("status") != "approved"


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
        if task.get("status") in allowed and not _is_approval_gated(task)
    ]
    if candidates:
        selected_index, source_task = sorted(candidates, key=lambda item: (_priority_value(item[1]), item[0]))[0]
        selected = dict(source_task)
        selected["status"] = "selected"
        selected["selected_by"] = run_id
        selected["selected_at"] = selected_at

    if not selected:
        gated = [
            {
                "id": task.get("id"),
                "title": task.get("title"),
                "priority": task.get("priority", "P999"),
                "reason": task.get("pause_reason", "requires director approval"),
            }
            for task in tasks
            if _is_approval_gated(task)
        ]
        if gated:
            paused_flag = state_dir / f".paused_{run_id}"
            try:
                paused_flag.write_text(
                    json.dumps(
                        {"run_id": run_id, "terminal_id": terminal_id, "gated": gated},
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                print(f"ERROR: failed to write pause flag: {exc}", file=sys.stderr)
                sys.exit(4)
            print("<promise>PAUSED_FOR_APPROVAL</promise>")
            print(
                f"PAUSED: {len(gated)} task(s) await director approval before /go will select them:"
            )
            for g in gated:
                print(f"  - {g['id']} ({g['priority']}): {g['title']} — {g['reason']}")
            print(
                'To resume: set each gated task\'s status to "approved" in the tasks file, '
                "then re-run /go."
            )
            sys.exit(2)
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
