"""
Template validation module with fail-fast gate.

Ordered check chain: file_exists → duplicates → permissions.
Early return on first failure with metadata["stage"].

Phase 2 of ADR-20260321: Fail-Fast Validation Gate
"""

from __future__ import annotations

import re
import logging
from pathlib import Path

from results import ArchResult

__all__ = [
    "TemplateValidator",
    "DUPLICATE_OVERLAP_THRESHOLD",
    "HIGH_OVERLAP_THRESHOLD",
    "DUPLICATE_CHECK_SECTIONS",
    "TEMPLATE_NAMES",
]

# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Threshold for duplicate detection (percentage overlap)
DUPLICATE_OVERLAP_THRESHOLD = 50.0

# Threshold for high overlap that causes validation failure
HIGH_OVERLAP_THRESHOLD = 70.0

# Sections to check for duplicate logic between templates
# NOTE: "Stage 0" excluded - it's boilerplate template header (From the user query, identify:)
# shared across ALL templates, not actual duplicate logic to detect.
DUPLICATE_CHECK_SECTIONS = [
    "Stage 0.5",
    "Domain Resource Inclusion",
    "IMPROVE_SYSTEM",
    "CKS.db",
]

# Template definitions
TEMPLATE_NAMES = {
    "fast": "fast.md",
    "deep": "deep.md",
    "cli": "cli.md",
    "python": "python.md",
    "data-pipeline": "data-pipeline.md",
    "precedent": "precedent.md",
}

# =============================================================================
# TemplateValidator
# =============================================================================


