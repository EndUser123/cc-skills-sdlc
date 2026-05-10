"""
Architecture routing module.

This module implements the routing logic for selecting appropriate templates
based on query analysis, domain detection, and configuration.

Routing flow: query -> domain detection -> template selection -> validation
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

from config import VALID_DOMAINS

__all__ = [
    # Public API functions
    "select_template",
    "validate_template",
    "extract_template_override",
    "detect_domain_keywords",
    "detect_complexity",
    "detect_intent_type",
    # Type definitions
    "TemplateResult",
    "ConfigResult",
    "ValidationResult",
    # Constants
    "VALID_TEMPLATES",
    "TEMPLATE_METADATA",
    # CKS integration
    "CKS_AVAILABLE",
    "CKS_IMPORT_ERROR",
    # Semantic search functions
    "cks_semantic_search",
    "cks_semantic_domain_search",
    # Follow-up query detection
    "detect_follow_up_query",
    "FollowUpContext",
    # Subject inference
    "retrieve_context_hint",
    "SubjectInferenceContext",
]

# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# CKS Integration
# =============================================================================

CKS_AVAILABLE: bool = False
CKS_IMPORT_ERROR: str | None = None

try:
    importlib.import_module("csf.cks.unified")
    CKS_AVAILABLE = True
    logger.debug("CKS module imported successfully")
except (ImportError, ModuleNotFoundError) as e:
    CKS_AVAILABLE = False
    CKS_IMPORT_ERROR = str(e)
    logger.warning(
        f"CKS Integration Error: Unable to import Constitutional Knowledge System (CKS): {e}\n"
        "The arch skill will continue with generic analysis without CKS historical data.\n"
        "To enable CKS integration:\n"
        "  1. Verify CKS is installed at: P:\\\\\\__csf/\n"
        "  2. Check CKS source path exists: P:\\\\\\__csf/src\n"
        "  3. Ensure CKS database exists: P:\\\\\\__csf/data/cks.db\n"
        "Proceeding with generic analysis..."
    )

# =============================================================================
# Constants
# =============================================================================

DOMAIN_KEYWORDS = {
    "cli": [
        "cli",
        "command line",
        "terminal",
        "shell",
        "posix",
        "exit code",
        "argument parsing",
    ],
    "python": [
        "python",
        "asyncio",
        "type hint",
        "pydantic",
        "fastapi",
        "flask",
        "django",
        "async",
        "await",
        "decorator",
        "context manager",
    ],
    "data-pipeline": [
        "etl",
        "elt",
        "pipeline",
        "streaming",
        "batch",
        "kafka",
        "spark",
        "airflow",
        "dagster",
        "prefect",
        "warehouse",
        "data lake",
    ],
    "precedent": [
        "adr",
        "decision record",
        "precedent",
        "document decision",
        "architecture decision record",
    ],
}

HIGH_COMPLEXITY_INDICATORS = [
    "redesign",
    "overhaul",
    "architecture",
    "microservices",
    "from scratch",
    "rewrite",
    "replace",
    "multi-system",
    "service boundary",
    "schema migration",
    "breaking change",
]

IMPROVE_KEYWORDS = [
    "improve",
    "optimize",
    "harden",
    "stabilize",
    "enhance",
    "strengthen",
]
SUBSYSTEM_KEYWORDS: list[str] = [
    "memory",
    "cks",
    "hooks",
    "research",
    "retro",
    "lesson",
    "ingestion",
    "validation",
]

VALID_TEMPLATES: set[str] = {
    "fast",
    "deep",
    "cli",
    "python",
    "data-pipeline",
    "precedent",
}

TEMPLATE_METADATA = {
    "fast": {"complexity": "LOW", "domain": "Generic", "output_size": "~5 KB"},
    "deep": {"complexity": "HIGH", "domain": "Generic", "output_size": "~15-30 KB"},
    "cli": {"complexity": "Any", "domain": "CLI/POSIX", "output_size": "~8 KB"},
    "python": {"complexity": "Any", "domain": "Python 3.12+", "output_size": "~10 KB"},
    "data-pipeline": {
        "complexity": "Any",
        "domain": "Data Systems",
        "output_size": "~12 KB",
    },
    "precedent": {"complexity": "Any", "domain": "ADR", "output_size": "~20 KB"},
}

# Domain priority order (higher priority = checked first)
DOMAIN_PRIORITY: list[str] = ["cli", "python", "data-pipeline", "precedent"]

# Pre-built keyword lookup for O(1) domain detection
# Maps each keyword to its domain, with priority handled via domain check order
_KEYWORD_TO_DOMAIN: dict[str, str] = {}
for domain in DOMAIN_PRIORITY:
    for keyword in DOMAIN_KEYWORDS.get(domain, []):
        _KEYWORD_TO_DOMAIN[keyword.lower()] = domain

# =============================================================================
# Type Definitions
# =============================================================================


class TemplateResult(TypedDict):
    """Result of template selection operation."""

    template: str
    source: str
    confidence: str
    chained_domains: list[str]  # Additional domains from template=X+Y syntax


class ConfigResult(TypedDict):
    """Result of config loading operation."""

    config: dict[str, str] | None
    source: str
    error: str | None


class ValidationResult(TypedDict):
    """Result of template validation operation."""

    is_valid: bool
    error_message: str
    template_path: Path | None


class FollowUpContext(TypedDict):
    """Context for follow-up query detection.

    When a query references prior conversation content, this struct
    signals to the template executor that prior context must be checked
    before proceeding with clarity gate or gap detection.
    """

    is_follow_up: bool
    reason: str  # "ordinal_ref" | "skill_ref" | None
    matched_text: str | None  # The text that triggered detection
    needs_prior_context: bool  # True → template executor must retrieve prior turns
    suggested_subject: str | None  # Inferred subject from recent history


class SubjectInferenceContext(TypedDict):
    """Result of subject inference from recent transcript history."""

    last_file: str | None
    last_hook: str | None
    last_contract: str | None
    recent_paths: list[str]
    hint_text: str  # Formatted text for LLM prompt injection


# =============================================================================
# Routing Functions
# =============================================================================


def extract_template_override(query: str) -> tuple[str | None, list[str]]:
    """
    Extract template override from query, supporting template chaining.

    Template chaining syntax: template=X+Y+Z
    - First template (X) is the primary template used for output structure
    - Additional templates (Y, Z) provide domain context layering

    SECURITY (SEC-002): Multi-layer validation to prevent template injection:
    1. Regex extraction with restrictive pattern (alphanumeric, hyphens, + for chaining)
    2. Allowlist validation against VALID_TEMPLATES for all templates
    3. Safe default (returns None, []) for any invalid input

    Given: query string
    When: query contains "template=<name>" or "template=X+Y+Z"
    Then: return (primary_template, [chained_domains]) or (None, [])

    Examples:
        "redesign api template=deep" -> ("deep", []) (valid)
        "build pipeline template=python+data-pipeline" -> ("python", ["data-pipeline"]) (chaining)
        "cli tool template=python+data-pipeline+cli" -> ("python", ["data-pipeline", "cli"]) (multi-chain)
        "redesign api template=malicious" -> (None, []) (invalid, not in allowlist)
        "improve memory system" -> (None, []) (no override)
        "redesign api template=../../../etc/passwd" -> (None, []) (regex rejects)
        "redesign api template=<script>alert(1)</script>" -> (None, []) (regex rejects)
    """
    # SEC-002: Restrictive regex - only alphanumeric, hyphens, and + for chaining
    # This prevents injection attempts with path traversal, HTML, shell commands
    match = re.search(r"template=([a-zA-Z0-9-]+(?:\+[a-zA-Z0-9-]+)*)", query)
    if match:
        template_spec = match.group(1)
        templates = template_spec.split("+")

        # Security validation: only return templates from the allowlist
        for template in templates:
            if template not in VALID_TEMPLATES:
                logger.debug(
                    f"Template override '{template}' rejected (not in VALID_TEMPLATES allowlist)"
                )
                return None, []

        primary = templates[0]
        chained = templates[1:] if len(templates) > 1 else []

        if chained:
            logger.debug(f"Template override found: {primary} + {chained}")
        else:
            logger.debug(f"Template override found: {primary}")

        return primary, chained

    logger.debug("No template override found in query")
    return None, []


def detect_domain_keywords(query: str) -> str | None:
    """
    Detect domain from query keywords.

    Given: query string
    When: query contains domain-specific keywords
    Then: return detected domain or None

    Priority: cli > python > data-pipeline > precedent

    Performance: O(n) where n is number of matched keywords in query (typically 0-1),
    not O(n*m) where n=domains and m=total_keywords. Uses pre-built lookup dict.
    """
    query_lower = query.lower()

    # Find all matching keywords in the query using the pre-built lookup
    matched_domains = []
    for keyword, domain in _KEYWORD_TO_DOMAIN.items():
        if keyword in query_lower:
            matched_domains.append(domain)

    # Return the highest priority domain (first in DOMAIN_PRIORITY list)
    if matched_domains:
        # Find the first (highest priority) matched domain
        for domain in DOMAIN_PRIORITY:
            if domain in matched_domains:
                logger.debug(f"Domain detected: {domain}")
                return domain

    logger.debug("No domain keywords detected")
    return None


def detect_complexity(query: str) -> str:
    """
    Detect complexity from query.

    Given: query string
    When: query contains high complexity indicators
    Then: return "deep" or "fast"

    Default: "fast"
    """
    query_lower = query.lower()

    for indicator in HIGH_COMPLEXITY_INDICATORS:
        if indicator.lower() in query_lower:
            logger.debug(f"High complexity detected: {indicator}")
            return "deep"

    logger.debug("Defaulting to low complexity (fast)")
    return "fast"


def detect_intent_type(query: str) -> str:
    """
    Detect intent type from query.

    Given: query string
    When: query matches review keywords + architecture → ARCHITECTURE_REVIEW
         query contains both improve and subsystem keywords → IMPROVE_SYSTEM
    Then: return "ARCHITECTURE_REVIEW", "IMPROVE_SYSTEM", or "DEFAULT"
    """
    query_lower = query.lower()

    # ARCHITECTURE_REVIEW: explicit review/audit/assess of architecture
    review_keywords = ("review", "audit", "assess", "evaluate", "critique")
    architecture_keywords = ("architecture", "arch", "design", "system")
    has_review = any(keyword in query_lower for keyword in review_keywords)
    has_architecture = any(keyword in query_lower for keyword in architecture_keywords)

    if has_review and has_architecture:
        logger.debug("Intent type detected: ARCHITECTURE_REVIEW")
        return "ARCHITECTURE_REVIEW"

    # IMPROVE_SYSTEM: improve specific subsystem
    has_improve = any(keyword in query_lower for keyword in IMPROVE_KEYWORDS)
    has_subsystem = any(keyword in query_lower for keyword in SUBSYSTEM_KEYWORDS)

    if has_improve and has_subsystem:
        logger.debug("Intent type detected: IMPROVE_SYSTEM")
        return "IMPROVE_SYSTEM"

    logger.debug("Intent type detected: DEFAULT")
    return "DEFAULT"


# =============================================================================
# Follow-Up Query Detection
# =============================================================================

# Patterns that indicate the query references prior conversation content
_ORDINAL_REF_PATTERNS = [
    re.compile(r"(?i)\boption\s+\d+\b"),
    re.compile(r"(?i)\b(idea|point|item|number|num|no\.?)\s*\d+\b"),
    re.compile(r"(?i)\b(idea|point|item|these|those)\s+\d+\b"),
    re.compile(r"(?i)\b(idea|point|item)\s+(?:one|two|three|four|five)\b"),
    re.compile(r"(?i)\b(points?|ideas?|items?|options?)\s+(?:\d+\s+and\s+\d+|\d+\s*,\s*\d+)\b"),
    re.compile(r"(?i)\b(that|this|those|these)\s+(?:suggestion|recommendation|approach|option|idea|design)\b"),
    re.compile(r"(?i)\b(these|those)\s+(?:ideas?|points?|options?|items?)\b"),
]

_SKILL_REF_PATTERNS = [
    re.compile(r"(?i)(?:add|apply|extend)\s+(?:this|that|it|them)\s+to\s+/\w+"),
    re.compile(r"(?i)(?:add|apply|extend)\s+to\s+/\w+"),
    re.compile(r"(?i)(?:does|did|has|have|is|was)\s+/\w+\s+(?:already|have|has|already\s+have)"),
    re.compile(r"(?i)/\w+\s+(?:already|have|has)\b"),
]


def detect_follow_up_query(query: str) -> FollowUpContext:
    """
    Detect whether a query references prior conversation content.

    This is used by the Stage 0.5 clarity gate to distinguish between:
    - A standalone query that needs full context assessment
    - A follow-up query that references prior turns and should
      have context retrieved before clarity gate evaluation

    Given: query string
    When: query contains ordinal references or skill references
    Then: return FollowUpContext with is_follow_up=True

    Examples:
        "what about option 2?" -> is_follow_up=True, reason="ordinal_ref"
        "add this to /plan" -> is_follow_up=True, reason="skill_ref"
        "design a new API" -> is_follow_up=False, reason=None
    """
    query_lower = query.lower()

    # Check ordinal references first (e.g., "option 2", "idea 3")
    for pattern in _ORDINAL_REF_PATTERNS:
        match = pattern.search(query)
        if match:
            logger.debug(f"Follow-up query detected (ordinal ref): {match.group()!r}")
            return FollowUpContext(
                is_follow_up=True,
                reason="ordinal_ref",
                matched_text=match.group(),
                needs_prior_context=True,
            )

    # Check skill references (e.g., "add to /plan", "does /arch already")
    for pattern in _SKILL_REF_PATTERNS:
        match = pattern.search(query)
        if match:
            logger.debug(f"Follow-up query detected (skill ref): {match.group()!r}")
            return FollowUpContext(
                is_follow_up=True,
                reason="skill_ref",
                matched_text=match.group(),
                needs_prior_context=True,
            )

    logger.debug("Query is standalone (no follow-up indicators)")
    return FollowUpContext(
        is_follow_up=False,
        reason="",
        matched_text=None,
        needs_prior_context=False,
        suggested_subject=None,
    )


def retrieve_context_hint(limit: int = 5) -> SubjectInferenceContext:
    """
    Programmatically retrieve a context hint from recent session history.

    This scans recent tool calls (Read, Edit, Grep, etc.) to identify the
    most likely subject for follow-up queries like "is it safe?" or
    "what about this?".

    Returns a SubjectInferenceContext with a formatted hint_text for LLM injection.
    """
    ctx: SubjectInferenceContext = {
        "last_file": None,
        "last_hook": None,
        "last_contract": None,
        "recent_paths": [],
        "hint_text": "",
    }

    # SEC-001: Path Resolution
    # We look for the trace file in the diagnostics directory
    diag_dir = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "logs" / "diagnostics"
    trace_file = diag_dir / "ups_execution_trace.jsonl"

    if not trace_file.exists():
        ctx["hint_text"] = "No recent execution trace found for context inference."
        return ctx

    try:
        # Read the last 50 lines to find the current session's transcript path
        # Using deque for memory-efficient tail reading
        with open(trace_file, "r", encoding="utf-8") as f:
            last_lines = deque(f, 50)

        transcript_path: Path | None = None
        for line in reversed(last_lines):
            try:
                data = json.loads(line)
                if "transcript_path" in data:
                    path = Path(data["transcript_path"])
                    if path.exists():
                        transcript_path = path
                        break
            except (json.JSONDecodeError, KeyError, OSError):
                continue

        if not transcript_path:
            ctx["hint_text"] = "No active transcript path found in trace."
            return ctx

        # Read the last 20 messages from the transcript to find tool calls
        with open(transcript_path, "r", encoding="utf-8") as f:
            messages = deque(f, 20)

        found_paths: list[str] = []
        for msg_line in reversed(messages):
            try:
                msg_data = json.loads(msg_line)
                message = msg_data.get("message", {})
                content_list = message.get("content", [])

                for item in content_list:
                    if item.get("type") == "tool_use":
                        name = item.get("name")
                        args = item.get("input", {})

                        # Extract paths from common tool calls
                        path = args.get("file_path") or args.get("path") or args.get("target_path")
                        if path and isinstance(path, str):
                            # Clean up path (strip project root if present)
                            clean_path = path.replace("P:\\\\\\", "").replace("P:\\\\\\\", "")
                            if clean_path not in found_paths:
                                found_paths.append(clean_path)

                        # Detect specific subject types
                        if name == "Read" or name == "Edit" or name == "replace":
                            if not ctx["last_file"]:
                                ctx["last_file"] = path

                        if "hook" in str(path).lower():
                            if not ctx["last_hook"]:
                                ctx["last_hook"] = path

                        if "contract" in str(path).lower() or "boundary" in str(path).lower():
                            if not ctx["last_contract"]:
                                ctx["last_contract"] = path

            except (json.JSONDecodeError, KeyError, OSError):
                continue

        ctx["recent_paths"] = found_paths[:limit]

        # Format the hint text for the LLM
        hints = []
        if ctx["last_file"]:
            hints.append(f"Last accessed file: {ctx['last_file']}")
        if ctx["last_hook"]:
            hints.append(f"Last mentioned hook: {ctx['last_hook']}")
        if found_paths:
            top_paths = ", ".join(found_paths[:3])
            hints.append(f"Recent relevant paths: {top_paths}")

        if hints:
            ctx["hint_text"] = "CONSTRUCTIVE CONTEXT HINT:\n- " + "\n- ".join(hints)
        else:
            ctx["hint_text"] = "No clear subject inferred from recent tool calls."

    except Exception as e:
        logger.warning(f"Failed to retrieve context hint: {e}")
        ctx["hint_text"] = f"Context inference failed: {e}"

    return ctx


# =============================================================================
# Template Selection - Chain of Responsibility Pattern
# =============================================================================


def _validate_template(template: str) -> str:
    """Validate template and return it, raising ValueError if invalid."""
    if template not in VALID_TEMPLATES:
        raise ValueError(
            f"Invalid template override: '{template}'. Must be one of {VALID_TEMPLATES}"
        )
    return template


def _resolve_domain(default_domain: str | None, env_domain: str | None) -> str | None:
    """Resolve effective domain from parameters (default takes precedence over env)."""
    if default_domain:
        return default_domain
    return env_domain


def _validate_domain(domain: str | None) -> None:
    """Validate domain, raising ValueError if invalid."""
    if domain and domain not in VALID_DOMAINS:
        raise ValueError(f"Invalid domain: '{domain}'. Must be one of {VALID_DOMAINS}")


class _TemplateSelector:
    """Base handler in chain of responsibility for template selection."""

    def __init__(self, query: str) -> None:
        self.query = query

    def try_select(self) -> str | None:
        """Attempt to select template. Returns None if not applicable."""
        return None


class _OverrideParamSelector(_TemplateSelector):
    """Handler for template override parameter (highest priority)."""

    def __init__(self, query: str, template_override: str | None) -> None:
        super().__init__(query)
        self.template_override = template_override

    def try_select(self) -> str | None:
        if self.template_override:
            logger.info(f"Template selected from override parameter: {self.template_override}")
            return _validate_template(self.template_override)
        return None


class _QueryOverrideSelector(_TemplateSelector):
    """Handler for template override extracted from query."""

    def __init__(self, query: str) -> None:
        super().__init__(query)
        self.chained_domains: list[str] = []  # Track chained domains from template=X+Y+Z

    def try_select(self) -> str | None:
        override, chained = extract_template_override(self.query)
        self.chained_domains = chained
        if override:
            logger.info(f"Template selected from query override: {override}")
            if chained:
                logger.info(f"Chained domains for context layering: {chained}")
            return _validate_template(override)
        return None


class _KeywordDetectionSelector(_TemplateSelector):
    """Handler for domain keyword detection."""

    def try_select(self) -> str | None:
        detected = detect_domain_keywords(self.query)
        if detected:
            logger.info(f"Template selected from keyword detection: {detected}")
            return detected
        return None


class _DefaultDomainSelector(_TemplateSelector):
    """Handler for default domain (only used when not 'auto' and no keywords detected)."""

    def __init__(self, query: str, domain: str | None) -> None:
        super().__init__(query)
        self.domain = domain

    def try_select(self) -> str | None:
        if self.domain and self.domain != "auto" and self.domain in VALID_TEMPLATES:
            logger.info(f"Template selected from default domain: {self.domain}")
            return self.domain
        return None


class _ComplexityDetectionSelector(_TemplateSelector):
    """Handler for complexity detection (final fallback)."""

    def try_select(self) -> str:
        """Always returns a template (never None)."""
        template = detect_complexity(self.query)
        logger.info(f"Template selected from complexity detection: {template}")
        return template


def select_template(
    query: str,
    template_override: str | None = None,
    default_domain: str | None = None,
    env_domain: str | None = None,
) -> TemplateResult:
    """
    Select appropriate template based on query and configuration.

    Full routing flow:
    1. Template override (highest priority)
    2. Default domain from config/env
    3. Domain keyword detection
    4. Complexity detection

    Given: query string and optional configuration
    When: following routing priority
    Then: return TemplateResult with template name and metadata

    Returns:
        TemplateResult with template, source, confidence, and chained_domains

    Raises:
        ValueError: If invalid template or domain specified
    """
    # Resolve and validate domain (for error checking only)
    domain = _resolve_domain(default_domain, env_domain)
    _validate_domain(domain)

    # Chain of responsibility: try each handler in priority order
    selectors = [
        _OverrideParamSelector(query, template_override),
        _QueryOverrideSelector(query),
        _KeywordDetectionSelector(query),
        _DefaultDomainSelector(query, domain),
        _ComplexityDetectionSelector(query),  # Always succeeds
    ]

    for selector in selectors:
        result = selector.try_select()
        if result is not None:
            # Build TemplateResult
            chained_domains: list[str] = []
            source: str
            confidence: str

            if isinstance(selector, _QueryOverrideSelector):
                chained_domains = selector.chained_domains
                source = "query_override"
                confidence = "high"
            elif isinstance(selector, _OverrideParamSelector):
                source = "parameter_override"
                confidence = "high"
            elif isinstance(selector, _KeywordDetectionSelector):
                source = "keyword_detection"
                confidence = "medium"
            elif isinstance(selector, _DefaultDomainSelector):
                source = "default_domain"
                confidence = "medium"
            else:  # _ComplexityDetectionSelector
                source = "complexity_detection"
                confidence = "low"

            # Usage monitoring: Log when template chaining is used
            if chained_domains:
                logger.info(
                    f"Template chaining detected: primary={result}, "
                    f"chained={chained_domains}, source={source}"
                )

            return TemplateResult(
                template=result,
                source=source,
                confidence=confidence,
                chained_domains=chained_domains,
            )

    # Unreachable: _ComplexityDetectionSelector always returns a template
    raise RuntimeError("Template selection failed unexpectedly")


@lru_cache(maxsize=32)
def _validate_template_cached(template_name: str, mtime: float) -> tuple[bool, str]:
    """
    Internal cached function for template validation.

    Cache key includes (template_name, mtime) so cache invalidates
    when file is modified.

    PERF-002: Caches file content to avoid redundant disk I/O.
    """
    # Check if template file exists and get mtime
    resources_dir = Path(__file__).parent / "resources"
    template_path = resources_dir / f"{template_name}.md"

    if not template_path.exists():
        error = f"Template file not found: {template_path}"
        logger.error(error)
        return (False, error)

    # Check if file is readable
    try:
        with open(template_path) as f:
            content = f.read()
        if not content:
            error = f"Template file is empty: {template_path}"
            logger.error(error)
            return (False, error)
    except PermissionError:
        error = f"Cannot read template file: {template_path}. Check file permissions"
        logger.error(error)
        return (False, error)
    except UnicodeDecodeError:
        error = f"Cannot read template file: {template_path}. encoding issue - verify file is utf-8"
        logger.error(error)
        return (False, error)
    except OSError as e:
        # Check for file lock/resource temporarily unavailable
        if "temporarily unavailable" in str(e).lower() or getattr(e, "errno", None) == 11:
            error = (
                f"Cannot read template file: {template_path}. file may be locked by another process"
            )
            logger.error(error)
            return (False, error)
        error = f"Cannot read template file: {template_path}. Check disk space. Error: {e}"
        logger.error(error)
        return (False, error)
    except Exception as e:
        error = f"Cannot read template file: {template_path}. Error: {e}"
        logger.error(error)
        return (False, error)

    logger.debug(f"Template validated successfully: {template_name}")
    return (True, "")


def validate_template(template_name: str) -> tuple[bool, str]:
    """
    Validate template name and file existence with caching.

    Given: template name
    When: checking against valid templates and file system
    Then: return (is_valid, error_message)

    PERF-002: Results are cached by (template_name, mtime) to avoid
    redundant file I/O. Cache invalidates when file is modified.

    Returns:
        (True, "") if valid, (False, error_message) if invalid

    Cache Methods:
        validate_template.cache_info() - Returns cache statistics (hits, misses)
        validate_template.cache_clear() - Clears the entire cache
    """
    # Check if template name is valid (non-cached, fast check)
    if template_name not in VALID_TEMPLATES:
        error = f"Invalid template: '{template_name}'. Must be one of {VALID_TEMPLATES}"
        logger.error(error)
        return (False, error)

    # Get file mtime for cache key
    resources_dir = Path(__file__).parent / "resources"
    template_path = resources_dir / f"{template_name}.md"

    try:
        mtime = template_path.stat().st_mtime
    except OSError as e:
        error = f"Cannot stat template file: {template_path}. Error: {e}"
        logger.error(error)
        return (False, error)

    # Call cached function with mtime as part of cache key
    return _validate_template_cached(template_name, mtime)


# Expose cache methods from internal cached function
validate_template.cache_info = _validate_template_cached.cache_info  # type: ignore[attr-defined]
validate_template.cache_clear = _validate_template_cached.cache_clear  # type: ignore[attr-defined]


# =============================================================================
# Semantic Search Functions (Embedding Integration)
# =============================================================================


def cks_semantic_search(
    query: str,
    entry_type: str | None = None,
    limit: int = 5,
    enable_semantic: bool = True,
) -> list[dict[str, Any]]:
    """
    Perform semantic search on CKS with fallback to keyword search.

    This function provides a unified interface for semantic search with
    automatic fallback to keyword search when semantic is unavailable.

    Args:
        query: Search query text
        entry_type: Filter by entry type (memory, pattern, code, knowledge, etc.)
        limit: Maximum number of results to return
        enable_semantic: Whether to use semantic search (default: True)

    Returns:
        List of matching entries with similarity scores, sorted by relevance

    Example:
        >>> results = cks_semantic_search("memory failures", entry_type="memory", limit=5)
        >>> for result in results:
        ...     print(f"{result['title']}: {result.get('similarity', 'N/A')}")
    """
    if not CKS_AVAILABLE:
        logger.warning("CKS not available, returning empty results")
        return []

    try:
        # Import CKS class
        from cks.unified import CKS  # type: ignore[import-untyped]

        # Initialize CKS (uses default db_path)
        with CKS(enable_semantic=enable_semantic) as cks:
            if enable_semantic:
                # Use semantic search
                results = cks.search_semantic(
                    query=query,
                    entry_type=entry_type,
                    limit=limit,
                )
                logger.debug(f"Semantic search returned {len(results)} results for '{query}'")
            else:
                # Fallback to keyword search
                results = cks.search(
                    query=query,
                    entry_type=entry_type,
                    limit=limit,
                )
                logger.debug(f"Keyword search returned {len(results)} results for '{query}'")

            return results  # type: ignore[no-any-return]

    except Exception as e:
        logger.error(f"CKS search failed: {e}")
        return []


def cks_semantic_domain_search(
    query: str,
    domain: str | None = None,
    entry_type: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Perform domain-aware semantic search on CKS.

    Enhances semantic search with domain-specific query expansion and filtering.

    Args:
        query: Search query text
        domain: Domain hint (cli, python, data-pipeline, precedent) for context
        entry_type: Filter by entry type (memory, pattern, code, knowledge, etc.)
        limit: Maximum number of results to return

    Returns:
        List of matching entries with similarity scores, sorted by relevance

    Example:
        >>> results = cks_semantic_domain_search(
        ...     "async patterns",
        ...     domain="python",
        ...     entry_type="pattern",
        ...     limit=5
        ... )
    """
    if not CKS_AVAILABLE:
        logger.warning("CKS not available, returning empty results")
        return []

    try:
        from cks.unified import CKS

        # Enhance query with domain context if provided
        enhanced_query = query
        if domain:
            domain_contexts = {
                "cli": ["command line", "terminal", "shell", "posix", "cli"],
                "python": ["python", "asyncio", "type hint", "pydantic", "fastapi"],
                "data-pipeline": ["etl", "pipeline", "streaming", "batch", "kafka"],
                "precedent": ["adr", "decision record", "architecture decision"],
            }
            context_terms = domain_contexts.get(domain, [])
            if context_terms and not any(term.lower() in query.lower() for term in context_terms):
                # Add most relevant context term to query for semantic matching
                enhanced_query = f"{query} {context_terms[0]}"
                logger.debug(f"Enhanced query with domain context: '{enhanced_query}'")

        with CKS(enable_semantic=True) as cks:
            results = cks.search_semantic(
                query=enhanced_query,
                entry_type=entry_type,
                limit=limit,
            )
            logger.debug(f"Domain-aware semantic search returned {len(results)} results")
            return results  # type: ignore[no-any-return]

    except Exception as e:
        logger.error(f"CKS domain search failed: {e}")
        return []


