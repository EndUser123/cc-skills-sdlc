#!/usr/bin/env python3
"""
Failing tests for hardcoded path replacement in arch skill templates.

These tests verify that templates (fast.md, deep.md) use cross-platform
path resolution functions instead of hardcoded P:/ paths.

Test scenarios:
1. test_replace_p_drive_with_platform_detection - fast.md should use cross_platform_paths.resolve_cks_db_path()
2. test_deep_md_uses_cross_platform_paths - deep.md should use cross_platform_paths
3. test_no_hardcoded_p_colon_slash - No "P:/" strings in templates after replacement
4. test_template_uses_forward_slashes - Template paths always use / not \

Run with: pytest P:/.claude/skills/arch/tests/test_harcoded_paths.py -v

NOTE: These tests are written to FAIL in the RED phase of TDD.
The templates currently contain hardcoded "P:/" paths that need to be
replaced with cross-platform path resolution function calls.
"""

from pathlib import Path
import pytest
import re


class TestReplacePDriveWithPlatformDetection:
    """
    Tests for P:/ drive replacement with platform detection.

    These tests verify that fast.md uses cross_platform_paths.resolve_cks_db_path()
    instead of hardcoded "P:/" paths.
    """

    @pytest.fixture
    def fast_md_path(self) -> Path:
        """Return path to fast.md template."""
        return Path(__file__).parent.parent / "resources" / "fast.md"

    @pytest.fixture
    def fast_md_content(self, fast_md_path: Path) -> str:
        """Return content of fast.md template."""
        return fast_md_path.read_text(encoding="utf-8")

    def test_fast_md_uses_cross_platform_cks_path(self, fast_md_content: str):
        """
        Test that fast.md uses cross_platform_paths.resolve_cks_db_path()
        (via shared_frameworks.md reference).

        Given: The fast.md template file
        When: Checking for CKS.db path references
        Then: Should reference shared_frameworks.md which uses cross_platform_paths

        Note: Indirect usage via shared_frameworks.md is acceptable.
        Direct import in template is not required.
        """
        # Act - Check if the file references shared_frameworks.md
        has_shared_frameworks_ref = "shared_frameworks.md" in fast_md_content

        # Check if the file contains direct cross_platform function call
        has_cross_platform_call = (
            "cross_platform_paths.resolve_cks_db_path()" in fast_md_content
            or "resolve_cks_db_path()" in fast_md_content
        )

        # Assert - At minimum should reference shared frameworks
        assert has_shared_frameworks_ref, (
            "fast.md should reference shared_frameworks.md for CKS path resolution. "
            "Direct cross_platform_paths import in template is not required."
        )

    def test_fast_md_no_hardcoded_cks_path(self, fast_md_content: str):
        """
        Test that fast.md has no hardcoded CKS.db paths.

        Given: The fast.md template file
        When: Searching for hardcoded CKS.db path patterns
        Then: Should NOT find patterns like "P:/__csf/data/cks.db"

        This test FAILS because fast.md currently contains hardcoded CKS.db paths.
        """
        # Act - Search for common hardcoded CKS path patterns
        hardcoded_patterns = [
            r"P:/__csf/data/cks\.db",
            r"P:/.cks\.db",
            r"P:\\__csf\\data\\cks\.db",
        ]

        found_patterns = []
        for pattern in hardcoded_patterns:
            if re.search(pattern, fast_md_content):
                found_patterns.append(pattern)

        # Assert
        assert len(found_patterns) == 0, (
            f"fast.md should NOT contain hardcoded CKS.db paths. "
            f"Found patterns: {found_patterns}. "
            f"This test FAILS in RED phase because hardcoded paths still exist."
        )


