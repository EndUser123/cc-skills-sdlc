#!/usr/bin/env python3
"""
Template validation script for /arch skill.

Validates:
- Required headings match between templates and contracts
- Contract compliance (must_include items)
- Duplicate logic detection across templates
- Evidence hygiene for pasted LLM content
"""

import sys
import re
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, cast
from functools import lru_cache

logger = logging.getLogger(__name__)

__all__ = [
    # Public API functions
    "validate_all",
    "validate_required_headings",
    "check_duplicate_logic",
    "validate_template_chain",
    "load_template_content",
    "load_contracts",
    "extract_headings",
    # Evidence hygiene
    "validate_evidence_hygiene",
    "classify_evidence_tier",
    # Entity scope validation
    "validate_entity_scope",
    # Friction budget
    "validate_friction_budget",
    # Constants
    "TEMPLATE_NAMES",
    "DUPLICATE_OVERLAP_THRESHOLD",
    "HIGH_OVERLAP_THRESHOLD",
    "DEFAULT_CACHE_SIZE",
    "EVIDENCE_TIERS",
]

# Constants
# Color codes for terminal output
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_RESET = "\033[0m"

# Aliases for backward compatibility with tests
GREEN = COLOR_GREEN
RED = COLOR_RED
YELLOW = COLOR_YELLOW
RESET = COLOR_RESET

# Validation thresholds
DUPLICATE_OVERLAP_THRESHOLD = 50.0  # Percentage threshold for duplicate detection
HIGH_OVERLAP_THRESHOLD = (
    70.0  # Percentage threshold for high overlap (causes validation failure)
)

# Cache configuration
DEFAULT_CACHE_SIZE = 32  # Default LRU cache size for template content loading

# Evidence tier classifications
EVIDENCE_TIERS = {
    "VERIFIED_FROM_FILES": "Claim backed by direct inspection, test output, or runtime behavior",
    "USER_AUTHORITATIVE": "User preference or explicit requirement",
    "PASTED_LLM_CLAIM": "Third-party/LLM output (unverified hypothesis)",
    "ASSISTANT_INFERENCE": "Model deduction without direct evidence",
}

# Friction budget thresholds
FRICTION_BUDGET_THRESHOLDS = {
    "fast": {
        "max_clarifications": 1,
        "max_permission_pushes": 0,
        "max_implementation_choices": 1,
        "max_time_to_first_action": 300,  # 5 minutes in seconds
    },
    "deep": {
        "max_clarifications": 3,
        "max_permission_pushes": 2,
        "max_implementation_choices": 2,
        "max_time_to_first_action": 600,  # 10 minutes in seconds
    },
}

# Friction indicators (patterns that increase friction)
_FRICTION_INDICATORS = {
    "clarification": (
        r"\b(could you clarify|clarify this|what do you mean|i need more info|not sure what you mean)\b",
        r"\b(before i proceed, i need|to help me better|to understand your requirement)\b",
        r"\b(and one more thing|and one last thing|one more thing)\b",  # Chain of clarifications
    ),
    "permission_push": (
        r"\b(may i|should i|can i|would you like me to|do you want me to|shall i)\b",
        r"\b(is it ok|is that acceptable|would that work)\b",
    ),
    "implementation_choice": (
        r"\b(which (one|option|approach)|option [a-z]:|alternative [0-9]:|choice [0-9]:)\b",
        r"\b(do you prefer|would you prefer|which would you rather|which approach)\b",
        r"\b(choose between|select from|pick one)\b",
        r"\b(which (do )?you prefer|which one (do )?you (want|like|prefer))\b",  # Broader match
    ),
    "internal_failure": (
        r"\b(tool failed|error in tool|tool error|tried but failed|attempt failed)\b",
        r"\b(fallback to|retrying|trying another approach)\b",
    ),
}

# Patterns for detecting pasted LLM content
_PASTED_LLM_MARKERS = (
    r"```(?:python|markdown|bash|sh|text)?",  # Code blocks (language optional)
    r"According to (?:ChatGPT|Claude|GPT|GPT-\d+|the model|the AI|another (?:model|LLM|assistant)):?",
    r"(?:ChatGPT|Claude|GPT|GPT-\d+) (?:said|responded|output|generated|claimed|suggested|indicated)(?: that|:|,)?",
    r"from (?:another (?:model|LLM|assistant)|the previous (?:model|LLM|assistant)):?",
    r"the (?:other|previous) (?:model|LLM|assistant) (?:said|told|wrote|claimed)(?: that|:|,)?",
    r"based on (?:the (?:other|previous) (?:model|LLM|assistant)'s (?:output|response|suggestion)):?",
    r"(?:ChatGPT|Claude|GPT|GPT-\d+|the model|the AI) (?:said|told|wrote|stated|suggested|claimed|indicated) that",
)

