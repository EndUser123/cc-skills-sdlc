"""SQA Layer State Tracker.

Tracks which layers ran, what findings were produced, and where halt was triggered.
State is written after each layer completion and read by the Stop hook gate.

State file format:
{
  "target": "P:/path/to/target",
  "session_id": "uuid",
  "halt_on": "HIGH",
  "layers": {
    "L0": {"ran": false, "skipped": true, "reason": "fast-path"},
    "L1": {"ran": true, "findings": 5, "halt_triggered": false},
    "L2": {"ran": true, "findings": 0, "halt_triggered": false},
    ...
  },
  "halt_triggered_at": null,
  "final_layer_completed": "L2"
}
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from filelock import FileLock
except ImportError:
    FileLock = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


STATE_DIR = Path.home() / ".claude" / "sqa_state"
HALT_FLAG_PATH = STATE_DIR / "halt_triggered.json"


@dataclass
class LayerState:
    ran: bool = False
    skipped: bool = False
    reason: str | None = None
    findings: int = 0
    halt_triggered: bool = False


@dataclass
class SQAState:
    target: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    halt_on: str = "HIGH"
    layers: dict[str, LayerState] = field(default_factory=dict)
    halt_triggered_at: str | None = None
    final_layer_completed: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Accumulated findings from all layers (for RNS presentation on halt/completion)
    accumulated_findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SQAState:
        layers = {}
        for name, state in data.get("layers", {}).items():
            layers[name] = LayerState(**state)
        return cls(
            target=data["target"],
            session_id=data.get("session_id", str(uuid.uuid4())[:8]),
            halt_on=data.get("halt_on", "HIGH"),
            layers=layers,
            halt_triggered_at=data.get("halt_triggered_at"),
            final_layer_completed=data.get("final_layer_completed"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


def get_sanitized_terminal_id() -> str:
    """Get sanitized terminal ID from environment.

    Returns sanitized terminal ID (alphanumeric, underscore, hyphen only).
    Falls back to "default" if no terminal ID is set or if sanitization produces empty string.
    """
    raw_id = os.environ.get("CLAUDE_TERMINAL_ID", os.environ.get("TERMINAL_ID", "default"))
    import re
    terminal_id = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id) or "default"
    # Add length limit to prevent filesystem issues
    return terminal_id[:64]


def _get_state_path(session_id: str | None = None) -> Path:
    """Get path for state file. Uses TERMINAL_ID for isolation."""
    terminal_id = get_sanitized_terminal_id()
    state_dir = STATE_DIR / f"terminal_{terminal_id}"
    state_dir.mkdir(parents=True, exist_ok=True)
    if session_id:
        return state_dir / f"sqa_state_{session_id}.json"
    return state_dir / "sqa_state_current.json"


def _write_halt_flag(layer: str, findings_count: int) -> None:
    """Write halt flag to disk - cannot be bypassed by exception catching.

    This is a fail-safe mechanism. Even if HaltExceededThreshold exception
    is caught and suppressed, the flag on disk prevents further layer execution.
    """
    halt_flag = {
        "halted": True,
        "layer": layer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "finding_count": findings_count,
    }
    HALT_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    HALT_FLAG_PATH.write_text(json.dumps(halt_flag, indent=2))
    # Set restrictive permissions
    os.chmod(HALT_FLAG_PATH, 0o600)
    logger.info(f"Halt flag written to {HALT_FLAG_PATH} for layer {layer}")


def is_halted() -> bool:
    """Check if halt was triggered - used by layers before execution.

    Returns True if halt flag exists on disk, regardless of exception state.
    This prevents bypass via exception suppression.
    """
    if HALT_FLAG_PATH.exists():
        try:
            data = json.loads(HALT_FLAG_PATH.read_text())
            if data.get("halted", False):
                logger.warning(
                    f"Halt flag detected from layer {data.get('layer')} - execution blocked"
                )
                return True
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read halt flag: {e}")
    return False


def clear_halt_flag() -> None:
    """Clear halt flag - used when starting a new SQA run.

    Should be called at the start of each new SQA session to ensure
    stale halt flags from previous runs don't block execution.
    """
    if HALT_FLAG_PATH.exists():
        HALT_FLAG_PATH.unlink()
        logger.info("Halt flag cleared")


def init_state(target: str, halt_on: str = "HIGH") -> SQAState:
    """Initialize a new SQA state for a session.

    Clears any stale halt flag from previous runs.
    """
    # Clear stale halt flag from previous runs
    clear_halt_flag()

    state = SQAState(
        target=target,
        halt_on=halt_on,
        layers={
            f"L{i}": LayerState() for i in range(8)
        } | {"META": LayerState()},
    )
    _write_state(state)
    return state


def record_layer_complete(
    layer: str,
    findings: int = 0,
    skipped: bool = False,
    reason: str | None = None,
) -> SQAState:
    """Record that a layer completed."""
    state = load_state()
    if state is None:
        return state

    if layer in state.layers:
        state.layers[layer].ran = True
        state.layers[layer].skipped = skipped
        state.layers[layer].reason = reason
        state.layers[layer].findings = findings

    state.final_layer_completed = layer
    _write_state(state)
    return state


def record_halt(layer: str) -> SQAState:
    """Record that halt was triggered at a layer."""
    state = load_state()
    if state is None:
        return state

    if layer in state.layers:
        state.layers[layer].halt_triggered = True
    state.halt_triggered_at = layer
    _write_state(state)
    return state


def load_state(session_id: str | None = None) -> SQAState | None:
    """Load current SQA state. Returns None if file missing or corrupt."""
    path = _get_state_path(session_id)
    try:
        data = json.loads(path.read_text())
        return SQAState.from_dict(data)
    except FileNotFoundError:
        # File doesn't exist — not an error, just no state
        return None
    except (json.JSONDecodeError, KeyError, TypeError, OSError) as e:
        # State file is corrupt or unreadable — log before returning None
        logger.warning(f"Failed to load state from {path}: {e}")
        return None


def _write_state(state: SQAState) -> None:
    """Write state to disk atomically with retry on lock contention.

    Implements exponential backoff retry (3 attempts: 1s, 2s, 4s) before giving up.
    Sets restrictive file permissions (0o600) on state file.
    """
    import time

    path = _get_state_path(state.session_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2))

    # Set restrictive permissions before atomic replace
    os.chmod(tmp, 0o600)

    if FileLock is not None:
        lock_path = path.with_suffix(".lock")
        max_retries = 3
        base_timeout = 1

        for attempt in range(max_retries):
            try:
                timeout = base_timeout * (2 ** attempt)  # 1s, 2s, 4s
                lock = FileLock(lock_path, timeout=timeout)
                with lock:
                    os.replace(str(tmp), str(path))
                    # Ensure final file has correct permissions
                    os.chmod(path, 0o600)
                    return  # Success
            except Exception as e:
                if attempt == max_retries - 1:
                    # Final attempt failed - escalate
                    logger.error(
                        f"Failed to acquire lock for {path} after {max_retries} attempts. "
                        f"Another terminal may be running SQA concurrently. "
                        f"State update NOT written. Error: {e}"
                    )
                    raise IOError(
                        f"Concurrent SQA execution detected. "
                        f"Cannot update state file - another terminal holds the lock. "
                        f"Run SQA sequentially or use different terminal IDs."
                    ) from e
                logger.warning(f"Lock attempt {attempt + 1} failed, retrying...")
                time.sleep(0.1 * (2 ** attempt))
    else:
        # No filelock available: proceed without locking (best effort)
        os.replace(str(tmp), str(path))
        os.chmod(path, 0o600)


def clear_state(session_id: str | None = None) -> None:
    """Clear state file."""
    path = _get_state_path(session_id)
    if path.exists():
        path.unlink()


def add_findings(layer: str, findings: list[dict]) -> SQAState:
    """Add findings from a layer to the accumulated findings list.

    Each finding dict should contain at minimum:
    - "finding_id": str
    - "severity": str (CRITICAL, BLOCKER, HIGH, MEDIUM, LOW)
    - "category": str
    - "location": str (file:line or similar)
    - "title": str
    - "description": str
    - "recommendation": str
    - "source_layer": str
    """
    state = load_state()
    if state is None:
        return state

    # Add source_layer to each finding if not present
    for finding in findings:
        if "source_layer" not in finding:
            finding["source_layer"] = layer

    state.accumulated_findings.extend(findings)
    _write_state(state)
    return state


def get_accumulated_findings(session_id: str | None = None) -> list[dict]:
    """Get all accumulated findings from all completed layers."""
    state = load_state(session_id)
    if state is None:
        return []
    return state.accumulated_findings.copy()


def get_rns_summary(session_id: str | None = None) -> dict:
    """Get summary of accumulated findings grouped for RNS presentation.

    Returns dict with domain-grouped findings and metadata.
    """
    findings = get_accumulated_findings(session_id)

    # Group by domain (derived from category)
    domain_mapping = {
        "security": "🔒",
        "performance": "⚡",
        "quality": "🔧",
        "testing": "🧪",
        "docs": "📄",
        "logic": "🔧",
        "state_machine": "🔧",
        "io_validation": "🔧",
        "failure_modes": "🔧",
        "qa": "🧪",
    }

    grouped: dict[str, list[dict]] = {}
    for f in findings:
        category = f.get("category", "other")
        domain = _category_to_domain(category)
        if domain not in grouped:
            grouped[domain] = []
        grouped[domain].append(f)

    # Count severities
    severity_counts = {"CRITICAL": 0, "BLOCKER": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f.get("severity", "LOW").upper()
        if sev in severity_counts:
            severity_counts[sev] += 1

    return {
        "grouped": grouped,
        "domain_mapping": domain_mapping,
        "severity_counts": severity_counts,
        "total": len(findings),
    }


def _category_to_domain(category: str) -> str:
    """Map finding category to RNS domain."""
    category_lower = category.lower()

    if "security" in category_lower:
        return "security"
    elif "perf" in category_lower:
        return "performance"
    elif any(x in category_lower for x in ["test", "qa"]):
        return "testing"
    elif "doc" in category_lower:
        return "docs"
    else:
        return "quality"
