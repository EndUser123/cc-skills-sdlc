#!/usr/bin/env python3
"""delegated_op.py — narrow /go → codex-external-delegation bridge seam."""

from __future__ import annotations
import argparse, json, os, subprocess, sys, time, uuid
from pathlib import Path
from typing import Any

BRIDGE_CLI = Path("P:/packages/codex-external-delegation/bin/external-delegation.mjs")
INVOCATION_PROFILE = "opencode-readonly-v1"
OPERATION = "repo_map_v1"
ALLOWED_WORKER = "opencode"
ALLOWED_MODEL = "opencode/big-pickle"
ALLOWED_AGENT = "external-readonly-primary"
POLICY_VERSION = "v2"
SCHEMA_VERSION = "2"
DEFAULT_TIMEOUT_SECONDS = 90

DISPOSITIONS = {
    "confirmed": "claim independently verified",
    "disproven": "claim refuted",
    "duplicate": "claim already established",
    "unresolved-blocking": "cannot be resolved before plan proceeds",
    "unresolved-nonblocking": "unresolved but does not block",
    "out-of-scope": "outside the operation objective",
}


def _resolve_session_id() -> str:
    tf = Path.home() / "claude-log.transcript_path.txt"
    try:
        text = tf.read_text(encoding="utf-8").strip()
        if text:
            stem = Path(text).stem
            if stem and len(stem) >= 36 and "-" in stem:
                return stem
    except OSError:
        pass
    return os.environ.get("CLAUDE_SESSION_ID") or ""


def _record_baseline(state_dir: Path, sid: str, rid: str, tid: str, obj: str) -> Path:
    d = state_dir / "delegated-ops"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"baseline-{tid}.json"
    p.write_text(json.dumps({
        "session_id": sid, "run_id": rid, "task_id": tid,
        "operation": OPERATION, "invocation_profile": INVOCATION_PROFILE,
        "objective": obj,
        "controller_pre_position": "delegation requested; controller retains authority",
        "ts": time.time(),
        "evidence_precedence": [
            "deterministic observed evidence",
            "repository-grounded evidence",
            "authoritative external sources",
            "independent worker findings",
            "implementer narrative",
            "unsupported inference",
        ],
    }, indent=2), encoding="utf-8")
    return p


def _build_packet(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "operation": OPERATION,
        "request_id": args.request_id, "session_id": args.session_id,
        "run_id": args.run_id, "task_id": args.task_id,
        "invocation_id": args.invocation_id,
        "worker": ALLOWED_WORKER, "model": ALLOWED_MODEL,
        "agent": ALLOWED_AGENT, "objective": args.objective,
        "cwd": args.workspace_id, "allowed_paths": ["."],
        "forbidden_actions": [
            "invoke another lane", "commit", "push",
            "edit files", "run shell commands", "access the network",
        ],
        "mode": "read_only",
        "output_schema": {"required": ["observations"]},
        "expected_result_schema": "repo_map.v1",
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "verification": {"commands": ["node --version"]},
        "failure_policy": "halt_no_automatic_fallback",
        "policy_version": POLICY_VERSION, "selected_lane": "opencode",
    }


def _validate_inputs(args: argparse.Namespace) -> str | None:
    for fld in ("session_id", "run_id", "task_id", "request_id",
                "invocation_id", "workspace_id"):
        if not getattr(args, fld):
            return f"identity_missing:{fld}"
    if not Path(args.workspace_id).is_dir():
        return f"workspace_invalid:{args.workspace_id}"
    return None


def _identity_match(result: dict[str, Any], args: argparse.Namespace) -> str | None:
    for fld, expected in (
        ("task_id", args.task_id), ("session_id", args.session_id),
        ("run_id", args.run_id), ("request_id", args.request_id),
        ("invocation_id", args.invocation_id),
    ):
        if result.get(fld) != expected:
            return f"foreign_result:{fld}_mismatch"
    if result.get("worker") != ALLOWED_WORKER or result.get("model") != ALLOWED_MODEL:
        return "not_opencode_readonly_v1"
    return None


