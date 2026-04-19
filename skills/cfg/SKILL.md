---
name: cfg
description: Control Flow Graph visualization for Python files - visualize execution paths and branching logic
category: debug
domain: code-analysis
version: 1.0.0
status: stable

triggers:
  - "cfg"
  - "control flow"
  - "branching"
  - "execution path"
  - "visualize flow"

aliases:
  - /cfg

dependencies:
  - P:/__csf/src/features/cfg/cfg_wrapper.py
  - P:/__csf/src/features/cfg/cfg_cli.py

suggest:
  - /debug
  - /complexity
---

# /cfg - Control Flow Graph Visualization

## Purpose

Visualize execution paths and branching logic for Python files.

## Project Context

### Constitution/Constraints
- Python 3.12+ native implementation (no external dependencies)
- On-demand visualization only
- Evidence-based debugging support

### Technical Context
- Dependencies: `P:/__csf/src/features/cfg/cfg_wrapper.py`, `P:/__csf/src/features/cfg/cfg_cli.py`
- AST-based CFG generation
- Output formats: text summary, Graphviz DOT
- Handles: if/elif/else, for/while loops, try/except, functions, classes

### Architecture Alignment
- Part of debug skills family
- Integrates with /debug and /complexity
- Suggested for nested conditionals and cyclomatic complexity >5

## Your Workflow

1. **Identify Target** - Select Python file for analysis
2. **Generate CFG** - Parse AST, build blocks and edges
3. **Visualize** - Output text summary or DOT format
4. **Interpret** - Show execution paths, branch targets, entry/exit points
5. **Integrate** - Suggest next debugging steps

## Validation Rules

### Prohibited Actions
- **NEVER claim CFG without generation** - run actual analysis
- **NEVER assume Python version** - verify 3.12+ compatibility

### Required Output
- Block numbers with line numbers
- Statement counts per block
- Exit targets with block references
- Branch conditions visible

Generate and visualize Control Flow Graphs (CFG) for Python source files.

## Quick Start

```bash
# Generate CFG for a file
/cfg path/to/file.py

# Show text summary with blocks and edges
/cfg path/to/file.py --summary

# Export to Graphviz DOT format
/cfg path/to/file.py --dot

# Save DOT to file
/cfg path/to/file.py --output flow.dot
```

## When to Use

Use CFG visualization when debugging:

- **Complex branching logic** - nested if/else statements that are hard to follow
- **Loop patterns** - understanding how loops branch and exit
- **Exception flow** - tracing try/except paths
- **Function call graphs** - seeing how functions connect
- **"Why isn't line X executing?"** - visualize the path to understand conditions

## What It Shows

For each Python file, CFG generates:

- **Blocks** - Basic blocks of sequential code
- **Edges** - Possible execution paths between blocks
- **Entry/Exit points** - Where execution starts and ends
- **Branch targets** - Where if/else/loops direct flow

## Output Format

### Text Summary (default)

```
Block 1: entry (line 1)
  Statements: 5
  Exits: 1 → ['B2']

Block 2: if_test (line 10)
  Statements:
    - if x > 0
  Exits: 2 → ['B3', 'B4']
```

### Graphviz DOT

```
digraph CFG {
  rankdir=TB;
  node [shape=box, style=rounded];
  block_1 [label="entry\nline 1"];
  block_2 [label="if_test\nline 10"];
  block_1 -> block_2;
}
```

## CLI Usage

```bash
# Direct CLI usage
python P:/__csf/src/features/cfg/cfg_cli.py file.py

# With options
python P:/__csf/src/features/cfg/cfg_cli.py file.py --summary --dot
python P:/__csf/src/features/cfg/cfg_cli.py file.py -o output.dot
```

## Integration with /debug

The /debug skill automatically suggests CFG visualization when:
- Multiple nested conditionals detected
- Cyclomatic complexity > 5
- User asks "why isn't this branch executing?"

## Implementation Notes

- Native Python AST-based implementation
- Compatible with Python 3.12+ (no external dependencies)
- Handles: if/elif/else, for/while loops, try/except, functions, classes
- Location: `P:/__csf/src/features/cfg/`
