#!/usr/bin/env python3
"""Pattern Validation Framework - Prevents false positive bugs in detector modules.

Related bugs:
- unverified_stance_detector.py Bug #1: Bare "has" caused false positives
- Pattern "blocked" matched injected context keywords

This module validates detector patterns BEFORE implementation to catch:
1. Context keyword conflicts (pattern matches injected context)
2. Over-matching (pattern is too broad/common word)
3. Regex syntax errors (invalid regex patterns)
"""

import re
from typing import NamedTuple


class PatternIssue(NamedTuple):
    """Represents a single issue found during pattern validation.

    Attributes:
        pattern: The problematic pattern string
        issue: Human-readable description of the issue
        severity: "critical" | "high" | "medium"
        recommendation: Suggested fix or mitigation
    """
    pattern: str
    issue: str
    severity: str  # "critical" | "high" | "medium"
    recommendation: str


# Common words that are too broad for reliable detection
# These often appear in non-factual statements and cause false positives
COMMON_WORDS = {
    "verify", "check", "that", "this", "have", "has",
    "think", "believe", "consider", "regard", "use", "using"
}


def validate_detector_patterns(
    patterns: list[str],
    context_keywords: list[str]
) -> list[PatternIssue]:
    """Validate detector patterns against common failure modes.

    Checks performed:
    1. Context keyword conflicts - Pattern matches injected context keywords
    2. Over-matching - Pattern is a common word (too broad)
    3. Regex syntax - Pattern has invalid regex syntax

    Args:
        patterns: List of detector patterns (regex strings, keywords, phrases)
        context_keywords: List of keywords injected into context
                        (e.g., ["blocked", "verification", "evidence"])

    Returns:
        List of PatternIssue objects (empty if no issues found)

    Examples:
        >>> validate_detector_patterns(["blocked"], ["blocked"])
        [PatternIssue(pattern='blocked', severity='critical', ...)]

        >>> validate_detector_patterns([r"\\bfactual\\b"], ["blocked"])
        []
    """
    issues = []

    # Normalize context keywords to lowercase for case-insensitive matching
    context_keywords_lower = [kw.lower() for kw in context_keywords]

    for pattern in patterns:
        # Skip empty patterns (handled gracefully)
        if not pattern or pattern.isspace():
            continue

        # Check 1: Context keyword conflicts
        for keyword in context_keywords_lower:
            if keyword in pattern.lower():
                issues.append(PatternIssue(
                    pattern=pattern,
                    issue=f"Pattern matches injected context keyword '{keyword}'",
                    severity="critical",
                    recommendation=f"Use word boundaries: \\b{pattern}\\b"
                ))
                # Only report once per pattern (avoid duplicates)
                break

        # Check 2: Over-matching (common words)
        pattern_lower = pattern.lower()
        if pattern_lower in COMMON_WORDS:
            issues.append(PatternIssue(
                pattern=pattern,
                issue="Pattern is too broad (common word)",
                severity="high",
                recommendation="Add surrounding context or use phrase matching"
            ))

        # Check 3: Regex syntax validation
        try:
            re.compile(pattern)
        except re.error as e:
            issues.append(PatternIssue(
                pattern=pattern,
                issue=f"Invalid regex: {e}",
                severity="critical",
                recommendation="Fix regex syntax"
            ))

    return issues
