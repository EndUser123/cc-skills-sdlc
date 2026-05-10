#!/usr/bin/env bash
set -euo pipefail

export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')}"
export RUN_ID="${RUN_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export GO_TASKS_FILE="${GO_TASKS_FILE:-.claude/tasks/tasks.json}"
export GO_STATE_DIR=".claude/.artifacts/${TERMINAL_ID}/go"

mkdir -p "$GO_STATE_DIR"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "ERROR: not in a git repository"
  exit 1
}

BRANCH="$(git branch --show-current)"
case "$BRANCH" in
  main|master)
    echo "ERROR: do not run /go on $BRANCH"
    exit 1
    ;;
esac

git worktree list --porcelain | grep -F "worktree $(pwd)" >/dev/null 2>&1 || {
  echo "ERROR: current directory is not a git worktree"
  exit 1
}

if [ ! -f "$GO_TASKS_FILE" ]; then
  echo "ERROR: tasks file not found: $GO_TASKS_FILE"
  exit 1
fi

echo "TERMINAL_ID=$TERMINAL_ID"
echo "RUN_ID=$RUN_ID"
echo "GO_STATE_DIR=$GO_STATE_DIR"
echo "GO_TASKS_FILE=$GO_TASKS_FILE"
echo
git diff --stat HEAD || true
echo
read -r -p "Invoke /go now? [y/N] " ANSWER

case "$ANSWER" in
  y|Y|yes|YES)
    ;;
  *)
    echo "Cancelled"
    exit 0
    ;;
esac

if command -v /go >/dev/null 2>&1; then
  /go
elif command -v go >/dev/null 2>&1; then
  go
else
  echo "ERROR: /go command not found"
  exit 1
fi
