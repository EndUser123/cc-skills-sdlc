---
name: meta-review
description: Cross-file meta-review system for Python packages with security, performance, and quality analysis.
---
# Meta-Review Skill

## Purpose

Comprehensive cross-file analysis for Python packages that goes beyond single-file reviews.

**Mandatory Protocol:** See `__lib/adversarial_review_protocol.md` for the Critic persona and cross-file integration checks.

## When to Use

Use `/meta-review` for:
- **Security analysis**: Path traversal detection with taint propagation.
- **Architecture validation**: Circular dependency and layering checks.
- **Quality checks**: Documentation consistency across files.
- **Performance analysis**: Module-level side effects and disk I/O at import.

## Replaces These Skills

- `//p` (Single-file quality)
- `/code-standards` (Style checks)
- `/comply` (Single-file compliance)

## Perspectives

| Perspective | Focus |
|-------------|------------|
| `security` | Taint propagation, path traversal via input. |
| `performance` | Circular deps, import-time I/O. |
| `quality` | Missing docstrings, outdated docs. |
| `architecture` | Layering violations, abstraction leaks. |

## Configuration

`META_REVIEW_ENABLED` (default: true)
`META_REVIEW_MAX_TOKENS` (default: 8000)

## Output Format

See `__lib/adversarial_review_protocol.md` for the required findings schema and severity ratings.

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
