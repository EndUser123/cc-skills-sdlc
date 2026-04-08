#!/usr/bin/env python3
"""User opt-out handler for modernization detection."""

import json
from pathlib import Path
from typing import Final


# Constants for opt-out detection
CHECKED_CHECKBOX_PATTERN: Final = "- [x]"
OPTOUT_KEYWORDS: Final = ["skip", "modernization"]
PLAN_FILENAME: Final = "plan.md"
OPTOUT_FILENAME: Final = "modernization_optout.json"
CLAUDE_DIRNAME: Final = ".claude"


class UserOptoutHandler:
    """Handle user opt-out preferences for modernization detection.

    This class provides methods to detect and persist user preferences for
    skipping modernization considerations in project plans.
    """

    def __init__(self, project_dir: Path) -> None:
        """
        Initialize the opt-out handler.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = Path(project_dir)
        self.plan_file = self.project_dir / PLAN_FILENAME
        self.optout_file = self.project_dir / CLAUDE_DIRNAME / OPTOUT_FILENAME

    def should_skip_modernization(self) -> bool:
        """
        Check if user has opted out of modernization detection.

        Looks for "- [x] Skip Modernization Considerations" in plan.md.
        The check is case-insensitive and flexible on spacing.

        Returns:
            True if user has opted out (checkbox is checked)
            False if checkbox is unchecked, missing, or plan.md doesn't exist
        """
        try:
            if not self.plan_file.exists():
                return False

            content = self.plan_file.read_text()
            return self._contains_optout_checkbox(content)

        except Exception:
            # Never raise exceptions - return False on any error
            return False

    def _contains_optout_checkbox(self, content: str) -> bool:
        """
        Check if content contains a checked opt-out checkbox.

        Args:
            content: The plan file content to search

        Returns:
            True if opt-out checkbox pattern is found, False otherwise
        """
        for line in content.splitlines():
            line_lower = line.strip().lower()
            if self._is_optout_line(line_lower):
                return True
        return False

    def _is_optout_line(self, line: str) -> bool:
        """
        Determine if a line contains the opt-out checkbox pattern.

        Args:
            line: Lowercase, stripped line from plan file

        Returns:
            True if line contains checked checkbox with opt-out keywords
        """
        has_checked_checkbox = CHECKED_CHECKBOX_PATTERN in line
        has_all_keywords = all(keyword in line for keyword in OPTOUT_KEYWORDS)
        return has_checked_checkbox and has_all_keywords

    def save_opt_out_preference(self, opt_out: bool) -> bool:
        """
        Persist opt-out preference to project-specific storage.

        Args:
            opt_out: True to opt out, False to opt in

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.optout_file.parent.mkdir(parents=True, exist_ok=True)
            preference_data = {"opt_out": opt_out}
            self.optout_file.write_text(json.dumps(preference_data, indent=2))
            return True
        except Exception:
            return False

    def has_persisted_preference(self) -> bool:
        """
        Check if user has a persisted opt-out preference.

        Returns:
            True if persisted preference exists, False otherwise
        """
        try:
            return self.optout_file.exists()
        except Exception:
            return False

    def get_persisted_preference(self) -> bool | None:
        """
        Retrieve persisted opt-out preference.

        Returns:
            True if opted out, False if opted in, None if no preference exists
        """
        try:
            if not self.optout_file.exists():
                return None

            content = self.optout_file.read_text()
            preference_data = json.loads(content)
            return preference_data.get("opt_out")
        except Exception:
            return None