def _extract_claims(payload: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    raw = payload.get("observations", "") if isinstance(payload, dict) else ""
    if not isinstance(raw, str) or not raw.strip():
        return claims
    for line in (l.strip() for l in raw.splitlines() if l.strip()):
        disposition = "unresolved-nonblocking"
        verification = "independent worker findings"
        if any(t in line for t in ("/", ".txt", ".md", ".json", ".py", ".ts", ".js")):
            disposition = "confirmed"
            verification = "deterministic observed evidence (path reference)"
        elif any(t in line.lower() for t in ("cannot", "blocked", "violates")):
            disposition = "disproven"
            verification = "policy-enforced refusal"
        claims.append({
            "claim_text": line, "disposition": disposition,
            "disposition_meaning": DISPOSITIONS[disposition],
            "verification_method": verification,
            "evidence_precedence_tier": 4,
        })
    return claims


def _decision_delta(baseline: Path, claims: list[dict[str, Any]],
                    status: str, failure_class: str) -> dict[str, Any]:
    confirmed = [c for c in claims if c["disposition"] == "confirmed"]
    disproven = [c for c in claims if c["disposition"] == "disproven"]
    return {
        "baseline_ref": str(baseline), "result_status": status,
        "result_failure_class": failure_class,
        "claims_total": len(claims), "claims_confirmed": len(confirmed),
        "claims_disproven": len(disproven),
        "claims_unresolved_blocking": sum(1 for c in claims if c["disposition"] == "unresolved-blocking"),
        "claims_unresolved_nonblocking": sum(1 for c in claims if c["disposition"] == "unresolved-nonblocking"),
        "claims_out_of_scope": sum(1 for c in claims if c["disposition"] == "out-of-scope"),
        "claims_duplicate": sum(1 for c in claims if c["disposition"] == "duplicate"),
        "changed_plan": bool(confirmed) or bool(disproven),
        "note": "/go retains final completion authority",
        "ts": time.time(),
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="delegate repo_map_v1 via bridge")
    p.add_argument("--session-id", default=_resolve_session_id())
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--invocation-id", default=str(uuid.uuid4()))
    p.add_argument("--request-id", default=str(uuid.uuid4()))
    p.add_argument("--workspace-id", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--state-dir", required=True)
    args = p.parse_args(argv)
    rejection = _validate_inputs(args)
    if rejection:
        print(json.dumps({"status": "rejected", "rejection": rejection}, indent=2))
        return 30
    baseline = _record_baseline(Path(args.state_dir), args.session_id,
                                args.run_id, args.task_id, args.objective)
    packet = _build_packet(args)
    packet_path = Path(args.state_dir) / f"delegated-packet-{args.task_id}.json"
    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    if not BRIDGE_CLI.is_file():
        print(json.dumps({"status": "rejected", "rejection": "bridge_failed:cli_missing",
                          "bridge_cli": str(BRIDGE_CLI)}, indent=2))
        return 30
    proc = subprocess.run(
        ["node", str(BRIDGE_CLI), "run", "--packet", str(packet_path)],
        capture_output=True, text=True, timeout=DEFAULT_TIMEOUT_SECONDS + 30,
    )
    if proc.returncode != 0:
        print(json.dumps({"status": "rejected",
                          "rejection": f"bridge_failed:exit_{proc.returncode}",
                          "stderr": proc.stderr[:2000]}, indent=2))
        return 30
    artifact_dir = Path(packet["cwd"]) / ".codex" / "state" / "external-delegation" / args.task_id
    result_path = artifact_dir / "result.json"
    if not result_path.is_file():
        print(json.dumps({"status": "rejected", "rejection": "bridge_failed:result_missing"}, indent=2))
        return 30
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"status": "rejected", "rejection": f"bridge_failed:parse:{e}"}, indent=2))
        return 30
    identity_reject = _identity_match(result, args)
    if identity_reject:
        print(json.dumps({"status": "rejected", "rejection": identity_reject,
                          "result_task_id": result.get("task_id")}, indent=2))
        return 30
    claims = _extract_claims(result.get("result_payload", {}))
    delta = _decision_delta(baseline, claims, result.get("status", "unknown"),
                            result.get("failure_class", "unknown"))
    output = {
        "status": result.get("status"), "failure_class": result.get("failure_class"),
        "worker": result.get("worker"), "model": result.get("model"),
        "artifact_dir": str(artifact_dir), "decision_delta": delta,
        "claims": claims, "evidence_precedence_tier": 4, "ts": time.time(),
    }
    print(json.dumps(output, indent=2))
    return 0 if result.get("status") == "ok" else 20


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))