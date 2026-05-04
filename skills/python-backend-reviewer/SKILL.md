---
name: python-backend-reviewer
description: Expert Python backend code reviewer that identifies over-complexity, duplicates, bad optimizations, and violations of best practices. Use when asked to review Python code quality, check for duplicate code, analyze module complexity, optimize backend code, identify anti-patterns, or ensure adherence to best practices. Ideal for preventing AI-generated code from creating unnecessary files instead of imports, finding repeated validation logic, and catching over-engineered solutions.
version: 1.0.0
status: stable
category: code-review
---

# Python Backend Code Reviewer

Expert analysis and refactoring of Python backend code to eliminate duplication, reduce complexity, and enforce best practices.

**Mandatory Protocol:** See `__lib/adversarial_review_protocol.md` for the Critic persona and backend-specific logic/scaling checks.

## Overview

This skill helps identify and fix common issues in Python backend code:
- **Duplicate code** across files.
- **Complexity** in async flows.
- **Concurrency issues** (shared state mutation).
- **Import side-effects**.

## Architecture-Aware Prioritization

**Correctness in critical paths > Complexity in secondary paths.**

| Finding | Critical Path | Secondary Path |
|---------|---------------|----------------|
| Shared state mutation | 🔴 Fix immediately | 🟡 Review |
| High complexity (>25) | 🟡 Refactor carefully | 🟢 Backlog |
| Duplicates | 🟡 Extract if >3 | 🟢 Nice to have |

## Pragmatic Thresholds

| Metric | Strict | Pragmatic |
|--------|--------|-----------|
| Cyclomatic complexity | 10 | **25** |
| Function length | 50 lines | **150 lines** |
| Nesting depth | 4 | **5** |

## Quick Start

```bash
# Detect duplicates
uv run python scripts/detect_duplicates.py <path>

# Check complexity
uv run python scripts/complexity_analyzer.py <path>

# Concurrency safety
uv run python scripts/concurrency_analyzer.py <path>
```

## Output Format

See `__lib/adversarial_review_protocol.md` for the required findings schema and severity ratings.
