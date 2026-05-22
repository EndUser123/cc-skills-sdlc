---
name: tldr-router
description: Maps questions to the optimal tldr command. Use this to pick the right layer
---
# TLDR Smart Router

Maps questions to the optimal tldr command. Use this to pick the right layer.

## Question → Command Mapping

### "What files/functions exist?"
```bash
tldr tree . --ext .py          # File overview
tldr structure src/ --lang python  # Function/class overview
```
**Use:** Starting exploration, orientation

### "What does X call / who calls X?"
```bash
tldr context <function> --project . --depth 2
tldr calls src/
```
**Use:** Understanding architecture, finding entry points

### "How complex is X?"
```bash
tldr cfg <file> <function>
```
**Use:** Identifying refactoring candidates, understanding difficulty

### "Where does variable Y come from?"
```bash
tldr dfg <file> <function>
```
**Use:** Debugging, understanding data flow

### "What affects line Z?"
```bash
tldr slice <file> <function> <line>
```
**Use:** Impact analysis, safe refactoring

### "Search for pattern P"
```bash
tldr search "pattern" src/
```
**Use:** Finding code, structural search

## Decision Tree

```
START
  │
  ├─► "What exists?" ──► tree / structure  [GENERATION — discovery only]
  │
  ├─► "How does X connect?" ──► context / calls  [GENERATION — mapping only]
  │
  ├─► "Why is X complex?" ──► cfg  [GENERATION — measurement only]
  │
  ├─► "Where does Y flow?" ──► dfg  [GENERATION — tracing only]
  │
  ├─► "What depends on Z?" ──► slice  [GENERATION — dependency analysis]
  │
  └─► "Find something" ──► search  [GENERATION — search only]

--- SEPARATION ---

DO NOT intermix generation outputs with validation conclusions.

After each generation command:
  1. Read the output
  2. [STOP GATE] Ask: "Is this output CLAIMING correctness, or just DESCRIBING state?"
  3. If correctness claim: defer to /verification-before-completion
  4. If description: proceed to next generation step or synthesize findings
```

## Intent Detection Keywords

## Intent Detection Keywords

| Intent | Keywords | Layer |
|--------|----------|-------|
| Navigation | "what", "where", "find", "exists" | tree, structure, search |
| Architecture | "calls", "uses", "connects", "depends" | context, calls |
| Complexity | "complex", "refactor", "branches", "paths" | cfg |
| Data Flow | "variable", "value", "assigned", "comes from" | dfg |
| Impact | "affects", "changes", "slice", "dependencies" | slice/pdg |
| Debug | "bug", "error", "investigate", "broken" | cfg + dfg + context |

## Automatic Hook Integration

The `tldr-read-enforcer` and `tldr-context-inject` hooks automatically:
1. Detect intent from your messages
2. Route to appropriate layers
3. Inject context into tool calls

You don't need to manually run these commands - the hooks do it for you.

## Manual Override

If you need a specific layer the hooks didn't provide:

```bash
# Force specific analysis — generation only, NOT validation
tldr cfg path/to/file.py function_name
tldr dfg path/to/file.py function_name
tldr slice path/to/file.py function_name 42

# STOP GATE: After running manual override, do NOT claim correctness.
# Output is EVIDENCE for a separate validation phase.
# Do NOT say "this function is complex" as if it were a verdict.
# Say instead: "cfg shows cyclomatic complexity of 12 — threshold for review is 10"
```

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
