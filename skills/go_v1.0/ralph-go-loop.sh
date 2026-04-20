#!/bin/bash
# ralph-go-loop.sh — autonomous /go Ralph loop for Gen 2 JSON contracts
# Usage: ./ralph-go-loop.sh [max_cycles]

set -euo pipefail

MAX_CYCLES="${1:-10}"
CYCLE=0

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

if ! command -v python >/dev/null 2>&1; then
  echo -e "${RED}✗ python is required${NC}"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo -e "${RED}✗ Not inside a git repository${NC}"
  exit 1
fi

if ! git worktree list --porcelain | grep -q "$(pwd)"; then
  echo -e "${RED}✗ Not in a git worktree${NC}"
  exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
  echo -e "${RED}✗ Refusing to run on ${CURRENT_BRANCH}${NC}"
  exit 1
fi

export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1)}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"

ARTIFACTS_DIR=".claude/.artifacts/$TERMINAL_ID/go"
PLAN_FILE="$ARTIFACTS_DIR/active-plan.json"
mkdir -p "$ARTIFACTS_DIR"

if [ ! -f "$PLAN_FILE" ]; then
  echo -e "${RED}✗ Missing required plan file:${NC} $PLAN_FILE"
  exit 1
fi

if ! python -c "
import json, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
if not isinstance(data, dict):
    raise SystemExit(1)
if 'tasks' not in data or not isinstance(data['tasks'], list):
    raise SystemExit(1)
print('OK')
" "$PLAN_FILE" 2>/dev/null; then
  echo -e "${RED}✗ active-plan.json is invalid${NC}"
  exit 1
fi

echo -e "${BLUE}┌──────────────────────────────────────────────┐${NC}"
echo -e "${BLUE}│ Ralph Loop: /go until plan is exhausted      │${NC}"
echo -e "${BLUE}└──────────────────────────────────────────────┘${NC}"
echo ""
echo -e "Terminal ID: ${YELLOW}$TERMINAL_ID${NC}"
echo -e "Max cycles: ${YELLOW}$MAX_CYCLES${NC}"
echo -e "Max attempts/run: ${YELLOW}$MAX_ATTEMPTS${NC}"
echo -e "Artifacts: ${YELLOW}$ARTIFACTS_DIR${NC}"
echo -e "Branch: ${YELLOW}$CURRENT_BRANCH${NC}"
echo ""

plan_summary() {
  python -c "
import json, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

tasks = data.get('tasks', [])
done_ids = {t.get('task_id') for t in tasks if t.get('status') == 'done'}

eligible = []
pending = 0
done = 0
blocked = 0

for t in tasks:
    status = t.get('status', 'unknown')
    if status == 'pending':
        pending += 1
        deps = t.get('depends_on', [])
        required = [
            'task_id', 'title', 'objective',
            'allowed_files', 'forbidden_files',
            'acceptance_criteria', 'verification_commands'
        ]
        if all(dep in done_ids for dep in deps) and all(k in t for k in required):
            eligible.append(t)
    elif status == 'done':
        done += 1
    elif status == 'blocked':
        blocked += 1

print(f'PLAN_ID={data.get(\"plan_id\", \"UNKNOWN\")}')
print(f'TOTAL={len(tasks)}')
print(f'PENDING={pending}')
print(f'DONE={done}')
print(f'BLOCKED={blocked}')
print(f'ELIGIBLE={len(eligible)}')

if eligible:
    eligible = sorted(eligible, key=lambda x: (x.get('priority', 999999), x.get('task_id', '')))
    nxt = eligible[0]
    print(f'NEXT_TASK_ID={nxt.get(\"task_id\", \"\")}')
    print(f'NEXT_TITLE={nxt.get(\"title\", \"\")}')
    print(f'NEXT_PRIORITY={nxt.get(\"priority\", \"\")}')
else:
    print('NEXT_TASK_ID=')
    print('NEXT_TITLE=')
    print('NEXT_PRIORITY=')
" "$PLAN_FILE"
}

