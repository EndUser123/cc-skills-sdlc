# TLDR-Code Languages, Tool Comparison & Python API Reference

## Languages Supported

| Language | AST | Call Graph | CFG | DFG | PDG |
|----------|-----|------------|-----|-----|-----|
| Python | Yes | Yes | Yes | Yes | Yes |
| TypeScript | Yes | Yes | Yes | Yes | Yes |
| JavaScript | Yes | Yes | Yes | Yes | Yes |
| Go | Yes | Yes | Yes | Yes | Yes |
| Rust | Yes | Yes | Yes | Yes | Yes |
| Java | Yes | Yes | - | - | - |
| C/C++ | Yes | Yes | - | - | - |
| Ruby | Yes | - | - | - | - |
| PHP | Yes | - | - | - | - |
| Kotlin | Yes | - | - | - | - |
| Swift | Yes | - | - | - | - |
| C# | Yes | - | - | - | - |
| Scala | Yes | - | - | - | - |
| Lua | Yes | - | - | - | - |
| Elixir | Yes | - | - | - | - |

---

## Ignore Patterns

TLDR respects `.tldrignore` (gitignore syntax):

```gitignore
# .tldrignore
.venv/
__pycache__/
node_modules/
*.min.js
dist/
```

First run creates `.tldrignore` with sensible defaults.
Use `--no-ignore` to bypass.

---

## When to Use TLDR vs Other Tools

| Task | Use TLDR | Use Grep |
|------|----------|----------|
| Find function definition | `tldr extract file --function X` | - |
| Search code patterns | `tldr search "pattern"` | - |
| String literal search | - | `grep "literal"` |
| Config values | - | `grep "KEY="` |
| Cross-file calls | `tldr calls` | - |
| Reverse deps | `tldr impact func` | - |
| Complexity analysis | `tldr cfg file func` | - |
| Variable tracking | `tldr dfg file func` | - |
| Natural language query | `tldr semantic search` | - |

---

## Python API

```python
from tldr.api import (
    # L1: AST
    extract_file, extract_functions, get_imports,
    # L2: Call Graph
    build_project_call_graph, get_intra_file_calls,
    # L3: CFG
    get_cfg_context,
    # L4: DFG
    get_dfg_context,
    # L5: PDG
    get_slice, get_pdg_context,
    # Unified
    get_relevant_context,
    # Analysis
    analyze_dead_code, analyze_architecture, analyze_impact,
)

# Example: Get context for LLM
ctx = get_relevant_context("src/", "main", depth=2, language="python")
print(ctx.to_llm_string())
```

---

## Bug Fixing Workflow (Navigation + Read)

**Key insight:** TLDR navigates, then you read. Don't try to fix bugs from summaries alone.

### The Pattern

```bash
# 1. NAVIGATE: Find which files matter
tldr imports file.py              # What does buggy file depend on?
tldr impact func_name .           # Who calls the buggy function?
tldr calls .                      # Cross-file edges (follow 2-hop for models)

# 2. READ: Get actual code for critical files (2-4 files, not all 50)
# Use Read tool or tldr search -C for code with context
tldr search "def buggy_func" . -C 20
```

### Why This Works

For cross-file bugs (e.g., wrong field name, type mismatch), you need to see:
- The file with the bug (handler accessing `task.user_id`)
- The file with the contract (model defining `owner_id`)

TLDR finds which files matter. Then you read them.

### Getting More Context

If TLDR output isn't enough:
- `tldr search "pattern" . -C 20` - Get actual code with 20 lines context
- `tldr imports file.py` - See what a file depends on
- Read the file directly if you need the full implementation

---

## Token Savings Evidence

```
Raw file read:    23,314 tokens
TLDR all layers:   1,189 tokens
─────────────────────────────────
Savings:              95%
```

The insight: Call graph navigates to relevant code, then layers give structured summaries. You don't read irrelevant code.
