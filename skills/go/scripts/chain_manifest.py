"""Persistent chain-state manifest for skill-chaining dispatcher.

Schema: skill-chain.v1
Storage: P:/.artifacts/skill-chains/{chain_id}.json

Follows the go_continuation_gate.py pointer-file pattern for
persistent state tracking across context compaction boundaries.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "skill-chain.v1"
CHAIN_STEPS_DIR = "P:/.artifacts/skill-chains"
SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
UUID_RE = re.compile(r"[0-9a-fA-F-]{36}")
DEFAULT_TTL_SECONDS = 86400  # 24 hours


@dataclass
class ChainStep:
    """A single step in a skill chain."""
    index: int
    skill: str
    args: str = ""
    status: str = "pending"  # pending | running | complete | failed | skipped

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "skill": self.skill, "args": self.args, "status": self.status}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChainStep:
        return cls(
            index=data["index"],
            skill=data["skill"],
            args=data.get("args", ""),
            status=data.get("status", "pending"),
        )


@dataclass
class ChainState:
    """Persistent chain-state manifest for a single skill chain."""
    schema_version: str = SCHEMA_VERSION
    chain_id: str = ""
    session_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    status: str = "in_progress"  # in_progress | complete | failed | abandoned
    steps: list[ChainStep] = field(default_factory=list)
    current_step: int = 0
    origin_command: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "chain_id": self.chain_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
            "origin_command": self.origin_command,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChainState:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            chain_id=data.get("chain_id", ""),
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            status=data.get("status", "in_progress"),
            steps=[ChainStep.from_dict(s) for s in data.get("steps", [])],
            current_step=data.get("current_step", 0),
            origin_command=data.get("origin_command", ""),
        )

    def validate(self) -> list[str]:
        """Validate the chain state, returning a list of errors (empty = valid)."""
        errors: list[str] = []
        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version: expected {SCHEMA_VERSION}, got {self.schema_version}")
        if not self.chain_id or not UUID_RE.fullmatch(self.chain_id):
            errors.append(f"chain_id: expected UUID, got {self.chain_id!r}")
        if not self.session_id:
            errors.append("session_id: required")
        if self.status not in ("in_progress", "complete", "failed", "abandoned"):
            errors.append(f"status: invalid value {self.status!r}")
        if not self.steps:
            errors.append("steps: must have at least one step")
        else:
            for i, step in enumerate(self.steps):
                if step.index != i:
                    errors.append(f"steps[{i}].index: expected {i}, got {step.index}")
                if not step.skill:
                    errors.append(f"steps[{i}].skill: required")
                if step.status not in ("pending", "running", "complete", "failed", "skipped"):
                    errors.append(f"steps[{i}].status: invalid {step.status!r}")
        if self.current_step < 0 or self.current_step >= len(self.steps) if self.steps else True:
            errors.append(f"current_step: out of range ({self.current_step})")
        return errors


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _chain_dir() -> Path:
    return Path(CHAIN_STEPS_DIR)


def _chain_path(chain_id: str) -> Path:
    return _chain_dir() / f"{chain_id}.json"


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_manifest(
    steps: list[tuple[str, str]],
    *,
    session_id: str = "",
    chain_id: str = "",
    origin_command: str = "",
) -> ChainState:
    """Create a new chain-state manifest with atomic exclusive write.

    Args:
        steps: List of (skill, args) tuples defining the chain order.
        session_id: Session UUID. Auto-generated if empty.
        chain_id: Explicit chain ID (UUID). Auto-generated if empty.
        origin_command: The original prompt that created this chain.

    Returns:
        The created ChainState (already written to disk).

    Raises:
        FileExistsError: If a manifest with the same chain_id already exists.
        ValueError: If steps is empty.
    """
    if not steps:
        raise ValueError("steps must be non-empty")

    _chain_dir().mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    _chain_id = chain_id or str(uuid.uuid4())
    _session_id = session_id or str(uuid.uuid4())

    chain = ChainState(
        chain_id=_chain_id,
        session_id=_session_id,
        created_at=now,
        updated_at=now,
        steps=[ChainStep(index=i, skill=s, args=a) for i, (s, a) in enumerate(steps)],
        current_step=0,
        origin_command=origin_command or f"chain-{_chain_id}",
    )

    path = _chain_path(_chain_id)
    with open(path, "x", encoding="utf-8", newline="\n") as f:
        json.dump(chain.to_dict(), f, ensure_ascii=False, indent=2)
        f.write("\n")

    return chain


def get_chain(chain_id: str) -> ChainState:
    """Read and validate an existing chain manifest.

    Raises:
        FileNotFoundError: If the chain manifest does not exist.
        ValueError: If the manifest is corrupted or fails validation.
    """
    path = _chain_path(chain_id)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chain = ChainState.from_dict(data)
    errors = chain.validate()
    if errors:
        raise ValueError(f"Corrupted chain manifest for {chain_id}: {'; '.join(errors)}")
    return chain


def advance_step(
    chain_id: str,
    *,
    new_status: str = "complete",
    step_index: int | None = None,
) -> ChainState:
    """Advance the chain to the next step.

    Args:
        chain_id: The chain manifest to update.
        new_status: Status to set for the current/completing step.
        step_index: Explicit step index to update. Defaults to current_step.

    Returns:
        Updated ChainState.

    Raises:
        FileNotFoundError: If the chain manifest doesn't exist.
        ValueError: If the chain is already terminal, or step is out of range.
    """
    chain = get_chain(chain_id)

    if chain.status in ("complete", "failed", "abandoned"):
        raise ValueError(f"Chain {chain_id} is already {chain.status}")

    idx = step_index if step_index is not None else chain.current_step
    if idx < 0 or idx >= len(chain.steps):
        raise ValueError(f"Step index {idx} out of range for chain with {len(chain.steps)} steps")

    # Update the step status
    chain.steps[idx].status = new_status

    # If complete and not the last step, advance to next
    if new_status == "complete" and idx < len(chain.steps) - 1:
        chain.current_step = idx + 1
        chain.steps[chain.current_step].status = "running"
    elif new_status == "complete" and idx == len(chain.steps) - 1:
        chain.status = "complete"
    elif new_status == "failed":
        chain.status = "failed"

    chain.updated_at = datetime.now(timezone.utc).isoformat()

    path = _chain_path(chain_id)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(chain.to_dict(), f, ensure_ascii=False, indent=2)
        f.write("\n")

    return chain


def clear_chain(
    chain_id: str,
    *,
    force: bool = False,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """Remove a chain manifest if it's expired or force is True.

    Args:
        chain_id: The chain manifest to remove.
        force: Skip the TTL check.
        ttl_seconds: Age threshold in seconds (default 86400).

    Returns:
        True if the file was removed, False if it's still within TTL.
    """
    path = _chain_path(chain_id)
    if not path.exists():
        return False

    if force:
        path.unlink(missing_ok=True)
        return True

    # Check TTL
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        path.unlink(missing_ok=True)
        return True

    return False


def list_chains(*, session_id: str = "") -> list[ChainState]:
    """List all chain manifests, optionally filtered by session_id.

    Returns:
        List of ChainState objects sorted by created_at descending.
    """
    chain_dir = _chain_dir()
    if not chain_dir.exists():
        return []

    chains: list[ChainState] = []
    for path in sorted(chain_dir.glob("*.json"), reverse=True):
        try:
            chain = get_chain(path.stem)
            if not session_id or chain.session_id == session_id:
                chains.append(chain)
        except (json.JSONDecodeError, ValueError, FileNotFoundError):
            continue

    return chains
