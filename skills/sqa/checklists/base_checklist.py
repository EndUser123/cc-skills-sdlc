"""Base verification checklist class.

Provides the foundation for domain-specific checklists (skills, hooks, features).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class VerificationChecklist(ABC):
    """Abstract base class for verification checklists.

    Domain-specific checklists (skill, hook, feature) extend this class
    to provide structured verification with clear pass/fail criteria.

    ChecklistResult format:
    {
        "status": "pass" | "partial" | "fail",
        "items_checked": int,
        "items_passed": int,
        "findings": List[str]
    }
    """

    # Valid status values for type checking
    VALID_STATUSES = ("pass", "partial", "fail")

    @abstractmethod
    def verify_target(self, target_path: str) -> Dict[str, Any]:
        """Verify a target against checklist criteria.

        Args:
            target_path: Path to the target file or directory

        Returns:
            ChecklistResult dict with status, counts, and findings

        Raises:
            ValueError: If target_path is invalid
        """
        pass

    def _create_result(
        self,
        status: str,
        items_checked: int,
        items_passed: int,
        findings: List[str],
    ) -> Dict[str, Any]:
        """Create a standardized ChecklistResult.

        Args:
            status: Overall verification status
            items_checked: Total items checked
            items_passed: Total items that passed
            findings: List of detailed finding messages

        Returns:
            Dictionary containing the checklist result
        """
        return {
            "status": status,
            "items_checked": items_checked,
            "items_passed": items_passed,
            "findings": findings,
        }

    def _calculate_status(
        self,
        items_checked: int,
        items_passed: int,
    ) -> str:
        """Calculate overall status from check counts.

        Args:
            items_checked: Total number of items checked
            items_passed: Total number of items that passed

        Returns:
            Status string: "pass", "partial", or "fail"
        """
        if items_passed == items_checked:
            return "pass"
        if items_passed == 0:
            return "fail"
        return "partial"

    def _file_exists(self, path: str) -> bool:
        """Check if a file or directory exists.

        Args:
            path: Path to check

        Returns:
            True if path exists, False otherwise
        """
        return Path(path).exists()

    def _read_file(self, path: str) -> str:
        """Read file contents safely.

        Args:
            path: Path to the file to read

        Returns:
            File contents as string, or empty string if read fails
        """
        try:
            return Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
