#!/usr/bin/env python3
"""Unit tests for modernization_section_generator.py module.

This test suite verifies the ModernizationSectionGenerator class which formats
modernization findings into markdown sections for plan.md.

Run with: pytest P:/.claude/skills/code/tests/test_modernization_section_generator.py -v
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.modernization_section_generator import ModernizationSectionGenerator


class TestModernizationSectionGeneratorBasicFormatting:
    """Test basic markdown section generation."""

    def test_generates_modernization_considerations_section(self):
        """
        Test that generator creates "Modernization Considerations" section.

        Given: Modernization findings with divergences
        When: generate_section() is called
        Then: Section is created with proper header and structure
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "requests",
                    "current_version": "2.25.0",
                    "latest_version": "2.31.0",
                    "priority": "P1",
                    "breaking_changes": ["deprecated verify parameter"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert "## Modernization Considerations" in section
        assert len(section) > 0

    def test_section_has_three_subsections(self):
        """
        Test that section contains three required subsections.

        Given: Modernization findings
        When: generate_section() is called
        Then: Section includes Detected Divergences, Recommendation, Your Choice
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "django",
                    "current_version": "3.2.0",
                    "latest_version": "4.2.0",
                    "priority": "P0",
                    "breaking_changes": ["API changes in ORM"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert "### Detected Divergences" in section
        assert "### Recommendation" in section
        assert "### Your Choice" in section


class TestModernizationSectionGeneratorPriorityFormatting:
    """Test P0/P1/P2 priority categorization and formatting."""

    def test_formats_p0_priority_divergences(self):
        """
        Test that P0 (critical) divergences are formatted correctly.

        Given: Finding with P0 priority (security vulnerabilities, breaking API changes)
        When: generate_section() is called
        Then: P0 priority is displayed prominently with explanation
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "urllib3",
                    "current_version": "1.26.0",
                    "latest_version": "2.0.0",
                    "priority": "P0",
                    "breaking_changes": ["Security vulnerability CVE-2023-43804"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert "**P0**" in section or "P0" in section
        assert "urllib3" in section
        assert "1.26.0" in section
        assert "2.0.0" in section

    def test_formats_p1_priority_divergences(self):
        """
        Test that P1 (high) divergences are formatted correctly.

        Given: Finding with P1 priority (performance improvements, deprecated features)
        When: generate_section() is called
        Then: P1 priority is displayed with appropriate emphasis
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "numpy",
                    "current_version": "1.20.0",
                    "latest_version": "1.24.0",
                    "priority": "P1",
                    "breaking_changes": ["Deprecated np.int usage"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert "**P1**" in section or "P1" in section
        assert "numpy" in section

    def test_formats_p2_priority_divergences(self):
        """
        Test that P2 (low) divergences are formatted correctly.

        Given: Finding with P2 priority (minor improvements, cosmetic changes)
        When: generate_section() is called
        Then: P2 priority is displayed with minimal emphasis
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "pytest",
                    "current_version": "7.0.0",
                    "latest_version": "7.4.0",
                    "priority": "P2",
                    "breaking_changes": ["Minor CLI improvements"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert "**P2**" in section or "P2" in section
        assert "pytest" in section

    def test_orders_divergences_by_priority(self):
        """
        Test that divergences are ordered P0 first, then P1, then P2.

        Given: Multiple findings with different priorities
        When: generate_section() is called
        Then: Findings appear in priority order (P0 → P1 → P2)
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "requests",
                    "current_version": "2.25.0",
                    "latest_version": "2.31.0",
                    "priority": "P1",
                    "breaking_changes": ["Deprecated verify"]
                },
                {
                    "library": "urllib3",
                    "current_version": "1.26.0",
                    "latest_version": "2.0.0",
                    "priority": "P0",
                    "breaking_changes": ["Security vulnerability"]
                },
                {
                    "library": "pytest",
                    "current_version": "7.0.0",
                    "latest_version": "7.4.0",
                    "priority": "P2",
                    "breaking_changes": ["Minor improvements"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Find P0, P1, P2 positions
        p0_pos = section.find("P0")
        p1_pos = section.find("P1")
        p2_pos = section.find("P2")

        # P0 should appear before P1, P1 before P2
        assert p0_pos < p1_pos, "P0 should appear before P1"
        assert p1_pos < p2_pos, "P1 should appear before P2"


class TestModernizationSectionGeneratorRecommendations:
    """Test recommendation generation and formatting."""

    def test_recommends_existing_patterns_by_default(self):
        """
        Test that default recommendation is to use existing codebase patterns.

        Given: Modernization findings detected
        When: generate_section() is called
        Then: Recommendation defaults to existing patterns for consistency
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "flask",
                    "current_version": "2.0.0",
                    "latest_version": "3.0.0",
                    "priority": "P1",
                    "breaking_changes": ["API changes"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert "existing" in section.lower() or "codebase patterns" in section.lower()

    def test_recommends_modern_for_p0_security(self):
        """
        Test that P0 security vulnerabilities recommend modernization.

        Given: P0 finding with security vulnerability
        When: generate_section() is called
        Then: Recommendation suggests modernization for security
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "cryptography",
                    "current_version": "3.4.0",
                    "latest_version": "41.0.0",
                    "priority": "P0",
                    "breaking_changes": ["Security vulnerability CVE-2023-23931"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert "modern" in section.lower() or "update" in section.lower()
        assert "P0" in section

    def test_provides_clear_recommendation_text(self):
        """
        Test that recommendation is clearly stated and actionable.

        Given: Modernization findings
        When: generate_section() is called
        Then: Recommendation subsection has clear, actionable text
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "fastapi",
                    "current_version": "0.68.0",
                    "latest_version": "0.100.0",
                    "priority": "P1",
                    "breaking_changes": [" breaking changes in dependency injection"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Check that recommendation subsection exists and has content
        recommendation_start = section.find("### Recommendation")
        assert recommendation_start != -1

        # Extract recommendation subsection
        recommendation_end = section.find("### Your Choice", recommendation_start)
        recommendation_text = section[recommendation_start:recommendation_end]

        # Should have actual content (not just header)
        assert len(recommendation_text) > 20


class TestModernizationSectionGeneratorUserChoiceOptions:
    """Test user choice option formatting with checkboxes."""

    def test_formats_user_choice_with_checkboxes(self):
        """
        Test that user choice section includes checkbox options.

        Given: Modernization findings
        When: generate_section() is called
        Then: Your Choice subsection has checkbox options for user selection
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "sqlalchemy",
                    "current_version": "1.4.0",
                    "latest_version": "2.0.0",
                    "priority": "P0",
                    "breaking_changes": ["Major ORM changes"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Check for markdown checkboxes ([ ] or [x])
        assert "- [ ]" in section or "- [x]" in section or "* [ ]" in section

    def test_includes_existing_pattern_option(self):
        """
        Test that user choice includes "use existing patterns" option.

        Given: Modernization findings
        When: generate_section() is called
        Then: Checkbox option for existing codebase patterns is present
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "pandas",
                    "current_version": "1.3.0",
                    "latest_version": "2.0.0",
                    "priority": "P1",
                    "breaking_changes": ["Deprecations"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should have option to use existing patterns
        choice_start = section.find("### Your Choice")
        choice_section = section[choice_start:]

        assert "existing" in choice_section.lower()
        assert "- [" in choice_section  # Checkbox format

    def test_includes_modern_pattern_option(self):
        """
        Test that user choice includes "use modern patterns" option.

        Given: Modernization findings
        When: generate_section() is called
        Then: Checkbox option for modern patterns is present
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "aiohttp",
                    "current_version": "3.8.0",
                    "latest_version": "3.9.0",
                    "priority": "P2",
                    "breaking_changes": ["Minor API updates"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should have option to use modern patterns
        choice_start = section.find("### Your Choice")
        choice_section = section[choice_start:]

        assert "modern" in choice_section.lower()
        assert "- [" in choice_section  # Checkbox format


class TestModernizationSectionGeneratorContext7Urls:
    """Test Context7 URL inclusion for migration guides."""

    def test_includes_migration_links(self):
        """
        Test that migration guide links are included in section.

        Given: Findings with Context7 URLs
        When: generate_section() is called
        Then: Context7 URLs appear as clickable links in output
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "django",
                    "current_version": "3.2.0",
                    "latest_version": "4.2.0",
                    "priority": "P0",
                    "breaking_changes": ["Major ORM changes"],
                    "context7_url": "https://context7.io/docs/django/4.2/migration"
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should include URL in markdown link format
        assert "https://context7.io" in section or "context7" in section.lower()
        assert "[" in section and "](" in section  # Markdown link format

    def test_handles_missing_context7_url(self):
        """
        Test that generator handles missing Context7 URLs gracefully.

        Given: Findings without Context7 URLs
        When: generate_section() is called
        Then: Section is generated without errors, no broken links
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "click",
                    "current_version": "8.0.0",
                    "latest_version": "8.1.0",
                    "priority": "P2",
                    "breaking_changes": ["Minor changes"]
                    # No context7_url field
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should still generate valid section
        assert len(section) > 0
        assert "click" in section

    def test_formats_context7_urls_as_clickable_links(self):
        """
        Test that Context7 URLs are formatted as markdown clickable links.

        Given: Findings with Context7 URLs
        When: generate_section() is called
        Then: URLs appear in [text](url) markdown format
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "requests",
                    "current_version": "2.25.0",
                    "latest_version": "2.31.0",
                    "priority": "P1",
                    "breaking_changes": ["Deprecated verify parameter"],
                    "context7_url": "https://context7.io/docs/requests/2.31/migration"
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Check for markdown link pattern [text](url)
        assert "](" in section  # Markdown link format
        assert "https://" in section


class TestModernizationSectionGeneratorEmptyFindings:
    """Test handling of empty findings or no divergences detected."""

    def test_handles_empty_findings_gracefully(self):
        """
        Test that generator handles empty divergences list.

        Given: No divergences detected (empty list)
        When: generate_section() is called
        Then: Graceful message or minimal section is generated
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {"divergences": []}

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should return a valid string
        assert isinstance(section, str)
        assert len(section) > 0

    def test_empty_findings_message(self):
        """
        Test that empty findings shows user-friendly message.

        Given: No divergences detected
        When: generate_section() is called
        Then: Message indicates no modernization needed or divergences found
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {"divergences": []}

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should mention no divergences or similar
        assert "no" in section.lower() or "none" in section.lower() or "detected" in section.lower()

    def test_handles_missing_divergences_key(self):
        """
        Test that generator handles missing 'divergences' key in findings.

        Given: Findings dict without 'divergences' key
        When: generate_section() is called
        Then: Graceful handling, no crashes
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {}  # No 'divergences' key

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should return a valid string
        assert isinstance(section, str)
        assert len(section) > 0


class TestModernizationSectionGeneratorOutputFormat:
    """Test output format and structure."""

    def test_returns_string_type(self):
        """
        Test that generate_section() returns a string.

        Given: Any valid findings input
        When: generate_section() is called
        Then: Return type is str (not dict, list, etc.)
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {"divergences": []}

        # Act
        section = generator.generate_section(findings)

        # Assert
        assert isinstance(section, str)

    def test_output_is_valid_markdown(self):
        """
        Test that output is valid markdown format.

        Given: Modernization findings
        When: generate_section() is called
        Then: Output is valid markdown with proper headers and formatting
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "pytest",
                    "current_version": "7.0.0",
                    "latest_version": "7.4.0",
                    "priority": "P2",
                    "breaking_changes": ["Minor improvements"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Check for markdown headers
        assert "##" in section  # Header markers
        # Check for lists
        assert "- " in section or "* " in section  # List markers

    def test_section_is_not_empty(self):
        """
        Test that generated section has substantial content.

        Given: Modernization findings
        When: generate_section() is called
        Then: Output is not empty or just whitespace
        """
        # Arrange
        generator = ModernizationSectionGenerator()
        findings = {
            "divergences": [
                {
                    "library": "flask",
                    "current_version": "2.0.0",
                    "latest_version": "3.0.0",
                    "priority": "P1",
                    "breaking_changes": ["API changes"]
                }
            ]
        }

        # Act
        section = generator.generate_section(findings)

        # Assert
        # Should have meaningful content
        assert len(section.strip()) > 50  # At least some content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
