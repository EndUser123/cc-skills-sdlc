#!/usr/bin/env python3
"""
Pattern Extractor for rca auto-learning system.

Extracts reusable search patterns from mechanism-only search misses
so the system learns and improves over time.
"""

import re
from datetime import datetime

# Symptom type classification patterns
SYMPTOM_PATTERNS = {
    "PERFORMANCE": [
        re.compile(r"Progress|Spinner|Loader|Bar", re.I),
        re.compile(r"update|render|draw|paint", re.I),
        re.compile(r"slow|flash|timeout|lag", re.I),
        re.compile(r"%|percent|complete", re.I),
    ],
    "ERROR": [
        re.compile(r"Exception|Error|Traceback", re.I),
        re.compile(r"fail|crash|abort", re.I),
        re.compile(r"raise|throw|except", re.I),
    ],
    "INTEGRATION": [
        re.compile(r"API|Client|Server|Request", re.I),
        re.compile(r"http|endpoint|route", re.I),
        re.compile(r"import|include|require", re.I),
    ],
    "INTERMITTENT": [
        re.compile(r"race|lock|mutex|semaphore", re.I),
        re.compile(r"async|await|promise|callback", re.I),
        re.compile(r"sometimes|flaky|random", re.I),
    ],
    "SECURITY": [
        re.compile(r"auth|token|password|login", re.I),
        re.compile(r"permission|access|denied", re.I),
        re.compile(r"encrypt|decrypt|hash", re.I),
    ],
}


# Functional pattern suggestions by symptom type
FUNCTIONAL_SUGGESTIONS = {
    "PERFORMANCE": [
        "yt-api:",
        "status:",
        "percent:",
        "complete:",
        "console.log",
        "print(",
        "output:",
        "display:",
    ],
    "ERROR": [
        "error:",
        "exception:",
        "fail:",
        "traceback",
        "stderr:",
        "fatal:",
        "critical:",
    ],
    "INTEGRATION": [
        "response:",
        "status:",
        "result:",
        "output:",
        "return:",
        "payload:",
        "body:",
    ],
    "INTERMITTENT": [
        "timeout:",
        "retry:",
        "attempt:",
        "state:",
        "locked:",
        "blocked:",
        "waiting:",
    ],
    "SECURITY": [
        "unauthorized:",
        "forbidden:",
        "denied:",
        "invalid:",
        "expired:",
        "missing:",
    ],
}


def classify_symptom_type(searches: list[dict]) -> str:
    """Classify symptom type from mechanism search patterns.

    Args:
        searches: List of search dicts with 'pattern' key

    Returns:
        Symptom type: PERFORMANCE, ERROR, INTEGRATION, INTERMITTENT, or SECURITY
    """
    if not searches:
        return "PERFORMANCE"  # Default

    # Combine all patterns for analysis
    all_patterns = " ".join(s.get("pattern", "") for s in searches)

    # Score each symptom type
    scores = {}
    for symptom_type, patterns in SYMPTOM_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = pattern.findall(all_patterns)
            score += len(matches)
        scores[symptom_type] = score

    # Return highest scoring type
    if not scores or max(scores.values()) == 0:
        return "PERFORMANCE"  # Default

    return max(scores, key=scores.get)


def suggest_functional_pattern(symptom_type: str, mechanism_patterns: list[str]) -> str:
    """Suggest functional search pattern based on symptom type.

    Args:
        symptom_type: PERFORMANCE, ERROR, INTEGRATION, INTERMITTENT, or SECURITY
        mechanism_patterns: List of mechanism patterns searched

    Returns:
        Suggested functional pattern string
    """
    suggestions = FUNCTIONAL_SUGGESTIONS.get(symptom_type, FUNCTIONAL_SUGGESTIONS["PERFORMANCE"])

    # Context-aware suggestion: pick most relevant based on mechanism
    mechanism_text = " ".join(mechanism_patterns)

    if "Progress" in mechanism_text or "update" in mechanism_text:
        return "yt-api:"  # Progress output
    elif "Exception" in mechanism_text or "Error" in mechanism_text:
        return "error:"  # Error messages
    elif "API" in mechanism_text or "http" in mechanism_text:
        return "response:"  # API response
    elif "async" in mechanism_text or "await" in mechanism_text:
        return "timeout:"  # Async timeout
    elif "auth" in mechanism_text or "token" in mechanism_text:
        return "denied:"  # Access denied

    # Return first suggestion for symptom type
    return suggestions[0] if suggestions else "visible-output:"


