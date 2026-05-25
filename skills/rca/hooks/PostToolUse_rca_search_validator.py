#!/usr/bin/env python3
"""
PostToolUse: Search validator for /rca workflow.
Detects mechanism-only searches and warns when functional search is missing.

This hook enforces multi-angle search strategy in real-time by:
1. Tracking grep patterns used during investigation
2. Classifying searches as mechanism, functional, temporal, or contextual
3. Detecting when 3+ consecutive mechanism searches occur without functional search
4. Warning user with suggested functional search pattern

Example warning:
    ⚠️ MECHANISM-ONLY SEARCH DETECTED
    You've searched for implementation patterns 3 times.
    Consider adding functional search for visible symptom:
      grep("yt-api:", "src/")
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
STATE_DIR = Path(os.environ.get("DEBUG_RCA_STATE_DIR", CLAUDE_HOME / "state" / "rca"))
SEARCH_STATE_FILE = STATE_DIR / "search_validator.json"

# Import auto-logging decorator (optional)
_hooks_lib = CLAUDE_HOME / "hooks" / "__lib"
if _hooks_lib.exists():
    sys.path.insert(0, str(_hooks_lib))
    try:
        from hook_base import hook_main
    except ImportError:
        hook_main = lambda f: f  # Fallback: no-op decorator
else:
    hook_main = lambda f: f  # Fallback: no-op decorator


# FileLock for cross-terminal state file safety
try:
    import portalocker

    class FileLock:
        def __init__(self, lock_path, timeout=5.0):
            self.lock_path = Path(lock_path)
            self.timeout = timeout
            self.lock_file = None

        def __enter__(self):
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.lock_file = open(self.lock_path, "w")
                portalocker.lock(self.lock_file, portalocker.LOCK_EX)
            except Exception:
                return self
            return self

        def __exit__(self, *args):
            if self.lock_file:
                try:
                    self.lock_file.close()
                except Exception:
                    pass
except ImportError:

    class FileLock:
        def __init__(self, lock_path, timeout=5.0):
            self.lock_path = lock_path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass


# Search pattern classification
# Mechanism: How is it implemented? (code structure, classes, functions)
MECHANISM_PATTERNS = [
    re.compile(r"Progress\(\)"),  # Rich Progress contexts
    re.compile(r"class\s+\w+"),  # Class definitions
    re.compile(r"def\s+\w+"),  # Function definitions
    re.compile(r"update\(\)"),  # State update functions
    re.compile(r"render|draw|paint", re.I),  # Rendering operations
    re.compile(r"import\s+\w+"),  # Import statements
    re.compile(r"from\s+\w+"),  # From imports
    re.compile(r"async\s+def"),  # Async functions
    re.compile(r"@.* decorator"),  # Decorators
]

# Functional: What produces visible symptom? (user-facing output)
FUNCTIONAL_PATTERNS = [
    re.compile(r"yt-api:"),  # VISIBLE: "yt-api: 54%" output
    re.compile(r"status\s*:"),  # Progress bars, counters
    re.compile(r"console\.log|print\("),  # Console output
    re.compile(r"error\s*:", re.I),  # Error messages
    re.compile(r"exception", re.I),  # Exceptions
    re.compile(r"traceback", re.I),  # Tracebacks
    re.compile(r"warning", re.I),  # Warnings
    re.compile(r"\d+%"),  # Percentage displays
    re.compile(r"<[^>]+>"),  # HTML/XML tags in output
]

# Temporal: What changed recently? (git, timestamps)
TEMPORAL_PATTERNS = [
    re.compile(r"git\s+(log|diff)"),
    re.compile(r"changed?|recent|latest", re.I),
    re.compile(r"\d{4}-\d{2}-\d{2}"),  # Dates
]

# Contextual: What calls it/related code? (imports, references)
CONTEXTUAL_PATTERNS = [
    re.compile(r"from\s+.*\s+import"),
    re.compile(r"__main__|__name__"),
    re.compile(r"if\s+__name__"),
]


# Constants
MAX_STDIN_SIZE = 1 * 1024 * 1024  # 1MB max payload size
MECHANISM_ONLY_THRESHOLD = 3  # Warn after 3 mechanism searches without functional
STATE_TTL_MINUTES = 120  # State expires after 2 hours


def validate_stdin_payload(raw_stdin: str) -> dict:
    """Validate stdin payload with size and schema checks."""
    if len(raw_stdin.encode("utf-8")) > MAX_STDIN_SIZE:
        return {}

    try:
        payload = json.loads(raw_stdin)
    except json.JSONDecodeError:
        return {}

    required_keys = {"tool_name", "tool_input", "tool_response"}
    if not required_keys.issubset(payload.keys()):
        return {}

    if not isinstance(payload.get("tool_name"), str):
        return {}

    return payload


def classify_search_pattern(pattern: str) -> str:
    """Classify a grep search pattern by search angle.

    Returns: 'mechanism', 'functional', 'temporal', 'contextual', or 'unknown'
    """
    if not pattern:
        return "unknown"

    # Check each category (order matters for precision)
    for regex in FUNCTIONAL_PATTERNS:
        if regex.search(pattern):
            return "functional"

    for regex in TEMPORAL_PATTERNS:
        if regex.search(pattern):
            return "temporal"

    for regex in CONTEXTUAL_PATTERNS:
        if regex.search(pattern):
            return "contextual"

    for regex in MECHANISM_PATTERNS:
        if regex.search(pattern):
            return "mechanism"

    # If no pattern matched, check if it looks like code (default to mechanism)
    # Common code patterns: identifiers, parens, dots
    if re.search(r"\w+\(|\w+\.\w+|\w+\[", pattern):
        return "mechanism"

    return "unknown"


def get_current_terminal_id() -> str:
    """Get the current Claude Code terminal ID from environment."""
    return os.environ.get("CLAUDE_TERMINAL_ID", "").strip()


def load_search_state() -> dict:
    """Load search state from file, respecting TTL and terminal ID."""
    current_terminal_id = get_current_terminal_id()

    if not SEARCH_STATE_FILE.exists():
        return {}

    try:
        with FileLock(SEARCH_STATE_FILE.parent / ".lock"):
            data = json.loads(SEARCH_STATE_FILE.read_text(encoding="utf-8"))

            # Check terminal ID match (multi-terminal safety)
            if data.get("terminal_id") and data.get("terminal_id") != current_terminal_id:
                # Different terminal - start fresh
                return {}

            # Check TTL
            created_at = data.get("created_at")
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at)
                    if datetime.now() - created_dt > timedelta(minutes=STATE_TTL_MINUTES):
                        # State expired
                        return {}
                except (ValueError, TypeError):
                    pass

            return data
    except (OSError, json.JSONDecodeError):
        return {}


def save_search_state(state: dict) -> None:
    """Save search state to file with terminal ID."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    state["terminal_id"] = get_current_terminal_id()
    state["updated_at"] = datetime.now().isoformat()

    if "created_at" not in state:
        state["created_at"] = state["updated_at"]

    try:
        with FileLock(SEARCH_STATE_FILE.parent / ".lock"):
            SEARCH_STATE_FILE.write_text(json.dumps(state, indent=2))
    except OSError:
        pass


