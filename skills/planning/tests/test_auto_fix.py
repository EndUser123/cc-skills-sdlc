#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "__lib"))

import auto_fix


def test_auto_fix_does_not_reorder_sections_by_default(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    original = """---
status: draft
---

# Plan: Test

## Open Questions

None.

## Goal

Goal text.
"""
    plan_path.write_text(original, encoding="utf-8")

    result = auto_fix.fix_plan(str(plan_path))
    updated = plan_path.read_text(encoding="utf-8")

    assert result["status"] in {"NO_FIXES_NEEDED", "FIXED"}
    assert "## Open Questions" in updated
    assert updated.index("## Open Questions") < updated.index("## Goal")


def test_auto_fix_reorders_sections_only_when_requested(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    original = """---
status: draft
---

# Plan: Test

## Open Questions

None.

## Goal

Goal text.
"""
    plan_path.write_text(original, encoding="utf-8")

    result = auto_fix.fix_plan(str(plan_path), reorder=True)
    updated = plan_path.read_text(encoding="utf-8")

    assert result["status"] == "FIXED"
    assert updated.index("## Goal") < updated.index("## Open Questions")
