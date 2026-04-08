#!/usr/bin/env python3
"""Tests for auto_fix.py v2 - non-semantic repairs only.

auto_fix v2 is LIMITED to:
- Header normalization (consistent ## prefix, proper spacing)
- Section ordering (canonical order)
- Metadata updates (status header, source path)

auto_fix v2 does NOT:
- Insert placeholder content (*Describe the problem*, path/to/file1.py)
- Generate fake tasks (TASK-001)
- Add plausible-looking scaffold (Component A, Criteria one)
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "__lib"))

import auto_fix

# =============================================================================
# Test: normalize_headers
# =============================================================================


class TestNormalizeHeaders:
    """Test header normalization."""

    def test_double_space_after_header_normalized(self) -> None:
        """## followed by multiple spaces is normalized to one space."""
        plan = "##  Problem\n\nContent."
        result, fixes = auto_fix.normalize_headers(plan)
        assert result == "## Problem\n\nContent."
        assert "Header spacing normalized" in fixes

    def test_no_space_after_header_normalized(self) -> None:
        """## with no space is normalized to one space."""
        plan = "##Problem\n\nContent."
        result, fixes = auto_fix.normalize_headers(plan)
        assert result == "## Problem\n\nContent."
        assert "Header spacing normalized" in fixes

    def test_trailing_whitespace_removed(self) -> None:
        """Trailing whitespace on header lines is removed."""
        plan = "## Problem   \n\nContent."
        result, fixes = auto_fix.normalize_headers(plan)
        assert result == "## Problem\n\nContent."
        assert "Trailing whitespace removed" in fixes

    def test_multiple_headers_normalized(self) -> None:
        """Multiple headers all get normalized."""
        plan = "##  Problem\n##   Context\n##Solution"
        result, _ = auto_fix.normalize_headers(plan)
        lines = result.split("\n")
        assert lines[0] == "## Problem"
        assert lines[1] == "## Context"
        assert lines[2] == "## Solution"


# =============================================================================
# Test: reorder_sections
# =============================================================================


class TestReorderSections:
    """Test canonical section ordering."""

    def test_sections_reordered_to_canonical_order(self) -> None:
        """Sections are reordered to canonical order."""
        plan = """## Solution

Solution content.

## Problem

Problem content.

## Implementation Plan

Implementation content.
"""
        result, fixes = auto_fix.reorder_sections(plan)
        goal_pos = result.find("## Goal")
        design_pos = result.find("## Design Decisions and Invariants")
        impl_pos = result.find("## Implementation Changes")
        assert goal_pos < design_pos < impl_pos

    def test_unknown_sections_preserved(self) -> None:
        """Sections not in canonical order are preserved at end."""
        plan = """## Problem

Problem content.

## Custom Section

Custom content.
"""
        result, fixes = auto_fix.reorder_sections(plan)
        assert "## Goal" in result
        assert "## Custom Section" in result
        assert "Preserved: Custom Section" in fixes

    def test_frontmatter_preserved(self) -> None:
        """Frontmatter (--- block) is preserved at start."""
        plan = """---
status: draft
---

## Problem

Problem content.
"""
        result, _ = auto_fix.reorder_sections(plan)
        assert result.startswith("---")
        assert "status: draft" in result[:100]

    def test_title_preserved(self) -> None:
        """Title (# heading) is preserved after frontmatter."""
        plan = """---
status: draft
---

# Plan: My Title

## Problem

Problem content.
"""
        result, _ = auto_fix.reorder_sections(plan)
        assert "# Plan: My Title" in result

    def test_section_aliases_mapped(self) -> None:
        """Section aliases are recognized and ordered correctly."""
        plan = """## Background

Context content.

## Problem Statement

Problem content.
"""
        result, _ = auto_fix.reorder_sections(plan)
        goal_pos = result.find("## Goal")
        state_pos = result.find("## Current State with Evidence")
        assert goal_pos < state_pos, "Goal should come before Current State with Evidence"


# =============================================================================
# Test: update_status_header
# =============================================================================


class TestUpdateStatusHeader:
    """Test status header updates."""

    def test_status_updated_when_exists(self) -> None:
        """Status is updated when --- block exists."""
        plan = """---
status: draft
---

## Problem

Content.
"""
        result, fixes = auto_fix.update_status_header(plan, "in-review")
        assert "status: in-review" in result
        assert "Status updated to: in-review" in fixes

    def test_status_added_when_missing(self) -> None:
        """Status is added when --- exists but status line missing."""
        plan = """---
source: some/path
---

## Problem

Content.
"""
        result, fixes = auto_fix.update_status_header(plan, "implementation-ready")
        assert "status: implementation-ready" in result
        assert "Status updated to: implementation-ready" in fixes

    def test_no_change_when_no_frontmatter(self) -> None:
        """Missing frontmatter is created when metadata is updated."""
        plan = """## Problem

Content.
"""
        result, fixes = auto_fix.update_status_header(plan, "in-review")
        assert result.startswith("---")
        assert "status: in-review" in result
        assert "source: null" in result
        assert "unresolved_blockers: 0" in result
        assert fixes == ["Status updated to: in-review"]


