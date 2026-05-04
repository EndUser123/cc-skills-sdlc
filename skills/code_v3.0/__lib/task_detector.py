#!/usr/bin/env python3
"""Task type detection for Ralph Loop auto-enable functionality.

This module provides keyword-based task type detection to automatically
enable or disable Ralph Loop based on the user's query.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class TaskType(Enum):
    """Task type enumeration."""
    IMPLEMENTATION = "implementation"
    RESEARCH = "research"


@dataclass
class TaskDetectionResult:
    """Result of task type detection."""
    task_type: TaskType
    enable_ralph_loop: bool
    confidence: float
    reasoning: str


# Implementation keywords (enable Ralph Loop)
_IMPLEMENTATION_KEYWORDS = [
    "implement",
    "refactor",
    "fix",
    "add",
    "create",
    "build",
    "develop",
]

# Research keywords (disable Ralph Loop)
_RESEARCH_KEYWORDS = [
    "research",
    "analyze",
    "document",
    "explore",
    "investigate",
    "study",
    "review",
]


def detect_task_type(query: str) -> TaskDetectionResult:
    """Detect task type from user query.

    Args:
        query: User's query or feature description

    Returns:
        TaskDetectionResult with task type, Ralph Loop decision, and confidence

    Rules:
    - Implementation tasks (implement/refactor/fix) → enable Ralph Loop
    - Research tasks (research/analyze/document) → disable Ralph Loop
    - Returns moderate confidence (0.6-0.8) for keyword matches
    - Returns low confidence (0.3-0.5) for ambiguous queries

    Note:
        Auto-detection is disabled when RALPH_LOOP_AUTO_DETECT environment variable
        is set to "false". This allows manual control override and rollback.
    """
    # Check for auto-detect disable flag
    auto_detect_disabled = os.environ.get("RALPH_LOOP_AUTO_DETECT", "true").lower() == "false"

    if auto_detect_disabled:
        # Auto-detection disabled - return RESEARCH type with Ralph Loop disabled
        # This ensures manual control when auto-detect is turned off
        return TaskDetectionResult(
            task_type=TaskType.RESEARCH,
            enable_ralph_loop=False,
            confidence=1.0,  # High confidence - this is explicit user intent
            reasoning="Auto-detection disabled via RALPH_LOOP_AUTO_DETECT=false - manual control mode",
        )
    query_lower = query.lower()

    # Check for implementation keywords
    impl_matches = [kw for kw in _IMPLEMENTATION_KEYWORDS if kw in query_lower]

    # Check for research keywords
    research_matches = [kw for kw in _RESEARCH_KEYWORDS if kw in query_lower]

    # Determine task type based on keyword matches
    if len(impl_matches) > len(research_matches):
        # Implementation task detected
        return TaskDetectionResult(
            task_type=TaskType.IMPLEMENTATION,
            enable_ralph_loop=True,
            confidence=0.7,
            reasoning=f"Implementation keywords detected: {', '.join(impl_matches)}",
        )
    elif len(research_matches) > len(impl_matches):
        # Research task detected
        return TaskDetectionResult(
            task_type=TaskType.RESEARCH,
            enable_ralph_loop=False,
            confidence=0.7,
            reasoning=f"Research keywords detected: {', '.join(research_matches)}",
        )
    else:
        # Ambiguous - default to research (safer default)
        return TaskDetectionResult(
            task_type=TaskType.RESEARCH,
            enable_ralph_loop=False,
            confidence=0.3,
            reasoning="No clear task type keywords detected - defaulting to research (safer)",
        )


def log_detection_decision(
    result: TaskDetectionResult,
    query: str,
    project_root: Path,
) -> Path:
    """Log auto-detection decision to evidence file.

    Args:
        result: Task detection result
        query: Original user query
        project_root: Project root directory

    Returns:
        Path to the evidence file created

    Raises:
        OSError: If evidence directory cannot be created
    """
    # Create evidence file path
    evidence_file = project_root / ".evidence" / "ralph_auto_detection.md"

    # CRITICAL FIX: Ensure parent directories exist before creating file
    # This prevents FileNotFoundError when project_root doesn't exist yet
    evidence_file.parent.mkdir(parents=True, exist_ok=True)

    # Generate timestamp
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build content
    content = f"""# Ralph Loop Auto-Detection Evidence

**Query:** {query}
**Timestamp:** {timestamp}

## Detection Result

- **Task Type:** {result.task_type.value}
- **Ralph Loop:** {'ENABLED' if result.enable_ralph_loop else 'DISABLED'}
- **Confidence:** {result.confidence:.2f}
- **Reasoning:** {result.reasoning}

"""

    # Write to file
    with open(evidence_file, "a", encoding="utf-8") as f:
        # Add separator if file exists
        if evidence_file.exists() and evidence_file.stat().st_size > 0:
            f.write("\n---\n\n")

        f.write(content)

    return evidence_file
