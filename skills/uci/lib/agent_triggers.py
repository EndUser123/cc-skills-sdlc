"""
Per-Agent Trigger Criteria for Unified Code Inspection

Defines explicit trigger patterns for agents that need more precise activation
than mode-based bundling provides. Agents can be triggered by:
1. File path patterns (e.g., "state" in path → state-machine agent)
2. Code content patterns (e.g., "match/case" → state-machine agent)
3. File extension patterns (e.g., ".py" → python-modernization)

Triggers are ADDITIVE: they fire on top of mode selection, so a triggered
agent runs even if its tier wouldn't normally be active in the current mode.

Confidence thresholds prevent noise:
- HIGH confidence: 3+ matches across patterns → strong signal
- MEDIUM confidence: 2 matches → moderate signal
- LOW confidence: 1 match → weak signal, only triggers if no other agent in category

All patterns are case-insensitive regexes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Agent trigger definitions
# Each agent can have:
#   - path_patterns: list of regexes that match file paths
#   - content_patterns: list of regexes that match code content
#   - extension_patterns: list of file extensions (with or without dot)
#   - min_confidence: minimum confidence to trigger (default 0.5)
#   - stack_with_tier: if True, triggers even if agent's tier isn't in current mode

AGENT_TRIGGERS: dict[str, dict[str, Any]] = {
    "adversarial-state-machine": {
        "description": "State-transition bugs, invalid states, TOCTOU issues",
        "path_patterns": [
            r"state",
            r"statemachine",
            r"state_machine",
            r"fsm",
            r"workflow",
            r"transition",
        ],
        "content_patterns": [
            r"\bmatch\b.*\bcase\b",  # Python match/case
            r"\bswitch\b.*\bcase\b",  # JS/Java switch
            r"state\s*=\s*[\"']",  # state = "..."
            r"valid_state",
            r"invalid_state",
            r"transition_to",
            r"next_state",
            r"current_state",
            r"on_enter",
            r"on_exit",
            r"State\s*\(",  # State class instantiation
            r"handle_[a-z_]+\(",  # handle_* event handlers
            r"process_[a-z_]+\(",  # process_* methods
        ],
        "min_confidence": 0.5,
        "stack_with_tier": False,
    },
    "adversarial-io-validation": {
        "description": "Path validation, file existence, external service assumptions",
        "path_patterns": [
            r"file",
            r"path",
            r"dir",
            r"io",
            r"fs",
            r"storage",
            r"upload",
            r"download",
        ],
        "content_patterns": [
            r"open\s*\(",  # file open
            r"Path\s*\(.*\)\s*\)",  # Path(...)
            r"path\.join",  # path.join
            r"pathlib",  # pathlib usage
            r"\.exists\(",  # exists()
            r"\.mkdir\(",  # mkdir
            r"\.rmdir\(",  # rmdir
            r"\.remove\(",  # remove
            r"\.unlink\(",  # unlink
            r"\.write_text\(",  # write_text
            r"\.read_text\(",  # read_text
            r"\.read_bytes\(",  # read_bytes
            r"shutil\.",  # shutil operations
            r"os\.remove",  # os.remove
            r"os\.path",  # os.path operations
            r"file_exists",  # file_exists check
            r"ensure_dir",  # ensure directory exists
            r"validate_path",  # path validation
            r"sanitize_path",  # path sanitization
        ],
        "min_confidence": 0.5,
        "stack_with_tier": False,
    },
    "adversarial-invariants": {
        "description": "ID collision, referential integrity, uniqueness constraints",
        "path_patterns": [
            r"id",
            r"uuid",
            r"unique",
            r"constraint",
            r"integrity",
            r"transaction",
            r"atomic",
        ],
        "content_patterns": [
            r"\bunique\b",
            r"\buuid\b",
            r"constraint",
            r"foreign.?key",
            r"referential.?integrity",
            r"\batomic\b",
            r"transaction",
            r"rollback",
            r"commit",
            r"dedupe",
            r"deduplicate",
            r"duplicate.*check",
            r"id\s*=",  # ID assignment
            r"generate_id",
            r"new_id",
            r"cursor\.lastrowid",
            r"RETURNING.*id",
            r"ON CONFLICT",
            r"UNIQUE\s+CONSTRAINT",
        ],
        "min_confidence": 0.5,
        "stack_with_tier": False,
    },
    "adversarial-compliance": {
        "description": "Spec/schema validation, API contracts, type hints",
        "path_patterns": [
            r"schema",
            r"contract",
            r"api",
            r"interface",
            r"validation",
            r"model",
            r"schema",
        ],
        "content_patterns": [
            r"class\s+\w+.*Validator",  # Validator classes
            r"validate\(",
            r"@validator",
            r"@field_validator",
            r"pydantic",
            r"BaseModel",
            r"schema",
            r"json_schema",
            r"type.*hint",
            r"TypedDict",
            r"Protocol",
            r"Interface",
            r"api.*contract",
            r"request.*validation",
            r"response.*validation",
            r"OpenAPI",
            r"swagger",
        ],
        "min_confidence": 0.5,
        "stack_with_tier": False,
    },
    "python-modernization": {
        "description": "Python 3.12+ idioms, type hints, modern patterns",
        "path_patterns": [],
        "content_patterns": [
            r"from\s+__future__\s+import",
            r"type:\s*ignore",
            r"Optional\[",
            r"List\[",
            r"Dict\[",
            r"Union\[",
            r"@dataclass",
            r"@cache",
            r"@lru_cache",
            r"functools\.cache",
            r"match\s+.*:\s*$",  # match statement
            r"case\s+.*:",  # case clause
            r" walrus ",
            r":=",
            r"python_version",
            r"sys\.version",
        ],
        "extension_patterns": [".py"],
        "min_confidence": 0.4,
        "stack_with_tier": False,
    },
}


@dataclass
class TriggerMatch:
    """A single trigger match for an agent."""

    agent_name: str
    match_type: str  # "path" | "content" | "extension"
    pattern: str
    file_path: str = ""


@dataclass
class AgentTriggerResult:
    """Result of trigger evaluation for a single agent."""

    agent_name: str
    triggered: bool
    confidence: float  # 0.0 - 1.0
    path_matches: int = 0
    content_matches: int = 0
    extension_matches: int = 0
    triggered_by: list[TriggerMatch] = field(default_factory=list)


def evaluate_agent_triggers(
    file_paths: list[str],
    file_contents: dict[str, str] | None = None,
) -> dict[str, AgentTriggerResult]:
    """
    Evaluate trigger criteria for all agents.

    Args:
        file_paths: List of file paths to scan
        file_contents: Optional dict of file_path -> content for content scanning.
                      If None, files are read from disk.

    Returns:
        Dict mapping agent_name -> AgentTriggerResult
    """
    results: dict[str, AgentTriggerResult] = {}

    for agent_name, trigger_def in AGENT_TRIGGERS.items():
        result = _evaluate_single_agent(agent_name, trigger_def, file_paths, file_contents)
        results[agent_name] = result

    return results


def _evaluate_single_agent(
    agent_name: str,
    trigger_def: dict[str, Any],
    file_paths: list[str],
    file_contents: dict[str, str] | None,
) -> AgentTriggerResult:
    """Evaluate triggers for a single agent."""
    matches: list[TriggerMatch] = []
    path_matches = 0
    content_matches = 0
    extension_matches = 0

    path_patterns = trigger_def.get("path_patterns", [])
    content_patterns = trigger_def.get("content_patterns", [])
    extension_patterns = trigger_def.get("extension_patterns", [])
    min_confidence = trigger_def.get("min_confidence", 0.5)

    # Evaluate path patterns
    for pattern_str in path_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        for file_path in file_paths:
            if pattern.search(file_path):
                matches.append(
                    TriggerMatch(
                        agent_name=agent_name,
                        match_type="path",
                        pattern=pattern_str,
                        file_path=file_path,
                    )
                )
                path_matches += 1

    # Evaluate extension patterns
    for ext in extension_patterns:
        if not ext.startswith("."):
            ext = "." + ext
        for file_path in file_paths:
            if file_path.endswith(ext):
                matches.append(
                    TriggerMatch(
                        agent_name=agent_name,
                        match_type="extension",
                        pattern=ext,
                        file_path=file_path,
                    )
                )
                extension_matches += 1

    # Evaluate content patterns
    for pattern_str in content_patterns:
        pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
        for file_path in file_paths:
            content = _get_file_content(file_path, file_contents)
            if content and pattern.search(content):
                matches.append(
                    TriggerMatch(
                        agent_name=agent_name,
                        match_type="content",
                        pattern=pattern_str,
                        file_path=file_path,
                    )
                )
                content_matches += 1

    # Calculate confidence
    total_matches = path_matches + content_matches + extension_matches
    if total_matches == 0:
        confidence = 0.0
    elif total_matches == 1:
        confidence = 0.3  # LOW - single match
    elif total_matches == 2:
        confidence = 0.6  # MEDIUM - two matches
    else:
        confidence = min(1.0, 0.6 + (total_matches - 2) * 0.1)  # HIGH

    triggered = confidence >= min_confidence

    return AgentTriggerResult(
        agent_name=agent_name,
        triggered=triggered,
        confidence=confidence,
        path_matches=path_matches,
        content_matches=content_matches,
        extension_matches=extension_matches,
        triggered_by=matches,
    )


def _get_file_content(
    file_path: str,
    file_contents: dict[str, str] | None,
) -> str:
    """Get file content from cache or disk."""
    if file_contents and file_path in file_contents:
        return file_contents[file_path]
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return ""


def get_triggered_agents(
    file_paths: list[str],
    file_contents: dict[str, str] | None = None,
    current_mode: str = "standard",
    current_agents: list[str] | None = None,
) -> list[str]:
    """
    Get list of agents to add based on trigger evaluation.

    Args:
        file_paths: Files being reviewed
        file_contents: Optional cached file contents
        current_mode: Current review mode (triage|standard|deep|comprehensive)
        current_agents: Agents already selected by mode

    Returns:
        List of additional agent names to add
    """
    results = evaluate_agent_triggers(file_paths, file_contents)
    current_agents_set: set[str] = set(current_agents or [])

    tier_map = {
        "triage": ["core"],
        "standard": ["core", "extended"],
        "deep": ["core", "extended"],
        "comprehensive": ["core", "extended", "comprehensive"],
    }
    active_tiers = tier_map.get(current_mode, ["core", "extended"])

    from .agent_registry import AGENT_REGISTRY

    additional_agents = []
    for agent_name, result in results.items():
        if not result.triggered:
            continue
        if agent_name in current_agents_set:
            continue

        # Check if agent's tier is active in current mode
        agent_tier = AGENT_REGISTRY.get(agent_name, {}).get("tier", "extended")
        stack_with_tier = AGENT_TRIGGERS.get(agent_name, {}).get("stack_with_tier", False)

        if agent_tier in active_tiers:
            # Agent already covered by mode, no need to add
            continue

        # Only add if confidence is high enough or stack_with_tier
        if result.confidence >= 0.5 or stack_with_tier:
            additional_agents.append(agent_name)

    return additional_agents


def format_trigger_report(results: dict[str, AgentTriggerResult]) -> str:
    """
    Format trigger evaluation results as a readable string.

    Returns empty string if no agents were triggered.
    """
    triggered = {name: r for name, r in results.items() if r.triggered}

    if not triggered:
        return ""

    lines = ["", "### Agent Triggers (additive)", ""]
    for name, result in sorted(triggered.items(), key=lambda x: -x[1].confidence):
        conf_pct = int(result.confidence * 100)
        lines.append(
            f"- **{name}** ({conf_pct}% confidence) — "
            f"{result.path_matches} path, {result.content_matches} content"
        )
        for match in result.triggered_by[:3]:
            lines.append(f"  - {match.match_type}: `{match.pattern}` in `{match.file_path}`")

    return "\n".join(lines)
