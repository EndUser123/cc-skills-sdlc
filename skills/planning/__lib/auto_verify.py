#!/usr/bin/env python3
"""
Auto-verify implementation plans v2 — strict readiness gating.

Checks performed:
1. Placeholder detection — FAIL if any placeholder residue found
2. Section completeness — all required sections present
3. Solo-dev violations — no team coordination patterns
4. RTM coverage — requirements mapped to tasks
5. Contradiction checks — FAIL if plan claims ready but has unresolved blockers
6. Disposition checks — every blocker/high finding has machine-readable disposition
7. Plan-purity checks — FAIL if plan contains raw findings tables or verification dumps
8. Status header — FAIL if status header missing or malformed
9. Stateful contract checks — FAIL if applicable plans leave identity, ordering,
   dedupe, invalidation, source-of-truth, or isolation semantics ambiguous, if
   tests contradict those contracts, or if the documented mechanisms cannot fire
   under the plan's own invariants
10. Contract matrix checks — FAIL if contract-sensitive plans omit required
    matrix fields, per-row packet references, or test bindings
11. Contract authority drift — FAIL if planning-owned boundary semantics drift
    from the active planning contract or use unrecognized phase-precondition
    metadata to claim readiness

Usage:
    python P:\\\\\\.claude/skills/planning/__lib/auto_verify.py <plan_path>

Output:
    <plan_path>.review.result.json with verification results
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from arch_handoff_state import find_pending_arch_handoff_receipt, mark_arch_handoff_consumed

# DEPTH RULE: When skills/ layer is added, increment parents[N] by 1.
# e.g. from planning/__lib__/: parents[2]→[3] (sdlc/ is 3 levels up from __lib__/)
_ROOT = Path(__file__).resolve()
_CONTRACT_PRIMITIVES_CANDIDATES = [
    _ROOT.parents[3] / "contract-primitives" / "src",
    Path(_ROOT.anchor) / "packages" / "cc-skills-sdlc" / "contract-primitives" / "src",
]
for _candidate in _CONTRACT_PRIMITIVES_CANDIDATES:
    if _candidate.exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from contract_primitives import (
    ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR,
    PLACEHOLDER_BINDINGS,
    REQUIRED_PLAN_MATRIX_FIELDS,
    adr_requires_planning_handoff,
    extract_markdown_table,
    find_contract_boundary_rows,
    parse_planning_handoff_packet,
    parse_planning_source_packet,
)

# Configurable skill search paths for evidence resolution
DEFAULT_SKILL_SEARCH_PATHS = [
    Path.home() / ".claude" / "skills",  # User-level skills
    Path("P:\\\\\\__csf") / ".claude" / "skills",  # Project P: drive skills (if exists)
    Path("C:/Users/brsth") / ".claude" / "skills",  # Project C: drive skills (if exists)
]

# Required plan sections (v2 canonical names, with legacy aliases accepted for compatibility)
SECTION_ALIASES = {
    "goal": ["Goal", "Problem", "Problem Statement"],
    "current_state": [
        "Current State with Evidence",
        "Current state with evidence",
        "Current State",
        "Context",
        "Context Analysis",
        "Background",
        "Existing Implementation",
        "Existing Implementation Discovery",
        "Current Implementation",
    ],
    "design_decisions": [
        "Design Decisions and Invariants",
        "Design Decisions",
        "Design",
        "Solution",
        "Proposed Solution",
        "Approach",
    ],
    "implementation_changes": [
        "Implementation Changes",
        "Implementation Plan",
        "Implementation Steps",
        "Steps",
        "Tasks",
    ],
    "test_matrix": ["Test Matrix", "Test Coverage", "Test Discovery", "Tests", "Testing"],
    "assumptions": [
        "Assumptions/Defaults",
        "Assumptions and Defaults",
        "Assumptions",
        "Defaults",
        "Risks, Success Criteria, Dependencies",
    ],
    "open_questions": ["Open Questions", "Open Issues", "Questions"],
    "contract_authority_reference": ["Contract Authority Reference", "Contract-Authority Reference"],
    "contract_boundary_matrix": ["Contract Boundary Matrix", "Contract-Boundary Matrix"],
    "state_model_contracts": ["State Model Contracts", "State-Model Contracts"],
}

REQUIRED_SECTIONS = [
    SECTION_ALIASES[key][0]
    for key in [
        "goal",
        "current_state",
        "design_decisions",
        "implementation_changes",
        "test_matrix",
        "assumptions",
        "open_questions",
    ]
]

SOLO_DEV_VIOLATIONS = [
    r"stakeholder\s+approval",
    r"team\s+coordination",
    r"consensus\s+required",
    r"team\s+review",
    r"collaborative\s+effort",
    r"multi-?\s*team",
    r"cross-?\s*team",
    r"team\s+lead\s+approval",
]

REQUIRED_ADVERSARIAL_AGENTS = [
    "adversarial-compliance",
    "adversarial-logic",
    "adversarial-testing",
    "adversarial-security",
    "adversarial-failure-modes",
    "adversarial-critic",
]

ARCH_REMEDIATION_CATEGORIES = {
    "contract_ambiguity",
    "state_model",
    "schema_consistency",
    "identity_boundary",
    "contract_test_coherence",
    "mechanism_triggerability",
    "authority_drift",
    "execution_policy",
    "conditional_trigger",
}

ARCH_REMEDIATION_IDS = {
    "STATE-002",
}

# Placeholder patterns that block readiness
PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"Describe the problem",
    r"Add risk analysis",
    r"path/to/",
    r"Component A",
    r"Component B",
    r"Criteria one",
    r"Criteria two",
    r"Describe the solution",
    r"Add test coverage",
    r"\*Add .+\*",  # Italicized "Add ..." like "*Add risk analysis*"
    r"\[ \] .+",  # Unchecked checkbox placeholders
]

# Patterns that indicate raw findings/verification merged into plan
PLAN_PURITY_VIOLATIONS = [
    r"##\s*Adversarial Findings",
    r"##\s*Verification Results",
    r"##\s*Verification Status",
    r"\|\s*ID\s*\|\s*Severity\s*\|\s*Finding",  # Findings table
    r"###\s*BLOCKER",
    r"###\s*HIGH",
    r"auto_verify.*:\s*READY",
    r"auto_verify.*:\s*BLOCKED",
    r"##\s*Findings.*(?:compliance|logic|testing|security)",  # Raw findings headers
]

ADR_SOURCE_LINE_PATTERN = re.compile(r"^\*\*Source ADR:\*\*\s*`?([^`\n]+)`?", re.MULTILINE)
ADR_HEADING_PATTERNS = [
    "Context",
    "Design",
    "Contract Boundaries",
    "Implementation Sequence",
    "Dependencies",
    "Consequences",
]

CANONICAL_PLAN_SECTION_NAMES = {
    alias.lower()
    for aliases in SECTION_ALIASES.values()
    for alias in aliases
}

CANONICAL_PLAN_SECTION_NAMES = {
    alias.lower()
    for aliases in SECTION_ALIASES.values()
    for alias in aliases
}

STATEFUL_PLAN_PATTERNS = [
    r"\bwatermark\b",
    r"\bdedupe\b",
    r"\bdedup\b",
    r"\binvalidation\b",
    r"\bstale[- ]data\b",
    r"\bstale data immunity\b",
    r"\bterminal_id\b",
    r"\bturn_id\b",
    r"\bsession_id\b",
    r"\bevent log\b",
    r"\breplay\b",
    r"\bsource of truth\b",
    r"\bhandoff\b",
    r"\bresume\b",
    r"\brestore(?:d)?\b.{0,40}\b(?:state|session|payload|artifact|flow|context|history|resume)\b",
    r"\bledger\b",
    r"\bmulti-terminal\b",
]

PROVIDER_STATEFUL_PATTERNS = [
    r"\bprovider_instance_id\b",
    r"\bprovider_id\b",
    r"\bmulti-provider\b",
    r"\bprovider failover\b",
    r"\bprovider routing\b",
    r"\bprovider selection\b",
    r"\bprovider cache\b",
    r"\bfallback chain\b",
]

EVIDENCE_FILE_PATTERNS = (
    "py",
    "ts",
    "tsx",
    "json",
    "js",
    "jsx",
    "yaml",
    "yml",
    "toml",
    "md",
    "go",
    "rs",
    "java",
    "cs",
    "cpp",
    "c",
    "h",
    "ps1",
    "sh",
)

INLINE_FILE_LINE_RE = re.compile(
    rf"(?P<path>(?<!\.)(?:[A-Za-z]:[\/])?[\w./\-_]+\.(?!['\"])(?:{'|'.join(EVIDENCE_FILE_PATTERNS)}))(?:(?:#L|:)(?P<start>\d+)(?:[-:](?P<end>\d+))?)?",
    re.IGNORECASE,
)
EXPLICIT_FILE_LINE_RE = re.compile(
    r"^\s*\*\*(?:File|Path):\*\*\s*`?(?P<path>[^`\n]+?)`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
EXPLICIT_LINES_RE = re.compile(
    r"^\s*\*\*Lines?:\*\*\s*(?P<start>\d+)(?:\s*[-:]\s*(?P<end>\d+))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
LAYER_REFERENCE_RE = re.compile(r"\b(?:Layer|Tier)\s+\d+\b", re.IGNORECASE)
EXECUTION_SEMANTIC_KEYWORDS = (
    "blocking",
    "advisory",
    "optional",
    "fallback",
    "required",
    "must run",
    "always runs",
    "always run",
    "must execute",
)
VAGUE_CONDITIONAL_PATTERNS = (
    r"\bonly if needed\b",
    r"\bif needed\b",
    r"\bonly when needed\b",
    r"\bwhen necessary\b",
    r"\bas necessary\b",
    r"\bif insufficient\b",
    r"\bonly if .* insufficient\b",
)
TRIGGER_SIGNAL_KEYWORDS = (
    "trigger:",
    "trigger signal",
    "signal:",
    "criteria:",
    "condition:",
    "defined as",
    "measured by",
    "threshold",
    "when all of",
    "when both",
    "when either",
)

STATE_EXTENSION_FIELD_RE = re.compile(
    r"\b(?:add|introduce|extend)\b.{0,40}?`?(?P<field>[a-z_][a-z0-9_]*)`?(?::\s*(?P<value>\[[^\]]*\]|true|false|null|[a-z0-9_]+))?",
    re.IGNORECASE,
)
MODE_SYSTEM_CHANGE_PATTERNS = (
    "mode transition",
    "mode messages",
    "new modes",
    "iteration-based",
    "current_iteration",
)
SELECTOR_DEFAULT_PATTERNS = (
    "when ",
    "otherwise",
    "fallback",
    "default behavior",
    "when absent",
    "when missing",
    "degrade_to",
    "standard mode",
    "existing modes",
    "remain unchanged",
)
FIELD_DATA_FLOW_PATTERNS = (
    "producer",
    "consumer",
    "writes",
    "reads",
    "read by",
    "written by",
    "populate",
    "populated by",
    "stores",
    "format",
    "plain text",
    "structured object",
    "parsed by",
    "comes from",
    "from llm response",
    "source:",
)
FAILURE_MODE_TEST_PATTERNS = (
    "backward compatibility",
    "missing field",
    "field absent",
    "ttl",
    "expired",
    "interrupt",
    "interruption",
    "corrupt",
    "malformed",
    "empty",
    "fallback",
    "degrade",
    "inactive",
)

HOOK_VISIBLE_FIELD_RE = re.compile(r"`(?P<field>[a-z_][a-z0-9_]*)`")
HOOK_FIELD_CONTEXT_PATTERNS = (
    "stophook",
    "pretooluse",
    "state",
    "session",
    "payload",
    "field",
    "mode",
    "phase",
)
KNOWN_STATE_FIELDS = {
    "current_iteration",
    "max_iterations",
    "intermediate_answers",
    "final_answer",
}
HELPER_REFERENCE_RE = re.compile(r"(?<![A-Za-z0-9])(_[a-z][a-z0-9_]+)\(")
STRUCTURED_SCHEMA_PATTERNS = (
    "structured object",
    "structured objects",
    '{"id":',
    '"id":',
    '"claim":',
    "object list",
    "json object",
)
PARSER_DEPENDENCY_PATTERNS = (
    "extract",
    "regex",
    "pattern-match",
    "pattern matching",
    "llm response",
    "response prefixes",
    "parse the response",
    "parse response",
)
PARSER_FAILURE_POLICY_PATTERNS = (
    "retry",
    "re-prompt",
    "at least 2",
    "fewer than",
    "minimum",
    "malformed",
    "if extraction fails",
    "if fewer than",
    "fallback",
    "abort",
    "proceed with",
    "too many",
)
COMPONENT_OWNER_PATTERNS: dict[str, tuple[str, ...]] = {
    "pretooluse": ("pretooluse", "pre_tool_use", "pre-tool-use"),
    "stophook": ("stophook", "stophook", "stop hook"),
    "userpromptsubmit": ("userpromptsubmit", "user prompt submit", "userpromptsubmit"),
}
COMPONENT_LOGIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "pretooluse": (
        "pre_tool_use(",
        "pretooluse",
        "mode message",
        "mode messages",
        "is_hypothesis_mode",
        "select mode",
        "current_iteration",
        "branching logic",
    ),
    "stophook": (
        "stophook",
        "stophook",
        "_extract_hypotheses",
        "extract hypotheses",
        "parse the response",
        "parsed from the llm response",
        "hypothesis_details",
        "_format_hypothesis_context",
        "set_final_answer",
    ),
}

STATELESS_DECLARATION_PATTERNS = [
    r"\bthis plan is not stateful\b",
    r"\bnot stateful\b",
    r"\bstateless\b",
    r"\bno shared mutable state\b",
    r"\bno persistence\b",
    r"\beach .* call is independent\b",
    r"\bcall-scoped isolation\b",
]

NOT_APPLICABLE_DECLARATION_PATTERNS = [
    r"\bnot applicable\b",
    r"\bnot contract-sensitive\b",
    r"\bcontract[- ]sensitive\b.{0,20}\bno\b",
]

STATEFUL_CONTRADICTION_PATTERNS = [
    r"\bprovider_instance_id\b",
    r"\bprovider_id\b",
    r"\bsession_id\b",
    r"\bturn_id\b",
    r"\bterminal_id\b",
    r"\bwatermark\b",
    r"\breplay\b",
    r"\bevent log\b",
    r"\bsource of truth\b",
    r"\bmulti-terminal\b",
    r"\bmulti-provider\b",
]

ACCEPTANCE_PLACEHOLDER_PATTERNS = [
    r"^\s*tbd\s*$",
    r"^\s*tba\s*$",
    r"^\s*todo\s*$",
    r"^\s*to be decided\s*$",
    r"^\s*to be determined\s*$",
    r"^\s*n/?a\s*$",
    r"^\s*none\s*$",
]

AMBIGUOUS_CONTRACT_PATTERNS = [
    (
        "ordering/watermark",
        [
            r"(?:either|one of).{0,80}(?:ordering|watermark)",
            r"(?:ordering|watermark).{0,80}\b(?:either|or)\b",
            r"Alternative:.*(?:ordering|watermark)",
            r"parse numeric IDs?.{0,120}zero-padded",
            r"zero-padded.{0,120}parse numeric IDs?",
        ],
    ),
    (
        "dedupe",
        [
            r"(?:either|one of).{0,80}(?:dedupe|dedup)",
            r"(?:dedupe|dedup).{0,80}\b(?:either|or)\b",
            r"Alternative:.*(?:dedupe|dedup)",
        ],
    ),
    (
        "identity/isolation",
        [
            r"(?:either|one of).{0,80}(?:identity|terminal_id|provider_instance_id|isolation)",
            r"(?:identity|terminal_id|provider_instance_id|isolation).{0,80}\b(?:either|or)\b",
            r"Alternative:.*(?:identity|terminal_id|provider_instance_id|isolation)",
        ],
    ),
    (
        "freshness/invalidation",
        [
            r"(?:either|one of).{0,80}(?:invalidation|freshness|stale)",
            r"(?:invalidation|freshness|stale).{0,80}\b(?:either|or)\b",
            r"Alternative:.*(?:invalidation|freshness|stale)",
        ],
    ),
]

OPEN_QUESTION_BLOCKERS = [
    r"source of truth",
    r"authoritative",
    r"ordering",
    r"watermark",
    r"dedupe",
    r"dedup",
    r"invalidation",
    r"stale",
    r"freshness",
    r"task event",
    r"event source",
    r"isolation",
    r"terminal_id",
    r"provider_instance_id",
]


def extract_section_content(plan: str, section_name: str) -> str:
    """Extract content of a specific section from plan."""
    aliases_to_check = [section_name]
    for canonical_name, alias_list in SECTION_ALIASES.items():
        if section_name == canonical_name:
            aliases_to_check = alias_list
            break
        elif section_name in alias_list:
            aliases_to_check = alias_list
            break

    for alias in aliases_to_check:
        # Match H1-H6 headings so ### Section works alongside ## Section.
        # Note: uses r"" not rf"" to avoid {N} being interpolated as f-string tuple.
        #
        # Bug fix: non-greedy .*? with (?=^#{1,6}\s+) as lookahead stops
        # prematurely at H3 subsections (### TASK) that appear within a section,
        # because the lookahead matches at the first # character it sees.
        # This truncates the extracted content to just the inline task list
        # before H3 subsections begin.
        #
        # OLD (truncates at H3 subsections):
        #   pattern = r"^#{1,6}\s+" + re.escape(alias) + r".*?(?=^#{1,6}\s+|\Z)"
        #
        # NEW: require lookahead to match an H2 heading (##) or end-of-string.
        # This correctly skips over H3 task subsections (### TASK) within a section.
        pattern = r"^#{1,6}\s+" + re.escape(alias) + r".*?(?=^#{2}\s+|\Z)"
        match = re.search(pattern, plan, re.DOTALL | re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(0)
    return ""


def is_stateful_plan(plan: str) -> bool:
    """Heuristic detection for plans that need state/history/provider contract checks."""
    frontmatter = parse_frontmatter(plan)
    explicit_stateful = frontmatter.get("stateful", "").strip().lower()
    if explicit_stateful in {"true", "yes"}:
        return True
    if explicit_stateful in {"false", "no", "stateless"}:
        return False

    state_model_section = extract_section_content(plan, "state_model_contracts")
    # Check the state_model section directly — do NOT strip it before checking,
    # as stripping would remove the very negative declaration we need to detect.
    if _has_negative_declaration(state_model_section):
        return False

    searchable_text = _strip_negative_declaration_sections(plan)
    return any(
        re.search(pattern, searchable_text, re.IGNORECASE)
        for pattern in [*STATEFUL_PLAN_PATTERNS, *PROVIDER_STATEFUL_PATTERNS]
    )


def parse_frontmatter(plan: str) -> dict[str, str]:
    """Parse simple YAML-like frontmatter into a flat key/value dict."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", plan, re.DOTALL)
    if not match:
        return {}

    frontmatter = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip()

    return frontmatter


