#!/usr/bin/env python3
"""
Auto-fix v2 — non-semantic repairs only.

This module is LIMITED to:
- Header normalization (consistent ## prefix, proper spacing)
- Section ordering (canonical order)
- Metadata updates (status header, source path)

This module does NOT:
- Insert placeholder content (*Describe the problem*, path/to/file1.py)
- Generate fake tasks (TASK-001)
- Add plausible-looking scaffold (Component A, Criteria one)
- Write any content that is not purely structural

Usage:
    python P:\\\\\\.claude/skills/planning/__lib/auto_fix.py <plan_path> [status] [unresolved_blockers] [--reorder]

Output:
    Updated plan file with only structural fixes applied
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Canonical section order (v2 headings)
CANONICAL_ORDER = [
    "Goal",
    "Current State with Evidence",
    "Design Decisions and Invariants",
    "Implementation Changes",
    "Test Matrix",
    "Assumptions/Defaults",
    "Open Questions",
]


def extract_sections(plan: str) -> dict[str, tuple[str, int, int]]:
    """Extract all sections with content and positions."""
    sections = {}
    pattern = r"^##\s+(.+)$"
    matches = list(re.finditer(pattern, plan, re.MULTILINE))

    for i, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(plan)
        content = plan[start:end]
        sections[header] = (content, start, end)

    return sections


def normalize_headers(plan: str) -> tuple[str, list[str]]:
    """Normalize ## header formatting: consistent spacing, no trailing whitespace."""
    fixes = []
    # Ensure ## is followed by exactly one space (zero spaces also normalized)
    # Use [ \t] not \s to avoid consuming \r (from CRLF line endings) as whitespace
    before = plan
    plan = re.sub(r"^##[ \t]*", "## ", plan, flags=re.MULTILINE)
    if plan != before:
        fixes.append("Header spacing normalized")

    # Remove trailing spaces/tabs (not newlines) from header lines
    before = plan
    plan = re.sub(r"^(## .+?)[ \t]+$", r"\1", plan, flags=re.MULTILINE)
    if plan != before:
        fixes.append("Trailing whitespace removed")

    return plan, fixes


