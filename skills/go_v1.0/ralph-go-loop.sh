#!/usr/bin/env bash
set -euo pipefail

MAX_CYCLES="${1:-10}"

export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')}"
export RUN_ID="${RUN_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export GO_TASKS_FILE="${GO_TASKS_FILE:-.claude/tasks/tasks.json}"
export GO_RALPH_MODE="${GO_RALPH_MODE:-true}"
export GO_STATE_DIR=".claude/.artifacts/${TERMINAL_ID}/go"

mkdir -p "$GO_STATE_DIR"

log() {
  printf '[go-loop] %s\n' "$*"
}

require_file() {
  local path="$1"
  if [ ! -f "$path" ]; then
    log "ERROR: required file missing: $path"
    exit 1
  fi
}

has_flag() {
  local name="$1"
  [ -f "$GO_STATE_DIR/$name" ]
}

emit_status_summary() {
  log "terminal_id=$TERMINAL_ID"
  log "run_id=$RUN_ID"
  log "state_dir=$GO_STATE_DIR"
}

check_task_source() {
  if [ ! -f "$GO_TASKS_FILE" ]; then
    log "ERROR: tasks file not found at $GO_TASKS_FILE"
    exit 1
  fi
}

invoke_go() {
  if command -v /go >/dev/null 2>&1; then
    /go 2>&1 | tee "$GO_STATE_DIR/go-output_$RUN_ID.log"
    return "${PIPESTATUS[0]}"
  fi

  if command -v go >/dev/null 2>&1; then
    go 2>&1 | tee "$GO_STATE_DIR/go-output_$RUN_ID.log"
    return "${PIPESTATUS[0]}"
  fi

  log "ERROR: neither /go nor go command is available"
  exit 1
}

count_attempts() {
  find "$GO_STATE_DIR" -maxdepth 1 -type f -name ".attempt_*_${RUN_ID}" | wc -l | tr -d ' '
}

task_outcome() {
  # Artifact flags are authoritative; check them first
  if has_flag ".pr-ready_$RUN_ID"; then
    echo "PR_READY"
    return 0
  fi

  if has_flag ".blocked_$RUN_ID"; then
    echo "BLOCKED"
    return 0
  fi

  if [ "$(count_attempts)" -ge "$MAX_ATTEMPTS" ]; then
    echo "BLOCKED"
    return 0
  fi

  # Fallback: parse log only if no authoritative flag exists
  if [ -f "$GO_STATE_DIR/go-output_$RUN_ID.log" ]; then
    if grep -q '<promise>PR_READY</promise>' "$GO_STATE_DIR/go-output_$RUN_ID.log"; then
      echo "PR_READY"
      return 0
    fi
    if grep -q '<promise>BLOCKED</promise>' "$GO_STATE_DIR/go-output_$RUN_ID.log"; then
      echo "BLOCKED"
      return 0
    fi
  fi

  echo "UNKNOWN"
}

remaining_tasks_after_current() {
  python - <<'PY'
import json, os, pathlib, sys

tasks_file = pathlib.Path(os.environ["GO_TASKS_FILE"])
state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

active = state_dir / f"active-task_{run_id}.json"
if not active.exists():
    print("unknown")
    raise SystemExit(0)

selected_id = json.loads(active.read_text(encoding="utf-8"))["task"].get("id")
data = json.loads(tasks_file.read_text(encoding="utf-8"))
tasks = data.get("tasks", [])
allowed = {"ready", "queued", "approved"}

seen = False
remaining = False

for task in tasks:
    if task.get("id") == selected_id:
        seen = True
        continue
    if seen and task.get("status") in allowed:
        remaining = True
        break

print("yes" if remaining else "no")
PY
}

show_success_artifacts() {
  local pr_ready_file="$GO_STATE_DIR/pr-ready_$RUN_ID.md"
  local commit_file="$GO_STATE_DIR/commit-message_$RUN_ID.txt"

  [ -f "$pr_ready_file" ] && {
    echo
    cat "$pr_ready_file"
    echo
  }

  [ -f "$commit_file" ] && {
    log "Suggested commit command:"
    printf 'git commit -F "%s"\n' "$commit_file"
  }
}

main() {
  check_task_source
  emit_status_summary

  local cycle=1
  while [ "$cycle" -le "$MAX_CYCLES" ]; do
    log "cycle=$cycle/$MAX_CYCLES"

    # Artifact flags are authoritative — resume from last known state
    if has_flag ".pr-ready_$RUN_ID"; then
      log "artifact already indicates PR_READY"
      show_success_artifacts
      exit 0
    fi

    if has_flag ".blocked_$RUN_ID"; then
      log "artifact already indicates BLOCKED"
      exit 1
    fi

    set +e
    invoke_go
    GO_EXIT=$?
    set -e

    log "go_exit=$GO_EXIT"

    OUTCOME="$(task_outcome)"
    log "outcome=$OUTCOME"

    case "$OUTCOME" in
      PR_READY)
        MORE="$(remaining_tasks_after_current)"
        show_success_artifacts
        if [ "$MORE" = "yes" ]; then
          echo "<promise>MORE_TASKS_IN_PLAN</promise>"
        else
          echo "<promise>ALL_TASKS_COMPLETE</promise>"
        fi
        exit 0
        ;;
      BLOCKED)
        log "run blocked"
        exit 1
        ;;
      *)
        ATTEMPTS="$(count_attempts)"
        log "attempts=$ATTEMPTS"
        if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
          log "max attempts reached"
          exit 1
        fi
        ;;
    esac

    cycle=$((cycle + 1))
  done

  log "max cycles reached without terminal outcome"
  exit 1
}

main "$@"