# =============================================================================
# Test: update_source_header
# =============================================================================


class TestUpdateSourceHeader:
    """Test source path header updates."""

    def test_source_updated_when_exists(self) -> None:
        """Source is updated when already present."""
        plan = """---
status: draft
source: old/path
---

## Problem

Content.
"""
        result, fixes = auto_fix.update_source_header(plan, "new/path")
        assert "source: new/path" in result
        assert "Source updated to: new/path" in fixes

    def test_source_added_when_missing(self) -> None:
        """Source is added when --- exists but source line missing."""
        plan = """---
status: draft
---

## Problem

Content.
"""
        result, fixes = auto_fix.update_source_header(plan, "some/adr.md")
        assert "source: some/adr.md" in result
        assert "Source updated to: some/adr.md" in fixes


# =============================================================================
# Test: fix_plan integration
# =============================================================================


class TestFixPlanIntegration:
    """Integration tests for fix_plan function."""

    def test_fix_plan_returns_only_structural_fixes(self) -> None:
        """fix_plan returns only structural fixes, no content added."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""## Problem

Real problem content.

## Solution

Real solution.
""")
            plan_path = f.name

        try:
            result = auto_fix.fix_plan(plan_path)
            assert result["status"] == "FIXED"
            # Must have structural fixes
            assert len(result["fixes_applied"]) > 0
            # No placeholder content should appear
            with open(plan_path) as f:
                content = f.read()
            assert "*Describe the problem*" not in content
            assert "path/to/" not in content
            assert "Component A" not in content
            assert "**TASK-001**" not in content
        finally:
            Path(plan_path).unlink()

    def test_fix_plan_complete_no_changes(self) -> None:
        """Plan with all canonical sections in order returns NO_FIXES_NEEDED."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""---
status: draft
source: null
unresolved_blockers: 0
---

# Plan: Complete

## Goal

Problem content.

## Current State with Evidence

Context content.

## Design Decisions and Invariants

Impl content.

## Implementation Changes

**TASK-001**: Task content.
- Action: Do the thing
- Acceptance:
  - It works

## Test Matrix

Test content.

## Assumptions/Defaults

Assumptions content.

## Open Questions

None.
""")
            plan_path = f.name

        try:
            result = auto_fix.fix_plan(plan_path)
            assert result["status"] == "NO_FIXES_NEEDED"
        finally:
            Path(plan_path).unlink()

    def test_fix_plan_does_not_insert_placeholders(self) -> None:
        """Verify that fix_plan NEVER inserts placeholder content."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""## Problem

Only problem.
""")
            plan_path = f.name

        try:
            result = auto_fix.fix_plan(plan_path)
            with open(plan_path) as f:
                content = f.read()
            # Must NOT contain any placeholder patterns
            forbidden = [
                "*Describe the problem*",
                "*Description*",
                "path/to/",
                "Component A",
                "Component B",
                "Criteria one",
                "Criteria two",
                "**TASK-001**",
                "**TASK-002**",
                "*Add risk analysis*",
            ]
            for pattern in forbidden:
                assert pattern not in content, f"Placeholder '{pattern}' should not appear"
        finally:
            Path(plan_path).unlink()

    def test_fix_plan_status_update(self) -> None:
        """fix_plan can update status header."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""---
status: draft
---

## Problem

Problem content.
""")
            plan_path = f.name

        try:
            result = auto_fix.fix_plan(plan_path, new_status="in-review")
            assert result["status"] == "FIXED"
            with open(plan_path) as f:
                content = f.read()
            assert "status: in-review" in content
        finally:
            Path(plan_path).unlink()

    def test_fix_plan_unresolved_blockers_update(self) -> None:
        """fix_plan can update unresolved_blockers metadata."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""---
status: draft
source: null
unresolved_blockers: 2
---

## Goal

Problem content.
""")
            plan_path = f.name

        try:
            result = auto_fix.fix_plan(plan_path, unresolved_blockers=0)
            assert result["status"] == "FIXED"
            with open(plan_path) as f:
                content = f.read()
            assert "unresolved_blockers: 0" in content
        finally:
            Path(plan_path).unlink()


# =============================================================================
# Test: No placeholder insertion
# =============================================================================


class TestNoPlaceholderInsertion:
    """Verify auto_fix v2 NEVER inserts placeholder content."""

    def test_get_placeholder_does_not_exist(self) -> None:
        """auto_fix v2 should not have get_placeholder function."""
        assert not hasattr(
            auto_fix, "get_placeholder"
        ), "auto_fix v2 must NOT have get_placeholder function"

    def test_add_missing_sections_does_not_exist(self) -> None:
        """auto_fix v2 should not have add_missing_sections function."""
        assert not hasattr(
            auto_fix, "add_missing_sections"
        ), "auto_fix v2 must NOT have add_missing_sections function"

    def test_no_placeholder_constants(self) -> None:
        """No placeholder content constants should exist."""
        for attr in dir(auto_fix):
            if "placeholder" in attr.lower():
                pytest.fail(f"auto_fix v2 must NOT have placeholder-related attr: {attr}")


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
