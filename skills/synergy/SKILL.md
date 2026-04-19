---
name: synergy
description: "Detect cross-file refactoring opportunities (extract, merge, consolidate, standardize, restructure)"
version: "1.0.0"
status: stable
category: analysis
triggers:
  - /synergy
  - "synergy detection"
  - "cross-file refactor"
aliases:
  - /synergy

suggest:
  - /refactor
  - /p2

depends_on_skills:
  - /refactor
---

## Code Editing Patterns

For Python code editing patterns and anti-patterns:
- **Authority**: /p Neural Cache
- **Example**: `/search "ThreadPoolExecutor KeyboardInterrupt immediate cleanup"`
- **Example**: `/search "string manipulation AST LibCST code editing"`

Reflect automatically propagates code editing learnings to /p. Query CKS for patterns.


# /synergy - Cross-File Synergy Detection

## Purpose

Detect cross-file refactoring opportunities without making changes. Runs `/refactor --dry-run` to identify synergies that per-file analysis misses.

**Core question:** "What cross-file improvements exist?"

**What this does:**
- Runs `/refactor --dry-run` on target
- Identifies: extract, merge, consolidate, standardize, restructure opportunities
- Reports findings with severity ratings (HIGH/MEDIUM/LOW)
- Does NOT modify code

## Your Workflow

When `/synergy` is invoked:

### Step 1: Detect Target Scope

```bash
# If no target, use current directory
TARGET="${1:-.}"

# Check if single file or multi-file
git diff --name-only HEAD | wc -l
```

**Skip if single file** — synergies require 2+ files.

### Step 2: Run Refactor Dry-Run

```bash
# Run refactor in dry-run mode
/refactor "${TARGET}" --dry-run
```

### Step 3: Aggregate and Present Findings

Format output:
```
## Synergy Detection: ${TARGET}

**Scope:** ${file_count} files analyzed

**Findings:** ${total}

| Severity | Count | Type | Example |
|----------|-------|------|---------|
| HIGH     | 2     | Restructure | Circular dependency: auth.py → session.py |
| MEDIUM   | 5     | Standardize | Inconsistent error handling in 5 files |
| LOW      | 3     | Extract | Common validation logic in controllers/ |

[Detailed findings...]

**Next actions:**
- /refactor ${TARGET} --apply     # Apply all findings
- /refactor ${TARGET} --interactive  # Interactive mode
- /p2 ${TARGET}                     # Full adversarial review
```

## Severity Mapping

| Synergy Type | Priority | Rationale |
|---------------|----------|-----------|
| Restructure (circular deps) | HIGH | Blocks correct operation |
| Standardize (inconsistent patterns) | HIGH | Causes bugs, confusion |
| Extract / Consolidate / Merge | MEDIUM | Maintainability, DRY |
| Extract / Consolidate / Merge (large >20 lines) | HIGH | Significant duplication |

## Usage

```
/synergy                   # Analyze current directory
/synergy src/              # Analyze specific directory
/synergy src/auth.py       # Single file → skips (no synergies)
/synergy --json             # JSON output for tools
```

## What This Does NOT Do

- Does NOT modify code (dry-run only)
- Does NOT create new files
- Does NOT run on single files (no cross-file synergies)
- Does NOT replace `/refactor` — it's a convenience wrapper

## Difference from /refactor

| Aspect | /synergy | /refactor |
|--------|----------|-----------|
| Scope | Detection only | Detection + application |
| Mode | Always dry-run | Dry-run or apply |
| Focus | Cross-file patterns | Full refactor capability |
| Output | Human-readable | Multiple formats |
| Use case | Quick opportunity scan | Complete refactoring workflow |
