"""Layer 0 — PREDICTIVE: adversarial validation of latent failure modes.

Runs adversarial-logic, adversarial-quality, adversarial-io-validation,
adversarial-security, adversarial-performance, adversarial-testing,
adversarial-state-machine, and adversarial-critic in parallel to surface
predictable issues before they manifest as failures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from findings.models import EvidenceTier, Finding, Layer, Severity

# NOTE: Layer 0 adversarial agents (adversarial-logic, adversarial-quality,
# adversarial-io-validation, adversarial-security, adversarial-performance,
# adversarial-testing, adversarial-state-machine) are LLM subagents dispatched via
# the Agent tool — they CANNOT be invoked via subprocess or Python import.
#
# The orchestrator (Python) cannot run these. They must be dispatched by
# the SQA skill's execution context using the Agent tool:
#
#   from agents import adversarial_logic
#   agent = Agent("adversarial-logic")
#   findings = agent.analyze(target, findings=[...])
#
# Currently returns empty list — agent dispatch must happen at skill level.


def _adversarial_agents_available() -> bool:
    """Check if adversarial agents can be dispatched (Agent tool availability)."""
    # Adversarial agents are Claude Code subagents — only callable via Agent tool.
    # This module is Python (orchestrator), not conversation context.
    # Return False so orchestrator knows to skip or warn.
    return False


def _convert_finding(data: dict[str, Any], agent: str) -> Finding:
    """Convert adversarial agent output to a Finding."""
    sev_map = {
        "CRITICAL": Severity.CRITICAL,
        "HIGH": Severity.HIGH,
        "MEDIUM": Severity.MEDIUM,
        "LOW": Severity.LOW,
    }
    tier_map = {
        "T1": EvidenceTier.T1,
        "T2": EvidenceTier.T2,
        "T3": EvidenceTier.T3,
        "T4": EvidenceTier.T4,
    }

    sev = sev_map.get(data.get("severity", "MEDIUM"), Severity.MEDIUM)
    tier_str = data.get("evidence_tier", "T3")
    tier = tier_map.get(tier_str, EvidenceTier.T3)

    return Finding(
        finding_id=f"L0-{agent.upper()}-{data.get('title', 'unknown')[:40]}".replace(" ", "_")[:64],
        severity=sev,
        layer=Layer.L0_PREDICTIVE,
        title=data.get("title", f"{agent} finding"),
        description=data.get("description", ""),
        location=data.get("location"),
        evidence_tier=tier,
        consensus=1,
        category=data.get("category", "predictive"),
    )


def run(target: Path) -> list[Finding]:
    """Run Layer 0: predictive adversarial validation.

    Layer 0 adversarial agents (adversarial-logic, adversarial-quality,
    adversarial-io-validation, adversarial-security, adversarial-performance,
    adversarial-testing, adversarial-state-machine) are LLM subagents that must
    be dispatched via the Agent tool from conversation context. This Python
    module cannot invoke them directly.

    Args:
        target: Path to directory being analyzed.

    Returns:
        Empty list — agent dispatch must happen at skill level.
    """
    import logging
    logger = logging.getLogger(__name__)

    if _adversarial_agents_available():
        # Agent tool is available — dispatch agents here if called from skill context
        logger.info("Layer 0 adversarial agents available via Agent tool")
    else:
        logger.warning(
            "Layer 0 adversarial agents require Agent tool dispatch (skill-level execution). "
            "Returning empty findings. Use Agent('adversarial-logic'), Agent('adversarial-quality'), etc. "
            "from conversation context to run predictive analysis."
        )

    findings = []

    # NOTE: L0 is special — findings come from skill-level Agent dispatch
    # The SKILL.md conductor should call check_halt() after synthesizing agent findings
    return findings