class TemplateValidator:
    """
    Fail-fast template validator with ordered check chain.

    Validates templates via three-stage pipeline:
    1. file_exists - Verify template files are present
    2. duplicates - Check for duplicate logic between templates
    3. permissions - Verify template files are readable

    Each stage runs in order with early return on first failure.
    metadata["stage"] indicates which gate failed.

    Examples:
        >>> validator = TemplateValidator()
        >>> result = validator.validate_templates(["fast", "deep"])
        >>> result.is_success
        True
        >>> result.metadata["stage"]
        'all'
    """

    def __init__(self, resources_dir: Path | None = None) -> None:
        """
        Initialize validator with optional custom resources directory.

        Args:
            resources_dir: Path to template resources directory.
                          Defaults to skill/resources relative to this module.
        """
        if resources_dir is None:
            resources_dir = Path(__file__).parent / "resources"
        self.resources_dir = resources_dir

    # -------------------------------------------------------------------------
    # Stage 1: File Existence
    # -------------------------------------------------------------------------

    def _check_file_exists(self, template_names: list[str]) -> ArchResult[list[str]]:
        """
        Stage 1: Verify all template files exist.

        Args:
            template_names: List of template names to check.

        Returns:
            ArchResult with value=list of valid template paths on success,
            or error with missing_templates in metadata.
        """
        missing: list[str] = []
        valid_paths: list[str] = []

        for name in template_names:
            template_path = self.resources_dir / f"{name}.md"
            if template_path.exists():
                valid_paths.append(str(template_path))
            else:
                missing.append(name)
                logger.error(f"Template file not found: {template_path}")

        if missing:
            return ArchResult(
                is_success=False,
                error="file_exists_failed",
                metadata={
                    "stage": "file_exists",
                    "missing_templates": missing,
                },
            )

        return ArchResult(
            is_success=True,
            value=valid_paths,
            metadata={"stage": "file_exists"},
        )

    # -------------------------------------------------------------------------
    # Stage 2: Duplicate Detection
    # -------------------------------------------------------------------------

    def _extract_section_content(self, content: str, section_name: str) -> str | None:
        """
        Extract section content from markdown.

        Args:
            content: Full markdown content.
            section_name: Name of section to extract.

        Returns:
            Section content without heading, or None if not found.
        """
        pattern = rf"(?:^#+\s*{re.escape(section_name)}.*?$)(.*?)(?=^#+\s|\Z)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        return match.group(1).strip() if match else None

    def _calculate_line_overlap(self, text1: str, text2: str) -> float:
        """
        Calculate percentage of line overlap between two text blocks.

        Args:
            text1: First text block.
            text2: Second text block.

        Returns:
            Overlap percentage (0-100).
        """
        lines1 = set(text1.split("\n"))
        lines2 = set(text2.split("\n"))

        if not lines1:
            return 0.0

        shared_lines = lines1 & lines2
        max_unique_lines = max(len(lines1), len(lines2), 1)

        return len(shared_lines) / max_unique_lines * 100

    def _check_duplicates(self, template_names: list[str]) -> ArchResult[list[str]]:
        """
        Stage 2: Check for duplicate logic between template pairs.

        Only checks pairs that both exist. Early returns on first
        high-overlap duplicate found.

        Args:
            template_names: List of template names to check.

        Returns:
            ArchResult with value=list of valid template paths on success,
            or error with duplicate info in metadata.
        """
        # Load all template contents
        contents: dict[str, str] = {}
        for name in template_names:
            template_path = self.resources_dir / f"{name}.md"
            if template_path.exists():
                try:
                    contents[name] = template_path.read_text(encoding="utf-8")
                except OSError as e:
                    logger.warning(f"Could not read {name}: {e}")
                    continue

        # Check for duplicate sections between template pairs
        template_list = list(contents.keys())
        for i, name1 in enumerate(template_list):
            for name2 in template_list[i + 1 :]:
                content1 = contents[name1]
                content2 = contents[name2]

                for section_name in DUPLICATE_CHECK_SECTIONS:
                    if section_name not in content1 or section_name not in content2:
                        continue

                    section1 = self._extract_section_content(content1, section_name)
                    section2 = self._extract_section_content(content2, section_name)

                    if section1 is None or section2 is None:
                        continue

                    overlap = self._calculate_line_overlap(section1, section2)

                    if overlap > HIGH_OVERLAP_THRESHOLD:
                        logger.error(
                            f"High duplicate overlap in '{section_name}' "
                            f"between {name1} and {name2}: {overlap:.1f}%"
                        )
                        return ArchResult(
                            is_success=False,
                            error="duplicate_logic_high_overlap",
                            metadata={
                                "stage": "duplicates",
                                "section": section_name,
                                "template1": name1,
                                "template2": name2,
                                "overlap_percent": overlap,
                            },
                        )

        return ArchResult(
            is_success=True,
            value=template_names,
            metadata={"stage": "duplicates"},
        )

    # -------------------------------------------------------------------------
    # Stage 3: Permissions
    # -------------------------------------------------------------------------

    def _check_permissions(self, template_names: list[str]) -> ArchResult[list[str]]:
        """
        Stage 3: Verify template files are readable.

        Args:
            template_names: List of template names to check.

        Returns:
            ArchResult with value=list of valid template paths on success,
            or error with unreadable_templates in metadata.
        """
        unreadable: list[str] = []
        valid_paths: list[str] = []

        for name in template_names:
            template_path = self.resources_dir / f"{name}.md"
            if not template_path.exists():
                continue

            try:
                with open(template_path, encoding="utf-8") as f:
                    content = f.read()
                if not content:
                    unreadable.append(name)
                    logger.error(f"Template file is empty: {template_path}")
                else:
                    valid_paths.append(str(template_path))
            except PermissionError:
                unreadable.append(name)
                logger.error(f"Cannot read template file (permission denied): {template_path}")
            except UnicodeDecodeError:
                unreadable.append(name)
                logger.error(f"Cannot read template file (encoding issue): {template_path}")
            except OSError as e:
                unreadable.append(name)
                logger.error(f"Cannot read template file: {template_path}: {e}")

        if unreadable:
            return ArchResult(
                is_success=False,
                error="permissions_failed",
                metadata={
                    "stage": "permissions",
                    "unreadable_templates": unreadable,
                },
            )

        return ArchResult(
            is_success=True,
            value=valid_paths,
            metadata={"stage": "permissions"},
        )

    # -------------------------------------------------------------------------
    # Main Entry Point
    # -------------------------------------------------------------------------

    def validate_templates(self, template_names: list[str] | None = None) -> ArchResult[list[str]]:
        """
        Run validation pipeline on templates with fail-fast gate.

        Validates via ordered check chain:
        1. file_exists - All template files must exist
        2. duplicates - No high-overlap duplicate sections
        3. permissions - All template files must be readable

        Early returns on first failure. metadata["stage"] indicates
        which gate failed.

        Args:
            template_names: List of template names to validate.
                           Defaults to all known templates.

        Returns:
            ArchResult containing validated template paths on success,
            or error with metadata indicating which stage failed.

        Examples:
            >>> validator = TemplateValidator()
            >>> result = validator.validate_templates(["fast", "deep"])
            >>> result.is_success
            True
            >>> result.metadata["stage"]
            'all'
        """
        if template_names is None:
            template_names = list(TEMPLATE_NAMES.keys())

        # Stage 1: file_exists
        result = self._check_file_exists(template_names)
        if not result.is_success:
            logger.debug(f"Fail-fast at stage 1 (file_exists): {result.error}")
            return result

        # Stage 2: duplicates
        result = self._check_duplicates(template_names)
        if not result.is_success:
            logger.debug(f"Fail-fast at stage 2 (duplicates): {result.error}")
            return result

        # Stage 3: permissions
        result = self._check_permissions(template_names)
        if not result.is_success:
            logger.debug(f"Fail-fast at stage 3 (permissions): {result.error}")
            return result

        # All stages passed
        return ArchResult(
            is_success=True,
            value=template_names,
            metadata={"stage": "all"},
        )


# =============================================================================
# Standalone Function Wrapper (Phase 4: Function/Class Duality)
# =============================================================================


def validate_templates(
    template_names: list[str] | None = None,
) -> ArchResult[list[str]]:
    """
    Standalone wrapper for TemplateValidator.validate_templates().

    Provided for backward compatibility and Phase 4 function/class duality.

    Args:
        template_names: List of template names to validate.

    Returns:
        ArchResult containing validated template paths on success.
    """
    validator = TemplateValidator()
    return validator.validate_templates(template_names)
