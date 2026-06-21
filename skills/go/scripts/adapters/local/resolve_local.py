"""Resolve local LLM configuration from GO_LOCAL_LLM env var."""

import os
import re
from dataclasses import dataclass
from typing import Literal

LocalLLMType = Literal["ollama", "lmstudio", "vllm"]


@dataclass
class LocalLLMConfig:
    """Parsed local LLM configuration."""

    provider: LocalLLMType
    model: str
    base_url: str


def resolve_local_llm() -> LocalLLMConfig | None:
    """Parse GO_LOCAL_LLM env var and return configuration.

    Formats supported:
    - ollama://model
    - lmstudio://http://localhost:1234
    - vllm://http://localhost:8000

    Returns:
        LocalLLMConfig or None if GO_LOCAL_LLM is not set or invalid
    """
    spec = os.environ.get("GO_LOCAL_LLM", "").strip()
    if not spec:
        return None

    match = re.match(r"^(ollama|lmstudio|vllm)://(.+)$", spec.lower())
    if not match:
        return None

    provider = match.group(1)  # type: ignore[assignment]
    value = match.group(2)

    if provider == "ollama":
        # ollama://model → base_url is http://localhost:11434
        return LocalLLMConfig(
            provider="ollama",
            model=value,
            base_url="http://localhost:11434",
        )
    elif provider == "lmstudio":
        # lmstudio://http://localhost:1234 → base_url is provided
        return LocalLLMConfig(
            provider="lmstudio",
            model="default",
            base_url=value,
        )
    elif provider == "vllm":
        # vllm://http://localhost:8000 → base_url is provided
        return LocalLLMConfig(
            provider="vllm",
            model="default",
            base_url=value,
        )

    return None