def reorder_sections(plan: str) -> tuple[str, list[str]]:
    """Reorder sections to canonical order."""
    # Extract frontmatter (--- block at start)
    frontmatter = ""
    body = plan
    fm_match = re.match(r"^(---\s*\n.*?\n---)\s*\n", plan, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1) + "\n\n"
        body = plan[fm_match.end() :]

    # Extract title (first # heading before any ##)
    title = ""
    title_match = re.match(r"^(# [^\n]+\n)\n", body)
    if title_match:
        title = title_match.group(1) + "\n"
        body = body[title_match.end() :]

    # Extract all ## sections
    sections = extract_sections(body)
    if not sections:
        return plan, []

    fixes = []

    # Build ordered section map
    ordered_sections = {}
    remaining = dict(sections)

    # Canonical header names (for replacement)
    CANONICAL_HEADERS = {
        "Goal": "Goal",
        "Current State with Evidence": "Current State with Evidence",
        "Design Decisions and Invariants": "Design Decisions and Invariants",
        "Implementation Changes": "Implementation Changes",
        "Test Matrix": "Test Matrix",
        "Assumptions/Defaults": "Assumptions/Defaults",
        "Open Questions": "Open Questions",
    }

    # Alias map for lookup
    ALIASES = {
        "Goal": ["Goal", "Problem", "Problem Statement"],
        "Current State with Evidence": [
            "Current State with Evidence",
            "Current state with evidence",
            "Current State",
            "Context",
            "Context Analysis",
            "Background",
            "Existing Implementation",
            "Existing Implementation Discovery",
            "Current Implementation",
        ],
        "Design Decisions and Invariants": [
            "Design Decisions and Invariants",
            "Design Decisions",
            "Design",
            "Solution",
            "Proposed Solution",
            "Approach",
        ],
        "Implementation Changes": [
            "Implementation Changes",
            "Implementation Plan",
            "Implementation Steps",
            "Steps",
            "Tasks",
        ],
        "Test Matrix": ["Test Matrix", "Test Coverage", "Test Discovery", "Tests", "Testing"],
        "Assumptions/Defaults": [
            "Assumptions/Defaults",
            "Assumptions and Defaults",
            "Assumptions",
            "Defaults",
            "Risks, Success Criteria, Dependencies",
        ],
        "Open Questions": ["Open Questions", "Open Issues", "Questions"],
    }

    def replace_header(content: str, old_header: str, new_header: str) -> str:
        """Replace ## Header with new canonical header."""
        return re.sub(
            rf"^(##\s+){re.escape(old_header)}$", rf"\1{new_header}", content, flags=re.MULTILINE
        )

    # Track original positions: (header_lower, start_position)
    # These are sorted by start position in the original plan
    original_canonical_order = []
    for canonical in CANONICAL_ORDER:
        for header, (content, start, end) in list(remaining.items()):
            matched = False
            if header.lower() == canonical.lower():
                matched = True
            elif canonical in ALIASES and header in ALIASES[canonical]:
                matched = True
            if matched:
                original_canonical_order.append((canonical, start, header))
                break

    # Match by canonical name or alias
    for canonical in CANONICAL_ORDER:
        for header, (content, start, end) in list(remaining.items()):
            matched = False
            # Exact canonical match (case-insensitive)
            if header.lower() == canonical.lower():
                matched = True
            # Alias match
            elif canonical in ALIASES and header in ALIASES[canonical]:
                matched = True

            if matched:
                # Replace header with canonical name if different
                was_renamed = header != CANONICAL_HEADERS.get(canonical, canonical)
                if was_renamed:
                    content = replace_header(
                        content, header, CANONICAL_HEADERS.get(canonical, canonical)
                    )
                ordered_sections[canonical] = (content, start, end, was_renamed)
                del remaining[header]
                break

    # Add any sections not in canonical order (preserve them)
    for header, (content, start, end) in remaining.items():
        ordered_sections[header] = (content, start, end, False)

    # Compute final canonical order positions for comparison
    final_canonical_positions = {}
    for i, canonical in enumerate(CANONICAL_ORDER):
        if canonical in ordered_sections:
            _, start, _, _ = ordered_sections[canonical]
            final_canonical_positions[canonical] = start

    # Rebuild plan
    parts = [frontmatter, title]
    seen_canonicals = set()
    for idx, canonical in enumerate(CANONICAL_ORDER):
        if canonical in ordered_sections:
            content, _, _, was_renamed = ordered_sections[canonical]
            parts.append(content)
            # Only append newline if content doesn't already end with one
            if not content.endswith("\n"):
                parts.append("\n")
            seen_canonicals.add(canonical)
            # Only report "Ordered" if position changed OR header was renamed
            orig_pos = next(
                (i for i, (c, _, _) in enumerate(original_canonical_order) if c == canonical), None
            )
            position_changed = orig_pos is not None and orig_pos != idx
            if position_changed or was_renamed:
                fixes.append(f"Ordered: {canonical}")

    # Append any sections not in canonical list
    for header, (content, _, _, _) in ordered_sections.items():
        if header not in seen_canonicals:
            parts.append(content)
            if not content.endswith("\n"):
                parts.append("\n")
            fixes.append(f"Preserved: {header}")

    return "".join(parts), fixes


def ensure_frontmatter(plan: str) -> str:
    """Ensure a frontmatter block exists."""
    if re.match(r"^---\s*\n.*?\n---\s*\n?", plan, re.DOTALL):
        return plan
    return "---\nstatus: draft\nsource: null\nunresolved_blockers: 0\n---\n\n" + plan.lstrip()


