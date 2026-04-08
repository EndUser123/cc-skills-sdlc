"""
Integration test for external callers of select_template.

This test simulates how external code (outside the arch skill) would import
and use select_template. It catches breaking changes to the function signature.

Purpose: When select_template() signature changes (e.g., return type changes),
external callers break. This test verifies the public API contract.

Run with: pytest P:/.claude/skills/arch/tests/test_external_caller_integration.py -v
"""

import sys
from pathlib import Path
from typing import Any, get_type_hints

# Add parent directories for package imports
test_dir = Path(__file__).parent
skills_dir = test_dir.parent.parent
sys.path.insert(0, str(skills_dir))

import pytest


class TestExternalCallerIntegration:
    """
    Integration tests for external callers of select_template.

    These tests simulate how external code would import and use select_template,
    ensuring breaking changes are caught before they reach production.
    """

    def test_external_import_path_works(self):
        """
        GIVEN: External code imports select_template from skill.routing
        WHEN: Calling select_template with a query
        THEN: Function is callable and returns expected type
        """
        # This simulates how external code would import
        from skill.routing import select_template

        # External caller expects function to be callable
        assert callable(select_template), "select_template must be callable"

        # External caller expects to pass a query string
        result = select_template("redesign api")

        # External caller expects a dict-like return value
        assert isinstance(result, dict), (
            f"select_template must return dict, got {type(result).__name__}"
        )

    def test_external_caller_handles_template_result_dict(self):
        """
        GIVEN: External code calls select_template
        WHEN: Accessing result["template"] key
        THEN: Returns valid template string
        """
        from skill.routing import select_template, VALID_TEMPLATES

        result = select_template("redesign api")

        # External caller accesses result["template"]
        assert "template" in result, (
            "TemplateResult dict must have 'template' key for backward compatibility"
        )

        template = result["template"]
        assert isinstance(template, str), (
            f"result['template'] must be str, got {type(template).__name__}"
        )

        # External caller expects valid template
        assert template in VALID_TEMPLATES, (
            f"result['template'] must be in VALID_TEMPLATES, got '{template}'"
        )

    def test_external_caller_handles_all_template_result_keys(self):
        """
        GIVEN: External code calls select_template
        WHEN: Accessing all TemplateResult keys
        THEN: All expected keys are present
        """
        from skill.routing import select_template

        result = select_template("command line tool")

        # External caller expects these specific keys (TemplateResult contract)
        expected_keys = {"template", "source", "confidence"}

        for key in expected_keys:
            assert key in result, (
                f"TemplateResult dict must have '{key}' key for backward compatibility"
            )

    def test_external_caller_with_template_override(self):
        """
        GIVEN: External code calls select_template with template_override
        WHEN: Passing template_override parameter
        THEN: Returns expected template in TemplateResult dict
        """
        from skill.routing import select_template

        result = select_template("any query", template_override="deep")

        # External caller accesses result["template"]
        assert result["template"] == "deep", (
            f"template_override parameter must work, got '{result['template']}'"
        )

        # External caller checks source
        assert result["source"] == "parameter_override", (
            f"source must be 'parameter_override' when template_override used, got '{result['source']}'"
        )

    def test_external_caller_with_default_domain(self):
        """
        GIVEN: External code calls select_template with default_domain
        WHEN: Passing default_domain parameter
        THEN: Returns expected template in TemplateResult dict
        """
        from skill.routing import select_template

        result = select_template("random query", default_domain="python")

        # External caller accesses result["template"]
        assert result["template"] == "python", (
            f"default_domain parameter must work, got '{result['template']}'"
        )

        # External caller checks source
        assert result["source"] in ["default_domain", "keyword_detection", "complexity_detection"], (
            f"source must indicate domain/detection was used, got '{result['source']}'"
        )

    def test_external_caller_type_annotation_match(self):
        """
        GIVEN: External code checks select_template return type
        WHEN: Getting type hints
        THEN: Return type annotation matches actual return value
        """
        from skill.routing import select_template

        # Get the function's type hints
        type_hints = get_type_hints(select_template)
        return_annotation = type_hints.get("return")

        # External caller expects return type to be properly annotated
        assert return_annotation is not None, (
            "select_template must have return type annotation"
        )

        # Call the function and verify actual return matches annotation
        result = select_template("test query")
        assert isinstance(result, dict), (
            f"Return type annotation {return_annotation} doesn't match actual return {type(result).__name__}"
        )

    def test_external_caller_importlib_import(self):
        """
        GIVEN: External code uses importlib to import select_template
        WHEN: Using dynamic import (common in plugins/extensions)
        THEN: Function works correctly
        """
        import importlib

        # Dynamic import (simulates plugin/extension loading)
        routing_module = importlib.import_module("skill.routing")
        select_template = routing_module.select_template

        # Use the dynamically imported function
        result = select_template("redesign system")

        # Verify it works
        assert isinstance(result, dict), (
            "Dynamically imported select_template must return dict"
        )
        assert "template" in result, (
            "Dynamically imported select_template must return dict with 'template' key"
        )

    def test_breaking_change_catch_old_string_return(self):
        """
        GIVEN: External code expects TemplateResult dict (not str)
        WHEN: select_template is called
        THEN: Return value is NOT a bare string (catches old API)

        This test specifically catches the breaking change from:
        OLD: select_template() -> str
        NEW: select_template() -> TemplateResult (dict)

        If this test fails, it means select_template reverted to returning str.
        """
        from skill.routing import select_template

        result = select_template("test query")

        # CRITICAL: If select_template returns str instead of dict,
        # external callers will crash. This test catches that regression.
        assert not isinstance(result, str), (
            "BREAKING CHANGE: select_template returned str instead of TemplateResult dict. "
            "External code expecting dict will crash. "
            "Update select_template to return TemplateResult dict."
        )

    def test_external_caller_backward_compatibility_batch(self):
        """
        GIVEN: External code has multiple call patterns
        WHEN: Calling select_template with various parameters
        THEN: All calls return TemplateResult dict consistently
        """
        from skill.routing import select_template

        # Common external call patterns
        call_patterns = [
            # (query, kwargs, description)
            ("simple query", {}, "basic query"),
            ("redesign api", {}, "complexity detection"),
            ("command line tool", {}, "keyword detection"),
            ("any query", {"template_override": "deep"}, "template override"),
            ("any query", {"default_domain": "python"}, "default domain"),
            ("any query", {"env_domain": "cli"}, "env domain"),
        ]

        for query, kwargs, description in call_patterns:
            result = select_template(query, **kwargs)

            # All external callers expect dict with specific keys
            assert isinstance(result, dict), (
                f"{description}: select_template must return dict, got {type(result).__name__}"
            )
            assert "template" in result, (
                f"{description}: TemplateResult must have 'template' key"
            )
            assert "source" in result, (
                f"{description}: TemplateResult must have 'source' key"
            )
            assert "confidence" in result, (
                f"{description}: TemplateResult must have 'confidence' key"
            )

    def test_external_caller_chained_domains_feature(self):
        """
        GIVEN: External code calls select_template with template chaining
        WHEN: Query contains template=X+Y syntax
        THEN: TemplateResult dict contains template and source info

        This verifies that the new chaining feature doesn't break external callers.
        """
        from skill.routing import select_template, VALID_TEMPLATES

        # Test template chaining syntax
        result = select_template("design api template=deep+python+cli")

        # External caller expects dict format
        assert isinstance(result, dict), (
            "Chained template result must be dict"
        )

        # External caller expects template key
        assert "template" in result, (
            "Chained template result must have 'template' key"
        )

        # Primary template (first in chain)
        assert result["template"] == "deep", (
            f"Primary template should be 'deep', got '{result['template']}'"
        )

        # Source should indicate override was used
        assert result["source"] == "query_override", (
            f"Source should be 'query_override' for template=X+Y syntax, got '{result['source']}'"
        )
