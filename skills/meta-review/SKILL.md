---
name: meta-review
description: Cross-file meta-review system for Python packages with security, performance, and quality analysis.
version: 1.0.0
status: stable
category: execution
triggers:
  - /meta-review
aliases:
  - /meta-review

suggest:
  - //p
  - /q
  - /package
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
