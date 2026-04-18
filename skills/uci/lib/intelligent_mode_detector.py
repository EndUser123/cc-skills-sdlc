"""
Intelligent Mode Detection for Unified Code Inspection

Analyzes context signals to automatically select the appropriate review mode.
Provides intelligent defaults that can be overridden with --lite and --full flags.

Mode selection is based on:
1. File count (number of changed files)
2. Risk indicators (security, auth, payments, etc.)
3. Line count (size of changes)
4. File types (configuration vs code)
5. Change type (bug fix, feature, refactor)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ContextSignals:
    """Collected signals about the code change context."""
    file_count: int
    line_count: int
    risk_score: int  # 0-100, higher = more risk
    has_tests: bool
    file_extensions: Set[str]
    high_risk_paths: List[str]
    change_type: Optional[str] = None


@dataclass
class ModeDetectionResult:
    """Result of intelligent mode detection."""
    mode: str
    reason: str
    confidence: float  # 0.0-1.0
    signals: ContextSignals


# Risk patterns that signal need for deeper review
RISK_PATTERNS = {
    "security": 30,
    "auth": 25,
    "login": 25,
    "password": 30,
    "secret": 30,
    "crypto": 25,
    "payment": 30,
    "checkout": 20,
    "user": 15,
    "session": 20,
    "token": 25,
    "api": 15,
    "database": 15,
    "migration": 20,
    "deploy": 20,
    "infrastructure": 20,
}

# File extension risk modifiers
EXTENSION_RISK = {
    # Infrastructure/Config - lower risk
    ".md": -10,
    ".txt": -10,
    ".yml": -5,
    ".yaml": -5,
    ".json": -5,
    ".toml": -5,
    ".lock": -15,

    # Python/Code - standard risk
    ".py": 0,
    ".js": 0,
    ".ts": 0,
    ".jsx": 0,
    ".tsx": 0,

    # Templates - slightly lower risk
    ".html": -5,
    ".css": -5,
    ".scss": -5,

    # Shell/Infrastructure - higher risk
    ".sh": 10,
    ".bash": 10,
    ".dockerfile": 15,
    "Dockerfile": 15,
}


def detect_mode_from_context(
    file_paths: List[str],
    diff_content: str = "",
    change_type: Optional[str] = None,
    lite_override: bool = False,
    full_override: bool = False,
) -> ModeDetectionResult:
    """
    Detect appropriate review mode from context signals.

    Args:
        file_paths: List of changed file paths
        diff_content: Git diff content (for line counting)
        change_type: Optional change type hint (bug_fix, new_feature, etc.)
        lite_override: If True, force triage mode
        full_override: If True, force comprehensive mode

    Returns:
        ModeDetectionResult with selected mode and reasoning

    Examples:
        >>> detect_mode_from_context(["src/auth.py"], "diff...")
        ModeDetectionResult(mode='deep', reason='High-risk auth code detected', ...)

        >>> detect_mode_from_context(["README.md"], "diff...", lite_override=True)
        ModeDetectionResult(mode='triage', reason='--lite flag override', ...)
    """
    # Handle override flags first
    if lite_override:
        return ModeDetectionResult(
            mode="triage",
            reason="--lite flag override: fast review with 3 core agents",
            confidence=1.0,
            signals=ContextSignals(
                file_count=len(file_paths),
                line_count=diff_content.count('\n'),
                risk_score=0,
                has_tests=False,
                file_extensions=set(),
                high_risk_paths=[],
            ),
        )

    if full_override:
        return ModeDetectionResult(
            mode="comprehensive",
            reason="--full flag override: complete review with all agents",
            confidence=1.0,
            signals=ContextSignals(
                file_count=len(file_paths),
                line_count=diff_content.count('\n'),
                risk_score=0,
                has_tests=False,
                file_extensions=set(),
                high_risk_paths=[],
            ),
        )

    # Collect context signals
    signals = _collect_signals(file_paths, diff_content, change_type)

    # Apply mode selection logic
    mode, reason, confidence = _select_mode(signals)

    logger.info(f"Auto-detected mode: {mode} (confidence: {confidence:.2f}) - {reason}")

    return ModeDetectionResult(
        mode=mode,
        reason=reason,
        confidence=confidence,
        signals=signals,
    )


def _collect_signals(
    file_paths: List[str],
    diff_content: str,
    change_type: Optional[str],
) -> ContextSignals:
    """Collect all context signals for mode detection."""
    # Count lines in diff (approximate)
    line_count = diff_content.count('\n') if diff_content else 0

    # Extract file extensions
    file_extensions = set()
    for path in file_paths:
        ext = Path(path).suffix.lower()
        if ext:
            file_extensions.add(ext)

    # Detect test files
    has_tests = any(_is_test_file(p) for p in file_paths)

    # Calculate risk score
    risk_score, high_risk_paths = _calculate_risk_score(file_paths)

    return ContextSignals(
        file_count=len(file_paths),
        line_count=line_count,
        risk_score=risk_score,
        has_tests=has_tests,
        file_extensions=file_extensions,
        high_risk_paths=high_risk_paths,
        change_type=change_type,
    )


def _select_mode(signals: ContextSignals) -> Tuple[str, str, float]:
    """
    Select mode based on collected signals.

    Returns:
        Tuple of (mode, reason, confidence)
    """
    score = 0
    reasons = []

    # 1. Risk scoring (highest weight)
    if signals.risk_score >= 50:
        score += 40
        reasons.append(f"high-risk files ({signals.high_risk_paths})")
    elif signals.risk_score >= 30:
        score += 25
        reasons.append("moderate-risk files")
    elif signals.risk_score >= 15:
        score += 10
        reasons.append("some risk indicators")

    # 2. File count
    if signals.file_count == 0:
        score += 0
    elif signals.file_count <= 2:
        score += 5
        reasons.append(f"small scope ({signals.file_count} files)")
    elif signals.file_count <= 5:
        score += 10
        reasons.append(f"focused change ({signals.file_count} files)")
    elif signals.file_count <= 15:
        score += 20
        reasons.append(f"moderate scope ({signals.file_count} files)")
    elif signals.file_count <= 50:
        score += 30
        reasons.append(f"large scope ({signals.file_count} files)")
    else:
        score += 40
        reasons.append(f"very large scope ({signals.file_count} files)")

    # 3. Line count
    if signals.line_count < 100:
        score += 5
    elif signals.line_count < 500:
        score += 10
        reasons.append(f"{signals.line_count} lines changed")
    elif signals.line_count < 2000:
        score += 20
        reasons.append(f"{signals.line_count} lines changed")
    else:
        score += 30
        reasons.append(f"{signals.line_count}+ lines (substantial change)")

    # 4. Test presence (slightly reduces score - tests provide safety)
    if signals.has_tests:
        score -= 5

    # 5. Extension risk modifiers
    ext_risk = sum(EXTENSION_RISK.get(ext, 0) for ext in signals.file_extensions)
    score += max(-15, min(20, ext_risk))  # Clamp between -15 and 20
    if ext_risk > 10:
        reasons.append("infrastructure changes detected")
    elif ext_risk < -10:
        reasons.append("mostly documentation/config changes")

    # 6. Change type hints
    if signals.change_type:
        if signals.change_type == "bug_fix":
            score += 15  # Bug fixes need careful review
            reasons.append("bug fix requires careful verification")
        elif signals.change_type == "new_feature":
            score += 20  # New features need thorough review
            reasons.append("new feature implementation")
        elif signals.change_type == "refactor":
            score += 10  # Refactors need quality review
            reasons.append("refactoring for quality")
        elif signals.change_type == "config_infra":
            score += 5  # Config changes are lower risk
            reasons.append("infrastructure/configuration change")

    # Normalize score to 0-100 range (approximately)
    normalized_score = max(0, min(100, score))

    # Map score to mode with confidence
    if normalized_score >= 70:
        return "comprehensive", _build_reason(reasons, "comprehensive"), 0.85
    elif normalized_score >= 50:
        return "deep", _build_reason(reasons, "deep"), 0.80
    elif normalized_score >= 25:
        return "standard", _build_reason(reasons, "standard"), 0.75
    else:
        return "triage", _build_reason(reasons, "triage"), 0.70


def _calculate_risk_score(file_paths: List[str]) -> Tuple[int, List[str]]:
    """
    Calculate risk score based on file paths.

    Returns:
        Tuple of (risk_score, list_of_high_risk_paths)
    """
    risk_score = 0
    high_risk_paths = []

    for path in file_paths:
        path_lower = path.lower()
        file_risk = 0

        # Check for risk patterns in path
        for pattern, pattern_risk in RISK_PATTERNS.items():
            if pattern in path_lower:
                file_risk += pattern_risk
                if pattern_risk >= 20:
                    high_risk_paths.append(path)

        # Check extension risk
        ext = Path(path).suffix.lower()
        file_risk += EXTENSION_RISK.get(ext, 0)

        # Accumulate total risk
        risk_score += max(0, file_risk)

    return min(100, risk_score), high_risk_paths


def _is_test_file(path: str) -> bool:
    """Check if a file is a test file."""
    path_lower = path.lower()
    return "test" in path_lower or "spec" in path_lower


def _build_reason(reasons: List[str], mode: str) -> str:
    """Build human-readable reason string."""
    if not reasons:
        return f"auto-detected {mode} mode based on change analysis"
    return f"auto-detected {mode} mode: {', '.join(reasons[:3])}"


def format_mode_detection_message(result: ModeDetectionResult) -> str:
    """
    Format a user-friendly message explaining mode selection.

    Returns:
        Formatted message for display
    """
    lines = [
        f"**Mode**: {result.mode.upper()}",
        f"**Reason**: {result.reason}",
        "",
        f"**Context**: {result.signals.file_count} files, {result.signals.line_count} lines, risk score {result.signals.risk_score}/100",
    ]

    if result.signals.high_risk_paths:
        lines.append(f"**High-risk files**: {', '.join(result.signals.high_risk_paths[:3])}")

    agent_counts = {
        "triage": 3,
        "standard": 4,
        "deep": 8,
        "comprehensive": 11,
    }
    lines.append(f"**Agents running**: {agent_counts.get(result.mode, '?')}")

    return "\n".join(lines)
