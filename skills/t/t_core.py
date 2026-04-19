#!/usr/bin/env python3
"""
Core context extraction and codemap integration for /t command.

Implements conversation-based context detection and codemap reuse.

TEST EDIT: Added this comment to verify change detection works.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _ensure_import_paths() -> None:
    """Ensure CSF modules are in sys.path."""
    for candidate in ("P:/__csf/src", "P:/__csf", "P:/"):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


@dataclass
class WorkContext:
    """Context extracted from conversation about what's being worked on."""

    target_files: list[str] = field(default_factory=list)
    work_type: str = ""
    affected_modules: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    information_flow: list[tuple[str, str]] = field(default_factory=list)
    codemap: dict[str, Any] = field(default_factory=dict)


def extract_context_from_conversation() -> WorkContext:
    """
    Extract work context from conversation history.

    The LLM already knows what we're working on from the conversation.
    This function parses that context to determine:
    - What files are being modified
    - What type of work is happening
    - What dependencies exist

    Implementation:
        1. Analyze recent conversation for file mentions
        2. Identify work type from keywords (fixing, adding, refactoring)
        3. Extract module names from file paths
        4. Generate codemap using existing enhance_command.create_codemap()
        5. Return WorkContext with all discovered context

    Returns:
        WorkContext with conversation-derived information and codemap
    """
    _ensure_import_paths()

    try:
        # Import enhance_command for codemap generation
        from commands.cb.enhance_command import FourLayerCommandEnhancer

        # Create enhancer instance (no parameters needed)
        enhancer = FourLayerCommandEnhancer()

        # Discover all files in project for codemap generation
        project_path = Path.cwd()
        discovered = enhancer.discover_command_files(
            command_name="t_analysis",
            search_paths=[project_path]
        )

        # Generate codemap using existing infrastructure
        codemap = enhancer.create_codemap(
            command_name="t_analysis",
            discovered_files=discovered
        )

        # Extract target files from file structure
        target_files = []
        file_structure = codemap.get("file_structure", {})
        main_files = file_structure.get("main_files", [])

        # Filter to Python source files only
        for file_path in main_files:
            if file_path.endswith(".py"):
                target_files.append(file_path)

        # Infer work type from git state if available
        work_type = _infer_work_type_from_git(project_path)

        # Trace code flow using existing codemap
        affected_modules, information_flow = trace_code_flow(target_files, codemap)

        # Extract dependencies from relationships
        dependencies = []
        relationships = codemap.get("relationships", {})
        python_imports = relationships.get("python_imports", {})

        for file_path in target_files:
            imports = python_imports.get(file_path, [])
            dependencies.extend(imports)

        # Deduplicate
        dependencies = list(set(dependencies))

        return WorkContext(
            target_files=target_files,
            work_type=work_type,
            affected_modules=affected_modules,
            dependencies=dependencies,
            information_flow=information_flow,
            codemap=codemap,
        )

    except Exception as e:
        # Graceful degradation: return empty context on error
        print(f"Warning: Context extraction failed: {e}")
        return WorkContext(
            target_files=[],
            work_type="unknown",
            affected_modules=[],
            dependencies=[],
            information_flow=[],
            codemap={},
        )


def _infer_work_type_from_git(project_path: Path) -> str:
    """Infer work type from git state (unstaged, staged, etc.)."""
    try:
        import subprocess

        # Check for unstaged changes
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=project_path,
            capture_output=True,
            timeout=5,
        )
        if result.stdout.strip():
            return "feature"

        # Check for staged changes
        result = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            cwd=project_path,
            capture_output=True,
            timeout=5,
        )
        if result.stdout.strip():
            return "feature"

        # Default to refactor if clean tree
        return "refactor"

    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        # No git available
        return "unknown"


def trace_code_flow(
    target_files: list[str], codemap: dict[str, Any]
) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Trace code flow and dependencies using existing codemap.

    For each target file, determine:
    - What modules does it import/depend on? (from codemap.relationships)
    - What modules depend on it? (from codemap.relationships)
    - What information flows through it?

    Implementation:
        1. Extract relationships from existing codemap
        2. Build dependency graph from codemap.relationships
        3. Trace information flow patterns using python_imports and file_references

    Args:
        target_files: List of files to trace
        codemap: Codemap from enhance_command.create_codemap()

    Returns:
        Tuple of (affected_modules, information_flow)

    Example:
        target_files = ["router.py"]
        codemap = generate_codemap("test_command")
        → affected_modules = codemap["relationships"]["python_imports"]["router.py"]
        → information_flow = codemap["relationships"]["file_references"]

    Note: Reuses existing codemap infrastructure from enhance_command.create_codemap()
    """
    affected_modules: list[str] = []
    information_flow: list[tuple[str, str]] = []

    if not codemap:
        return affected_modules, information_flow

    relationships = codemap.get("relationships", {})
    python_imports = relationships.get("python_imports", {})
    file_references = relationships.get("file_references", {})

    for target_file in target_files:
        # Get upstream dependencies (what this file imports)
        imports = python_imports.get(target_file, [])
        affected_modules.extend(imports)

        # Get downstream consumers (what imports this file)
        for module, refs in python_imports.items():
            if target_file in refs:
                affected_modules.append(module)

        # Build information flow pairs
        refs = file_references.get(target_file, [])
        for ref in refs:
            information_flow.append((target_file, ref))

    # Deduplicate while preserving order
    seen = set()
    unique_modules = []
    for module in affected_modules:
        if module not in seen:
            seen.add(module)
            unique_modules.append(module)

    return unique_modules, information_flow


def load_testing_config() -> dict[str, Any]:
    """
    Load testing.yml config from project root.

    Returns:
        Config dict, or empty dict if file not found.

    Error handling:
        - If file missing → return {}
        - If YAML invalid → log warning, return {}
        - If validation fails → log warning, use defaults
    """
    config_path = Path("testing.yml")

    if not config_path.exists():
        return {}

    try:
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        return config
    except Exception as e:
        print(f"Warning: Failed to load testing.yml: {e}")
        return {}
