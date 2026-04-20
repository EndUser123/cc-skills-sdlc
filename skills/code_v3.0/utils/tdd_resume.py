#!/usr/bin/env python3
"""TDD Resume Context Injection for /code skill.

Detects and restores TDD context after compaction or session resume.
Reads state files from:
- .claude/state/tdd/{terminal_id}/tdd.*.json (TDD state files)
- .claude/evidence/tdd95/{contract_id}/ (Phase 3 evidence)

Provides context injection for SessionStart or handoff restore.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# State directory for TDD state files (configurable via env var for testing)
TDD_STATE_DIR = Path(os.environ.get("TDD_STATE_DIR", "P:/.claude/state/tdd"))

# Evidence directory for Phase 3 TDD contracts (configurable via env var for testing)
TDD_EVIDENCE_DIR = Path(os.environ.get("TDD_EVIDENCE_DIR", "P:/.claude/evidence/tdd95"))


def get_terminal_id() -> str:
    """Get current terminal ID from environment."""
    return os.environ.get("CLAUDE_TERMINAL_ID", "default")


def get_session_id() -> str:
    """Get current session ID from environment."""
    return os.environ.get("CLAUDE_SESSION_ID", "default")


def find_active_tdd_contracts(terminal_id: str | None = None) -> list[dict]:
    """Find all active TDD contracts for this terminal.

    Args:
        terminal_id: Terminal ID to search (uses current if None)

    Returns:
        List of contract state dicts with contract_id, phase, test_file, timestamp
    """
    tid = terminal_id or get_terminal_id()
    terminal_dir = TDD_STATE_DIR / tid

    if not terminal_dir.exists():
        return []

    contracts = []
    for state_file in terminal_dir.glob("tdd.*.json"):
        try:
            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)

            # Skip completed/IDLE contracts
            phase = state.get("phase", "IDLE")
            if phase == "IDLE" or state.get("completed", False):
                continue

            contracts.append(
                {
                    "contract_id": state_file.stem.replace("tdd.", ""),
                    "phase": phase,
                    "test_file": state.get("test_file"),
                    "impl_files": state.get("impl_files", []),
                    "timestamp": state_file.stat().st_mtime,
                    "state_file": str(state_file),
                }
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Failed to read TDD state {state_file}: {e}")
            continue

    # Sort by most recent
    contracts.sort(key=lambda x: x["timestamp"], reverse=True)
    return contracts


def find_phase3_evidence(contract_id: str | None = None) -> list[dict]:
    """Find Phase 3 evidence files for TDD contracts.

    Args:
        contract_id: Specific contract to find (finds all if None)

    Returns:
        List of evidence dicts with contract_id, phase, evidence_file, timestamp
    """
    if not TDD_EVIDENCE_DIR.exists():
        return []

    evidence_list = []

    # Search specific contract or all contracts
    if contract_id:
        contract_dirs = (
            [TDD_EVIDENCE_DIR / contract_id] if (TDD_EVIDENCE_DIR / contract_id).exists() else []
        )
    else:
        contract_dirs = [d for d in TDD_EVIDENCE_DIR.iterdir() if d.is_dir()]

    for contract_dir in contract_dirs:
        for evidence_file in contract_dir.glob("*.json"):
            try:
                with open(evidence_file, encoding="utf-8") as f:
                    evidence = json.load(f)

                evidence_list.append(
                    {
                        "contract_id": contract_dir.name,
                        "phase": evidence.get("phase", "unknown"),
                        "evidence_hash": evidence.get("evidence_hash"),
                        "timestamp": evidence_file.stat().st_mtime,
                        "evidence_file": str(evidence_file),
                    }
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"Failed to read evidence {evidence_file}: {e}")
                continue

    # Sort by most recent
    evidence_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return evidence_list


def generate_tdd_resume_context(terminal_id: str | None = None) -> str | None:
    """Generate context string for TDD resume after compaction.

    This function is called during SessionStart or handoff restore to
    detect and restore TDD context that was lost during compaction.

    Args:
        terminal_id: Terminal ID to check (uses current if None)

    Returns:
        Context string to inject, or None if no active TDD sessions
    """
    tid = terminal_id or get_terminal_id()

    # Find active TDD contracts
    contracts = find_active_tdd_contracts(tid)

    if not contracts:
        return None

    # Build context for each active contract
    context_parts = ["## TDD Session Resume Context\n"]
    context_parts.append(f"**Terminal**: {tid}\n")
    context_parts.append(f"**Active TDD Sessions**: {len(contracts)}\n\n")

    for contract in contracts:
        context_parts.append(f"### Contract: {contract['contract_id']}\n")
        context_parts.append(f"- **Phase**: {contract['phase']}\n")
        if contract["test_file"]:
            context_parts.append(f"- **Test File**: {contract['test_file']}\n")
        if contract["impl_files"]:
            context_parts.append(
                f"- **Implementation Files**: {', '.join(contract['impl_files'])}\n"
            )

        # Check for Phase 3 evidence
        evidence = find_phase3_evidence(contract["contract_id"])
        if evidence:
            latest = evidence[0]
            context_parts.append(
                f"- **Latest Evidence**: {latest['phase']} phase (hash: {latest['evidence_hash'][:16]}...)\n"
            )

        context_parts.append("\n")

    # Add resume instructions
    context_parts.append("---\n\n")
    context_parts.append("**Resume Instructions**:\n")
    context_parts.append("1. Read the state file for the contract you want to resume\n")
    context_parts.append("2. Check the current phase and proceed accordingly:\n")
    context_parts.append("   - AWAITING_RED: Run the test to confirm failure\n")
    context_parts.append("   - RED_CONFIRMED: Implement code to pass tests\n")
    context_parts.append("   - GREEN_CONFIRMED: Refactor if needed, then verify\n")
    context_parts.append("3. Continue TDD cycle until phase reaches VERIFY complete\n")

    return "".join(context_parts)


def get_tdd_state_for_handoff(terminal_id: str | None = None) -> dict:
    """Get TDD state summary for handoff envelope.

    This is called during handoff capture to include TDD state in the
    handoff envelope, ensuring context is preserved across sessions.

    Args:
        terminal_id: Terminal ID to check (uses current if None)

    Returns:
        Dict with active_contracts, evidence_summary for handoff envelope
    """
    tid = terminal_id or get_terminal_id()

    contracts = find_active_tdd_contracts(tid)
    evidence = find_phase3_evidence()

    return {
        "active_contracts": [
            {
                "contract_id": c["contract_id"],
                "phase": c["phase"],
                "test_file": c["test_file"],
            }
            for c in contracts
        ],
        "evidence_count": len(evidence),
        "terminal_id": tid,
    }


# CLI entry point for testing
if __name__ == "__main__":
    import sys

    if "--handoff" in sys.argv:
        print(json.dumps(get_tdd_state_for_handoff(), indent=2))
    else:
        context = generate_tdd_resume_context()
        if context:
            print(context)
        else:
            print("No active TDD sessions found")
