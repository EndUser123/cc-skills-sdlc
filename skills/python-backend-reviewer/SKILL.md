---
name: python-backend-reviewer
description: Expert Python backend code reviewer that identifies over-complexity, duplicates, bad optimizations, and violations of best practices. Use when asked to review Python code quality, check for duplicate code, analyze module complexity, optimize backend code, identify anti-patterns, or ensure adherence to best practices. Ideal for preventing AI-generated code from creating unnecessary files instead of imports, finding repeated validation logic, and catching over-engineered solutions.
version: 1.0.0
status: stable
category: code-review
---

# Python Backend Code Reviewer

Expert analysis and refactoring of Python backend code to eliminate duplication, reduce complexity, and enforce best practices.

## Overview

This skill helps identify and fix common issues in Python backend code, particularly problems introduced by AI code generation:

- **Duplicate code** across multiple files
- **Recreated utilities** instead of imports
- **Over-engineered** solutions
- **High complexity** functions and classes
- **Anti-patterns** and code smells
- **Concurrency issues** in async code (shared state mutation)

The skill provides automated analysis tools and comprehensive refactoring guidance.

## ⚠️ Architecture-Aware Prioritization

**Static analysis finds issues, but architectural context determines priority.**

Before prioritizing fixes, identify:

1. **Critical paths**: Which code runs on every request?
   - WebSocket/HTTP handlers
   - Main workflow orchestration
   - Shared services/middleware

2. **Secondary paths**: Less critical code
   - CLI tools
   - Scripts
   - Dev-only utilities
   - One-time migrations

3. **Concurrency model**: How is state shared?
   - Are handlers concurrent?
   - Are instances shared across requests?
   - Is there mutable singleton state?

**Prioritization rule**: Correctness in critical paths > Complexity in secondary paths

| Finding               | Critical Path                | Secondary Path  |
| --------------------- | ---------------------------- | --------------- |
| Shared state mutation | 🔴 Fix immediately           | 🟡 Review       |
| High complexity (>25) | 🟡 Refactor carefully        | 🟢 Backlog      |
| Duplicates            | 🟡 Extract if >3 occurrences | 🟢 Nice to have |
| God class             | 🟡 Migrate to façade         | 🟢 Low priority |

## Pragmatic Thresholds

For **orchestration/workflow code**, use realistic thresholds:

| Metric                | Strict Threshold | Pragmatic Threshold | Notes                                        |
| --------------------- | ---------------- | ------------------- | -------------------------------------------- |
| Cyclomatic complexity | 10               | **25**              | Orchestrators naturally have decision points |
| Function length       | 50 lines         | **150 lines**       | Async flows can be longer                    |
| Nesting depth         | 4                | **5**               | Guard clauses help more than extracting      |
| God class methods     | 20               | **N/A**             | OK if it's a **façade** that delegates       |

**Hard limits (always fix):**

- No functions > 300 lines
- No nesting > 7 levels
- No shared-state mutation without synchronization guard

## Quick Start

### 1. Run Automated Analysis

Start with automated tools to identify issues:

```bash
# Detect duplicate code blocks
uv run python scripts/detect_duplicates.py <path>

# Analyze imports and utility reimplementation
uv run python scripts/analyze_imports.py <path>

# Check code complexity
uv run python scripts/complexity_analyzer.py <path>

# Check for concurrency issues (shared state mutation)
uv run python scripts/concurrency_analyzer.py <path>
```

### 2. Review Analysis Results

Each tool outputs:

- **Severity levels**: Warnings (must fix) vs Info (should review)
- **File locations**: Exact line numbers for each issue
- **Specific recommendations**: What to change and why

### 3. Apply Fixes

Use the reference guides to refactor issues:

- See [refactoring_patterns.md](references/refactoring_patterns.md) for step-by-step fixes
- See [python_antipatterns.md](references/python_antipatterns.md) for anti-pattern examples
- See [best_practices.md](references/best_practices.md) for Python conventions

## Main Workflows

See [workflows.md](references/workflows.md) for detailed step-by-step procedures.

| Workflow | When | Key Tool |
|----------|------|----------|
| Review a file | "Review this code" | All analysis tools |
| Check duplicates | "Find duplicate code" | `detect_duplicates.py` |
| Over-engineering | "Is this over-engineered?" | `complexity_analyzer.py` |
| Best practices | "Optimize this code" | All tools + best_practices.md |
| Concurrency safety | "Check async code" | `concurrency_analyzer.py` |

All workflows follow: **Run analysis -> Categorize by severity -> Provide specific fixes with line numbers**.

## Reference Files

| File | Contents |
|------|----------|
| [analysis-tools.md](references/analysis-tools.md) | Tool usage, options, metrics, and reference doc guide |
| [workflows.md](references/workflows.md) | Step-by-step procedures for each workflow |
| [example-reviews.md](references/example-reviews.md) | Concrete review examples with code |
| [concurrency-patterns.md](references/concurrency-patterns.md) | Async concurrency fixes and patterns |
| [refactoring_patterns.md](references/refactoring_patterns.md) | Step-by-step refactoring techniques |
| [python_antipatterns.md](references/python_antipatterns.md) | Anti-pattern catalog with examples |
| [best_practices.md](references/best_practices.md) | Python backend best practices |

## When NOT to Refactor

⚠️ Avoid refactoring when:

- No tests exist and can't be added
- Close to deadline
- Code won't be modified again
- Would break public APIs without migration path

## Output Format

When reviewing code, structure feedback as:

1. **Summary**: Brief overview of findings
2. **Critical Issues**: Must-fix problems (duplicates, security)
3. **Important Issues**: Should-fix problems (complexity, utilities)
4. **Suggestions**: Nice-to-have improvements
5. **Code Examples**: Specific before/after for each issue
6. **Next Steps**: Recommended action plan

Always include:

- Exact file paths and line numbers
- Severity level for each issue
- Concrete code examples
- References to patterns/practices when applicable