def calculate_confidence(mechanism_count: int, symptom_type: str) -> float:
    """Calculate confidence score for extracted pattern.

    Args:
        mechanism_count: Number of mechanism searches
        symptom_type: Classified symptom type

    Returns:
        Confidence score 0.0-1.0
    """
    # Base confidence from mechanism count (more searches = clearer pattern)
    base_confidence = min(mechanism_count / 5.0, 0.8)

    # Boost if mechanism searches are consistent (similar patterns)
    # This would require analyzing pattern similarity - simplified for now

    return round(base_confidence, 2)


def extract_learning_from_mechanism_search(state: dict) -> dict:
    """Extract learning from mechanism-only search sequence.

    Args:
        state: Search state with 'searches' list

    Returns:
        Learning dict with symptom_type, patterns, relationship, confidence
    """
    searches = state.get("searches", [])

    if not searches:
        return {}

    # Extract mechanism patterns (last 3-5 searches)
    mechanism_searches = [s for s in searches if s.get("type") == "mechanism"][-5:]
    mechanism_patterns = [s.get("pattern", "") for s in mechanism_searches]

    if len(mechanism_patterns) < 2:
        return {}  # Need at least 2 mechanism searches to extract pattern

    # Classify symptom type
    symptom_type = classify_symptom_type(mechanism_searches)

    # Suggest functional pattern
    functional_pattern = suggest_functional_pattern(symptom_type, mechanism_patterns)

    # Calculate confidence
    confidence = calculate_confidence(len(mechanism_patterns), symptom_type)

    # Build relationship description
    mechanism_summary = ", ".join(f'"{p}"' for p in mechanism_patterns[:3])
    if len(mechanism_patterns) > 3:
        mechanism_summary += f", and {len(mechanism_patterns) - 3} more"

    relationship = (
        f"When searching for {symptom_type} implementation "
        f"({mechanism_summary}), also search for visible symptom: "
        f'"{functional_pattern}"'
    )

    # Build learning entry
    learning = {
        "type": "rca_search_pattern",
        "symptom_type": symptom_type,
        "mechanism_patterns": mechanism_patterns,
        "functional_suggestion": functional_pattern,
        "relationship": relationship,
        "confidence": confidence,
        "created_at": datetime.now().isoformat(),
        "times_helpful": 0,
        "example_session": f"Mechanism-only search missed: {mechanism_patterns[0]}",
    }

    return learning


def format_learning_for_cks(learning: dict) -> str:
    """Format learning entry for CKS storage.

    Args:
        learning: Learning dict from extract_learning_from_mechanism_search

    Returns:
        Formatted markdown string for CKS
    """
    if not learning:
        return ""

    symptom_type = learning.get("symptom_type", "UNKNOWN")
    functional = learning.get("functional_suggestion", "")
    mechanism_str = ", ".join(learning.get("mechanism_patterns", [])[:3])
    confidence = learning.get("confidence", 0.0)
    relationship = learning.get("relationship", "")

    return f"""# RCA Search Pattern: {symptom_type}

**Symptom Type:** {symptom_type}
**Confidence:** {confidence}

## Pattern

When searching for **mechanism**: `{mechanism_str}`

**Also search for functional symptom:** `{functional}`

## Relationship

{relationship}

## Example Session

{learning.get("example_session", "Mechanism-only search detected")}

## Usage

In your RCA Step 1.5 (Multi-Angle Search), add:

```bash
grep("{functional}", "src/")
```

This searches for the visible user-facing symptom, not just implementation.

---
*Auto-extracted by rca v2.5.0 on {learning.get("created_at", "")}*"""
