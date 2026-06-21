"""Local dispatch orchestrator for /go.

Dispatches task prompts to local LLM adapters and records transcripts.
"""

import json
import os
from pathlib import Path

from adapter_interface import LocalLLMAdapter
from resolve_local import resolve_local_llm


def dispatch_local(prompt: str, state_dir: Path, run_id: str) -> int:
    """Dispatch a task prompt to the configured local LLM.

    Args:
        prompt: The task prompt to send
        state_dir: State directory for artifacts
        run_id: Run identifier

    Returns:
        Exit code: 0 for success, non-zero for failure
    """
    config = resolve_local_llm()
    if config is None:
        print("ERROR: GO_LOCAL_LLM not set or invalid format", file=sys.stderr)
        return 1

    adapter = None
    if config.provider == "ollama":
        from ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter(config.base_url, config.model)
    elif config.provider == "lmstudio":
        from lmstudio_adapter import LMStudioAdapter
        adapter = LMStudioAdapter(config.base_url)
    elif config.provider == "vllm":
        from vllm_adapter import VLLMAdapter
        adapter = VLLMAdapter(config.base_url)
    else:
        print(f"ERROR: Unknown provider: {config.provider}", file=sys.stderr)
        return 1

    response, error_code = adapter.send_prompt(prompt)

    if error_code != 0:
        print(f"ERROR: Local LLM returned error code {error_code}: {response}", file=sys.stderr)
        return 1

    # Record transcript
    transcript = {
        "run_id": run_id,
        "dispatch": "local",
        "provider": config.provider,
        "model": config.model,
        "prompt": prompt,
        "response": response,
    }

    transcript_path = state_dir / f"local-transcript_{run_id}.json"
    transcript_path.write_text(json.dumps(transcript, indent=2) + "\n", encoding="utf-8")

    print(response)
    return 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: dispatch_local.py <prompt>", file=sys.stderr)
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    state_dir = Path(os.environ["GO_STATE_DIR"])
    run_id = os.environ["RUN_ID"]

    sys.exit(dispatch_local(prompt, state_dir, run_id))