while [ "$CYCLE" -lt "$MAX_CYCLES" ]; do
  CYCLE=$((CYCLE + 1))
  export RUN_ID="$(uuidgen)"

  echo -e "${BLUE}──────────────────────────────────────────────${NC}"
  echo -e "${BLUE}Cycle $CYCLE/$MAX_CYCLES${NC}"
  echo -e "${BLUE}──────────────────────────────────────────────${NC}"
  echo -e "Run ID: ${YELLOW}$RUN_ID${NC}"
  echo ""

  eval "$(plan_summary)"
  echo "Plan ID: $PLAN_ID"
  echo "Total tasks: $TOTAL"
  echo "Pending: $PENDING"
  echo "Done: $DONE"
  echo "Blocked: $BLOCKED"
  echo "Eligible now: $ELIGIBLE"

  if [ "$ELIGIBLE" -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ No eligible tasks remain${NC}"
    echo "<promise>ALL_TASKS_COMPLETE</promise>"
    exit 0
  fi

  echo "Next eligible task:"
  echo "  task_id:  $NEXT_TASK_ID"
  echo "  title:    $NEXT_TITLE"
  echo "  priority: $NEXT_PRIORITY"
  echo ""

  cat > "$ARTIFACTS_DIR/.env_$RUN_ID" <<EOF
TERMINAL_ID=$TERMINAL_ID
RUN_ID=$RUN_ID
MAX_ATTEMPTS=$MAX_ATTEMPTS
BRANCH=$CURRENT_BRANCH
ARTIFACTS_DIR=$ARTIFACTS_DIR
PLAN_FILE=$PLAN_FILE
CYCLE=$CYCLE
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  OUTPUT_FILE="$ARTIFACTS_DIR/go-output_$RUN_ID.log"
  /go >"$OUTPUT_FILE" 2>&1 || true

  BLOCKED_FLAG="$ARTIFACTS_DIR/.blocked_$RUN_ID"
  PR_READY_FLAG="$ARTIFACTS_DIR/.pr-ready_$RUN_ID"
  ACTIVE_TASK_FILE="$ARTIFACTS_DIR/active-task_$RUN_ID.json"
  TASK_RESULT_FILE="$ARTIFACTS_DIR/task-result_$RUN_ID.json"
  PR_READY_FILE="$ARTIFACTS_DIR/pr-ready_$RUN_ID.md"

  if [ -f "$ACTIVE_TASK_FILE" ]; then
    echo -e "${BLUE}Selected task${NC}"
    cat "$ACTIVE_TASK_FILE"
    echo ""
  fi

  if [ -f "$TASK_RESULT_FILE" ]; then
    echo -e "${BLUE}Task result${NC}"
    cat "$TASK_RESULT_FILE"
    echo ""
  fi

  if [ -f "$BLOCKED_FLAG" ]; then
    echo -e "${RED}✗ BLOCKED${NC}"
    if [ -f "$OUTPUT_FILE" ]; then
      echo ""
      echo -e "${YELLOW}Last /go output:${NC}"
      cat "$OUTPUT_FILE"
      echo ""
    fi
    echo "<promise>BLOCKED</promise>"
    exit 1
  fi

  if [ -f "$PR_READY_FLAG" ]; then
    echo -e "${GREEN}✓ PR_READY flag detected${NC}"
    if [ -f "$PR_READY_FILE" ]; then
      echo ""
      cat "$PR_READY_FILE"
      echo ""
    fi
  else
    echo -e "${RED}✗ Missing .pr-ready_$RUN_ID after /go${NC}"
    if [ -f "$OUTPUT_FILE" ]; then
      echo ""
      echo -e "${YELLOW}Last /go output:${NC}"
      cat "$OUTPUT_FILE"
      echo ""
    fi
    exit 1
  fi

  eval "$(plan_summary)"
  echo -e "${BLUE}Post-cycle plan state${NC}"
  echo "Pending: $PENDING"
  echo "Done: $DONE"
  echo "Blocked: $BLOCKED"
  echo "Eligible now: $ELIGIBLE"
  echo ""

  if [ "$ELIGIBLE" -gt 0 ]; then
    echo -e "${YELLOW}More eligible tasks remain; continuing...${NC}"
    echo "<promise>MORE_TASKS_IN_PLAN</promise>"
    echo ""
    sleep 1
    continue
  fi

  echo -e "${GREEN}══════════════════════════════════════════════${NC}"
  echo -e "${GREEN} ✓✓✓ ALL TASKS COMPLETE ✓✓✓${NC}"
  echo -e "${GREEN}══════════════════════════════════════════════${NC}"
  echo ""
  echo -e "Artifacts: ${YELLOW}$ARTIFACTS_DIR${NC}"
  echo -e "Terminal ID: ${YELLOW}$TERMINAL_ID${NC}"
  echo "<promise>ALL_TASKS_COMPLETE</promise>"
  exit 0
done

echo ""
echo -e "${RED}✗ Max cycles ($MAX_CYCLES) reached before plan completion${NC}"
exit 1