def _extract_entry_content(entry: dict) -> tuple[str, str]:
    """
    Extract question and answer from a CKS entry with fallback logic.

    This helper function handles the variability in CKS entry storage formats:
    - Memory entries store question in metadata["question"] and answer in content
    - Pattern entries may only have title and content
    - Some entries may have empty or missing metadata

    Args:
        entry: CKS entry dictionary with potential keys:
               - id, title, content, metadata (dict with "question"), type

    Returns:
        Tuple of (question, answer) with fallback strategies:
        1. question: metadata["question"] → title (if missing/empty)
        2. answer: content field

    Example:
        >>> entry = {"id": "mem_1", "title": "What is JWT?", "content": "JWT is...",
        ...          "metadata": {"question": ""}}
        >>> question, answer = _extract_entry_content(entry)
        >>> question  # Falls back to title when metadata["question"] is empty
        'What is JWT?'
    """
    # Extract answer - always use content field
    answer = entry.get("content", "")

    # Extract question with fallback chain
    # 1. Try metadata["question"] first (full question for memory entries)
    # 2. Fall back to title field (truncated question or pattern title)

    metadata = entry.get("metadata")

    if metadata and isinstance(metadata, dict):
        question = metadata.get("question", "")
        # Trim and check if question is non-empty
        if question and question.strip():
            return question.strip(), answer

    # Fallback: use title field
    title = entry.get("title", "")
    return title.strip() if title else "", answer


