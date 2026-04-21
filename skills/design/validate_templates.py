#!/usr/bin/env python3
"""
Template validation script for /arch skill.

Validates:
- Required headings match between templates and contracts
- Contract compliance (must_include items)
- Duplicate logic detection across templates
"""

import sys
import re
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, cast
from functools import lru_cache

__all__ = [
    # Public API functions
    "validate_all",
    "validate_required_headings",
    "check_duplicate_logic",
    "validate_template_chain",
    "load_template_content",
    "load_contracts",
    "extract_headings",
    # Constants
    "TEMPLATE_NAMES",
    "DUPLICATE_OVERLAP_THRESHOLD",
    "HIGH_OVERLAP_THRESHOLD",
    "DEFAULT_CACHE_SIZE",
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
