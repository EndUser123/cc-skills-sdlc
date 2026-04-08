# Code Quality Standards

**Purpose**: These standards apply to ALL code written during `/code` execution. They are enforced during the REFACTOR phase and validated in the AUDIT phase.

## Naming Conventions

**Rules**:
- Names must reveal intent - avoid abbreviations unless universally known (URL, ID, API)
- Boolean variables use predicate prefixes: `is_valid`, `has_permission`, `can_admin`
- Constants use UPPER_SNAKE_CASE: `MAX_RETRIES`, `DEFAULT_TIMEOUT`
- Classes use PascalCase: `UserRepository`, `DataPipeline`
- Functions and variables use snake_case: `get_user`, `process_data`
- Private members use single underscore prefix: `_internal_method`

**Examples**:
```python
# WRONG: Obscure names
d = new Date()
chk = val => val > 0

# CORRECT: Clear names
current_date = datetime.now()
is_positive = value > 0
```

## Function Design

**Single Responsibility**: Each function does ONE thing
- **Max length**: 50 lines (including blank lines and comments)
- **Max parameters**: 4 parameters (use dataclass for more)
- **Return early**: Avoid deep nesting

**Examples**:
```python
# WRONG: Does too many things
def process_user(user_id):
    user = db.get_user(user_id)
    if not user:
        return None
    validated = validate(user)
    transformed = transform(validated)
    saved = save_to_db(transformed)
    send_email(saved)
    return saved

# CORRECT: Single responsibility
def get_validated_user(user_id: int) -> User | None:
    """Fetch and validate user by ID."""
    user = db.get_user(user_id)
    if user:
        validate(user)
    return user
```

## Anti-Patterns to Avoid

**DRY Violations**:
- Copy-pasted code blocks -> Extract to function
- Repeated conditionals -> Create predicate function
- Magic numbers -> Use named constants

**Separation of Concerns**:
- Functions that mix I/O with business logic -> Split layers
- Classes with unrelated methods -> Split into smaller classes
- Modules that contain unrelated utilities -> Organize by domain

**Complexity Red Flags**:
- Deep nesting (>4 levels) -> Extract functions, use early returns
- God objects (classes that do everything) -> Split by responsibility
- Feature envy (code using more of another class than its own) -> Move to appropriate class

## Pre-Edit Safety Checks

**Before writing code**, verify:
1. **File exists?** Don't create new files without user confirmation
2. **Function exists?** Check before modifying - prefer extension over replacement
3. **Import exists?** Verify before adding new dependencies
4. **Tests exist?** Understand test structure before adding features

**Example**:
```python
# BEFORE adding user authentication:
# 1. Check if user auth module exists
# 2. Check if tests cover auth flows
# 3. Ask user: "Add to existing auth.py or create new module?"

# WRONG: Create without checking
def authenticate_user(username, password):
    # 50 lines of auth logic
    pass

# CORRECT: Check first, extend existing
if has_module('auth'):
    extend_auth_functionality(username, password)
else:
    confirm_with_user("Create new authentication module?")
```

## Regex Pattern String Escaping

When writing Python regex patterns with character classes containing quote characters (`['"`]`), match the outer string delimiter to avoid syntax errors:

- **Pattern has double quotes inside:** Use `r'...'` (single-quoted raw string)
  ```python
  # CORRECT: Character class has ", so use ' as outer delimiter
  re.compile(r'pattern["`](.+?)["`]')
  ```

- **Pattern has single quotes inside:** Use `r"..."` (double-quoted raw string)
  ```python
  # CORRECT: Character class has ', so use " as outer delimiter
  re.compile(r"pattern['`](.+?)['`]")
  ```

**Verification:** Always compile regex patterns immediately after creation with `re.compile()` to catch syntax errors early.

**Common anti-pattern to avoid:**
```python
# WRONG: Character class [\"`] inside r"..." causes premature string closing
re.compile(r"pattern[\"`](.+?)[\"`]")  # SyntaxError!
```
