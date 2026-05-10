#!/usr/bin/env python3
"""
SessionEnd hook to clean up /rca session state.
Archives RCA findings, clears temporary state, and ingests lessons to CKS.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
CSF_SRC = os.environ.get("CSF_SRC", "P:\\\\\\__csf/src")
STATE_DIR = Path(os.environ.get("DEBUG_RCA_STATE_DIR", CLAUDE_HOME / "state" / "rca"))
STATE_FILE = STATE_DIR / "rca_workflow.json"
ARCHIVE_DIR = STATE_DIR / "archive"
ACTIVE_SESSION_FILE = STATE_DIR / "active_session.json"
ACTIVE_SESSION_TTL_HOURS = 8

# Import auto-logging decorator (optional)
_hooks_lib = CLAUDE_HOME / "hooks" / "__lib"
if _hooks_lib.exists():
    sys.path.insert(0, str(_hooks_lib))
    try:
        from hook_base import hook_main
    except ImportError:
        hook_main = lambda f: f  # Fallback: no-op decorator
else:
    hook_main = lambda f: f  # Fallback: no-op decorator


# FileLock for cross-terminal CKS write safety
try:
    import portalocker

    class FileLock:
        def __init__(self, lock_path, timeout=5.0):
            self.lock_path = Path(lock_path)
            self.timeout = timeout
            self.lock_file = None

        def __enter__(self):
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.lock_file = open(self.lock_path, "w")
                portalocker.lock(self.lock_file, portalocker.LOCK_EX)
            except Exception:
                return self
            return self

        def __exit__(self, *args):
            if self.lock_file:
                try:
                    self.lock_file.close()
                except Exception:
                    pass
except ImportError:

    class FileLock:
        def __init__(self, lock_path, timeout=5.0):
            self.lock_path = lock_path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass


def ingest_rca_to_cks(state):
    """Ingest RCA findings to CKS using cks_auto_extractor (direct Python, no subprocess)."""
    # Extract findings from state even if root_cause not explicitly set
    findings = extract_findings_from_state(state)
    if not findings.get("root_cause") and not findings.get("fix"):
        return {"stored": 0, "failed": 0, "reason": "no findings"}

    try:
        # Import from package first (self-contained)
        _hook_dir = Path(__file__).parent.parent.parent.parent / "src"
        if str(_hook_dir) not in sys.path:
            sys.path.insert(0, str(_hook_dir))
        from rca.cks_auto_extractor import extract_and_store_learning

        session_id = state.get("session_id", "unknown")
        problem_desc = findings.get("problem", "")
        root_cause = findings.get("root_cause", "")
        fix_applied = findings.get("fix", "")
        files_changed = findings.get("files", [])

        success = extract_and_store_learning(
            session_id=session_id,
            problem_description=problem_desc,
            root_cause=root_cause,
            fix_applied=fix_applied,
            files_changed=files_changed,
        )
        if success:
            return {"stored": 1, "failed": 0}
        return {"stored": 0, "failed": 1}

    except Exception as e:
        return {"stored": 0, "failed": 1, "error": str(e)}


def extract_findings_from_state(state: dict) -> dict:
    """Extract RCA findings from workflow state for automatic storage.

    This enables automatic lesson capture even when the user doesn't
    manually run `rca record`. It synthesizes findings from:
    - Completed phases
    - Tool usage patterns (files edited, errors encountered)
    - Hypothesis ledger (if populated)
    - Session friction points
    """
    findings = {
        "problem": "",
        "root_cause": "",
        "fix": "",
        "files": [],
    }

    # 1. Extract problem from session friction or debug evidence
    if state.get("session_friction"):
        friction_items = state.get("session_friction", [])[:3]
        findings["problem"] = "; ".join(friction_items)
    elif state.get("debug_evidence"):
        evidence = state.get("debug_evidence", [{}])[0]
        findings["problem"] = evidence.get("description", "")

    if not findings["problem"]:
        findings["problem"] = state.get("problem_preview", "RCA investigation")

    # 2. Extract root cause from explicit field or synthesize from phases
    if state.get("root_cause"):
        findings["root_cause"] = state["root_cause"]
    else:
        # Synthesize from completed phases
        phases_completed = state.get("phases_completed", [])
        if 3 in phases_completed:  # five_whys phase completed
            findings["root_cause"] = "Investigation completed via five_whys phase"
        elif 2 in phases_completed:  # hypothesis_ledger phase completed
            findings["root_cause"] = "Investigation completed via hypothesis_ledger phase"
        elif 1 in phases_completed:  # data_flow_trace phase completed
            findings["root_cause"] = "Investigation completed via data_flow_trace phase"

    # 3. Extract fix from confirmed hypotheses or tool usage
    confirmed_hypotheses = [
        h.get("hypothesis", "")
        for h in state.get("hypotheses", [])
        if isinstance(h, dict) and h.get("status") == "confirmed"
    ]
    if confirmed_hypotheses:
        findings["fix"] = "; ".join(confirmed_hypotheses)
    elif state.get("fix_applied"):
        findings["fix"] = state["fix_applied"]

    # 4. Extract files from tool usage (if available)
    # This would require parsing tool history - for now, empty list
    findings["files"] = state.get("files_changed", [])

    return findings


def cleanup_active_session(state: dict) -> None:
    """Remove stale or matching active session state."""
    if not ACTIVE_SESSION_FILE.exists():
        return
    try:
        active = json.loads(ACTIVE_SESSION_FILE.read_text(encoding="utf-8"))
        active_session_id = active.get("session_id")
        target_session_id = state.get("session_id")
        created_at = active.get("created_at")

        should_remove = False
        if target_session_id and active_session_id == target_session_id:
            should_remove = True
        elif created_at:
            age = datetime.now() - datetime.fromisoformat(created_at)
            if age > timedelta(hours=ACTIVE_SESSION_TTL_HOURS):
                should_remove = True

        if should_remove:
            ACTIVE_SESSION_FILE.unlink(missing_ok=True)
    except Exception:
        # Best-effort cleanup only.
        pass


@hook_main
def main():
    """Entry point - clean up RCA session state and ingest to CKS."""
    # Check if CKS ingestion is disabled
    cks_disabled = os.environ.get("CKS_STORAGE_DISABLED") == "1"

    # Archive RCA findings if workflow was active
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())

            # Create archive entry
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = ARCHIVE_DIR / f"rca_{timestamp}.json"

            # Add completion metadata
            state["session_ended_at"] = datetime.now().isoformat()
            state["archived_at"] = datetime.now().isoformat()

            # Write archive
            archive_file.write_text(json.dumps(state, indent=2))

            # CKS ingestion: automatic if findings exist
            already_recorded = state.get("outcome_recorded", False)

            # Extract findings even if root_cause not explicitly set
            extracted = extract_findings_from_state(state)
            has_findings = bool(extracted.get("root_cause") or extracted.get("fix"))

            if not cks_disabled and has_findings and not already_recorded:
                storage_results = ingest_rca_to_cks(state)
                state["cks_ingestion"] = storage_results
                state["extracted_findings"] = extracted

                # Update archive with ingestion results
                archive_file.write_text(json.dumps(state, indent=2))

                # Notify about automatic storage
                if storage_results.get("stored", 0) > 0:
                    print(
                        json.dumps(
                            {
                                "message": f"✅ RCA findings automatically stored to CKS ({extracted.get('problem', '')[:60]}...)"
                            }
                        )
                    )
                elif storage_results.get("failed", 0) > 0:
                    print(
                        json.dumps({"message": "⚠️ CKS storage failed - findings archived locally"})
                    )

            # Nudge via stdout if no findings were captured
            if not has_findings and not already_recorded:
                session_id = state.get("session_id", "unknown")
                print(
                    json.dumps(
                        {
                            "message": (
                                f"ℹ️ RCA session {session_id} archived without findings. "
                                "To close the learning loop, run: "
                                'rca record --outcome resolved --problem "..." '
                                '--root-cause "..." --fix "..."'
                            )
                        }
                    )
                )
                # Remove active state and exit early
                STATE_FILE.unlink()
                cleanup_active_session(state)
                sys.exit(0)

            # Remove active state
            STATE_FILE.unlink()
            cleanup_active_session(state)

        except (OSError, json.JSONDecodeError):
            pass

    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()
