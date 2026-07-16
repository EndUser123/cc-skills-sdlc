#!/usr/bin/env python3
"""cc-skills-sdlc hook router - dispatches to plugin hooks by event type.

Registered in P:/.claude/settings.json so the central config points only at this
router, not at individual plugin hook scripts (keeps the project hooks dir clean;
plugin hooks.json is not reliably loaded from external files - GitHub #16288).

Usage:
    python router.py <EventName>

Dispatch model: FAITHFUL PASS-THROUGH. Each child hook owns its own output
contract; this router forwards child stdout/stderr verbatim and inherits the
child's exit code. It does NOT append {} or force exit 2 (those would violate
strict-contract hooks like go_continuation_gate, which prints decision:block +
exit 0 to block and NOTHING + exit 0 to allow). A child that emits
{"decision":"block"} stops the dispatch chain (the block payload is already
forwarded on stdout).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

# event -> list of hook paths relative to PLUGIN_ROOT.
# Add future cc-skills-sdlc hooks here as they move off direct settings.json
# registration.
DISPATCH: dict[str, list[str]] = {
    "Stop": ["skills/go/scripts/go_continuation_gate.py"],
    "UserPromptSubmit": ["skills/go/scripts/chain_advance_ups.py"],
}

_TIMEOUT = 20.0  # generous; dispatched hooks do local file reads only


def _is_block(stdout_text: str) -> bool:
    """True if the child's stdout is a JSON block decision."""
    s = stdout_text.strip()
    if not s:
        return False
    try:
        parsed = json.loads(s)
        return isinstance(parsed, dict) and parsed.get("decision") == "block"
    except json.JSONDecodeError:
        return False


def main() -> None:
    if len(sys.argv) < 2:
        return
    event = sys.argv[1]
    hooks = DISPATCH.get(event)
    if not hooks:
        return

    input_data = sys.stdin.buffer.read()
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    for rel in hooks:
        hook_path = PLUGIN_ROOT / rel
        if not hook_path.exists():
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=input_data,
                capture_output=True,
                timeout=_TIMEOUT,
                creationflags=flags,
            )
        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue

        # Faithful pass-through: forward child stdout/stderr, inherit exit code.
        if result.stdout:
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.flush()
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
            sys.stderr.flush()
        if result.returncode != 0:
            sys.exit(result.returncode)

        # Child exited 0. If it emitted a block decision, stop the chain; the
        # block JSON is already on stdout. Otherwise continue to the next hook.
        if _is_block(result.stdout.decode(errors="replace")):
            return


if __name__ == "__main__":
    main()
