#!/usr/bin/env python3
"""
StopHook_rca_contract.py - RCA Contract Structural Gate
=======================================================

Stateless structural gate for RCA turns. Validates 8-field schema
with evidence-links. Only active when rca_turn=True (derived from
skill_state by Stop_router.py).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import TypedDict

_logger = logging.getLogger(__name__)


class BandAidState(TypedDict):
    """Schema for band-aid chain detection state.

    Tracks how many times each file has been fixed to detect the band-aid
    anti-pattern (repeated fixes to the same file suggest wrong root cause).

    Attributes:
        _ts: Monotonic timestamp for TTL expiration
        fixes: Mapping from file path to fix count
    """
    _ts: float
    fixes: dict[str, int]

# Advisory mode: when true, log warnings but don't block
_ADVISORY_MODE = os.environ.get("RCA_CONTRACT_ADVISORY", "false").lower() == "true"

# Single root cause escape hatch pattern
SINGLE_RC_ESCAPE = re.compile(
    r"\[SINGLE\s+ROOT\s+CAUSE\s+CONFIRMED\]",
    re.IGNORECASE,
)

# Urgency detection patterns
URGENCY_PATTERNS = [
    r"\b(urgent|urgency|emergency)\b",
    r"\b(incident|outage|down)\b",
    r"\b(prod(uction)?|live|customer)\s+(issue|problem|outage|down|broken)\b",
    r"\b(time\s*(critical|sensitive)|ASAP|right now|immediately)\b",
]

try:
    from evidence_scope import SCOPE_TURN_STRICT, load_scoped_tool_events
except Exception:
    SCOPE_TURN_STRICT = ""
    load_scoped_tool_events = None

# Import evidence_store functions for binding validation (TASK-006)
try:
    from evidence_store import (
        load_epistemic_bindings,
        load_epistemic_commitments,
    )
except Exception:
    load_epistemic_commitments = None
    load_epistemic_bindings = None

HOOKS_DIR = Path(__file__).resolve().parent
STATE_DIR = HOOKS_DIR / "state"
LOG_DIR = HOOKS_DIR / "state" / "logs"

# --- Logging ---------------------------------------------------------------

LOG_DIR.mkdir(parents=True, exist_ok=True)


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


def _get_logger():
    """Lazy logger initialization to avoid issues at import time."""
    import logging

    logger = logging.getLogger("rca_contract")
    handler = logging.FileHandler(LOG_DIR / "rca_contract.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger


# --- RCA Contract Schema Fields -------------------------------------------

REQUIRED_FIELDS = [
    "Symptom",
    "Evidence",
    "Executed Path",
    "Alternative Hypothesis",
    "Falsifier",
    "Ruled Out",
    "Root Cause",
    "Fix",
    "Verification",
]

# Block reason codes
BLOCK_REASONS = {
    "missing-symptom": "Symptom section missing or only contains hypothesis",
    "missing-evidence": "No current-turn evidence cited in Evidence section",
    "missing-executed-path": "No executed path shown in Executed Path section",
    "unreachable-root-cause": "Root Cause not reachable from Executed Path",
    "dead-code-in-path": "Executed Path references function with 0 callers",
    "unlabeled-transcript-evidence": "Evidence contains unlabeled transcript-time facts",
    "missing-alternative": "Alternative Hypothesis section missing",
    "missing-falsifier": "Falsifier missing or does not refute alternative",
    "missing-fix": "Fix section missing or only describes symptom",
    "missing-verification": "Verification plan absent or non-specific",
    # TASK-006: Semantic binding validation block reasons
    "unbound-evidence": "Evidence claims not bound to tool events",
    "stale-evidence": "Evidence not from current turn",
    "cross-terminal-evidence": "Evidence from different terminal session",
    "stale-binding": "Binding marked stale due to mutations",
    "evidence-without-tool-events": "Evidence without corresponding tool execution",
    # TASK-004: Structure validation block reasons
    "missing-artifact": "Artifact path cited in Evidence does not exist on disk",
    # TASK-001: Zero-tool-call guard block reason
    "zero-tool-calls-for-confirmed-root-cause": (
        "Confirmed Root Cause declared with zero tool calls - no investigation occurred"
    ),
    # ANTI-PATTERN-1: Single-hypothesis-lock - overfits to first plausible explanation
    "single-hypothesis-lock": (
        "Only one hypothesis presented before declaring root cause. "
        "Generate >=2 ranked alternatives using hypothesis-scoring.md formula. "
        "Do NOT name root cause until >=2 hypotheses are explored and falsified."
    ),
    # Negative Proof Rule (Layer 3)
    "missing-diverse-negative-proof": (
        "Claim of absence (e.g., 'not found', 'found 0') requires 2+ diverse "
        "verification strategies (e.g., ls + grep, read + glob) to ensure it's not a missed search."
    ),
    "unverified-hypothesis-testing": (
        "Hypothesis marked as tested (\u2713/\u2717) but no corresponding tool evidence found in store. "
        "Ensure you have actually run the verification tools for this hypothesis this turn."
    ),
    # ANTI-PATTERN-2: No call-site evidence - reasoning from partial reads
    "no-call-site-evidence": (
        "Executed Path names a function without showing callers (call-site evidence). "
        "Run: grep -r 'funcName(' src/ to prove the function is actually called. "
        "Functions with 0 callers are dead code and cannot be the root cause."
    ),
    # ANTI-PATTERN-2: Automatic dead-code detection
    "auto-dead-code": (
        "Function '{func}' has 0 callers in codebase - dead code cannot be root cause. "
        "Trace the actual execution path: find what calls the failing code."
    ),
    # ANTI-PATTERN-3: Band-aid chain - defends local consistency too long
    "band-aid-chain": (
        "XY-SUSPECT: {file} has received {count}+ RCA fixes in this terminal session. "
        "Repeated patches to the same file suggest the root cause is elsewhere. "
        "Consider: Is there a shared dependency or upstream cause?"
    ),
    # ANTI-PATTERN-5: Stale execution path - does not re-ground after codebase changes
    "stale-execution-path": (
        "Executed Path references file(s) modified AFTER this RCA session began. "
        "The execution path may no longer reflect current code. "
        "Re-trace the execution path with current file versions."
    ),
    # TASK-001: Ruled Out field - document what alternatives were considered and why rejected
    "missing-ruled-out": (
        "Ruled Out section missing. "
        "Document what alternatives were considered and why each was rejected."
    ),
    # TASK-002: Evidence tier labels - all evidence must have [current-state], [transcript-time], or [inference]
    "evidence-without-tier-label": (
        "Evidence lines lack tier labels. "
        "Prefix each evidence item with: [current-state], [transcript-time], or [inference]"
    ),
    # TASK-003: AP6 - hypothesis was falsified by evidence
    "hypothesis-falsified": (
        "Hypothesis was falsified by evidence. "
        "A hypothesis that can be disproved cannot be the root cause. "
        "Revise hypothesis or generate new alternatives."
    ),
}

# Verification tool names
VERIFICATION_TOOLS = frozenset(
    {
        "Read",
        "Grep",
        "Glob",
        "Bash",
        "View",
        "WebFetch",
    }
)


# --- Turn-scoped Evidence Loading -----------------------------------------


def _get_current_turn_tools(tool_events: list[dict]) -> set[str]:
    """Extract tool names used this turn from tool_events."""
    tools = set()
    for event in tool_events:
        name = event.get("name", "")
        if name:
            tools.add(name)
    return tools


def _load_turn_scoped_tool_events(session_id: str, terminal_id: str) -> list[dict]:
    """Load turn-safe tool events scoped to both session and terminal."""
    if not session_id or not terminal_id or load_scoped_tool_events is None:
        return []
    try:
        return list(
            load_scoped_tool_events(
                session_id=session_id,
                terminal_id=terminal_id,
                scope=SCOPE_TURN_STRICT,
                limit=200,
            )
        )
    except Exception as exc:
        _logger.exception("load_turn_scoped_tool_events failed: %s", exc)
        return []


def _has_verification_this_turn(tool_events: list[dict]) -> bool:
    """Check if verification tools (Read/Grep/Bash/etc.) were used this turn."""
    tools = _get_current_turn_tools(tool_events)
    return bool(tools & VERIFICATION_TOOLS)


def _contains_transcript_only_claim(content: str) -> bool:
    lowered = content.lower()
    return "transcript" in lowered and "transcript-time:" not in lowered


def _normalize_section_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


def _get_section(sections: dict[str, str], field: str) -> str:
    target = _normalize_section_name(field)
    for key, value in sections.items():
        if _normalize_section_name(key) == target:
            return value
    return ""


# --- Section Parsing ------------------------------------------------------


def _parse_hypotheses_from_text(text: str) -> list[dict[str, str]]:
    """Extract hypotheses and their status from response text.
    
    Supports:
    | [Icon] | H[n]: [Name] | [Evidence] |
    - [Icon] H[n]: [Name] ([Evidence])
    """
    hypotheses = []
    
    # Table format: | Icon | H1: Name | Evidence |
    table_pattern = re.compile(r'\|\s*([\u2713\u2717\u29E7\u23F3])\s*\|\s*([^|]+)\|\s*([^|]+)\|', re.UNICODE)
    for match in table_pattern.finditer(text):
        icon, name, evidence = match.groups()
        status = "CONFIRMED" if icon == "\u2713" else ("FALSIFIED" if icon == "\u2717" else ("INCONCLUSIVE" if icon == "\u29E7" else "UNTESTED"))
        hypotheses.append({
            "name": name.strip(),
            "status": status,
            "evidence": evidence.strip(),
            "icon": icon
        })
        
    # List format: - Icon H1: Name (Evidence)
    list_pattern = re.compile(r'^[*-]\s*([\u2713\u2717\u29E7\u23F3])\s*(H\d+:[^(\n]+)(?:\(([^)]+)\))?', re.MULTILINE | re.UNICODE)
    for match in list_pattern.finditer(text):
        icon, name, evidence = match.groups()
        status = "CONFIRMED" if icon == "\u2713" else ("FALSIFIED" if icon == "\u2717" else ("INCONCLUSIVE" if icon == "\u29E7" else "UNTESTED"))
        hypotheses.append({
            "name": name.strip(),
            "status": status,
            "evidence": (evidence or "").strip(),
            "icon": icon
        })
        
    return hypotheses


def _is_absence_claim(text: str) -> bool:
    """Check if text contains a claim of absence/non-existence."""
    absence_patterns = [
        r"found\s+0",
        r"no\s+occurrences",
        r"not\s+found",
        r"empty",
        r"does\s+not\s+exist",
        r"absent",
        r"missing",
        r"0\s+matches",
        r"none\s+found"
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in absence_patterns)


def _count_diverse_tools(tool_events: list[dict]) -> int:
    """Count unique tool types used in the current context."""
    tool_types = set()
    for event in tool_events:
        name = event.get("name", "")
        if name:
            tool_types.add(name)
    return len(tool_types)


def _extract_sections(response: str) -> dict[str, str]:
    """Extract RCA sections from response text.

    Returns dict mapping section name to section content.
    Sections are identified by lines starting with "## " or "### " markdown headers,
    or all-caps headings without markdown.
    """
    sections = {}
    lines = response.split("\n")
    current_section = None
    current_content = []

    # Also check for uppercase non-markdown headings: "SYMPTOM:" or "SYMPTOM\n======="
    markdown_header = re.compile(r"^#{1,3}\s+([A-Za-z ]+):?\s*$")
    underline_header = re.compile(r"^([A-Z][A-Z\s]+)\n=+$")
    colon_header = re.compile(r"^([A-Z][A-Za-z\s]+):\s*$")

    for line in lines:
        # Check for markdown header
        md_match = markdown_header.match(line.strip())
        if md_match:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = md_match.group(1).strip().rstrip(":")
            current_content = []
            continue

        # Check for underline header (SYMPTOM\n=======)
        ul_match = underline_header.match(line.strip())
        if ul_match:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = ul_match.group(1).strip()
            current_content = []
            continue

        # Check for colon header (SYMPTOM:\n)
        col_match = colon_header.match(line.strip())
        if col_match:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = col_match.group(1).strip()
            current_content = []
            continue

        # Check for standalone all-caps line followed by content
        if current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def _section_exists(sections: dict, field: str) -> bool:
    """Check if a section exists and has non-empty content."""
    content = _get_section(sections, field)
    return bool(content and content.strip())


def _section_has_current_turn_evidence(sections: dict, field: str) -> bool:
    """Check if a section contains evidence of current-turn tool usage."""
    content = _get_section(sections, field)
    if not content:
        return False

    # Check for explicit current-turn indicators
    current_turn_patterns = [
        r"Read on [`'\"]",
        r"Grep (?:found|matched|showed)",
        r"Bash (?:showed|output|returned|executed)",
        r"From (?:Read|Grep|Bash|Glob|View)",
        r"\btargets?\s+[`'\"](?!.*transcript)",
    ]

    for pattern in current_turn_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True

    return False


def _find_function_mentions(func_name: str) -> int:
    count = 0
    needle = f"{func_name}("
    for path in HOOKS_DIR.rglob("*.py"):
        try:
            count += path.read_text(encoding="utf-8").count(needle)
        except Exception as exc:
            _logger.exception("Failed to read %s: %s", path, exc)
            continue
    return count


def _extract_function_names(text: str) -> list[str]:
    seen: list[str] = []
    for match in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        if match not in seen:
            seen.append(match)
    return seen


def _count_hypothesis_rows(hypothesis_text: str) -> int:
    """Count the number of hypothesis rows in a markdown hypothesis table."""
    if not hypothesis_text:
        return 0
    rows = 0
    for line in hypothesis_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("|") and any(c in line for c in ("0.", "1.", "Tier", "\u2713", "\u2717")):
            rows += 1
    return rows


def _check_dead_code_auto(executed_path: str, root_cause: str, falsifier: str) -> list[str]:
    """Automatically detect dead code — ALL function names in Executed Path."""
    func_names = _extract_function_names(executed_path)
    if not func_names:
        return []

    # Start with all functions as potentially dead; remove each found in a file
    dead_functions: set[str] = set(func_names)

    # Scan each file once, checking all needles against each file
    for path in HOOKS_DIR.rglob("*.py"):
        try:
            content = path.read_text(encoding="utf-8")
            for func_name in list(dead_functions):
                if f"{func_name}(" in content:
                    dead_functions.discard(func_name)
        except Exception as exc:
            _logger.exception("Failed to read %s: %s", path, exc)
            continue

    return list(dead_functions)


def _has_call_site_evidence(executed_path: str, evidence: str) -> bool:
    """Check if Evidence section shows grep/call-site evidence for Executed Path functions."""
    func_names = _extract_function_names(executed_path)
    if not func_names:
        return True  # No functions named, nothing to prove

    # Evidence must show grep results for at least one function in Executed Path
    call_evidence_patterns = [
        r"grep\s+(?:found|matched|calls?|callers?)",
        r"\bcallers?\s*[:=]",
        r"\b\d+\s+callers?",
    ]
    for pattern in call_evidence_patterns:
        if re.search(pattern, evidence, re.IGNORECASE):
            return True
    return False


# --- AP3: Band-Aid Chain Detector ---------------------------------------------

BAND_AID_FILE = "rca_band_aid.json"
# BAND_AID_THRESHOLD = 3: More than 3 fixes to the same file suggests band-aid pattern
# (RFC 1925 rule of optimality: repeated patches indicate root cause is elsewhere)
BAND_AID_THRESHOLD = 3
BAND_AID_STATE_TTL = 3600  # 1-hour terminal state TTL


def _load_band_aid_state(terminal_id: str) -> BandAidState:
    if not terminal_id:
        return {}
    try:
        from __lib.state_paths import get_terminal_state_path
        path = get_terminal_state_path(terminal_id, BAND_AID_FILE)
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.monotonic() - data.get("_ts", 0) > BAND_AID_STATE_TTL:
            return {}
        return data
    except FileNotFoundError:
        # State file doesn't exist yet
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        # Corrupt state file or I/O error - log and return empty
        _logger.error("Corrupt or unreadable band-aid state file: %s", exc)
        return {}


def _save_band_aid_state(terminal_id: str, state: dict) -> None:
    if not terminal_id:
        return
    try:
        from __lib.state_paths import get_terminal_state_path
        path = get_terminal_state_path(terminal_id, BAND_AID_FILE)
        state["_ts"] = time.monotonic()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, encoding="utf-8"), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        _logger.error("Unexpected error saving band-aid state: %s", exc)


def _extract_fix_files(fix_text: str) -> list[str]:
    if not fix_text:
        return []
    paths: list[str] = []
    for match in re.finditer(r"([A-Za-z]:[\\\/])?[\w./\\-]+\.py\b", fix_text):
        path = match.group()
        if path and len(path) > 3:
            paths.append(path)
    return paths


def _check_band_aid_chain(fix_text: str, terminal_id: str) -> list[str]:
    if not terminal_id or not fix_text:
        return []

    files = _extract_fix_files(fix_text)
    if not files:
        return []

    try:
        from __lib.file_lock import FileLock
        from __lib.state_paths import get_terminal_state_path
        lock_path = get_terminal_state_path(terminal_id, BAND_AID_FILE).with_suffix(".lock")
        with FileLock(lock_path, timeout=5.0):
            state = _load_band_aid_state(terminal_id)
            fixes: dict = state.get("fixes", {})
            block_messages: list[str] = []
            for fpath in files:
                key = fpath.replace("\\", "/")
                count = fixes.get(key, 0) + 1
                fixes[key] = count
                if count >= BAND_AID_THRESHOLD:
                    block_messages.append(
                        BLOCK_REASONS["band-aid-chain"].format(file=key, count=BAND_AID_THRESHOLD)
                    )
            state["fixes"] = fixes
            _save_band_aid_state(terminal_id, state)
            return block_messages
    except Exception as exc:
        # Fail-safe: Log error but don't block completion. Band-aid detection is
        # a protective feature, not a blocking requirement. Users can inspect
        # logs if they suspect repeated fixes are not being caught.
        _logger.error("Unexpected error in band-aid chain check: %s", exc)
        return []


# --- AP5: Filesystem Freshness Validator --------------------------------------


def _extract_file_paths_from_path(executed_path: str) -> list[str]:
    if not executed_path:
        return []
    paths: list[str] = []
    for match in re.finditer(r"([A-Za-z]:[\\\/])?[\w./\\-]+\.py\b", executed_path):
        path = match.group()
        if path and len(path) > 3:
            paths.append(path)
    return paths


def _get_file_mtime(file_path: str) -> float | None:
    p: Path = Path(file_path)
    if not p.is_absolute():
        p = Path("P:\\\\\\") / file_path
    try:
        if p.exists():
            return p.stat().st_mtime
        return None
    except Exception as exc:
        _logger.error("Unexpected error accessing %s: %s", p, exc)
        return None


def _check_stale_execution_path(
    executed_path: str,
    rca_timestamp: float | None,
) -> list[str]:
    if not rca_timestamp or not executed_path:
        return []

    files = _extract_file_paths_from_path(executed_path)
    if not files:
        return []

    block_messages: list[str] = []
    for fpath in files:
        mtime = _get_file_mtime(fpath)
        if mtime is not None and mtime > rca_timestamp:
            block_messages.append(
                f"stale-execution-path:{fpath} (modified {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))} > RCA session start)"
            )

    return block_messages


def _contains_unverified_token(text: str) -> bool:
    return bool(re.search(r"\bUNVERIFIED\b", text, re.IGNORECASE))


def _detect_single_rc_escape(response: str) -> bool:
    return bool(SINGLE_RC_ESCAPE.search(response))


def _detect_urgency(response: str) -> bool:
    for pattern in URGENCY_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            return True
    return False


def _format_structured_feedback(block_reasons: list, hypothesis_details: list | None = None) -> str:
    lines = [
        "**RCA Contract Structural Validation Failed**\n",
        "Your RCA response is missing required structural elements:\n",
    ]
    for reason in block_reasons:
        lines.append(f"- {reason}")

    if hypothesis_details:
        tested_count = sum(
            1 for h in hypothesis_details
            if h.get("status") in ("CONFIRMED", "FALSIFIED", "INCONCLUSIVE")
        )
        total = len(hypothesis_details)
        lines.extend([
            "",
            f"Hypothesis Testing Progress: {tested_count}/{total} tested",
            "",
            "Hypothesis Status:",
            "",
        ])
        for h in hypothesis_details:
            status = h.get("status", "UNTESTED").upper()
            icon = "\u2713" if status == "CONFIRMED" else ("\u2717" if status == "FALSIFIED"
                    else "\u29E7" if status == "INCONCLUSIVE" else "\u23F3")
            # Note: Fallback pattern is intentional here - hypotheses use "name" key
            # (from _parse_hypotheses_from_text) but legacy data may use "claim"
            name = h.get("name") or h.get("claim", "Unknown")
            lines.append(f"   {icon} {name} \u2192 {status}")
            if status == "UNTESTED" and h.get("test_suggestion"):
                lines.append(f"      Suggested test: {h['test_suggestion']}")

    lines.extend(
        [
            "",
            "Required sections: Symptom, Evidence (>=1 current-turn tool), Executed Path,",
            "Alternative Hypothesis, Falsifier, Root Cause (in Executed Path), Fix, Verification.",
            "",
            "Do NOT block on wording style -- only on missing structural proof.",
        ]
    )

    return "\n".join(lines)


# --- TASK-002: Evidence Tier Label Validation --------------------------------


def _validate_evidence_tier_labels(evidence: str) -> list[str]:
    if not evidence:
        return []

    required_labels = ["[current-state]", "[transcript-time]", "[inference]"]
    unlabeled_lines = []
    in_code_block = False

    for line in evidence.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped:
            continue
        if any(stripped.startswith(label) for label in required_labels):
            continue
        if len(stripped) <= 3:
            continue
        unlabeled_lines.append(stripped[:50])

    if unlabeled_lines:
        return ["evidence-without-tier-label: " + "; ".join(unlabeled_lines[:3])]
    return []


# --- TASK-003: AP6 Adversarial Hypothesis Validator ----------------------------


def _validate_adversarial_hypothesis(
    sections: dict,
    tool_events: list[dict],
) -> list[str]:
    falsifier = _get_section(sections, "Falsifier")
    if not falsifier:
        return []

    block_reasons = []
    falsified_patterns = [
        r"falsified",
        r"disproved",
        r"debunked",
        r"test showed hypothesis",
        r"hypothesis is false",
        r"hypothesis is wrong",
        r"grep found 0",
    ]

    falsifier_lower = falsifier.lower()
    for pattern in falsified_patterns:
        if re.search(pattern, falsifier_lower):
            block_reasons.append(
                "hypothesis-falsified: Alternative hypothesis was disproved by evidence. "
                "Revise or replace the hypothesis before declaring root cause."
            )
            break

    return block_reasons


# --- Structure Validation (TASK-004): Artifact Path Existence -----------------------


def _validate_artifact_paths_exist(sections: dict) -> list[str]:
    evidence = _get_section(sections, "Evidence")
    if not evidence:
        return []

    artifact_paths = _extract_artifact_paths(evidence)
    if not artifact_paths:
        return []

    block_reasons = []
    for path_str in artifact_paths:
        if path_str.startswith(("http", "https", "ftp", "file")):
            continue
        p = Path(path_str)
        if not p.is_absolute():
            p = Path("P:\\\\\\") / path_str
        if not p.exists():
            block_reasons.append(f"missing-artifact:{path_str}")

    return block_reasons


# --- Semantic Binding Validation (TASK-006) --------------------------------


def _extract_artifact_paths(evidence_text: str) -> list[str]:
    if not evidence_text:
        return []

    path_patterns = [
        r'Read\s+(?:on\s+)?(?:from\s+)?[`"]([^`"]+)[`"]',
        r'Grep\s+found\s+(?:\w+\s+)?in\s+[`"]([^`"]+)[`"]',
        r'Bash\s+(?:showed|output).*?in\s+[`"]([^`"]+)[`"]',
        r":\s*([\\w./-]+\\\w[\\w./-]+)",
    ]

    artifacts = set()
    for pattern in path_patterns:
        for match in re.finditer(pattern, evidence_text, re.IGNORECASE):
            artifact = match.group(1).replace("\\", "/")
            if ":" in artifact:
                if "/" in artifact and artifact.find("/") < artifact.rfind(":"):
                    artifact = artifact.rsplit(":", 1)[0]
            if artifact:
                artifacts.add(artifact)

    return sorted(artifacts)


def _validate_evidence_bindings(
    sections: dict,
    tool_events: list[dict],
    session_id: str,
    terminal_id: str,
) -> list[str]:
    if not load_epistemic_bindings:
        return []

    evidence = _get_section(sections, "Evidence")
    if not evidence:
        return []

    block_reasons = []
    artifact_paths = _extract_artifact_paths(evidence)
    if not artifact_paths:
        return []

    tool_event_ids = {event.get("id") for event in tool_events if event.get("id")}
    if not tool_event_ids:
        block_reasons.append("evidence-without-tool-events")
        return block_reasons

    try:
        bindings = list(load_epistemic_bindings(session_id=session_id, terminal_id=terminal_id))
    except Exception:
        return []

    for artifact_path in artifact_paths:
        artifact_bindings = [b for b in bindings if b.get("artifact_path", "") == artifact_path]
        if not artifact_bindings:
            block_reasons.append(f"unbound-evidence:{artifact_path}")
            continue
        valid_bindings = [b for b in artifact_bindings if b.get("tool_event_id") in tool_event_ids]
        if not valid_bindings:
            block_reasons.append(f"stale-evidence:{artifact_path}")
            continue
        if any(b.get("terminal_id", "") != terminal_id for b in artifact_bindings):
            block_reasons.append(f"cross-terminal-evidence:{artifact_path}")
        if any(b.get("is_stale") == 1 for b in artifact_bindings):
            block_reasons.append(f"stale-binding:{artifact_path}")

    return block_reasons


# --- Main Validation Logic ------------------------------------------------


def _validate_rca_contract(
    data: dict,
    response: str,
    tool_events: list[dict],
    rca_turn: bool,
    session_id: str = "",
    terminal_id: str = "",
    rca_timestamp: float | None = None,
) -> tuple[bool, list[str]]:
    if not rca_turn:
        return True, []

    block_reasons: list[str] = []
    sections = _extract_sections(response)

    symptom = _get_section(sections, "Symptom")
    evidence = _get_section(sections, "Evidence")
    executed_path = _get_section(sections, "Executed Path")
    alternative = _get_section(sections, "Alternative Hypothesis")
    falsifier = _get_section(sections, "Falsifier")
    root_cause = _get_section(sections, "Root Cause")
    fix = _get_section(sections, "Fix")
    verification = _get_section(sections, "Verification")

    if not symptom: block_reasons.append(BLOCK_REASONS["missing-symptom"])
    if not evidence:
        block_reasons.append(BLOCK_REASONS["missing-evidence"])
    elif _contains_transcript_only_claim(evidence):
        block_reasons.append(BLOCK_REASONS["unlabeled-transcript-evidence"])
    elif not _has_verification_this_turn(tool_events) or not _section_has_current_turn_evidence(sections, "Evidence"):
        block_reasons.append(BLOCK_REASONS["missing-evidence"])
    else:
        block_reasons.extend(_validate_evidence_bindings(sections, tool_events, session_id, terminal_id))

    if evidence and not _contains_transcript_only_claim(evidence):
        block_reasons.extend(_validate_artifact_paths_exist(sections))

    if not executed_path:
        block_reasons.append(BLOCK_REASONS["missing-executed-path"])
    elif _contains_transcript_only_claim(executed_path):
        block_reasons.append(BLOCK_REASONS["unlabeled-transcript-evidence"])

    if _extract_function_names(executed_path) and evidence and not _has_call_site_evidence(executed_path, evidence):
        block_reasons.append(BLOCK_REASONS["no-call-site-evidence"])

    block_reasons.extend(_check_stale_execution_path(executed_path, rca_timestamp))

    if root_cause and alternative and _count_hypothesis_rows(alternative) < 2:
        block_reasons.append(BLOCK_REASONS["single-hypothesis-lock"])

    if not alternative: block_reasons.append(BLOCK_REASONS["missing-alternative"])
    if not falsifier:
        block_reasons.append(BLOCK_REASONS["missing-falsifier"])
    elif alternative:
        alt_tokens = {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", alternative)}
        if alt_tokens and not any(t in falsifier.lower() for t in alt_tokens):
            block_reasons.append(BLOCK_REASONS["missing-falsifier"])

    if falsifier:
        block_reasons.extend(_validate_adversarial_hypothesis(sections, tool_events))
    if evidence:
        block_reasons.extend(_validate_evidence_tier_labels(evidence))

    if not _get_section(sections, "Ruled Out"): block_reasons.append(BLOCK_REASONS["missing-ruled-out"])

    if not root_cause:
        block_reasons.append(BLOCK_REASONS["unreachable-root-cause"])
    else:
        identifiers = [idf for idf in re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", root_cause) if len(idf) > 2]
        if executed_path and identifiers and not any(idf.lower() in executed_path.lower() for idf in identifiers):
            block_reasons.append(BLOCK_REASONS["unreachable-root-cause"])
        dead_funcs = _check_dead_code_auto(executed_path, root_cause, falsifier)
        for func in dead_funcs: block_reasons.append(BLOCK_REASONS["auto-dead-code"].format(func=func))

    if not fix: block_reasons.append(BLOCK_REASONS["missing-fix"])
    if fix and terminal_id: block_reasons.extend(_check_band_aid_chain(fix, terminal_id))

    if not verification:
        block_reasons.append(BLOCK_REASONS["missing-verification"])
    elif any(re.match(p, verification.strip(), re.IGNORECASE) for p in [r"^test\s+it\s*$", r"^verify\s*$", r"^check\s+it\s*$", r"^run\s+the?\s+test"]):
        block_reasons.append(BLOCK_REASONS["missing-verification"])

    # --- Layer 3: Evidence-Backed Hypothesis Verification ---
    hypotheses = _parse_hypotheses_from_text(response)
    if hypotheses:
        if not data.get("hypothesis_details"):
            data["hypothesis_details"] = hypotheses
        for h in hypotheses:
            if h["status"] in ("CONFIRMED", "FALSIFIED"):
                h_evidence = h.get("evidence", "")
                h_name = h.get("name", "")
                if _is_absence_claim(h_evidence) or _is_absence_claim(h_name):
                    if _count_diverse_tools(tool_events) < 2:
                        block_reasons.append(BLOCK_REASONS["missing-diverse-negative-proof"])
                if not tool_events:
                    block_reasons.append(BLOCK_REASONS["unverified-hypothesis-testing"])

    unique_reasons = list(dict.fromkeys(block_reasons))
    root_cause_confirmed = bool(root_cause) and not _contains_unverified_token(root_cause)
    if root_cause_confirmed and not tool_events:
        unique_reasons.append(BLOCK_REASONS["zero-tool-calls-for-confirmed-root-cause"])

    return len(unique_reasons) == 0, unique_reasons


def check(data: dict) -> dict | None:
    rca_turn = data.get("rca_turn", False)
    if not rca_turn: return None
    response = data.get("assistant_response", "") or data.get("response", "") or ""
    if not response: return None
    single_rc_escape = _detect_single_rc_escape(response)
    session_id = data.get("session_id", "")
    terminal_id = data.get("terminal_id", "")
    rca_timestamp = data.get("session_start_ts")
    tool_events = data.get("tool_events", [])
    if not tool_events: tool_events = _load_turn_scoped_tool_events(session_id, terminal_id)
    
    is_valid, block_reasons = _validate_rca_contract(data, response, tool_events, rca_turn, session_id, terminal_id, rca_timestamp)
    
    if single_rc_escape:
        hypo_related = {"single-hypothesis-lock", "missing-alternative", "missing-falsifier", "missing-ruled-out"}
        block_reasons = [r for r in block_reasons if not any(r.lower().startswith(BLOCK_REASONS[k].lower()[:50]) for k in hypo_related if k in BLOCK_REASONS)]
        is_valid = len(block_reasons) == 0

    if is_valid: return None
    if _ADVISORY_MODE:
        _get_logger().warning("ADVISORY: RCA contract violations: %s", block_reasons)
        return None

    _get_logger().info("RCA contract validation failed: %s", block_reasons)
    feedback = _format_structured_feedback(block_reasons, data.get("hypothesis_details"))
    return {"decision": "block", "reason": feedback, "blocking_hook": "StopHook_rca_contract", "block_reasons": block_reasons}


def run(data: dict) -> dict | None:
    result = check(data)
    if result and result.get("decision") == "block":
        return {"block": True, "reason": result.get("reason", ""), "blocking_hook": result.get("blocking_hook", "StopHook_rca_contract")}
    return result


if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read().strip())
        result = check(data)
        if result: print(json.dumps(_normalize_stdout(result)))
        if result and result.get("decision") == "block": sys.exit(2)
    except Exception:
        sys.exit(0)
