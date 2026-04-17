"""SQD dispatcher — parallel multi-LLM adversarial review dispatch."""

import json
import asyncio
from pathlib import Path
from typing import Optional

MODELS = {"deepseek", "gemini", "claude", "gpt"}


async def dispatch_parallel(target: str, models: list[str], output_dir: Path) -> int:
    """Dispatch adversarial review to multiple LLM providers in parallel.

    Args:
        target: Path or description of artifact to review.
        models: List of model names (deepseek, gemini, claude, gpt).
        output_dir: Directory to write findings.

    Returns:
        Exit code: 0 consensus, 1 divergent, 2 model failure, 3 target not found.
    """
    findings = await asyncio.gather(
        *[dispatch_single(target, model, output_dir) for model in models],
        return_exceptions=True,
    )

    failures = [f for f in findings if isinstance(f, Exception)]
    if failures:
        return 2

    scores = [f["score"] for f in findings if isinstance(f, dict)]
    if len(set(int(s * 10) for s in scores)) == 1:
        return 0  # consensus

    await synthesize(findings, output_dir)
    return 1


async def dispatch_single(target: str, model: str, output_dir: Path) -> dict:
    """Dispatch to a single LLM provider (stub — wire to actual agent)."""
    # TODO: Wire to actual LLM dispatch (e.g., via OpenAI-compatible API or agent spawn)
    raise NotImplementedError(f"Model {model} dispatch not yet wired")


async def synthesize(findings: list, output_dir: Path) -> None:
    """Synthesize divergent findings into a consensus report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "synthesis.json"
    with open(out_path, "w") as f:
        json.dump({"findings": findings}, f, indent=2)