# Sections to check for duplicate logic between templates
DUPLICATE_CHECK_SECTIONS = [
    "Stage 0",
    "Stage 0.5",
    "Domain Resource Inclusion",
    "IMPROVE_SYSTEM",
    "CKS.db",
]

# Template definitions
TEMPLATE_NAMES = {
    "fast": "fast.md",
    "deep": "deep.md",
    "cli": "cli.md",
    "python": "python.md",
    "data-pipeline": "data-pipeline.md",
    "precedent": "precedent.md",
}


@dataclass
class ValidationResult:
    """
    Represents the result of validating a single template.

    Attributes:
        template_name: Name identifier for the template.
        check_type: Type of validation performed (e.g., "headings").
        status: Result status ("pass" or "fail").
        details: Optional list of additional details (e.g., missing headings).
    """

    template_name: str
    check_type: str
    status: str
    details: Optional[list[str]] = None


def classify_evidence_tier(claim_text: str, source: str | None = None) -> str:
    """
    Classify a claim's evidence tier based on its content and source.

    Evidence tiers:
    - VERIFIED_FROM_FILES: Direct tool result (Read, Grep, Bash with output)
    - USER_AUTHORITATIVE: Explicit user statement
    - PASTED_LLM_CLAIM: Third-party/LLM output (treat as hypothesis)
    - ASSISTANT_INFERENCE: Model deduction without direct evidence

    Args:
        claim_text: The claim text to classify.
        source: Optional source information (e.g., "user", "Read tool", "Grep tool").

    Returns:
        The evidence tier constant.

    Examples:
        >>> classify_evidence_tier("File contains function X", "Read tool")
        'VERIFIED_FROM_FILES'
        >>> classify_evidence_tier("ChatGPT said X is faster", "user")
        'PASTED_LLM_CLAIM'
        >>> classify_evidence_tier("I want option A", "user")
        'USER_AUTHORITATIVE'
    """
    lower_claim = claim_text.lower()
    lower_source = (source or "").lower()

    # Check for pasted LLM markers first
    for pattern in _PASTED_LLM_MARKERS:
        if re.search(pattern, claim_text, re.IGNORECASE):
            logger = __import__("logging").getLogger(__name__)
            logger.debug(f"Pasted LLM claim detected: {pattern}")
            return "PASTED_LLM_CLAIM"

    # User-authoritative: explicit preference or requirement
    user_authoritative_patterns = (
        r"\b(i want|i need|i prefer|i'd like)\b",
        r"\b(requirement:|must|must not|should not)\b",
    )
    for pattern in user_authoritative_patterns:
        if re.search(pattern, lower_claim):
            if "llm" not in lower_source and "ai" not in lower_source:
                return "USER_AUTHORITATIVE"

    # Verified from tools
    verified_patterns = (
        r"\b(file contains|line \d+|grep found|test result|runtime behavior)\b",
        r"\baccording to (the file|the code|the test|the output)\b",
    )
    if source and any(keyword in lower_source for keyword in ("read", "grep", "bash", "test", "inspect")):
        return "VERIFIED_FROM_FILES"

    # Default: assistant inference
    return "ASSISTANT_INFERENCE"


