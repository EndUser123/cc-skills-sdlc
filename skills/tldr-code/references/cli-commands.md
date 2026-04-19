# TLDR-Code CLI Commands Reference

## Navigation

```bash
# File tree
tldr tree [path]
tldr tree src/ --ext .py .ts        # Filter extensions
tldr tree . --show-hidden           # Include hidden files

# Code structure (codemaps)
tldr structure [path] --lang python
tldr structure src/ --max 100       # Max files to analyze
```

## Search

```bash
# Text search
tldr search <pattern> [path]
tldr search "def process" src/
tldr search "class.*Error" . --ext .py
tldr search "TODO" . -C 3           # 3 lines context
tldr search "func" . --max 50       # Limit results

# Semantic search (natural language)
tldr semantic search "authentication flow"
tldr semantic search "error handling" --k 10
tldr semantic search "database queries" --expand  # Include call graph
```

## File Analysis

```bash
# Full file info
tldr extract <file>
tldr extract src/api.py
tldr extract src/api.py --class UserService      # Filter to class
tldr extract src/api.py --function process       # Filter to function
tldr extract src/api.py --method UserService.get # Filter to method

# Relevant context (follows call graph)
tldr context <entry> --project <path>
tldr context main --project src/ --depth 3
tldr context UserService.create --project . --lang typescript
```

## Flow Analysis

```bash
# Control flow graph (complexity)
tldr cfg <file> <function>
tldr cfg src/processor.py process_data
# Returns: cyclomatic complexity, blocks, branches, loops

# Data flow graph (variable tracking)
tldr dfg <file> <function>
tldr dfg src/processor.py process_data
# Returns: where variables are defined, read, modified

# Program slice (what affects line X)
tldr slice <file> <function> <line>
tldr slice src/processor.py process_data 42
tldr slice src/processor.py process_data 42 --direction forward
tldr slice src/processor.py process_data 42 --var result
```

## Codebase Analysis

```bash
# Build cross-file call graph
tldr calls [path]
tldr calls src/ --lang python

# Reverse call graph (who calls this function?)
tldr impact <func> [path]
tldr impact process_data src/ --depth 5
tldr impact authenticate . --file auth  # Filter by file

# Find dead/unreachable code
tldr dead [path]
tldr dead src/ --entry main cli test_  # Specify entry points
tldr dead . --lang typescript

# Detect architectural layers
tldr arch [path]
tldr arch src/ --lang python
# Returns: entry layer, middle layer, leaf layer, circular deps
```

## Import Analysis

```bash
# Parse imports from file
tldr imports <file>
tldr imports src/api.py
tldr imports src/api.ts --lang typescript

# Reverse import lookup (who imports this module?)
tldr importers <module> [path]
tldr importers datetime src/
tldr importers UserService . --lang typescript
```

## Quality & Testing

```bash
# Type check + lint
tldr diagnostics <file|path>
tldr diagnostics src/api.py
tldr diagnostics . --project              # Whole project
tldr diagnostics src/ --no-lint           # Type check only
tldr diagnostics src/ --format text       # Human-readable

# Find affected tests
tldr change-impact [files...]
tldr change-impact                        # Auto-detect (session/git)
tldr change-impact src/api.py             # Explicit files
tldr change-impact --session              # Session-modified files
tldr change-impact --git                  # Git diff files
tldr change-impact --git --git-base main  # Diff against branch
tldr change-impact --run                  # Actually run affected tests
```

## Caching

```bash
# Pre-build call graph cache
tldr warm <path>
tldr warm src/ --lang python
tldr warm . --background                  # Build in background

# Build semantic index (one-time)
tldr semantic index [path]
tldr semantic index . --lang python
tldr semantic index . --model all-MiniLM-L6-v2  # Smaller model (80MB)
```
