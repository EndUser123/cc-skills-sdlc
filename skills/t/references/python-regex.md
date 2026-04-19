# Python Regex Best Practices

## Regex Pattern String Escaping

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
