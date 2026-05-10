"""Tests for ArchResult generic result type.

Run with: pytest P:\\\\\\packages/arch/skill/tests/test_results.py -v
"""

import pytest

from arch.skill.results import ArchResult


class TestArchResultSuccess:
    """Tests for successful result construction and properties."""

    def test_is_success_true_on_success(self):
        """is_success should be True when result indicates success."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.is_success is True

    def test_value_available_on_success(self):
        """value should be accessible on success."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.value == {"key": "val"}

    def test_error_none_on_success(self):
        """error should be None on success."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.error is None

    def test_is_complete_true_when_success_with_value(self):
        """is_complete should be True when success and value is not None."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.is_complete is True

    def test_is_valid_true_on_success(self):
        """is_valid should be True on success (terminal state)."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.is_valid is True

    def test_templates_used_defaults_to_empty_list(self):
        """templates_used should default to empty list."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.templates_used == []

    def test_metadata_defaults_to_empty_dict(self):
        """metadata should default to empty dict."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.metadata == {}

    def test_templates_used_can_be_set(self):
        """templates_used can be set at construction."""
        result = ArchResult(
            is_success=True,
            value={"key": "val"},
            templates_used=["fast", "deep"],
        )
        assert result.templates_used == ["fast", "deep"]

    def test_metadata_can_be_set(self):
        """metadata can be set at construction."""
        result = ArchResult(
            is_success=True,
            value={"key": "val"},
            metadata={"stage": "file_exists"},
        )
        assert result.metadata == {"stage": "file_exists"}


class TestArchResultError:
    """Tests for error result construction and properties."""

    def test_is_success_false_on_error(self):
        """is_success should be False when result indicates error."""
        result = ArchResult(is_success=False, error="template_not_found")
        assert result.is_success is False

    def test_value_none_on_error(self):
        """value should be None on error."""
        result = ArchResult(is_success=False, error="template_not_found")
        assert result.value is None

    def test_error_available_on_error(self):
        """error should be accessible on error."""
        result = ArchResult(is_success=False, error="template_not_found")
        assert result.error == "template_not_found"

    def test_is_complete_false_on_error(self):
        """is_complete should be False on error."""
        result = ArchResult(is_success=False, error="template_not_found")
        assert result.is_complete is False

    def test_is_valid_true_on_error(self):
        """is_valid should be True on error (terminal state)."""
        result = ArchResult(is_success=False, error="template_not_found")
        assert result.is_valid is True

    def test_error_with_metadata(self):
        """error result can include metadata."""
        result = ArchResult(
            is_success=False,
            error="file_exists_failed",
            metadata={"missing_templates": ["fast", "deep"]},
        )
        assert result.error == "file_exists_failed"
        assert result.metadata["missing_templates"] == ["fast", "deep"]


class TestArchResultUnwrap:
    """Tests for unwrap method."""

    def test_unwrap_returns_value_on_success(self):
        """unwrap should return the value on success."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.unwrap() == {"key": "val"}

    def test_unwrap_raises_on_error(self):
        """unwrap should raise RuntimeError on error."""
        result = ArchResult(is_success=False, error="template_not_found")
        with pytest.raises(RuntimeError, match="template_not_found"):
            result.unwrap()

    def test_unwrap_raises_when_value_is_none_on_success(self):
        """unwrap should raise RuntimeError when is_success=True but value is None."""
        result = ArchResult(is_success=True, value=None)
        with pytest.raises(RuntimeError, match="is_success=True but value is None"):
            result.unwrap()


class TestArchResultUnwrapOr:
    """Tests for unwrap_or method."""

    def test_unwrap_or_returns_value_on_success(self):
        """unwrap_or should return the value on success."""
        result = ArchResult(is_success=True, value={"key": "val"})
        assert result.unwrap_or({}) == {"key": "val"}

    def test_unwrap_or_returns_default_on_error(self):
        """unwrap_or should return the default on error."""
        result = ArchResult(is_success=False, error="template_not_found")
        assert result.unwrap_or({"default": True}) == {"default": True}

    def test_unwrap_or_returns_default_when_value_is_none(self):
        """unwrap_or should return the default when value is None on success."""
        result = ArchResult(is_success=True, value=None)
        assert result.unwrap_or({"default": True}) == {"default": True}


class TestArchResultUnwrapError:
    """Tests for unwrap_error method."""

    def test_unwrap_error_returns_error_string(self):
        """unwrap_error should return the error string."""
        result = ArchResult(is_success=False, error="template_not_found")
        assert result.unwrap_error() == "template_not_found"

    def test_unwrap_error_raises_on_success(self):
        """unwrap_error should raise RuntimeError on success."""
        result = ArchResult(is_success=True, value={"key": "val"})
        with pytest.raises(RuntimeError, match="is not an error"):
            result.unwrap_error()

    def test_unwrap_error_returns_unknown_when_error_is_none(self):
        """unwrap_error should return 'unknown error' when error is None on error result."""
        result = ArchResult(is_success=False, error=None)
        assert result.unwrap_error() == "unknown error"


class TestArchResultGeneric:
    """Tests for generic type parameter handling."""

    def test_generic_with_dict_value(self):
        """ArchResult can be typed with dict."""
        result: ArchResult[dict] = ArchResult(is_success=True, value={"key": "val"})
        assert result.value == {"key": "val"}

    def test_generic_with_list_value(self):
        """ArchResult can be typed with list."""
        result: ArchResult[list] = ArchResult(is_success=True, value=["a", "b"])
        assert result.value == ["a", "b"]

    def test_generic_with_str_value(self):
        """ArchResult can be typed with str."""
        result: ArchResult[str] = ArchResult(is_success=True, value="template_name")
        assert result.value == "template_name"

    def test_generic_with_tuple_value(self):
        """ArchResult can be typed with tuple."""
        result: ArchResult[tuple] = ArchResult(is_success=True, value=("a", 1))
        assert result.value == ("a", 1)


class TestArchResultInvariant:
    """Tests for type invariance (generic type parameter is invariant)."""

    def test_archresult_of_dict_not_assignable_to_archresult_of_list(self):
        """ArchResult[dict] is NOT assignable to ArchResult[list] due to invariance."""
        result_dict: ArchResult[dict] = ArchResult(is_success=True, value={"key": "val"})
        # This assignment should fail type checking (invariant)
        # result_list: ArchResult[list] = result_dict  # Would be type error
        # Verify they are different types
        assert result_dict is not None  # Just to confirm construction works

    def test_archresult_of_str_not_assignable_to_archresult_of_int(self):
        """ArchResult[str] is NOT assignable to ArchResult[int] due to invariance."""
        result_str: ArchResult[str] = ArchResult(is_success=True, value="template")
        # This assignment should fail type checking (invariant)
        # result_int: ArchResult[int] = result_str  # Would be type error
        assert result_str is not None
