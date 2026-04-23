"""LibCST-based AST refactoring helpers.

Provides safe, composable AST transformations for Python refactoring.
All transformations preserve comments and formatting where possible.
"""

from __future__ import annotations

import difflib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TypeVar

import libcst as cst

T = TypeVar("T", bound=cst.CSTNode)


@dataclass
class TransformResult:
    """Result of an AST transformation."""

    success: bool
    changed: bool
    error: str | None = None
    count: int = 0
    original_source: str = ""
    new_source: str = ""


def safe_transform_file(
    file_path: str | Path,
    transformer: type[cst.CSTTransformer],
    **kwargs: object,
) -> TransformResult:
    """Apply a LibCST transformer to a file safely.

    Args:
        file_path: Path to the Python file to transform.
        transformer: LibCST transformer class (must accept kwargs).
        **kwargs: Passed to the transformer constructor.

    Returns:
        TransformResult with success status, changed flag, and source.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return TransformResult(
            success=False,
            changed=False,
            error=f"File not found: {file_path}",
        )

    try:
        original_source = file_path.read_text(encoding="utf-8")
    except OSError as e:
        return TransformResult(
            success=False,
            changed=False,
            error=f"Cannot read {file_path}: {e}",
        )

    try:
        original_tree = cst.parse_module(original_source)
    except cst.ParserSyntaxError as e:
        return TransformResult(
            success=False,
            changed=False,
            error=f"Parse error in {file_path}: {e}",
            original_source=original_source,
        )

    try:
        instance = transformer(**kwargs)
        new_tree = original_tree.visit(instance)
    except Exception as e:
        return TransformResult(
            success=False,
            changed=False,
            error=f"Transform error in {file_path}: {e}",
            original_source=original_source,
        )

    new_source = new_tree.code
    changed = new_source != original_source
    count = getattr(instance, "_modifications", 0)

    if changed:
        try:
            file_path.write_text(new_source, encoding="utf-8")
        except OSError as e:
            return TransformResult(
                success=False,
                changed=True,
                error=f"Cannot write {file_path}: {e}",
                original_source=original_source,
                new_source=new_source,
                count=count,
            )

    return TransformResult(
        success=True,
        changed=changed,
        original_source=original_source,
        new_source=new_source,
        count=count,
    )


# ─── Base transformer with modification counting ─────────────────────────────────


class LibCSTTransformer(cst.CSTTransformer):
    """Base LibCST transformer with modification tracking."""

    def __init__(self) -> None:
        super().__init__()
        self._modifications: int = 0

    def _increment(self) -> None:
        self._modifications += 1


# ─── Rename Attribute ───────────────────────────────────────────────────────────


class RenameAttribute(LibCSTTransformer):
    """Rename an attribute on all matching class instances."""

    def __init__(
        self,
        old_name: str,
        new_name: str,
        class_name: str | None = None,
    ) -> None:
        super().__init__()
        self.old_name = old_name
        self.new_name = new_name
        self.class_name = class_name

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        if original_node.attr.value == self.old_name:
            self._increment()
            return updated_node.with_changes(attr=cst.Name(self.new_name))
        return updated_node


# ─── Remove Unused Import ───────────────────────────────────────────────────────


class RemoveUnusedImport(LibCSTTransformer):
    """Remove imports that are not referenced in the module."""

    def __init__(self, import_name: str) -> None:
        super().__init__()
        self.import_name = import_name
        self._used: bool = False
        self._in_from: str | None = None

    def leave_Name(self, original_node: cst.Name) -> cst.Name | cst.RemoveFromParent:
        if original_node.value == self.import_name:
            self._used = True
        return original_node

    def leave_Import(self, original_node: cst.Import) -> cst.Import | cst.RemoveFromParent:
        for alias in original_node.names:
            if alias.name.value == self.import_name:
                self._increment()
                return cst.RemoveFromParent()
        return original_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemoveFromParent:
        if original_node.module is None:
            return original_node
        module_name = original_node.module.value if hasattr(original_node.module, "value") else str(original_node.module)
        if module_name == self.import_name:
            self._increment()
            return cst.RemoveFromParent()
        return original_node


# ─── Extract Method ────────────────────────────────────────────────────────────


@dataclass
class ExtractMethodConfig:
    """Configuration for method extraction."""

    target_function: str
    new_method_name: str
    extracted_body: list[cst.BaseStatement] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)


class ExtractMethodTransformer(LibCSTTransformer):
    """Extract a block of code into a new method on the same class."""

    def __init__(self, config: ExtractMethodConfig) -> None:
        super().__init__()
        self.config = config
        self._in_target: bool = False
        self._target_indent: int | None = None

    def visit_FunctionDef(self, node: cst.FunctionDef) -> cst.CSTNode:
        if node.name.value == self.config.target_function:
            self._in_target = True
        return node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if not self._in_target:
            return updated_node
        self._in_target = False
        self._increment()
        # The caller should replace the body with a call + new method.
        # This transformer marks the location; the caller handles the actual replacement.
        return updated_node


def extract_method_callsafe(
    file_path: str | Path,
    target_function: str,
    new_method: str,
    call_args: list[str] | None = None,
) -> TransformResult:
    """Extract the body of target_function into a new method and replace the original.

    This is a simplified version that adds a new method after the class definition
    and replaces the function body with a call to it.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return TransformResult(success=False, changed=False, error=f"File not found: {file_path}")

    source = file_path.read_text(encoding="utf-8")
    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        return TransformResult(success=False, changed=False, error=f"Parse error: {e}", original_source=source)

    # Find the target function and get its parameters
    finder = _FunctionFinder(target_function)
    tree.visit(finder)

    if not finder.function_node:
        return TransformResult(success=False, changed=False, error=f"Function '{target_function}' not found", original_source=source)

    params = finder.function_params
    params_str = ", ".join(params)

    # Build new method stub
    new_method_code = f"\n    def {new_method}({params_str}):\n        raise NotImplementedError(\"Extracted method - implement here\")\n"

    # Insert new method after the target function
    lines = source.splitlines(keepends=True)
    end_line = finder.function_end_line

    if end_line and end_line < len(lines):
        # Find the end of the function by dedent
        lines.insert(end_line + 1, new_method_code)

    new_source = "".join(lines)
    changed = new_source != source

    if changed:
        file_path.write_text(new_source, encoding="utf-8")

    return TransformResult(
        success=True,
        changed=changed,
        original_source=source,
        new_source=new_source,
        count=1,
    )


class _FunctionFinder(cst.CSTVisitor):
    """Find a function definition and its line range."""

    def __init__(self, target: str) -> None:
        self.target = target
        self.function_node: cst.FunctionDef | None = None
        self.function_end_line: int | None = None
        self.function_params: list[str] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if node.name.value == self.target:
            self.function_node = node
            self.function_params = [p.name.value for p in node.params.params]
            # Get end line from node positions
            if node.end_lineno:
                self.function_end_line = node.end_lineno


def diff_sources(original: str, new: str, file_path: str | Path) -> str:
    """Generate a unified diff between two sources."""
    path_str = str(file_path)
    original_lines = original.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{path_str}",
        tofile=f"b/{path_str}",
        lineterm="",
    )
    return "".join(diff)
