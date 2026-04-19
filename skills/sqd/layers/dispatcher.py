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

# pi model identifiers: full model ID for --model flag
# Use "provider/model-id" format with --model (not --provider + --model separate)
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
    """Parse pi output, extracting final assistant message or JSON.

    Handles two formats:
    1. JSONL (with --mode json): Each line is a JSON object with type field
    2. Plain/markdown (without --mode json): JSON wrapped in markdown fences

    Looks for error indicators (stopReason="error", errorMessage) inside
    agent_end.messages[0] — pi nests these fields inside the message dict,
    not at the agent_end dict level.
    """
    raw = raw_output.strip()
    if not raw:
        return None

    # Try JSONL format first (--mode json)
    full_text = ""
    for line in raw.splitlines():
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

    if full_text:
        return {"text": full_text}

    # Try parsing entire output as plain JSON (without --mode json, wrapped in markdown)
    # Strip markdown fences if present
    cleaned = raw
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove first line (```json) and last line (```)
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
        return parsed
    except json.JSONDecodeError:
        pass

    # Last resort: return full text
    if raw:
        return {"text": raw}
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


def _normalize_finding(result: dict) -> dict:
    """Normalize different JSON schemas to the standard {score, summary, issues} format.

    Handles:
    - {vulnerabilities: [...]} -> extract issues, infer score from severity
    - {issues: [...]} (already correct)
    - {score, summary, issues} (already correct)
    """
    if "score" in result and "summary" in result and "issues" in result:
        return result  # Already normalized

    normalized = dict(result)

    # Handle vulnerabilities schema
    if "vulnerabilities" in result and isinstance(result["vulnerabilities"], list):
        vulns = result["vulnerabilities"]
        issues = []
        severity_map = {"Critical": 0.1, "High": 0.3, "Medium": 0.5, "Low": 0.7, "Info": 0.9}
        score_parts = []

        for v in vulns:
            if isinstance(v, dict):
                # Build issue string from vulnerability fields
                vuln_type = v.get("type", "Unknown vulnerability")
                severity = v.get("severity", "Medium")
                location = v.get("location", "")
                description = v.get("description", "")[:150]

                issue_parts = []
                if vuln_type:
                    issue_parts.append(vuln_type)
                if severity:
                    issue_parts.append(f"[{severity}]")
                if location:
                    issue_parts.append(f"at {location}")
                if description:
                    issue_parts.append(f"- {description}")

                issues.append(" ".join(issue_parts).strip())

                # Accumulate severity scores
                sev_score = severity_map.get(severity, 0.5)
                score_parts.append(sev_score)

        # Calculate score from severities
        if score_parts:
            normalized["score"] = min(score_parts)  # Use worst-case severity
        else:
            normalized["score"] = 0.5

        # Build summary from vulnerability types
        if vulns:
            types = [v.get("type", "Unknown") for v in vulns[:3] if isinstance(v, dict)]
            if len(vulns) > 3:
                normalized["summary"] = f"Found {len(vulns)} issues including: {', '.join(types)}"
            else:
                normalized["summary"] = f"Found {len(vulns)} issues: {', '.join(types)}"

        normalized["issues"] = issues
        return normalized

    # Handle plain issues array without score/summary
    if "issues" in result and isinstance(result["issues"], list):
        if "score" not in normalized:
            # Infer score from issue count
            issue_count = len(result["issues"])
            normalized["score"] = max(0.1, 0.9 - issue_count * 0.1)
        if "summary" not in normalized:
            normalized["summary"] = f"Found {len(result['issues'])} issues"
        return normalized

    return normalized


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

    pi_model = PI_MODEL_MAP[model]  # e.g. "mistral/devstral-2512"
    output_path = output_dir / f"finding_{model}.json"

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

    # Use @{path} syntax — pi reads the file and includes content in context
    # This works for files of any size and is more reliable than --tools read or embedding
    import tempfile
    target_content = _read_target_content(target)
    temp_path = None
    created_temp = False

    if target_content:
        # Write content to temp file, use @{temp_path} syntax
        try:
            suffix = ".py" if Path(target).suffix in (".py", ".pyx") else ".txt"
            with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
                f.write(target_content)
                temp_path = f.name
                created_temp = True
        except Exception:
            temp_path = target  # fallback to original path

        # @{path} is passed separately; instruction starts with context for the review
        instruction = (
            f"Analyze this file for security vulnerabilities. Be adversarial and critical.\n"
            f'Return ONLY valid JSON: {{"score": <0-1>, "summary": "<1 sentence>", "issues": ["<issue with line numbers>"]}}\n'
            f"0.0 = critical issues, 1.0 = no issues. Score reflects severity of found issues."
        )
    else:
        # No content readable, reference original path
        instruction = (
            f"You are an adversarial code reviewer.\n"
            f"Analyze the artifact at: {target}\n\n"
            f'Return ONLY valid JSON: {{"score": <0-1>, "summary": "<1 sentence>", "issues": ["<issue with line numbers>"]}}'
        )

    # @{path} and instruction must be separate arguments after -p
    # Correct: pi -p @<path> "instruction"
    cmd = [PI_BIN, "--model", pi_model, "-p", f"@{temp_path}", instruction]

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
    finally:
        # Clean up temp file only if we created one
        if created_temp and temp_path:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if return_code != 0:
        raise RuntimeError(f"pi ({model}) exited {return_code}: {stderr[:500]}")

    # Parse JSONL output — @{path} approach returns JSON in --mode json
    result = _parse_pi_jsonl(stdout) or {}
    if "text" in result and "score" not in result:
        text = result["text"]
        if isinstance(text, str):
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines_list = cleaned.splitlines()
                cleaned = "\n".join(lines_list[1:-1] if lines_list[-1] == "```" else lines_list[1:])
            cleaned = cleaned.strip()
            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                # Not JSON - parse as freeform markdown review
                result = _parse_freeform_review(text)
    if "error" in result:
        raise RuntimeError(f"pi ({model}) error: {result['error']}")

    # Normalize different JSON schemas to standard format
    result = _normalize_finding(result)

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


