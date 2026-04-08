#!/usr/bin/env python3
"""Tests for Pre-Execution Checklist integration - RED phase (failing tests)."""

import sys
from pathlib import Path

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import checklist module (doesn't exist yet - will cause import error)
try:
    from lib.checklist import ChecklistValidationError, validate_checklist

    CHECKLIST_AVAILABLE = True
except ImportError:
    CHECKLIST_AVAILABLE = False
    validate_checklist = None
    ChecklistValidationError = None


class TestPreExecutionChecklist:
    """Test pre-execution checklist integration - NEW FUNCTIONALITY."""

    def test_checklist_step_in_workflow(self):
        """Checklist step should exist in workflow_steps."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        # Load frontmatter properly
        with open(skill_path) as f:
            lines = []
            in_frontmatter = False
            for line in f:
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                        continue
                    else:
                        break
                if in_frontmatter:
                    lines.append(line)

            frontmatter_text = "".join(lines)
            frontmatter = yaml.safe_load(frontmatter_text)

        workflow_steps = frontmatter.get("workflow_steps", [])

        # Check that pre_execution_checklist step exists
        step_names = [
            step if isinstance(step, str) else step.get("id", step.get("name", ""))
            for step in workflow_steps
        ]

        assert (
            "pre_execution_checklist" in step_names
        ), "pre_execution_checklist should be in workflow_steps"

    def test_checklist_step_before_analyze_query_intent(self):
        """Checklist step should come before analyze_query_intent."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        # Load frontmatter properly
        with open(skill_path) as f:
            lines = []
            in_frontmatter = False
            for line in f:
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                        continue
                    else:
                        break
                if in_frontmatter:
                    lines.append(line)

            frontmatter_text = "".join(lines)
            frontmatter = yaml.safe_load(frontmatter_text)

        workflow_steps = frontmatter.get("workflow_steps", [])

        # Get step names
        step_names = [
            step if isinstance(step, str) else step.get("id", step.get("name", ""))
            for step in workflow_steps
        ]

        # Find indices
        checklist_idx = (
            step_names.index("pre_execution_checklist")
            if "pre_execution_checklist" in step_names
            else -1
        )
        analyze_idx = (
            step_names.index("analyze_query_intent") if "analyze_query_intent" in step_names else -1
        )

        assert checklist_idx >= 0, "pre_execution_checklist step should exist"
        assert analyze_idx >= 0, "analyze_query_intent step should exist"
        assert (
            checklist_idx < analyze_idx
        ), "pre_execution_checklist should come before analyze_query_intent"

    def test_no_checklist_flag_exists(self):
        """--no-checklist flag should exist in argument-hint."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            for line in f:
                if line.startswith("argument-hint:"):
                    argument_hint = line.split(":", 1)[1].strip()
                    assert (
                        "--no-checklist" in argument_hint
                    ), "--no-checklist flag should be in argument-hint"
                    return

        pytest.fail("argument-hint not found in SKILL.md")

    def test_checklist_documented_in_skill(self):
        """Checklist should be documented in skill content."""
        skill_path = Path(__file__).parent.parent / "SKILL.md"

        with open(skill_path) as f:
            content = f.read()

        # Check for checklist section
        assert (
            "Pre-Execution Checklist" in content or "pre-execution checklist" in content.lower()
        ), "Checklist should be documented in skill content"

    def test_checklist_questions_defined(self):
        """5 questions should be defined for checklist."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        # This test will be updated in GREEN phase to check actual questions
        # For now, just verify the module exists (which it doesn't yet)
        assert validate_checklist is not None, "validate_checklist function should exist"

    def test_checklist_validation_module_exists(self):
        """Checklist validation module should exist."""
        module_path = Path(__file__).parent.parent / "lib" / "checklist.py"

        assert module_path.exists(), f"Checklist module should exist at {module_path}"

    def test_checklist_validate_function_exists(self):
        """validate_checklist function should exist and be callable."""
        if not CHECKLIST_AVAILABLE:
            pytest.skip("checklist module not available - expected for RED phase")

        assert callable(validate_checklist), "validate_checklist should be a callable function"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
