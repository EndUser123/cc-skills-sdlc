"""Test that SKILL.md code examples are valid and match actual implementation.

This test catches "documentation drift" where SKILL.md shows code examples
that reference non-existent functions or incorrect import paths.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


def extract_python_blocks_from_skill_md() -> list[dict]:
    """Extract Python code blocks from SKILL.md.

    Returns:
        List of dicts with 'code' (str), 'line_number' (int), 'context' (str)
    """
    skill_md_path = Path(__file__).parent.parent / "SKILL.md"
    content = skill_md_path.read_text()

    # Find all ```python blocks
    pattern = r"```python\n(.*?)```"
    matches = re.finditer(pattern, content, re.DOTALL)

    blocks = []
    for match in matches:
        code = match.group(1).strip()
        line_num = content[:match.start()].count("\n") + 1
        # Get surrounding context for error messages
        lines = content.split("\n")
        context_start = max(0, line_num - 3)
        context_end = min(len(lines), line_num + 2)
        context = "\n".join(lines[context_start:context_end])

        blocks.append({"code": code, "line_number": line_num, "context": context})

    return blocks


def validate_imports_exist(code: str, line_number: int) -> list[str]:
    """Check that all imports in a code block could resolve.

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []

    # Known valid local modules
    valid_local_modules = {
        "layers.layer0_predictive",
        "layers.layer1_syntactic",
        "layers.layer2_semantic",
        "layers.layer3_structural",
        "layers.layer4_requirements",
        "layers.layer5_security",
        "layers.layer6_performance",
        "layers.layer7_operational",
        "layers.layer_meta",
        "lib.sqa_state_tracker",
        "lib.sqa_evidence_patterns",
        "findings.models",
        "orchestrator",
    }

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Line {line_number}: Syntax error in SKILL.md code block: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                try:
                    __import__(module_name.split(".")[0])
                except ImportError:
                    # Check if it's a local import
                    if module_name.startswith("layers.") or module_name.startswith("lib.") or module_name.startswith("findings."):
                        # Local import - verify module exists
                        module_path = Path(__file__).parent.parent / (module_name.replace(".", "/") + ".py")
                        if not module_path.exists() and module_name not in valid_local_modules:
                            errors.append(
                                f"Line {line_number}: Local import '{module_name}' not found at {module_path}"
                            )
                    else:
                        errors.append(f"Line {line_number}: Cannot import '{module_name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module
                if module_name.startswith("layers.") or module_name.startswith("lib.") or module_name.startswith("findings."):
                    # Check against known valid modules
                    if module_name in valid_local_modules:
                        continue
                    # Local import - verify module exists
                    module_path = Path(__file__).parent.parent / (module_name.replace(".", "/") + ".py")
                    if not module_path.exists():
                        # Also check for __init__.py packages
                        init_path = Path(__file__).parent.parent / module_name.replace(".", "/") / "__init__.py"
                        if not init_path.exists():
                            errors.append(
                                f"Line {line_number}: Local import 'from {module_name}' not found (checked {module_path} and {init_path})"
                            )

    return errors


def validate_functions_exist(code: str, line_number: int) -> list[str]:
    """Check that functions called in code blocks actually exist.

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # Already reported by validate_imports_exist

    # First, collect all functions defined INLINE in this code block
    inline_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            inline_functions.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            inline_functions.add(node.name)

    # Collect all function calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                # Skip if defined inline in this same block
                if func_name in inline_functions:
                    continue
                # Skip builtins
                if func_name in ["print", "len", "str", "int", "Path", "list", "dict", "set", "range", "enumerate", "zip", "open", "json", "time", "sys", "os", "subprocess"]:
                    continue
                # Check if it's a known local function pattern
                if func_name.startswith("_") and not func_name.startswith("__"):
                    # Private function - check if it exists in local modules
                    found = False
                    for module_file in Path(__file__).parent.parent.rglob("*.py"):
                        content = module_file.read_text()
                        if f"def {func_name}(" in content:
                            found = True
                            break
                    if not found:
                        errors.append(
                            f"Line {line_number}: Function '{func_name}()' called but not found in any local module"
                        )
            elif isinstance(node.func, ast.Attribute):
                # Method call like module.function()
                if isinstance(node.func.value, ast.Name):
                    module_name = node.func.value.id
                    func_name = node.func.attr
                    # Skip builtins
                    if module_name in ["json", "Path", "sys", "os", "time", "subprocess"]:
                        continue
                    # Check if it's defined inline
                    if func_name in inline_functions:
                        continue
                    # Special check for sqa_state_tracker functions
                    if func_name in ["get_rns_summary", "get_accumulated_findings", "record_layer_complete", "record_halt", "add_findings", "init_state"]:
                        # These are imported from sqa_state_tracker
                        continue

    return errors


def test_skill_md_python_blocks_are_valid():
    """Test that all Python code blocks in SKILL.md are syntactically valid."""
    blocks = extract_python_blocks_from_skill_md()

    assert len(blocks) > 0, "No Python code blocks found in SKILL.md"

    all_errors = []
    for block in blocks:
        # Check syntax
        try:
            ast.parse(block["code"])
        except SyntaxError as e:
            all_errors.append(f"Line {block['line_number']}: Syntax error: {e}")
            continue

        # Check imports
        import_errors = validate_imports_exist(block["code"], block["line_number"])
        all_errors.extend(import_errors)

        # Check function calls
        function_errors = validate_functions_exist(block["code"], block["line_number"])
        all_errors.extend(function_errors)

    if all_errors:
        error_msg = "SKILL.md code block validation failed:\n\n" + "\n".join(all_errors)
        raise AssertionError(error_msg)


def test_skill_md_layers_documented_functions_exist():
    """Test that functions documented in SKILL.md 'Your Workflow' section actually exist.

    This catches drift where SKILL.md says "run via X" but X doesn't exist.
    """
    skill_md_path = Path(__file__).parent.parent / "SKILL.md"
    content = skill_md_path.read_text()

    errors = []

    # Look for patterns like "via `_run_ruff()`" or "via `some_function()`"
    function_pattern = r'via `(_?[\w]+)\('
    matches = re.finditer(function_pattern, content)

    for match in matches:
        func_name = match.group(1)
        line_num = content[:match.start()].count("\n") + 1

        # Skip builtins and known external commands
        if func_name in ["print", "len", "str", "int", "Path", "list"]:
            continue

        # Search for the function in local modules
        found = False
        for module_file in Path(__file__).parent.parent.rglob("*.py"):
            content = module_file.read_text()
            if f"def {func_name}(" in content or f"def {func_name}(" in content:
                found = True
                break

        if not found:
            errors.append(
                f"Line {line_num}: SKILL.md references function '{func_name}()' but it doesn't exist in codebase"
            )

    if errors:
        error_msg = "SKILL.md documents non-existent functions:\n\n" + "\n".join(errors)
        raise AssertionError(error_msg)
