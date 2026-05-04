#!/usr/bin/env bash
# Ralph-loop driver for /go skill — iterates until PR_READY or BLOCKED
# Usage: ./ralph-loop.sh [ticket-id]
# Requires: git worktree already created and cd'd into it

set -euo pipefail

TICKET="${1:-$(git branch --show-current 2>/dev/null | grep -oE '[a-zA-Z]+-[0-9]+' | head -1)}"
STATE_FILE=".claude/.artifacts/${CLAUDE_TERMINAL_ID:-unknown}/go/progress.txt"
ITERATION=0

echo "Ralph loop driver for: $TICKET"
echo "================================"

while true; do
  ITERATION=$((ITERATION + 1))
  echo ""
  echo "--- Iteration $ITERATION ---"

  # Run /go and capture output
  OUTPUT=$(/go 2>&1)
  echo "$OUTPUT"

  # Check for terminal tokens
  if echo "$OUTPUT" | grep -q '<promise>PR_READY</promise>'; then
    echo ""
    echo "Ralph loop complete: PR_READY"
    exit 0
  fi

  if echo "$OUTPUT" | grep -q '<promise>BLOCKED</promise>'; then
    echo ""
    echo "Ralph loop blocked — fix issues and re-run /go manually"
    exit 1
  fi

  if echo "$OUTPUT" | grep -q '<promise>ALL_TASKS_COMPLETE</promise>'; then
    echo ""
    echo "Ralph loop complete: ALL_TASKS_COMPLETE"
    exit 0
  fi

  if echo "$OUTPUT" | grep -q '<promise>MORE_TASKS_IN_PLAN</promise>'; then
    echo ""
    echo "More tasks in plan — continuing loop"
    continue
  fi

  # If no recognized token, check progress file for iteration count
  if [[ -f "$STATE_FILE" ]]; then
    LAST_ITER=$(grep -oE 'Iteration:[0-9]+' "$STATE_FILE" 2>/dev/null | tail -1 | grep -oE '[0-9]+' || echo "0")
    if [[ "$LAST_ITER" -ge "$ITERATION" ]]; then
      # Progress file shows advancement — loop should continue
      continue
    fi
  fi

  # Safety: max 10 iterations to prevent infinite loops
  if [[ "$ITERATION" -ge 10 ]]; then
    echo "Safety stop: 10 iterations reached"
    exit 1
  fi

  echo "No terminal token detected — retrying in 5s"
  sleep 5
done
