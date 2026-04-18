"""SQD dispatcher — parallel multi-LLM adversarial review dispatch."""

import asyncio
import json
import os
import sys
from pathlib import Path

# All models supported by SQD adversarial review
# Maps to real pi providers/models from `pi --list-models`
# Only includes providers verified to work with ~/.pi/agent/auth.json keys
MODELS = {
    "mistral", "nvidia-nim",
}

# pi model identifiers: provider/model-id format
# pi splits on first "/" to get provider; remaining part is the model ID
PI_MODEL_MAP = {
    "mistral":    "mistral/devstral-2512",
    "nvidia-nim": "nvidia-nim/mistralai/devstral-2-123b-instruct-2512",
}

PI_BIN = "pi.cmd"
DISPATCH_TIMEOUT_SEC = 300
MAX_TARGET_READ_BYTES = 200_000  # cap content at 200KB to avoid token limits


def _read_target_content(target: str) -> str:
    """Read target file or directory content for embedding in prompt.

    For files: returns full content (capped at MAX_TARGET_READ_BYTES).
    For directories: returns a tree listing + key file contents (SKILL.md, *.py).
    Returns empty string if target not found or unreadable.
    """
    p = Path(target)
    if not p.exists():
        return ""

    try:
        if p.is_file():
            content = p.read_text("utf-8", errors="replace")
            return content[:MAX_TARGET_READ_BYTES]

        if p.is_dir():
            parts = [f"Directory: {target}\n"]
            # Walk the tree
            for entry in sorted(p.rglob("*")):
                if entry.is_file() and not any(x in entry.parts for x in (".git", "__pycache__", ".claude", "node_modules")):
                    rel = entry.relative_to(p)
                    parts.append(f"\n--- {rel} ---\n")
                    try:
                        content = entry.read_text("utf-8", errors="replace")
                        parts.append(content[:10_000])  # cap individual files at 10KB
                    except Exception:
                        parts.append("[binary or unreadable]")
            combined = "\n".join(parts)
            return combined[:MAX_TARGET_READ_BYTES]
    except Exception:
        return ""

    return ""


def _parse_pi_jsonl(raw_output: str) -> dict | None:
    """Parse pi JSONL output, extracting final assistant message.

    Looks for error indicators (stopReason="error", errorMessage) inside
    agent_end.messages[0] — pi nests these fields inside the message dict,
    not at the agent_end dict level.
    """
    try:
        full_text = ""
        for line in raw_output.strip().splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    etype = obj.get("type")
                    if etype == "message_update":
                        part = obj.get("part", {})
                        if isinstance(part, dict):
                            ame = part.get("assistantMessageEvent", {})
                            if ame.get("type") == "text_delta":
                                delta = ame.get("delta", "")
                                if delta:
                                    full_text += delta
                    elif etype == "agent_end":
                        # Check for errors nested inside messages[0]
                        msgs = obj.get("messages", [])
                        for msg in msgs:
                            # stopReason and errorMessage live inside the message dict
                            if msg.get("stopReason") == "error":
                                err = msg.get("errorMessage") or msg.get("stopReason")
                                if err:
                                    return {"error": str(err)}
                            if msg.get("role") == "assistant":
                                # content is a list of {"type": "text", "text": "..."} parts
                                content_list = msg.get("content", [])
                                if isinstance(content_list, list):
                                    for part in content_list:
                                        if isinstance(part, dict) and part.get("type") == "text":
                                            text = part.get("text", "").strip()
                                            if text:
                                                return {"text": text}
                                elif isinstance(content_list, str) and content_list:
                                    return {"text": content_list}
                        if full_text:
                            return {"text": full_text}
                        return obj
            except json.JSONDecodeError:
                continue
        return {"text": full_text} if full_text else None
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
    """Dispatch adversarial review to a single LLM provider via pi.

    Args:
        target: Path or description of artifact to review.
        model: Model name (deepseek, gemini, claude, openai, ...).
        output_dir: Directory to write per-model findings.

    Returns:
        dict with at least keys: score (float 0-1), model, finding_text, raw
    """
    if model not in PI_MODEL_MAP:
        raise ValueError(f"Unknown model: {model}. Must be one of {list(PI_MODEL_MAP)}")

    pi_model = PI_MODEL_MAP[model]
    pi_parts = pi_model.split("/", 1)
    provider = pi_parts[0]
    model_id = pi_parts[1] if len(pi_parts) > 1 else pi_model
    output_path = output_dir / f"finding_{model}.json"

    # Build the adversarial review prompt — be explicit about JSON-only output
    prompt = (
        f"You are an adversarial code reviewer.\n"
        f"Review the artifact at: {target}\n\n"
        f"IMPORTANT: Respond with ONLY valid JSON. No markdown, no code fences, no explanation.\n"
        f"Your entire response must be parseable by json.loads().\n"
        f'Format: {{"score": <0.0-1.0>, "summary": "<1 sentence>", "issues": ["<issue1>", ...]}}\n'
        f"Score 0.0 = critical issues found, 1.0 = no issues."
    )

    # pi's internal wrapper checks NVIDIA_NIM_API_KEY regardless of provider.
    # Env vars set in shell may not propagate to Python subprocess env,
    # so read keys from auth.json as a fallback and always forward them.
    env = os.environ.copy()
    auth_path = Path.home() / ".pi" / "agent" / "auth.json"
    auth_data = {}
    try:
        with open(auth_path) as f:
            auth_data = json.load(f)
    except Exception:
        pass

    # Forward NVIDIA_NIM_API_KEY if not already present
    if "NVIDIA_NIM_API_KEY" not in env:
        nvidia_key = env.get("NVIDIA_API_KEY")
        if not nvidia_key:
            for provider_key in ("nvidia", "nvidia-nim"):
                if provider_key in auth_data:
                    entry = auth_data[provider_key]
                    if isinstance(entry, dict) and entry.get("type") == "api_key":
                        nvidia_key = entry.get("key")
                        if nvidia_key:
                            break
        if nvidia_key:
            env["NVIDIA_NIM_API_KEY"] = nvidia_key

    # Forward MISTRAL_API_KEY if not already present (for mistral provider)
    if "MISTRAL_API_KEY" not in env:
        if "mistral" in auth_data:
            entry = auth_data["mistral"]
            if isinstance(entry, dict) and entry.get("type") == "api_key":
                mistral_key = entry.get("key")
                if mistral_key:
                    env["MISTRAL_API_KEY"] = mistral_key

    # pi uses -p which has a ~8K char prompt limit on some models.
    # Only embed content if it fits a reasonable budget (~6000 chars).
    # Otherwise fall back to path reference.
    MAX_EMBED_CHARS = 6_000
    target_content = _read_target_content(target)
    if target_content and len(target_content) <= MAX_EMBED_CHARS:
        prompt = (
            f"You are an adversarial code reviewer.\n"
            f"Review the following code:\n\n{target_content}\n\n"
            f"IMPORTANT: Respond with ONLY valid JSON. No markdown, no code fences, no explanation.\n"
            f"Your entire response must be parseable by json.loads().\n"
            f'Format: {{"score": <0.0-1.0>, "summary": "<1 sentence>", "issues": ["<issue1>", ...]}}\n'
            f"Score 0.0 = critical issues found, 1.0 = no issues."
        )
    elif target_content:
        # Large target — truncate to first 6000 chars (models can at least see the start)
        truncated = target_content[:MAX_EMBED_CHARS] + "\n... [truncated]"
        prompt = (
            f"You are an adversarial code reviewer.\n"
            f"Review the following code:\n\n{truncated}\n\n"
            f"IMPORTANT: Respond with ONLY valid JSON. No markdown, no code fences, no explanation.\n"
            f"Your entire response must be parseable by json.loads().\n"
            f'Format: {{"score": <0.0-1.0>, "summary": "<1 sentence>", "issues": ["<issue1>", ...]}}\n'
            f"Score 0.0 = critical issues found, 1.0 = no issues."
        )
    else:
        prompt = (
            f"You are an adversarial code reviewer.\n"
            f"Review the artifact at: {target}\n\n"
            f"IMPORTANT: Respond with ONLY valid JSON. No markdown, no code fences, no explanation.\n"
            f"Your entire response must be parseable by json.loads().\n"
            f'Format: {{"score": <0.0-1.0>, "summary": "<1 sentence>", "issues": ["<issue1>", ...]}}\n'
            f"Score 0.0 = critical issues found, 1.0 = no issues."
        )

    # Use -p/--print to avoid piped stdin hanging in --mode json
    cmd = [PI_BIN, "--mode", "json", "--provider", provider, "--model", model_id, "-p", prompt]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=DISPATCH_TIMEOUT_SEC,
        )
        return_code = proc.returncode
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"pi ({model}) timed out after {DISPATCH_TIMEOUT_SEC}s")
    except OSError as e:
        raise RuntimeError(f"Failed to spawn pi ({model}): {e}")

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if return_code != 0:
        raise RuntimeError(f"pi ({model}) exited {return_code}: {stderr[:500]}")

    # Parse JSONL output — check for errors surfaced in the result
    result = _parse_pi_jsonl(stdout)
    if result is None:
        # Fallback: try raw JSON
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"No parseable JSON from pi ({model}). stdout: {stdout[:500]}")

    # If result has text but no score/summary, try to parse the text as JSON
    if "text" in result and "score" not in result:
        text = result["text"]
        if isinstance(text, str):
            # Try stripping markdown code fences
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                cleaned = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            cleaned = cleaned.strip()
            try:
                parsed = json.loads(cleaned)
                result = parsed
            except json.JSONDecodeError:
                # Treat as freeform review — assign a moderate default score
                result = {"score": 0.5, "summary": text[:200], "issues": []}

    # Surface errors returned from _parse_pi_jsonl (e.g. stopReason=error)
    if "error" in result:
        raise RuntimeError(f"pi ({model}) API error: {result['error']}")

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

    Models are dispatched sequentially via pi.

    Args:
        target: Path or description of artifact to review.
        models: List of model names (deepseek, gemini, claude, gpt).
        output_dir: Directory to write findings.

    Returns:
        Exit code: 0 consensus, 1 divergent, 2 model failure, 3 target not found.
    """
    if not models:
        return 3

    output_dir.mkdir(parents=True, exist_ok=True)
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
