"""Utilities for /code skill.

This package provides helper modules for state management, path normalization,
and evidence tracking in the /code skill workflow.
"""

from .evidence import EvidenceManager
from .normalize_paths import normalize_path, normalize_paths_in_command
from .phase_state import PhaseStateManager

__all__ = [
    "EvidenceManager",
    "normalize_path",
    "normalize_paths_in_command",
    "PhaseStateManager",
]