def _parse_freeform_review(stdout: str) -> dict:
    """Parse freeform text output from pi into a structured finding dict.

    Extracts issues from markdown-style headers and bullets, estimates score
    based on issue count and severity keywords.
    """
    import re

    result: dict = {"score": 0.5, "summary": "", "issues": [], "text": stdout[:1000]}
    text_lower = stdout.lower()

    # Find security-related issues mentioned anywhere in text
    security_patterns = [
        (r"(?:shell\s+injection|command\s+injection)", "Shell injection vulnerability"),
        (r"(?:arbitrary\s+code|exec\(|eval\()", "Code execution vulnerability"),
        (r"(?:credential\s+exposure|api[_-]?key\s+exposure|secret\s+exposure)", "Credential exposure"),
        (r"(?:sql\s+injection|sqli)", "SQL injection vulnerability"),
        (r"(?:path\s+traversal|/etc/passwd|\.\.\/)", "Path traversal vulnerability"),
        (r"(?:race\s+condition|toctou|time-of-check)", "Race condition"),
        (r"(?:deadlock|livelock)", "Concurrency issue"),
        (r"(?:buffer\s+overflow|heap\s+overflow)", "Memory safety issue"),
        (r"(?:dos|denial\s+of\s+service|resource\s+exhaustion)", "DoS vulnerability"),
        (r"(?:xxe|xml\s+external\s+entity)", "XXE vulnerability"),
        (r"(?:unsafe\s+pickle|deserialization)", "Unsafe deserialization"),
        (r"(?:hardcoded\s+credential|hardcoded\s+password)", "Hardcoded credential"),
        (r"(?:insecure\s+rand|weak\s+crypto)", "Weak cryptography"),
    ]

    for pattern, label in security_patterns:
        if re.search(pattern, text_lower):
            # Find the sentence containing this issue
            for sentence in re.split(r"[.!\n]", stdout):
                if re.search(pattern, sentence.lower()):
                    issue = sentence.strip()[:200]
                    if issue and issue not in result["issues"]:
                        result["issues"].append(issue)
                    break

    # Extract bullet points and numbered list items as issues
    bullet_issues: set[str] = set()
    for line in stdout.splitlines():
        stripped = line.strip()
        # Bullet points (not in headers)
        if stripped.startswith(("*", "-", "+", "•")) and not stripped.startswith("**"):
            issue = re.sub(r"^[*\-+•\s]+", "", stripped).strip()
            # Skip if it's a category label like "* Security Issues"
            if issue and len(issue) > 10 and not issue.endswith(":"):
                bullet_issues.add(issue[:200])
        # Numbered items
        elif re.match(r"^\d+[.)]\s+\*?\*?", stripped):
            issue = re.sub(r"^\d+[.)]\s+\*?\*?", "", stripped).strip()
            if issue and len(issue) > 10:
                bullet_issues.add(issue[:200])

    for issue in bullet_issues:
        if issue not in result["issues"]:
            result["issues"].append(issue)

    # Extract summary - look for "## Summary" section or first paragraph
    lines = stdout.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Look for Summary section
        if re.match(r"^##?\s+Summary\s*:?\s*$", stripped, re.I):
            # Collect next lines until next header or empty line block
            summary_parts = []
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if not next_line:
                    break
                if re.match(r"^##", next_line):
                    break
                summary_parts.append(next_line)
            if summary_parts:
                result["summary"] = " ".join(summary_parts)[:500]
                break
    else:
        # No Summary header found - use first substantive paragraph
        for line in lines:
            stripped = line.strip()
            # Skip headers and empty lines
            if not stripped or re.match(r"^#{1,3}\s+", stripped):
                continue
            # Skip bullet list items for summary
            if stripped.startswith(("*", "-", "+", "•", "1.", "2.", "3.")):
                continue
            # Take first substantive sentence
            if len(stripped) > 30:
                result["summary"] = stripped[:500]
                break

    # Score based on issues found and keywords
    issue_count = len(result["issues"])
    severity_score = 0.0

    for pattern, _ in security_patterns:
        if re.search(pattern, text_lower):
            severity_score += 0.15

    # Base score
    base_penalty = min(issue_count * 0.06, 0.4)
    severity_penalty = min(severity_score, 0.3)
    result["score"] = max(0.0, min(1.0, 0.9 - base_penalty - severity_penalty))

    # If no issues found, check for positive/negative indicators
    if issue_count == 0:
        if any(kw in text_lower for kw in ["no issues", "looks good", "well written", "no vulnerabilities", "no security issues"]):
            result["score"] = 0.95
        elif any(kw in text_lower for kw in ["summary of its functionality", "what the code does", "key features"]):
            # Model is describing, not critiquing - score conservatively
            result["score"] = 0.7
        else:
            result["score"] = 0.75

    return result


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
