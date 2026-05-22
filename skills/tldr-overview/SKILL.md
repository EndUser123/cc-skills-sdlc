---
name: tldr-overview
description: Get a token-efficient overview of any project using the TLDR stack
---
# TLDR Project Overview

Get a token-efficient overview of any project using the TLDR stack.

## Trigger
- `/overview` or `/tldr-overview`
- "give me an overview of this project"
- "what's in this codebase"
- Starting work on an unfamiliar project

## Execution Phases

### PHASE 1: FILE TREE (Generation)

```bash
tldr tree . --ext .py    # or .ts, .go, .rs
```

**Output:** Directory structure and file listing. This is discovery, not assessment.

---

### PHASE GATE: Stop after File Tree

```
STOP — Before claiming code structure is "good" or "bad":

File tree shows WHAT files exist, not whether they are correct.
Proceed to structure analysis only after tree output is available.
```

---

### PHASE 2: CODE STRUCTURE (Generation)

```bash
tldr structure src/ --lang python --max 50
```

**Output:** Functions, classes, imports per file. This is mapping, not validation.

---

### PHASE GATE: Stop after Structure

```
STOP — Before claiming architecture is sound or flawed:

Structure analysis shows HOW components are organized,
not whether the organization is fit for purpose.

Assessment requires comparing against requirements (handled by separate skills).
```

---

### PHASE 3: CALL GRAPH (Generation)

```bash
tldr calls src/
```

**Output:** Cross-file relationships, entry points. This is connection mapping, not correctness proof.

---

### PHASE 4: COMPLEXITY ANALYSIS (Generation)

For each entry point:

```bash
tldr cfg src/main.py main  # Get complexity
```

**Output:** Cyclomatic complexity, branch count. This is measurement, not judgment.

---

### PHASE GATE: Stop before Project Assessment

```
STOP — Before claiming the project is "well-structured" or "needs work":

Complexity metrics describe QUANTITATIVE characteristics,
not QUALITATIVE fitness.

A "high complexity" finding requires a separate validation phase
(compare against project requirements, determine acceptable thresholds)
before becoming an actionable issue.
```

---

### PHASE 5: VALIDATION (Separate)

Project overview is generation. Assessment against project-specific requirements is a separate phase:

```bash
# After generating all Phase 1-4 outputs:
# 1. Compare complexity metrics against project-defined thresholds
# 2. Check if entry points align with stated architecture decisions
# 3. Identify discrepancies — these are findings, not assumptions

# Run appropriate verification: project tests, build commands, etc.
# Read output → THEN claim project health
```

**Rule:** tldr-overview generates architectural context. Quality assessment is a separate workflow.

## Output Format

```
## Project Overview: {project_name}

### Structure
{tree output - files and directories}

### Key Components
{structure output - functions, classes per file}

### Architecture (Call Graph)
{calls output - how components connect}

### Complexity Hot Spots
{cfg output - functions with high cyclomatic complexity}

---
Token cost: ~{N} tokens (vs ~{M} raw = {savings}% savings)
```

## When NOT to Use
- Already familiar with the project
- Working on a specific file (use targeted tldr commands instead)
- Test files (need full context)

## Programmatic Usage

```python
from tldr.api import get_file_tree, get_code_structure, build_project_call_graph

# 1. Tree
tree = get_file_tree("src/", extensions={".py"})

# 2. Structure
structure = get_code_structure("src/", language="python", max_results=50)

# 3. Call graph
calls = build_project_call_graph("src/", language="python")

# 4. Complexity for hot functions
for edge in calls.edges[:10]:
    cfg = get_cfg_context("src/" + edge[0], edge[1])

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
```
