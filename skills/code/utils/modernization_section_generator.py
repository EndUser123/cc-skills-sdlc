#!/usr/bin/env python3
"""Modernization section generator for plan.md.

Generates "Modernization Considerations" section with detected divergences,
recommendations, and user choice options.
"""

from typing import Any, Dict, List


class ModernizationSectionGenerator:
    """Generates modernization considerations section for plan.md."""

    # Priority ordering (lower number = higher priority)
    PRIORITY_ORDER: Dict[str, int] = {"P0": 0, "P1": 1, "P2": 2}

    # Fallback priority for unknown values
    DEFAULT_PRIORITY_VALUE: int = 99

    # Minimum section content length
    MIN_SECTION_LENGTH: int = 50

    def generate_section(self, findings: Dict[str, List[Dict[str, Any]]]) -> str:
        """Generate markdown section for modernization considerations.

        Args:
            findings: Dict with 'divergences' key containing list of divergence dicts.
                     Each divergence has: library, current_version, latest_version,
                     priority, breaking_changes, optional context7_url

        Returns:
            str: Formatted markdown section with 3 subsections

        """
        divergences = findings.get("divergences", [])

        if not divergences:
            return self._generate_empty_section()

        # Sort by priority (P0 first, then P1, then P2)
        sorted_divergences = sorted(
            divergences,
            key=lambda d: self.PRIORITY_ORDER.get(
                d.get("priority", "P2"),
                self.DEFAULT_PRIORITY_VALUE,
            ),
        )

        lines = []
        lines.append("## Modernization Considerations")
        lines.append("")
        lines.append(self._generate_detected_divergences(sorted_divergences))
        lines.append("")
        lines.append(self._generate_recommendation(sorted_divergences))
        lines.append("")
        lines.append(self._generate_user_choice())

        return "\n".join(lines)

    def _generate_empty_section(self) -> str:
        """Generate section for empty findings.

        Returns:
            str: Empty section with message indicating no divergences

        """
        lines = []
        lines.append("## Modernization Considerations")
        lines.append("")
        lines.append(
            "No divergences detected. The codebase is consistent "
            "with modern patterns.",
        )
        return "\n".join(lines)

    def _generate_detected_divergences(self, divergences: List[Dict[str, Any]]) -> str:
        """Generate Detected Divergences subsection.

        Args:
            divergences: List of divergence dictionaries sorted by priority

        Returns:
            str: Formatted markdown subsection with divergence details

        """
        lines = []
        lines.append("### Detected Divergences")
        lines.append("")

        for div in divergences:
            library = div.get("library", "unknown")
            current = div.get("current_version", "unknown")
            latest = div.get("latest_version", "unknown")
            priority = div.get("priority", "P2")
            breaking = div.get("breaking_changes", [])
            context7_url = div.get("context7_url")

            lines.append(f"- **{library}**: {current} → {latest} (**{priority}**)")

            if breaking:
                lines.extend(f"  - {change}" for change in breaking)

            if context7_url:
                lines.append(f"  - Migration guide: [Context7]({context7_url})")

            lines.append("")

        return "\n".join(lines)

    def _generate_recommendation(self, divergences: List[Dict[str, Any]]) -> str:
        """Generate Recommendation subsection.

        Args:
            divergences: List of divergence dictionaries sorted by priority

        Returns:
            str: Formatted recommendation based on priority and security issues

        """
        lines = []
        lines.append("### Recommendation")
        lines.append("")

        # Check if any P0 security issues
        has_p0_security = any(
            div.get("priority") == "P0" and
            any("security" in str(c).lower() or "cve" in str(c).lower()
                for c in div.get("breaking_changes", []))
            for div in divergences
        )

        if has_p0_security:
            lines.append(
                "**Modernize to latest patterns** - P0 security "
                "vulnerabilities detected.",
            )
        else:
            lines.append(
                "**Use existing codebase patterns** - Maintain consistency "
                "with current implementation.",
            )

        return "\n".join(lines)

    def _generate_user_choice(self) -> str:
        """Generate Your Choice subsection with checkboxes.

        Returns:
            str: Formatted subsection with user choice checkboxes

        """
        lines = []
        lines.append("### Your Choice")
        lines.append("")
        lines.append("- [ ] Use existing codebase patterns (consistent, stable)")
        lines.append(
            "- [ ] Use modern patterns (latest features, "
            "potential migration needed)",
        )

        return "\n".join(lines)
