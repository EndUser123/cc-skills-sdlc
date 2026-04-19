"""
Integration tests for validate_templates.py.

These tests verify end-to-end validation workflow using real template files.
Run with: pytest P:/.claude/skills/arch/tests/test_integration_validation.py -v -m integration
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.integration
def test_validate_templates_end_to_end(tmp_path):
    """
    Test that validate_all() completes successfully with real template files.

    This is an end-to-end integration test that:
    1. Creates minimal valid template files in tmp_path
    2. Creates a valid contracts YAML file
    3. Calls validate_all() with the template_dir parameter
    4. Verifies validation completes successfully (returns 0)

    Given: Minimal valid template and contract files in tmp_path
    When: validate_all() is called with template_dir parameter
    Then: Validation returns 0 (success)
    """
    # Import here to avoid import issues
    from validate_templates import validate_all, load_template_content

    # Create resources directory structure
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir()

    # Create minimal valid contracts file
    contracts_file = resources_dir / "template_contracts.yaml"
    contracts_content = """
fast:
  required_headings:
    - "# Quick Architecture Decision"
    - "## Stage 0"
    - "## IMPROVE_SYSTEM"
    - "## DEFAULT"
  must_include:
    - "DECISION:"
    - "RATIONALE:"

deep:
  required_headings:
    - "# Comprehensive Architecture Analysis"
    - "## Stage 0"
    - "## IMPROVE_SYSTEM"
    - "## DEFAULT"
  must_include:
    - "SYSTEMS_THINKING:"

cli:
  required_headings:
    - "# CLI Architecture"
    - "## Stage 0"
    - "## IMPROVE_SYSTEM"
    - "## DEFAULT"
  must_include:
    - "DECISION:"

python:
  required_headings:
    - "# Python Architecture"
    - "## Stage 0"
    - "## IMPROVE_SYSTEM"
    - "## DEFAULT"
  must_include:
    - "DECISION:"

data-pipeline:
  required_headings:
    - "# Data Pipeline Architecture"
    - "## Stage 0"
    - "## IMPROVE_SYSTEM"
    - "## DEFAULT"
  must_include:
    - "DECISION:"

precedent:
  required_headings:
    - "# ADR Documentation Analysis"
    - "## Stage 0"
    - "## IMPROVE_SYSTEM"
    - "## DEFAULT"
  must_include:
    - "STATUS:"
"""
    contracts_file.write_text(contracts_content)

    # Create minimal valid template files
    templates = {
        "fast.md": """# Quick Architecture Decision

## Stage 0
Context gathering stage.

## IMPROVE_SYSTEM
System improvement analysis.

## DEFAULT
Default recommendations.

DECISION: Test decision
RATIONALE: Test rationale
""",
        "deep.md": """# Comprehensive Architecture Analysis

## Stage 0
Deep context gathering.

## IMPROVE_SYSTEM
Deep system analysis.

## DEFAULT
Deep recommendations.

SYSTEMS_THINKING: Dependencies identified
""",
        "cli.md": """# CLI Architecture

## Stage 0
CLI context.

## IMPROVE_SYSTEM
CLI improvements.

## DEFAULT
CLI defaults.

DECISION: CLI recommendation
""",
        "python.md": """# Python Architecture

## Stage 0
Python context.

## IMPROVE_SYSTEM
Python improvements.

## DEFAULT
Python defaults.

DECISION: Python recommendation
""",
        "data-pipeline.md": """# Data Pipeline Architecture

## Stage 0
Data context.

## IMPROVE_SYSTEM
Data improvements.

## DEFAULT
Data defaults.

DECISION: Data recommendation
""",
        "precedent.md": """# ADR Documentation Analysis

## Stage 0
Precedent context.

## IMPROVE_SYSTEM
Precedent improvements.

## DEFAULT
Precedent defaults.

STATUS: PROPOSED
""",
    }

    for template_name, content in templates.items():
        template_path = resources_dir / template_name
        template_path.write_text(content)

    # Clear the cache before running
    load_template_content.cache_clear()

    # Run validation with template_dir parameter
    result = validate_all(template_dir=resources_dir)

    # Assert validation succeeds
    assert result == 0, f"Expected validation to succeed (0), got {result}"
