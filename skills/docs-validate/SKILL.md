---
name: docs-validate
description: This skill should be used when the user asks to "validate documentation", "check docs", "docs quality", "check documentation quality", or "validate markdown files". Provides manual documentation quality validation with automated checks and actionable fix suggestions.
---
# Documentation Quality Validation

Validate documentation quality using automated checks and receive actionable improvement suggestions.

## Purpose

Manual documentation quality validation for Claude Code skills and plugins. Detect common documentation issues that reduce clarity and maintainability.

## When to Use

Trigger this skill when:
- User asks to "validate documentation", "check docs", "docs quality"
- User mentions "check documentation quality" or "validate markdown"
- Reviewing SKILL.md files or markdown documentation
- Ensuring documentation meets progressive disclosure standards
- Pre-publish documentation validation

## Workflow

1. **Identify Target**: Determine documentation directory or file to validate
2. **Run Validation**: Execute DocumentationValidator with all checks
3. **Categorize Issues**: Group findings by severity and type
4. **Suggest Fixes**: Provide actionable recommendations for each issue
5. **Generate Report**: Output structured validation report

## Quick Start

**Automatic Validation** (default behavior):
- PostToolUse hook automatically validates all .md file writes in skills directories
- Returns warning messages (non-blocking) when issues found
- Works for all skills, not just `/package`

**Manual Validation** (comprehensive reports):
```bash
# Validate specific documentation directory
/docs-validate P://.claude/skills/my-skill

# Validate current directory
/docs-validate

# Check documentation quality
check documentation quality in P://packages/my-project/docs
```

## Integration

Uses the `DocumentationValidator` class from `/package` skill:

```python
from skills.package.resources.validate_docs import DocumentationValidator

validator = DocumentationValidator("/path/to/docs")
issues = validator.validate_all()
```

### Automatic Validation (Core Integration)

**PostToolUse Hook**: Automatic validation via `PostToolUse_documentation_validator.py`:
- **Trigger**: Write/Edit operations on `.md` files in skills directories
- **Behavior**: Validates documentation quality after each write
- **Output**: Returns warning dict (non-blocking) or `permissionDecision=deny` (blocking mode)
- **Scope**: All skills directories, not just `/package`

No manual setup required -- the hook is automatically registered.

### Manual Validation

`/docs-validate` provides comprehensive reports with:
- Detailed issue descriptions and fix recommendations
- Issue severity categorization
- File-by-file analysis

Use for pre-publish quality sweeps, comprehensive audits, or analyzing specific issues.

## Validation Checks

The validator detects four issue types:

| Check | Detection | Impact |
|-------|-----------|--------|
| **Circular References** | Files A and B cross-reference each other, both under 50 lines | Navigation traps -- users never find substantive content |
| **Incomplete Content** | File under 50 lines with "See [other-file]" and no substance | Violates progressive disclosure |
| **Version Conflicts** | Documentation references outdated versions (v5.1 vs v5.2+) | Failed conversions or migrations |
| **Broken Cross-References** | "See [file](path.md)" points to non-existent file | Dead-end links |

See **references/validation-checks.md** for detailed detection rules, examples, and fixes for each check.

## Issue Severity Levels

| Level | Impact | Examples |
|-------|--------|---------|
| **Critical** | Blocks usage | Circular references, broken cross-refs to essential content, version conflicts |
| **Important** | Reduces quality | Incomplete content, minor version inconsistencies, missing progressive disclosure |
| **Nice-to-have** | Polish | Style inconsistencies, missing examples, outdated contact info |

## Output Format

```
## Documentation Validation Report

Target: P://.claude/skills/my-skill
Issues Found: 3

### Critical (1)
1. Circular Reference: a.md <-> b.md
   - Both files under 50 lines with cross-references
   - Fix: Expand one file, remove circular reference

### Important (2)
2. Incomplete Content: guide.md (17 lines)
   - Contains "See full-guide.md" without substantive content
   - Fix: Add essential content to guide.md

3. Broken Reference: advanced.md missing
   - quick-start.md references non-existent advanced.md
   - Fix: Create file or update reference

## Summary
- Files Scanned: 12
- Issues: 3 (1 critical, 2 important)
- Recommendation: Fix circular reference first, then expand stub content
```

See **references/examples.md** for more usage examples.

## Configuration

Automatic validation behavior is configured per skill via `.claude/docs-validate.local.md`.

**Quick config options:**

| Option | Default | Values |
|--------|---------|--------|
| `mode` | `suggestive` | `suggestive`, `blocking`, `off` |
| `severity_threshold` | `medium` | `low`, `medium`, `high` |
| `auto_validate` | `true` | `true`, `false` |

See **references/configuration.md** for:
- Configuration file structure and examples
- Intelligent mode selection logic
- DRY-RUN report behavior and workflow

## Quality Checklist

Before publishing documentation:

- [ ] No circular references between stub files
- [ ] All cross-references point to existing files
- [ ] Version references match current codebase
- [ ] Main files have 50+ lines of substantive content
- [ ] Progressive disclosure structure (lean body, detailed refs)
- [ ] Examples use imperative form ("Run X" not "You should run X")
- [ ] Third-person description with trigger phrases
- [ ] No platform-specific hardcoded paths
- [ ] Error handling documented (if applicable)

## Troubleshooting

See **references/validation-checks.md** for troubleshooting guidance on:
- False positives (flags non-issues)
- Missing issues (obvious problems not caught)
- Import errors (DocumentationValidator not found)

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

- **PostToolUse Hook**: Automatic validation enabled by default for all skills
- **Manual Validation**: `/docs-validate` command provides comprehensive reports
- **Shared Validator**: Uses same `DocumentationValidator` class as `/package`

## Related Documentation

- **/package skill**: Complete package creation and validation workflow
- **references/configuration.md**: Configuration options and DRY-RUN behavior
- **references/validation-checks.md**: Check details, best practices, troubleshooting
- **references/examples.md**: Real-world usage examples
- **Progressive Disclosure**: Lean SKILL.md with detailed references/
