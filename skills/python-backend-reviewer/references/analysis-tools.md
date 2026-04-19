# Analysis Tools Reference

Detailed documentation for the four analysis tools used by the Python Backend Reviewer.

---

## detect_duplicates.py

Finds duplicate code blocks using AST analysis.

**Usage:**

```bash
uv run python scripts/detect_duplicates.py <path>
uv run python scripts/detect_duplicates.py --min-lines 10 <path>
```

**Detects:**

- Duplicate functions (identical implementations)
- Duplicate classes
- Repeated code blocks

**Options:**

- `--min-lines N`: Minimum lines for a block to be considered (default: 5)

---

## analyze_imports.py

Analyzes import organization and detects recreated utilities.

**Usage:**

```bash
uv run python scripts/analyze_imports.py <path>
```

**Detects:**

- Wildcard imports (`from module import *`)
- Relative imports in non-package contexts
- Functions that look like reimplemented utilities
- Common patterns that should use libraries

**Common utilities flagged:**

- JSON serialization -> use `json` or `orjson`
- Retry logic -> use `tenacity` or `backoff`
- Validation -> use `pydantic`
- HTTP clients -> use `requests` or `httpx`

---

## complexity_analyzer.py

Measures cyclomatic complexity, function length, and nesting depth.

**Usage:**

```bash
uv run python scripts/complexity_analyzer.py <path>
uv run python scripts/complexity_analyzer.py --max-complexity 10 --max-length 50 <path>
```

**Metrics:**

- **Cyclomatic complexity**: Number of decision points (default threshold: 10)
- **Function length**: Lines in function (default threshold: 50)
- **Nesting depth**: Maximum levels of nested control structures (threshold: 4)
- **God classes**: Classes with 20+ methods

**Options:**

- `--max-complexity N`: Cyclomatic complexity threshold (default: 10)
- `--max-length N`: Function length threshold (default: 50)

---

## concurrency_analyzer.py

Detects concurrency issues in async Python code.

**Usage:**

```bash
uv run python scripts/concurrency_analyzer.py <path>
```

**Detects:**

- Shared state mutation in async methods (`self.x = y` in async def)
- Module-level mutable state (shared across requests)
- Missing synchronization patterns
- Potentially unsafe singleton patterns

**Severity levels:**

- **Critical**: Mutation of shared state like `client`, `session`, `agent`, `config`
- **Warning**: Any `self.attr` mutation in async context
- **Info**: Module-level mutable objects

**When to use:** Run on services, handlers, and workflow code that handles concurrent requests.

---

## Reference Documentation Guide

### python_antipatterns.md

Comprehensive catalog of anti-patterns with examples:

- Code duplication patterns
- Over-engineering examples
- God objects
- Complexity issues
- Import problems
- Error handling mistakes
- Performance anti-patterns

**Use when:** You identify an issue but need to see the anti-pattern and solution

### refactoring_patterns.md

Step-by-step refactoring techniques:

- Extract function/variable
- Consolidate duplicates
- Simplify conditionals
- Break up god classes
- Reduce complexity
- Improve imports

**Use when:** You know what's wrong and need concrete refactoring steps

### best_practices.md

Python backend best practices and principles:

- Core principles (DRY, SOLID)
- Code organization
- Type hints
- Error handling
- Async patterns
- Database practices
- API design
- Security guidelines

**Use when:** Establishing coding standards or need authoritative guidance
