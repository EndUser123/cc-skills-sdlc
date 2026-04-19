"""
Tests for verifying load_arch_config has been extracted from SKILL.md to config.py.

These tests verify that:
1. config.py exists and is importable
2. load_arch_config() function exists in config module
3. SKILL.md references config.load_arch_config() (not inline implementation)
4. SKILL.md does NOT contain the full function implementation

This is a refactoring verification test - the config module should already exist,
but SKILL.md may still contain the inline implementation that should be removed.

Run with: pytest P:/.claude/skills/arch/tests/test_config_extraction.py -v
"""

import pytest
from pathlib import Path


class TestConfigModuleExists:
    """Tests for config.py module existence and importability."""

    def test_config_module_exists(self):
        """
        Test that config.py exists and is importable.

        Given: The arch skill has been refactored to extract config logic
        When: Checking if config module exists
        Then: config.py should exist in the arch skill directory
        """
        config_path = Path(__file__).parent.parent / "config.py"
        assert config_path.exists(), (
            f"config.py not found at {config_path}. "
            "The config module should exist to contain load_arch_config()."
        )

    def test_config_module_importable(self):
        """
        Test that config module can be imported.

        Given: config.py exists
        When: Attempting to import the module
        Then: Module should import without errors
        """
        try:
            import importlib
            import sys
            from pathlib import Path

            # Add parent directory to path for import
            parent_dir = str(Path(__file__).parent.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            config = importlib.import_module("config")
            assert config is not None
        except ImportError as e:
            pytest.fail(f"Failed to import config module: {e}")


class TestLoadArchConfigFunction:
    """Tests for load_arch_config() function in config module."""

    def test_load_arch_config_function_exists(self):
        """
        Test that load_arch_config() function exists in config module.

        Given: config.py exists
        When: Checking for load_arch_config function
        Then: Function should be defined in the config module
        """
        import importlib
        import sys
        from pathlib import Path

        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        config = importlib.import_module("config")

        assert hasattr(config, "load_arch_config"), (
            "load_arch_config() function not found in config module. "
            "The function should be defined in config.py."
        )

    def test_load_arch_config_is_callable(self):
        """
        Test that load_arch_config is a callable function.

        Given: load_arch_config exists in config module
        When: Checking if it's callable
        Then: load_arch_config should be a callable function
        """
        import importlib
        import sys
        from pathlib import Path

        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        config = importlib.import_module("config")

        assert callable(config.load_arch_config), (
            "load_arch_config exists but is not callable. "
            "It should be defined as a function."
        )


class TestSkillMdReferencesModule:
    """Tests for SKILL.md referencing the config module."""

    @pytest.fixture
    def skill_md_path(self):
        """Get path to SKILL.md."""
        return Path(__file__).parent.parent / "SKILL.md"

    @pytest.fixture
    def skill_md_content(self, skill_md_path):
        """Load SKILL.md content."""
        if not skill_md_path.exists():
            pytest.skip(f"SKILL.md not found at {skill_md_path}")
        return skill_md_path.read_text()

    def test_skill_md_references_config_load_arch_config(self, skill_md_content):
        """
        Test that SKILL.md references config.load_arch_config().

        Given: SKILL.md exists
        When: Searching for references to the config module function
        Then: SKILL.md should contain a reference to config.load_arch_config()
        """
        # Check for various reference patterns
        reference_patterns = [
            "config.load_arch_config()",
            "from config import load_arch_config",
            "from .config import load_arch_config",
            "from arch.config import load_arch_config",
        ]

        found_reference = any(
            pattern in skill_md_content for pattern in reference_patterns
        )

        assert found_reference, (
            "SKILL.md does not reference config.load_arch_config(). "
            "The documentation should reference the extracted function instead of "
            "containing the full implementation inline. "
            f"Expected one of: {reference_patterns}"
        )

    def test_skill_md_contains_config_import_example(self, skill_md_content):
        """
        Test that SKILL.md shows how to import/use the config module.

        Given: SKILL.md exists and references config
        When: Checking for import/usage examples
        Then: SKILL.md should contain a usage example for config module
        """
        # Look for import statements or usage patterns
        import_patterns = [
            "import config",
            "from config",
            "from .config",
            "config.load_arch_config",
        ]

        found_import = any(pattern in skill_md_content for pattern in import_patterns)

        assert found_import, (
            "SKILL.md does not show how to import/use the config module. "
            "An import example should be provided for users of the skill."
        )


class TestNoDuplicateFunctionInDoc:
    """Tests for ensuring SKILL.md does not contain duplicate function implementation."""

    @pytest.fixture
    def skill_md_path(self):
        """Get path to SKILL.md."""
        return Path(__file__).parent.parent / "SKILL.md"

    @pytest.fixture
    def skill_md_content(self, skill_md_path):
        """Load SKILL.md content."""
        if not skill_md_path.exists():
            pytest.skip(f"SKILL.md not found at {skill_md_path}")
        return skill_md_path.read_text()

    def test_no_full_function_definition_in_skill_md(self, skill_md_content):
        """
        Test that SKILL.md does NOT contain the full load_arch_config() implementation.

        Given: load_arch_config() has been extracted to config.py
        When: Examining SKILL.md content
        Then: SKILL.md should NOT contain the full function definition

        This test checks for the function signature pattern which indicates
        the full implementation is still inline in SKILL.md.
        """
        # Look for the function definition pattern that appears in the inline version
        # The inline version has: "def load_arch_config() -> dict | None:"
        function_patterns = [
            "def load_arch_config()",
            "def load_arch_config (",
            "    def load_arch_config()",
        ]

        found_function_def = any(
            pattern in skill_md_content for pattern in function_patterns
        )

        assert not found_function_def, (
            "SKILL.md contains a full function definition for load_arch_config(). "
            "The function implementation should be in config.py only. "
            "SKILL.md should reference config.load_arch_config() instead of "
            "containing the full implementation inline."
        )

    def test_no_duplicate_implementation_details(self, skill_md_content):
        """
        Test that SKILL.md does not contain duplicate implementation details.

        Given: load_arch_config() has been extracted to config.py
        When: Checking for implementation-specific patterns
        Then: SKILL.md should NOT contain implementation code blocks

        This checks for specific implementation patterns that would indicate
        the code is duplicated inline rather than properly extracted.
        """
        # These are implementation-specific patterns that should only be in config.py
        implementation_patterns = [
            'project_config = Path.cwd() / ".archconfig.json"',
            'project_config = Path.cwd() / ".arch" / "config.json"',
            'user_config_path = Path.home() / ".archconfig.json"',
            "with open(project_config) as f:",
            "with open(user_config) as f:",
            "json.load(f)",
            'VALID_DOMAINS = {"cli", "python"',
        ]

        found_patterns = [p for p in implementation_patterns if p in skill_md_content]

        assert len(found_patterns) == 0, (
            f"SKILL.md contains implementation details that should be in config.py: "
            f"{found_patterns[:3]}. "
            "SKILL.md should reference config.load_arch_config() instead of "
            "containing implementation code."
        )

    def test_skill_md_has_concise_reference_not_implementation(self, skill_md_content):
        """
        Test that SKILL.md has a concise reference rather than full implementation.

        Given: SKILL.md should reference the extracted function
        When: Examining the structure of config-related content
        Then: The reference should be concise (not dozens of lines of code)

        This is a heuristic test - if SKILL.md contains a very long code block
        with config implementation details, it's likely the full implementation.
        """
        # Count lines that look like config implementation code
        lines = skill_md_content.split("\n")

        # Look for code blocks (indented lines in markdown code blocks)
        in_code_block = False
        config_impl_lines = 0

        for line in lines:
            if "```" in line:
                in_code_block = not in_code_block
                continue

            if in_code_block:
                # Count lines that look like implementation details
                if any(
                    pattern in line
                    for pattern in [
                        "project_config",
                        "user_config",
                        "json.load",
                        "VALID_DOMAINS",
                        "Path.home()",
                        "Path.cwd()",
                    ]
                ):
                    config_impl_lines += 1

        # If there are more than 10 lines of config implementation code,
        # it's likely the full implementation is still inline
        assert config_impl_lines <= 10, (
            f"SKILL.md contains {config_impl_lines} lines of config implementation code. "
            "This suggests the full load_arch_config() implementation is still inline. "
            "SKILL.md should have a concise reference to config.load_arch_config() "
            "instead of the full implementation."
        )
