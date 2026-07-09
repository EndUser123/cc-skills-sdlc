#!/usr/bin/env python3
"""Optional PreToolUse guard for integration-sensitive files.

Warns (stderr, allow) when an Edit/Write targets an integration-sensitive file
and no active task worktree is registered for the current session.

Set GO_WORKTREE_SAFETY_BLOCK=1 to upgrade warnings to denies.

Fail-safe: missing/malformed metadata → warn, not block.

Registration (optional — NOT auto-registered):
  Add to SKILL.md frontmatter hooks.PreToolUse or to settings.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HOOK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HOOK_DIR.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from worktree_safety import is_integration_sensitive, _list_metadata, _resolve_state_dir  # noqa: E402


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        return 0  # fail-silent on malformed payload

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    if not file_path:
        return 0  # no file target — allow

    # Resolve to repo-relative (best-effort)
    p = str(file_path).replace("\\", "/")
    # Strip common prefixes to get repo-relative
    for prefix in ("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/",
                   "packages/.claude-marketplace/plugins/cc-skills-sdlc/"):
        if p.startswith(prefix):
            p = p[len(prefix):]
            break

    if not is_integration_sensitive(p):
        return 0  # non-sensitive — silent allow

    # Sensitive file touched — check for active task worktree
    state_dir = _resolve_state_dir(None)
    tasks = _list_metadata(state_dir)
    has_active = any(t.get("status") == "active" for t in tasks)

    if has_active:
        return 0  # registered worktree exists — allow

    # No active worktree — warn or block
    msg = (f"WORKTREE_SAFETY: editing integration-sensitive file '{p}' "
           f"outside a registered task worktree. Consider "
           f"'python scripts/worktree_safety.py start --task-id ...' first.")

    if os.environ.get("GO_WORKTREE_SAFETY_BLOCK", "").strip() == "1":
        print(json.dumps({
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }))
    else:
        print(msg, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
