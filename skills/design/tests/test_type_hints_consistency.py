"""
Failing tests for type hint consistency in validate_templates.py (QUAL-002).

These tests verify Python 3.9+ style type hints are used consistently.

Run with: pytest P:/.claude/skills/arch/tests/test_type_hints_consistency.py -v

EXPECTED BEHAVIOR:
- BEFORE refactoring: Tests FAIL (old-style typing imports present)
- AFTER refactoring: Tests PASS (built-in generics used, old imports removed)
"""

import ast
import pytest
from pathlib import Path


class TestTypeHintConsistency:
    """Tests for Python 3.9+ type hint style compliance."""

    @pytest.fixture
    def module_path(self) -> Path:
        """Path to validate_templates.py."""
        return Path(__file__).parent.parent / "validate_templates.py"

    @pytest.fixture
    def module_source(self, module_path: Path) -> str:
        """Read the source code of validate_templates.py."""
        return module_path.read_text(encoding="utf-8")

    @pytest.fixture
    def module_ast(self, module_source: str) -> ast.Module:
        """Parse the module into an AST."""
        return ast.parse(module_source)

    def test_no_old_typing_imports(self, module_ast: ast.Module):
        """
        Test that old-style typing generics are NOT imported.

        Python 3.9+ uses built-in generics (dict, list, tuple) instead of
        typing.Dict, typing.List, typing.Tuple.

        FAILS if: Dict, List, or Tuple are imported from typing
        PASSES if: Only Optional, Any, cast are imported from typing
        """
        typing_imports = []
        for node in ast.walk(module_ast):
            if isinstance(node, ast.ImportFrom):
                if node.module == "typing":
                    for alias in node.names:
                        typing_imports.append(alias.name)

        # These should NOT be imported after refactoring to Python 3.9+ style
        old_generics = {"Dict", "List", "Tuple"}

        # Assert that old generics are NOT in imports (will FAIL before refactoring)
        assert not old_generics.intersection(set(typing_imports)), (
            f"Old-style generics {old_generics & set(typing_imports)} found in imports: {typing_imports}. "
            f"Use built-in dict, list, tuple instead of typing.Dict, typing.List, typing.Tuple"
        )

    def test_list_syntax_uses_lowercase(self, module_source: str):
        """
        Test that list type hints use lowercase list[str] not List[str].

        FAILS if: "List[" is found in source code
        PASSES if: only "list[" is used
        """
        has_old_list = "List[" in module_source
        has_new_list = "list[" in module_source

        # Should not have old-style List[str]
        assert not has_old_list, (
            "Found old-style List[str] in source. Use list[str] instead."
        )

    def test_dict_syntax_uses_lowercase(self, module_source: str):
        """
        Test that dict type hints use lowercase dict[K,V] not Dict[K,V].

        FAILS if: "Dict[" is found in source code
        PASSES if: only "dict[" is used
        """
        has_old_dict = "Dict[" in module_source

        # Should not have old-style Dict[K, V]
        assert not has_old_dict, (
            "Found old-style Dict[K, V] in source. Use dict[K, V] instead."
        )

    def test_tuple_syntax_uses_lowercase(self, module_source: str):
        """
        Test that tuple type hints use lowercase tuple[...] not Tuple[...].

        FAILS if: "Tuple[" is found in source code
        PASSES if: only "tuple[" is used
        """
        has_old_tuple = "Tuple[" in module_source

        # Should not have old-style Tuple[...]
        assert not has_old_tuple, (
            "Found old-style Tuple[...] in source. Use tuple[...] instead."
        )

    def test_necessary_typing_imports_remain(self, module_ast: ast.Module):
        """
        Test that necessary typing imports are preserved.

        These have no built-in equivalent and should remain:
        - Optional (until Python 3.10+ | syntax)
        - Any (no built-in equivalent)
        - cast (utility function, not a type)

        This test should ALWAYS pass (before and after refactoring).
        """
        typing_imports = []
        for node in ast.walk(module_ast):
            if isinstance(node, ast.ImportFrom):
                if node.module == "typing":
                    for alias in node.names:
                        typing_imports.append(alias.name)

        necessary = {"Optional", "Any", "cast"}

        # These should ALWAYS be present (before and after refactoring)
        assert necessary.issubset(set(typing_imports)), (
            f"Required typing imports {necessary - set(typing_imports)} not found in {typing_imports}"
        )
