# Workflow Procedures

Detailed step-by-step procedures for each review workflow.

---

## Review a Python File

When a user asks to review a specific file:

1. **Run all analysis tools** on the file:

   ```bash
   python scripts/detect_duplicates.py path/to/file.py
   python scripts/analyze_imports.py path/to/file.py
   python scripts/complexity_analyzer.py path/to/file.py
   ```

2. **Analyze results** and categorize issues:
   - Critical: Duplicates, high complexity, security issues
   - Important: Utility reimplementation, deep nesting
   - Minor: Style issues, minor inefficiencies

3. **Provide specific fixes**:
   - Quote exact code locations with line numbers
   - Show before/after examples
   - Explain why the change improves the code

4. **Offer to implement fixes** if requested

---

## Check Backend for Duplicates

When a user asks to check a project/module for duplicates:

1. **Run duplicate detection** on the entire directory:

   ```bash
   python scripts/detect_duplicates.py src/
   ```

2. **Group duplicates by severity**:
   - High: 10+ lines duplicated, 3+ occurrences
   - Medium: 5-10 lines, 2+ occurrences
   - Low: Helper functions that could be extracted

3. **Recommend consolidation strategy**:
   - Extract to shared utilities for cross-cutting concerns
   - Create base classes for inherited behavior
   - Use decorators for repeated patterns

---

## Analyze Module Over-Engineering

When code appears over-engineered:

1. **Run complexity analysis**:

   ```bash
   python scripts/complexity_analyzer.py --max-complexity 10 --max-length 50 path/
   ```

2. **Identify over-engineering patterns**:
   - Premature abstractions (base classes with one implementation)
   - Excessive configuration options
   - God classes (20+ methods)
   - Deep inheritance hierarchies

3. **Suggest simplifications**:
   - Replace abstractions with simple functions
   - Remove unused configuration
   - Split god classes by responsibility
   - Flatten inheritance

4. **Reference specific patterns** from [python_antipatterns.md](python_antipatterns.md)

---

## Optimize Following Best Practices

When asked to optimize code or ensure best practices:

1. **Run all analysis tools** to get baseline metrics

2. **Check against best practices**:
   - DRY principle violations
   - SOLID principle violations
   - Type hint coverage
   - Error handling patterns
   - Async/await consistency

3. **Prioritize optimizations**:
   - First: Correctness (bugs, security)
   - Second: Maintainability (duplicates, complexity)
   - Third: Performance (N+1 queries, inefficiencies)
   - Fourth: Style (naming, imports)

4. **Reference [best_practices.md](best_practices.md)** for specific guidelines

---

## Analyze Concurrency Safety

When reviewing async code that handles concurrent requests:

1. **Run concurrency analysis**:

   ```bash
   uv run python scripts/concurrency_analyzer.py services/ workflows/
   ```

2. **Prioritize by severity**:
   - **Critical**: Fix before production deployment
   - **Warning**: Review for actual sharing patterns
   - **Info**: Consider but often acceptable

3. **Apply fixes** -- see [concurrency-patterns.md](concurrency-patterns.md) for code examples

4. **Alternative patterns**:
   - Pass state through parameters (preferred)
   - Use `contextvars` for request-scoped data
   - Use `asyncio.Lock` for truly shared state
   - Create new instances per request
