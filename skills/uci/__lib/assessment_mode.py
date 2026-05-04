"""
Assessment/Dry-Run Mode for Unified Code Inspection

Provides dry-run reporting capability for all agents.
Analyzes code without making changes, returning structured findings.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AssessmentFinding:
    """A single finding from assessment mode."""
    file: str
    line_range: str  # e.g., "45-50" or "45"
    code_snippet: str
    issue_description: str
    recommendation: str
    verdict: str  # HIGH/MED/LOW
    category: str  # logic, security, performance, etc.
    agent: str


@dataclass
class AssessmentReport:
    """Complete assessment report for dry-run mode."""
    findings: List[AssessmentFinding] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    top_actionable: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get formatted summary string."""
        total = len(self.findings)
        high = sum(1 for f in self.findings if f.verdict == "HIGH")
        medium = sum(1 for f in self.findings if f.verdict == "MED")
        low = sum(1 for f in self.findings if f.verdict == "LOW")

        return (
            f"Total findings: {total}\n"
            f"  HIGH: {high}\n"
            f"  MEDIUM: {medium}\n"
            f"  LOW: {low}"
        )


class AssessmentMode:
    """
    Dry-run assessment mode for code inspection.

    Requirements from TASK-006B:
    - Report Format: File, line range, code snippet, issue description, recommendation, verdict (HIGH/MED/LOW)
    - Verification Requirements: Read files before claiming line numbers/counts
    - Recommendation Quality Gate: 6-check validation before including findings
    - Severity Calibration: HIGH (correctness/leaks), MEDIUM (maintainability), LOW (style)
    - Multi-File Reporting: Group by priority, then file, line-number order
    - Summary: Total findings by severity, top 3 actionable items
    """

    # Severity calibration
    SEVERITY_HIGH = "HIGH"
    SEVERITY_MEDIUM = "MEDIUM"
    SEVERITY_LOW = "LOW"

    # 6-check validation for recommendation quality
    QUALITY_CHECKS = [
        "specific_action",  # Recommendation specifies concrete action
        "feasible",  # Action is achievable for solo-dev
        "no_team_coord",  # Doesn't require team coordination
        "evidence_based",  # Based on actual code evidence
        "clear_benefit",  # Benefit is clear
        "not_yagni",  # Not solving non-existent problem
    ]

    def __init__(self, scope_files: Optional[List[str]] = None):
        """
        Initialize assessment mode.

        Args:
            scope_files: List of files to assess (optional)
        """
        self.scope_files = scope_files or []
        self.findings: List[AssessmentFinding] = []

    def assess_findings(
        self,
        raw_findings: List[Dict[str, Any]],
        agent_name: str
    ) -> List[AssessmentFinding]:
        """
        Assess raw findings and convert to AssessmentFinding format.

        Args:
            raw_findings: Raw findings from agents
            agent_name: Name of the agent generating findings

        Returns:
            List of validated AssessmentFinding objects
        """
        validated = []

        for finding in raw_findings:
            # Extract required fields
            location = finding.get("location", "")
            if not location:
                continue  # Skip findings without location

            # Parse file and line range from location
            file_path, line_range = self._parse_location(location)

            # Get code snippet if available
            code_snippet = self._get_code_snippet(file_path, line_range)

            # Assess severity
            verdict = self._assess_severity(finding)

            # Validate recommendation quality (6-check gate)
            if not self._validate_recommendation_quality(finding):
                logger.debug(f"Finding rejected by quality gate: {finding.get('problem', 'unknown')}")
                continue

            # Create AssessmentFinding
            assessment = AssessmentFinding(
                file=file_path,
                line_range=line_range,
                code_snippet=code_snippet,
                issue_description=finding.get("problem", "No description"),
                recommendation=finding.get("recommendation", "No recommendation"),
                verdict=verdict,
                category=finding.get("category", "general"),
                agent=agent_name
            )

            validated.append(assessment)

        return validated

    def _parse_location(self, location: str) -> tuple[str, str]:
        """
        Parse location string into file and line range.

        Args:
            location: Location string (e.g., "src/auth.py:45" or "src/auth.py:45-50")

        Returns:
            Tuple of (file_path, line_range)
        """
        if ":" in location:
            parts = location.split(":")
            file_path = parts[0]
            line_range = parts[1] if len(parts) > 1 else "unknown"
        else:
            file_path = location
            line_range = "unknown"

        return file_path, line_range

    def _get_code_snippet(self, file_path: str, line_range: str) -> str:
        """
        Get code snippet from file for context.

        Args:
            file_path: Path to file
            line_range: Line range (e.g., "45-50")

        Returns:
            Code snippet string
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return "[File not found]"

            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            # Parse line range
            if "-" in line_range:
                start, end = line_range.split("-")
                start_line = int(start) - 1  # Convert to 0-indexed
                end_line = int(end)
            else:
                try:
                    start_line = int(line_range) - 1
                    end_line = start_line + 3  # Show 3 lines of context
                except ValueError:
                    start_line = 0
                    end_line = min(3, len(lines))

            # Extract snippet
            snippet_lines = lines[max(0, start_line):min(end_line, len(lines))]
            return "\n".join(snippet_lines)

        except Exception as e:
            logger.debug(f"Failed to read code snippet: {e}")
            return "[Could not read snippet]"

    def _assess_severity(self, finding: Dict[str, Any]) -> str:
        """
        Assess severity based on finding type.

        Severity Calibration:
        - HIGH: Correctness issues, leaks, crashes
        - MEDIUM: Maintainability, technical debt
        - LOW: Style, conventions

        Args:
            finding: Finding dictionary

        Returns:
            Severity level (HIGH/MEDIUM/LOW)
        """
        category = finding.get("category", "").lower()
        problem = finding.get("problem", "").lower()

        # HIGH severity categories
        high_categories = ["security", "logic", "async", "race", "error"]
        high_keywords = ["crash", "leak", "corrupt", "injection", "overflow", "deadlock"]

        # LOW severity categories
        low_categories = ["conventions", "style", "syntax"]
        low_keywords = ["formatting", "whitespace", "naming"]

        # Check HIGH
        if any(cat in category for cat in high_categories):
            return self.SEVERITY_HIGH
        if any(kw in problem for kw in high_keywords):
            return self.SEVERITY_HIGH

        # Check LOW
        if any(cat in category for cat in low_categories):
            return self.SEVERITY_LOW
        if any(kw in problem for kw in low_keywords):
            return self.SEVERITY_LOW

        # Default to MEDIUM
        return self.SEVERITY_MEDIUM

    def _validate_recommendation_quality(self, finding: Dict[str, Any]) -> bool:
        """
        Validate recommendation quality using 6-check gate.

        Checks:
        1. Specific action (not vague)
        2. Feasible for solo-dev
        3. No team coordination required
        4. Based on evidence
        5. Clear benefit
        6. Not YAGNI

        Args:
            finding: Finding dictionary

        Returns:
            True if recommendation passes all checks
        """
        recommendation = finding.get("recommendation", "").lower()

        # Check 1: Specific action
        if not recommendation or len(recommendation) < 10:
            return False  # Too vague

        # Check 2: Feasible for solo-dev
        impractical_patterns = [
            "team coordination",
            "stakeholder approval",
            "cross-team coordination",
            "requires team discussion",
            "get team consensus",
        ]
        if any(pattern in recommendation for pattern in impractical_patterns):
            return False  # Requires team coordination

        # Check 3: Based on evidence (has location)
        if not finding.get("location"):
            return False  # No evidence location

        # Check 4: Clear benefit (has "fix", "add", "remove", etc.)
        action_verbs = ["fix", "add", "remove", "replace", "update", "change", "implement"]
        if not any(verb in recommendation for verb in action_verbs):
            return False  # Unclear benefit

        # Check 5: Not YAGNI (not solving non-existent problem)
        if "consider" in recommendation and "future" in recommendation:
            return False  # Probably YAGNI

        # Check 6: Evidence-based (problem is specific)
        problem = finding.get("problem", "")
        if len(problem) < 10:
            return False  # Problem too vague

        return True

    def generate_report(self, findings: List[AssessmentFinding]) -> AssessmentReport:
        """
        Generate complete assessment report.

        Multi-File Reporting: Group by priority, then file, line-number order.

        Args:
            findings: List of validated findings

        Returns:
            AssessmentReport with grouped findings and summary
        """
        # Sort by verdict (HIGH first), then file, then line number
        def sort_key(f: AssessmentFinding):
            verdict_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            verdict_priority = verdict_order.get(f.verdict, 3)
            return (verdict_priority, f.file, f.line_range)

        sorted_findings = sorted(findings, key=sort_key)

        # Generate summary
        summary = {
            "total": len(findings),
            "high": sum(1 for f in findings if f.verdict == "HIGH"),
            "medium": sum(1 for f in findings if f.verdict == "MEDIUM"),
            "low": sum(1 for f in findings if f.verdict == "LOW"),
        }

        # Top 3 actionable items (highest priority)
        top_actionable = [
            f"[{f.verdict}] {f.file}:{f.line_range} - {f.issue_description[:60]}"
            for f in sorted_findings[:3]
        ]

        return AssessmentReport(
            findings=sorted_findings,
            summary=summary,
            top_actionable=top_actionable
        )


def create_assessment_mode(scope_files: Optional[List[str]] = None) -> AssessmentMode:
    """
    Factory function to create an assessment mode instance.

    Args:
        scope_files: Optional list of files to assess

    Returns:
        AssessmentMode instance
    """
    return AssessmentMode(scope_files=scope_files)


def run_assessment(
    raw_findings: List[Dict[str, Any]],
    agent_name: str,
    scope_files: Optional[List[str]] = None
) -> AssessmentReport:
    """
    Run assessment mode on raw findings.

    Convenience function that creates assessment mode and generates report.

    Args:
        raw_findings: Raw findings from agents
        agent_name: Name of the agent
        scope_files: Optional list of files to assess

    Returns:
        AssessmentReport with validated findings and summary
    """
    assessment = create_assessment_mode(scope_files)
    validated = assessment.assess_findings(raw_findings, agent_name)
    return assessment.generate_report(validated)
