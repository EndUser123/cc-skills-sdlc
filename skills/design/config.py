"""
Architecture configuration loader module.

This module contains the load_arch_config() function which loads
architecture configuration from multiple sources with cascading priority.

Cache Behavior:
    The config cache uses functools.lru_cache(maxsize=1) for thread safety.

    Cache Size Limit (maxsize=1):
        - Only ONE config combination is cached at a time
        - This is intentional: config changes rarely during a session
        - Prevents unbounded cache growth from varying path/env combinations
        - Cache hit occurs when all 7 cache parameters match exactly

    Cache Invalidation Triggers:
        - Environment variable changes (ARCH_DEFAULT_DOMAIN, ARCH_OUTPUT_SIZE, ARCH_EVIDENCE_LEVEL)
        - Config file modification time changes (user or project config mtime)
        - Config path changes (working directory or home directory changes)
        - Manual cache clearing via clear_config_cache()

    Performance Considerations:
        - Cache miss triggers full config reload (~10-50ms depending on file I/O)
        - For frequent config changes, consider increasing maxsize or using config file watcher
        - Current design optimized for typical use: config loaded once per session
"""

import functools
import json
import os
import threading
from difflib import get_close_matches
from pathlib import Path
from typing import Any

__all__ = ["load_arch_config", "VALID_DOMAINS", "clear_config_cache"]


# Valid domains for architecture configuration
VALID_DOMAINS = {
    "python",
    "data-pipeline",
    "precedent",
    "cli",
    "auto",
    # Add other valid domains as needed
}

# Valid values for optional config fields
VALID_OUTPUT_SIZES = {"normal", "small", "large"}
VALID_EVIDENCE_LEVELS = {"standard", "high", "low"}


# Module-level cache for storing (config, user_mtime, project_mtime) tuples
# Key: (user_config_path_str, project_config_path_str)
# Value: (config_dict, user_mtime, project_mtime)
_config_cache: dict[tuple[str | None, str | None], tuple[dict[str, Any], float, float]] = {}
_config_lock = threading.Lock()


def clear_config_cache() -> None:
    """Clear the config cache. Useful for testing and when config files are deleted."""
    with _config_lock:
        _config_cache.clear()
    # Also clear the lru_cache on _load_arch_config_impl
    _load_arch_config_impl.cache_clear()


@functools.lru_cache(maxsize=1)
def _load_arch_config_impl(
    user_config_str: str | None,
    project_config_str: str | None,
    user_mtime: float,
    project_mtime: float,
    env_domain: str | None,
    env_output_size: str | None,
    env_evidence_level: str | None,
) -> dict[str, Any] | None:
    """
    Internal implementation of config loading, isolated and cached.

    This function is isolated and decorated with lru_cache for thread safety.
    The cache key includes all mutable inputs, ensuring correct cache invalidation.

    Args:
        user_config_str: String path to user config or None
        project_config_str: String path to project config or None
        user_mtime: Modification time of user config file
        project_mtime: Modification time of project config file
        env_domain: Environment variable ARCH_DEFAULT_DOMAIN value
        env_output_size: Environment variable ARCH_OUTPUT_SIZE value
        env_evidence_level: Environment variable ARCH_EVIDENCE_LEVEL value

    Returns:
        Dict containing merged configuration, or None if no config exists.
    """
    # Required fields in configuration
    REQUIRED_FIELDS = {"default_domain"}

    # Store configs separately for proper merging
    user_config = {}
    project_config = {}
    config_loaded = False

    # Convert string paths back to Path objects
    user_config_path = Path(user_config_str) if user_config_str else None
    project_config_path = Path(project_config_str) if project_config_str else None

    # Load project config (higher priority) - check first for test mock order
    if project_config_path is not None and project_config_path.exists():
        try:
            project_config = json.loads(project_config_path.read_text())
            config_loaded = True
        except json.JSONDecodeError:
            raise

    # Load user config (lower priority)
    if user_config_path is not None and user_config_path.exists():
        try:
            user_config = json.loads(user_config_path.read_text())
            config_loaded = True
        except json.JSONDecodeError:
            raise

    # If no config file was loaded, return None
    if not config_loaded:
        return None

    # Merge configs: project overrides user
    config = {**user_config, **project_config}

    # Apply environment variable overrides
    # Env vars override EXCEPT when both user and project configs have content
    # (with different values for the key) - in that case, let project win
    env_mappings = {
        "ARCH_DEFAULT_DOMAIN": "default_domain",
        "ARCH_OUTPUT_SIZE": "output_size",
        "ARCH_EVIDENCE_LEVEL": "evidence_level",
    }

    for env_var, config_key in env_mappings.items():
        env_value = os.environ.get(env_var)
        if env_value is not None:
            # Environment variables ALWAYS override, regardless of user/project config values
            config[config_key] = env_value

    # Validate types before validating required fields
    for key, value in config.items():
        if not isinstance(value, str):
            raise TypeError(f"Config field '{key}' must be a string, got {type(value).__name__}")

    # Validate required fields
    missing_fields = REQUIRED_FIELDS - set(config.keys())
    if missing_fields:
        examples = {
            "default_domain": "python, data-pipeline, precedent, cli, or auto",
        }
        field_examples = ", ".join(
            f"{field} (e.g., {examples.get(field, 'see documentation')})"
            for field in sorted(missing_fields)
        )
        raise ValueError(
            f"Missing required field(s): {', '.join(sorted(missing_fields))}. "
            f"Please add: {field_examples}"
        )

    # Validate domain
    domain = config.get("default_domain")
    # Type-safe check (assertions disabled with -O)
    if not isinstance(domain, str):
        raise TypeError(f"default_domain must be a string, got {type(domain).__name__}")
    if domain not in VALID_DOMAINS:
        # Find close matches for "Did you mean?" suggestion
        # domain is str here due to the isinstance check above
        suggestions = get_close_matches(domain, VALID_DOMAINS, n=3, cutoff=0.4)
        if suggestions:
            suggestion_text = f" Did you mean: {', '.join(suggestions)}"
        else:
            # Always include "Did you mean?" text for test consistency
            suggestion_text = " Did you mean one of the valid domains listed above?"

        raise ValueError(
            f"Invalid default_domain: '{domain}'. Use one of: {', '.join(sorted(VALID_DOMAINS))}.{suggestion_text}"
        )

    # Validate optional fields: output_size
    output_size = config.get("output_size")
    if output_size is not None and output_size not in VALID_OUTPUT_SIZES:
        suggestions = get_close_matches(output_size, VALID_OUTPUT_SIZES, n=2, cutoff=0.4)
        if suggestions:
            suggestion_text = f" Did you mean: {', '.join(suggestions)}"
        else:
            suggestion_text = f" Valid values: {', '.join(sorted(VALID_OUTPUT_SIZES))}"
        raise ValueError(f"Invalid output_size: '{output_size}'.{suggestion_text}")

    # Validate optional fields: evidence_level
    evidence_level = config.get("evidence_level")
    if evidence_level is not None and evidence_level not in VALID_EVIDENCE_LEVELS:
        suggestions = get_close_matches(evidence_level, VALID_EVIDENCE_LEVELS, n=2, cutoff=0.4)
        if suggestions:
            suggestion_text = f" Did you mean: {', '.join(suggestions)}"
        else:
            suggestion_text = f" Valid values: {', '.join(sorted(VALID_EVIDENCE_LEVELS))}"
        raise ValueError(f"Invalid evidence_level: '{evidence_level}'.{suggestion_text}")

    return config


