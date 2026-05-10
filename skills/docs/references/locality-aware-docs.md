# Locality-Aware Documentation Rules

## Automatic Trigger After File Modifications

When you modify files in a directory, **BEFORE claiming completion**:

### 1. Check for Documentation Files

**Core Documentation (Required):**
- `CLAUDE.md` - Module context for Claude Code (use `/init` to create)
- `README.md` - General documentation for humans
- `ARCHITECTURE.md` - System design and component relationships
- `CHANGELOG.md` - Version history and notable changes

**Extended Documentation (Optional):**
- `CONTRIBUTING.md` - Contribution guidelines
- `DEVELOPING.md` - Development setup and workflow
- `API.md` - API reference documentation
- `DESIGN.md` - Design documents and decisions
- Any `*.md` file describing the modified component

### 2. If Core Docs Are MISSING

- `CLAUDE.md` missing -> Run `/init <target>` to create it
- `README.md` missing -> Recommend creating it
- `ARCHITECTURE.md` missing -> Flag for creation if module is complex
- `CHANGELOG.md` missing -> Flag for creation if library/package

### 3. If Docs Exist and Changes Affect Behavior

- Update those docs immediately
- **Do not wait for user instruction** - this is a maintenance obligation

### 4. Example Pattern

```
Modified: P:\\\\\\.claude/hooks/StopHook_reality_check.py
  -> Auto-Check: P:\\\\\\.claude/hooks/README.md, P:\\\\\\.claude/hooks/ARCHITECTURE.md
  -> Action: Add new hook to catalog and architecture map
```
