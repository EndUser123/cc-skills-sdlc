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

Comprehensive cross-file analysis for Python packages that goes beyond single-file reviews. Detects architectural issues like circular dependencies, path traversal vulnerabilities, documentation inconsistencies, and import-time side effects.

## When to Use

Use `/meta-review` when you need:
- **Security analysis**: Path traversal vulnerability detection with taint propagation
- **Architecture validation**: Circular dependency and layering violation detection
- **Quality checks**: Documentation consistency across files
- **Performance analysis**: Disk I/O at import time, module-level side effects

## Replaces These Skills

`/meta-review` provides superior cross-file analysis compared to these single-focus skills:

| Old Skill | Replacement Perspective | Why Meta-Review is Better |
|-----------|------------------------|----------------------------|
| `//p` | `quality` | Cross-file analysis vs single-file checks |
| `/`ruff` (automatic) + `/p`` | `security,performance` | Taint propagation + import graph vs async-only patterns |
| `/code-standards` | `quality` | Doc consistency + import graph vs style checks |
| `/slc (solo-dev compliance)` | `quality` | Architectural validation + doc checks vs gatekeeping |
| `/comply` | `quality` | Cross-file invariant validation vs single-file compliance |

**Note**: These skills are NOT removed. They remain available for specialized use cases. `/meta-review` is recommended for comprehensive Python package analysis.

For migration instructions, see `references/migration-guide.md`.

## How It Works (Overview)

1. **Create analysis unit** from package directory
2. **Run analyzers**: path_traversal (security), import_graph (architecture/performance), doc_consistency (quality)
3. **Prepare agent context** with a perspective lens (security, performance, quality, architecture, or all)

For full API details and code examples, see `references/analyzer-api.md`.

## Perspectives

| Perspective | Analyzers | Detects |
|-------------|------------|----------|
| `security` | path_traversal | Path traversal via user input, bypass techniques |
| `performance` | import_graph | Circular deps, disk I/O at import, side effects |
| `quality` | doc_consistency | Missing docstrings, outdated docs |
| `architecture` | import_graph | Layering violations, circular dependencies |
| `all` | All analyzers | Comprehensive analysis |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `META_REVIEW_ENABLED` | `true` | Enable/disable meta-review system |
| `META_REVIEW_MAX_TOKENS` | `8000` | Default token budget for agent context |

### Disabling Meta-Review

```bash
# Disable meta-review (falls back to legacy validation)
export META_REVIEW_ENABLED=false

# Re-enable
unset META_REVIEW_ENABLED
```

## Output Format, Integration Points & Examples

For output format details, `/package` and `/p` integration, and usage examples (security review, custom layering policy), see `references/output-format-and-examples.md`.

## Changelog

See `references/changelog.md` for version history.

## See Also

- **Analyzer API**: `references/analyzer-api.md`
- **Analysis Unit API**: `lib/analysis_unit/__init__.py`
- **Analyzers**: `lib/analysis_unit/analyzers/`
- **Context Preparation**: `lib/meta_review/prepare_context.py`
- **Integration Tests**: `tests/integration/test_meta_review_integration.py`
- **Regression Suite**: `tests/integration/test_known_bad_packages.py`
