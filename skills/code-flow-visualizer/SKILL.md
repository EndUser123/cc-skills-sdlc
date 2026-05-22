# Code Flow Visualizer

## Overview

Convert code into Mermaid flowcharts to visualize and understand logic structure.

**Mandatory Protocol:** See `__lib/visual_standards.md` for Diagram Type Selection and the "Iron Laws" of Diagramming (Readable, Labeled, Contextual).

## Usage

Use when the user says "visualize logic" or "generate flowchart" for a specific function.

---

## Phases

### Phase 1: Generate

**Entry criteria:** User request with target function identified (via explicit mention or grep).

**Actions:**
1. Read the target source file
2. Identify control flow structure (conditionals, loops, branches, exits)
3. Emit Mermaid flowchart to `.claude/.artifacts/{terminal_id}/code-flow-visualizer/`

**Exit criteria:** Mermaid diagram file exists at expected path with non-empty content.

---

**[STOP] Verification required before Phase 2**

Before proceeding to validation, confirm:
- Diagram file was written successfully (read verification)
- Diagram contains expected node count or structural markers

If verification fails, stop and report the generation failure to the user.

---

### Phase 2: Validate

**Entry criteria:** Phase 1 diagram file exists and is non-empty.

**Actions:**
1. Read the generated diagram file
2. Apply visual standards checklist (from `__lib/visual_standards.md`):
   - Readable: no label truncation, appropriate depth
   - Labeled: all nodes have meaningful text
   - Contextual: entry/exit points clear, no orphan nodes
3. If validation fails, report specific failures to user
4. If validation passes, deliver the diagram path to the user

**Exit criteria:** Validation result communicated to user.

---

## Best Practices

- **Scope**: Focus on a single function or critical path.
- **Simplify**: Truncate repetitive loops or trivial error checks.
- **Symbolic**: Use Rectangles for actions, Diamonds for decisions.

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious
