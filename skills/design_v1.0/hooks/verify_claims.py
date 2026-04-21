"""Claim verification state writer for design_v1.0.

Called by the LLM after completing Step 0.4 (Claim Verification Gate).
Writes a .verified_<RUNID> flag file so the stop_if_unverified.py hook
can confirm verification was performed.

Usage:
    python verify_claims.py <run_id> <verification_domain> [claims_count]

Arguments:
    run_id:              The RUN ID for this design session
    verification_domain: The detected verification domain
                         (browser_automation|performance|api_integration|general)
    claims_count:        Optional number of claims verified (default: 0)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

VALID_DOMAINS = ("browser_automation", "performance", "api_integration", "general")


def _state_dir() -> Path:
    """Resolve the arch_decisions directory for verification state files."""
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root.parent.parent.parent / ".claude" / "arch_decisions"


def verify(run_id: str, domain: str, claims_count: int = 0) -> str:
    """Write verification flag file. Returns path to flag file."""
    if not run_id:
        print("ERROR: run_id is required", file=sys.stderr)
        sys.exit(1)

    if domain not in VALID_DOMAINS:
        print(f"ERROR: invalid domain '{domain}'. Must be one of {VALID_DOMAINS}", file=sys.stderr)
        sys.exit(1)

    state_dir = _state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    flag_file = state_dir / f".verified_{run_id}"

    record = {
        "run_id": run_id,
        "verification_domain": domain,
        "claims_verified": claims_count,
        "timestamp": time.time(),
    }

    flag_file.write_text(json.dumps(record), encoding="utf-8")
    return str(flag_file)


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

    flag_path = verify(run_id, domain, claims_count)
    print(f"VERIFIED: run_id={run_id} domain={domain} claims={claims_count}")
    print(f"Flag written: {flag_path}")


if __name__ == "__main__":
    main()
