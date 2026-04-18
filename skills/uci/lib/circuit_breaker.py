"""
LLM Provider Circuit Breaker for Unified Code Inspection

Implements circuit breaker pattern to prevent cascading failures:
- Tracks failure rates per provider
- Opens circuit after threshold exceeded
- Allows half-open state for testing recovery
- Automatic fallback to alternative providers
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, not allowing requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ProviderState:
    """State tracking for a single provider."""
    name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    opened_at: Optional[datetime] = None

    # Configuration
    failure_threshold: int = 5  # Open circuit after N failures
    success_threshold: int = 2  # Close circuit after N successes in half-open
    timeout_seconds: int = 60  # How long to stay open before half-open


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    state_file: Path = field(default_factory=lambda: Path(".claude/state/uci/circuit_breaker.json"))
    default_failure_threshold: int = 5
    default_success_threshold: int = 2
    default_timeout_seconds: int = 60
    max_provider_retries: int = 3


class LLMCircuitBreaker:
    """
    Circuit breaker for LLM provider resilience.

    Prevents cascading failures by:
    - Tracking provider health
    - Opening circuit on repeated failures
    - Testing recovery in half-open state
    - Automatic provider fallback
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.providers: Dict[str, ProviderState] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load circuit breaker state from file."""
        if self.config.state_file.exists():
            try:
                with open(self.config.state_file) as f:
                    data = json.load(f)
                for provider_name, provider_data in data.items():
                    # Convert datetime strings back to datetime objects
                    if provider_data.get("last_failure_time"):
                        provider_data["last_failure_time"] = datetime.fromisoformat(
                            provider_data["last_failure_time"]
                        )
                    if provider_data.get("last_success_time"):
                        provider_data["last_success_time"] = datetime.fromisoformat(
                            provider_data["last_success_time"]
                        )
                    if provider_data.get("opened_at"):
                        provider_data["opened_at"] = datetime.fromisoformat(
                            provider_data["opened_at"]
                        )

                    self.providers[provider_name] = ProviderState(
                        name=provider_name,
                        **{k: v for k, v in provider_data.items() if k != "name"}
                    )
            except Exception as e:
                logger.warning(f"Failed to load circuit breaker state: {e}")

    def _save_state(self) -> None:
        """Save circuit breaker state to file."""
        self.config.state_file.parent.mkdir(parents=True, exist_ok=True)

        data = {}
        for provider_name, provider_state in self.providers.items():
            provider_data = {
                "state": provider_state.state.value,
                "failure_count": provider_state.failure_count,
                "success_count": provider_state.success_count,
                "failure_threshold": provider_state.failure_threshold,
                "success_threshold": provider_state.success_threshold,
                "timeout_seconds": provider_state.timeout_seconds,
            }
            if provider_state.last_failure_time:
                provider_data["last_failure_time"] = provider_state.last_failure_time.isoformat()
            if provider_state.last_success_time:
                provider_data["last_success_time"] = provider_state.last_success_time.isoformat()
            if provider_state.opened_at:
                provider_data["opened_at"] = provider_state.opened_at.isoformat()

            data[provider_name] = provider_data

        with open(self.config.state_file, "w") as f:
            json.dump(data, f, indent=2)

    def register_provider(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        success_threshold: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """Register a new provider with circuit breaker."""
        if name not in self.providers:
            self.providers[name] = ProviderState(
                name=name,
                failure_threshold=failure_threshold or self.config.default_failure_threshold,
                success_threshold=success_threshold or self.config.default_success_threshold,
                timeout_seconds=timeout_seconds or self.config.default_timeout_seconds,
            )
            self._save_state()

    def is_available(self, provider_name: str) -> bool:
        """Check if provider is available (circuit is closed or half-open)."""
        provider = self.providers.get(provider_name)
        if not provider:
            # Unknown providers are assumed available
            return True

        # Auto-transition from open to half-open after timeout
        if provider.state == CircuitState.OPEN:
            if provider.opened_at:
                time_since_open = datetime.now() - provider.opened_at
                if time_since_open.total_seconds() >= provider.timeout_seconds:
                    provider.state = CircuitState.HALF_OPEN
                    self._save_state()
                    return True
            return False

        return provider.state != CircuitState.OPEN

    def record_success(self, provider_name: str) -> None:
        """Record successful request from provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            return

        provider.last_success_time = datetime.now()
        provider.success_count += 1

        if provider.state == CircuitState.HALF_OPEN:
            # In half-open, successes move us toward closed
            if provider.success_count >= provider.success_threshold:
                provider.state = CircuitState.CLOSED
                provider.failure_count = 0
                provider.success_count = 0
                logger.info(f"Circuit breaker CLOSED for provider {provider_name}")

        self._save_state()

    def record_failure(self, provider_name: str, error: Optional[str] = None) -> None:
        """Record failed request from provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            # Auto-register on first failure
            self.register_provider(provider_name)
            provider = self.providers[provider_name]

        provider.last_failure_time = datetime.now()
        provider.failure_count += 1

        if provider.state == CircuitState.HALF_OPEN:
            # Failure in half-open immediately opens circuit
            provider.state = CircuitState.OPEN
            provider.opened_at = datetime.now()
            logger.warning(f"Circuit breaker OPEN for provider {provider_name} (failed in half-open)")
        elif provider.failure_count >= provider.failure_threshold:
            # Too many failures, open circuit
            provider.state = CircuitState.OPEN
            provider.opened_at = datetime.now()
            logger.warning(
                f"Circuit breaker OPEN for provider {provider_name} "
                f"({provider.failure_count} failures)"
            )

        self._save_state()

    def get_available_providers(self, preferred_providers: List[str]) -> List[str]:
        """
        Get list of available providers in preference order.

        Args:
            preferred_providers: Ordered list of preferred provider names

        Returns:
            Available providers in preference order
        """
        available = []
        seen = set()

        # First, check preferred providers
        for provider in preferred_providers:
            if provider not in seen and self.is_available(provider):
                available.append(provider)
                seen.add(provider)

        # Then, add any other available providers
        for provider in self.providers:
            if provider not in seen and self.is_available(provider):
                available.append(provider)
                seen.add(provider)

        return available

    def reset_provider(self, provider_name: str) -> None:
        """Manually reset circuit breaker for a provider (admin operation)."""
        provider = self.providers.get(provider_name)
        if provider:
            provider.state = CircuitState.CLOSED
            provider.failure_count = 0
            provider.success_count = 0
            provider.opened_at = None
            self._save_state()
            logger.info(f"Circuit breaker manually reset for provider {provider_name}")

    def get_provider_status(self, provider_name: str) -> Dict[str, Any]:
        """Get current status of a provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            return {"error": "Provider not found"}

        return {
            "name": provider.name,
            "state": provider.state.value,
            "failure_count": provider.failure_count,
            "success_count": provider.success_count,
            "last_failure_time": provider.last_failure_time.isoformat()
            if provider.last_failure_time
            else None,
            "last_success_time": provider.last_success_time.isoformat()
            if provider.last_success_time
            else None,
            "opened_at": provider.opened_at.isoformat() if provider.opened_at else None,
            "available": self.is_available(provider_name),
        }

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers."""
        return {
            provider_name: self.get_provider_status(provider_name)
            for provider_name in self.providers
        }


class CircuitBreakerMiddleware:
    """
    Middleware for automatic circuit breaker integration.

    Wraps LLM calls with automatic failure tracking and provider fallback.
    """

    def __init__(self, circuit_breaker: Optional[LLMCircuitBreaker] = None):
        self.circuit_breaker = circuit_breaker or LLMCircuitBreaker()

    async def execute_with_fallback(
        self,
        providers: List[str],
        execute_func,  # Async function taking provider_name as argument
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, str]:
        """
        Execute function with automatic provider fallback.

        Args:
            providers: Ordered list of provider names to try
            execute_func: Async function to execute (takes provider_name)
            context: Optional context for logging

        Returns:
            Tuple of (result, provider_used)

        Raises:
            Exception: If all providers fail
        """
        context = context or {}
        last_error = None

        available_providers = self.circuit_breaker.get_available_providers(providers)

        if not available_providers:
            raise Exception("No providers available (all circuits open)")

        for provider in available_providers:
            try:
                logger.debug(f"Attempting provider {provider}")
                result = await execute_func(provider)
                self.circuit_breaker.record_success(provider)
                return result, provider
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider} failed: {e}")
                self.circuit_breaker.record_failure(provider, str(e))
                continue

        # All providers failed
        raise Exception(f"All providers failed. Last error: {last_error}")

    def execute_sync_with_fallback(
        self,
        providers: List[str],
        execute_func,  # Sync function taking provider_name as argument
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, str]:
        """
        Execute function with automatic provider fallback (synchronous version).

        Args:
            providers: Ordered list of provider names to try
            execute_func: Sync function to execute (takes provider_name)
            context: Optional context for logging

        Returns:
            Tuple of (result, provider_used)

        Raises:
            Exception: If all providers fail
        """
        context = context or {}
        last_error = None

        available_providers = self.circuit_breaker.get_available_providers(providers)

        if not available_providers:
            raise Exception("No providers available (all circuits open)")

        for provider in available_providers:
            try:
                logger.debug(f"Attempting provider {provider}")
                result = execute_func(provider)
                self.circuit_breaker.record_success(provider)
                return result, provider
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider} failed: {e}")
                self.circuit_breaker.record_failure(provider, str(e))
                continue

        # All providers failed
        raise Exception(f"All providers failed. Last error: {last_error}")
