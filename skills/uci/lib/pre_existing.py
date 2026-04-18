"""
Pre-Existing Issue Detection for Unified Code Inspection

Distinguishes between issues in user's diff vs pre-existing problems.
Helps users focus on "must fix before merge" vs "pre-existing issue" separation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PreExistingResult:
    """Result of pre-existing issue detection."""
    new_issues: List[Dict[str, Any]]
    pre_existing_issues: List[Dict[str, Any]]
    diff_files: Set[str] = field(default_factory=set)
    stats: Dict[str, int] = field(default_factory=dict)


class PreExistingDetector:
    """
    Detects whether findings are new issues or pre-existing problems.

    Uses git diff to determine if a finding's location is within
    the user's changes (new issue) or outside the diff (pre-existing).

    This helps users focus on:
    - "MUST FIX BEFORE MERGE" - issues in their code
    - "PRE-EXISTING ISSUES" - problems that existed before their changes
    """

    def __init__(self, base_branch: str = "main"):
        """
        Initialize pre-existing issue detector.

        Args:
            base_branch: Base branch for diff comparison (default: "main")
        """
        self.base_branch = base_branch

    def detect_pre_existing(
        self,
        findings: List[Dict[str, Any]],
        diff_output: str | None = None
    ) -> PreExistingResult:
        """
        Distinguish new issues from pre-existing problems.

        Args:
            findings: List of findings with location information
            diff_output: Git diff output (optional, will generate if not provided)

        Returns:
            PreExistingResult with new_issues, pre_existing_issues, and stats
        """
        if diff_output is None:
            # Try to get diff from git
            diff_output = self._get_git_diff()

        # Parse diff to get changed files and line ranges
        changed_files, changed_ranges = self._parse_diff(diff_output)

        new_issues = []
        pre_existing = []

        for finding in findings:
            location = finding.get("location", "")
            if not location:
                # No location info - can't determine, mark as new conservatively
                finding["_in_diff"] = True
                finding["_pre_existing"] = False
                new_issues.append(finding)
                continue

            file_path = self._extract_file_path(location)

            if file_path in changed_files:
                # Check if specific line is in the diff
                line_number = finding.get("line_number", 0)
                in_diff = self._is_line_in_diff(
                    line_number,
                    changed_ranges.get(file_path, set())
                )

                finding["_in_diff"] = in_diff
                finding["_pre_existing"] = not in_diff

                if in_diff:
                    new_issues.append(finding)
                else:
                    finding["_status"] = "PRE-EXISTING"
                    finding["_note"] = "This issue existed before your changes"
                    pre_existing.append(finding)
            else:
                # File not in diff = pre-existing issue
                finding["_in_diff"] = False
                finding["_pre_existing"] = True
                finding["_status"] = "PRE-EXISTING"
                finding["_note"] = "This file was not modified in your changes"
                pre_existing.append(finding)

        stats = {
            "total_findings": len(findings),
            "new_issues": len(new_issues),
            "pre_existing_issues": len(pre_existing),
            "changed_files": len(changed_files),
        }

        return PreExistingResult(
            new_issues=new_issues,
            pre_existing_issues=pre_existing,
            diff_files=changed_files,
            stats=stats
        )

    def _get_git_diff(self) -> str:
        """
        Get git diff output for the current working tree.

        Returns:
            Git diff output as string
        """
        import subprocess

        try:
            # Try diff against base branch first
            result = subprocess.run(
                ["git", "diff", f"{self.base_branch}...HEAD"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout

            # Fallback to staged changes
            result = subprocess.run(
                ["git", "diff", "--staged"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout

            # Fallback to unstaged changes
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout if result.returncode == 0 else ""

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to get git diff: {e}")
            return ""

    def _parse_diff(self, diff_output: str) -> Tuple[Set[str], Dict[str, Set[int]]]:
        """
        Parse git diff to extract changed files and line numbers.

        Args:
            diff_output: Git diff output

        Returns:
            Tuple of (set of changed files, dict of file -> changed line numbers)
        """
        changed_files = set()
        changed_ranges: Dict[str, Set[int]] = {}

        if not diff_output:
            return changed_files, changed_ranges

        current_file = None
        current_line_start = None
        current_line_count = 0

        for line in diff_output.split("\n"):
            if line.startswith("+++ b/") or line.startswith("--- a/"):
                # Extract file path from diff header
                parts = line.split()
                if len(parts) >= 2:
                    file_path = parts[1].lstrip("ab/")
                    # Remove leading "b/" if present
                    file_path = file_path.lstrip("b/")
                    changed_files.add(file_path)
                    current_file = file_path
                    current_line_start = None
                    current_line_count = 0

            elif current_file and line.startswith("@@"):
                # Parse hunk header: @@ -start,count +start,count @@
                # Example: @@ -10,5 +10,7 @@ means new lines start at 10, 7 lines
                try:
                    parts = line.split()
                    if len(parts) >= 2:
                        hunk_info = parts[1]  # +start,count
                        if hunk_info.startswith("+"):
                            range_info = hunk_info[1:]
                            if "," in range_info:
                                start, count = range_info.split(",")
                                line_start = int(start)
                                line_count = int(count)
                            else:
                                line_start = int(range_info)
                                line_count = 1

                            current_line_start = line_start
                            current_line_count = line_count

                            # Add line range to changed lines
                            if current_file not in changed_ranges:
                                changed_ranges[current_file] = set()

                            for i in range(line_count):
                                changed_ranges[current_file].add(line_start + i)

                except (ValueError, IndexError):
                    logger.debug(f"Failed to parse hunk header: {line}")

        return changed_files, changed_ranges

    def _extract_file_path(self, location: str) -> str:
        """
        Extract file path from location string.

        Args:
            location: Location string (e.g., "src/auth.py:45")

        Returns:
            File path only
        """
        if ":" in location:
            return location.split(":")[0]
        return location

    def _is_line_in_diff(self, line_number: int, changed_lines: Set[int]) -> bool:
        """
        Check if a line number is within the changed lines.

        Args:
            line_number: Line number to check
            changed_lines: Set of changed line numbers

        Returns:
            True if line is in the diff
        """
        if line_number == 0:
            # No specific line number - can't determine
            # Conservatively mark as new issue
            return True

        return line_number in changed_lines

    def format_pre_existing_report(self, result: PreExistingResult) -> str:
        """
        Format pre-existing issue detection result as a report.

        Args:
            result: PreExistingResult from detect_pre_existing

        Returns:
            Formatted report string
        """
        lines = [
            "## Pre-Existing Issue Detection",
            "",
            f"**Total Findings**: {result.stats['total_findings']}",
            f"**New Issues** (MUST FIX BEFORE MERGE): {result.stats['new_issues']}",
            f"**Pre-Existing Issues**: {result.stats['pre_existing_issues']}",
            f"**Files Changed**: {result.stats['changed_files']}",
            "",
        ]

        if result.new_issues:
            lines.extend([
                "### New Issues (Must Fix)",
                ""
            ])
            for issue in result.new_issues[:10]:  # Show first 10
                lines.append(f"- **{issue.get('id', 'UNKNOWN')}**: {issue.get('location', '')}")
                lines.append(f"  {issue.get('problem', 'No description')[:80]}")

        if result.pre_existing_issues:
            lines.extend([
                "",
                "### Pre-Existing Issues (Not Your Fault)",
                ""
            ])
            for issue in result.pre_existing_issues[:10]:  # Show first 10
                lines.append(f"- **{issue.get('id', 'UNKNOWN')}**: {issue.get('location', '')}")
                lines.append(f"  {issue.get('problem', 'No description')[:80]}")

        return "\n".join(lines)


def detect_pre_existing_issues(
    findings: List[Dict[str, Any]],
    diff_output: str | None = None,
    base_branch: str = "main"
) -> PreExistingResult:
    """
    Distinguish new issues from pre-existing problems.

    Convenience function that creates detector and runs detection.

    Args:
        findings: List of findings with location information
        diff_output: Git diff output (optional)
        base_branch: Base branch for diff comparison

    Returns:
        PreExistingResult with new_issues, pre_existing_issues, and stats
    """
    detector = PreExistingDetector(base_branch=base_branch)
    return detector.detect_pre_existing(findings, diff_output)
