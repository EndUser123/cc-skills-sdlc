#!/usr/bin/env python3
"""Failure pattern grouping using similarity detection."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


class FailureGrouper:
    """Group similar test failures by root cause."""

    def __init__(self, similarity_threshold: float = 0.6):
        self.similarity_threshold = similarity_threshold

    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity (0-1)."""
        return SequenceMatcher(None, s1, s2).ratio()

    def _extract_error_signature(self, error_message: str, stack_trace: str = "") -> str:
        """Extract error type/message for grouping."""
        # Common patterns to normalize
        signature = error_message.split("\n")[0].strip()

        # Remove numbers, file paths, line numbers
        import re

        signature = re.sub(r"\d+", "N", signature)
        signature = re.sub(r'File ".*?"', 'File "X"', signature)
        signature = re.sub(r"line \d+", "line N", signature)

        return signature

    def group_failures(self, failed_tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Group failed tests by similar error patterns.

        Args:
            failed_tests: List of {"test_name": str, "error": str, "trace": str}

        Returns:
            List of {"root_cause": str, "affected_tests": List[str], "count": int}
        """
        if not failed_tests:
            return []

        # Extract signatures
        signatures = []
        for test in failed_tests:
            sig = self._extract_error_signature(
                test.get("error", ""), test.get("trace", "")
            )
            signatures.append(
                {"test_name": test.get("test_name"), "signature": sig, "original_error": test.get("error", "")}
            )

        # Group by similarity
        groups: list[dict] = []

        for sig in signatures:
            # Find existing group with similar signature
            matched = False
            for group in groups:
                similarity = self._similarity(sig["signature"], group["root_cause"])
                if similarity >= self.similarity_threshold:
                    group["affected_tests"].append(sig["test_name"])
                    group["count"] += 1
                    matched = True
                    break

            # No match, create new group
            if not matched:
                groups.append(
                    {
                        "root_cause": sig["signature"],
                        "affected_tests": [sig["test_name"]],
                        "count": 1,
                        "sample_error": sig["original_error"],
                    }
                )

        # Sort by group size (largest first)
        groups.sort(key=lambda g: g["count"], reverse=True)

        return groups

    def format_grouped_failures(self, groups: list[dict[str, Any]]) -> str:
        """Format grouped failures as markdown."""
        lines = ["## Grouped Failures", ""]

        for group in groups:
            lines.append(f"### Root Cause: {group['root_cause']}")
            lines.append(f"**Affected tests:** {group['count']}")
            lines.append("")
            lines.append("**Tests:**")
            for test in group["affected_tests"]:
                lines.append(f"- {test}")
            lines.append("")
            lines.append("**Sample error:**")
            lines.append("```")
            sample = group["sample_error"]
            if len(sample) > 200:
                sample = sample[:200] + "..."
            lines.append(sample)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)
