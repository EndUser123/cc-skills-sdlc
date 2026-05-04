"""
Output Formatter for Unified Code Inspection

Formats findings in multiple output formats:
- json: Machine-readable JSON with full findings
- markdown: Human-readable markdown with severity sections
- summary: Compact summary with verdict and key stats
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .impact_effort import (
    calculate_impact_effort,
    format_impact_effort,
    impact_effort_to_score,
    sort_findings_by_priority,
)
from .verdict import format_verdict_summary, synthesize_verdict

# RSN bridge imports - handle both package and direct import
try:
    from ....hooks.__lib.rsn_formatter import RSNFormatter
except ImportError:
    import sys
    from pathlib import Path

    # Direct import path: go up to .claude and import hooks.__lib.rsn_formatter
    _uci_lib_dir = Path(__file__).parent  # P:\.claude\skills\uci\lib
    _claude_dir = _uci_lib_dir.parent.parent.parent  # P:\.claude
    sys.path.insert(0, str(_claude_dir))
    from hooks.__lib.rsn_formatter import RSNFormatter


class OutputFormat(Enum):
    """Supported output formats."""

    JSON = "json"
    MARKDOWN = "markdown"
    SUMMARY = "summary"


@dataclass
class FormattedOutput:
    """Container for formatted output."""

    format: OutputFormat
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class UCIFormatter:
    """
    Formats Unified Code Inspection results in multiple formats.

    Features:
    - Enhanced schema with impact/effort matrix
    - Three-tier verdict synthesis
    - Priority-based sorting
    - Multiple output formats
    """

    def format(
        self,
        findings: List[Dict[str, Any]],
        output_format: str = "markdown",
        tests_pass: Optional[bool] = None,
        context: Optional[Dict[str, Any]] = None,
        use_gto_format: bool = False,
        use_rsn_format: bool = True,
    ) -> FormattedOutput:
        """
        Format findings according to specified format.

        Args:
            findings: List of finding dicts
            output_format: One of "json", "markdown", "summary"
            tests_pass: Whether tests pass (for verdict calculation)
            context: Additional context (git scope, mode, etc.)
            use_gto_format: If True, use GTO-style domain-grouped Recommended Next Steps
            use_rsn_format: If True, use RSN formatter for unified output

        Returns:
            FormattedOutput with content and metadata
        """
        context = context or {}
        format_enum = OutputFormat(output_format.lower())

        # Enhance findings with impact/effort
        enhanced_findings = self._enhance_findings(findings)

        # Sort by priority
        sorted_findings = sort_findings_by_priority(enhanced_findings)

        # Generate verdict
        verdict_dict = synthesize_verdict(sorted_findings, tests_pass)

        if format_enum == OutputFormat.JSON:
            content = self._format_json(sorted_findings, verdict_dict, context)
        elif format_enum == OutputFormat.MARKDOWN:
            content = self._format_markdown(
                sorted_findings,
                verdict_dict,
                context,
                use_gto_format=use_gto_format,
                use_rsn_format=use_rsn_format,
            )
        elif format_enum == OutputFormat.SUMMARY:
            content = self._format_summary(sorted_findings, verdict_dict, context)
        else:
            content = self._format_markdown(
                sorted_findings,
                verdict_dict,
                context,
                use_gto_format=use_gto_format,
                use_rsn_format=use_rsn_format,
            )

        return FormattedOutput(
            format=format_enum,
            content=content,
            metadata={
                "finding_count": len(sorted_findings),
                "verdict": verdict_dict["verdict"],
                "tests_pass": tests_pass,
            },
        )

    def _enhance_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add impact/effort levels and priority score to findings."""
        enhanced = []

        for finding in findings:
            impact, effort = calculate_impact_effort(finding)
            priority_score = impact_effort_to_score(impact, effort)

            enhanced_finding = {
                **finding,
                "impact": format_impact_effort(impact, effort),
                "priority_score": priority_score,
            }
            enhanced.append(enhanced_finding)

        return enhanced

    def _format_json(
        self,
        findings: List[Dict[str, Any]],
        verdict_dict: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Format findings as JSON."""
        output = {
            "verdict": verdict_dict,
            "findings": findings,
            "context": context,
            "metadata": {
                "total_findings": len(findings),
                "format_version": "1.0",
            },
        }
        return json.dumps(output, indent=2)

    def _format_markdown(
        self,
        findings: List[Dict[str, Any]],
        verdict_dict: Dict[str, Any],
        context: Dict[str, Any],
        use_gto_format: bool = False,
        use_rsn_format: bool = True,
    ) -> str:
        """Format findings as human-readable markdown."""
        lines = []

        # Header with verdict
        lines.append("# Unified Code Inspection Results")
        lines.append("")

        # Verdict summary
        lines.append(format_verdict_summary(verdict_dict))
        lines.append("")

        # Context info
        if context:
            lines.append("## Review Context")
            if "mode" in context:
                lines.append(f"- **Mode**: {context['mode']}")
            if "target_scope" in context:
                lines.append(f"- **Scope**: {context['target_scope']}")
            if "agents" in context:
                lines.append(f"- **Agents**: {', '.join(context['agents'])}")
            lines.append("")

        # Findings by severity
        lines.append("## Findings")
        lines.append("")

        # Group findings by severity
        by_severity = self._group_by_severity(findings)

        # Display findings (blockers first)
        for severity_level in ["blocker", "high", "medium", "low"]:
            severity_findings = by_severity.get(severity_level, [])
            if not severity_findings:
                continue

            # Section header
            emoji = {"blocker": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            lines.append(f"### {emoji.get(severity_level, '')} {severity_level.upper()} Priority")
            lines.append("")

            for finding in severity_findings[:20]:  # Limit to 20 per section
                lines.append(self._format_finding_markdown(finding))
                lines.append("")

            if len(severity_findings) > 20:
                lines.append(f"*... and {len(severity_findings) - 20} more*")
                lines.append("")

        # RSN-style Recommended Next Steps (unified format)
        if use_rsn_format:
            lines.append(format_rsn_from_findings(findings))
        elif use_gto_format:
            lines.append(self.format_gto_next_steps(findings))

        return "\n".join(lines)

    def format_gto_next_steps(
        self,
        findings: List[Dict[str, Any]],
    ) -> str:
        """
        Format findings as GTO-style Recommended Next Steps grouped by technical domain.

        Args:
            findings: List of finding dicts

        Returns:
            GTO-formatted Recommended Next Steps
        """
        lines = []
        lines.extend(["", "**Recommended Next Steps**", ""])

        # Group findings by technical domain
        by_domain = self._group_by_domain(findings)

        # Domain order for consistent presentation
        domain_order = [
            "Input Validation",
            "Cryptography",
            "Concurrency",
            "File Operations",
            "Process Safety",
            "Other",
        ]

        step_num = 1
        for domain in domain_order:
            domain_findings = by_domain.get(domain, [])
            if not domain_findings:
                continue

            # Domain header with finding count
            finding_ids = ", ".join([f.get("id", "?") for f in domain_findings])
            lines.append(
                f"{step_num} ({domain}) - Fix {len(domain_findings)} issue(s) [{finding_ids}]"
            )
            lines.append("")

            # Actions for each finding in this domain
            action_letter = ord("a")
            for finding in domain_findings:
                finding_id = finding.get("id", "UNKNOWN")
                location = finding.get("location", "")
                recommendation = finding.get("recommendation", "")

                # Format action
                lines.append(
                    f"  {chr(action_letter)}: Fix {finding_id} → Manual check - {recommendation[:80]}"
                )
                lines.append(f"       Location: {location}")
                lines.append("")

                action_letter += 1
                if action_letter > ord("z"):  # Reset after 'z'
                    action_letter = ord("a")

            step_num += 1

        lines.extend(["0 - Do ALL Recommended Next Steps", ""])
        return "\n".join(lines)

    def _format_summary(
        self,
        findings: List[Dict[str, Any]],
        verdict_dict: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Format findings as compact summary."""
        lines = []

        # Verdict (one-line)
        verdict_emoji = {
            "Ready to Merge": "✅",
            "Needs Attention": "⚠️",
            "Needs Work": "❌",
        }
        emoji = verdict_emoji.get(verdict_dict["verdict"], "")
        lines.append(f"{emoji} {verdict_dict['verdict']}: {verdict_dict['reason']}")
        lines.append("")

        # Quick stats
        blockers = verdict_dict["blockers"]
        high = verdict_dict["high"]
        medium = verdict_dict["medium"]
        low = verdict_dict["low"]

        if blockers > 0:
            lines.append(f"🔴 {blockers} blocker(s) must be fixed")
        if high > 0:
            lines.append(f"🟠 {high} high priority issue(s)")
        if medium > 0:
            lines.append(f"🟡 {medium} medium priority issue(s)")
        if low > 0:
            lines.append(f"🟢 {low} low priority issue(s)")

        lines.append("")

        # Quick wins (high impact, low effort)
        quick_wins = [f for f in findings if "LOW Effort" in f.get("impact", "")]
        if quick_wins:
            lines.append(f"**Quick wins** ({len(quick_wins)} items):")
            for finding in quick_wins[:5]:
                problem = finding.get("problem", "Unknown issue")[:60]
                lines.append(f"  • {problem}...")
            if len(quick_wins) > 5:
                lines.append(f"  ... and {len(quick_wins) - 5} more")
            lines.append("")

        # Top 3 recommendations
        lines.append("**Top 3 recommendations:**")
        for i, finding in enumerate(findings[:3], 1):
            problem = finding.get("problem", "Unknown")[:50]
            recommendation = finding.get("recommendation", "See details")[:50]
            lines.append(f"{i}. {problem}")
            lines.append(f"   → {recommendation}")
            lines.append("")

        return "\n".join(lines)

    def _format_finding_markdown(self, finding: Dict[str, Any]) -> str:
        """Format a single finding as markdown."""
        lines = []

        # Header with ID and severity
        finding_id = finding.get("id", "UNKNOWN")
        severity = finding.get("severity", "unknown").upper()
        location = finding.get("location", "")

        header = f"#### {finding_id}"
        if location:
            header += f" · {location}"
        header += f" · {severity}"
        lines.append(header)
        lines.append("")

        # Problem
        problem = finding.get("problem", "No description")
        lines.append(f"**Problem**: {problem}")
        lines.append("")

        # Impact (if available)
        if "impact" in finding:
            lines.append(f"**Impact**: {finding['impact']}")
            lines.append("")

        # Recommendation
        recommendation = finding.get("recommendation", "No recommendation provided")
        lines.append(f"**Recommendation**: {recommendation}")
        lines.append("")

        return "\n".join(lines)

    def _group_by_severity(self, findings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group findings by severity level."""
        groups: Dict[str, List[Dict[str, Any]]] = {
            "blocker": [],
            "high": [],
            "medium": [],
            "low": [],
        }

        for finding in findings:
            severity = finding.get("severity", "").lower()
            if "blocker" in severity:
                groups["blocker"].append(finding)
            elif "high" in severity or "critical" in severity:
                groups["high"].append(finding)
            elif "medium" in severity or "med" in severity:
                groups["medium"].append(finding)
            elif "low" in severity:
                groups["low"].append(finding)
            else:
                groups["low"].append(finding)

        return groups

    def _get_technical_domain(self, finding: Dict[str, Any]) -> str:
        """Determine technical domain from finding characteristics."""
        # Check evidence for domain-specific patterns
        evidence = finding.get("evidence", {})
        title = finding.get("title", "").lower()
        file_path = evidence.get("file_path", "").lower()

        # Domain classification patterns
        domain_patterns = {
            "Input Validation": [
                "path traversal",
                "injection",
                "validation",
                "sanitize",
                "normalize",
                "user input",
                "terminal_id",
            ],
            "Cryptography": [
                "encryption",
                "key",
                "password",
                "cipher",
                "acl",
                "permission",
                "fernet",
                "pbkdf2",
            ],
            "Concurrency": [
                "race condition",
                "lock",
                "atomic",
                "toctou",
                "concurrent",
                "multi-terminal",
            ],
            "File Operations": ["temp file", "atomic", "write", "exposure", "permissions"],
            "Process Safety": [
                "command injection",
                "subprocess",
                "git command",
                "shell",
                "execution",
            ],
        }

        # Check patterns in title and file_path
        for domain, patterns in domain_patterns.items():
            for pattern in patterns:
                if pattern in title or pattern in file_path:
                    return domain

        return "Other"

    def _group_by_domain(self, findings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group findings by technical domain."""
        groups: Dict[str, List[Dict[str, Any]]] = {}

        for finding in findings:
            domain = self._get_technical_domain(finding)
            if domain not in groups:
                groups[domain] = []
            groups[domain].append(finding)

        return groups

    def save_output(
        self,
        formatted: FormattedOutput,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Save formatted output to file.

        Args:
            formatted: FormattedOutput object
            output_path: Optional path (auto-generates if not provided)

        Returns:
            Path to saved file
        """
        if output_path is None:
            # Auto-generate path based on format and timestamp
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            ext = "json" if formatted.format == OutputFormat.JSON else "md"
            output_path = Path(".claude/.state/uci") / f"review-{timestamp}.{ext}"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(formatted.content, encoding="utf-8")

        return output_path


# UCI severity to RSN severity mapping
UCI_SEVERITY_TO_RSN: dict[str, str] = {
    "blocker": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}

# UCI technical domain to RSN domain mapping
UCI_DOMAIN_TO_RSN_DOMAIN: dict[str, str] = {
    "Input Validation": "input_validation",
    "Cryptography": "security",
    "Concurrency": "concurrency",
    "File Operations": "file_ops",
    "Process Safety": "process_safety",
    "Other": "other",
}

# UCI-specific section definitions for RSN formatter
# Maps RSN domain strings to (section_name, section_key)
UCI_SECTION_DEFINITIONS: dict[str, tuple[str, str]] = {
    "input_validation": ("Input Validation Issues", "input_validation"),
    "security": ("Security & Cryptography Issues", "security"),
    "concurrency": ("Concurrency Issues", "concurrency"),
    "file_ops": ("File Operation Issues", "file_ops"),
    "process_safety": ("Process Safety Issues", "process_safety"),
    "other": ("Other Issues", "other"),
}


def format_rsn_from_findings(
    findings: list[dict[str, Any]],
    intent_summary: str = "",
) -> str:
    """
    Format UCI findings using the shared RSN formatter.

    This is a bridge function that transforms UCI finding dictionaries into
    RSN format and delegates to the shared RSNFormatter.

    Args:
        findings: List of UCI finding dicts with keys:
            - id: finding identifier
            - severity: blocker/high/medium/low
            - problem: issue description
            - location: file path (optional)
            - recommendation: what to do (optional)
        intent_summary: One-line description of what was analyzed

    Returns:
        Formatted RSN text string
    """
    # Transform UCI findings to RSN findings
    rsn_findings = []
    for finding in findings:
        # Map UCI severity to RSN severity
        uci_severity = finding.get("severity", "low")
        rs_severity = UCI_SEVERITY_TO_RSN.get(uci_severity.lower(), "LOW")

        # Build file_ref from location
        file_ref = finding.get("location", "")

        # Get recommendation or problem as message
        message = finding.get("recommendation") or finding.get("problem", "")

        # Determine domain from _get_technical_domain logic
        # We'll use the domain field if present, otherwise default
        domain = finding.get("domain", "other").lower()
        if not finding.get("domain"):
            # Fallback: try to extract domain from evidence patterns
            evidence = finding.get("evidence", {})
            title = finding.get("title", "").lower()
            file_path = evidence.get("file_path", "").lower()
            combined = f"{title} {file_path}"

            if any(
                p in combined for p in ["path traversal", "injection", "validation", "sanitize"]
            ):
                domain = "input_validation"
            elif any(p in combined for p in ["encryption", "key", "password", "cipher", "acl"]):
                domain = "security"
            elif any(p in combined for p in ["race condition", "lock", "atomic", "toctou"]):
                domain = "concurrency"
            elif any(p in combined for p in ["temp file", "atomic", "write"]):
                domain = "file_ops"
            elif any(p in combined for p in ["command injection", "subprocess", "git command"]):
                domain = "process_safety"
            else:
                domain = "other"

        rsn_findings.append(
            {
                "id": finding.get("id", "UNKNOWN"),
                "severity": rs_severity,
                "message": message,
                "file_ref": file_ref,
                "action_type": "Manual",
                "effort_minutes": 5,  # Default effort
                "domain": domain,
            }
        )

    # Use shared RSN formatter with UCI-specific section definitions
    formatter = RSNFormatter(section_definitions=UCI_SECTION_DEFINITIONS)
    result = formatter.create_result(intent_summary=intent_summary, findings=rsn_findings)
    formatter.sort_all_sections(result)
    return formatter.render_text(result)
