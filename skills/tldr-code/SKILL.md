---
name: tldr-code
description: Token-efficient code analysis via 5-layer stack (AST, Call Graph, CFG, DFG, PDG). 95% token savings.
version: "1.0.0"
status: stable
category: tools
allowed-tools: [Bash]
keywords: [debug, refactor, understand, complexity, "call graph", "data flow", "what calls", "how complex", search, explore, analyze, dead code, architecture, imports]
---

# TLDR-Code: Token-Efficient Code Analysis

**95% token savings** vs raw file reads using a 5-layer analysis stack.

## Quick Reference

| Task | Command |
|------|---------|
| File tree | `tldr tree src/` |
| Code structure | `tldr structure . --lang python` |
| Search code | `tldr search "pattern" .` |
| Call graph | `tldr calls src/` |
| Who calls X? | `tldr impact func_name .` |
| Control flow | `tldr cfg file.py func` |
| Data flow | `tldr dfg file.py func` |
| Program slice | `tldr slice file.py func 42` |
| Dead code | `tldr dead src/` |
| Architecture | `tldr arch src/` |
| Imports | `tldr imports file.py` |
| Who imports X? | `tldr importers module_name .` |
| Affected tests | `tldr change-impact --git` |
| Type check | `tldr diagnostics file.py` |
| Semantic search | `tldr semantic search "auth flow"` |

---

## The 5-Layer Stack

```
Layer 1: AST         ~500 tokens   Function signatures, imports
Layer 2: Call Graph  +440 tokens   What calls what (cross-file)
Layer 3: CFG         +110 tokens   Complexity, branches, loops
Layer 4: DFG         +130 tokens   Variable definitions/uses
Layer 5: PDG         +150 tokens   Dependencies, slicing
───────────────────────────────────────────────────────────────
Total:              ~1,200 tokens  vs 23,000 raw = 95% savings
```

---

## Bug Fixing Workflow

**Key insight:** TLDR navigates, then you read. Don't fix bugs from summaries alone.

```bash
# 1. NAVIGATE: Find which files matter
tldr imports file.py              # What does buggy file depend on?
tldr impact func_name .           # Who calls the buggy function?
tldr calls .                      # Cross-file edges

# 2. READ: Get actual code for critical files (2-4 files, not all 50)
tldr search "def buggy_func" . -C 20
```

---

## Token Savings Evidence

```
Raw file read:    23,314 tokens
TLDR all layers:   1,189 tokens
─────────────────────────────────
Savings:              95%
```

---

## References

Detailed documentation is split into focused reference files:

| File | Contents |
|------|----------|
| `references/cli-commands.md` | All CLI commands: navigation, search, file analysis, flow analysis, codebase analysis, import analysis, quality/testing, caching |
| `references/daemon-and-semantic.md` | Daemon setup & commands, socket protocol, semantic search setup & configuration |
| `references/languages-and-tool-comparison.md` | Supported languages table, ignore patterns, TLDR vs Grep comparison, Python API, bug fixing workflow details |
| `rules.md` | Usage rules: when to use TLDR vs Grep/Read, decision tree, hook integration |

### Language Support Summary

15 languages supported. Full 5-layer support (AST + Call Graph + CFG + DFG + PDG): **Python, TypeScript, JavaScript, Go, Rust**. AST + Call Graph only: Java, C/C++. AST only: Ruby, PHP, Kotlin, Swift, C#, Scala, Lua, Elixir. See `references/languages-and-tool-comparison.md` for full matrix.

### CLI Command Categories

8 command categories: Navigation, Search, File Analysis, Flow Analysis, Codebase Analysis, Import Analysis, Quality & Testing, Caching. See `references/cli-commands.md` for all flags and examples.

### Daemon & Semantic Search

Daemon holds indexes in memory for instant queries (22 commands, auto-shutdown after 30min idle). Semantic search uses embeddings (bge-large-en-v1.5 default, all-MiniLM-L6-v2 for smaller footprint). See `references/daemon-and-semantic.md` for setup and configuration.

### Python API

Import from `tldr.api` for programmatic access to all 5 layers plus unified `get_relevant_context()`. See `references/languages-and-tool-comparison.md` for full API surface.

### Tool Selection

See `references/languages-and-tool-comparison.md` for the TLDR vs Grep/Read comparison table, and `rules.md` for the decision tree and integration notes.
