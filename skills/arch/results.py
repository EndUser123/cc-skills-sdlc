"""
Unified result type for /arch skill modules.

Provides a consistent return type across all public functions,
eliminating heterogeneous dict structures that callers must navigate.

Usage:
    from arch.results import ArchResult

    def load_config() -> ArchResult[ArchConfig]:
        ...
        return ArchResult(is_success=True, value=config)

    result = load_config()
    if result.is_success:
        print(result.value)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")

__all__ = ["ArchResult"]


@dataclass
class ArchResult(Generic[T]):
    """
    Unified result type for all /arch public functions.

    Attributes:
        is_success: True if the operation succeeded.
        value: The result value on success, or None on failure.
        error: Error code string on failure, or None on success.
        templates_used: List of template names used (for routing/persistence).
        metadata: Additional structured metadata (stage, schema_version, etc.).

    Properties:
        is_complete: True when operation succeeded and value is not None.
        is_valid: True when operation is in a terminal state (success or error).

    Examples:
        >>> result = ArchResult(is_success=True, value={"key": "val"})
        >>> result.is_success
        True
        >>> result.is_complete
        True
        >>> result.is_valid
        True

        >>> error_result = ArchResult(is_success=False, error="template_not_found")
        >>> error_result.is_success
        False
        >>> error_result.is_complete
        False
        >>> error_result.is_valid
        True
    """

    is_success: bool
    value: T | None = None
    error: str | None = None
    templates_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """True when the operation succeeded and produced a value."""
        return self.is_success and self.value is not None

    @property
    def is_valid(self) -> bool:
        """True when the result is in a terminal state (success or error)."""
        return self.is_success or self.error is not None

    def unwrap(self) -> T:
        """
        Return the value, raising if error.

        Raises:
            RuntimeError: If the result is an error.

        Returns:
            The value on success.
        """
        if not self.is_success:
            raise RuntimeError(f"ArchResult error: {self.error}")
        if self.value is None:
            raise RuntimeError("ArchResult is_success=True but value is None")
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Return value or default if error."""
        if self.is_success and self.value is not None:
            return self.value
        return default

    def unwrap_error(self) -> str:
        """Return the error string, raising if not an error."""
        if self.is_success:
            raise RuntimeError("ArchResult is not an error")
        return self.error or "unknown error"