def update_status_header(plan: str, new_status: str | None = None) -> tuple[str, list[str]]:
    """Update or add status header in frontmatter."""
    fixes = []
    if new_status is None:
        return plan, fixes

    plan = ensure_frontmatter(plan)
    if re.search(r"^status:", plan, re.MULTILINE):
        plan = re.sub(r"^status:.*$", f"status: {new_status}", plan, flags=re.MULTILINE)
    else:
        plan = re.sub(r"^(---\s*\n)", rf"\1status: {new_status}\n", plan, flags=re.MULTILINE)
    fixes.append(f"Status updated to: {new_status}")

    return plan, fixes


def update_source_header(plan: str, source_path: str | None) -> tuple[str, list[str]]:
    """Update or add source path in frontmatter."""
    fixes = []
    if source_path is None:
        return plan, fixes

    plan = ensure_frontmatter(plan)
    if re.search(r"^source:", plan, re.MULTILINE):
        plan = re.sub(r"^source:.*$", f"source: {source_path}", plan, flags=re.MULTILINE)
    else:
        plan = re.sub(r"^(---\s*\n)", rf"\1source: {source_path}\n", plan, flags=re.MULTILINE)
    fixes.append(f"Source updated to: {source_path}")

    return plan, fixes


def update_unresolved_blockers(
    plan: str, unresolved_blockers: int | None = None
) -> tuple[str, list[str]]:
    """Update or add unresolved_blockers in frontmatter."""
    fixes = []
    if unresolved_blockers is None:
        return plan, fixes

    plan = ensure_frontmatter(plan)
    if re.search(r"^unresolved_blockers:", plan, re.MULTILINE):
        plan = re.sub(
            r"^unresolved_blockers:.*$",
            f"unresolved_blockers: {unresolved_blockers}",
            plan,
            flags=re.MULTILINE,
        )
    else:
        plan = re.sub(
            r"^(---\s*\n)",
            rf"\1unresolved_blockers: {unresolved_blockers}\n",
            plan,
            flags=re.MULTILINE,
        )
    fixes.append(f"Unresolved blockers updated to: {unresolved_blockers}")

    return plan, fixes


def fix_plan(
    plan_path: str,
    new_status: str | None = None,
    source_path: str | None = None,
    unresolved_blockers: int | None = None,
    reorder: bool = False,
) -> dict:
    """Apply non-semantic fixes to the plan.

    Returns:
        Dict with fixes_applied list and status
    """
    plan_path_obj = Path(plan_path)

    with open(plan_path_obj, encoding="utf-8") as f:
        plan = f.read()

    all_fixes = []

    # Apply only non-semantic fixes in order
    plan, fixes = normalize_headers(plan)
    all_fixes.extend(fixes)

    if reorder:
        plan, fixes = reorder_sections(plan)
        all_fixes.extend(fixes)

    if new_status:
        plan, fixes = update_status_header(plan, new_status)
        all_fixes.extend(fixes)

    if source_path:
        plan, fixes = update_source_header(plan, source_path)
        all_fixes.extend(fixes)

    if unresolved_blockers is not None:
        plan, fixes = update_unresolved_blockers(plan, unresolved_blockers)
        all_fixes.extend(fixes)

    # Write back
    with open(plan_path_obj, "w", encoding="utf-8") as f:
        f.write(plan)

    return {
        "status": "FIXED" if all_fixes else "NO_FIXES_NEEDED",
        "fixes_applied": all_fixes,
    }


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python auto_fix.py <plan_path> [status] [unresolved_blockers] [--reorder]")
        sys.exit(1)

    args = [arg for arg in sys.argv[1:] if arg != "--reorder"]
    reorder = "--reorder" in sys.argv[1:]

    plan_path = args[0]
    new_status = args[1] if len(args) > 1 else None
    unresolved_blockers = int(args[2]) if len(args) > 2 else None
    result = fix_plan(
        plan_path,
        new_status=new_status,
        unresolved_blockers=unresolved_blockers,
        reorder=reorder,
    )

    import json

    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
