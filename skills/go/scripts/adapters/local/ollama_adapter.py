"""Ollama HTTP API adapter for /go orchestrator."""

import json
import time
from typing import Literal

from adapter_interface import LocalLLMAdapter


class OllamaAdapter(LocalLLMAdapter):
    """Ollama HTTP API adapter.

    Communicates with Ollama via /api/generate endpoint.
    """

    def __init__(self, base_url: str, model: str, timeout: int = 60) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def send_prompt(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> tuple[str, int]:
        """Send a prompt to Ollama via /api/generate.

        Args:
            prompt: The user prompt to send
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Tuple of (response_text, error_code)
            Error codes: 0=success, 1=timeout, 2=model_unavailable, 3=rate_limit, 9=unknown
        """
        try:
            import urllib.request
            import urllib.error

            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            start_time = time.time()
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if time.time() - start_time > self.timeout:
                    return "", 1  # timeout

                result = json.loads(response.read().decode("utf-8"))
                return result.get("response", ""), 0

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "", 2  # model_unavailable
            if e.code == 429:
                return "", 3  # rate_limit
            return f"HTTP error: {e.code}", 9
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower():
                return "", 1  # timeout
            if "connection refused" in str(e).lower():
                return "", 2  # model_unavailable
            return f"URL error: {e}", 9
        except Exception as e:
            return f"Unknown error: {e}", 9
