#!/usr/bin/env python3
"""Incremental testing based on code flow tracing."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def map_modules_to_tests(codemap: dict[str, Any]) -> dict[str, list[str]]:
    """
    Map modules to their corresponding test files.

    Uses codemap.file_references to find which test files reference each module.

    Args:
        codemap: Codemap from enhance_command.create_codemap()

    Returns:
        Dictionary mapping module paths to lists of test file paths
    """
    module_tests: dict[str, list[str]] = {}

    # Get all test files from codemap
    test_files = codemap.get("file_structure", {}).get("test_files", [])

    for test_file in test_files:
        test_path = Path(test_file)
        try:
            content = test_path.read_text()
        except Exception:
            continue

        # Find all modules referenced in this test
        for module, refs in codemap.get("relationships", {}).get("file_references", {}).items():
            if module in content:
                module_tests.setdefault(module, []).append(str(test_path))

    return module_tests


def calculate_incremental_scope(
    target_files: list[str], codemap: dict[str, Any]
) -> dict[str, Any]:
    """
    Calculate which tests to run based on code flow from changed files.

    Returns:
        Dictionary with:
        - total_tests: Total number of tests
        - affected_tests: List of affected test files
        - skipped_tests: List of skipped test files
        - time_saved_seconds: Estimated time saved
        - dependency_chain: List of affected modules
    """
    # Get module->test mapping
    module_tests = map_modules_to_tests(codemap)

    # Find all affected modules via dependency graph
    affected_modules: set[str] = set()

    for target_file in target_files:
        # Add the target file itself
        affected_modules.add(target_file)

        # Add upstream dependencies (what this file imports)
        imports = codemap.get("relationships", {}).get("python_imports", {}).get(target_file, [])
        affected_modules.update(imports)

        # Add downstream consumers (what imports this file)
        for module, refs in codemap.get("relationships", {}).get("python_imports", {}).items():
            if target_file in refs:
                affected_modules.add(module)

    # Collect all tests for affected modules
    affected_tests: set[str] = set()
    for module in affected_modules:
        affected_tests.update(module_tests.get(module, []))

    # Get total test count (all test files)
    all_test_files = codemap.get("file_structure", {}).get("test_files", [])
    total_tests = len(all_test_files)

    return {
        "total_tests": total_tests,
        "affected_tests": sorted(list(affected_tests)),
        "skipped_tests": [f for f in all_test_files if f not in affected_tests],
        "time_saved_seconds": (total_tests - len(affected_tests)) * 0.5,
        "dependency_chain": sorted(list(affected_modules)),
    }


def format_incremental_report(scope: dict[str, Any]) -> str:
    """Format incremental test scope report."""
    lines = [
        "## Incremental Test Scope",
        "",
        f"Changed files affect {len(scope['affected_tests'])} tests (vs {scope['total_tests']} total)",
        f"Estimated time saved: {scope['time_saved_seconds']:.1f} seconds",
        "",
        "### Dependency Chain:",
    ]

    for module in scope["dependency_chain"][:10]:
        lines.append(f"- {module}")

    if len(scope["dependency_chain"]) > 10:
        lines.append(f"- ... and {len(scope['dependency_chain']) - 10} more")

    lines.extend(["", f"### Tests to Run ({len(scope['affected_tests'])}):"])

    for test in scope["affected_tests"][:10]:
        lines.append(f"- {Path(test).name}")

    if len(scope["affected_tests"]) > 10:
        lines.append(f"- ... and {len(scope['affected_tests']) - 10} more")

    return "\n".join(lines)
