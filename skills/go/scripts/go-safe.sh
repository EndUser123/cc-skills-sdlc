#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT_DIR"

# Derive TERMINAL_ID via the canonical generator (frozen cross-plugin source);
# env override wins, else python loader, else uuidgen fallback.
_CANONICAL_TID_PY="$(python -c '
import importlib.util
spec = importlib.util.spec_from_file_location("_t", "P:/packages/.claude-marketplace/plugins/search-research/core/terminal_id.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.canonical_terminal_id())
' 2>/dev/null || true)"
TERMINAL_ID="${CLAUDE_TERMINAL_ID:-${TERMINAL_ID:-${_CANONICAL_TID_PY:-$(uuidgen | cut -d'-' -f1)}}}"
GO_RUN_ID="${GO_RUN_ID:-$(uuidgen)}"
ARTIFACT_ROOT="${CLAIREC_CODE_ARTIFACTS_DIR:-.claude/.artifacts}"
GO_ARTIFACT_DIR="${ARTIFACT_ROOT}/${TERMINAL_ID}/go"
SCHEMA_DIR="${ROOT_DIR}/skills/go/schemas"
VALIDATOR="${ROOT_DIR}/skills/go/scripts/validate_go_contracts.py"
INIT_SCRIPT="${ROOT_DIR}/skills/go/scripts/init_go_run.py"

export TERMINAL_ID
export GO_RUN_ID
export GO_ARTIFACT_DIR

mkdir -p "$GO_ARTIFACT_DIR"

die() {
  echo "ERROR: $*" >&2
  touch "${GO_ARTIFACT_DIR}/.blocked_${GO_RUN_ID}" || true
  exit 1
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || die "missing required file: $path"
}

CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
[[ -n "${CURRENT_BRANCH}" ]] || die "not in a git repository or branch undetectable"
[[ "${CURRENT_BRANCH}" != "main" && "${CURRENT_BRANCH}" != "master" ]] || die "refusing to run on ${CURRENT_BRANCH}"

if git worktree list --porcelain >/tmp/go_worktrees.$$ 2>/dev/null; then
  if grep -Fq "worktree $(pwd)" /tmp/go_worktrees.$$; then
    touch "${GO_ARTIFACT_DIR}/.worktree-ready_${GO_RUN_ID}"
  else
    die "current directory is not an active git worktree"
  fi
else
  touch "${GO_ARTIFACT_DIR}/.worktree-ready_${GO_RUN_ID}"
fi
rm -f /tmp/go_worktrees.$$ || true

python "$INIT_SCRIPT" \
  --root-dir "$ROOT_DIR" \
  --terminal-id "$TERMINAL_ID" \
  --go-run-id "$GO_RUN_ID" \
  --artifact-dir "$GO_ARTIFACT_DIR" \
  "$@"

require_file "${GO_ARTIFACT_DIR}/run_${GO_RUN_ID}.json"
require_file "${GO_ARTIFACT_DIR}/selected-task_${GO_RUN_ID}.json"
require_file "${GO_ARTIFACT_DIR}/dispatch-decision_${GO_RUN_ID}.json"
require_file "${GO_ARTIFACT_DIR}/dispatch-result_${GO_RUN_ID}.json"

python "$VALIDATOR" \
  --schema-dir "$SCHEMA_DIR" \
  --artifact-dir "$GO_ARTIFACT_DIR"

echo "<promise>GO_DISPATCHED</promise>"
echo "GO_RUN_ID=${GO_RUN_ID}"
echo "TERMINAL_ID=${TERMINAL_ID}"
echo "ARTIFACT_DIR=${GO_ARTIFACT_DIR}"