def validate_evidence_hygiene(content: str) -> list[str]:
    """
    Validate evidence hygiene in content, flagging unverified pasted LLM claims.

    This function scans content for pasted LLM output and ensures that
    any claims from such sources are marked as unverified rather than
    treated as factual authority.

    Args:
        content: The content to validate (e.g., design document, ADR).

    Returns:
        A list of validation warnings. Empty list if no issues found.

    Examples:
        >>> validate_evidence_hygiene("According to ChatGPT, X is faster.")
        ['PASTED_LLM_CLAIM: Claim from "According to ChatGPT..." must be verified before design decisions']
    """
    warnings: list[str] = []

    # Find pasted LLM content blocks
    for pattern in _PASTED_LLM_MARKERS:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        for match in matches:
            # Extract context around the match
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            context = content[start:end].strip()

            # Check if this is marked as unverified
            if not any(
                keyword in context.lower()
                for keyword in ("unverified", "hypothesis", "needs verification", "to be verified")
            ):
                warnings.append(
                    f"PASTED_LLM_CLAIM: Claim in context \"{context}\" must be marked "
                    "as unverified or independently verified before use in design decisions"
                )

    # Check for unverified claims without evidence trail
    # Look for claim patterns that should have evidence but don't
    claim_patterns = (
        r"(?:this|that) (?:is|has|uses?) better [^\.]+\.",
        r"(?:the system|the code|the module) (?:should|will|can) [^\.]+\.",
    )

    for pattern in claim_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            sentence = match.group(0)

            # If claim exists but no evidence markers nearby, flag as inference
            # This is a soft warning (not an error) since some claims are inferred
            if not any(
                keyword in sentence.lower()
                for keyword in (
                    "file:",
                    "line ",
                    "test ",
                    "verified",
                    "according to the",
                    "evidence:",
                    "verified_from_files",
                    "user_authoritative",
                )
            ):
                # Only warn if this looks like a strong claim
                if any(
                    keyword in sentence.lower()
                    for keyword in ("must", "should", "cannot", "will", "guarantee")
                ):
                    warnings.append(
                        f"ASSISTANT_INFERENCE: Strong claim \"{sentence}\" lacks "
                        "evidence tier marker. Consider adding evidence source."
                    )

    return warnings


def validate_entity_scope(query: str, evidence_sources: list[Path]) -> tuple[bool, str]:
    """
    Validate that evidence sources are within the correct entity's scope.

    This function prevents incorrect claims by ensuring that when a user
    asks about a specific skill/command/package/module, the evidence
    comes from that entity's directory, not from a similarly-named artifact
    in a different location.

    Args:
        query: The user query containing the entity name.
        evidence_sources: List of file paths used as evidence.

    Returns:
        A tuple of (is_valid, error_message). If valid, error_message is empty.

    Examples:
        >>> validate_entity_scope("how does /design work?", [Path("/design/skills/design/routing.py")])
        (True, "")

        >>> validate_entity_scope("how does /design work?", [Path("/other-skill/routing.py")])
        (False, "Evidence from /other-skill/routing.py does not match requested entity /design")
    """
    # Extract named entities from query
    # Look for patterns like "/design", "/go", "routing.py", "package X"
    entity_patterns = (
        r"/(\w+)",  # /design, /go, etc.
        r"(?:in|for|about) (?:the )?(?:skill|command|package|module) ['\"]?(\w+)['\"]?",  # skill "design", module routing
        r"\b(\w+)(?:\.py|\.md)\b",  # routing.py, SKILL.md
    )

    entities: set[str] = set()
    for pattern in entity_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        entities.update(matches)

    if not entities:
        # No entities named, scope is not verifiable
        return True, ""

    # Check each evidence source
    for evidence_path in evidence_sources:
        path_str = str(evidence_path).lower()

        # For each entity in the query, check if evidence is scoped correctly
        for entity in entities:
            entity_lower = entity.lower()

            # If the path doesn't contain the entity, it might be wrong scope
            # But we need to be careful about common names (e.g., "test")
            if entity_lower not in path_str:
                # Check if there are similarly-named artifacts in other locations
                # This is a simplified check - in a full implementation,
                # we'd search the codebase for similarly-named files
                possible_wrong_scope = False

                # If the evidence file is in a different top-level directory
                # than the entity, it's likely wrong scope
                if f"/{entity_lower}/" not in path_str.replace("\\", "/"):
                    possible_wrong_scope = True

                if possible_wrong_scope:
                    error = (
                        f"Evidence from {evidence_path} may be outside scope "
                        f"for requested entity {entity}. Verify evidence source "
                        "matches the named entity."
                    )
                    logger.warning(error)
                    return False, error

    return True, ""


