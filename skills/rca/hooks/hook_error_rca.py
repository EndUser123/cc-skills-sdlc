#!/usr/bin/env python3
"""hook_error_rca.py - Enumerate and test hook registrations for RCA.

Usage:
    python P:\\\\\\.claude/hooks/hook_error_rca.py enumerate PostToolUse --tool Task
    python P:\\\\\\.claude/hooks/hook_error_rca.py test PostToolUse --tool Task
    python P:\\\\\\.claude/hooks/hook_error_rca.py full PostToolUse --tool Task
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


# Path getter functions (read env vars at runtime for testability)
def get_settings_file() -> Path:
    return Path(os.environ.get("CLAUDE_SETTINGS", "P:\\\\\\.claude/settings.json"))


def get_hooks_dir() -> Path:
    return Path(os.environ.get("CLAUDE_HOOKS_DIR", "P:\\\\\\.claude/hooks"))


def validate_state_dir(state_dir: Path) -> Path:
    """Ensure state directory is within allowed base path (SEC-003).

    Prevents arbitrary file write via CSF_STATE_DIR environment variable
    manipulation by validating the resolved path is within the expected
    P:\\\\\\.claude/state/ directory tree.

    Args:
        state_dir: The state directory path to validate

    Returns:
        The validated state directory path, or the default if invalid
    """
    try:
        state_dir = state_dir.resolve()
        allowed_base = Path("P:\\\\\\.claude/state").resolve()
        # Use relative_to to check if state_dir is within allowed_base
        state_dir.relative_to(allowed_base)
        return state_dir
    except ValueError:
        # Security: path traversal attempt
        print(f"[SECURITY] Path traversal blocked: {state_dir}", file=sys.stderr)
        return Path("P:\\\\\\.claude/state/rca")
    except OSError as e:
        # I/O error during path resolution
        print(f"[WARNING] Cannot resolve path {state_dir}: {e}", file=sys.stderr)
        return Path("P:\\\\\\.claude/state/rca")


def validate_hook_path(hook_path: Path, hooks_dir: Path) -> bool:
    """Validate that hook_path is within hooks_dir (SEC-001).

    Prevents arbitrary code execution via hook command injection by:
    1. Validating the resolved hook path is within the expected hooks directory tree
    2. Checking against a whitelist of allowed hook base directories
    3. Verifying .py extension
    4. Checking for path traversal in basename

    Args:
        hook_path: The hook file path to validate
        hooks_dir: The allowed base directory for hooks

    Returns:
        True if hook_path is within hooks_dir and passes all security checks,
        False otherwise
    """
    try:
        # Resolve to canonical path (eliminates .. and symlinks)
        hook_path = hook_path.resolve()
        hooks_dir = hooks_dir.resolve()

        # SEC-001: Verify hooks_dir is in whitelist
        # Normalize path separators for cross-platform comparison
        hooks_dir_normalized = hooks_dir.as_posix()
        allowed = False
        for allowed_base in ALLOWED_HOOK_BASES:
            # Normalize allowed base for comparison
            allowed_normalized = Path(allowed_base).as_posix()
            if hooks_dir_normalized.startswith(allowed_normalized):
                allowed = True
                break

        if not allowed:
            print(f"[SECURITY] Hooks directory not in whitelist: {hooks_dir}", file=sys.stderr)
            return False

        # SEC-001: Verify .py extension
        if hook_path.suffix != ".py":
            print(f"[SECURITY] Hook file must have .py extension: {hook_path}", file=sys.stderr)
            return False

        # SEC-001: Check for path traversal in basename (defense in depth)
        basename = hook_path.name
        if ".." in basename or "/" in basename or "\\" in basename:
            print(f"[SECURITY] Path traversal detected in basename: {basename}", file=sys.stderr)
            return False

        # Use relative_to to check if hook_path is within hooks_dir
        hook_path.relative_to(hooks_dir)
        return True
    except ValueError:
        # Security: path traversal attempt
        print(f"[SECURITY] Path traversal blocked: {hook_path}", file=sys.stderr)
        return False
    except OSError as e:
        # I/O error during path resolution
        print(f"[WARNING] Cannot resolve path {hook_path}: {e}", file=sys.stderr)
        return False


def validate_diagnostics_dir(diagnostics_dir: Path, hooks_dir: Path | None = None) -> Path:
    """Ensure diagnostics directory is within allowed base path (SEC-002).

    Prevents arbitrary file read/write via CC_DIAGNOSTICS_DIR environment
    variable manipulation by validating the resolved path is within the
    expected hooks directory tree (logs subdirectory).

    Args:
        diagnostics_dir: The diagnostics directory path to validate
        hooks_dir: Optional hooks directory for determining the allowed base

    Returns:
        The validated diagnostics directory path, or the default if invalid
    """
    try:
        diagnostics_dir = diagnostics_dir.resolve()
        # Determine allowed base: hooks_dir/logs or default
        if hooks_dir is None:
            hooks_dir = get_hooks_dir()
        allowed_base = (hooks_dir / "logs").resolve()
        # Use relative_to to check if diagnostics_dir is within allowed_base
        diagnostics_dir.relative_to(allowed_base)
        return diagnostics_dir
    except ValueError:
        # Security: path traversal attempt
        default_path = Path("P:\\\\\\.claude/hooks/logs/diagnostics")
        print(f"[SECURITY] Path traversal blocked: {diagnostics_dir}", file=sys.stderr)
        return default_path
    except OSError as e:
        # I/O error during path resolution
        default_path = Path("P:\\\\\\.claude/hooks/logs/diagnostics")
        print(f"[WARNING] Cannot resolve path {diagnostics_dir}: {e}", file=sys.stderr)
        return default_path


def get_state_dir() -> Path:
    """Get the state directory with path validation (SEC-003)."""
    state_dir = Path(os.environ.get("CSF_STATE_DIR", "P:\\\\\\.claude/state/rca"))
    return validate_state_dir(state_dir)


def get_cc_errors() -> Path:
    diagnostics_dir = Path(
        os.environ.get("CC_DIAGNOSTICS_DIR", "P:\\\\\\.claude/hooks/logs/diagnostics")
    )
    validated_dir = validate_diagnostics_dir(diagnostics_dir, get_hooks_dir())
    return validated_dir / "cc_errors.jsonl"


SPECIAL_MATCHER_PATTERNS = ("", ".*", "*")

# SEC-001: Whitelist of allowed hook directories
ALLOWED_HOOK_BASES = (
    "P:\\\\\\.claude/hooks",
    "/.claude/hooks",
    "/usr/local/lib/claude/hooks",
    # Add more allowed base paths as needed
)

# Hook testing constants
TIMEOUT_BUFFER_SEC = 5  # Extra time beyond hook's declared timeout
MAX_TEST_TIMEOUT_SEC = 30  # Safety ceiling for test execution
MAX_OUTPUT_LENGTH = 2000  # Truncate stdout/stderr to prevent oversized state files

# Module-level cache for settings.json (PERF-001)
_settings_cache = {"data": None, "mtime": 0, "expires": 0}


def _load_settings() -> dict:
    """Load settings.json with caching (60s TTL or file change detection).

    Returns cached dict if available and valid, empty dict if file missing or invalid.

    Returns:
        Settings dictionary (empty dict if file missing/invalid)
    """
    global _settings_cache

    settings_file = get_settings_file()
    current_mtime = settings_file.stat().st_mtime if settings_file.exists() else 0
    now = time.time()

    # Return cached data if valid (same mtime and not expired)
    if (
        _settings_cache["data"] is not None
        and current_mtime == _settings_cache["mtime"]
        and now < _settings_cache["expires"]
    ):
        return _settings_cache["data"]

    # Need to reload from disk
    try:
        if not settings_file.exists():
            settings = {}
        else:
            settings = json.loads(settings_file.read_text(encoding="utf-8"))

        _settings_cache["data"] = settings
        _settings_cache["mtime"] = current_mtime
        _settings_cache["expires"] = now + 60  # 60s TTL
        return settings
    except (OSError, json.JSONDecodeError) as e:
        print(f"[ERROR] Failed to read settings file {settings_file}: {e}", file=sys.stderr)
        return {}


@dataclass
class HookRegistration:
    """Represents a hook registration from settings.json."""

    event_type: str
    matcher: str
    command: str
    hook_file: str
    timeout: int
    file_exists: bool
    matches_tool: bool
    source: str  # "settings.json" or "skill:<name>"


@dataclass
class HookTestResult:
    """Represents the result of testing a hook in isolation."""

    hook_file: str
    matcher: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    verdict: Literal[
        "pass",
        "fail_error",
        "fail_timeout",
        "fail_missing",
        "block_intent",
        "fail_crash",
        "pass_with_stderr",
    ]


def resolve_hook_file(command: str) -> Path | None:
    """Extract the actual .py file from a hook command string.

    Handles patterns observed in settings.json:
    - hook_runner.py wrapper: python P:\\\\\\.claude/hooks/__lib/hook_runner.py <actual>.py
    - direct python: python "<path>.py" or python <path>.py
    - uv run: uv run <path>.py

    Args:
        command: The hook command string from settings.json

    Returns:
        Path to the hook file, or None if not resolved
    """
    # Pattern 1: hook_runner.py wrapper (extract actual hook from runner args)
    # Must be checked FIRST to avoid matching the runner path itself
    # Handles both quoted and unquoted paths with spaces
    runner_match = re.search(r'hook_runner\.py\s+["\']([^"\']+\.py)["\']', command)
    if runner_match:
        return Path(runner_match.group(1))
    runner_match_unquoted = re.search(r"hook_runner\.py\s+([^\s]+\.py)", command)
    if runner_match_unquoted:
        return Path(runner_match_unquoted.group(1))

    # Pattern 2: python "<path>.py" (quoted, may contain spaces)
    direct_match_quoted = re.search(r'python\s+["\']([^"\']+\.py)["\']', command)
    if direct_match_quoted:
        return Path(direct_match_quoted.group(1))

    # Pattern 2b: python <path>.py (unquoted, no spaces)
    direct_match = re.search(r"python\s+([^\s]+\.py)", command)
    if direct_match:
        return Path(direct_match.group(1))

    # Pattern 3: uv run "<path>.py" (quoted, may contain spaces)
    uv_match_quoted = re.search(r'uv\s+run\s+["\']([^"\']+\.py)["\']', command)
    if uv_match_quoted:
        return Path(uv_match_quoted.group(1))

    # Pattern 3b: uv run <path>.py (unquoted, no spaces)
    uv_match = re.search(r"uv\s+run\s+([^\s]+\.py)", command)
    if uv_match:
        return Path(uv_match.group(1))

    return None


def validate_matcher_pattern(matcher: str, tool_name: str) -> tuple[bool, str]:
    """Validate matcher pattern and return (matches, warning).

    Returns True for invalid patterns (safe default: allow the hook).
    Logs warning for invalid regex.

    Args:
        matcher: The regex pattern to validate
        tool_name: The tool name to match against

    Returns:
        Tuple of (matches, warning_message)
        - matches: True if pattern matches or is invalid (safe default)
        - warning_message: Empty string if valid, warning text if invalid
    """
    # Special patterns always match
    if matcher in SPECIAL_MATCHER_PATTERNS:
        return True, ""

    # Check for catastrophic backtracking patterns
    dangerous_patterns = [
        "(a+)+b",  # Catastrophic backtracking
        "((a+)*)+",  # Nested quantifiers
    ]
    for dangerous in dangerous_patterns:
        if dangerous in matcher:
            logger.warning(
                f"Matcher '{matcher}' contains potentially catastrophic pattern. "
                f"Defaulting to match-all for safety."
            )
            return True, f"Potentially catastrophic pattern in matcher '{matcher}'"

    # Try to compile and match the regex
    try:
        matches = bool(re.search(matcher, tool_name))
        return matches, ""
    except re.error as e:
        logger.warning(
            f"Invalid regex '{matcher}' for tool '{tool_name}': {e}. "
            f"Defaulting to match-all for safety."
        )
        return True, f"Invalid regex '{matcher}': {e}"


def enumerate_registrations(
    event_type: str,
    tool_name: str | None = None,
) -> list[HookRegistration]:
    """Parse settings.json to find all hook registrations for an event type.

    Args:
        event_type: The hook event type (e.g., "PostToolUse", "PreToolUse")
        tool_name: Optional tool name to filter by matcher

    Returns:
        List of HookRegistration objects
    """
    registrations: list[HookRegistration] = []

    settings = _load_settings()
    if not settings:
        return registrations

    # Navigate to hooks section
    hooks_section = settings.get("hooks", {})
    event_hooks = hooks_section.get(event_type, [])

    if not isinstance(event_hooks, list):
        return registrations

    for entry in event_hooks:
        matcher = entry.get("matcher", ".*")
        hooks_list = entry.get("hooks", [])

        # Test if this matcher would match the tool name
        matches = True
        if tool_name:
            matches, warning = validate_matcher_pattern(matcher, tool_name)
            if warning:
                logger.warning(f"Hook matcher validation: {warning}")

        for hook_def in hooks_list:
            command = hook_def.get("command", "")
            timeout = hook_def.get("timeout", 10)

            hook_path = resolve_hook_file(command)
            file_exists = hook_path.exists() if hook_path else False

            registrations.append(
                HookRegistration(
                    event_type=event_type,
                    matcher=matcher,
                    command=command,
                    hook_file=str(hook_path) if hook_path else f"UNRESOLVED:{command}",
                    timeout=timeout,
                    file_exists=file_exists,
                    matches_tool=matches,
                    source="settings.json",
                )
            )

    return registrations


def _load_cc_errors_entries() -> list[dict]:
    """Load all cc_errors.jsonl entries into memory (PERF-010 cache).

    Returns:
        List of error entry dicts. Empty list if file doesn't exist or on error.
    """
    cc_errors = get_cc_errors()
    if not cc_errors.exists():
        return []

    try:
        lines = cc_errors.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries
    except OSError as e:
        print(f"[ERROR] Failed to read cc_errors file {cc_errors}: {e}", file=sys.stderr)
        return []


def _extract_hook_from_error_type(error_type: str) -> str:
    """Best-effort extraction of hook name from error_type text."""
    if not error_type:
        return "unknown"
    # Common format: "hook_error: HookName" or "... HookName.py"
    if ":" in error_type:
        candidate = error_type.split(":", 1)[1].strip()
    else:
        candidate = error_type.strip()
    # Normalize path-like values to basename stem
    candidate_path = Path(candidate)
    if candidate_path.suffix == ".py":
        return candidate_path.stem
    # Keep token-sized value if available
    token = re.split(r"\s+", candidate)[0].strip()
    return token or "unknown"


def _is_timeout_entry(entry: dict) -> bool:
    """Return True if entry appears to be timeout-related."""
    context = entry.get("context", {}) if isinstance(entry.get("context", {}), dict) else {}
    category = str(context.get("error_category", "")).lower()
    error_type = str(entry.get("error_type", "")).lower()
    error_message = str(entry.get("error_message", "")).lower()
    return "timeout" in category or "timeout" in error_type or "timed out" in error_message


def build_diagnostic_sweep(
    registrations: list[HookRegistration],
    cc_errors_entries: list[dict],
    hours: int = 24,
) -> dict:
    """Cross-source sweep over diagnostics log to surface patterns before RCA claims."""
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    recent_entries: list[dict] = []
    for entry in reversed(cc_errors_entries):
        timestamp = entry.get("timestamp", "")
        if not timestamp:
            continue
        if timestamp < cutoff:
            break
        recent_entries.append(entry)

    matching_hook_names = {
        Path(r.hook_file).stem
        for r in registrations
        if r.matches_tool and r.hook_file and "UNRESOLVED:" not in r.hook_file
    }
    category_counts: dict[str, int] = {}
    timeout_by_hook: dict[str, int] = {}
    timeout_samples: list[dict] = []

    for entry in recent_entries:
        context = entry.get("context", {}) if isinstance(entry.get("context", {}), dict) else {}
        category = str(context.get("error_category", "unknown"))
        category_counts[category] = category_counts.get(category, 0) + 1

        if _is_timeout_entry(entry):
            hook_name = _extract_hook_from_error_type(str(entry.get("error_type", "")))
            timeout_by_hook[hook_name] = timeout_by_hook.get(hook_name, 0) + 1
            if len(timeout_samples) < 10:
                timeout_samples.append(
                    {
                        "timestamp": entry.get("timestamp"),
                        "error_type": entry.get("error_type"),
                        "error_category": context.get("error_category"),
                        "error_message": entry.get("error_message", "")[:200],
                    }
                )

    matching_timeout_by_hook = {
        hook: count for hook, count in timeout_by_hook.items() if hook in matching_hook_names
    }

    return {
        "completed": True,
        "hours": hours,
        "recent_entries_scanned": len(recent_entries),
        "category_counts": category_counts,
        "timeout_pattern_scan_completed": True,
        "timeout_total": sum(timeout_by_hook.values()),
        "timeout_by_hook": timeout_by_hook,
        "matching_timeout_by_hook": matching_timeout_by_hook,
        "timeout_samples": timeout_samples,
    }


def build_signal_source_verification(
    test_results: list[HookTestResult],
    registrations: list[HookRegistration],
) -> dict:
    """Verify whether 'hook error' appears to be functional failure vs labeling artifact."""
    pass_with_stderr = [r for r in test_results if r.verdict == "pass_with_stderr"]
    hard_failures = [
        r
        for r in test_results
        if r.verdict in ("fail_error", "fail_timeout", "fail_missing", "fail_crash")
    ]
    wrapper_count = sum(1 for r in registrations if "hook_runner.py" in r.command)
    direct_count = max(0, len(registrations) - wrapper_count)

    if pass_with_stderr:
        inferred_source = "stderr_labeling_artifact"
    elif hard_failures:
        inferred_source = "functional_hook_failure"
    else:
        inferred_source = "no_repro_in_isolation"

    return {
        "signal_source_verified": True,
        "inferred_source": inferred_source,
        "pass_with_stderr_count": len(pass_with_stderr),
        "hard_failure_count": len(hard_failures),
        "wrapper_usage": {
            "hook_runner_wrapped": wrapper_count,
            "direct_or_unresolved": direct_count,
        },
    }


def check_recent_errors(
    hook_name: str,
    hours: int = 24,
    use_regex: bool = False,
    return_metadata: bool = False,
    _cached_entries: list[dict] | None = None,
) -> list[dict] | dict:
    """Check cc_errors.jsonl for recent errors matching a hook name.

    Provides Tier 1 evidence from the actual error log.

    Uses reverse chronological scan with early cutoff to avoid reading
    entire file when recent matching entries are found (PERF-003).

    Args:
        hook_name: Name of the hook to search for (or regex pattern if use_regex=True)
        hours: Number of hours to look back (default 24)
        use_regex: If True, treat hook_name as regex pattern (default False)
        return_metadata: If True, return dict with metadata (default False for backward compat)

    PERF-010: Accepts _cached_entries to avoid re-reading file in loops.

    Args:
        hook_name: Name of the hook to search for (or regex pattern if use_regex=True)
        hours: Number of hours to look back (default 24)
        use_regex: If True, treat hook_name as regex pattern (default False)
        return_metadata: If True, return dict with metadata (default False for backward compat)
        _cached_entries: Pre-loaded error entries (PERF-010 optimization)

    Returns:
        List of error entries by default (backward compatible),
        or dict with {"errors": [...], "count": N} when return_metadata=True
    """
    if _cached_entries is not None:
        entries = _cached_entries
    else:
        cc_errors = get_cc_errors()
        if not cc_errors.exists():
            return {"errors": [], "count": 0} if return_metadata else []

        try:
            lines = cc_errors.read_text(encoding="utf-8").splitlines()
            entries = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError as e:
            print(f"[ERROR] Failed to read cc_errors file {cc_errors}: {e}", file=sys.stderr)
            return {"errors": [], "count": 0} if return_metadata else []

    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    errors = []

    # Reverse scan - newest first (PERF-003)
    for entry in reversed(entries):
        timestamp = entry.get("timestamp", "")
        # Skip entries without timestamp
        if not timestamp:
            continue
        # Past cutoff in reverse order - stop scanning
        if timestamp < cutoff:
            break

        error_type = entry.get("error_type", "")

        # Match hook name (regex or substring)
        matches = False
        if use_regex:
            try:
                matches = bool(re.search(hook_name, error_type))
            except re.error:
                # Invalid regex: fall back to substring match
                matches = hook_name.lower() in error_type.lower()
        else:
            matches = hook_name.lower() in error_type.lower()

        if matches:
            errors.append(entry)
            # Limit per hook to avoid returning excessive data
            if len(errors) >= 5:
                break

    if return_metadata:
        return {"errors": errors, "count": len(errors)}
    return errors


def test_hook_isolated(
    reg: HookRegistration,
    tool_name: str = "Bash",
) -> HookTestResult:
    """Run a single hook in isolation and capture all output.

    Uses the same subprocess model as Claude Code (stdin JSON, capture
    exit code + stdout + stderr). The test payload mirrors the documented
    PostToolUse input schema.

    Args:
        reg: HookRegistration to test
        tool_name: Tool name to use in test payload

    Returns:
        HookTestResult with verdict classification
    """
    hook_path = Path(reg.hook_file)

    # SEC-001: Validate hook path is within allowed hooks directory
    if not validate_hook_path(hook_path, get_hooks_dir()):
        return HookTestResult(
            hook_file=reg.hook_file,
            matcher=reg.matcher,
            exit_code=-1,
            stdout="",
            stderr=f"Hook path rejected: {reg.hook_file} is outside allowed hooks directory",
            duration_ms=0,
            verdict="fail_crash",
        )

    if not hook_path.exists():
        return HookTestResult(
            hook_file=reg.hook_file,
            matcher=reg.matcher,
            exit_code=-1,
            stdout="",
            stderr=f"File not found: {reg.hook_file}",
            duration_ms=0,
            verdict="fail_missing",
        )

    # Build test payload matching documented PostToolUse input schema
    payload = json.dumps(
        {
            "session_id": "test-rca-session",
            "transcript_path": "",
            "cwd": str(Path.cwd()),
            "permission_mode": "default",
            "hook_event_name": "PostToolUse",
            "tool_name": tool_name,
            "tool_input": {"command": "echo test"},
            "tool_response": {"stdout": "test", "exit_code": 0},
            "tool_use_id": "toolu_test",
        }
    )

    timeout_sec = min(reg.timeout + TIMEOUT_BUFFER_SEC, MAX_TEST_TIMEOUT_SEC)

    try:
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(get_hooks_dir()),
        )
        duration = (time.perf_counter() - start) * 1000

        # Classify per Claude Code's exit code semantics:
        # 0 = success, 2 = intentional block, other = error
        # PLUS: stderr on exit 0 = "pass_with_stderr" (the false-error case)
        if result.returncode == 0:
            if result.stderr.strip():
                verdict = "pass_with_stderr"  # The HOOK_STDERR_STYLE_GUIDE case
            else:
                verdict = "pass"
        elif result.returncode == 2:
            verdict = "block_intent"
        else:
            verdict = "fail_error"

        return HookTestResult(
            hook_file=reg.hook_file,
            matcher=reg.matcher,
            exit_code=result.returncode,
            stdout=result.stdout[:MAX_OUTPUT_LENGTH],
            stderr=result.stderr[:MAX_OUTPUT_LENGTH],
            duration_ms=round(duration, 1),
            verdict=verdict,
        )

    except subprocess.TimeoutExpired:
        return HookTestResult(
            hook_file=reg.hook_file,
            matcher=reg.matcher,
            exit_code=124,
            stdout="",
            stderr=f"Timed out after {timeout_sec}s",
            duration_ms=timeout_sec * 1000,
            verdict="fail_timeout",
        )
    except Exception as e:
        return HookTestResult(
            hook_file=reg.hook_file,
            matcher=reg.matcher,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            duration_ms=0,
            verdict="fail_crash",
        )


def _stage1_enumerate(event_type: str, tool_name: str | None) -> list[HookRegistration]:
    """Stage 1: Enumerate and filter hook registrations.

    Args:
        event_type: The hook event type (e.g., "PostToolUse", "PreToolUse")
        tool_name: Optional tool name to filter by matcher

    Returns:
        List of HookRegistration objects
    """
    print("STAGE 1: Enumerating hook registrations from settings.json...")
    registrations = enumerate_registrations(event_type, tool_name)
    matching = [r for r in registrations if r.matches_tool]

    print(f"  Total registrations for {event_type}: {len(registrations)}")
    print(f"  Matching tool '{tool_name or '*'}': {len(matching)}")

    for r in registrations:
        status = "MATCH" if r.matches_tool else "skip "
        exists = "OK" if r.file_exists else "MISSING"
        name = Path(r.hook_file).name if "/" in r.hook_file or "\\" in r.hook_file else r.hook_file
        print(f"    [{status}] [{exists}] matcher='{r.matcher}' -> {name} (timeout={r.timeout}s)")

    # Immediate finding: missing files
    missing_files = [r for r in matching if not r.file_exists]
    if missing_files:
        print(f"\n  ** IMMEDIATE FINDING: {len(missing_files)} hook file(s) missing **")
        for r in missing_files:
            print(f"    MISSING: {r.hook_file}")
            print(f"    Command: {r.command}")

    return registrations


def _stage2_test(
    registrations: list[HookRegistration], tool_name: str | None
) -> tuple[list[HookTestResult], dict[str, list]]:
    """Stage 2: Test each matching hook and check error logs.

    PERF-004: Uses parallel execution via ThreadPoolExecutor to test hooks
    concurrently, reducing total execution time.

    Args:
        registrations: List of HookRegistration objects
        tool_name: Optional tool name to use in test payload

    Returns:
        Tuple of (test_results, error_log_evidence)
    """
    matching = [r for r in registrations if r.matches_tool]

    print(f"\nSTAGE 2: Testing {len(matching)} matching hooks in isolation...")
    test_results: list[HookTestResult] = []

    # PERF-004: Parallel hook execution using ThreadPoolExecutor
    max_workers = min(32, len(matching)) if matching else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all hook tests to the executor
        future_to_reg = {
            executor.submit(test_hook_isolated, r, tool_name or "Bash"): r for r in matching
        }

        # Collect results as they complete
        for future in as_completed(future_to_reg):
            result = future.result()
            test_results.append(result)

            icon = {
                "pass": "PASS",
                "block_intent": "BLCK",
                "pass_with_stderr": "STDR",
                "fail_error": "FAIL",
                "fail_timeout": "TIME",
                "fail_missing": "MISS",
                "fail_crash": "BOOM",
            }.get(result.verdict, "????")
            print(
                f"    [{icon}] {Path(result.hook_file).name} "
                f"(exit={result.exit_code}, {result.duration_ms:.0f}ms)"
            )
            if result.stderr:
                for line in result.stderr.strip().split("\n")[:3]:
                    print(f"           stderr: {line[:120]}")

    # PERF-010: Load cc_errors.jsonl ONCE before the loop
    cc_errors_entries = _load_cc_errors_entries()

    # Check cc_errors.jsonl for each hook using cached data
    print("\nSTAGE 2b: Checking cc_errors.jsonl for recent failures...")
    error_log_evidence: dict[str, list] = {}
    for r in matching:
        hook_name = Path(r.hook_file).stem
        recent = check_recent_errors(hook_name, hours=24, _cached_entries=cc_errors_entries)
        if isinstance(recent, dict):
            recent = recent.get("errors", [])
        if recent:
            error_log_evidence[hook_name] = recent[:5]  # Limit to 5 per hook
            cats = {e.get("context", {}).get("error_category", "?") for e in recent}
            print(
                f"    {hook_name}: {len(recent)} errors in last 24h "
                f"(categories: {', '.join(cats)})"
            )

    print("\nSTAGE 2c: Diagnostic sweep across cc_errors.jsonl...")
    sweep = build_diagnostic_sweep(matching, cc_errors_entries, hours=24)
    error_log_evidence["__diagnostic_sweep__"] = [sweep]
    timeout_total = sweep.get("timeout_total", 0)
    if timeout_total:
        hot_hooks = sweep.get("timeout_by_hook", {})
        top = sorted(hot_hooks.items(), key=lambda kv: kv[1], reverse=True)[:5]
        top_str = ", ".join(f"{name}={count}" for name, count in top) if top else "n/a"
        print(f"    timeout patterns detected: {timeout_total} (top hooks: {top_str})")
    else:
        print("    no timeout patterns detected in recent window")

    return test_results, error_log_evidence


def _stage3_classify(
    test_results: list[HookTestResult],
    registrations: list[HookRegistration],
    tool_name: str | None,
    event_type: str,
    error_log_evidence: dict[str, list],
) -> list[str]:
    """Stage 3: Classify test results into categories and determine root causes.

    Args:
        test_results: List of HookTestResult objects
        registrations: List of HookRegistration objects
        tool_name: Optional tool name filter
        event_type: The hook event type
        error_log_evidence: Error log evidence from cc_errors.jsonl

    Returns:
        List of root cause strings
    """
    matching = [r for r in registrations if r.matches_tool]
    failures = [r for r in test_results if r.verdict not in ("pass", "block_intent")]
    real_errors = [r for r in failures if r.verdict != "pass_with_stderr"]
    stderr_only = [r for r in test_results if r.verdict == "pass_with_stderr"]

    print(f"\n{'='*60}")
    print("  STAGE 3: ROOT CAUSE DETERMINATION")
    print(f"{'='*60}")
    print(f"  Clean passes: {sum(1 for r in test_results if r.verdict == 'pass')}")
    print(f"  Block-intent (exit 2): {sum(1 for r in test_results if r.verdict == 'block_intent')}")
    print(f"  Pass-with-stderr (false 'hook error'): {len(stderr_only)}")
    print(f"  Real failures: {len(real_errors)}")

    root_causes: list[str] = []

    if real_errors:
        for r in real_errors:
            cause = (
                f"Root cause: {Path(r.hook_file).name} fails with "
                f"exit code {r.exit_code}. Error: {r.stderr[:200]}"
            )
            root_causes.append(cause)
            print(f"\n  ROOT CAUSE: {cause}")

    if stderr_only:
        for r in stderr_only:
            cause = (
                f"Root cause: {Path(r.hook_file).name} exits 0 but writes to "
                f"stderr, which Claude Code displays as 'hook error'. "
                f"Stderr: {r.stderr[:100]}"
            )
            root_causes.append(cause)
            print(f"\n  ROOT CAUSE (stderr-as-error): {cause}")
            print(
                "  Fix: Apply HOOK_STDERR_STYLE_GUIDE.md - silence stderr "
                "or gate on DEBUG env var"
            )

    if not root_causes and not matching:
        print(f"\n  NO MATCHING HOOKS for {event_type}:{tool_name}")
        print("  Check if error is from a different event type or matcher bug")

    if not root_causes and matching and not failures:
        print("\n  ALL HOOKS PASSED in isolation.")
        print("  Remaining investigations:")
        print("  - [ ] Check if real payload shape differs from test payload")
        total_timeout = sum(r.timeout for r in matching)
        print(f"        Sum of timeouts: {total_timeout}s")
        print("  - [ ] Check cc_errors.jsonl for intermittent failures")
        if not error_log_evidence:
            print("\n  Root cause not found. Investigation incomplete.")

    return root_causes


def _save_state(
    event_type: str,
    tool_name: str | None,
    registrations: list[HookRegistration],
    test_results: list[HookTestResult],
    root_causes: list[str],
    error_log_evidence: dict[str, list],
) -> dict:
    """Save investigation state to file.

    Args:
        event_type: The hook event type
        tool_name: Optional tool name filter
        registrations: List of HookRegistration objects
        test_results: List of HookTestResult objects
        root_causes: List of root cause strings
        error_log_evidence: Error log evidence from cc_errors.jsonl

    Returns:
        The state dictionary that was saved
    """
    state_dir = get_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "hook_error_investigation.json"

    failures = [r for r in test_results if r.verdict not in ("pass", "block_intent")]
    sweep_list = error_log_evidence.get("__diagnostic_sweep__", [])
    sweep = sweep_list[0] if sweep_list and isinstance(sweep_list[0], dict) else {}
    signal_source = build_signal_source_verification(test_results, registrations)
    state = {
        "event_type": event_type,
        "tool_name": tool_name,
        "registrations": [asdict(r) for r in registrations],
        "test_results": [asdict(r) for r in test_results],
        "root_causes": root_causes,
        "error_log_evidence": error_log_evidence,
        "diagnostic_sweep_completed": bool(sweep.get("completed")),
        "timeout_pattern_scan_completed": bool(sweep.get("timeout_pattern_scan_completed")),
        "timeout_patterns": {
            "timeout_total": sweep.get("timeout_total", 0),
            "timeout_by_hook": sweep.get("timeout_by_hook", {}),
            "matching_timeout_by_hook": sweep.get("matching_timeout_by_hook", {}),
        },
        "signal_source_verified": bool(signal_source.get("signal_source_verified")),
        "signal_source": signal_source,
        "all_passed": len(failures) == 0,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    try:
        state_file.write_text(json.dumps(state, indent=2))
        print(f"\n  Evidence saved to: {state_file}")
    except OSError as e:
        print(f"\n  [WARNING] Failed to save state to {state_file}: {e}", file=sys.stderr)

    return state


def run_full_investigation(event_type: str, tool_name: str | None = None) -> dict:
    """Execute the complete hook-error RCA pipeline.

    Args:
        event_type: The hook event type (e.g., "PostToolUse", "PreToolUse")
        tool_name: Optional tool name to filter by matcher

    Returns:
        Investigation state dictionary with all findings
    """
    print(f"\n{'='*60}")
    print(f"  HOOK-ERROR RCA: {event_type}" + (f":{tool_name}" if tool_name else ""))
    print(f"{'='*60}\n")

    # ── Stage 1: Enumerate ──
    registrations = _stage1_enumerate(event_type, tool_name)

    # ── Stage 2: Isolate & Test ──
    test_results, error_log_evidence = _stage2_test(registrations, tool_name)

    # ── Stage 3: Classify & Report ──
    root_causes = _stage3_classify(
        test_results, registrations, tool_name, event_type, error_log_evidence
    )

    # ── Save State ──
    return _save_state(
        event_type, tool_name, registrations, test_results, root_causes, error_log_evidence
    )


# ==================== No-Handwave Gate ====================

DISMISSAL_PATTERNS = [
    r"\bcosmetic\b",
    r"display\s+artifact",
    r"\bnon.?blocking\b",
    r"\btransient\b",
    r"\bbenign\b",
    r"can\s+be\s+safely\s+ignored",
    r"visual\s+noise",
    r"UI\s+artifact",
    r"informational\s+only",
]

SPECIFICITY_PATTERNS = [
    r"[\w/\\]+\.py",  # Names a .py file (\w = [A-Za-z0-9_])
    r"exit\s*code\s*[012]+",  # Cites an exit code
    r"stderr",  # References stderr output
    r"cc_errors\.jsonl",  # References the error log
    r"settings\.json",  # References configuration
    r"ImportError|ModuleNotFoundError|TimeoutError|SyntaxError|OSError",
    r"line\s+\d+",  # Cites a line number
    r"file.?not.?found",  # Cites missing file
]


# Internal helper functions for no_handwave_gate (backward compatibility with dict inputs)
# NOTE: These are private helpers within hook_error_rca.py, not shared library code
def _get_verdict(result: HookTestResult | dict) -> str:
    """Get verdict from HookTestResult object or dict (for backward compatibility).

    Args:
        result: HookTestResult object or dict with 'verdict' key

    Returns:
        The verdict string
    """
    if isinstance(result, HookTestResult):
        return result.verdict
    return result.get("verdict", "")


def _get_hook_file(result: HookTestResult | dict) -> str:
    """Get hook_file from HookTestResult object or dict (for backward compatibility).

    Args:
        result: HookTestResult object or dict with 'hook_file' key

    Returns:
        The hook_file string
    """
    if isinstance(result, HookTestResult):
        return result.hook_file
    return result.get("hook_file", "")


def no_handwave_gate(
    test_results: list[HookTestResult] | list[dict],
    root_cause_statement: str,
) -> tuple[bool, str]:
    """Mechanical gate preventing cosmetic dismissal of hook errors.

    Evidence basis for design:
    - code.claude.com/docs/en/hooks: exit code semantics (0/2/other)
    - HOOK_STDERR_STYLE_GUIDE.md:9: "any stderr output" = "hook error"
    - hook_base.py:149: @hook_main prints to stderr on ALL exceptions
    - cc_errors.jsonl: 4 observed failure categories

    The gate enforces: if you say "cosmetic", you must have tested every
    matching hook and found they all pass cleanly (no stderr either).

    Args:
        test_results: List of HookTestResult objects or dicts (backward compatible)
        root_cause_statement: The root cause statement to validate

    Returns:
        (passed, reason) tuple:
        - passed: True if gate allows, False if blocked
        - reason: Explanation of the decision
    """
    if not test_results:
        return False, (
            "BLOCKED: No hooks were tested in isolation. "
            "Run: python hook_error_rca.py full <event_type> --tool <tool>"
        )

    # Explicit admission of unknown is always valid
    if re.search(
        r"root\s+cause\s+not\s+found|unknown|investigation\s+incomplete",
        root_cause_statement,
        re.IGNORECASE,
    ):
        return True, "PASSED: Explicit unknown/incomplete admission."

    has_dismissal = any(
        re.search(p, root_cause_statement, re.IGNORECASE) for p in DISMISSAL_PATTERNS
    )

    has_specificity = any(re.search(p, root_cause_statement) for p in SPECIFICITY_PATTERNS)

    if has_dismissal:
        # Only allow if ALL hooks pass with zero stderr
        all_clean = all(_get_verdict(r) == "pass" for r in test_results)
        has_stderr_hooks = any(_get_verdict(r) == "pass_with_stderr" for r in test_results)

        if not all_clean:
            failing = [r for r in test_results if _get_verdict(r) not in ("pass", "block_intent")]
            names = ", ".join(
                f"{Path(_get_hook_file(r)).name} ({_get_verdict(r)})" for r in failing[:5]
            )
            return False, (
                f"BLOCKED: Cannot dismiss as cosmetic when {len(failing)} hook(s) "
                f"have non-clean results: {names}"
            )

        if has_stderr_hooks:
            stderr_hooks = [r for r in test_results if _get_verdict(r) == "pass_with_stderr"]
            names = ", ".join(Path(_get_hook_file(r)).name for r in stderr_hooks[:5])
            return False, (
                f"BLOCKED: Cannot dismiss as cosmetic. {len(stderr_hooks)} hook(s) "
                f"exit 0 but write to stderr (which Claude Code shows as 'hook error'): "
                f"{names}. This IS the root cause per HOOK_STDERR_STYLE_GUIDE.md."
            )

        if not has_specificity:
            return False, (
                "BLOCKED: Dismissal language used without citing what was checked. "
                "List the specific hooks tested and their results."
            )

    # Non-dismissal root causes must still reference something specific
    if not has_specificity:
        return False, (
            "BLOCKED: Root cause statement does not reference a specific "
            "file, exit code, or error. Add concrete evidence."
        )

    return True, "PASSED"


# ==================== CLI ====================


def main():
    """CLI entry point."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Hook-Error RCA Utility - Enumerate and test hook registrations"
    )
    parser.add_argument("action", choices=["enumerate", "test", "full"], help="Action to perform")
    parser.add_argument("event_type", help="Hook event type (e.g., PostToolUse, PreToolUse)")
    parser.add_argument("--tool", help="Tool name filter (e.g., Task, Bash)", default=None)

    args = parser.parse_args()

    if args.action == "full":
        run_full_investigation(args.event_type, args.tool)
    elif args.action == "enumerate":
        for r in enumerate_registrations(args.event_type, args.tool):
            try:
                print(json.dumps(asdict(r), indent=2))
            except TypeError as e:
                print(f"JSON serialization error: {e}", file=sys.stderr)
                raise
    elif args.action == "test":
        regs = enumerate_registrations(args.event_type, args.tool)
        for r in regs:
            if r.matches_tool:
                result = test_hook_isolated(r, args.tool or "Bash")
                try:
                    print(json.dumps(asdict(result), indent=2))
                except TypeError as e:
                    print(f"JSON serialization error: {e}", file=sys.stderr)
                    raise


if __name__ == "__main__":
    main()
