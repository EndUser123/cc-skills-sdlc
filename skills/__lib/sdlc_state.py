import os
from pathlib import Path

def resolve_state_root() -> Path:
    """Resolve STATE_ROOT, routing to .claude/.artifacts/{terminal_id}/sdlc/."""
    cwd = Path(os.getcwd()).resolve()
    tid = os.environ.get("CLAUDE_TERMINAL_ID", "unknown")
    # Using 'sdlc' as the base for all SDLC skills
    return cwd / ".claude" / ".artifacts" / tid / "sdlc"

def resolve_tdd_state_root() -> Path:
    """Resolve STATE_ROOT for TDD specifically."""
    return resolve_state_root() / "tdd"

def resolve_go_state_root() -> Path:
    """Resolve STATE_ROOT for GO specifically."""
    return resolve_state_root() / "go"
