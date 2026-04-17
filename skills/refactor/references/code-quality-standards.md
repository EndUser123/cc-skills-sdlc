# Code Quality Standards

**Purpose**: These standards guide refactoring decisions — what to simplify, consolidate, or standardize. They apply to ALL code changes during the REFACTOR phase.

## Refactoring Quality Targets

**DRY (Don't Repeat Yourself)**:
- **Copy-pasted code blocks** → Extract to shared function
- **Repeated conditionals** → Create predicate function
- **Magic numbers** → Use named constants
- **Duplicated business logic** → Consolidate to single source of truth

**Separation of Concerns**:
- **Functions mixing I/O with business logic** → Split layers
- **Classes with unrelated methods** → Split by responsibility
- **Modules containing unrelated utilities** → Organize by domain

**Complexity Reduction**:
- **Deep nesting (>4 levels)** → Extract functions, use early returns
- **God objects (classes doing everything)** → Split by responsibility
- **Feature envy (using more of another class)** → Move to appropriate class
- **Long functions (>50 lines)** → Break into smaller, focused functions

## Naming Conventions

**Rules**:
- Names must reveal intent — avoid abbreviations unless universally known (URL, ID, API)
- Boolean variables use predicate prefixes: `is_valid`, `has_permission`, `can_admin`
- Constants use UPPER_SNAKE_CASE: `MAX_RETRIES`, `DEFAULT_TIMEOUT`
- Classes use PascalCase: `UserRepository`, `DataPipeline`
- Functions and variables use snake_case: `get_user`, `process_data`
- Private members use single underscore prefix: `_internal_method`

## Function Design Standards

**Single Responsibility**: Each function does ONE thing
- **Max length**: 50 lines (including blank lines and comments)
- **Max parameters**: 4 parameters (use dataclass for more)
- **Return early**: Avoid deep nesting

## Pre-Edit Safety Checks

**Before refactoring code**, verify:
1. **Tests exist?** Understand test coverage before changing behavior
2. **Function is called?** Check for dead code before investing in refactoring
3. **Import path correct?** Verify module structure before consolidating
4. **Breaking changes?** Identify all call sites before modifying signatures

## Python Regex Best Practices

### Regex Pattern String Escaping

When writing Python regex patterns with character classes containing quote characters (`['"`]`), match the outer string delimiter to avoid syntax errors:

- **Pattern has double quotes inside:** Use `r'...'` (single-quoted raw string)
  ```python
  # CORRECT: Character class has ", so use ' as outer delimiter
  re.compile(r'pattern["\`](.+?)["\`]')
  ```

- **Pattern has single quotes inside:** Use `r"..."` (double-quoted raw string)
  ```python
  # CORRECT: Character class has ', so use " as outer delimiter
  re.compile(r"pattern['`](.+?)['`]")
  ```

**Verification:** Always compile regex patterns immediately after creation with `re.compile()` to catch syntax errors early.
