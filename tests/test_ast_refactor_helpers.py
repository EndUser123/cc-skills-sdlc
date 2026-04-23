"""Tests for ast_refactor_helpers."""

import tempfile
from pathlib import Path

import pytest

# Import from scripts using correct path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "refactor"))

from scripts.ast_refactor_helpers import (
    TransformResult,
    LibCSTTransformer,
    safe_transform_file,
    RenameAttribute,
    RemoveUnusedImport,
    extract_method_callsafe,
    diff_sources,
)


class DummyTransformer(LibCSTTransformer):
    """Transformer that just tracks visits."""

    def __init__(self) -> None:
        super().__init__()
        self.visited: list[str] = []

    def visit_Name(self, node) -> None:
        self.visited.append(node.value)


class TestSafeTransformFile:
    """Tests for safe_transform_file."""

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        result = safe_transform_file(tmp_path / "nonexistent.py", DummyTransformer)
        assert result.success is False
        assert "not found" in result.error

    def test_valid_file_parses_and_transforms(self, tmp_path: Path) -> None:
        """Transform RenameAttribute renames an attribute in a simple class."""
        src = "class C:\n  x: int = 1\n  def foo(self):\n    return self.old_name\n"
        f = tmp_path / "x.py"
        f.write_text(src)

        result = safe_transform_file(f, RenameAttribute, old_name="old_name", new_name="new_name")
        assert result.success is True
        assert result.changed is True
        assert "new_name" in result.new_source
        assert "old_name" not in result.new_source

    def test_no_change_returns_changed_false(self, tmp_path: Path) -> None:
        src = "x = 1\n"
        f = tmp_path / "x.py"
        f.write_text(src)

        result = safe_transform_file(f, RenameAttribute, old_name="old_name", new_name="new_name")
        assert result.success is True
        assert result.changed is False

    def test_invalid_python_returns_parse_error(self, tmp_path: Path) -> None:
        src = "def f(:\\n  pass\\n"
        f = tmp_path / "x.py"
        f.write_text(src)

        result = safe_transform_file(f, DummyTransformer)
        assert result.success is False
        assert "Parse error" in result.error


class TestExtractMethodCallsafe:
    """Tests for extract_method_callsafe."""

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        result = extract_method_callsafe(tmp_path / "nonexistent.py", "foo", "new_foo")
        assert result.success is False
        assert "not found" in result.error

    def test_nonexistent_function_returns_error(self, tmp_path: Path) -> None:
        src = "def other():\n  pass\n"
        f = tmp_path / "x.py"
        f.write_text(src)

        result = extract_method_callsafe(f, "nonexistent", "new_func")
        assert result.success is False
        assert "not found" in result.error


class TestDiffSources:
    """Tests for diff_sources."""

    def test_diff_shows_changes(self) -> None:
        old = "x = 1\\n"
        new = "x = 2\\n"
        diff = diff_sources(old, new, "x.py")
        assert "---" in diff
        assert "+++" in diff
        assert "-x = 1" in diff
        assert "+x = 2" in diff

    def test_diff_empty_when_identical(self) -> None:
        src = "x = 1\\n"
        diff = diff_sources(src, src, "x.py")
        assert diff == ""
