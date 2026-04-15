"""SQA Orchestrator — Pure utilities only. No orchestration logic.

This module provides utility functions for SQA. The actual orchestration
(the CONDUCTOR) is the LLM executing the SKILL.md workflow.

What stays here (utilities):
- _validate_target: path validation with resource bounds
- _atomic_write: safe atomic file writes
- _get_terminal_state_dir: terminal-isolated state
- L2State: checkpoint dataclass
- SQAReport: report dataclass
- save_report: atomic report persistence

What does NOT belong here (orchestration — done by LLM in SKILL.md):
- Layer execution order
- Agent tool dispatch for adversarial layers
- Parallel vs sequential layer grouping
- Hard dependency logic (L2 → L4)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from findings.models import (
    Finding,
    SQAReport,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MAX_FILES = 10_000
MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB

# Halt severity threshold mapping
HALT_SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class HaltExceededThreshold(Exception):
    """Raised when layer findings exceed the halt threshold.

    Layers should raise this when check_halt() returns True.
    The conductor (LLM or code) should catch this and stop execution.
    """
    pass


@dataclass
class SeverityHaltTracker:
    """Tracks findings per layer and determines if execution should halt.

    Uses raw (non-deduplicated) counts for halt decisions — deduplication
    is only for health score calculation, not for halt threshold checks.
    """

    threshold: str = "HIGH"  # CRITICAL, HIGH, MEDIUM, LOW, NONE

    def should_halt(self, findings: list[Finding]) -> bool:
        """Check if findings exceed the halt threshold.

        Args:
            findings: List of Finding objects from current layer.

        Returns:
            True if execution should halt.
        """
        if self.threshold == "NONE":
            return False

        threshold_level = HALT_SEVERITY_ORDER.index(self.threshold)
        for finding in findings:
            finding_level = HALT_SEVERITY_ORDER.index(finding.severity.value.upper())
            if finding_level >= threshold_level:
                return True
        return False

    def get_halt_message(self, findings: list[Finding]) -> str:
        """Generate halt message with findings summary."""
        by_severity: dict[str, list[Finding]] = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for f in findings:
            by_severity[f.severity.value.upper()].append(f)

        lines = ["[HALT] Layer completed with findings exceeding threshold:\n"]
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if by_severity[sev]:
                lines.append(f"  {sev}: {len(by_severity[sev])} finding(s)")
        lines.append("\nUse /sqa --halt-on NONE to run all layers regardless.")
        return "\n".join(lines)


def check_halt(layer_name: str, findings: list[Finding]) -> None:
    """Check if findings exceed halt threshold and raise exception if so.

    Fail-safe: Checks halt flag on disk before evaluating threshold.
    Even if exception is caught and suppressed, the flag prevents execution.

    Args:
        layer_name: Current layer being executed (e.g., "L0", "L1")
        findings: List of Finding objects from current layer

    Raises:
        HaltExceededThreshold: If findings exceed the configured halt threshold

    Usage in layers:
        from orchestrator import check_halt
        check_halt("L0", findings)  # Raises if threshold exceeded
    """
    from lib.sqa_state_tracker import load_state, is_halted, _write_halt_flag

    # Fail-fast: Check if halt was already triggered
    if is_halted():
        raise HaltExceededThreshold(
            f"[HALT] {layer_name}: Halt flag detected from prior layer. Execution blocked."
        )

    state = load_state()
    if state is None:
        # No state loaded, skip halt check (may be first run)
        return

    tracker = SeverityHaltTracker(threshold=state.halt_on)

    if tracker.should_halt(findings):
        # CRITICAL: Write halt flag to disk BEFORE raising exception
        # This ensures halt persists even if exception is caught
        _write_halt_flag(layer_name, len(findings))

        # Record halt in state
        from lib.sqa_state_tracker import record_halt
        record_halt(layer_name)

        message = tracker.get_halt_message(findings)
        raise HaltExceededThreshold(f"[HALT] {layer_name}: {message}")


ALLOWED_COMMANDS = [
    "ruff",
    "mypy",
    "pytest",
    "aid",
    "gto",
    "verify",
    "hook-audit",
    "hook-inventory",
    "diagnose",
    "adversarial-security",
    "adversarial-performance",
]


@dataclass
class L2State:
    """Checkpoint state persisted after Layer 2 completes."""

    layer2_had_failures: bool
    target: str


def _atomic_write(path: Path, data: str) -> None:
    """Write data atomically using os.replace() with a temp file.

    os.replace() is atomic on all POSIX and Windows Vista+.
    Adds chmod(0o600) after write for owner-only read permissions.
    """
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data)
    os.replace(str(tmp), str(path))
    os.chmod(path, 0o600)


def _get_terminal_state_dir() -> Path:
    """Return terminal-scoped state directory with sanitized terminal_id.

    Uses shared sanitization function from sqa_state_tracker.
    """
    from lib.sqa_state_tracker import get_sanitized_terminal_id

    terminal_id = get_sanitized_terminal_id()
    state_root = Path.home() / ".claude" / "sqa_state" / f"terminal_{terminal_id}"
    state_root.mkdir(parents=True, exist_ok=True)
    return state_root


def _validate_target(target: str) -> Path:
    """Validate and resolve target path. Raises ValueError on failure."""
    resolved = Path(os.path.realpath(target))
    if not resolved.exists():
        raise ValueError(f"Target {target} does not exist")
    if not resolved.is_dir():
        raise ValueError(f"Target {target} is not a directory")
    if resolved.is_symlink():
        raise ValueError(f"Target {target} is a symlink")
    allowed_roots = [Path.cwd()]
    if not any(resolved.is_relative_to(r) for r in allowed_roots):
        raise ValueError(f"Target {target} outside allowed roots")

    # Resource bounds: use os.scandir for ~3x faster than Path.stat(), sample first 2000
    file_count = 0
    total_size = 0
    sample_limit = 2000  # Sample first 2000 entries as proxy for total size
    sampled = 0

    for entry in resolved.rglob("*"):
        if sampled >= sample_limit:
            break
        if entry.is_file():
            file_count += 1
            try:
                total_size += entry.stat().st_size
                sampled += 1
            except OSError:
                # File unreadable, skip it
                pass

    if file_count > MAX_FILES:
        raise ValueError(f"Target exceeds {MAX_FILES} file limit ({file_count})")
    if total_size > MAX_TOTAL_SIZE:
        raise ValueError(f"Target exceeds {MAX_TOTAL_SIZE // (1024 * 1024)}MB limit ({total_size // (1024 * 1024)}MB)")
    return resolved


def _check_command(cmd: str) -> None:
    """Validate command against ALLOWED_COMMANDS."""
    cmd_name = cmd.split()[0] if isinstance(cmd, str) else cmd[0]
    if cmd_name not in ALLOWED_COMMANDS:
        raise ValueError(f"Command {cmd_name} not in ALLOWED_COMMANDS")


def save_report(report: SQAReport, _path: Path | None) -> None:
    """Save SQAReport to terminal-isolated, atomic-written JSON file.

    Report lands in ~/.claude/sqa_reports/terminal_{tid}/{target_hash}.json.
    Uses os.replace() for true atomicity with chmod(0o600) for owner-only access.
    """
    raw_id = os.environ.get("CLAUDE_TERMINAL_ID", os.environ.get("TERMINAL_ID", "default"))
    terminal_id = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id) or "default"
    report_dir = Path.home() / ".claude" / "sqa_reports" / f"terminal_{terminal_id}"
    report_dir.mkdir(parents=True, exist_ok=True)
    target_hash = hashlib.sha256(report.target.encode()).hexdigest()[:16]
    terminal_path = report_dir / f"{target_hash}.json"
    data = {
        "findings": [
            {
                "finding_id": f.finding_id,
                "severity": f.severity.value,
                "layer": f.layer.value,
                "title": f.title,
                "description": f.description,
                "location": f.location,
                "evidence_tier": f.evidence_tier.value,
                "consensus": f.consensus,
                "category": f.category,
                "evidence": [
                    {
                        "tier": e.tier.value,
                        "description": e.description,
                        "location": e.location,
                    }
                    for e in f.evidence
                ],
            }
            for f in report.findings
        ],
        "health_score": report.health_score,
        "layers_completed": report.layers_completed,
        "audit_trail": [
            {
                "timestamp": a.timestamp,
                "skill": a.skill,
                "exit_code": a.exit_code,
                "finding_count": a.finding_count,
                "notes": a.notes,
            }
            for a in report.audit_trail
        ],
        "target": report.target,
        "timestamp": report.timestamp,
    }
    _atomic_write(terminal_path, json.dumps(data, indent=2))


if __name__ == "__main__":
    print("SQA utilities module. Run via /sqa skill, not directly.")
    print("This module provides: _validate_target, _atomic_write, _get_terminal_state_dir,")
    print("L2State, SQAReport, save_report")
    print("No orchestration logic — orchestration is done by the LLM via SKILL.md")
