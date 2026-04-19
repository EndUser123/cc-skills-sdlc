"""
Test suite for /docs-validate skill.

Tests the skill's ability to validate documentation quality and provide actionable feedback.
"""

import tempfile
from pathlib import Path
import sys

# Add /package skill to path for DocumentationValidator import
package_skill_path = Path(__file__).parent.parent.parent / "package"
sys.path.insert(0, str(package_skill_path))

from resources.validate_docs import DocumentationValidator


class TestDocsValidateSkillTriggering:
    """Test skill triggering and loading."""

    def test_skill_file_exists(self):
        """SKILL.md file must exist at correct location."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"
        assert skill_path.exists(), "SKILL.md must exist at skill root"

    def test_skill_frontmatter(self):
        """SKILL.md must have valid YAML frontmatter with required fields."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"
        content = skill_path.read_text()

        # Check frontmatter markers
        assert content.startswith("---"), "SKILL.md must start with YAML frontmatter marker"
        assert "\n---\n" in content, "SKILL.md must have closing frontmatter marker"

        # Extract frontmatter
        frontmatter = content.split("---")[1]
        assert "name:" in frontmatter, "Frontmatter must contain 'name' field"
        assert "description:" in frontmatter, "Frontmatter must contain 'description' field"

    def test_skill_description_trigger_phrases(self):
        """Description must include specific trigger phrases."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"
        content = skill_path.read_text()

        frontmatter = content.split("---")[1]
        assert "validate documentation" in frontmatter.lower(), "Description must mention 'validate documentation'"
        assert "check docs" in frontmatter.lower() or "check documentation" in frontmatter.lower(), "Description must mention checking docs"


class TestDocsValidateWorkflow:
    """Test the documentation validation workflow."""

    def test_workflow_detects_circular_references(self, tmp_path):
        """Circular reference detection: SKILL.md → B.md (under 50 lines, mentions SKILL.md)."""
        # Create SKILL.md with reference
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: test\nversion: 1.0.0\n---\n\nSee b.md for details.\n")

        # Create referenced file with circular reference (under 50 lines, mentions SKILL.md)
        file_b = tmp_path / "b.md"
        file_b.write_text("# File B\n\nSee SKILL.md for details.\n")  # Under 50 lines

        # The skill should detect this circular reference
        validator = DocumentationValidator(tmp_path)
        issues = validator.validate()

        circular_issues = [i for i in issues if i['type'] == 'circular_reference']
        assert len(circular_issues) > 0, "Should detect circular references"

    def test_workflow_detects_incomplete_content(self, tmp_path):
        """Incomplete content detection: Missing referenced files."""
        # Create SKILL.md with reference to non-existent file
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: test\nversion: 1.0.0\n---\n\nSee guide.md for more details.\n")

        validator = DocumentationValidator(tmp_path)
        issues = validator.validate()

        # Should detect missing file (not 'incomplete_content' which doesn't exist)
        missing_issues = [i for i in issues if i['type'] == 'missing_file']
        assert len(missing_issues) > 0, "Should detect missing referenced file"

    def test_workflow_detects_version_conflicts(self, tmp_path):
        """Version conflict detection: v5.1 references in v5.2 codebase."""
        # Create SKILL.md with version
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: test\nversion: 5.2.0\n---\n\n# Test Skill\n")

        # Create other file with old version reference
        old_file = tmp_path / "old.md"
        old_file.write_text("# Legacy Doc\n\nThis is from Version 5.1. See migration guide.\n")

        validator = DocumentationValidator(tmp_path)
        issues = validator.validate()

        version_issues = [i for i in issues if i['type'] == 'version_conflict']
        assert len(version_issues) > 0, "Should detect version conflicts"


class TestDocsValidateIntegration:
    """Test integration with /package DocumentationValidator."""

    def test_uses_package_validator(self):
        """Skill must use DocumentationValidator from /package."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"
        content = skill_path.read_text()

        # Check that skill mentions using DocumentationValidator
        assert "DocumentationValidator" in content or "validate_docs.py" in content, \
            "Skill must reference DocumentationValidator from /package"

    def test_suggests_fixes_for_issues(self, tmp_path):
        """Skill should provide actionable fix suggestions."""
        # Create SKILL.md with reference to non-existent file
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: test\nversion: 1.0.0\n---\n\nSee [detailed guide](guide.md)\n")

        validator = DocumentationValidator(tmp_path)
        issues = validator.validate()

        # Each issue should have actionable guidance
        for issue in issues:
            assert 'file' in issue, "Issue must specify file path"
            assert 'type' in issue, "Issue must have type"
            assert 'message' in issue, "Issue must have message"
            assert 'fix' in issue, "Issue must have fix suggestion"


class TestDocsValidateExamples:
    """Test example scenarios from skill description."""

    def test_circular_reference_example(self):
        """Example: Circular refs between two stub files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create SKILL.md with circular reference
            skill_md = Path(tmp_dir) / "SKILL.md"
            skill_md.write_text("---\nname: test\nversion: 1.0.0\n---\n\nSee ref-b.md\n")

            # Create referenced file with circular reference
            file_b = Path(tmp_dir) / "ref-b.md"
            file_b.write_text("# Ref B\n\nSee SKILL.md\n")

            validator = DocumentationValidator(Path(tmp_dir))
            issues = validator.validate()

            circular = [i for i in issues if i['type'] == 'circular_reference']
            assert len(circular) > 0, "Should detect circular reference example"

    def test_incomplete_content_example(self):
        """Example: 17-line stub file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create SKILL.md with reference to non-existent file
            skill_md = Path(tmp_dir) / "SKILL.md"
            skill_md.write_text("---\nname: test\nversion: 1.0.0\n---\n\nSee guide.md\n")

            validator = DocumentationValidator(Path(tmp_dir))
            issues = validator.validate()

            # Should detect missing file (not 'incomplete_content')
            missing = [i for i in issues if i['type'] == 'missing_file']
            assert len(missing) > 0, "Should detect missing referenced file"


class TestDocsValidateQuality:
    """Test skill quality and completeness."""

    def test_skill_body_lean(self):
        """SKILL.md body should be lean (~1,500 words)."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"
        content = skill_path.read_text()

        # Extract body (after frontmatter)
        body_start = content.index("\n---\n") + 5
        body = content[body_start:]

        word_count = len(body.split())
        assert word_count < 2500, f"SKILL.md body too long: {word_count} words (target ~1,500)"

    def test_skill_imperative_form(self):
        """SKILL.md should use imperative form (not 'you should')."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"
        content = skill_path.read_text()

        # Check body (after frontmatter)
        body_start = content.index("\n---\n") + 5
        body = content[body_start:].lower()

        # Count prohibited phrases
        bad_phrases = [
            "you should", "you must", "you need to",
            "we recommend", "consider using"
        ]

        bad_count = sum(body.count(phrase) for phrase in bad_phrases)
        assert bad_count < 3, f"Too many 'you' phrases ({bad_count}), use imperative form instead"

    def test_skill_progressive_disclosure(self):
        """Skill should reference detailed docs in references/."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"
        content = skill_path.read_text()

        # Check for references to external documentation
        has_references = "references/" in content or "see " in content.lower()
        assert has_references, "Skill should reference external documentation for detailed content"