def _parse_int_frontmatter(frontmatter: dict[str, str], key: str) -> int | None:
    value = frontmatter.get(key)
    if value is None:
        return None
    value = value.strip().strip('"').strip("'")
    if not re.fullmatch(r"\d+", value):
        return None
    return int(value)


def _looks_like_adr_artifact(
    plan: str,
    frontmatter: dict[str, str],
    plan_path: str | None = None,
) -> bool:
    """Heuristically detect when the current artifact under verification is itself an ADR."""
    if frontmatter:
        return False

    heading_looks_adr = bool(re.search(r"^\s*#\s+ADR(?:\b|:|-)", plan, re.MULTILINE | re.IGNORECASE))
    if not heading_looks_adr:
        return False

    if not plan_path:
        return True

    normalized = plan_path.replace("\\", "/")
    file_name = Path(plan_path).name
    return (
        "arch_decisions/" in normalized.lower()
        or bool(re.search(r"(?:^|[/\\])ADR[-_ ]?\d+", normalized, re.IGNORECASE))
        or file_name.upper().startswith("ADR-")
    )


def detect_source_adr_path(
    plan: str,
    frontmatter: dict[str, str],
    plan_path: str | None = None,
) -> str | None:
    """Infer the source ADR path from frontmatter or legacy source line."""
    source = frontmatter.get("source", "").strip().strip('"').strip("'")
    if source and source.lower() != "null":
        normalized = source.replace("\\", "/")
        if "arch_decisions/" in normalized or re.search(r"(?:^|/)ADR[-_ ]?\d+", normalized, re.IGNORECASE):
            return source

    match = ADR_SOURCE_LINE_PATTERN.search(plan)
    if match:
        return match.group(1).strip()

    if plan_path and _looks_like_adr_artifact(plan, frontmatter, plan_path):
        return plan_path
    return None