def extract_grep_pattern(tool_input: dict) -> str:
    """Extract grep pattern from Grep tool input."""
    if not isinstance(tool_input, dict):
        return ""

    pattern = tool_input.get("pattern", "")
    if isinstance(pattern, str):
        return pattern

    return ""


def should_warn_user(state: dict) -> tuple[bool, str]:
    """Check if we should warn user about mechanism-only searches.

    Returns: (should_warn, warning_message)
    """
    searches = state.get("searches", [])

    # Need at least MECHANISM_ONLY_THRESHOLD searches
    if len(searches) < MECHANISM_ONLY_THRESHOLD:
        return False, ""

    # Check if ANY functional search exists in entire session
    has_functional = any(s.get("type") == "functional" for s in searches)

    # If user has done any functional search, don't warn
    if has_functional:
        return False, ""

    # Check last N searches for mechanism-only pattern
    recent_searches = searches[-MECHANISM_ONLY_THRESHOLD:]

    # Count mechanism searches in last N
    mechanism_count = sum(1 for s in recent_searches if s.get("type") == "mechanism")

    # Warn if last N searches are all mechanism and NO functional search ever
    if mechanism_count >= MECHANISM_ONLY_THRESHOLD:
        # Build suggested functional search based on context
        last_pattern = recent_searches[-1].get("pattern", "")

        # Suggest common functional searches
        suggestions = [
            'grep("yt-api:", "src/")',  # Progress output
            'grep("error:", "src/")',  # Error messages
            'grep("status:", "src/")',  # Status indicators
            'grep("traceback", "src/")',  # Tracebacks
            'grep("print(", "src/")',  # Print statements
        ]

        # Add context-aware suggestion if possible
        if "Progress" in last_pattern:
            suggested = 'grep("yt-api:", "src/")  # Visible progress output'
        elif "class" in last_pattern or "def" in last_pattern:
            suggested = 'grep("error:", "src/")    # Error messages'
        else:
            suggested = suggestions[0]

        warning = f"""⚠️  MECHANISM-ONLY SEARCH DETECTED

You've searched for implementation patterns {MECHANISM_ONLY_THRESHOLD} times without searching for visible symptoms.

Recent searches:
{chr(10).join(f"  - {s.get('pattern', '')}" for s in recent_searches)}

Consider adding functional search for what the USER sees:
  {suggested}

See SKILL.md Step 1.5: Multi-Angle Search templates for examples."""
        return True, warning

    return False, ""


