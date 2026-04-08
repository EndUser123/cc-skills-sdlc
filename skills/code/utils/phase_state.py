#!/usr/bin/env python3
"""
Phase state manager for /code skill workflow.

Tracks phase completion with commit-aware rollback detection, multi-terminal
ownership, and phase order enforcement.
"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

# Home-directory state path for /code skill
_HOME_CLAUDE_STATE = Path.home() / ".claude" / ".state" / "code"


def _sanitize_terminal_id(raw_id: str | None) -> str:
    """Sanitize terminal ID to prevent path traversal.

    Strips any character not in [a-zA-Z0-9_-] to prevent path traversal.
    Fallback chain: CLAUDE_TERMINAL_ID -> TERMINAL_ID -> "default"

    Args:
        raw_id: Raw terminal ID from environment or parameter

    Returns:
        Sanitized terminal identifier string
    """
    if not raw_id:
        raw_id = os.environ.get("CLAUDE_TERMINAL_ID", os.environ.get("TERMINAL_ID", "default"))
    # Sanitize: keep only alphanumeric, underscore, hyphen
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id)
    return sanitized or "default"


def get_git_head_hash() -> str | None:
    """Get current git HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


class PhaseStateManager:
    """Manage phase state for /code skill workflow."""

    def __init__(self, terminal_id: str):
        """Initialize phase state manager for terminal."""
        self.terminal_id = _sanitize_terminal_id(terminal_id)
        # Terminal-scoped state files for multi-terminal isolation
        self.global_state_file = _HOME_CLAUDE_STATE / f"phase_state_{self.terminal_id}.json"
        self.build_state_file = _HOME_CLAUDE_STATE / f"build_state_{self.terminal_id}.json"
        self._ensure_state_exists()

    def _ensure_state_exists(self):
        """Create state files if they don't exist."""
        # Global phase state
        if not self.global_state_file.exists():
            self.global_state_file.parent.mkdir(parents=True, exist_ok=True)
            self.global_state_file.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "last_updated": datetime.now().isoformat(),
                        "phases": {},
                        "current_phase": None,
                    },
                    indent=2,
                )
            )

        # Terminal-scoped build state
        if not self.build_state_file.exists():
            self.build_state_file.parent.mkdir(parents=True, exist_ok=True)
            self.build_state_file.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "terminal_id": self.terminal_id,
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "current_owner": None,
                        "owner_expires_at": None,
                        "active_phase": None,
                    },
                    indent=2,
                )
            )

    def _load_global_state(self) -> dict:
        """Load global phase state from disk."""
        return json.loads(self.global_state_file.read_text())

    def _save_global_state(self, state: dict):
        """Save global phase state to disk."""
        state["last_updated"] = datetime.now().isoformat()
        self.global_state_file.write_text(json.dumps(state, indent=2))

    def _load_build_state(self) -> dict:
        """Load terminal-scoped build state from disk."""
        return json.loads(self.build_state_file.read_text())

    def _save_build_state(self, state: dict):
        """Save terminal-scoped build state to disk."""
        state["last_updated"] = datetime.now().isoformat()
        self.build_state_file.write_text(json.dumps(state, indent=2))

    def is_phase_valid(self, phase_name: str) -> bool:
        """Check if phase completion is still valid given current git state."""
        state = self._load_global_state()
        phases = state.get("phases", {})
        phase_state = phases.get(phase_name, {})

        if not phase_state.get("completed"):
            return False

        recorded_hash = phase_state.get("commit_hash")
        if not recorded_hash:
            return False

        current_hash = get_git_head_hash()
        if current_hash and current_hash != recorded_hash:
            # Invalidate if commit changed
            return False

        return True

    def mark_phase_complete(
        self, phase_name: str, commit_hash: str | None = None, metadata: dict | None = None
    ):
        """Mark a phase as complete with commit hash for rollback detection."""
        state = self._load_global_state()

        if phase_name not in state["phases"]:
            state["phases"][phase_name] = {}

        state["phases"][phase_name]["completed"] = True
        state["phases"][phase_name]["completed_at"] = datetime.now().isoformat()
        state["phases"][phase_name]["terminal_id"] = self.terminal_id

        if commit_hash:
            state["phases"][phase_name]["commit_hash"] = commit_hash

        if metadata:
            for key, value in metadata.items():
                state["phases"][phase_name][key] = value

        state["current_phase"] = phase_name
        self._save_global_state(state)

    def invalidate_phase(self, phase_name: str):
        """Invalidate a phase (e.g., after rollback detected)."""
        state = self._load_global_state()
        phases = state.get("phases", {})

        if phase_name in phases:
            phases[phase_name]["completed"] = False
            phases[phase_name]["invalidated_at"] = datetime.now().isoformat()

        self._save_global_state(state)

    def acquire_build_ownership(self, timeout_minutes: int = 120) -> bool:
        """Acquire ownership of build process for this terminal.

        Returns True if ownership acquired, False if already owned by another terminal.
        """
        state = self._load_build_state()
        now = datetime.now().isoformat()

        # Check if current ownership is expired
        current_owner = state.get("current_owner")
        expires_at = state.get("owner_expires_at")

        if current_owner and current_owner != self.terminal_id:
            if expires_at and expires_at > now:
                # Still owned by another terminal
                return False

        # Acquire ownership
        state["current_owner"] = self.terminal_id
        state["owner_expires_at"] = datetime.fromtimestamp(
            datetime.now().timestamp() + (timeout_minutes * 60)
        ).isoformat()
        self._save_build_state(state)
        return True

    def release_build_ownership(self):
        """Release ownership of build process."""
        state = self._load_build_state()
        state["current_owner"] = None
        state["owner_expires_at"] = None
        self._save_build_state(state)

    def get_phase_status(self, phase_name: str) -> dict:
        """Get current status of a phase."""
        state = self._load_global_state()
        phases = state.get("phases", {})
        phase_state = phases.get(phase_name, {})

        return {
            "completed": phase_state.get("completed", False),
            "completed_at": phase_state.get("completed_at"),
            "commit_hash": phase_state.get("commit_hash"),
            "terminal_id": phase_state.get("terminal_id"),
            "valid": self.is_phase_valid(phase_name),
            "metadata": {
                k: v
                for k, v in phase_state.items()
                if k not in ["completed", "completed_at", "commit_hash", "terminal_id"]
            },
        }

    def get_all_phases_status(self) -> dict:
        """Get status of all phases."""
        state = self._load_global_state()
        phases = state.get("phases", {})
        result = {}

        for phase_name in phases:
            result[phase_name] = self.get_phase_status(phase_name)

        return result


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python phase_state.py <terminal_id> [command]")
        print("Commands:")
        print("  status - Show all phase status")
        print("  complete <phase> - Mark phase as complete")
        print("  invalidate <phase> - Invalidate phase")
        print("  acquire - Acquire build ownership")
        print("  release - Release build ownership")
        sys.exit(1)

    terminal_id = sys.argv[1]
    mgr = PhaseStateManager(terminal_id)

    if len(sys.argv) >= 3:
        command = sys.argv[2]

        if command == "status":
            status = mgr.get_all_phases_status()
            print("Phase Status:")
            for phase, data in status.items():
                valid = "✓" if data["valid"] else "✗"
                done = "✓" if data["completed"] else "✗"
                print(f"  {phase}: {done} completed, {valid} valid")

        elif command == "complete" and len(sys.argv) >= 4:
            phase = sys.argv[3]
            commit = get_git_head_hash()
            mgr.mark_phase_complete(phase, commit)
            print(f"Marked {phase} complete")

        elif command == "invalidate" and len(sys.argv) >= 4:
            phase = sys.argv[3]
            mgr.invalidate_phase(phase)
            print(f"Invalidated {phase}")

        elif command == "acquire":
            if mgr.acquire_build_ownership():
                print(f"Acquired build ownership for {terminal_id}")
            else:
                print("Failed to acquire ownership (owned by another terminal)")

        elif command == "release":
            mgr.release_build_ownership()
            print("Released build ownership")

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        print(f"Global state: {mgr.global_state_file}")
        print(f"Build state: {mgr.build_state_file}")
