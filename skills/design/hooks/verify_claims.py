"""Claim verification state writer for design skill.

Writes a .verified flag to the session state file so the stop_if_unverified.py hook
can confirm verification was performed.

No DESIGN_RUN_ID env var needed — uses session-scoped state file keyed by WT_SESSION.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


VALID_DOMAINS = ("browser_automation", "performance", "api_integration", "general")


def _terminal_id() -> str:
    """Resolve terminal ID, falling back to WT_SESSION or 'default'."""
    tid = os.environ.get("CLAUDE_TERMINAL_ID", "").strip()
    if tid:
        return tid
    tid = os.environ.get("WT_SESSION", "").strip()
    if tid:
        return tid
    return "default"


def _state_dir() -> Path:
    """Resolve the design artifact directory for this terminal session.

    Uses skill-local .claude/.artifacts/{TERMINAL_ID}/design/ following /go pattern.
    """
    skill_root = Path(__file__).resolve().parent.parent
    tid = _terminal_id()
    return skill_root / ".claude" / ".artifacts" / tid / "design"


def _state_file() -> Path:
    """Path to the session state file."""
    state_dir = _state_dir()
    return state_dir / ".state.json"


def verify(run_id: str, domain: str, claims_count: int = 0) -> str:
    """Write verification state. Returns path to state file."""
    if not run_id:
        print("ERROR: run_id is required", file=sys.stderr)
        sys.exit(1)

    if domain not in VALID_DOMAINS:
        print(f"ERROR: invalid domain '{domain}'. Must be one of {VALID_DOMAINS}", file=sys.stderr)
        sys.exit(1)

    state_dir = _state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    state_file = _state_file()
    record = {
        "run_id": run_id,
        "verification_domain": domain,
        "claims_verified": claims_count,
        "verified": True,
        "timestamp": time.time(),
    }
    state_file.write_text(json.dumps(record), encoding="utf-8")
    return str(state_file)


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: verify_claims.py <run_id> <verification_domain> [claims_count]\n"
            f"  verification_domain: {'|'.join(VALID_DOMAINS)}",
            file=sys.stderr
        )
        sys.exit(1)

    run_id = sys.argv[1]
    domain = sys.argv[2]
    claims_count = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    state_path = verify(run_id, domain, claims_count)
    print(f"VERIFIED: run_id={run_id} domain={domain} claims={claims_count}")
    print(f"State written: {state_path}")


if __name__ == "__main__":
    main()