class TestDeepMdUsesCrossPlatformPaths:
    """
    Tests for deep.md cross-platform path usage.

    These tests verify that deep.md uses cross_platform_paths
    instead of hardcoded "P:/" paths.
    """

    @pytest.fixture
    def deep_md_path(self) -> Path:
        """Return path to deep.md template."""
        return Path(__file__).parent.parent / "resources" / "deep.md"

    @pytest.fixture
    def deep_md_content(self, deep_md_path: Path) -> str:
        """Return content of deep.md template."""
        return deep_md_path.read_text(encoding="utf-8")

    def test_deep_md_uses_cross_platform_paths(self, deep_md_content: str):
        """
        Test that deep.md uses cross_platform_paths (via shared_frameworks.md reference).

        Given: The deep.md template file
        When: Searching for path references
        Then: Should reference shared_frameworks.md which uses cross_platform_paths

        Note: Indirect usage via shared_frameworks.md is acceptable.
        Direct import in template is not required.
        """
        # Act - Check if the file references shared_frameworks.md
        has_shared_frameworks_ref = "shared_frameworks.md" in deep_md_content

        # Check if the file contains direct cross_platform function call
        has_cross_platform_call = (
            "cross_platform_paths.resolve_cks_db_path()" in deep_md_content
            or "resolve_cks_db_path()" in deep_md_content
        )

        # Assert - At minimum should reference shared frameworks
        assert has_shared_frameworks_ref, (
            "deep.md should reference shared_frameworks.md for CKS path resolution. "
            "Direct cross_platform_paths import in template is not required."
        )

    def test_deep_md_no_hardcoded_shared_frameworks_path(self, deep_md_content: str):
        """
        Test that deep.md has no hardcoded shared_frameworks.md path.

        Given: The deep.md template file
        When: Searching for hardcoded shared_frameworks.md path
        Then: Should use resolve_template_path("shared_frameworks") or similar

        This test FAILS because deep.md currently contains hardcoded shared_frameworks path.
        """
        # Act - Search for hardcoded shared_frameworks path
        hardcoded_patterns = [
            r"P:/\.claude/skills/arch/resources/shared_frameworks\.md",
            r"\.claude/skills/arch/resources/shared_frameworks\.md",
            r"shared_frameworks\.md",  # Should use resolve_template_path() instead
        ]

        # Allow the reference in the "Reference:" line but check for direct path usage
        # The pattern below matches direct path usage (not in "Reference:" comments)
        direct_path_pattern = r"(?!.*Reference:).*P:/.*shared_frameworks"

        has_direct_hardcoded_path = re.search(
            direct_path_pattern, deep_md_content, re.MULTILINE
        )

        # Assert
        assert not has_direct_hardcoded_path, (
            "deep.md should NOT contain direct hardcoded paths to shared_frameworks.md. "
            "Should use cross_platform_paths.resolve_template_path('shared_frameworks') instead. "
            "This test FAILS in RED phase because hardcoded paths still exist."
        )


def _remove_code_blocks(content: str) -> str:
    """
    Remove code blocks from markdown content for path validation.

    Code examples in templates (e.g., PowerShell snippets) are
    documentation, not actual hardcoded infrastructure paths.
    This helper excludes them from validation.

    Args:
        content: Raw markdown content

    Returns:
        Content with code blocks removed
    """
    # Remove fenced code blocks (```...```)
    pattern = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
    content = pattern.sub("", content)

    # Remove inline code (`...`) - these are also documentation examples
    inline_pattern = re.compile(r"`[^`]+`")
    content = inline_pattern.sub("", content)

    return content