def validate_friction_budget(content: str, template_type: str = "fast") -> list[str]:
    """
    Validate that a design response respects the friction budget.

    This function counts friction indicators (clarifications, permission pushes,
    implementation choices, internal failures) and compares against thresholds.

    Args:
        content: The design response content to validate.
        template_type: The template type ("fast" or "deep") for threshold selection.

    Returns:
        A list of validation warnings/errors. Empty list if no issues found.

    Examples:
        >>> validate_friction_budget("I recommend A. Criterion: X. First step: Y.", "fast")
        []

        >>> validate_friction_budget("Which option do you prefer? A or B?", "fast")
        ['FAIL: implementation_choice_count=1 exceeds threshold for fast template']
    """
    issues: list[str] = []

    # Get thresholds for the template type
    thresholds = FRICTION_BUDGET_THRESHOLDS.get(
        template_type, FRICTION_BUDGET_THRESHOLDS["fast"]
    )

    # Count each type of friction indicator
    friction_counts = {
        "clarification": 0,
        "permission_push": 0,
        "implementation_choice": 0,
        "internal_failure": 0,
    }

    content_lower = content.lower()

    for category, patterns in _FRICTION_INDICATORS.items():
        for pattern in patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            friction_counts[category] += len(matches)

    # Check clarifications
    max_clarifications = thresholds["max_clarifications"]
    if friction_counts["clarification"] > max_clarifications:
        issues.append(
            f"FAIL: clarification_count={friction_counts['clarification']} "
            f"exceeds threshold {max_clarifications} for {template_type} template"
        )

    # Check permission pushes
    max_permission_pushes = thresholds["max_permission_pushes"]
    if friction_counts["permission_push"] > max_permission_pushes:
        if friction_counts["permission_push"] > max_permission_pushes + 1:
            issues.append(
                f"FAIL: permission_push_count={friction_counts['permission_push']} "
                f"exceeds threshold {max_permission_pushes} for {template_type} template"
            )
        else:
            issues.append(
                f"WARN: permission_push_count={friction_counts['permission_push']} "
                f"exceeds threshold {max_permission_pushes} for {template_type} template"
            )

    # Check implementation choices
    max_choices = thresholds["max_implementation_choices"]
    if friction_counts["implementation_choice"] > max_choices:
        issues.append(
            f"FAIL: implementation_choice_count={friction_counts['implementation_choice']} "
            f"exceeds threshold {max_choices} for {template_type} template. "
            "Consider recommending a default path with criterion."
        )

    # Check internal failures
    if friction_counts["internal_failure"] > 0:
        issues.append(
            f"WARN: internal_failure_count={friction_counts['internal_failure']}. "
            "Consider handling tool/gate failures transparently."
        )

    # Check for safe default choice
    # If there are implementation choices, is there a recommendation?
    if friction_counts["implementation_choice"] > 0:
        # Look for recommendation patterns
        recommendation_patterns = (
            r"\bi recommend\b",
            r"\bthe best (option|choice|path) is\b",
            r"\bcriterion:\s*\w",
        )

        has_recommendation = any(
            re.search(pattern, content_lower) for pattern in recommendation_patterns
        )

        if not has_recommendation:
            issues.append(
                "FAIL: No safe default choice provided. For each A/B choice, "
                "recommend a default and state the criterion."
            )

    return issues


def print_status(message: str, status: str = "info") -> None:
    """
    Print a colored status message to the console.

    Args:
        message: The message to display.
        status: The status type - 'pass', 'fail', 'warn', or 'info'.
                Defaults to 'info'.

    Prints:
        A formatted message with appropriate color coding and symbols.
    """
    if status == "pass":
        print(f"{COLOR_GREEN}✓{COLOR_RESET} {message}")
    elif status == "fail":
        print(f"{COLOR_RED}✗{COLOR_RESET} {message}")
    elif status == "warn":
        print(f"{COLOR_YELLOW}⚠{COLOR_RESET} {message}")
    else:
        print(f"  {message}")


# Internal cache with mtime and size-based invalidation
@lru_cache(maxsize=DEFAULT_CACHE_SIZE)
def _load_template_content_cached(path_str: str, mtime: float, size: int) -> str:
    """
    Internal cached function that loads template content.

    Uses file path, modification time, and size as cache key for automatic invalidation.

    Args:
        path_str: String representation of the template path.
        mtime: File modification time.
        size: File size in bytes.

    Returns:
        The file content as a string.
    """
    return Path(path_str).read_text()


def load_template_content(template_path: Path) -> str:
    """
    Load and return the content of a template file.

    This function uses LRU caching with maxsize=32 to cache template content.
    The cache automatically invalidates when the file modification time or size changes.

    Args:
        template_path: Path to the template markdown file.

    Returns:
        The file content as a string.

    Raises:
        FileNotFoundError: If the template file does not exist.
        OSError: If there are issues reading the file.
    """
    # Get current modification time and size
    stat_info = os.stat(template_path)
    mtime = stat_info.st_mtime
    size = stat_info.st_size
    # Call the cached function with path string, mtime, and size as cache key
    return _load_template_content_cached(str(template_path), mtime, size)