@hook_main
def _normalize_stdout(data: dict) -> dict:
    """Normalize hook output to Claude Code Zod-valid schema."""
    if data.get('decision') == 'allow':
        return {'decision': 'approve'}
    if data.get('decision') == 'block':
        return {'decision': 'block', 'reason': data.get('reason', '')}
    if 'allow' in data:
        if data['allow'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'continue' in data:
        if data['continue'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'ok' in data:
        return {'decision': 'approve'}
    return data


def main():
    """Entry point - validate search patterns and warn if needed."""
    # Read and validate stdin
    raw_stdin = sys.stdin.read()
    if not raw_stdin.strip():
        print(json.dumps({}))
        sys.exit(0)

    payload = validate_stdin_payload(raw_stdin)
    if not payload:
        print(json.dumps({}))
        sys.exit(0)

    # Only process Grep tool
    tool_name = payload.get("tool_name", "")
    if tool_name != "Grep":
        print(json.dumps({}))
        sys.exit(0)

    # Extract grep pattern
    tool_input = payload.get("tool_input", {})
    pattern = extract_grep_pattern(tool_input)

    if not pattern:
        print(json.dumps({}))
        sys.exit(0)

    # Classify search pattern
    search_type = classify_search_pattern(pattern)

    # Load existing state
    state = load_search_state()

    # Initialize state if needed
    if "searches" not in state:
        state["searches"] = []

    # Add this search to state
    state["searches"].append(
        {
            "pattern": pattern,
            "type": search_type,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Keep only last 20 searches
    if len(state["searches"]) > 20:
        state["searches"] = state["searches"][-20:]

    # Check if we should warn user
    should_warn, warning_message = should_warn_user(state)

    # Save state
    save_search_state(state)

    # Build result
    result = {}

    if should_warn:
        # Print warning to stdout (Claude Code will display it)
        print(warning_message, file=sys.stderr)
        result["warning"] = "mechanism_only_search_detected"
        result["suggestion"] = "Add functional search for visible symptom"

        # AUTO-LEARNING: Extract and store pattern in CKS
        try:
            from cks_integration import store_rca_pattern
            from pattern_extractor import extract_learning_from_mechanism_search

            learning = extract_learning_from_mechanism_search(state)
            if learning and learning.get("confidence", 0) >= 0.5:
                stored = store_rca_pattern(learning)
                if stored:
                    # Add info message about pattern storage
                    symptom = learning.get("symptom_type", "UNKNOWN")
                    functional = learning.get("functional_suggestion", "")
                    print(
                        f"\n[CKS] Learned pattern stored: {symptom} → search for '{functional}'",
                        file=sys.stderr,
                    )
        except ImportError:
            # Pattern extraction modules not available - skip auto-learning
            pass
        except Exception as e:
            # Auto-learning failure should not break RCA workflow
            print(f"[CKS] Failed to store pattern: {e}", file=sys.stderr)

    # Also print JSON result
    print(json.dumps(_normalize_stdout(result)))
    sys.exit(0)


if __name__ == "__main__":
    main()
