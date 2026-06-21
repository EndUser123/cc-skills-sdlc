"""Local LLM adapter interface for /go orchestrator."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LocalLLMAdapter(Protocol):
    """Protocol for local LLM adapters.

    All adapters must implement this interface to be compatible with
    the /go orchestrator's local dispatch mechanism.
    """

    def send_prompt(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> tuple[str, int]:
        """Send a prompt to the local LLM.

        Args:
            prompt: The user prompt to send
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Tuple of (response_text, error_code)
            Error codes: 0=success, 1=timeout, 2=model_unavailable, 3=rate_limit, 9=unknown
        """
        ...
