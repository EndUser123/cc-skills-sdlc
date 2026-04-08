from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

# DEPTH RULE: When skills/ layer is added, increment parents[N] by 1.
_ROOT = Path(__file__).resolve()
_CONTRACT_PRIMITIVES_CANDIDATES = [
    _ROOT.parents[3] / "contract-primitives" / "src",
    Path(_ROOT.anchor) / "packages" / "sdlc" / "contract-primitives" / "src",
]
for _candidate in _CONTRACT_PRIMITIVES_CANDIDATES:
    if _candidate.exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from contract_primitives import parse_contract_authority_packet, parse_planning_handoff_packet

_DEFAULT_STATE_DIR = Path(__file__).resolve().parents[1] / ".claude" / "state" / "arch_handoff"
_DEFAULT_RECEIPT_TTL_SECONDS = 20 * 60


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def get_terminal_id() -> str:
    return os.environ.get("CLAUDE_TERMINAL_ID", "default")


def get_session_id() -> str:
    return os.environ.get("CLAUDE_SESSION_ID", "default")


def get_state_dir() -> Path:
    configured = os.environ.get("PLANNING_ARCH_HANDOFF_STATE_DIR")
    if configured:
        return Path(configured)
    return _DEFAULT_STATE_DIR


def get_terminal_state_dir(terminal_id: str | None = None) -> Path:
    terminal = terminal_id or get_terminal_id()
    return get_state_dir() / terminal


def get_staging_dir(terminal_id: str | None = None) -> Path:
    terminal = terminal_id or get_terminal_id()
    return get_state_dir() / ".staging" / terminal


def get_receipt_ttl_seconds() -> int:
    raw_value = os.environ.get("PLANNING_ARCH_HANDOFF_TTL_SECONDS")
    if not raw_value:
        return _DEFAULT_RECEIPT_TTL_SECONDS
    try:
        return max(int(raw_value), 0)
    except ValueError:
        return _DEFAULT_RECEIPT_TTL_SECONDS


def normalize_path(path: str) -> str:
    normalized = str(Path(path)).replace("\\", "/")
    return normalized.lower() if os.name == "nt" else normalized


def plan_sha256(plan_path: str) -> str | None:
    path = Path(plan_path)
    if not path.exists():
        return None
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _plan_key(plan_path: str) -> str:
    return hashlib.sha256(normalize_path(plan_path).encode("utf-8")).hexdigest()[:16]


def _legacy_receipt_filename(plan_path: str, terminal_id: str) -> Path:
    key = hashlib.sha256(f"{normalize_path(plan_path)}::{terminal_id}".encode("utf-8")).hexdigest()[:16]
    return get_state_dir() / f"{terminal_id}_{key}.json"


def _receipt_filename(plan_path: str, terminal_id: str, snapshot_id: str) -> Path:
    return get_terminal_state_dir(terminal_id) / f"arch_handoff_{_plan_key(plan_path)}_{snapshot_id}.json"


def _receipt_glob(plan_path: str) -> str:
    return f"arch_handoff_{_plan_key(plan_path)}_*.json"