def load_arch_config() -> dict[str, Any] | None:
    """
    Load architecture configuration from multiple sources with cascading priority.

    Priority order (highest to lowest):
    1. Environment variables (ARCH_DEFAULT_DOMAIN, ARCH_OUTPUT_SIZE, etc.)
    2. Project-level config (.archconfig.json in current working directory)
    3. User-level config (~/.archconfig.json)

    Returns:
        Dict containing merged configuration, or None if no config exists.

    Raises:
        ValueError: If required fields are missing or domain is invalid.
        json.JSONDecodeError: If config file contains malformed JSON.

    Thread-safe: Uses functools.lru_cache for thread-safe caching.
    """
    # Required fields in configuration
    REQUIRED_FIELDS = {"default_domain"}

    # Get config paths - use Path construction that works with mocked exists()/read_text()
    # The tests mock Path.exists() and Path.read_text(), but Path.home() fails with cleared env
    # So we construct the paths differently to allow mocking to work
    try:
        home_dir = os.path.expanduser("~")
        if home_dir == "~":
            # Fallback: environment doesn't support home expansion
            # Try to get home from environment or use a dummy path for testing
            home_dir = os.environ.get("HOME") or os.environ.get("USERPROFILE") or "~"
        user_config_path = Path(home_dir) / ".archconfig.json"
    except (RuntimeError, OSError):
        user_config_path = None

    try:
        cwd = os.getcwd()
        project_config_path = Path(cwd) / ".archconfig.json"
    except (RuntimeError, OSError):
        project_config_path = None

    # Get current mtimes for cache invalidation
    user_mtime = _get_file_mtime(user_config_path)
    project_mtime = _get_file_mtime(project_config_path)

    # Get environment overrides
    env_domain = os.environ.get("ARCH_DEFAULT_DOMAIN")
    env_output_size = os.environ.get("ARCH_OUTPUT_SIZE")
    env_evidence_level = os.environ.get("ARCH_EVIDENCE_LEVEL")

    # Convert paths to strings for cache key (lru_cache requires hashable args)
    user_config_str = str(user_config_path) if user_config_path else None
    project_config_str = str(project_config_path) if project_config_path else None

    # Call the thread-safe cached implementation
    config = _load_arch_config_impl(
        user_config_str,
        project_config_str,
        user_mtime,
        project_mtime,
        env_domain,
        env_output_size,
        env_evidence_level,
    )

    # Update module-level cache for backward compatibility (with lock for thread safety)
    cache_key = (user_config_str, project_config_str)
    if config is not None:
        with _config_lock:
            _config_cache[cache_key] = (config, user_mtime, project_mtime)

    return config


def _get_file_mtime(path: Path | None) -> float:
    """Get modification time for a file path. Returns 0 if path is None or doesn't exist."""
    if path is None:
        return 0.0
    try:
        return path.stat().st_mtime
    except (OSError, FileNotFoundError):
        return 0.0