def get_failure_history(
    subsystem: str,
    limit: int = 10,
) -> list[dict]:
    """
    Query CKS for failure history of a subsystem using semantic search.

    This function implements the Priority 1 enhancement: semantic search
    for CKS failure queries instead of keyword-based iteration.

    Args:
        subsystem: Subsystem name (memory, hooks, CKS, research, etc.)
        limit: Maximum number of failure entries to return

    Returns:
        List of failure-related memory and pattern entries

    Example:
        >>> failures = get_failure_history("memory", limit=5)
        >>> for failure in failures:
        ...     print(f"FAILURE: {failure['title']}")
    """
    # Semantic search for failures related to subsystem
    failure_query = f"{subsystem} failures bugs errors problems crashes"
    results = cks_semantic_search(
        query=failure_query,
        entry_type="memory",
        limit=limit,
    )

    # Also search for patterns related to failures
    pattern_results = cks_semantic_search(
        query=f"{subsystem} failure patterns",
        entry_type="pattern",
        limit=limit // 2,
    )

    # Combine results (patterns after memories)
    combined = results + pattern_results

    # Deduplicate by title/id
    seen = set()
    unique_results = []
    for result in combined:
        key = result.get("title") or result.get("id")
        if key and key not in seen:
            seen.add(key)
            unique_results.append(result)

    logger.debug(f"Found {len(unique_results)} unique failure entries for '{subsystem}'")
    return unique_results[:limit]