def _serialize_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def _compute_checksum(data: dict[str, Any]) -> str:
    serializable = {k: v for k, v in data.items() if k != "checksum"}
    digest = hashlib.sha256(_serialize_json(serializable).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _write_json_atomic(path: Path, data: dict[str, Any], terminal_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = get_staging_dir(terminal_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    temp_path = staging_dir / f"{path.name}.{uuid4().hex}.tmp"
    payload = _serialize_json(data)
    try:
        temp_path.write_text(payload, encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_expired(snapshot: dict[str, Any]) -> bool:
    expires_at = _parse_iso_datetime(snapshot.get("expires_at"))
    if expires_at is None:
        return False
    return expires_at <= _utc_now()


def _extract_resume_snapshot(envelope: dict[str, Any]) -> dict[str, Any]:
    snapshot = envelope.get("resume_snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def _extract_receipt_body(envelope: dict[str, Any]) -> dict[str, Any]:
    receipt = envelope.get("arch_handoff_receipt")
    return receipt if isinstance(receipt, dict) else {}


def _flatten_envelope(envelope: dict[str, Any], receipt_path: Path) -> dict[str, Any]:
    snapshot = _extract_resume_snapshot(envelope)
    receipt = dict(_extract_receipt_body(envelope))
    receipt["receipt_path"] = str(receipt_path)
    receipt["snapshot_id"] = snapshot.get("snapshot_id")
    receipt["expires_at"] = snapshot.get("expires_at")
    receipt["terminal_id"] = snapshot.get("terminal_id") or receipt.get("terminal_id")
    receipt["session_id"] = snapshot.get("source_session_id") or receipt.get("session_id")
    receipt["resume_snapshot_status"] = snapshot.get("status")
    receipt["checksum"] = envelope.get("checksum")
    receipt["checksum_valid"] = True
    receipt["expired"] = _is_expired(snapshot)
    receipt["storage_format"] = "envelope"
    return receipt


def _flatten_legacy_receipt(receipt: dict[str, Any], receipt_path: Path) -> dict[str, Any]:
    flattened = dict(receipt)
    flattened["receipt_path"] = str(receipt_path)
    flattened["checksum_valid"] = None
    flattened["expired"] = False
    flattened["storage_format"] = "legacy"
    return flattened


def _read_receipt_payload(receipt_path: Path) -> tuple[dict[str, Any], str] | None:
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(payload, dict):
        return None

    if "resume_snapshot" in payload and "arch_handoff_receipt" in payload:
        if payload.get("checksum") != _compute_checksum(payload):
            return None
        return payload, "envelope"

    if "receipt_version" in payload:
        return payload, "legacy"

    return None


def _candidate_receipt_paths(plan_path: str, terminal_id: str) -> list[Path]:
    candidates: list[Path] = []
    terminal_dir = get_terminal_state_dir(terminal_id)
    if terminal_dir.exists():
        try:
            candidates.extend(terminal_dir.glob(_receipt_glob(plan_path)))
        except OSError:
            pass

    legacy_path = _legacy_receipt_filename(plan_path, terminal_id)
    if legacy_path.exists():
        candidates.append(legacy_path)

    return sorted(
        candidates,
        key=lambda candidate: candidate.stat().st_mtime if candidate.exists() else 0.0,
        reverse=True,
    )


def _load_latest_matching_receipt(
    plan_path: str,
    terminal_id: str,
) -> tuple[dict[str, Any], Path] | None:
    normalized_plan_path = normalize_path(plan_path)
    for receipt_path in _candidate_receipt_paths(plan_path, terminal_id):
        loaded = _read_receipt_payload(receipt_path)
        if loaded is None:
            continue
        payload, payload_kind = loaded
        if payload_kind == "envelope":
            receipt = _flatten_envelope(payload, receipt_path)
        else:
            receipt = _flatten_legacy_receipt(payload, receipt_path)

        if normalize_path(receipt.get("plan_path", plan_path)) != normalized_plan_path:
            continue
        return receipt, receipt_path

    return None


def _extract_resume_metadata(arch_output: str) -> tuple[str | None, str | None]:
    return_to_caller = None
    resume_policy = None

    caller_match = re.search(r"^RETURN TO CALLER:\s*(.+)$", arch_output, re.MULTILINE)
    if caller_match:
        return_to_caller = caller_match.group(1).strip()

    policy_match = re.search(r"^Resume policy:\s*(.+)$", arch_output, re.MULTILINE | re.IGNORECASE)
    if policy_match:
        resume_policy = policy_match.group(1).strip()

    return return_to_caller, resume_policy


def record_arch_handoff_receipt(
    plan_path: str,
    arch_output: str,
    *,
    blocker_ids: list[str] | None = None,
    terminal_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    handoff = parse_planning_handoff_packet(arch_output)
    contract = parse_contract_authority_packet(arch_output)
    if not handoff.packet_version and not contract.packet_version:
        raise ValueError("arch_output did not contain a parseable planning or contract packet")

    terminal = terminal_id or get_terminal_id()
    session = session_id or get_session_id()
    snapshot_id = str(uuid4())
    receipt_path = _receipt_filename(plan_path, terminal, snapshot_id)
    return_to_caller, resume_policy = _extract_resume_metadata(arch_output)
    now = _utc_now()
    now_iso = now.isoformat()
    expires_at = (now + timedelta(seconds=get_receipt_ttl_seconds())).isoformat()
    normalized_plan_path = str(Path(plan_path))
    receipt = {
        "receipt_version": 2,
        "status": "pending_consumption",
        "created_at": now_iso,
        "updated_at": now_iso,
        "plan_path": normalized_plan_path,
        "plan_path_normalized": normalize_path(plan_path),
        "plan_sha256": plan_sha256(plan_path),
        "planning_handoff_packet_version": handoff.packet_version,
        "contract_authority_packet_version": contract.packet_version,
        "source_adr": handoff.source_adr,
        "plan_title": handoff.plan_title,
        "goal": handoff.goal,
        "implementation_task_ids": handoff.implementation_task_ids,
        "contract_sensitive": handoff.contract_sensitive,
        "open_questions": handoff.open_questions,
        "boundary_ids": sorted(contract.boundaries.keys()),
        "arch_blocker_ids": sorted(set(blocker_ids or [])),
        "return_to_caller": return_to_caller,
        "resume_policy": resume_policy,
    }
    envelope = {
        "resume_snapshot": {
            "schema_version": 2,
            "snapshot_id": snapshot_id,
            "terminal_id": terminal,
            "source_session_id": session,
            "created_at": now_iso,
            "expires_at": expires_at,
            "status": "pending",
            "goal": handoff.goal or handoff.plan_title or "Consume /arch packet",
            "current_task": "Consume the /arch packet and rewrite the plan locally.",
            "progress_percent": 75,
            "progress_state": "awaiting_local_rewrite",
            "blockers": sorted(set(blocker_ids or [])),
            "active_files": [
                item
                for item in [normalized_plan_path, handoff.source_adr]
                if item
            ],
            "pending_operations": [
                {"type": "rewrite", "target": normalized_plan_path, "state": "pending"},
                {"type": "verify", "target": normalized_plan_path, "state": "pending"},
            ],
            "next_step": "Consume the /arch packet, rewrite the plan locally, and rerun auto_verify.",
            "decision_refs": [],
            "evidence_refs": [],
            "message_intent": "handoff",
            "quality_score": 1.0,
            "tasks_snapshot": handoff.implementation_task_ids,
        },
        "arch_handoff_receipt": receipt,
    }
    envelope["checksum"] = _compute_checksum(envelope)
    _write_json_atomic(receipt_path, envelope, terminal)
    return _flatten_envelope(envelope, receipt_path)


def load_arch_handoff_receipt(
    plan_path: str,
    *,
    terminal_id: str | None = None,
) -> dict[str, Any] | None:
    terminal = terminal_id or get_terminal_id()
    loaded = _load_latest_matching_receipt(plan_path, terminal)
    if loaded is None:
        return None
    receipt, _ = loaded
    return receipt


def find_pending_arch_handoff_receipt(
    plan_path: str,
    *,
    arch_blocker_ids: list[str] | None = None,
    terminal_id: str | None = None,
    current_plan_sha256: str | None = None,
) -> dict[str, Any] | None:
    expected_ids = sorted(set(str(item) for item in (arch_blocker_ids or [])))
    terminal = terminal_id or get_terminal_id()
    normalized_plan_path = normalize_path(plan_path)

    for receipt_path in _candidate_receipt_paths(plan_path, terminal):
        loaded = _read_receipt_payload(receipt_path)
        if loaded is None:
            continue

        payload, payload_kind = loaded
        receipt = (
            _flatten_envelope(payload, receipt_path)
            if payload_kind == "envelope"
            else _flatten_legacy_receipt(payload, receipt_path)
        )
        if normalize_path(receipt.get("plan_path", plan_path)) != normalized_plan_path:
            continue
        if receipt.get("status") != "pending_consumption":
            continue
        if receipt.get("expired"):
            continue

        recorded_ids = sorted(set(str(item) for item in receipt.get("arch_blocker_ids", [])))
        if expected_ids and recorded_ids and expected_ids != recorded_ids:
            continue

        if current_plan_sha256:
            recorded_sha256 = receipt.get("plan_sha256")
            if recorded_sha256 and recorded_sha256 != current_plan_sha256:
                continue

        return receipt

    return None


def mark_arch_handoff_consumed(
    plan_path: str,
    *,
    terminal_id: str | None = None,
    rewritten_plan_sha256: str | None = None,
) -> dict[str, Any] | None:
    receipt = load_arch_handoff_receipt(plan_path, terminal_id=terminal_id)
    if not receipt or receipt.get("status") == "consumed":
        return receipt

    receipt_path = Path(receipt["receipt_path"])
    terminal = terminal_id or str(receipt.get("terminal_id") or get_terminal_id())
    loaded = _read_receipt_payload(receipt_path)
    if loaded is None:
        return None

    payload, payload_kind = loaded
    now_iso = _utc_now_iso()

    if payload_kind == "legacy":
        payload["status"] = "consumed"
        payload["updated_at"] = now_iso
        payload["consumed_at"] = now_iso
        if rewritten_plan_sha256:
            payload["consumed_by_plan_sha256"] = rewritten_plan_sha256
        _write_json_atomic(receipt_path, payload, terminal)
        return _flatten_legacy_receipt(payload, receipt_path)

    snapshot = _extract_resume_snapshot(payload)
    receipt_body = _extract_receipt_body(payload)
    receipt_body["status"] = "consumed"
    receipt_body["updated_at"] = now_iso
    receipt_body["consumed_at"] = now_iso
    if rewritten_plan_sha256:
        receipt_body["consumed_by_plan_sha256"] = rewritten_plan_sha256

    snapshot["status"] = "consumed"
    snapshot["progress_percent"] = 100
    snapshot["progress_state"] = "completed"
    snapshot["current_task"] = "Arch handoff receipt consumed."
    snapshot["next_step"] = "None."
    payload["checksum"] = _compute_checksum(payload)
    _write_json_atomic(receipt_path, payload, terminal)
    return _flatten_envelope(payload, receipt_path)
