"""Tests for TemplateValidator with 3-stage fail-fast chain.

Run with: pytest P:/packages/arch/skill/tests/test_validate.py -v
"""

import tempfile
from pathlib import Path


from validate import (
    DUPLICATE_OVERLAP_THRESHOLD,
    HIGH_OVERLAP_THRESHOLD,
    DUPLICATE_CHECK_SECTIONS,
    TEMPLATE_NAMES,
    TemplateValidator,
    validate_templates,
)


class TestTemplateValidatorInit:
    """Tests for TemplateValidator initialization."""

    def test_default_resources_dir(self):
        """Validator uses skill/resources relative to module by default."""
        validator = TemplateValidator()
        expected = Path(__file__).parent.parent / "resources"
        assert validator.resources_dir == expected

    def test_custom_resources_dir(self):
        """Validator accepts custom resources directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = TemplateValidator(resources_dir=Path(tmpdir))
            assert validator.resources_dir == Path(tmpdir)


class TestCheckFileExists:
    """Tests for Stage 1: file_exists check."""

    def test_all_templates_exist(self):
        """Returns success when all template files exist."""
        validator = TemplateValidator()
        result = validator._check_file_exists(["fast", "deep"])
        assert result.is_success is True
        assert len(result.value) == 2
        assert result.metadata["stage"] == "file_exists"

    def test_missing_template_returns_error(self):
        """Returns error with missing_templates when files don't exist."""
        validator = TemplateValidator()
        result = validator._check_file_exists(["nonexistent"])
        assert result.is_success is False
        assert result.error == "file_exists_failed"
        assert "nonexistent" in result.metadata["missing_templates"]
        assert result.metadata["stage"] == "file_exists"

    def test_partial_missing(self):
        """Returns error when some templates missing."""
        validator = TemplateValidator()
        result = validator._check_file_exists(["fast", "nonexistent"])
        assert result.is_success is False
        assert "nonexistent" in result.metadata["missing_templates"]


class TestCheckDuplicates:
    """Tests for Stage 2: duplicate detection."""

    def test_no_duplicates_between_fast_and_deep(self):
        """No high overlap between fast.md and deep.md."""
        validator = TemplateValidator()
        result = validator._check_duplicates(["fast", "deep"])
        assert result.is_success is True
        assert result.metadata["stage"] == "duplicates"

    def test_extract_section_content(self):
        """Extracts section content from markdown correctly."""
        validator = TemplateValidator()
        content = """
# Stage 0

Some content here

# Stage 1

More content
"""
        result = validator._extract_section_content(content, "Stage 0")
        assert result is not None
        assert "Some content here" in result
        assert "# Stage 1" not in result

    def test_extract_section_not_found(self):
        """Returns None when section not found."""
        validator = TemplateValidator()
        result = validator._extract_section_content("# Only header", "Stage 0")
        assert result is None

    def test_calculate_line_overlap_empty(self):
        """Returns 0 for empty text."""
        validator = TemplateValidator()
        overlap = validator._calculate_line_overlap("", "some text")
        assert overlap == 0.0

    def test_calculate_line_overlap_full(self):
        """Returns 100 for identical texts."""
        validator = TemplateValidator()
        overlap = validator._calculate_line_overlap("a\nb\nc", "a\nb\nc")
        assert overlap == 100.0

    def test_calculate_line_overlap_partial(self):
        """Returns correct percentage for partial overlap."""
        validator = TemplateValidator()
        overlap = validator._calculate_line_overlap("a\nb\nc", "a\nb\nd")
        # 2 shared lines out of 3 max unique = 66.67%
        assert 66.0 < overlap < 67.0


class TestCheckPermissions:
    """Tests for Stage 3: permissions check."""

    def test_readable_templates(self):
        """Returns success for readable template files."""
        validator = TemplateValidator()
        result = validator._check_permissions(["fast", "deep"])
        assert result.is_success is True
        assert len(result.value) == 2
        assert result.metadata["stage"] == "permissions"

    def test_empty_file_is_unreadable(self, tmp_path):
        """Empty template file is flagged as unreadable."""
        resources_dir = tmp_path / "resources"
        resources_dir.mkdir()
        (resources_dir / "empty.md").write_text("")
        validator = TemplateValidator(resources_dir=resources_dir)
        result = validator._check_permissions(["empty"])
        assert result.is_success is False
        assert "empty" in result.metadata["unreadable_templates"]


class TestValidateTemplates:
    """Tests for full validation pipeline."""

    def test_valid_templates_pass_all_stages(self):
        """Validation passes for valid template set."""
        validator = TemplateValidator()
        result = validator.validate_templates(["fast", "deep"])
        assert result.is_success is True
        assert result.metadata["stage"] == "all"

    def test_fail_fast_at_file_exists(self):
        """Stops at file_exists stage when file missing."""
        validator = TemplateValidator()
        result = validator.validate_templates(["fast", "nonexistent"])
        assert result.is_success is False
        assert result.metadata["stage"] == "file_exists"
        # Should NOT reach duplicates stage
        assert result.metadata.get("section") is None

    def test_fail_fast_at_duplicates(self):
        """Stops at duplicates stage when high overlap detected."""
        # Create temp resources with known high overlap in a section
        # Note: "Stage 0.5" uses ## prefix to match template header format
        # 3 shared lines / 3 max = 100% overlap (exceeds 70% threshold)
        with tempfile.TemporaryDirectory() as tmpdir:
            resources_dir = Path(tmpdir)
            content_a = """
## Stage 0.5
Shared content line 1
Shared content line 2
Shared content line 3
Unique to A

## Other section
Different content
"""
            content_b = """
## Stage 0.5
Shared content line 1
Shared content line 2
Shared content line 3
Different content here
"""
            (resources_dir / "template_a.md").write_text(content_a)
            (resources_dir / "template_b.md").write_text(content_b)
            validator = TemplateValidator(resources_dir=resources_dir)
            result = validator.validate_templates(["template_a", "template_b"])
            # High overlap in Stage 0.5 should fail
            assert result.is_success is False

    def test_none_defaults_to_all_templates(self):
        """Passing None validates all known templates."""
        validator = TemplateValidator()
        result = validator.validate_templates(None)
        assert result.is_success is True
        assert result.metadata["stage"] == "all"

    def test_constants_are_correct(self):
        """Verify constant values."""
        assert DUPLICATE_OVERLAP_THRESHOLD == 50.0
        assert HIGH_OVERLAP_THRESHOLD == 70.0
        # "Stage 0" removed - it's boilerplate shared across all templates
        assert "Stage 0.5" in DUPLICATE_CHECK_SECTIONS
        assert "cli.md" in TEMPLATE_NAMES.values()


class TestStandaloneFunction:
    """Tests for standalone validate_templates() wrapper."""

    def test_wrapper_returns_arch_result(self):
        """Standalone function returns ArchResult."""
        result = validate_templates(["fast", "deep"])
        assert hasattr(result, "is_success")
        assert hasattr(result, "value")
        assert hasattr(result, "error")