def detect_source_artifact_path(plan: str, frontmatter: dict[str, str]) -> str | None:
    """Infer any non-null source artifact path from frontmatter or legacy source line."""
    source = frontmatter.get("source", "").strip().strip('"').strip("'")
    if source and source.lower() != "null":
        return source

    match = re.search(r"^\*\*Source:\*\*\s*`?([^`\n]+)`?", plan, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def extract_source_headings(source_text: str) -> list[str]:
    """Extract non-canonical headings from a source artifact for shallow-copy detection."""
    headings = []
    for raw_heading in re.findall(r"^##+\s+(.+)$", source_text, re.MULTILINE):
        heading = raw_heading.strip().strip("#").strip()
        lowered = heading.lower()
        if lowered in CANONICAL_PLAN_SECTION_NAMES:
            continue
        if lowered.startswith("plan:"):
            continue
        headings.append(heading)
    return headings


def detect_source_artifact_path(plan: str, frontmatter: dict[str, str]) -> str | None:
    """Infer any non-null source artifact path from frontmatter or legacy source line."""
    source = frontmatter.get("source", "").strip().strip('"').strip("'")
    if source and source.lower() != "null":
        return source

    match = re.search(r"^\*\*Source:\*\*\s*`?([^`\n]+)`?", plan, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def extract_source_headings(source_text: str) -> list[str]:
    """Extract non-canonical headings from a source artifact for shallow-copy detection."""
    headings = []
    for raw_heading in re.findall(r"^##+\s+(.+)$", source_text, re.MULTILINE):
        heading = raw_heading.strip().strip("#").strip()
        lowered = heading.lower()
        if lowered in CANONICAL_PLAN_SECTION_NAMES:
            continue
        if lowered.startswith("plan:"):
            continue
        headings.append(heading)
    return headings


def _has_negative_declaration(section_text: str) -> bool:
    lowered = section_text.lower()
    return any(
        re.search(pattern, lowered, re.IGNORECASE)
        for pattern in [*STATELESS_DECLARATION_PATTERNS, *NOT_APPLICABLE_DECLARATION_PATTERNS]
    )


def _strip_negative_declaration_sections(plan: str) -> str:
    searchable = plan.lower()
    for section_name in [
        "state_model_contracts",
        "contract_authority_reference",
        "contract_boundary_matrix",
        "implementation_changes",
    ]:
        section_text = extract_section_content(plan, section_name)
        if section_text and _has_negative_declaration(section_text):
            searchable = searchable.replace(section_text.lower(), " ")

    # Unconditionally strip sections that describe verification procedures,
    # not stateful implementation details.
    for section_name in ["test_matrix", "requirements_trace_matrix"]:
        section_text = extract_section_content(plan, section_name)
        if not section_text:
            # Fallback: search for raw header if not in SECTION_ALIASES
            # Handles sections like "Requirements Trace Matrix" that aren't aliased
            header_patterns = {
                "test_matrix": r"^## Test Matrix\n.*?(?=\n#{1,6}\s|\Z)",
                "requirements_trace_matrix": r"^## Requirements Trace Matrix\n.*?(?=\n#{1,6}\s|\Z)",
            }
            if section_name in header_patterns:
                match = re.search(header_patterns[section_name], plan, re.DOTALL | re.MULTILINE | re.IGNORECASE)
                if match:
                    section_text = match.group(0)
        if section_text:
            searchable = searchable.replace(section_text.lower(), " ")

    return searchable


def _resolve_evidence_path(raw_path: str, plan_path: str | None = None) -> Path | None:
    """Resolve an evidence file path against known skill locations.

    Searches multiple known skill directory locations to find files that
    may be cited with absolute paths that don't resolve correctly on Windows
    cross-drive scenarios.

    Args:
        raw_path: File path string from plan evidence citation (may be absolute or relative)
        plan_path: Optional plan path for relative path resolution

    Returns:
        Path object if found in any search location, None otherwise
    """
    normalized = raw_path.strip().strip("`").strip().strip('"').strip("'")
    if not normalized or "://" in normalized:
        return None

    path = Path(normalized.replace("\\", "/"))

    # If path is already absolute, first check it directly
    if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", normalized):
        if path.exists():
            return path
        # For absolute paths that don't exist, search in skill locations
        filename = path.name
        for search_base in DEFAULT_SKILL_SEARCH_PATHS:
            if not search_base.exists():
                continue
            candidate = search_base / filename
            if candidate.exists():
                return candidate
    else:
        # For relative paths, use existing logic
        if plan_path:
            candidate = Path(plan_path).resolve().parent / path
            if candidate.exists():
                return candidate
        candidate = Path.cwd() / path
        if candidate.exists():
            return candidate

    return None


def _resolve_file_reference(raw_path: str, plan_path: str | None) -> list[Path]:
    normalized = raw_path.strip().strip("`").strip().strip('"').strip("'")
    if not normalized or "://" in normalized:
        return []
    # Strip line-range suffixes (e.g. :1040, :1040-1044, #L1040) before path resolution.
    # On Windows, Path("P:\\\\\\foo.py:1040-1044").exists() is False because the colon
    # makes the path invalid — we must strip the suffix first.
    normalized = re.sub(r"[:#]L?\d+(?:[-\d]*)?$", "", normalized)
    path = Path(normalized.replace("\\", "/"))
    candidates: list[Path] = []
    if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", normalized):
        candidates.append(Path(normalized))
    else:
        if plan_path:
            candidates.append(Path(plan_path).resolve().parent / path)
        candidates.append(Path.cwd() / path)
        # Also search the hooks directory for hook-related file references
        # (e.g. PreToolUse.py, PreToolUse_investigation_gate.py).
        hooks_dir = Path(__import__('os').environ.get("CLAUDE_HOOKS_DIR", "P:\\\\\\.claude/hooks"))
        if hooks_dir.exists():
            candidates.append(hooks_dir / path)
        # Search P: drive for cross-drive compatibility (plan on C:, files on P:).
        p_drive = Path("P:\\\\\\")
        if p_drive.exists():
            candidates.append(p_drive / path)
            try:
                for match in p_drive.rglob(path.name):
                    if match.is_file() and match.name == path.name:
                        candidates.append(match)
                        break
            except OSError:
                pass
    # preserve order, remove duplicates
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _file_line_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _paragraphs_with_layer_signals(plan: str) -> list[str]:
    sections = [
        extract_section_content(plan, "Current State with Evidence"),
        extract_section_content(plan, "Design Decisions and Invariants"),
        extract_section_content(plan, "Implementation Changes"),
    ]
    text = "\n\n".join(section for section in sections if section)
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def _current_state_cited_files(plan: str, plan_path: str | None = None) -> list[Path]:
    """Collect file paths cited across all evidence-bearing sections.

    Scans Current State, Design Decisions, and Implementation Changes for both
    explicit (File:/Path:) and inline (filename.py) file references.
    """
    sections_to_scan = [
        extract_section_content(plan, "Current State with Evidence"),
        extract_section_content(plan, "Design Decisions and Invariants"),
        extract_section_content(plan, "Implementation Changes"),
    ]
    paths: list[Path] = []
    seen: set[str] = set()
    for section in sections_to_scan:
        if not section:
            continue
        for match in EXPLICIT_FILE_LINE_RE.finditer(section):
            for candidate in _resolve_file_reference(match.group("path"), plan_path):
                if candidate.exists():
                    key = str(candidate.resolve())
                    if key not in seen:
                        seen.add(key)
                        paths.append(candidate.resolve())
                    break
        for match in INLINE_FILE_LINE_RE.finditer(section):
            for candidate in _resolve_file_reference(match.group("path"), plan_path):
                if candidate.exists():
                    key = str(candidate.resolve())
                    if key not in seen:
                        seen.add(key)
                        paths.append(candidate.resolve())
                    break
    return paths


def _extract_added_state_fields(plan: str) -> list[tuple[str, str | None]]:
    fields: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    design = extract_section_content(plan, "Design Decisions and Invariants")
    changes = extract_section_content(plan, "Implementation Changes")
    combined = "\n".join(section for section in [design, changes] if section)
    for match in STATE_EXTENSION_FIELD_RE.finditer(combined):
        field = match.group("field").lower()
        if field in {"mode", "current_iteration", "max_iterations"}:
            continue
        if field not in seen:
            seen.add(field)
            fields.append((field, (match.group("value") or "").lower() or None))
    return fields


def _extract_hook_visible_fields(plan: str) -> list[str]:
    """Return hook-visible field names referenced in design or implementation prose."""
    relevant = "\n".join(
        [
            extract_section_content(plan, "Design Decisions and Invariants"),
            extract_section_content(plan, "Implementation Changes"),
            extract_section_content(plan, "State Model Contracts"),
        ]
    )
    fields: list[str] = []
    seen: set[str] = set()
    for line in relevant.splitlines():
        lowered_line = line.lower()
        if not any(marker in lowered_line for marker in HOOK_FIELD_CONTEXT_PATTERNS):
            continue
        for match in HOOK_VISIBLE_FIELD_RE.finditer(line):
            field = match.group("field").lower()
            if field in KNOWN_STATE_FIELDS:
                continue
            if field not in seen:
                seen.add(field)
                fields.append(field)
    return fields


def _extract_phase_headings(plan: str) -> list[int]:
    return sorted(
        {
            int(match)
            for match in re.findall(r"^#{2,6}\s+Phase\s+(\d+)\b", plan, re.IGNORECASE | re.MULTILINE)
        }
    )


def _extract_phase_precondition_blocks(frontmatter: dict[str, str]) -> list[int]:
    blocked: list[int] = []
    for key in frontmatter:
        match = re.fullmatch(r"phase(\d+)_preconditions", key)
        if not match:
            continue
        count = _parse_int_frontmatter(frontmatter, key) or 0
        if count > 0:
            blocked.append(int(match.group(1)))
    return blocked


def _extract_deferred_blocker_phases(plan: str) -> list[int]:
    match = re.search(r"^##\s+Deferred Blockers.*?(?=^##\s|\Z)", plan, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if not match:
        return []

    headers, rows = extract_markdown_table(match.group(0))
    if not headers or "Phase" not in headers:
        return []

    blocked: list[int] = []
    for row in rows:
        phase_cell = row.get("Phase", "")
        phase_match = re.search(r"\bPhase\s+(\d+)\b|\b(\d+)\b", phase_cell, re.IGNORECASE)
        if not phase_match:
            continue
        phase_value = phase_match.group(1) or phase_match.group(2)
        if phase_value:
            blocked.append(int(phase_value))
    return blocked


def infer_phase_ready_through(plan: str, frontmatter: dict[str, str] | None = None) -> int | None:
    """Infer bounded phase readiness from explicit metadata or deferred blockers.

    The verifier only infers bounded readiness when the plan names a later blocked
    phase explicitly. It does not infer "all phases ready" from headings alone.
    """

    frontmatter = frontmatter or parse_frontmatter(plan)
    explicit = _parse_int_frontmatter(frontmatter, "phase_ready_through")
    if explicit is not None and explicit > 0:
        return explicit

    blocked_phases = sorted(
        set(
            [
                *_extract_phase_precondition_blocks(frontmatter),
                *_extract_deferred_blocker_phases(plan),
            ]
        )
    )
    if not blocked_phases:
        return None

    earliest_blocked = blocked_phases[0]
    if earliest_blocked <= 1:
        return None

    phase_headings = _extract_phase_headings(plan)
    inferred = earliest_blocked - 1
    if phase_headings:
        inferred = min(inferred, max(phase_headings))
    return inferred if inferred > 0 else None


def _is_contract_sensitive(plan: str, frontmatter: dict[str, str] | None = None) -> bool:
    frontmatter = frontmatter or parse_frontmatter(plan)
    headers, rows = find_contract_boundary_rows(plan)
    if headers or rows:
        return True

    contract_sensitive = str(frontmatter.get("contract_sensitive", "")).strip().lower()
    if contract_sensitive in {"yes", "true", "1"}:
        return True
    if contract_sensitive in {"no", "false", "0"}:
        return False

    authority_section = extract_section_content(plan, "contract_authority_reference")
    if authority_section:
        if _has_negative_declaration(authority_section):
            return False
        return True

    boundary_section = extract_section_content(plan, "contract_boundary_matrix")
    if boundary_section and _has_negative_declaration(boundary_section):
        return False
    return False


def check_contract_sensitivity_contradictions(plan: str) -> list[dict[str, Any]]:
    """Fail when a plan declares itself non-contract-sensitive but still provides real boundary rows."""
    findings = []
    headers, rows = find_contract_boundary_rows(plan)
    if not headers and not rows:
        return findings

    frontmatter = parse_frontmatter(plan)
    contract_sensitive = str(frontmatter.get("contract_sensitive", "")).strip().lower()
    authority_section = extract_section_content(plan, "contract_authority_reference")
    explicitly_negative = contract_sensitive in {"no", "false", "0"} or (
        authority_section and _has_negative_declaration(authority_section)
    )
    if explicitly_negative:
        findings.append(
            {
                "id": "CONTRACT-DECL-001",
                "category": "schema_consistency",
                "priority": "HIGH",
                "title": "Plan declares itself non-contract-sensitive but includes boundary rows",
                "description": (
                    "A real Contract Boundary Matrix table is present, so the plan must be treated "
                    "as contract-sensitive. Remove the table or update the declaration."
                ),
            }
        )
    return findings


def extract_requirements(plan: str) -> list[dict[str, str]]:
    """Extract requirements from Goal section."""
    section = extract_section_content(plan, "Goal")
    if not section:
        return []

    requirements = []
    pattern = r"(?:^\s*\d+\.\s*|^\s*-\s*)(.+?)(?=(?:^\s*\d+\.\s*)|(?:^\s*-\s*)|\Z)"
    matches = re.findall(pattern, section, re.MULTILINE | re.DOTALL)

    for i, match in enumerate(matches, 1):
        text = match.strip()
        if text and len(text) > 10:
            requirements.append({"id": f"REQ-{i:03d}", "text": text[:200]})

    if requirements:
        return requirements

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            continue
        normalized = " ".join(line.strip() for line in paragraph.splitlines())
        if len(normalized) > 20:
            requirements.append({"id": "REQ-001", "text": normalized[:200]})
            break
    return requirements


def _strip_code_fences(text: str) -> str:
    """Remove triple-backtick code fences so ** inside them doesn't confuse block boundaries."""
    lines = text.splitlines()
    result: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append(line)
    return "\n".join(result)


def _has_non_placeholder_acceptance_text(text: str) -> bool:
    normalized = text.strip().strip("-").strip()
    if not normalized:
        return False
    if any(
        re.fullmatch(pattern, normalized, re.IGNORECASE)
        for pattern in ACCEPTANCE_PLACEHOLDER_PATTERNS
    ):
        return False
    # Split on sentence boundaries (period, em-dash, semicolon) and check each clause
    # If any clause explicitly declines to provide criteria, the whole line is rejected
    clauses = re.split(r"[.;—–-]", normalized)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        # Explicit "no acceptance criteria" / "deleted task" / deferred phrasing — not real criteria
        if re.search(
            r"(?i)\b(no new acceptance|acceptance criteria.*deleted|this task is deleted|deferred|not applicable\b.*acceptance)",
            clause,
        ):
            return False
    return True


def _extract_acceptance_body(task_block: str) -> str:
    lines = task_block.splitlines()
    for idx, line in enumerate(lines):
        # Handle inline **Acceptance Criteria:** header on same line as task heading
        # e.g. "### TASK-003: DELETED — Covered by TASK-002\n**Acceptance Criteria**: ..."
        inline_match = re.match(
            r"^#{1,6}\s+(?:TASK|CHANGE)-\d+[:\s]+[^\n]*\*\*Acceptance(?: Criteria)?(?:\s*\(?[^)]*\)?)?:\*\*\s*(.*)$",
            line,
            re.IGNORECASE,
        )
        if inline_match:
            inline = inline_match.group(1).strip()
            collected: list[str] = []
            if inline:
                collected.append(inline)
            for follow in lines[idx + 1:]:
                if re.match(r"^\*\*(?:TASK|CHANGE)-", follow):
                    break
                if re.match(r"^##\s+", follow):
                    break
                if follow.strip().startswith("**") and not re.search(r"\*\*File\*\*", follow, re.IGNORECASE):
                    break
                if follow.strip():
                    collected.append(follow.strip())
            return "\n".join(collected)

        if re.search(r"\*\*Acceptance(?: Criteria)?(?:\s*\(?[^)]*\)?)?:\*\*", line, re.IGNORECASE):
            inline = re.sub(
                r".*?\*\*Acceptance(?: Criteria)?(?:\s*\(?[^)]*\)?)?:\*\*",
                "",
                line,
                flags=re.IGNORECASE,
            ).strip()
            collected: list[str] = []
            if inline:
                collected.append(inline)
            for follow in lines[idx + 1:]:
                if re.match(r"^\*\*(?:TASK|CHANGE)-", follow):
                    break
                if re.match(r"^##\s+", follow):
                    break
                if follow.strip().startswith("**") and not re.search(r"\*\*File\*\*", follow, re.IGNORECASE):
                    break
                if follow.strip():
                    collected.append(follow.strip())
            return "\n".join(collected)

        bullet_match = re.match(r"^(\s*)-\s+Acceptance(?: Criteria)?:\s*(.*)$", line, re.IGNORECASE)
        if bullet_match:
            indent, inline = bullet_match.groups()
            header_indent = len(indent)
            collected: list[str] = [inline.strip()] if inline.strip() else []
            for follow in lines[idx + 1:]:
                if not follow.strip():
                    continue
                current_indent = len(follow) - len(follow.lstrip(" "))
                if current_indent <= header_indent and re.match(r"^\s*-\s+", follow):
                    break
                if current_indent <= header_indent and re.match(r"^##\s+", follow):
                    break
                if current_indent <= header_indent and re.match(r"^\*\*(?:TASK|CHANGE)-", follow):
                    break
                collected.append(follow.strip())
            return "\n".join(collected)
    return ""


def _keyword_set(text: str) -> set[str]:
    normalized = text.replace("_", " ").replace("-", " ")
    tokens = re.findall(r"\b[a-zA-Z]{4,}\b", normalized.lower())
    stems: set[str] = set()
    for token in tokens:
        stem = token
        if stem.endswith("ing") and len(stem) > 6:
            stem = stem[:-3]
        elif stem.endswith("ed") and len(stem) > 5:
            stem = stem[:-2]
        elif stem.endswith("es") and len(stem) > 5:
            stem = stem[:-2]
        elif stem.endswith("s") and len(stem) > 4:
            stem = stem[:-1]
        stems.add(stem)
    return stems


def extract_tasks(plan: str) -> list[dict[str, Any]]:
    """Extract changes/tasks from Implementation Changes section."""
    section = extract_section_content(plan, "Implementation Changes")
    if not section:
        return []

    tasks = []
    section_stripped = _strip_code_fences(section)
    header_pattern = re.compile(
        r"^(?:\*\*(?:TASK|CHANGE)-(\d+)[:\*\s]+([^\n]+)|#{1,6}\s+(?:TASK|CHANGE)-(\d+)[:\s]+([^\n]+)|(?:TASK|CHANGE)-(\d+)[:\s]+([^\n]+))",
        re.MULTILINE,
    )
    matches = list(header_pattern.finditer(section_stripped))

    for idx, match in enumerate(matches):
        groups = match.groups()
        task_num = (groups[0] or groups[2] or groups[4] or "").lstrip("0") or "0"
        title = groups[1] or groups[3] or groups[5]
        task_id = f"TASK-{task_num}"
        title_text = title.strip().rstrip("*").rstrip()
        if not title_text:
            continue

        next_header_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_stripped)
        task_block = section_stripped[match.start():next_header_start]

        # Acceptance criteria must be explicitly labeled; mentioning the word
        # "acceptance" in the task title does not count.
        has_acceptance_header = bool(
            re.search(
                r"\*\*Acceptance(?: Criteria)?(?:\s*\(?[^)]*\)?)?:\*\*",
                task_block,
                re.IGNORECASE,
            )
            or re.search(r"^\s*-\s+Acceptance(?: Criteria)?:", task_block, re.IGNORECASE | re.MULTILINE)
        )
        acceptance_body = _extract_acceptance_body(task_block)
        acceptance_lines = [line for line in acceptance_body.splitlines() if line.strip()]
        has_acceptance_content = any(
            _has_non_placeholder_acceptance_text(line)
            for line in acceptance_lines
        )
        has_acceptance = has_acceptance_header and has_acceptance_content

        tasks.append(
            {"id": task_id, "title": title_text[:100], "has_acceptance_criteria": has_acceptance}
        )

    # Deduplicate by task_id, keeping last occurrence (H3 subsection with
    # acceptance criteria appears later in the section scan, so it overwrites
    # the earlier inline task list entry which lacks acceptance criteria).
    seen: dict[str, dict[str, Any]] = {}
    for task in tasks:
        seen[task["id"]] = task  # last occurrence wins
    tasks = list(seen.values())

    return tasks


def _implementation_change_blocks(plan: str) -> list[tuple[str, str]]:
    """Extract implementation change blocks keyed by their heading/title."""
    section = extract_section_content(plan, "Implementation Changes")
    if not section:
        return []

    section_stripped = _strip_code_fences(section)
    header_pattern = re.compile(
        r"^(?:\*\*(?:TASK|CHANGE)-(\d+)[:\*\s]+([^\n]+)|#{1,6}\s+(?:TASK|CHANGE)-(\d+)[:\s]+([^\n]+)|(?:TASK|CHANGE)-(\d+)[:\s]+([^\n]+))",
        re.MULTILINE,
    )
    matches = list(header_pattern.finditer(section_stripped))
    blocks: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        groups = match.groups()
        title = (groups[1] or groups[3] or groups[5] or "").strip()
        if not title:
            continue
        next_header_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_stripped)
        blocks.append((title, section_stripped[match.start():next_header_start]))
    return blocks


def check_status_header(plan: str) -> list[dict[str, Any]]:
    """Check that status header is present and valid."""
    findings = []
    frontmatter = parse_frontmatter(plan)
    valid_statuses = {"draft", "in-review", "implementation-ready"}

    if not frontmatter:
        findings.append(
            {
                "id": "STATUS-001",
                "category": "status_header",
                "priority": "HIGH",
                "title": "Missing status frontmatter",
                "description": (
                    "Plan must begin with frontmatter containing status, source, and unresolved_blockers"
                ),
            }
        )
        return findings

    status = frontmatter.get("status")
    if status not in valid_statuses:
        findings.append(
            {
                "id": "STATUS-002",
                "category": "status_header",
                "priority": "HIGH",
                "title": "Missing or invalid status value",
                "description": (
                    "Frontmatter status must be one of: draft, in-review, implementation-ready"
                ),
            }
        )

    if "source" not in frontmatter:
        findings.append(
            {
                "id": "STATUS-003",
                "category": "status_header",
                "priority": "HIGH",
                "title": "Missing source metadata",
                "description": "Frontmatter must include source: <path or null>",
            }
        )

    unresolved_value = frontmatter.get("unresolved_blockers")
    if unresolved_value is None or not re.fullmatch(r"\d+", unresolved_value):
        findings.append(
            {
                "id": "STATUS-004",
                "category": "status_header",
                "priority": "HIGH",
                "title": "Missing or invalid unresolved_blockers metadata",
                "description": "Frontmatter must include unresolved_blockers: <non-negative integer>",
            }
        )

    phase_ready_value = frontmatter.get("phase_ready_through")
    if phase_ready_value is not None and not re.fullmatch(
        r"\d+", phase_ready_value.strip().strip('"').strip("'")
    ):
        findings.append(
            {
                "id": "STATUS-005",
                "category": "status_header",
                "priority": "HIGH",
                "title": "Invalid phase_ready_through metadata",
                "description": "phase_ready_through must be a positive integer when present.",
            }
        )

    return findings


def check_placeholders(plan: str) -> list[dict[str, Any]]:
    """FAIL if any placeholder pattern is found in the plan."""
    findings = []
    for pattern in PLACEHOLDER_PATTERNS:
        matches = re.findall(pattern, plan, re.IGNORECASE)
        if matches:
            # Deduplicate by pattern
            findings.append(
                {
                    "id": f"PLACEHOLDER-{len(findings) + 1:03d}",
                    "category": "placeholder",
                    "priority": "HIGH",
                    "title": f"Placeholder residue found: {pattern!r}",
                    "description": f"Pattern {pattern!r} matched {len(matches)} time(s). Replace with concrete content.",
                    "matched_count": len(matches),
                }
            )
    return findings


def check_plan_purity(plan: str) -> list[dict[str, Any]]:
    """FAIL if plan contains raw findings tables or verification dumps."""
    findings = []
    for pattern in PLAN_PURITY_VIOLATIONS:
        if re.search(pattern, plan, re.IGNORECASE | re.MULTILINE):
            findings.append(
                {
                    "id": f"PURITY-{len(findings) + 1:03d}",
                    "category": "plan_purity",
                    "priority": "HIGH",
                    "title": "Raw findings or verification output merged into plan",
                    "description": f"Pattern {pattern!r} suggests raw review output is in the plan artifact. Findings must live in separate files.",
                }
            )
    return findings


def check_section_completeness(plan: str) -> list[dict[str, Any]]:
    """Check that all required sections are present."""
    findings = []
    for section in REQUIRED_SECTIONS:
        if not extract_section_content(plan, section):
            findings.append(
                {
                    "id": f"SECTION-{len(findings) + 1:03d}",
                    "category": "structure",
                    "priority": "HIGH",
                    "title": f"Missing section: {section}",
                    "description": f"Required section '{section}' not found in plan",
                }
            )

    return findings


def check_adr_ingestion_contract(plan: str, plan_path: str | None = None) -> list[dict[str, Any]]:
    """Detect ADR-derived drafts that still mirror ADR structure instead of plan shape."""
    findings: list[dict[str, Any]] = []
    frontmatter = parse_frontmatter(plan)
    source_adr = detect_source_adr_path(plan, frontmatter, plan_path)
    if not source_adr:
        return findings
    normalized_plan_path = plan_path.replace("\\", "/") if plan_path else ""
    normalized_source_adr = source_adr.replace("\\", "/")
    self_sourced_adr = bool(normalized_plan_path and normalized_source_adr == normalized_plan_path)

    mirrored_headings = [
        heading
        for heading in ADR_HEADING_PATTERNS
        if re.search(rf"^##\s+{re.escape(heading)}\b", plan, re.MULTILINE)
    ]
    if not mirrored_headings and not self_sourced_adr:
        return findings

    missing_canonical = [
        section
        for section in ("Goal", "Implementation Changes", "Current State with Evidence")
        if not extract_section_content(plan, section)
    ]
    if frontmatter and not missing_canonical and not self_sourced_adr:
        return findings

    handoff_hint = ""
    source_path = Path(source_adr)
    if source_path.exists():
        try:
            source_text = source_path.read_text(encoding="utf-8")
        except OSError:
            source_text = ""
        if source_text:
            handoff = parse_planning_handoff_packet(source_text)
            if handoff.packet_version:
                handoff_hint = (
                    f" Source ADR already contains Planning Handoff Packet v{handoff.packet_version}; "
                    "rewrite from that packet before rerunning verification."
                )
            elif adr_requires_planning_handoff(source_text):
                handoff_hint = (
                    " Source ADR appears planning-bound but does not contain a Planning Handoff Packet; "
                    "rewrite locally now and treat the missing handoff as an upstream /arch closure defect."
                )

    findings.append(
        {
            "id": "ADR-INGEST-001",
            "category": "adr_ingestion",
            "priority": "HIGH",
            "title": "ADR-derived draft still requires local planning normalization",
            "description": (
                (
                    f"Current verification target '{source_adr}' is still an ADR artifact. "
                    if self_sourced_adr
                    else f"Draft sourced from '{source_adr}' still uses ADR headings ({', '.join(mirrored_headings)}). "
                )
                + (
                    f"Missing canonical plan structure: {', '.join(missing_canonical) or 'frontmatter'}."
                    if missing_canonical or not frontmatter
                    else "The draft must still be rewritten into the canonical planning artifact shape."
                )
                + " Canonicalize the plan locally before treating remaining issues as /arch blockers."
                + handoff_hint
            ),
            "source_adr": source_adr,
            "plan_path": plan_path,
        }
    )
    return findings


def check_source_ingestion_contract(plan: str, plan_path: str | None = None) -> list[dict[str, Any]]:
    """Detect non-ADR source drafts that still mirror source structure instead of plan shape."""
    findings: list[dict[str, Any]] = []
    frontmatter = parse_frontmatter(plan)
    source_path = detect_source_artifact_path(plan, frontmatter)
    if not source_path:
        return findings
    if detect_source_adr_path(plan, frontmatter):
        return findings

    missing_canonical = [
        section
        for section in ("Goal", "Implementation Changes", "Current State with Evidence")
        if not extract_section_content(plan, section)
    ]
    needs_normalization = bool(missing_canonical or not frontmatter)

    source_file = Path(source_path)
    source_text = ""
    if source_file.exists():
        try:
            source_text = source_file.read_text(encoding="utf-8")
        except OSError:
            source_text = ""

    mirrored_headings: list[str] = []
    source_hint = ""
    if source_text:
        mirrored_headings = [
            heading
            for heading in extract_source_headings(source_text)
            if re.search(rf"^##\s+{re.escape(heading)}\b", plan, re.MULTILINE)
        ]
        source_packet = parse_planning_source_packet(source_text)
        if source_packet.packet_version:
            source_hint = (
                f" Source artifact already contains Planning Source Packet v{source_packet.packet_version}; "
                "rewrite from that packet before rerunning verification."
            )
        else:
            source_hint = (
                " Build an explicit extraction map or add a Planning Source Packet before treating "
                "the source text as planning-ready input."
            )

    if not needs_normalization and not mirrored_headings:
        return findings

    findings.append(
        {
            "id": "SOURCE-INGEST-001",
            "category": "source_ingestion",
            "priority": "HIGH",
            "title": "Source-derived draft still mirrors source structure",
            "description": (
                f"Draft sourced from '{source_path}' still requires local normalization into the canonical plan shape."
                + (
                    f" Mirrored source headings: {', '.join(mirrored_headings)}."
                    if mirrored_headings
                    else ""
                )
                + (
                    f" Missing canonical plan structure: {', '.join(missing_canonical)}."
                    if missing_canonical
                    else ""
                )
                + source_hint
            ),
            "source_path": source_path,
            "plan_path": plan_path,
        }
    )
    return findings


def check_ambiguous_contracts(plan: str) -> list[dict[str, Any]]:
    """Fail stateful plans that leave core mechanics as competing alternatives."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    lowered = _strip_negative_declaration_sections(plan)
    for contract_name, patterns in AMBIGUOUS_CONTRACT_PATTERNS:
        for pattern in patterns:
            match = re.search(pattern, lowered, re.IGNORECASE | re.DOTALL)
            if match:
                # Skip if match is in SQL command context (e.g., "INSERT OR IGNORE")
                # Only skip for specific SQL COMMAND OR patterns, not incidental SQL keywords
                matched_text = match.group(0).lower()
                if re.search(r"\b(insert|update|delete|replace|abort|rollback)\s+or\b", matched_text):
                    continue
                # Skip Python/JavaScript code patterns with get() or os.environ.get() fallback chains.
                if re.search(
                    r"\b\w+\s*\.\s*get\s*\(\s*['\"][^'\"]+['\"]\s*\)\s+or\b"
                    r"|\bos\s*\.\s*environ\s*\.\s*get\s*\(",
                    matched_text,
                ):
                    continue
                findings.append(
                    {
                        "id": f"AMBIGUITY-{len(findings) + 1:03d}",
                        "category": "contract_ambiguity",
                        "priority": "HIGH",
                        "title": f"Ambiguous {contract_name} contract",
                        "description": (
                            f"Stateful plans must choose one mandatory {contract_name} rule. "
                            "Mutually exclusive alternatives remain in the plan."
                        ),
                    }
                )
                break  # One finding per contract category
    return findings


def check_state_model_completeness(plan: str) -> list[dict[str, Any]]:
    """Require explicit state-model contracts for stateful/history/provider plans."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    lowered = plan.lower()

    # Contract-domain identity models: if present, the plan is using domain-specific
    # identity keys (transcript_path, finding_id, task_id, skill_name+step+terminal_id)
    # that are equally valid for contract-sensitive plans even if they don't match the
    # generic provider/ingest terminology (provider_id, source_id, turn_id).
    has_contract_identity_model = any(
        term in lowered
        for term in [
            "transcript_path",
            "finding_id",
            "task_id",
            "skill_name",
        ]
    ) and (
        "terminal_id" in lowered
        or "snapshot_id" in lowered
    )

    required_contracts = {
        "identity model": [
            ["provider_id", "source_id", "session_id", "terminal_id", "turn_id"],
            ["terminal_id", "safe_terminal"],
            ["per terminal"],
            ["identity", "per-terminal"],
        ],
        "ordering contract": [
            ["ordering contract"],
            ["watermark ordering"],
            ["ordering", "watermark"],
            ["monotonic", "ordering"],
        ],
        "dedupe contract": [
            ["dedupe contract"],
            ["dedupe key"],
            ["dedupe"],
            ["dedup"],
        ],
        "freshness/invalidation contract": [
            ["invalidation contract"],
            ["freshness contract"],
            ["invalidation", "replay"],
            ["stale data", "invalidation"],
            ["stale-data", "invalidation"],
        ],
        "event source of truth": [
            ["event source of truth"],
            ["source of truth"],
            ["authoritative event source"],
        ],
    }

    missing = []
    for contract_name, keyword_groups in required_contracts.items():
        # Skip generic provider/ingest identity model check if the plan uses contract-domain
        # identity keys (transcript_path, finding_id, task_id, skill_name) that are equally
        # valid for contract-sensitive plans.
        if contract_name == "identity model" and has_contract_identity_model:
            continue
        if not any(all(keyword in lowered for keyword in group) for group in keyword_groups):
            missing.append(contract_name)

    has_isolation_boundary = (
        "terminal-private" in lowered
        or "workspace-shared" in lowered
        or "isolation boundary" in lowered
        or "provider_instance_id" in lowered
    )
    if not has_isolation_boundary:
        missing.append("isolation boundary")

    if missing:
        findings.append(
            {
                "id": "STATE-001",
                "category": "state_model",
                "priority": "HIGH",
                "title": "Missing required state-model contracts",
                "description": (
                    "Stateful/history/provider plans must explicitly define these contracts: "
                    + ", ".join(missing)
                ),
            }
        )
    return findings


def check_stateless_contradictions(plan: str) -> list[dict[str, Any]]:
    """Fail when a plan declares itself stateless but still encodes stateful semantics."""
    findings = []
    # is_stateful_plan returning False means the plan self-declared non-stateful via
    # frontmatter or a negative declaration in state_model_contracts. Stateful signals
    # found in the body of such plans are expected — the plan is correctly describing
    # inherited semantics (e.g., a read-only CLI that queries an existing SQLite DB).
    if not is_stateful_plan(plan):
        return findings
    state_model_section = extract_section_content(plan, "state_model_contracts")
    if not state_model_section:
        return findings

    lowered_section = state_model_section.lower()
    if not _has_negative_declaration(state_model_section):
        return findings

    meaningful_section_text = "\n".join(
        line.lower()
        for line in state_model_section.splitlines()
        if "not applicable" not in line.lower()
    )
    searchable_text = plan.lower().replace(lowered_section, " ") + "\n" + meaningful_section_text

    contradiction_terms: list[str] = []
    for pattern in STATEFUL_CONTRADICTION_PATTERNS:
        term_label = pattern.strip(r"\b").replace("\\", "")
        for match in re.finditer(pattern, searchable_text, re.IGNORECASE):
            prefix = searchable_text[max(0, match.start() - 24):match.start()]
            if re.search(r"\b(no|not|without)\s+$", prefix, re.IGNORECASE):
                continue
            line_start = searchable_text.rfind("\n", 0, match.start()) + 1
            line_end = searchable_text.find("\n", match.end())
            if line_end == -1:
                line_end = len(searchable_text)
            line_text = searchable_text[line_start:line_end]
            if re.search(
                rf"\b(no|not|without)\b.{{0,30}}{re.escape(term_label)}",
                line_text,
                re.IGNORECASE,
            ):
                continue
            contradiction_terms.append(term_label)
            break
    contradiction_terms = sorted(set(contradiction_terms))
    if contradiction_terms:
        findings.append(
            {
                "id": "STATE-004",
                "category": "state_model",
                "priority": "HIGH",
                "title": "Plan declares itself stateless but still encodes stateful semantics",
                "description": (
                    "The plan says it is stateless, but these stateful signals remain present: "
                    + ", ".join(contradiction_terms)
                ),
            }
        )
    return findings


def check_unresolved_core_decisions(plan: str) -> list[dict[str, Any]]:
    """Fail stateful plans whose Open Questions still contain implementation-shaping decisions."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    open_questions = extract_section_content(plan, "Open Questions")
    if not open_questions:
        return findings

    lowered = open_questions.lower()
    blockers = [
        keyword
        for keyword in OPEN_QUESTION_BLOCKERS
        if re.search(rf"\b{keyword}\b", lowered, re.IGNORECASE)
    ]
    if blockers:
        findings.append(
            {
                "id": "STATE-002",
                "category": "open_questions",
                "priority": "HIGH",
                "title": "Open Questions contains unresolved core state-model decisions",
                "description": (
                    "Implementation-shaping questions remain open for: "
                    + ", ".join(sorted(set(blockers)))
                ),
            }
        )
    return findings


def check_boundary_overload(plan: str) -> list[dict[str, Any]]:
    """Fail when terminal_id is overloaded as a non-terminal identity."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    lowered = plan.lower()
    overload_patterns = [
        r"terminal_id.{0,120}(?:derived from|synthesized from|derived via).{0,120}(?:workspace|session|conversation|provider)",
        r"synthetic terminal_id",
        r"providers? that do not expose a real terminal",
    ]
    if (
        "terminal_id" in lowered
        and any(
            re.search(pattern, lowered, re.IGNORECASE | re.DOTALL) for pattern in overload_patterns
        )
        and "provider_instance_id" not in lowered
    ):
        findings.append(
            {
                "id": "STATE-003",
                "category": "identity_boundary",
                "priority": "HIGH",
                "title": "terminal_id is overloaded as a synthetic provider/session boundary",
                "description": (
                    "Use a separate provider_instance_id or equivalent field when no real terminal "
                    "exists. terminal_id cannot be the generic fallback identity."
                ),
            }
        )
    return findings


def check_claim_schema_consistency(plan: str) -> list[dict[str, Any]]:
    """Catch prose/schema mismatches for stateful plan mechanics."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    lowered = plan.lower()
    schema_mentions_native_id_key = bool(
        re.search(
            r"(?:primary key|unique(?:\s+key|\s+constraint)?|schema).{0,160}"
            r"provider_id.{0,80}source_id.{0,80}native_event_id.{0,80}content_hash",
            lowered,
            re.IGNORECASE | re.DOTALL,
        )
    )
    prose_claims_content_hash_dedupe = bool(
        re.search(
            r"(?:new|different).{0,40}native_event_id.{0,140}(?:dedupe|dedup|deduplicat).{0,80}content_hash",
            lowered,
            re.IGNORECASE | re.DOTALL,
        )
        or re.search(
            r"content_hash.{0,140}(?:dedupe|dedup|deduplicat).{0,100}(?:new|different).{0,40}native_event_id",
            lowered,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if schema_mentions_native_id_key and prose_claims_content_hash_dedupe:
        findings.append(
            {
                "id": "STATE-004",
                "category": "schema_consistency",
                "priority": "HIGH",
                "title": "Dedupe schema does not match stated content-hash behavior",
                "description": (
                    "The plan claims content-hash dedupe across changing native_event_id values, "
                    "but the described key shape still treats native_event_id as part of identity."
                ),
            }
        )
    return findings


def check_contract_test_coherence(plan: str) -> list[dict[str, Any]]:
    """Fail when the test matrix asserts behavior that contradicts a named contract."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    design = extract_section_content(plan, "Design Decisions and Invariants").lower()
    tests = extract_section_content(plan, "Test Matrix").lower()
    if not design or not tests:
        return findings

    dedupe_contract_collapses_bucket_duplicates = bool(
        "bucket_seconds = 10" in design
        and "assumed duplicates" in design
        and "only the first is retained" in design
    )
    dedupe_test_retains_bucket_duplicates = bool(
        "same 10s bucket" in tests and "both retained" in tests
    )
    if dedupe_contract_collapses_bucket_duplicates and dedupe_test_retains_bucket_duplicates:
        findings.append(
            {
                "id": "STATE-005",
                "category": "contract_test_coherence",
                "priority": "HIGH",
                "title": "Test matrix contradicts dedupe fallback contract",
                "description": (
                    "The dedupe contract says same-bucket events without a stable ID collapse to "
                    "one retained row, but the test matrix expects both events retained."
                ),
            }
        )

    return findings


def check_existing_flow_overlap(plan: str, plan_path: str | None = None) -> list[dict[str, Any]]:
    """Fail when a plan extends an existing mode/phase system without addressing overlapping live flows."""
    findings = []
    lowered_plan = plan.lower()
    if not any(pattern in lowered_plan for pattern in MODE_SYSTEM_CHANGE_PATTERNS):
        return findings

    if "investigation" in lowered_plan:
        return findings

    for cited_file in _current_state_cited_files(plan, plan_path):
        if cited_file.suffix.lower() != ".py":
            continue
        try:
            content = cited_file.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if "_investigation_phases" in content or 'mode == "investigation"' in content:
            findings.append(
                {
                    "id": "STATE-010",
                    "category": "state_model",
                    "priority": "HIGH",
                    "title": "Plan extends an existing mode system without addressing overlapping live flows",
                    "description": (
                        "A cited implementation file already contains an investigation/alternate flow, "
                        "but the plan does not state whether the new flow replaces it, coexists with it, "
                        "or how trigger selection distinguishes them."
                    ),
                    "evidence": str(cited_file),
                }
            )
            break
    return findings


def check_state_extension_contracts(plan: str) -> list[dict[str, Any]]:
    """Fail when newly added state fields lack selector/default or producer/consumer semantics."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    added_fields = _extract_added_state_fields(plan)
    hook_visible_fields = _extract_hook_visible_fields(plan)
    if not added_fields and not hook_visible_fields:
        return findings

    lowered = plan.lower()
    if any("mode" in field for field, _ in added_fields) and any(
        pattern in lowered for pattern in MODE_SYSTEM_CHANGE_PATTERNS
    ):
        if not any(marker in lowered for marker in SELECTOR_DEFAULT_PATTERNS):
            findings.append(
                {
                    "id": "STATE-011",
                    "category": "schema_consistency",
                    "priority": "HIGH",
                    "title": "Extended mode system lacks explicit selector and default behavior",
                    "description": (
                        "When a plan adds new mode-discriminator fields or alternate mode flows, it must "
                        "state how the standard and extended flows are selected and what happens when the "
                        "new discriminator field is absent or false."
                    ),
                }
            )

    fields_requiring_contracts = {
        field
        for field in hook_visible_fields
        if any(token in field for token in ["mode", "hypothes", "phase", "state", "detail"])
    }
    fields_requiring_contracts.update(
        field
        for field, _ in added_fields
        if any(token in field for token in ["mode", "hypothes", "phase", "state", "detail"])
    )

    for field in fields_requiring_contracts:
        field_context = "\n".join(line for line in plan.splitlines() if field in line.lower()).lower()
        if not any(marker in field_context for marker in FIELD_DATA_FLOW_PATTERNS):
            findings.append(
                {
                    "id": "STATE-012",
                    "category": "consumer_validation_gap",
                    "priority": "HIGH",
                    "title": f"State field '{field}' lacks producer/consumer data-flow contract",
                    "description": (
                        "Plans that add or repurpose persistent or hook-visible fields must state who writes "
                        "them, who reads them, where the data comes from, and the expected shape/format."
                    ),
                }
            )
            break

    for field, value in added_fields:
        if value in {"[]", "false", "true", "null"} and (
            "absent" not in lowered
            and "missing" not in lowered
            and "backward compat" not in lowered
            and "backward compatibility" not in lowered
            and "when " + field not in lowered
        ):
            findings.append(
                {
                    "id": "STATE-013",
                    "category": "schema_consistency",
                    "priority": "HIGH",
                    "title": f"New state field '{field}' lacks explicit default/absent-field behavior",
                    "description": (
                        "Schema-extension plans must say what happens when newly added fields are absent "
                        "in older state files or default to their unset value."
                    ),
                }
            )
            break
    return findings


def check_stateful_failure_mode_tests(plan: str) -> list[dict[str, Any]]:
    """Fail stateful extension plans that only test the happy path."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    lowered = plan.lower()
    if not any(pattern in lowered for pattern in MODE_SYSTEM_CHANGE_PATTERNS) and not _extract_added_state_fields(plan):
        return findings

    tests = extract_section_content(plan, "Test Matrix").lower()
    if not tests:
        return findings

    if not any(pattern in tests for pattern in FAILURE_MODE_TEST_PATTERNS):
        findings.append(
            {
                "id": "TEST-STATE-002",
                "category": "contract_test_coherence",
                "priority": "HIGH",
                "title": "Stateful extension plan lacks failure-mode test coverage",
                "description": (
                    "Stateful hook/workflow changes must test at least one unhappy-path scenario such as "
                    "missing fields, corrupted state, interruption/resume, TTL expiry, or fallback behavior."
                ),
            }
        )
    return findings


def check_change_component_alignment(plan: str) -> list[dict[str, Any]]:
    """Fail when a change block's scoped component does not match the logic it describes."""
    findings: list[dict[str, Any]] = []
    for title, block in _implementation_change_blocks(plan):
        lowered_title = title.lower()
        lowered_block = block.lower()
        owner: str | None = None
        for component, markers in COMPONENT_OWNER_PATTERNS.items():
            if any(marker in lowered_title for marker in markers):
                owner = component
                break
        if owner is None:
            continue

        for other_component, logic_markers in COMPONENT_LOGIC_PATTERNS.items():
            if other_component == owner:
                continue
            if any(marker in lowered_block for marker in logic_markers):
                findings.append(
                    {
                        "id": "CHANGE-ALIGN-001",
                        "category": "implementation_scope",
                        "priority": "HIGH",
                        "title": "Change block scopes one component but specifies another component's logic",
                        "description": (
                            f"The change block '{title}' is scoped to {owner}, but its body contains "
                            f"logic markers for {other_component}. Move the logic to the owning change "
                            "or restate the ownership boundary explicitly."
                        ),
                    }
                )
                return findings
    return findings


def check_parser_failure_policy(plan: str) -> list[dict[str, Any]]:
    """Fail parser-dependent plans that do not define validation/retry/fallback behavior."""
    findings: list[dict[str, Any]] = []
    lowered = plan.lower()
    relevant = "\n".join(
        [
            extract_section_content(plan, "Design Decisions and Invariants"),
            extract_section_content(plan, "Implementation Changes"),
            extract_section_content(plan, "Test Matrix"),
        ]
    ).lower()
    if "hypothes" not in relevant:
        return findings
    if not any(pattern in relevant for pattern in PARSER_DEPENDENCY_PATTERNS):
        return findings
    if not any(pattern in lowered for pattern in PARSER_FAILURE_POLICY_PATTERNS):
        findings.append(
            {
                "id": "STATE-014",
                "category": "schema_consistency",
                "priority": "HIGH",
                "title": "Parser-dependent structured state lacks validation and failure policy",
                "description": (
                    "If the design parses model output into structured state, the plan must say what "
                    "happens when extraction yields too few items, malformed data, or variant formatting, "
                    "including retry, fallback, or abort behavior."
                ),
            }
        )
    return findings


def check_helper_reference_clarity(plan: str, plan_path: str | None = None) -> list[dict[str, Any]]:
    """Fail plans that reference helper functions without defining whether they exist or will be added."""
    findings: list[dict[str, Any]] = []
    relevant = "\n".join(
        [
            extract_section_content(plan, "Design Decisions and Invariants"),
            extract_section_content(plan, "Implementation Changes"),
        ]
    )
    if not relevant:
        return findings

    cited_contents: list[str] = []
    for cited_file in _current_state_cited_files(plan, plan_path):
        try:
            cited_contents.append(cited_file.read_text(encoding="utf-8", errors="ignore").lower())
        except OSError:
            continue
    cited_blob = "\n".join(cited_contents)
    lowered_relevant = relevant.lower()
    for helper in {match.group(1) for match in HELPER_REFERENCE_RE.finditer(relevant)}:
        helper_lower = helper.lower()
        if helper_lower in cited_blob:
            continue
        if re.search(
            rf"(?:add|define|implement|create|reuse|use existing).{{0,80}}{re.escape(helper_lower)}",
            lowered_relevant,
            re.IGNORECASE | re.DOTALL,
        ):
            continue
        findings.append(
            {
                "id": "HELPER-001",
                "category": "implementation_scope",
                "priority": "HIGH",
                "title": "Plan references an undefined helper without ownership or implementation guidance",
                "description": (
                    f"The plan references `{helper}()` but does not show it in cited current-state files "
                    "and does not explicitly say whether it will be added, reused, or replaced by an existing helper."
                ),
            }
        )
    return findings


def check_duplicate_implementations(plan: str, plan_path: str | None = None) -> list[dict[str, Any]]:
    """Fail when plan proposes creating components that already exist in the codebase.

    Checks for duplicate class/file proposals by searching the codebase for existing
    implementations of the same name or similar functionality.
    """
    findings: list[dict[str, Any]] = []

    # Extract proposed new files and classes from Implementation Changes
    implementation_section = extract_section_content(plan, "Implementation Changes")
    if not implementation_section:
        return findings

    # Pattern to match task descriptions that propose creating classes
    # Examples:
    # - "Create `core/query_expander.py` with QueryExpander class"
    # - "**TASK-XXX**: Create `path/to/file.py` with ClassName"
    # Use double quotes for raw string to avoid quote escaping issues
    task_class_pattern = re.compile(
        r"(?:Create|New file|Modify).*?[`'\"]([^`'\"]+/([^`'\"]+)\.py)[`'\"]?\s+(?:with\s+?)?([A-Z]\w*)\s+class",
        re.MULTILINE | re.IGNORECASE
    )

    # Also match direct class name mentions in task descriptions
    class_mention_pattern = re.compile(
        r"(?:Create|New file|Modify).*?[`'\"]([^`'\"]+\.py)[`'\"]?\s+(?:with\s+)?([A-Z]\w+)(?:\s+class|$)",
        re.MULTILINE | re.IGNORECASE
    )

    proposed_classes = set()

    # Extract class names from task descriptions
    for match in task_class_pattern.finditer(implementation_section):
        if match.group(3):  # The class name group
            proposed_classes.add(match.group(3))
    for match in class_mention_pattern.finditer(implementation_section):
        if match.group(2):  # The class name group
            proposed_classes.add(match.group(2))

    # If still no classes found, try a broader search for capitalized words near file paths
    # BUT only when "class" keyword appears nearby (not just any capitalized word)
    if not proposed_classes:
        broad_pattern = re.compile(
            r"[`'\"]([a-z_][a-z0-9_/]*\.py)[`'\"]?\s+.{0,30}\b([A-Z][a-zA-Z0-9]*)\s+class\b",
            re.IGNORECASE | re.DOTALL,
        )
        for match in broad_pattern.finditer(implementation_section):
            class_name = match.group(2)
            # Filter out common words that aren't class names
            if class_name not in ("Python", "The", "This", "That", "List", "Dict", "Any"):
                proposed_classes.add(class_name)

    # Common base class names to skip (too generic)
    generic_classes = {'Config', 'Settings', 'Utils', 'Helper', 'Base', 'Test', 'Manager', 'Handler'}
    proposed_classes = {c for c in proposed_classes if c not in generic_classes}

    # Search for existing implementations of proposed classes
    for class_name in proposed_classes:
        # Search for existing class definitions in the codebase
        existing_matches = []

        try:
            # Search in common project directories
            search_paths = [
                Path.cwd() / "packages",
                Path.cwd() / "src",
                Path.cwd() / "core",
                Path.cwd(),
            ]

            for search_path in search_paths:
                if not search_path.exists():
                    continue

                # Search for Python files containing the class
                for py_file in search_path.rglob("*.py"):
                    try:
                        content = py_file.read_text(encoding="utf-8", errors="ignore")
                        # Check for class definition (matches both `class Name:` and `class Name(Base):`)
                        if re.search(rf'class\s+{re.escape(class_name)}\s*[\(:]', content):
                            rel_path = py_file.relative_to(Path.cwd())
                            existing_matches.append(str(rel_path))
                    except (OSError, PermissionError):
                        continue
        except Exception:
            # If search fails, continue silently to avoid blocking verification
            pass

        if existing_matches:
            findings.append({
                "id": "DUPLICATE-001",
                "category": "implementation_scope",
                "priority": "HIGH",
                "title": f"Plan proposes duplicate of existing {class_name}",
                "description": (
                    f"Plan proposes creating {class_name} but it already exists in: "
                    f"{', '.join(existing_matches[:3])}. "
                    f"Consider extending existing implementation instead of creating duplicate."
                ),
                "evidence": existing_matches[0] if existing_matches else None,
            })

    return findings


def check_assumption_schema_contradictions(plan: str) -> list[dict[str, Any]]:
    """Fail when assumptions/defaults contradict the plan's stated schema or data shape."""
    findings: list[dict[str, Any]] = []
    assumptions = extract_section_content(plan, "Assumptions/Defaults").lower()
    if not assumptions:
        return findings
    design_blob = "\n".join(
        [
            extract_section_content(plan, "Design Decisions and Invariants"),
            extract_section_content(plan, "Implementation Changes"),
            extract_section_content(plan, "State Model Contracts"),
        ]
    ).lower()
    if not design_blob:
        return findings

    candidate_fields = set(_extract_hook_visible_fields(plan))
    candidate_fields.update(field for field, _ in _extract_added_state_fields(plan))
    if not candidate_fields:
        candidate_fields.add("hypotheses")

    for field in candidate_fields:
        assumption_lines = [
            line for line in assumptions.splitlines() if field in line and "plain text" in line
        ]
        if not assumption_lines:
            continue
        design_lines = [line for line in design_blob.splitlines() if field in line]
        if any(any(pattern in line for pattern in STRUCTURED_SCHEMA_PATTERNS) for line in design_lines):
            findings.append(
                {
                    "id": "ASSUMPTION-001",
                    "category": "schema_consistency",
                    "priority": "HIGH",
                    "title": "Assumptions/defaults contradict the declared schema shape",
                    "description": (
                        f"The assumptions section describes `{field}` as plain text, but the design or "
                        "implementation sections define it as structured data. Align the assumption with the schema."
                    ),
                }
            )
            break
    return findings


def check_open_question_blockers(plan: str) -> list[dict[str, Any]]:
    """Fail plans whose Open Questions still contain explicit blocker markers."""
    findings = []
    open_questions = extract_section_content(plan, "Open Questions")
    if not open_questions:
        return findings

    blocker_lines = []
    for line in open_questions.splitlines():
        lowered = line.lower()
        if "blocker" in lowered or "**blocker" in lowered:
            blocker_lines.append(line.strip())

    if blocker_lines:
        findings.append(
            {
                "id": "OPEN-QUESTION-002",
                "category": "open_questions",
                "priority": "HIGH",
                "title": "Open Questions contains explicit blocker items",
                "description": (
                    "Open Questions still contains blocker-marked items. Resolve, reclassify, "
                    "or defer them through recognized workflow state before claiming readiness."
                ),
                "examples": blocker_lines[:3],
            }
        )

    return findings


def check_contract_boundary_matrix(plan: str) -> list[dict[str, Any]]:
    """Validate matrix shape and per-row requirements for contract-sensitive plans."""
    findings = []
    frontmatter = parse_frontmatter(plan)
    if not _is_contract_sensitive(plan, frontmatter):
        return findings

    headers, rows = find_contract_boundary_rows(plan)
    if not headers:
        findings.append(
            {
                "id": "CONTRACT-MATRIX-001",
                "category": "schema_consistency",
                "priority": "HIGH",
                "title": "Missing contract boundary matrix table",
                "description": (
                    "Contract-sensitive plans must include a markdown Contract Boundary Matrix "
                    "with the required per-row contract fields."
                ),
            }
        )
        return findings

    # Case-insensitive comparison: headers are normalized by extract_markdown_table but
    # REQUIRED_PLAN_MATRIX_FIELDS uses original casing, so compare with .lower()
    header_lower = {h.lower(): h for h in headers}
    missing_columns = [field for field in REQUIRED_PLAN_MATRIX_FIELDS if field.lower() not in header_lower]
    if missing_columns:
        findings.append(
            {
                "id": "CONTRACT-MATRIX-002",
                "category": "schema_consistency",
                "priority": "HIGH",
                "title": "Contract boundary matrix is missing required columns",
                "description": "Missing required columns: " + ", ".join(missing_columns),
            }
        )
        return findings

    claimed_status = frontmatter.get("status", "draft")
    # Case-insensitive row key lookup since markdown table headers may have mixed casing
    # (e.g., "Contract Authority Packet" vs "Contract authority packet")
    def _ri(row: dict, key: str) -> str:
        lower_key = key.lower()
        for k, v in row.items():
            if k.lower() == lower_key:
                return v.strip()
        return ""

    for row in rows:
        boundary = _ri(row, "Boundary") or "UNKNOWN"
        packet_ref = _ri(row, "Contract authority packet")
        test_binding = _ri(row, "Test Binding")
        packet_alignment = _ri(row, "Packet Alignment")

        if not packet_ref:
            findings.append(
                {
                    "id": f"CONTRACT-MATRIX-{boundary}-PACKET",
                    "category": "schema_consistency",
                    "priority": "HIGH",
                    "title": f"Boundary row '{boundary}' is missing a per-row Contract authority packet reference",
                    "description": (
                        "Each boundary row must name the packet id/version/path or boundary_id "
                        "it derives from."
                    ),
                }
            )

        if not test_binding:
            findings.append(
                {
                    "id": f"CONTRACT-MATRIX-{boundary}-TEST",
                    "category": "contract_test_coherence",
                    "priority": "HIGH",
                    "title": f"Boundary row '{boundary}' is missing Test binding",
                    "description": "Each boundary row must name the test/trace that proves the contract.",
                }
            )
        elif claimed_status == "implementation-ready" and test_binding.lower() in PLACEHOLDER_BINDINGS:
            findings.append(
                {
                    "id": f"CONTRACT-MATRIX-{boundary}-TEST-PLACEHOLDER",
                    "category": "contract_test_coherence",
                    "priority": "HIGH",
                    "title": f"Boundary row '{boundary}' uses placeholder Test binding",
                    "description": (
                        "Implementation-ready plans cannot keep placeholder test bindings. "
                        "Name the proving test or keep the plan in-review."
                    ),
                }
            )

        if packet_alignment.lower().startswith("exact match") and not packet_ref:
            findings.append(
                {
                    "id": f"CONTRACT-MATRIX-{boundary}-ALIGNMENT",
                    "category": "schema_consistency",
                    "priority": "HIGH",
                    "title": f"Boundary row '{boundary}' claims exact packet alignment without a row-level packet reference",
                    "description": "Exact alignment claims must name the referenced packet boundary explicitly.",
                }
            )

    return findings


def _is_code_identifier_like(path: str) -> bool:
    """Return True if path looks like a code identifier rather than a real file path.

    This filters out false positives from INLINE_FILE_LINE_RE matching partial words
    inside code (e.g., self.c from self.config, l1.c from l1_results).
    Also filters bare filenames like orchestrator.py, SKILL.md that are actually
    references to the full path shown elsewhere in the plan.
    """
    if not path:
        return True
    # Strip Windows drive prefix
    if len(path) > 2 and path[1] == ":":
        path = path[2:]
    # No path separators → likely a bare identifier
    if "/" not in path and "\\" not in path:
        base = path.rsplit(".", 1)[0] if "." in path else path
        ext = path.rsplit(".", 1)[1].lower() if "." in path else ""
        # Single character base is almost certainly a code fragment
        if len(base) <= 2:
            return True
        # Bare filename (no path, common English name) → code ref not real path
        # Covers orchestrator.py, SKILL.md, results.json, config.yaml, etc.
        if base.islower() and ext in ("py", "md", "json", "ts", "js", "yaml", "yml", "toml", "go", "rs"):
            if base in (
                "orchestrator", "skill", "results", "config", "main", "test",
                "data", "self", "class", "def", "init", "batch_status",
                "cache", "inspect", "check_status", "transcript",
            ):
                return True
        # Also check uppercase/common variants case-insensitively
        if ext in ("py", "md", "json", "ts", "js", "yaml", "yml", "toml", "go", "rs"):
            if base.lower() in (
                "orchestrator", "skill", "results", "config", "main", "test",
                "data", "self", "class", "def", "init", "batch_status",
                "cache", "inspect", "check_status", "transcript",
            ):
                return True
        # Single-letter code extension paired with short base → code fragment
        # e.g. self.c, cls.h, x.cpp, obj.cs — not real paths
        if len(ext) == 1 and ext.isalpha() and ext in ("c", "h", "cpp", "cs", "go", "rs", "java"):
            if len(base) <= 8 and base.islower() and base.isalpha():
                return True
        # Single lowercase word that looks like a variable/identifier
        if base.islower() and "_" not in base and base.isidentifier():
            return True
    return False


def check_evidence_file_targets(plan: str, plan_path: str | None = None) -> list[dict[str, Any]]:
    """Fail when explicit file/line evidence points at nonexistent files or stale line spans."""
    findings: list[dict[str, Any]] = []
    current_state = extract_section_content(plan, "Current State with Evidence")
    design = extract_section_content(plan, "Design Decisions and Invariants")
    implementation = extract_section_content(plan, "Implementation Changes")

    sections_to_scan = [
        ("Current State with Evidence", current_state, True),
        ("Design Decisions and Invariants", design, True),
        ("Implementation Changes", implementation, False),
    ]

    seen_refs: set[tuple[str, str, int | None, int | None]] = set()
    for section_name, section_text, allow_explicit_file_only in sections_to_scan:
        if not section_text:
            continue

        for match in EXPLICIT_FILE_LINE_RE.finditer(section_text):
            raw_path = match.group("path").strip()
            line_match = EXPLICIT_LINES_RE.search(section_text[match.end():])
            start = int(line_match.group("start")) if line_match else None
            end = int(line_match.group("end") or line_match.group("start")) if line_match else None
            seen_refs.add((section_name, raw_path, start, end))

        for match in INLINE_FILE_LINE_RE.finditer(section_text):
            raw_path = match.group("path").strip()
            if _is_code_identifier_like(raw_path):
                continue
            start = int(match.group("start")) if match.group("start") else None
            end = int(match.group("end") or match.group("start")) if match.group("start") else None
            if allow_explicit_file_only or start is not None:
                seen_refs.add((section_name, raw_path, start, end))

    for section_name, raw_path, start, end in sorted(
        seen_refs, key=lambda item: (item[0], item[1], item[2] or -1, item[3] or -1)
    ):
        candidates = _resolve_file_reference(raw_path, plan_path)
        if not candidates:
            continue
        existing = next((candidate for candidate in candidates if candidate.exists()), None)
        if existing is None:
            # Try skill path resolution as fallback for cross-drive issues
            existing = _resolve_evidence_path(raw_path, plan_path)
            if existing is None:
                # Check if this is a future-state citation (plan explicitly says file
                # will be created / does not exist yet / is output, not current evidence).
                # If so, downgrade from HIGH to ADVISORY — it is not a true blocker.
                priority = "HIGH"
                if section_name == "Current State with Evidence":
                    normalized_lower = raw_path.lower()
                    # Scan the Current State section for future-state language near this file.
                    # Strip path separators for keyword matching.
                    path_variants = {normalized_lower, normalized_lower.replace("/", " ").replace("\\", " ")}
                    for kw in (
                        "does not exist",
                        "will contain",
                        "will be created",
                        "future output",
                        "append-only",
                        "not yet",
                        "will be created by",
                    ):
                        if kw in current_state.lower():
                            priority = "ADVISORY"
                            break
                    # Also check if the file appears as a known future file in the plan text.
                    # e.g. "synthesis/synthesis_core.py (TASK-13)" means TASK-13 creates it.
                    impl_lower = implementation.lower() if implementation else ""
                    file_basename = Path(normalized_lower).name.lower().replace(".py", "")
                    if file_basename in impl_lower or raw_path.lower() in impl_lower:
                        priority = "ADVISORY"

                findings.append(
                    {
                        "id": "EVIDENCE-001",
                        "category": "evidence_reference",
                        "priority": priority,
                        "title": (
                            "Plan cites a file that does not exist in the current workspace"
                            if priority == "HIGH"
                            else "Future file noted — will be created by a task in this plan"
                        ),
                        "description": (
                            "Explicit file evidence must resolve against the current workspace before the "
                            f"plan can rely on it. Missing target: {raw_path}"
                            if priority == "HIGH"
                            else f"File '{raw_path}' is noted as future/created-by-task in this plan. "
                            "No current workspace file required — ADVISORY only."
                        ),
                        "section": section_name,
                    }
                )
                continue

        if start is None:
            continue

        total_lines = _file_line_count(existing)
        if total_lines <= 0 or start > total_lines or (end is not None and end > total_lines) or (
            end is not None and end < start
        ):
            findings.append(
                {
                    "id": "EVIDENCE-002",
                    "category": "evidence_reference",
                    "priority": "HIGH",
                    "title": "Plan cites stale or invalid line references",
                    "description": (
                        f"Referenced lines {start}-{end or start} do not exist in {existing}. "
                        f"Current line count: {total_lines}."
                    ),
                }
            )

    return findings


def check_layer_execution_semantics(plan: str) -> list[dict[str, Any]]:
    """Fail when layered mechanisms omit whether a layer is blocking, advisory, optional, or fallback."""
    findings: list[dict[str, Any]] = []
    for paragraph in _paragraphs_with_layer_signals(plan):
        if not LAYER_REFERENCE_RE.search(paragraph):
            continue
        lowered = paragraph.lower()
        if any(keyword in lowered for keyword in EXECUTION_SEMANTIC_KEYWORDS):
            continue
        findings.append(
            {
                "id": "EXECUTION-001",
                "category": "execution_policy",
                "priority": "HIGH",
                "title": "Layered mechanism lacks explicit execution semantics",
                "description": (
                    "Layered plans must say whether each layer is blocking, advisory, optional, "
                    "fallback-only, or always-on. Do not leave layer behavior implicit."
                ),
                "evidence": paragraph[:220],
            }
        )
        break
    return findings


def check_conditional_trigger_clarity(plan: str) -> list[dict[str, Any]]:
    """Fail vague conditional execution phrases that do not define a trigger signal."""
    findings: list[dict[str, Any]] = []
    paragraphs = _paragraphs_with_layer_signals(plan)
    for idx, paragraph in enumerate(paragraphs):
        lowered = paragraph.lower()
        if not any(re.search(pattern, lowered, re.IGNORECASE) for pattern in VAGUE_CONDITIONAL_PATTERNS):
            continue
        window = paragraph
        if idx + 1 < len(paragraphs):
            window += "\n" + paragraphs[idx + 1]
        lowered_window = window.lower()
        if any(keyword in lowered_window for keyword in TRIGGER_SIGNAL_KEYWORDS):
            continue
        findings.append(
            {
                "id": "EXECUTION-002",
                "category": "conditional_trigger",
                "priority": "HIGH",
                "title": "Conditional execution is vague and lacks a defined trigger",
                "description": (
                    "Phrases like 'only if needed' or 'if 1+2 are insufficient' must define the "
                    "signal, evaluator, and threshold that trigger the conditional layer."
                ),
                "evidence": paragraph[:220],
            }
        )
        break
    return findings


def check_planning_contract_authority_drift(plan: str) -> list[dict[str, Any]]:
    """Catch stale plan-artifact semantics copied from older CAP/ADR revisions."""
    findings = []
    if not _is_contract_sensitive(plan):
        return findings

    headers, rows = find_contract_boundary_rows(plan)
    if not headers or "Boundary" not in headers or "Failure behavior" not in headers:
        return findings

    for row in rows:
        if row.get("Boundary", "").strip() != "plan-artifact":
            continue

        failure_behavior = row.get("Failure behavior", "")
        packet_alignment = row.get("Packet alignment", "")
        if "/planning" not in failure_behavior.lower() or "blocking" not in failure_behavior.lower():
            findings.append(
                {
                    "id": "AUTHORITY-DRIFT-001",
                    "category": "authority_drift",
                    "priority": "HIGH",
                    "title": "plan-artifact boundary semantics drift from the active /planning contract",
                    "description": (
                        "The plan-artifact row must reflect the active planning contract, which "
                        "treats packet consumption and contradictions as blocking before "
                        "implementation-ready."
                    ),
                    "expected_failure_behavior": ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR,
                    "actual_failure_behavior": failure_behavior,
                    "packet_alignment": packet_alignment,
                }
            )
        break

    return findings


def check_mechanism_triggerability(plan: str) -> list[dict[str, Any]]:
    """Fail when a stateful mechanism cannot trigger under the plan's stated invariants."""
    findings = []
    if not is_stateful_plan(plan):
        return findings

    design = extract_section_content(plan, "Design Decisions and Invariants").lower()
    tests = extract_section_content(plan, "Test Matrix").lower()
    if not design:
        return findings

    stale_check_uses_occurred_vs_cached = "occurred_at > cached_at" in design
    cached_at_equals_occurred_at = bool(
        re.search(
            r"cached_at.{0,40}set to.{0,40}occurred_at.{0,40}ingest time",
            design,
            re.IGNORECASE | re.DOTALL,
        )
    )
    archive_marked_immutable = (
        "append-only and immutable once written" in design
        or "archive files are append-only and immutable once written" in design
    )
    stale_check_uses_archive_mtime = "raw_payload_path" in design and "mtime" in design
    test_mutates_source_file = "mutate source file" in tests

    if (
        stale_check_uses_occurred_vs_cached
        and cached_at_equals_occurred_at
        and archive_marked_immutable
        and stale_check_uses_archive_mtime
    ):
        findings.append(
            {
                "id": "STATE-006",
                "category": "mechanism_triggerability",
                "priority": "HIGH",
                "title": "Freshness / invalidation trigger cannot fire under stated invariants",
                "description": (
                    "The plan sets cached_at = occurred_at at ingest time and also treats archive "
                    "files as immutable, so neither documented stale trigger is reachable."
                    + (
                        " The test matrix mutates the source file rather than the watched archive "
                        "artifact."
                        if test_mutates_source_file
                        else ""
                    )
                ),
            }
        )

    return findings


def check_solo_dev_violations(plan: str) -> list[dict[str, Any]]:
    """Check for team coordination patterns that violate solo-dev constraints."""
    findings = []
    negation_pattern = r"(?:no|without|avoid|not|lacking|minus|excluding)\s+"

    for pattern in SOLO_DEV_VIOLATIONS:
        matches = re.findall(pattern, plan, re.IGNORECASE)
        for match in matches:
            match_pos = plan.lower().find(match.lower())
            if match_pos > 0:
                context_before = plan[max(0, match_pos - 20) : match_pos].lower()
                if re.search(negation_pattern, context_before):
                    continue
            findings.append(
                {
                    "id": f"SOLO-{len(findings) + 1:03d}",
                    "category": "solo_dev_constraint",
                    "priority": "HIGH",
                    "title": f"Solo-dev violation: {match}",
                    "description": f"Pattern '{match}' indicates team coordination, not allowed in solo-dev",
                }
            )
    return findings


def check_rtm_coverage(
    requirements: list[dict[str, str]], tasks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Check RTM coverage."""
    findings = []

    if not tasks:
        findings.append(
            {
                "id": "RTM-005",
                "category": "traceability",
                "priority": "HIGH",
                "title": "No tasks detected",
                "description": "Implementation Plan contains no tasks.",
            }
        )
        return findings

    if not requirements:
        findings.append(
            {
                "id": "RTM-000",
                "category": "traceability",
                "priority": "MEDIUM",
                "title": "No requirements detected",
                "description": "Could not detect requirements in Goal section",
            }
        )

    # Skip tasks explicitly marked as DELETED from acceptance criteria checking
    tasks_without_acceptance = [
        t for t in tasks
        if not t["has_acceptance_criteria"] and "DELETED" not in t["title"].upper()
    ]
    if tasks_without_acceptance:
        findings.append(
            {
                "id": "RTM-003",
                "category": "traceability",
                "priority": "HIGH",
                "title": f"Missing acceptance criteria: {len(tasks_without_acceptance)} task(s)",
                "description": "Tasks without acceptance criteria:\n"
                + "\n".join(f"  - {t['id']}: {t['title'][:100]}" for t in tasks_without_acceptance),
            }
        )

    if requirements:
        orphan_requirements = []
        for req in requirements:
            req_keywords = _keyword_set(req["text"])
            mapped = False
            for task in tasks:
                task_keywords = _keyword_set(task["title"])
                if req_keywords & task_keywords:
                    mapped = True
                    break
            if not mapped:
                orphan_requirements.append(req)

        if orphan_requirements:
            findings.append(
                {
                    "id": "RTM-001",
                    "category": "traceability",
                    "priority": "HIGH",
                    "title": f"Orphan requirements: {len(orphan_requirements)} not mapped to tasks",
                    "description": "Requirements without corresponding tasks:\n"
                    + "\n".join(f"  - {r['id']}: {r['text'][:100]}" for r in orphan_requirements),
                }
            )

    return findings


def check_status_readiness(plan: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """FAIL if plan claims implementation-ready but has unresolved blocker/high findings."""
    result_findings = []
    frontmatter = parse_frontmatter(plan)

    claimed_status = frontmatter.get("status", "draft")
    unresolved_blockers = int(frontmatter.get("unresolved_blockers", "0") or "0")

    if claimed_status == "implementation-ready":
        high_priority = [f for f in findings if f.get("priority") == "HIGH"]
        if high_priority:
            result_findings.append(
                {
                    "id": "CONTRADICTION-001",
                    "category": "contradiction",
                    "priority": "HIGH",
                    "title": "Contradiction: plan claims implementation-ready but has unresolved HIGH findings",
                    "description": f"Status is 'implementation-ready' but {len(high_priority)} HIGH priority issue(s) remain. "
                    f"Fix all HIGH findings or defer them with rationale before marking implementation-ready.",
                    "blocking_findings": [f["id"] for f in high_priority],
                }
            )

        if unresolved_blockers != 0:
            result_findings.append(
                {
                    "id": "CONTRADICTION-002",
                    "category": "contradiction",
                    "priority": "HIGH",
                    "title": "Contradiction: implementation-ready plan reports unresolved blockers",
                    "description": (
                        "Frontmatter unresolved_blockers must be 0 before a plan can be marked "
                        "implementation-ready."
                    ),
                }
            )

        phase_preconditions = [
            (key, _parse_int_frontmatter(frontmatter, key) or 0)
            for key in frontmatter
            if re.fullmatch(r"phase\d+_preconditions", key)
        ]
        active_phase_preconditions = [item for item in phase_preconditions if item[1] > 0]
        if active_phase_preconditions and "phase_ready_through" not in frontmatter:
            formatted = ", ".join(f"{key}={value}" for key, value in active_phase_preconditions)
            result_findings.append(
                {
                    "id": "CONTRADICTION-003",
                    "category": "contradiction",
                    "priority": "HIGH",
                    "title": "implementation-ready plan uses unrecognized phase-precondition metadata",
                    "description": (
                        "Phase-specific preconditions are present ("
                        + formatted
                        + "), but no recognized readiness vocabulary such as phase_ready_through "
                          "was declared."
                    ),
                }
            )

    return result_findings


def load_review_findings(findings_path: Path) -> list[dict[str, Any]]:
    """Load blocker/high findings from flexible review-findings JSON structures."""
    if not findings_path.exists():
        return []

    try:
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    def flatten(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            collected = []
            for item in value:
                collected.extend(flatten(item))
            return collected
        if isinstance(value, dict):
            if "id" in value and ("severity" in value or "priority" in value):
                return [value]
            collected = []
            for nested in value.values():
                collected.extend(flatten(nested))
            return collected
        return []

    return flatten(payload)


def parse_dispositions(summary_path: Path) -> dict[str, str]:
    """Parse finding dispositions from a markdown summary table.

    Handles 5-column format (| Finding | Source | Severity | Disposition | Rationale |)
    used in review summaries, where Disposition may be bold (e.g., **ACCEPTED**).
    Also handles 4-column format (| ID | SEVERITY | disposition | rationale |)
    and 2-column format (| ID | disposition |).
    """
    if not summary_path.exists():
        return {}

    dispositions = {}
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| Finding") or line.startswith("|--------"):
            continue

        parts = [p.strip() for p in line.split("|")]
        # parts[0] is empty (leading |), parts[1] = Finding, parts[2] = Source,
        # parts[3] = Severity, parts[4] = Disposition, parts[5] = Rationale
        if len(parts) >= 5:
            finding_field = parts[1]
            disposition_field = parts[4] if len(parts) >= 5 else ""
            # Extract ID from finding field (e.g., "VIOLATION-1: MCP call in Stop hook" -> "VIOLATION-1")
            # IDs may contain hyphens (e.g., "CRITIC-ADVISORY-GHOST", "R1-COUNTER-STATE", "SEC-CKS-LEAK")
            id_match = re.match(r"^([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)", finding_field)
            if not id_match:
                continue
            finding_id = id_match.group(1)
            # Strip bold markdown from disposition (e.g., "**ACCEPTED**" -> "ACCEPTED")
            disp_clean = re.sub(
                r"^\*\*(.+)\*\*$", r"\1", disposition_field, flags=re.IGNORECASE
            ).lower()
            if disp_clean in ("accepted", "rejected", "deferred"):
                dispositions[finding_id] = disp_clean
                continue

        # Fallback: 4-column or 2-column regex patterns
        # 4-column: | ID | SEVERITY | disposition | rationale |
        match = re.match(
            r"^\|\s*([A-Za-z0-9_-]+)\s*\|\s*(?:BLOCKER|HIGH|MEDIUM|LOW|CRITICAL)\s*\|\s*(accepted|rejected|deferred)\s*\|",
            line,
            re.IGNORECASE,
        )
        if match:
            dispositions[match.group(1)] = match.group(2).lower()
            continue
        # 2-column: | ID | disposition |
        match = re.match(
            r"^\|\s*([A-Za-z0-9_-]+)\s*\|\s*(accepted|rejected|deferred)\s*\|",
            line,
            re.IGNORECASE,
        )
        if match:
            dispositions[match.group(1)] = match.group(2).lower()
    return dispositions


def check_dispositions(plan_path: str | None, plan: str) -> list[dict[str, Any]]:
    """Require review artifacts and blocker/high dispositions before implementation-ready."""
    findings = []
    frontmatter = parse_frontmatter(plan)
    claimed_status = frontmatter.get("status", "draft")
    if claimed_status != "implementation-ready":
        return findings

    if not plan_path:
        findings.append(
            {
                "id": "DISPOSITION-001",
                "category": "disposition",
                "priority": "HIGH",
                "title": "Cannot verify implementation-ready status without plan path",
                "description": (
                    "Implementation-ready verification requires a plan path so sidecar review "
                    "artifacts can be inspected."
                ),
            }
        )
        return findings

    findings_path = Path(plan_path).with_suffix(".review.findings.json")
    summary_path = Path(plan_path).with_suffix(".review.summary.md")

    if not findings_path.exists():
        findings.append(
            {
                "id": "DISPOSITION-002",
                "category": "disposition",
                "priority": "HIGH",
                "title": "Missing review findings artifact",
                "description": (
                    "Implementation-ready plans must have a sibling .review.findings.json artifact."
                ),
            }
        )
        return findings

    if not summary_path.exists():
        findings.append(
            {
                "id": "DISPOSITION-003",
                "category": "disposition",
                "priority": "HIGH",
                "title": "Missing review summary artifact",
                "description": (
                    "Implementation-ready plans must have a sibling .review.summary.md artifact "
                    "with finding dispositions."
                ),
            }
        )
        return findings

    review_findings = load_review_findings(findings_path)
    blocking_ids = []
    for finding in review_findings:
        severity = str(finding.get("severity") or finding.get("priority") or "").upper()
        if severity in {"BLOCKER", "HIGH", "CRITICAL"}:
            finding_id = finding.get("id")
            if finding_id:
                blocking_ids.append(str(finding_id))

    # Use JSON as authoritative disposition source (structured, machine-readable).
    # The summary table may use human-readable titles instead of IDs.
    dispositions = {}
    for f in review_findings:
        disp = f.get("disposition", "").lower().strip()
        if disp in ("accepted", "rejected", "deferred"):
            dispositions[f["id"]] = disp

    missing = [finding_id for finding_id in blocking_ids if finding_id not in dispositions]
    if missing:
        findings.append(
            {
                "id": "DISPOSITION-004",
                "category": "disposition",
                "priority": "HIGH",
                "title": "Missing blocker/high finding dispositions",
                "description": (
                    "Every blocker/high finding must be dispositioned in .review.summary.md. "
                    f"Missing: {', '.join(sorted(missing))}"
                ),
            }
        )

    return findings


def _detect_stale_review_summary(summary_text: str, result: dict[str, Any]) -> str | None:
    lowered = summary_text.lower()
    status = result.get("status")
    claimed_status = result.get("claimed_status")
    high_priority = result.get("summary", {}).get("high_priority", 0)

    if status == "READY" and (
        "blocked by auto_verify" in lowered
        or "auto_verify returns `blocked`" in lowered
        or "auto_verify returns blocked" in lowered
        or "false positives" in lowered
    ):
        return "Summary claims the plan is blocked or false-positive limited, but current verification is READY."

    if status == "BLOCKED" and (
        "ready for implementation" in lowered or "this plan is ready for implementation" in lowered
    ):
        return "Summary claims the plan is ready for implementation, but current verification is BLOCKED."

    if claimed_status != "implementation-ready" and "ready for implementation" in lowered:
        return (
            "Summary claims implementation readiness, but the current frontmatter status is not "
            "implementation-ready."
        )

    if high_priority > 0 and "0 findings" in lowered:
        return "Summary claims zero findings, but current verification reports HIGH findings."

    return None


def _candidate_review_summary_paths(plan_path: str) -> list[Path]:
    plan = Path(plan_path)
    candidates = [plan.with_suffix(".review.summary.md")]

    plans_roots = [plan.parent, Path.home() / ".claude" / "plans", Path("P:\\\\\\.claude/plans")]
    for plans_dir in plans_roots:
        adversarial_dir = plans_dir / "adversarial"
        if adversarial_dir.exists():
            candidates.extend(adversarial_dir.glob(f"{plan.stem}.review.summary.md"))
            nested_dir = adversarial_dir / plan.stem
            if nested_dir.exists():
                candidates.extend(nested_dir.glob("**/*.review.summary.md"))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def annotate_stale_review_artifacts(plan_path: str | None, result: dict[str, Any]) -> dict[str, Any]:
    """Mark contradictory review summaries as stale so they stop acting authoritative."""
    if not plan_path:
        return {"stale_review_summary": False, "reason": None, "paths": []}

    stale_paths: list[str] = []
    reasons: list[str] = []
    unreadable: list[str] = []

    for summary_path in _candidate_review_summary_paths(plan_path):
        if not summary_path.exists():
            continue

        try:
            summary_text = summary_path.read_text(encoding="utf-8")
        except OSError:
            unreadable.append(str(summary_path))
            continue

        reason = _detect_stale_review_summary(summary_text, result)
        if not reason:
            continue

        stale_prefix = "> STALE REVIEW ARTIFACT:"
        if stale_prefix not in summary_text:
            verified_at = int(result.get("artifact_freshness", {}).get("verified_at", time.time()))
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(verified_at))
            banner = (
                f"{stale_prefix} auto_verify at {timestamp} returned "
                f"{result.get('status')} ({result.get('summary', {}).get('high_priority', 0)} HIGH findings). "
                f"{reason} Regenerate adversarial review artifacts before treating this summary as authoritative.\n\n"
            )
            try:
                summary_path.write_text(banner + summary_text, encoding="utf-8")
            except OSError:
                unreadable.append(str(summary_path))
                continue

        stale_paths.append(str(summary_path))
        reasons.append(reason)

    return {
        "stale_review_summary": bool(stale_paths),
        "reason": reasons[0] if reasons else ("unreadable" if unreadable else None),
        "paths": stale_paths,
        "unreadable_paths": unreadable,
    }


def validate_adversarial_agents() -> dict[str, Any]:
    """Validate that all required adversarial agents are available."""
    missing = []
    available = []
    # Also check the .claude/agents relative to this module's location
    # (handles cases where cwd differs from project root, e.g. test environments)
    # Walk upward; when we find a directory named "skills", the sibling ../agents
    # is the agents directory (since .claude/skills is the project layout)
    module_dir = Path(__file__).resolve().parent
    claude_agents = None
    for _ in range(6):
        module_dir = module_dir.parent
        if module_dir.name == "skills" and (module_dir.parent / "agents").exists():
            claude_agents = module_dir.parent / "agents"
            break
    # Build list with all candidates
    agents_dirs = [
        Path.cwd() / ".claude" / "agents",
        Path.home() / ".claude" / "agents",
    ]
    # Also check $CLAUDE_ROOT/agents explicitly (P: drive is not home directory on Windows)
    p_drive_claude = Path("P:\\\\\\") / ".claude" / "agents"
    if p_drive_claude.exists():
        agents_dirs.append(p_drive_claude)
    if claude_agents:
        agents_dirs.append(claude_agents)

    for agent_name in REQUIRED_ADVERSARIAL_AGENTS:
        agent_file = f"{agent_name}.md"
        found = any((agents_dir / agent_file).exists() for agents_dir in agents_dirs)
        if found:
            available.append(agent_name)
        else:
            missing.append(agent_name)

    return {"valid": len(missing) == 0, "missing": missing, "available": available}


def classify_next_action(status: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose the next workflow action from verifier results."""
    if status == "READY":
        return {
            "type": "launch_adversarial_review",
            "reason": "Plan passed verification",
            "must_follow": True,
            "authoritative_source": "latest_auto_verify",
        }

    ingestion_findings = [
        finding
        for finding in findings
        if finding.get("category") in {"adr_ingestion", "source_ingestion"}
    ]
    if ingestion_findings:
        return {
            "type": "fix_issues",
            "reason": (
                f"Canonicalize {len(ingestion_findings)} source-ingestion issue(s) "
                "before routing any remaining blockers"
            ),
            "must_follow": True,
            "authoritative_source": "latest_auto_verify",
        }

    arch_findings = [
        finding
        for finding in findings
        if finding.get("category") in ARCH_REMEDIATION_CATEGORIES
        or finding.get("id") in ARCH_REMEDIATION_IDS
    ]
    if arch_findings:
        blocking_categories = sorted({str(finding.get("category")) for finding in arch_findings})
        return {
            "type": "invoke_arch_then_rewrite_plan",
            "reason": (
                f"Resolve {len(arch_findings)} architecture blocker(s) via /arch, "
                "then rewrite the plan and re-run verification"
            ),
            "must_follow": True,
            "authoritative_source": "latest_auto_verify",
            "recommended_skill": "/arch",
            "nested_subworkflow": True,
            "resume_skill": "/planning",
            "resume_policy": "automatic_return_to_caller",
            "user_reentry_required": False,
            "arch_blocker_ids": [str(finding.get("id")) for finding in arch_findings],
            "blocking_categories": blocking_categories,
            "ownership": "planning_rewrites_plan",
            "post_arch_actions": [
                "consume_arch_packet",
                "rewrite_plan",
                "rerun_auto_verify",
            ],
        }

    high_priority = [finding for finding in findings if finding.get("priority") == "HIGH"]
    return {
        "type": "fix_issues",
        "reason": f"Fix {len(high_priority)} HIGH priority issue(s)",
        "must_follow": True,
        "authoritative_source": "latest_auto_verify",
    }


def _current_arch_finding_ids(findings: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(finding.get("id"))
            for finding in findings
            if finding.get("category") in ARCH_REMEDIATION_CATEGORIES
            or finding.get("id") in ARCH_REMEDIATION_IDS
        }
    )


VALIDATION_MODES = {"light", "readiness", "contract"}


def _mode_checks_light() -> list:
    """Checks that run in light mode."""
    return [
        check_status_header,
        check_placeholders,
        check_plan_purity,
        check_section_completeness,
    ]


def _mode_checks_readiness() -> list:
    """Checks that run in readiness mode (light + full verification)."""
    return _mode_checks_light() + [
        check_adr_ingestion_contract,
        check_source_ingestion_contract,
        check_evidence_file_targets,
        check_layer_execution_semantics,
        check_conditional_trigger_clarity,
        check_change_component_alignment,
        check_helper_reference_clarity,
        check_duplicate_implementations,
        check_stateless_contradictions,
        check_ambiguous_contracts,
        check_state_model_completeness,
        check_unresolved_core_decisions,
        check_open_question_blockers,
        check_boundary_overload,
        check_existing_flow_overlap,
        check_state_extension_contracts,
        check_parser_failure_policy,
        check_assumption_schema_contradictions,
        check_claim_schema_consistency,
        check_contract_test_coherence,
        check_stateful_failure_mode_tests,
        check_mechanism_triggerability,
        check_contract_sensitivity_contradictions,
        check_contract_boundary_matrix,
        check_planning_contract_authority_drift,
        check_solo_dev_violations,
        check_rtm_coverage,
        check_dispositions,
        validate_adversarial_agents,
        check_status_readiness,
    ]


def _mode_checks_contract() -> list:
    """Checks that run in contract mode (readiness + CAP/boundary checks)."""
    return _mode_checks_readiness() + [
        check_contract_authority_refs,
        check_boundary_matrix_rows,
    ]


def _get_checks_for_mode(mode: str) -> list:
    """Return the list of check functions for the given mode."""
    normalized = mode.lower().strip()
    if normalized == "light":
        return _mode_checks_light()
    if normalized == "contract":
        return _mode_checks_contract()
    return _mode_checks_readiness()  # default: readiness


def check_contract_authority_refs(plan: str) -> list[dict[str, Any]]:
    """Contract mode only: verify CAP references point to existing files."""
    findings = []
    cap_refs = re.findall(r'`([^`]*\.contract-authority-packet\.json)`', plan)
    for ref in cap_refs:
        path = Path(ref)
        if not path.exists():
            findings.append({
                "id": "CAP-001",
                "category": "contract_authority",
                "priority": "HIGH",
                "title": f"Contract Authority Packet not found: {ref}",
                "description": "Referenced CAP file does not exist.",
                "evidence": ref,
            })
    return findings


def check_boundary_matrix_rows(plan: str) -> list[dict[str, Any]]:
    """Contract mode only: verify each matrix row has all required fields."""
    findings = []
    frontmatter = parse_frontmatter(plan)
    if not _is_contract_sensitive(plan, frontmatter):
        return findings

    headers, rows = find_contract_boundary_rows(plan)
    if not headers:
        return findings  # already caught by check_contract_boundary_matrix

    required_cols = {"Boundary", "Contract authority packet", "Producer", "Consumer"}
    for row in rows:
        for col in required_cols:
            if not row.get(col, "").strip():
                findings.append({
                    "id": "MATRIX-ROW-001",
                    "category": "contract_boundary",
                    "priority": "HIGH",
                    "title": f"Boundary row missing required field: {col}",
                    "description": f"Row '{row.get('Boundary', 'UNKNOWN')}' has no value for '{col}'.",
                    "evidence": str(row),
                })
    return findings


def verify_plan(plan_path: str | None = None, plan_content: str | None = None, mode: str = "readiness") -> dict[str, Any]:
    """Verify plan structure with strict readiness gating.

    Args:
        plan_path: Path to plan file
        plan_content: Plan content string (alternative to path)
        mode: Validation mode — "light", "readiness", or "contract".
              Light = structural only (frontmatter, sections, placeholders).
              Readiness = full verification (default).
              Contract = readiness + CAP references + boundary matrix row checks.

    Returns:
        Verification result dict with status, action_items, and next_action.
        next_action.type is one of:
        - launch_adversarial_review
        - invoke_arch_then_rewrite_plan
        - fix_issues
    """
    try:
        if plan_content:
            plan = plan_content
        elif plan_path:
            with open(plan_path, encoding="utf-8") as f:
                plan = f.read()
        else:
            return {
                "status": "BLOCKED",
                "action_items": [
                    {
                        "id": "ERROR-001",
                        "category": "error",
                        "priority": "HIGH",
                        "title": "Invalid arguments",
                        "description": "Either plan_path or plan_content must be provided",
                    }
                ],
                "summary": {"total_findings": 1, "high_priority": 1},
                "next_action": {"type": "fix_issues", "reason": "Invalid arguments"},
            }
    except FileNotFoundError:
        return {
            "status": "BLOCKED",
            "plan_path": plan_path,
            "action_items": [
                {
                    "id": "ERROR-002",
                    "category": "error",
                    "priority": "HIGH",
                    "title": f"Plan file not found: {plan_path}",
                    "description": str(Exception()),
                }
            ],
            "summary": {"total_findings": 1, "high_priority": 1},
            "next_action": {"type": "fix_issues", "reason": f"File not found: {plan_path}"},
        }
    except Exception as e:
        return {
            "status": "BLOCKED",
            "plan_path": plan_path,
            "action_items": [
                {
                    "id": "ERROR-003",
                    "category": "error",
                    "priority": "HIGH",
                    "title": f"Unexpected error: {type(e).__name__}",
                    "description": str(e),
                }
            ],
            "summary": {"total_findings": 1, "high_priority": 1},
            "next_action": {"type": "fix_issues", "reason": f"Error reading plan: {e}"},
        }

    # Run checks for the selected mode
    all_findings = []
    checks = _get_checks_for_mode(mode)
    ingestion_blocked = False
    agent_validation = {"valid": True, "missing": []}

    for check in checks:
        # ADR/source ingestion checks set a flag that short-circuits subsequent checks
        if check in (check_adr_ingestion_contract, check_source_ingestion_contract):
            findings = check(plan, plan_path) if check.__code__.co_argcount >= 2 else check(plan)
            all_findings.extend(findings)
            if findings:
                ingestion_blocked = True
        elif check == validate_adversarial_agents:
            # validate_adversarial_agents takes no plan arg
            result = check()
            if not result["valid"]:
                all_findings.append({
                    "id": "AGENT-001",
                    "category": "agent_availability",
                    "priority": "HIGH",
                    "title": "Missing adversarial agents",
                    "description": f"Cannot launch adversarial review. Missing: {', '.join(result['missing'])}",
                })
        elif check == check_status_readiness:
            # check_status_readiness takes (plan, findings)
            all_findings.extend(check(plan, all_findings))
        elif check == check_rtm_coverage:
            # check_rtm_coverage takes (requirements, tasks)
            requirements = extract_requirements(plan)
            tasks = extract_tasks(plan)
            all_findings.extend(check(requirements, tasks))
        elif check == check_dispositions:
            all_findings.extend(check(plan_path, plan))
        elif ingestion_blocked:
            continue  # skip all stateful checks when ADR/source ingestion blocked
        elif check in (check_contract_boundary_matrix, check_planning_contract_authority_drift,
                       check_contract_sensitivity_contradictions, check_state_model_completeness,
                       check_ambiguous_contracts, check_unresolved_core_decisions,
                       check_open_question_blockers, check_boundary_overload,
                       check_existing_flow_overlap, check_state_extension_contracts,
                       check_parser_failure_policy, check_assumption_schema_contradictions,
                       check_claim_schema_consistency, check_contract_test_coherence,
                       check_stateful_failure_mode_tests, check_mechanism_triggerability,
                       check_evidence_file_targets, check_layer_execution_semantics,
                       check_conditional_trigger_clarity, check_change_component_alignment,
                       check_helper_reference_clarity, check_stateless_contradictions,
                       check_solo_dev_violations):
            # These take (plan) or (plan, plan_path)
            all_findings.extend(check(plan, plan_path) if check.__code__.co_argcount >= 2 else check(plan))
        elif check == check_contract_authority_refs or check == check_boundary_matrix_rows:
            all_findings.extend(check(plan))
        else:
            all_findings.extend(check(plan) if check.__code__.co_argcount == 1 else check(plan, plan_path))

    # Determine overall status
    high_priority = [f for f in all_findings if f.get("priority") == "HIGH"]
    status = "BLOCKED" if high_priority else "READY"

    # Extract claimed status for result
    claimed_status = parse_frontmatter(plan).get("status", "draft")

    frontmatter = parse_frontmatter(plan)
    inferred_phase_ready_through = infer_phase_ready_through(plan, frontmatter)

    plan_sha256 = hashlib.sha256(plan.encode("utf-8")).hexdigest()
    next_action = classify_next_action(status, all_findings)
    active_arch_receipt = None
    current_arch_finding_ids = _current_arch_finding_ids(all_findings)

    if plan_path and not ingestion_blocked:
        if current_arch_finding_ids:
            active_arch_receipt = find_pending_arch_handoff_receipt(
                plan_path,
                arch_blocker_ids=current_arch_finding_ids,
                current_plan_sha256=plan_sha256,
            )
            if active_arch_receipt and next_action.get("type") == "invoke_arch_then_rewrite_plan":
                next_action = {
                    "type": "fix_issues",
                    "reason": (
                        "A pending /arch handoff receipt already exists for these architecture blockers. "
                        "Consume the receipt, rewrite the plan locally, and rerun verification."
                    ),
                    "must_follow": True,
                    "authoritative_source": "arch_handoff_receipt",
                    "ownership": "planning_rewrites_plan",
                    "post_arch_actions": [
                        "consume_arch_packet",
                        "rewrite_plan",
                        "rerun_auto_verify",
                    ],
                }
        else:
            active_arch_receipt = find_pending_arch_handoff_receipt(plan_path)
            if active_arch_receipt:
                active_arch_receipt = mark_arch_handoff_consumed(
                    plan_path,
                    rewritten_plan_sha256=plan_sha256,
                )

    result = {
        "status": status,
        "claimed_status": claimed_status,
        "plan_path": plan_path,
        "plan_sha256": plan_sha256,
        "readiness": {
            "phase_ready_through": inferred_phase_ready_through,
            "unresolved_blockers": _parse_int_frontmatter(frontmatter, "unresolved_blockers"),
        },
        "action_items": all_findings,
        "agent_validation": agent_validation,
        "summary": {
            "total_findings": len(all_findings),
            "high_priority": len(high_priority),
            "requirements_found": len(requirements),
            "tasks_found": len(tasks),
        },
        "next_action": next_action,
        "artifact_freshness": {
            "verified_at": int(time.time()),
            "plan_mtime": int(Path(plan_path).stat().st_mtime) if plan_path else None,
            "instruction": (
                "If the plan file or sibling artifacts change after this timestamp, rerun "
                "auto_verify.py and discard the previous blocker model."
            ),
        },
    }

    if active_arch_receipt:
        result["arch_handoff_receipt"] = {
            "status": active_arch_receipt.get("status"),
            "receipt_path": active_arch_receipt.get("receipt_path"),
            "source_adr": active_arch_receipt.get("source_adr"),
            "arch_blocker_ids": active_arch_receipt.get("arch_blocker_ids", []),
            "resume_policy": active_arch_receipt.get("resume_policy"),
        }

    if plan_path:
        result["artifact_consistency"] = annotate_stale_review_artifacts(plan_path, result)
        result_path = Path(plan_path).with_suffix(".review.result.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    # GTO skill coverage logging (lazy import to avoid blocking when GTO has import errors)
    try:
        import sys as _sys

        _gto_lib = Path("P:\\\\\\.claude/skills")
        if str(_gto_lib) not in _sys.path:
            _sys.path.insert(0, str(_gto_lib))
        from gto.lib.skill_coverage_detector import _append_skill_coverage

        _append_skill_coverage(
            target_key="skills/planning",
            skill="/planning",
            terminal_id="cli",
            git_sha=None,
        )
    except Exception:
        pass

    return result


def cleanup_plan_artifacts(
    plans_dir: str | Path | None = None, retention_seconds: int = 604800
) -> dict[str, Any]:
    """Remove stale review artifacts older than retention period (default: 7 days).

    Concurrent-session safe: uses atomic unlink, skips files that can't be removed.

    Args:
        plans_dir: Root plans directory. Defaults to ~/.claude/plans
        retention_seconds: Age threshold in seconds (default 7 days = 604800s)

    Returns:
        Dict with removed count, errors, and list of removed files
    """
    if plans_dir is None:
        plans_dir = Path.home() / ".claude" / "plans"
    else:
        plans_dir = Path(plans_dir)

    if not plans_dir.exists():
        return {"removed": [], "errors": [], "total_removed": 0}

    cutoff = time.time() - retention_seconds
    removed: list[str] = []
    errors: list[str] = []

    # Pattern matches all review artifact types (findings, summary, result)
    # Also matches per-plan subdirectory artifacts
    for pattern in [
        "**/*.review.findings.json",
        "**/*.review.summary.md",
        "**/*.review.result.json",
    ]:
        for artifact_path in plans_dir.glob(pattern):
            try:
                if artifact_path.stat().st_mtime >= cutoff:
                    continue  # Skip files within retention window
                # Atomic unlink — fails fast if file is held open by another process
                artifact_path.unlink()
                removed.append(str(artifact_path))
            except OSError as e:
                errors.append(f"{artifact_path}: {e}")

    return {"removed": removed, "errors": errors, "total_removed": len(removed)}


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python auto_verify.py <plan_path>")
        sys.exit(1)

    plan_path = sys.argv[1]
    result = verify_plan(plan_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "READY" else 1)


if __name__ == "__main__":
    main()