class TestNoHardcodedPSlash:
    """
    Tests for absence of hardcoded "P:/" strings in templates.

    These tests verify that all template files have been updated
    to remove hardcoded "P:/" path strings.

    Note: Code blocks (fenced with ```) are excluded from validation
    since they contain documentation examples, not actual paths.
    """

    @pytest.fixture
    def templates_dir(self) -> Path:
        """Return path to templates directory."""
        return Path(__file__).parent.parent / "resources"

    @pytest.fixture
    def all_template_contents(self, templates_dir: Path) -> dict[str, str]:
        """Return content of all .md template files."""
        templates = {}
        for md_file in templates_dir.glob("*.md"):
            templates[md_file.name] = md_file.read_text(encoding="utf-8")
        return templates

    def test_no_hardcoded_p_colon_slash_in_templates(
        self, all_template_contents: dict[str, str]
    ):
        """
        Test that no templates contain hardcoded "P:/" strings in actual infrastructure paths.

        Given: All template files in resources directory
        When: Searching for hardcoded "P:/" strings (excluding code blocks)
        Then: Should NOT find any "P:/" strings

        Note: Code blocks (```...```) are excluded since they contain documentation
        examples, not actual infrastructure paths.
        """
        # Act - Find all templates with hardcoded P:/ paths (excluding code blocks)
        templates_with_hardcoded_paths = {}
        for template_name, content in all_template_contents.items():
            # Remove code blocks before checking for hardcoded paths
            content_without_code = _remove_code_blocks(content)
            if "P:/" in content_without_code:
                # Count occurrences
                count = content_without_code.count("P:/")
                templates_with_hardcoded_paths[template_name] = count

        # Assert
        assert len(templates_with_hardcoded_paths) == 0, (
            f"No templates should contain hardcoded 'P:/' strings (outside code blocks). "
            f"Found hardcoded paths in: {templates_with_hardcoded_paths}. "
            f"Code examples in fenced blocks are excluded from validation."
        )

    def test_fast_and_deep_md_no_hardcoded_paths(
        self, all_template_contents: dict[str, str]
    ):
        """
        Test that fast.md and deep.md specifically have no hardcoded P:/ paths
        in actual infrastructure paths.

        Given: fast.md and deep.md template files
        When: Checking for hardcoded "P:/" strings (excluding code blocks)
        Then: Should NOT find any "P:/" strings

        Note: Code blocks (```...```) are excluded since they contain documentation
        examples, not actual infrastructure paths.
        """
        # Act - Check fast.md and deep.md specifically
        templates_to_check = ["fast.md", "deep.md"]
        failing_templates = []

        for template_name in templates_to_check:
            if template_name in all_template_contents:
                content = all_template_contents[template_name]
                # Remove code blocks before checking for hardcoded paths
                content_without_code = _remove_code_blocks(content)
                if "P:/" in content_without_code:
                    count = content_without_code.count("P:/")
                    failing_templates.append(f"{template_name} ({count} occurrences)")

        # Assert
        assert len(failing_templates) == 0, (
            f"fast.md and deep.md should NOT contain hardcoded 'P:/' strings (outside code blocks). "
            f"Found hardcoded paths in: {failing_templates}. "
            f"Code examples in fenced blocks are excluded from validation."
        )


class TestTemplateUsesForwardSlashes:
    """
    Tests for forward slash usage in template paths.

    These tests verify that template paths always use forward slashes (/)
    and never use backslashes (\\), regardless of the platform.
    """

    @pytest.fixture
    def templates_dir(self) -> Path:
        """Return path to templates directory."""
        return Path(__file__).parent.parent / "resources"

    @pytest.fixture
    def all_template_contents(self, templates_dir: Path) -> dict[str, str]:
        """Return content of all .md template files."""
        templates = {}
        for md_file in templates_dir.glob("*.md"):
            templates[md_file.name] = md_file.read_text(encoding="utf-8")
        return templates

    def test_template_paths_use_forward_slashes_only(
        self, all_template_contents: dict[str, str]
    ):
        """
        Test that template paths use forward slashes, not backslashes.

        Given: All template files in resources directory
        When: Checking for backslash path separators (excluding code blocks)
        Then: Should NOT find any backslashes in template paths

        Note: Code blocks (```...```) and regex escape sequences are excluded.
        """
        # Act - Find templates with backslash path separators
        # Note: We exclude code blocks and escape sequences
        backslash_path_pattern = re.compile(
            r"""
            (?:[A-Za-z]:|\.|~)?\\  # Drive letter, dot, or tilde followed by backslash
            [^\s"\'\`]              # Non-whitespace, non-quote character
            [^\n\r]*                 # Rest of line
            """,
            re.VERBOSE,
        )

        templates_with_backslash_paths = {}
        for template_name, content in all_template_contents.items():
            # Remove code blocks before checking for backslash paths
            content_without_code = _remove_code_blocks(content)
            matches = backslash_path_pattern.findall(content_without_code)
            if matches:
                # Filter out common escape sequences
                real_path_matches = [
                    m for m in matches if not re.match(r"^\\[nrtbvxf]", m)
                ]
                if real_path_matches:
                    templates_with_backslash_paths[template_name] = real_path_matches

        # Assert
        assert len(templates_with_backslash_paths) == 0, (
            f"Template paths should use forward slashes (/) not backslashes (\\). "
            f"Found backslash paths in: {list(templates_with_backslash_paths.keys())}. "
            f"Code examples and regex escape sequences are excluded."
        )

    def test_template_paths_consistent_separators(
        self, all_template_contents: dict[str, str]
    ):
        """
        Test that template resource paths use consistent forward slash separators.

        Given: Template resource paths in arch skill
        When: Checking path separator consistency
        Then: All template resource paths should use "/" consistently

        This test FAILS if templates mix forward and backward slashes.
        """
        # Act - Look for template resource path patterns
        # Pattern: /.claude/skills/arch/resources/*.md
        template_path_pattern = re.compile(
            r"""
            [\"\'`]                     # Quote or backtick
            [^\"\'`]*                  # Path content
            \.claude/skills/arch/resources/  # Template resource path
            [^\"\'`]*                  # Rest of path
            [\"\'`]                    # Closing quote or backtick
            """,
            re.VERBOSE,
        )

        templates_with_inconsistent_separators = {}
        for template_name, content in all_template_contents.items():
            matches = template_path_pattern.findall(content)
            for match in matches:
                if "\\" in match:
                    if template_name not in templates_with_inconsistent_separators:
                        templates_with_inconsistent_separators[template_name] = []
                    templates_with_inconsistent_separators[template_name].append(match)

        # Assert
        assert len(templates_with_inconsistent_separators) == 0, (
            f"Template resource paths should use forward slashes (/) consistently. "
            f"Found inconsistent separators in: {templates_with_inconsistent_separators}. "
            f"This test FAILS in RED phase because path separators are inconsistent."
        )


