---
name: deliberate-changes
description: Manage deliberate hook configuration changes to prevent false positives in validation systems
version: "1.0.0"
status: "stable"
category: utilities
triggers:
  - /deliberate-changes
aliases:
  - /deliberate-changes

suggest:
  - /comply
  - /validate
  - /standards
---

# Deliberate Changes Management

Manage deliberate hook configuration changes to prevent false positives in validation systems.

## Purpose

Manage deliberate hook configuration changes to prevent false positives in validation systems.

## Project Context

### Constitution/Constraints
- Follows CLAUDE.md constitutional principles
- Solo-dev appropriate (Director + AI workforce model)
- Prevents false positives from deliberate configuration changes

### Technical Context
- Stores changes in `.claude/deliberate_hook_changes.jsonl`
- Tracks hook-type, change-type, description, reason
- Supports validation and cleanup operations

### Architecture Alignment
- Part of CSF NIP validation system
- Integrates with /comply and /validate workflows
- Prevents validation system false positives

## Your Workflow

1. Record deliberate change with full context
2. List active changes when validation fails
3. Mark changes as validated after testing
4. Clean up old/expired changes periodically

## Validation Rules

- All changes must include description and reason
- Changes must be validated after testing
- Old changes should be cleaned up
- Record hook-type and change-type accurately

## Quick Start

```bash
/deliberate-changes record --hook-type pre_tool_use --change-type parameter_change --description "Increased timeout" --reason "API has higher latency"
/deliberate-changes list --active
/deliberate-changes validate 5
/deliberate-changes cleanup
```

## Subcommands

### record
Record a deliberate change.

```bash
/deliberate-changes record --hook-type <type> --change-type <type> --description "<desc>" --reason "<reason>"
```

### list
List changes with filtering.
```bash
/deliberate-changes list --hook-type pre_tool_use --validated-only --active
```

### validate
Mark a change as validated.
```bash
/deliberate-changes validate <id>
```

### cleanup
Remove old or expired changes.
```bash
/deliberate-changes cleanup --older-than-days 30
```

## File Location
Changes stored in: `.claude/deliberate_hook_changes.jsonl`
