#!/usr/bin/env python3
"""
CKS Integration for rca auto-learning system.

Stores learned search patterns in Constitutional Knowledge System (CKS)
and retrieves them for future RCA sessions.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
CKS_DIR = CLAUDE_HOME / "memory" / "cks"
RCA_PATTERNS_DIR = CKS_DIR / "rca_patterns"


def store_rca_pattern(learning: dict) -> bool:
    """Store RCA pattern learning in CKS.

    Args:
        learning: Learning dict from pattern_extractor.extract_learning

    Returns:
        True if stored successfully, False otherwise
    """
    if not learning or learning.get("confidence", 0) < 0.5:
        # Low confidence patterns not worth storing
        return False

    try:
        # Ensure directory exists
        RCA_PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

        # Generate filename from symptom type and timestamp
        symptom_type = learning.get("symptom_type", "UNKNOWN")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symptom_type}_{timestamp}.md"
        filepath = RCA_PATTERNS_DIR / filename

        # Format as markdown for CKS
        from pattern_extractor import format_learning_for_cks

        content = format_learning_for_cks(learning)

        # Write to file
        filepath.write_text(content, encoding="utf-8")

        # Also write JSON metadata for programmatic access
        meta_filepath = RCA_PATTERNS_DIR / f"{symptom_type}_{timestamp}.json"
        meta_filepath.write_text(json.dumps(learning, indent=2), encoding="utf-8")

        return True

    except Exception as e:
        # Graceful degradation - CKS storage failure should not break RCA
        print(f"[RCA_CKS] Failed to store pattern: {e}", file=sys.stderr)
        return False


def query_rca_patterns(symptom_type: str = None) -> list[dict]:
    """Query CKS for learned RCA patterns.

    Args:
        symptom_type: Optional filter by symptom type (PERFORMANCE, ERROR, etc.)

    Returns:
        List of pattern learning dicts
    """
    if not RCA_PATTERNS_DIR.exists():
        return []

    patterns = []

    try:
        # Read all JSON metadata files
        for json_file in RCA_PATTERNS_DIR.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))

                # Filter by symptom type if specified
                if symptom_type and data.get("symptom_type") != symptom_type:
                    continue

                # Only return high-confidence patterns
                if data.get("confidence", 0) >= 0.5:
                    patterns.append(data)

            except (OSError, json.JSONDecodeError):
                continue

        # Sort by confidence (highest first)
        patterns.sort(key=lambda p: p.get("confidence", 0), reverse=True)

        return patterns

    except Exception as e:
        print(f"[RCA_CKS] Failed to query patterns: {e}", file=sys.stderr)
        return []


def format_patterns_for_workflow(symptom_type: str = None) -> str:
    """Format learned patterns for display in RCA workflow.

    Args:
        symptom_type: Optional filter by symptom type

    Returns:
        Formatted markdown string with pattern suggestions
    """
    patterns = query_rca_patterns(symptom_type)

    if not patterns:
        return ""

    output = ["## Learned Search Patterns from CKS\n"]
    output.append("System has learned these patterns from previous RCA sessions:\n")

    for i, pattern in enumerate(patterns[:5], 1):  # Show top 5
        symptom = pattern.get("symptom_type", "UNKNOWN")
        functional = pattern.get("functional_suggestion", "")
        mechanisms = pattern.get("mechanism_patterns", [])[:3]
        confidence = pattern.get("confidence", 0.0)
        relationship = pattern.get("relationship", "")

        output.append(f"### Pattern {i}: {symptom} (confidence: {confidence})")
        output.append(f"\n**Mechanism patterns searched:** {', '.join(mechanisms)}")
        output.append(f"\n**Also search for:** `{functional}`")
        output.append(f"\n**Relationship:** {relationship}")
        output.append("\n---\n")

    return "\n".join(output)


def get_functional_suggestions_for_mechanism(mechanism_pattern: str) -> list[str]:
    """Get functional search suggestions based on mechanism pattern.

    Args:
        mechanism_pattern: The mechanism pattern being searched

    Returns:
        List of suggested functional patterns
    """
    # Query all patterns
    all_patterns = query_rca_patterns()

    # Find patterns where mechanism matches
    suggestions = []

    for pattern in all_patterns:
        mechanism_patterns = pattern.get("mechanism_patterns", [])

        # Check if this mechanism pattern is similar to stored patterns
        for stored_mechanism in mechanism_patterns:
            if (
                mechanism_pattern.lower() in stored_mechanism.lower()
                or stored_mechanism.lower() in mechanism_pattern.lower()
            ):
                # Found match - add functional suggestion
                functional = pattern.get("functional_suggestion", "")
                if functional and functional not in suggestions:
                    suggestions.append(functional)

    return suggestions


if __name__ == "__main__":
    # Test: Store and query a pattern
    test_learning = {
        "type": "rca_search_pattern",
        "symptom_type": "PERFORMANCE",
        "mechanism_patterns": ["Progress(", "class Progress", "def update"],
        "functional_suggestion": "yt-api:",
        "relationship": "When searching progress implementation, also search for visible output",
        "confidence": 0.8,
        "created_at": datetime.now().isoformat(),
        "times_helpful": 0,
        "example_session": "Test pattern",
    }

    print("Storing test pattern...")
    success = store_rca_pattern(test_learning)
    print(f"Stored: {success}")

    print("\nQuerying PERFORMANCE patterns...")
    patterns = query_rca_patterns("PERFORMANCE")
    print(f"Found {len(patterns)} patterns")
    for p in patterns:
        print(f"  - {p.get('symptom_type')}: {p.get('functional_suggestion')}")

    print("\nFormatted output:")
    print(format_patterns_for_workflow("PERFORMANCE"))