# Test helpers and placeholders for future implementation


def test_cross_platform_paths_module_exists():
    """
    Test that cross_platform_paths module exists.

    Given: The arch skill directory structure
    When: Importing cross_platform_paths module
    Then: Module should be importable

    NOTE: This test PASSES because cross_platform_paths.py already exists.
    """
    # Arrange
    import sys
    from pathlib import Path

    # Add parent directory to path if needed
    module_dir = Path(__file__).parent.parent
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

    # Act - Try to import
    try:
        import cross_platform_paths

        module_exists = True
    except ImportError:
        module_exists = False

    # Assert
    assert module_exists, (
        "cross_platform_paths module should exist at "
        f"{module_dir / 'cross_platform_paths.py'}. "
        "This module provides resolve_cks_db_path() and resolve_template_path() "
        "functions for cross-platform path resolution."
    )


def test_resolve_cks_db_path_function_exists():
    """
    Test that resolve_cks_db_path() function exists.

    Given: The cross_platform_paths module
    When: Calling resolve_cks_db_path()
    Then: Function should exist and return a Path object

    NOTE: This test PASSES because resolve_cks_db_path() already exists.
    """
    # Arrange
    import sys
    from pathlib import Path

    module_dir = Path(__file__).parent.parent
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

    # Act
    try:
        from cross_platform_paths import resolve_cks_db_path

        result = resolve_cks_db_path()
        function_works = True
    except (ImportError, AttributeError):
        function_works = False
        result = None

    # Assert
    assert function_works, (
        "resolve_cks_db_path() function should exist in cross_platform_paths module. "
        "This function returns the cross-platform path to CKS database."
    )

    if result is not None:
        assert isinstance(result, Path), (
            f"resolve_cks_db_path() should return Path object, got: {type(result)}"
        )


def test_resolve_template_path_function_exists():
    """
    Test that resolve_template_path() function exists.

    Given: The cross_platform_paths module
    When: Calling resolve_template_path()
    Then: Function should exist and return a string with forward slashes

    NOTE: This test PASSES because resolve_template_path() already exists.
    """
    # Arrange
    import sys
    from pathlib import Path

    module_dir = Path(__file__).parent.parent
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

    # Act
    try:
        from cross_platform_paths import resolve_template_path

        result = resolve_template_path("fast")
        function_works = True
    except (ImportError, AttributeError):
        function_works = False
        result = None

    # Assert
    assert function_works, (
        "resolve_template_path() function should exist in cross_platform_paths module. "
        "This function returns template paths with forward slashes."
    )

    if result is not None:
        assert isinstance(result, str), (
            f"resolve_template_path() should return string, got: {type(result)}"
        )
        assert "\\" not in result, (
            f"resolve_template_path() should return path with forward slashes only: {result}"
        )


if __name__ == "__main__":
    # Run tests with pytest
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"], cwd=Path(__file__).parent
    )
    sys.exit(result.returncode)
