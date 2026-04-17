"""SQD dispatcher — parallel multi-LLM adversarial review dispatch."""

import asyncio
import json
import sys
from pathlib import Path

MODELS = {"deepseek", "gemini", "claude", "gpt"}

# opencode model identifiers used by opencode_dispatch.py
OPENCODE_MODEL_MAP = {
    "deepseek": "deepseek/deepseek-chat-v3",
    "gemini": "google/gemini-2.5-flash",
    "claude": "anthropic/claude-3.5-sonnet",
    "gpt": "openai/gpt-4o",
}

OPENCODE_BIN = "C:/Users/brsth/AppData/Roaming/npm/opencode.cmd"
DISPATCH_TIMEOUT_SEC = 300


def _parse_opencode_jsonl(raw_output: str) -> dict | None:
    """Parse opencode JSONL output, extracting dict from part.text fields."""
    try:
        for line in raw_output.strip().splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    if obj.get("type") == "text":
                        inner = obj.get("part", {}).get("text", "")
                        if inner:
                            try:
                                return json.loads(inner)
                            except json.JSONDecodeError:
                                return {"text": inner}
                    elif obj.get("type") == "step_finish":
                        return obj
            except json.JSONDecodeError:
                continue
        return None
    except Exception:
        return None


def _score_from_finding(finding: dict) -> float:
    """Extract a 0.0-1.0 quality score from a finding dict.

    Looks for common score fields in priority order.
    """
    for key in ("score", "quality_score", "confidence", "rating"):
        if key in finding and isinstance(finding[key], (int, float)):
            return float(finding[key])
    # Walk through nested dicts
    for val in finding.values():
        if isinstance(val, dict):
            score = _score_from_finding(val)
            if score >= 0:
                return score
    return 0.5  # default


async def dispatch_single(target: str, model: str, output_dir: Path) -> dict:
    """Dispatch adversarial review to a single LLM provider via opencode.

    Args:
        target: Path or description of artifact to review.
        model: Model name (deepseek, gemini, claude, gpt).
        output_dir: Directory to write per-model findings.

    Returns:
        dict with at least keys: score (float 0-1), model, finding_text, raw
    """
    if model not in OPENCODE_MODEL_MAP:
        raise ValueError(f"Unknown model: {model}. Must be one of {list(OPENCODE_MODEL_MAP)}")

    opencode_model = OPENCODE_MODEL_MAP[model]
    output_path = output_dir / f"finding_{model}.json"

    # Build the adversarial review prompt
    prompt = (
        f"You are performing an adversarial code review.\n"
        f"Review the artifact at: {target}\n\n"
        f"Provide a JSON response with:\n"
        f'{{"score": <0.0-1.0>, "summary": "<1 sentence>", "issues": ["<issue1>", ...]}}'
    )

    cmd = [OPENCODE_BIN, "run", prompt, "--model", opencode_model, "--format", "json"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=(prompt + "\n").encode()),
            timeout=DISPATCH_TIMEOUT_SEC,
        )
        return_code = proc.returncode
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"opencode ({model}) timed out after {DISPATCH_TIMEOUT_SEC}s")
    except OSError as e:
        raise RuntimeError(f"Failed to spawn opencode ({model}): {e}")

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if return_code != 0:
        raise RuntimeError(f"opencode ({model}) exited {return_code}: {stderr[:500]}")

    # Parse JSONL output
    result = _parse_opencode_jsonl(stdout)
    if result is None:
        # Fallback: try raw JSON
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"No parseable JSON from opencode ({model}). stdout: {stdout[:500]}")

    score = _score_from_finding(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return {
        "score": score,
        "model": model,
        "finding_text": result.get("summary", result.get("text", "")),
        "issues": result.get("issues", []),
        "raw": result,
        "output_path": str(output_path),
    }


async def dispatch_parallel(target: str, models: list[str], output_dir: Path) -> int:
    """Dispatch adversarial review to multiple LLM providers.

    Models are dispatched sequentially to avoid opencode's SQLite backend
    locking when multiple instances run simultaneously.

    Args:
        target: Path or description of artifact to review.
        models: List of model names (deepseek, gemini, claude, gpt).
        output_dir: Directory to write findings.

    Returns:
        Exit code: 0 consensus, 1 divergent, 2 model failure, 3 target not found.
    """
    if not models:
        return 3

    findings = []
    for model in models:
        try:
            finding = await dispatch_single(target, model, output_dir)
            findings.append(finding)
        except Exception as e:
            print(f"[SQD ERROR] {e}", file=sys.stderr)
            return 2

    scores = [f["score"] for f in findings if isinstance(f, dict)]
    if not scores:
        return 2

    # Consensus: all scores within the same integer bucket (e.g. all 0.7-0.79 → 7)
    if len(set(int(s * 10) for s in scores)) == 1:
        return 0  # consensus

    await synthesize(findings, output_dir)
    return 1


async def synthesize(findings: list, output_dir: Path) -> None:
    """Synthesize divergent findings into a consensus report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "synthesis.json"
    with open(out_path, "w") as f:
        json.dump({"findings": findings}, f, indent=2, ensure_ascii=False)
