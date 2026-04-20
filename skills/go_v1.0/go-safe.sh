#!/bin/bash
# go-safe.sh — invoke /go with Gen 2 JSON-contract setup
# Usage: ./go-safe.sh

set -euo pipefail

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
  echo "Create one first:"
  echo "  git worktree add ../.worktrees/task-name -b task-name"
  exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
  echo -e "${RED}✗ Refusing to run on ${CURRENT_BRANCH}${NC}"
  exit 1
fi

export TERMINAL_ID="${TERMINAL_ID:-$(uuidgen | cut -d'-' -f1)}"
export RUN_ID="$(uuidgen)"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"

ARTIFACTS_DIR=".claude/.artifacts/$TERMINAL_ID/go"
PLAN_FILE="$ARTIFACTS_DIR/active-plan.json"
mkdir -p "$ARTIFACTS_DIR"

echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN} /go — Gen 2 JSON-Contract Workflow${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo ""
echo -e "Terminal ID: ${YELLOW}$TERMINAL_ID${NC}"
echo -e "Run ID: ${YELLOW}$RUN_ID${NC}"
echo -e "Max attempts: $MAX_ATTEMPTS"
echo -e "Artifacts: ${YELLOW}$ARTIFACTS_DIR${NC}"
echo -e "Branch: ${YELLOW}$CURRENT_BRANCH${NC}"
echo -e "Directory: ${YELLOW}$(pwd)${NC}"
echo ""

if [ ! -f "$PLAN_FILE" ]; then
  echo -e "${RED}✗ Missing required plan file:${NC} $PLAN_FILE"
  echo ""
  echo "Create active-plan.json first."
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

echo -e "${BLUE}Plan preview${NC}"
python -c "
import json, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

tasks = data.get('tasks', [])
eligible = []
done = 0
blocked = 0

for t in tasks:
    status = t.get('status', 'unknown')
    if status == 'done':
        done += 1
    elif status == 'blocked':
        blocked += 1
    elif status == 'pending':
        eligible.append(t)

print(f'Plan ID: {data.get(\"plan_id\", \"UNKNOWN\")}')
print(f'Total tasks: {len(tasks)}')
print(f'Pending tasks: {len(eligible)}')
print(f'Done tasks: {done}')
print(f'Blocked tasks: {blocked}')
print('')

if eligible:
    eligible = sorted(eligible, key=lambda x: (x.get('priority', 999999), x.get('task_id', '')))
    nxt = eligible[0]
    print('Next eligible task:')
    print(f'  task_id:   {nxt.get(\"task_id\", \"\")}')
    print(f'  title:     {nxt.get(\"title\", \"\")}')
    print(f'  priority:  {nxt.get(\"priority\", \"\")}')
    print(f'  objective: {nxt.get(\"objective\", \"\")}')
    print(f'  allowed:   {len(nxt.get(\"allowed_files\", []))} files')
    print(f'  forbidden:  {len(nxt.get(\"forbidden_files\", []))} rules')
    print(f'  checks:     {len(nxt.get(\"verification_commands\", []))} commands')
else:
    print('No eligible pending tasks found.')
" "$PLAN_FILE"
echo ""

# Check for eligible task
if ! python -c "
import json, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

tasks = data.get('tasks', [])
eligible = []
done_ids = {t.get('task_id') for t in tasks if t.get('status') == 'done'}

for t in tasks:
    if t.get('status') != 'pending':
        continue
    deps = t.get('depends_on', [])
    if all(dep in done_ids for dep in deps):
        required = [
            'task_id', 'title', 'objective',
            'allowed_files', 'forbidden_files',
            'acceptance_criteria', 'verification_commands'
        ]
        if all(k in t for k in required):
            eligible.append(t)

if not eligible:
    raise SystemExit(1)
print('ELIGIBLE_TASK_FOUND')
" "$PLAN_FILE" 2>/dev/null; then
  echo -e "${YELLOW}No eligible task is ready to run.${NC}"
  echo "If that is expected, /go would end with ALL_TASKS_COMPLETE or stop on unmet dependencies."
  exit 0
fi

cat > "$ARTIFACTS_DIR/.env_$RUN_ID" <<EOF
TERMINAL_ID=$TERMINAL_ID
RUN_ID=$RUN_ID
MAX_ATTEMPTS=$MAX_ATTEMPTS
BRANCH=$CURRENT_BRANCH
ARTIFACTS_DIR=$ARTIFACTS_DIR
PLAN_FILE=$PLAN_FILE
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

read -r -p "Proceed with /go? [y/N] " REPLY
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo ""
/go

echo ""
LATEST_ACTIVE_TASK="$ARTIFACTS_DIR/active-task_$RUN_ID.json"
LATEST_TASK_RESULT="$ARTIFACTS_DIR/task-result_$RUN_ID.json"
LATEST_PR_READY="$ARTIFACTS_DIR/pr-ready_$RUN_ID.md"

if [ -f "$LATEST_ACTIVE_TASK" ]; then
  echo -e "${BLUE}Selected task artifact${NC}"
  cat "$LATEST_ACTIVE_TASK"
  echo ""
fi

if [ -f "$LATEST_TASK_RESULT" ]; then
  echo -e "${BLUE}Task result artifact${NC}"
  cat "$LATEST_TASK_RESULT"
  echo ""
fi

if [ -f "$LATEST_PR_READY" ]; then
  echo -e "${GREEN}════════════════════════════════════════════${NC}"
  echo -e "${GREEN} ✓ PR_READY${NC}"
  echo -e "${GREEN}════════════════════════════════════════════${NC}"
  echo ""
  cat "$LATEST_PR_READY"
  echo ""
fi

if [ -f "$ARTIFACTS_DIR/.blocked_$RUN_ID" ]; then
  echo -e "${RED}════════════════════════════════════════════${NC}"
  echo -e "${RED} ✗ BLOCKED${NC}"
  echo -e "${RED}════════════════════════════════════════════${NC}"
  echo ""
fi

echo -e "Artifacts saved to: ${YELLOW}$ARTIFACTS_DIR${NC}"
echo -e "Run ID: ${YELLOW}$RUN_ID${NC}"
