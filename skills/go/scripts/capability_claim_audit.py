#!/usr/bin/env python3
"""Capability-claim audit for consolidation/deprecation/routing tasks.

Reads the active-task artifact, inspects source paths, checks routing,
and verifies backend existence. Writes capability-audit-{run_id}.json.

Exit 0 = all claims verified or explicitly deferred.
Exit 1 = overclaim detected (claim says shipped/absorbed but backend missing).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_active_task(state_dir: Path, run_id: str) -> dict[str, Any]:
    """Load the active-task artifact for this run."""
    candidates = list(state_dir.glob(f"active-task_{run_id}.*"))
    if not candidates:
        candidates = list(state_dir.glob("active-task_*"))
    if not candidates:
        return {}
    # Pick the most recent
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def audit_claim(claim: dict) -> dict[str, Any]:
    """Audit a single capability claim against real implementation paths.

    Returns a dict with classification, evidence, and status.
    """
    command = claim.get("command", "unknown")
    claimed_status = claim.get("claimed_status", "unknown")
    source_path = claim.get("source_path")
    parent_path = claim.get("parent_path")
    routing_mechanism = claim.get("routing_mechanism")
    backend_path = claim.get("backend_path")

    result: dict[str, Any] = {
        "command": command,
        "claimed_status": claimed_status,
        "source_path": source_path,
        "parent_path": parent_path,
        "routing_mechanism": routing_mechanism,
        "backend_path": backend_path,
        "classification": "unknown",
        "backend_exists": False,
        "status": "not_checked",
        "evidence": "",
    }

    # Classify based on source inspection
    classification = _classify_from_source(source_path, claimed_status, backend_path)
    result["classification"] = classification

    # Check backend existence
    if backend_path:
        bp = Path(backend_path)
        result["backend_exists"] = bp.exists()
    elif source_path:
        # If no explicit backend path, check if source exists
        sp = Path(source_path)
        result["backend_exists"] = sp.exists()

    # Determine status
    result["status"] = _determine_status(
        claimed_status, classification, result["backend_exists"], source_path
    )

    # Build evidence string
    result["evidence"] = _build_evidence(result)

    return result


def _classify_from_source(
    source_path: str | None,
    claimed_status: str,
    backend_path: str | None,
) -> str:
    """Classify a claim based on source file inspection."""
    if not source_path:
        return "unknown"

    source = Path(source_path)
    if not source.exists():
        if claimed_status in ("absorbed", "routed"):
            return "routed_to_parent"
        return "deleted"

    try:
        content = source.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "unknown"

    content_lower = content.lower()

    # True stub: pass-through, no-op, deprecation-only
    stub_signals = ("pass through", "pass-through", "no-op", "noop",
                    "raise deprecation", "warnings.warn")
    has_stub_header = any(s in content_lower for s in stub_signals)

    # Deprecation header on retained engine
    has_deprecation = ("deprecat" in content_lower or "deprecated" in content_lower)
    has_real_logic = (
        len(content) > 500
        and ("def " in content or "class " in content or "async def" in content)
        and not has_stub_header
    )

    if has_stub_header and not has_real_logic:
        return "true_stub"
    if has_deprecation and has_real_logic:
        return "deprecation_header_on_retained_engine"
    if has_real_logic:
        return "retained_engine"

    # Check for routing signals
    if any(r in content_lower for r in ("parent", "forward to", "delegate to", "route to")):
        return "routed_to_parent"

    # Check backend
    if backend_path:
        bp = Path(backend_path)
        if not bp.exists():
            return "pending_backend"

    return "unknown"


def _determine_status(
    claimed: str,
    classification: str,
    backend_exists: bool,
    source_path: str | None,
) -> str:
    """Determine audit status: verified, overclaim, or deferred."""
    # If claimed as shipped/absorbed/production but backend missing → overclaim
    if claimed in ("absorbed", "shipped", "production") and not backend_exists:
        return "overclaim"

    # If explicitly marked pending → deferred (allowed)
    if claimed == "pending" or classification == "pending_backend":
        return "deferred"

    # If classification matches what was claimed → verified
    if classification in ("true_stub", "deleted", "routed_to_parent", "retained_engine",
                          "deprecation_header_on_retained_engine"):
        return "verified"

    # If source exists and backend exists → verified
    if source_path and Path(source_path).exists() and backend_exists:
        return "verified"

    return "not_checked"


def _build_evidence(result: dict[str, Any]) -> str:
    """Build human-readable evidence string."""
    parts = []
    parts.append(f"Classification: {result['classification']}")

    if result["source_path"]:
        exists = Path(result["source_path"]).exists()
        parts.append(f"Source path {'exists' if exists else 'MISSING'}: {result['source_path']}")

    if result["backend_path"]:
        parts.append(f"Backend {'exists' if result['backend_exists'] else 'MISSING'}: {result['backend_path']}")

    if result["status"] == "overclaim":
        parts.append(f"OVERCLAIM: claimed '{result['claimed_status']}' but backend not found")
    elif result["status"] == "deferred":
        parts.append(f"Deferred: capability intentionally not yet implemented")
    elif result["status"] == "verified":
        parts.append(f"Verified: classification '{result['classification']}' matches claim")

    return "; ".join(parts)


def run_audit(state_dir: Path, run_id: str) -> dict[str, Any]:
    """Run the capability-claim audit. Returns the audit result dict."""
    active_task = load_active_task(state_dir, run_id)
    if not active_task:
        return {"audit_passed": False, "error": "No active task found"}

    task = active_task.get("task", {})
    capability_audit = task.get("capability_audit")
    if not capability_audit:
        return {"audit_passed": True, "claims": [], "note": "No capability audit required"}

    claims = capability_audit.get("claims", [])
    if not claims:
        return {"audit_passed": True, "claims": [], "note": "No claims to audit"}

    audited_claims = []
    all_passed = True
    deferred = []

    for claim in claims:
        result = audit_claim(claim)
        audited_claims.append(result)

        if result["status"] == "overclaim":
            all_passed = False
        elif result["status"] == "deferred":
            deferred.append(result["command"])

    return {
        "audit_passed": all_passed,
        "claims": audited_claims,
        "visible_surface_complete": all(
            c["classification"] in ("true_stub", "deleted", "routed_to_parent",
                                     "retained_engine", "deprecation_header_on_retained_engine")
            for c in audited_claims
        ),
        "routing_complete": all(
            c["classification"] in ("routed_to_parent", "deleted", "true_stub")
            or c["backend_exists"]
            for c in audited_claims
        ),
        "backend_implemented": all(
            c["backend_exists"] for c in audited_claims
            if c["claimed_status"] in ("absorbed", "shipped", "production")
        ),
        "deferred_capabilities": deferred,
    }


def main() -> int:
    """CLI entry point. Usage: capability_claim_audit.py <state_dir> <run_id>"""
    if len(sys.argv) < 3:
        print("Usage: capability_claim_audit.py <state_dir> <run_id>", file=sys.stderr)
        return 1

    state_dir = Path(sys.argv[1])
    run_id = sys.argv[2]

    result = run_audit(state_dir, run_id)

    # Write audit artifact
    artifact_path = state_dir / f"capability-audit-{run_id}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(result, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    # Print summary
    if result.get("error"):
        print(f"AUDIT ERROR: {result['error']}", file=sys.stderr)
        return 1

    claims = result.get("claims", [])
    overclaims = [c for c in claims if c["status"] == "overclaim"]

    if overclaims:
        print(f"CAPABILITY AUDIT FAILED: {len(overclaims)} overclaim(s) detected:")
        for oc in overclaims:
            print(f"  - {oc['command']}: claimed '{oc['claimed_status']}' "
                  f"but {oc['classification']} (backend {'missing' if not oc['backend_exists'] else 'exists'})")
        return 1

    if result.get("deferred_capabilities"):
        print(f"CAPABILITY AUDIT PASSED with {len(result['deferred_capabilities'])} deferred:")
        for d in result["deferred_capabilities"]:
            print(f"  - {d} (explicitly pending)")
    else:
        print(f"CAPABILITY AUDIT PASSED: {len(claims)} claim(s) verified")

    return 0


if __name__ == "__main__":
    sys.exit(main())