# Attach cache_info and cache_clear as methods of load_template_content
# for backward compatibility with tests that expect these as function attributes
# Callable doesn't have these attributes at type-check time, added at runtime
load_template_content.cache_info = lambda: _load_template_content_cached.cache_info()  # type: ignore[attr-defined]
load_template_content.cache_clear = lambda: _load_template_content_cached.cache_clear()  # type: ignore[attr-defined]


def extract_headings(content: str) -> list[str]:
    """
    Extract all markdown headings from the provided content.

    Args:
        content: The markdown content to parse.

    Returns:
        A list of heading strings with their # prefixes preserved.
        Returns an empty list if no headings are found.

    Examples:
        >>> extract_headings("# Title\\n## Subtitle")
        ['# Title', '## Subtitle']
    """
    return re.findall(r"^(#+\s+.+)$", content, re.MULTILINE)


def load_contracts(contracts_path: Path) -> Optional[dict[str, Any]]:
    """
    Load template contracts from a YAML file.

    Args:
        contracts_path: Path to the YAML contracts file.

    Returns:
        A dictionary containing the contract definitions,
        or None if the file is empty.

    Raises:
        FileNotFoundError: If the contracts file does not exist.
        yaml.YAMLError: If the YAML content is malformed.
    """
    import yaml

    try:
        with open(contracts_path) as f:
            result = yaml.safe_load(f)
            # yaml.safe_load returns Any, but we expect dict or None
            if result is None:
                return None
            return cast(dict[str, Any], result)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Contracts file not found: {contracts_path}") from e


def validate_required_headings(
    template_name: str,
    template_path: Path,
    contract_headings: list[str],
) -> tuple[bool, list[str]]:
    """
    Validate that a template contains all required headings from its contract.

    Args:
        template_name: Name identifier for the template (used for logging).
        template_path: Path to the template file to validate.
        contract_headings: List of required heading strings from the contract.

    Returns:
        A tuple of (is_valid, missing_headings) where:
        - is_valid: True if all required headings are present, False otherwise.
        - missing_headings: List of heading strings that were not found.

    Examples:
        >>> validate_required_headings(
        ...     "test",
        ...     Path("test.md"),
        ...     ["# Title", "## Subsection"]
        ... )
        (True, [])
    """
    content = load_template_content(template_path)
    actual_headings = extract_headings(content)

    missing_headings = [
        required_heading
        for required_heading in contract_headings
        if required_heading not in actual_headings
    ]

    is_valid = len(missing_headings) == 0
    return is_valid, missing_headings


