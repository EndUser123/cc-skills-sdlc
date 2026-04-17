#!/usr/bin/env python3
"""Reusable pi dispatch for multi-LLM skill reviews.

Usage:
    python pi_dispatch.py --model <model> --prompt "<prompt>" --output <path>

Example:
    python pi_dispatch.py --model minimax-coding-plan/MiniMax-M2.7 --prompt "Review..." --output findings.json
"""

import argparse
import subprocess
import sys
import json
from pathlib import Path


def parse_jsonl(raw_output: str) -> dict | None:
    """Parse Pi JSONL output, extracting final assistant message."""
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
                        # Final message collection
                        msgs = obj.get("messages", [])
                        for msg in msgs:
                            if msg.get("role") == "assistant":
                                content = msg.get("content", "")
                                if content:
                                    return {"text": content}
                        # Fallback: if we accumulated text during streaming
                        if full_text:
                            return {"text": full_text}
                        return obj
            except json.JSONDecodeError:
                continue
        return {"text": full_text} if full_text else None
    except Exception:
        return None


def run_dispatch(model: str, prompt: str, output_path: Path) -> int:
    """Run pi with model and prompt, write JSON output to output_path."""
    # model format: provider/model-id (e.g. openrouter/anthropic/claude-sonnet-4)
    parts = model.split("/", 1)
    provider = parts[0]
    model_id = parts[1] if len(parts) > 1 else model
    cmd = ["pi", "--mode", "json", "--provider", provider, "--model", model_id, prompt]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        stdout, stderr = proc.communicate(input=prompt + "\n", timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"[ERROR] opencode timed out after 300s", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"[ERROR] Failed to run opencode: {e}", file=sys.stderr)
        return 1

    combined = stdout + "\n" + stderr if stderr else stdout

    # Parse JSON from output
    result = parse_jsonl(combined)
    if result is None:
        # Last resort: look for any JSON dict in output
        try:
            result = json.loads(combined)
        except json.JSONDecodeError:
            print(f"[ERROR] No parseable JSON in opencode output", file=sys.stderr)
            print(f"stdout: {stdout[:500]}", file=sys.stderr)
            print(f"stderr: {stderr[:500] if stderr else '(none)'}", file=sys.stderr)
            return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[OK] {model} → {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="opencode multi-LLM dispatch")
    parser.add_argument("--model", required=True, help="Model name (e.g. minimax-coding-plan/MiniMax-M2.7)")
    parser.add_argument("--prompt", required=True, help="Prompt text")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    output_path = Path(args.output)
    return run_dispatch(args.model, args.prompt, output_path)


if __name__ == "__main__":
    sys.exit(main())
