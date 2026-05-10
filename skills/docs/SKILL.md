---
name: docs
description: Unified document system with locality awareness
version: "1.0.0"
status: "stable"
category: doc
aliases:
  - '/docs'

suggest:
  - /search
  - /cks
  - /research
triggers:
  - '/docs'
---

> [!CAUTION]
> **Context Safety**: In long sessions, run `/compact` before `/docs` to avoid context overflow.
>
> **Scope**: NEVER analyze whole codebase. Only: (1) git log files, (2) explicit target files, (3) locality parents.

# /docs - Documentation Automation

## Purpose

Unified document system with locality awareness -- intelligent document orchestration maintaining documentation hygiene through lazy mode (auto-detection) and structural locality awareness.

## EXECUTION DIRECTIVE

**When invoked, execute this workflow:**

```
MANDATORY:

1. DETERMINE MODE from invocation:
   - No arguments -> LAZY MODE (default)
   - File/directory argument -> TARGETED MODE
   - --scan-repository flag -> SCAN MODE
   - --dry-run flag -> DRY RUN (show only, no changes)

2. LAZY MODE (default):
   a) Run git status to find modified files
   b) For each modified file, identify documentation in locality:
      - Same directory README.md, CLAUDE.md, ARCHITECTURE.md, CHANGELOG.md
      - Parent directory docs for nested modules
   c) Read existing documentation
   d) ACTUALLY UPDATE the docs (Write tool) -- not just report
   e) Confirm each update with file read
   f) Report what was updated

3. TARGETED MODE:
   a) Read target file/directory
   b) Check for documentation in same location
   c) Detect missing core docs
   d) Create or update as needed (using Write tool)
   e) Report changes

4. SCAN MODE:
   a) Walk repository for directories with code files
   b) Check each for CLAUDE.md
   c) Report all missing documentation

5. DRY RUN: Skip all Write/Edit operations, report what WOULD be done

DEFAULT (no arguments): Lazy mode with git status

DO NOT:
- Report "documentation needs update" WITHOUT UPDATING IT
- Ask "should I update docs?" -- just update
- Skip documentation "to save time"
- Consider task complete until docs are ACTUALLY UPDATED

CRITICAL: Step 2d says "ACTUALLY UPDATE the docs (Write tool)"
- Use Write tool to make changes
- Do NOT just say "docs need updating"
- Do NOT wait for user confirmation
- UPDATE THE DOCUMENTATION

If git commands fail: Report exact error message. Do NOT fabricate results.
```

---

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **Documentation is mandatory**: Update docs before claiming completion
- **Locality awareness**: Documentation co-located with code (README, CLAUDE.md, ARCHITECTURE.md in same directory)
- **No asking "should I?"**: Update docs if change is significant, don't wait for instruction

### Technical Context
- **Lazy mode**: Auto-detect changes via git log (NOT git status -- handles auto-commit hooks)
- **Targeted mode**: Document specific files or directories
- **Repository scan**: Full health check for missing/stale docs
- **Core docs**: CLAUDE.md (module context), README.md (general), ARCHITECTURE.md (design), CHANGELOG.md (history)

### Architecture Alignment
- Integrates with /search (find docs), /cks (knowledge), /research (external docs)
- Links to /init (create CLAUDE.md), /test (verify docs match code), /commit (commit code+docs together)

## Validation Rules

- **Before claiming completion**: Check for documentation files in modified directory
- **After code changes**: Update relevant docs immediately (maintenance obligation)
- **When CLAUDE.md missing**: Run /init to create it
- **Anti-pattern**: Modifying code without updating docs, asking "should I update docs?", leaving "TODO: update docs"

### Prohibited Actions
- Modifying code without updating relevant docs
- Asking "Should I update docs?" (just update if significant)
- Leaving "TODO: update docs" comments
- Skipping CLAUDE.md for code modules

## When to Use

- **After coding:** Run `/docs` to auto-update relevant documentation
- **During changes:** "I need to document this new feature"
- **Maintenance:** "Scan repo for stale docs"

## Locality-Aware Documentation

Documentation must be checked and updated in the same directory as modified files. Core docs (CLAUDE.md, README.md, ARCHITECTURE.md, CHANGELOG.md) are required; extended docs (API.md, DEVELOPING.md, etc.) are optional. See [references/locality-aware-docs.md](references/locality-aware-docs.md) for the full checklist and missing-doc remediation rules.

## CSF Project Documentation

For CSF-specific documentation ($__CSF_ROOT/, P:\\\\\\packages\, .claude\hooks\, .claude\skills\), the project uses a hierarchical README tree with cross-reference update rules.

- **CSF README updates**: See [references/csf-readme-updates.md](references/csf-readme-updates.md) -- when and how to update $__CSF_ROOT/README.md, including the documentation file requirements table
- **CSF README tree structure**: See [references/csf-readme-tree.md](references/csf-readme-tree.md) -- hierarchical README layout, documentation update rules per path, and skill-specific documentation sync

## Workflow

### 1. Lazy Mode (Default)

Running `/docs` without arguments triggers Lazy Mode:

1. Analyzes git log (recent commits)
2. Checks for missing core documentation files
3. Checks chat context
4. Updates relevant docs

[Read Lazy Mode Details](resources/lazy-mode.md)

### 2. Targeted Mode

```bash
/docs "src/feature/login.py"  # Document specific file
/docs "docs/"                 # Audit documentation folder
```

### 3. Repository Scan

```bash
/docs --scan-repository       # Full health check
```

## Dry Run Mode

`/docs --dry-run` shows what documentation would be updated without making changes:

**Output includes:**
- Missing core documentation files (CLAUDE.md, README.md, etc.)
- Files that need documentation updates
- Stale documentation that needs refreshing
- Recommended `/init` targets

## Writing Standards

Documentation must be scannable, actionable, specific, and testable. See [references/writing-guide.md](references/writing-guide.md) for:
- Four Pillars philosophy and Be Specific writing rules
- Format Selection Guide (runbook, playbook, SOP, decision tree, ADR, etc.)
- Anti-patterns table and DO/DON'T lists
- Definition of Done template
- Code documentation best practices (regex escaping, etc.)

## AID Integration

Documentation generation via AI Distiller for single-file or multi-file docs, API references, and legacy code discovery. See [references/aid-integration.md](references/aid-integration.md) for commands, capabilities, and when to use AID.

## Next Steps

**If docs are updated:**

1. Complete. (If covers all changes)
2. `/test` (Verify changes matches docs)
3. `/commit` (Commit code + docs together)