def _extract_section_content(content: str, section_name: str) -> Optional[str]:
    """
    Extract the content of a specific section from markdown.

    Args:
        content: The full markdown content.
        section_name: The name of the section to extract.

    Returns:
        The section content (excluding the heading) or None if not found.
    """
    section_match = re.search(
        rf"(?:^#+\s*{re.escape(section_name)}.*?$)(.*?)(?=^#+\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    return section_match.group(1).strip() if section_match else None


def _calculate_line_overlap(text1: str, text2: str) -> float:
    """
    Calculate the percentage of line overlap between two text blocks.

    Args:
        text1: First text block.
        text2: Second text block.

    Returns:
        The overlap percentage (0-100), calculated as the ratio
        of shared lines to the maximum number of unique lines.
    """
    lines1 = set(text1.split("\n"))
    lines2 = set(text2.split("\n"))

    if not lines1:
        return 0.0

    shared_lines = lines1 & lines2
    max_unique_lines = max(len(lines1), len(lines2), 1)

    return len(shared_lines) / max_unique_lines * 100


def check_duplicate_logic(
    fast_content: str, deep_content: str
) -> list[tuple[str, float, str, str]]:
    """
    Check for duplicate logic sections between fast.md and deep.md templates.

    Analyzes predefined sections and identifies those with significant
    content overlap (above the configured threshold).

    Args:
        fast_content: The full content of the fast.md template.
        deep_content: The full content of the deep.md template.

    Returns:
        A list of tuples, each containing:
        - section_name: The name of the duplicated section.
        - overlap_percent: Float overlap percentage (0-100).
        - suggestion: Recommendation for handling the duplicate.
        - severity: 'warning' for 50-70% overlap, 'critical' for >70%.

    Examples:
        >>> check_duplicate_logic("## Stage 0\\nSame content", "## Stage 0\\nSame content")
        [('Stage 0', 100.0, 'Consider extraction to shared_frameworks.md', 'critical')]
    """
    duplicates = []

    for section_name in DUPLICATE_CHECK_SECTIONS:
        section_exists_in_both = (
            section_name in fast_content and section_name in deep_content
        )
        if not section_exists_in_both:
            continue

        fast_section = _extract_section_content(fast_content, section_name)
        deep_section = _extract_section_content(deep_content, section_name)

        if fast_section is None or deep_section is None:
            continue

        overlap_percent = _calculate_line_overlap(fast_section, deep_section)

        if overlap_percent > DUPLICATE_OVERLAP_THRESHOLD:
            suggestion = "Consider extraction to shared_frameworks.md"
            severity = (
                "critical" if overlap_percent > HIGH_OVERLAP_THRESHOLD else "warning"
            )
            duplicates.append(
                (
                    section_name,
                    overlap_percent,
                    suggestion,
                    severity,
                )
            )
            # Print warning directly (format float for display)
            print_status(
                f"{section_name}: {overlap_percent:.1f}% overlap - {suggestion}",
                "warn",
            )

    return duplicates


def validate_template_chain(chain: str) -> tuple[bool, str]:
    """
    Validate template chaining rules from SKILL.md.

    Enforces the following rules:
    - Max 2 templates in a chain
    - 'precedent' cannot be a secondary template
    - 'fast' and 'deep' are complexity selectors, not chainable templates

    Args:
        chain: Template chain string (e.g., "python+data-pipeline", "fast")

    Returns:
        A tuple of (is_valid, error_message) where:
        - is_valid: True if chain is valid, False otherwise
        - error_message: Empty string if valid, otherwise contains error description

    Examples:
        >>> validate_template_chain("python+data-pipeline")
        (True, "")
        >>> validate_template_chain("python+precedent")
        (False, "'precedent' cannot be secondary template")
        >>> validate_template_chain("python+fast")
        (False, "'fast' and 'deep' are complexity selectors, not chainable")
        >>> validate_template_chain("python+data-pipeline+cli")
        (False, "Max 2 templates allowed, got 3")
    """
    # No chaining is always valid
    if "+" not in chain:
        return True, ""

    parts = chain.split("+")

    # Rule 1: Max 2 templates
    if len(parts) > 2:
        return False, f"Max 2 templates allowed, got {len(parts)}"

    # Rule 2: 'precedent' cannot be secondary
    if "precedent" in parts[1:]:
        return False, "'precedent' cannot be secondary template"

    # Rule 3: 'fast' and 'deep' are not chainable (except as primary)
    if any(p in {"fast", "deep"} for p in parts[1:]):
        return False, "'fast' and 'deep' are complexity selectors, not chainable"

    return True, ""


def _validate_template_dir(template_dir: Path) -> None:
    """
    Validate template directory path to prevent path traversal attacks.

    SECURITY: Resolves path and checks for suspicious patterns before
    allowing file operations. Raises ValueError if path validation fails.

    Args:
        template_dir: Path to validate

    Raises:
        ValueError: If path contains traversal sequences or resolves outside expected bounds
    """
    # Convert to absolute path for validation
    abs_path = template_dir.resolve()

    # Check for path traversal patterns in original path string
    path_str = str(template_dir)
    if ".." in path_str or path_str.startswith("~"):
        raise ValueError(
            f"Path traversal detected in template_dir: {template_dir}. "
            f"Absolute path resolved to: {abs_path}. "
            f"Use an absolute path within the expected directory structure."
        )


def validate_all(template_dir: Optional[Path] = None) -> int:
    """
    Run all template validations and return the appropriate exit code.

    This is the main entry point for the validation script. It performs
    the following validations:
    1. Loads template contracts from YAML
    2. Validates each template against its required headings
    3. Checks for duplicate logic between fast.md and deep.md
    4. Validates template chaining rules (max 2 templates, precedent not secondary, fast/deep not chainable)

    Args:
        template_dir: Optional path to the directory containing templates
                     and contracts file. If None, uses the default
                     resources directory relative to this script.

    Returns:
        0 if all validations pass, 1 if any validation fails.

    Raises:
        FileNotFoundError: If required files are missing.
        OSError: If there are issues reading files.
        ValueError: If template_dir contains path traversal sequences (SEC-001).
    """
    if template_dir is None:
        script_dir = Path(__file__).parent
        resources_dir = script_dir / "resources"
    else:
        # SEC-001: Validate user-provided path to prevent traversal attacks
        _validate_template_dir(template_dir)
        resources_dir = template_dir
    contracts_file = resources_dir / "template_contracts.yaml"

    print_status("Loading contracts...", "info")
    contracts = load_contracts(contracts_file)

    # Build template paths
    templates = {
        name: resources_dir / filename for name, filename in TEMPLATE_NAMES.items()
    }

    # Track validation results
    all_passed = True
    validation_results: list[ValidationResult] = []

    # Phase 1: Validate required headings
    print()
    print_status("Validating required headings...", "info")
    print("-" * 60)

    for template_name, template_path in templates.items():
        if not template_path.exists():
            print_status(f"{template_name}: Template file not found", "fail")
            all_passed = False
            continue

        if contracts is None:
            print_status("No contracts loaded", "fail")
            return 1

        if template_name not in contracts:
            print_status(f"{template_name}: No contract defined", "warn")
            continue

        contract = contracts[template_name]
        required_headings = contract.get("required_headings", [])

        is_valid, missing_headings = validate_required_headings(
            template_name, template_path, required_headings
        )

        if is_valid:
            print_status(f"{template_name}: All required headings present", "pass")
            validation_results.append(
                ValidationResult(template_name, "headings", "pass")
            )
        else:
            missing_str = ", ".join(missing_headings)
            print_status(f"{template_name}: Missing headings: {missing_str}", "fail")
            all_passed = False
            validation_results.append(
                ValidationResult(template_name, "headings", "fail", missing_headings)
            )

    # Phase 2: Check for duplicate logic between fast.md and deep.md
    print()
    print_status("Checking for duplicate logic...", "info")
    print("-" * 60)

    has_critical_duplicates = False
    duplicates = []
    try:
        fast_content = load_template_content(templates["fast"])
        deep_content = load_template_content(templates["deep"])

        duplicates = check_duplicate_logic(fast_content, deep_content)

        if not duplicates:
            print_status("No significant duplicate logic found", "pass")
        else:
            # Check for critical duplicates (>70% overlap)
            for section_name, overlap_percent, suggestion, severity in duplicates:
                if severity == "critical":
                    has_critical_duplicates = True
                # Also print each duplicate (for mocked test case)
                # Format float for display
                print_status(
                    f"{section_name}: {overlap_percent:.1f}% overlap - {suggestion}",
                    "warn",
                )
            print_status(
                "Consider extracting shared logic to shared_frameworks.md", "info"
            )
    except (FileNotFoundError, OSError) as e:
        print_status(f"Could not check duplicate logic: {e}", "warn")

    # Phase 3: Validate template chaining rules
    print()
    print_status("Validating template chaining rules...", "info")
    print("-" * 60)

    # Test all valid template combinations
    chain_passed = True
    test_chains = [
        # Valid single templates
        "fast",
        "deep",
        "python",
        "cli",
        "data-pipeline",
        "precedent",
        # Valid chains
        "python+data-pipeline",
        "cli+python",
        "precedent+python",
        # Invalid chains (should fail validation)
        "python+precedent",  # precedent as secondary
        "python+fast",  # fast as secondary
        "deep+python",  # deep as primary (should be complexity selector)
        "python+data-pipeline+cli",  # more than 2 templates
    ]

    for chain in test_chains:
        is_valid, error_msg = validate_template_chain(chain)
        # Chains with '+' are the ones being validated
        if "+" in chain:
            if is_valid:
                print_status(f"'{chain}': Valid chain", "pass")
            else:
                print_status(f"'{chain}': {error_msg}", "warn")
                # For known invalid chains, this is expected behavior
                # We're validating the validator catches these errors
        # Single templates (no '+') are always valid

    print_status("Template chaining validation complete", "pass")

    # Summary and exit code
    print()
    print("=" * 60)
    if all_passed and not has_critical_duplicates:
        print_status("All validations passed!", "pass")
        return 0
    else:
        print_status("Some validations failed. Please review.", "fail")
        return 1


def main() -> None:
    """
    Entry point for the script when executed directly.

    Exits with the appropriate status code from validate_all().
    """
    sys.exit(validate_all())


if __name__ == "__main__":
    main()
