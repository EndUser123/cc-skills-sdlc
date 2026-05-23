# Usage Examples

## Example 1: Circular Reference Detection

```bash
/docs-validate P://packages/skill-guard

**Output**: Critical issue detected
- circular_reference: src/skill_guard/SKILL.md <-> references/conversion.md
- Both files under 50 lines with cross-references
- Fix: Expand one file with actual conversion workflow
```

## Example 2: Incomplete Content Detection

```bash
check docs in P://.claude/skills/my-skill

**Output**: Important issues detected
- incomplete_content: references/advanced.md (12 lines)
- Contains "See README.md for full details" without substantive content
- Fix: Add advanced techniques to references/advanced.md or inline into main doc
```

## Example 3: Version Conflict Detection

```bash
validate documentation P://packages/skill-guard

**Output**: Important issue detected
- version_conflict: README.md references "v5.1 structure"
- Current codebase is v5.2 (core/ directory, no pyproject.toml)
- Fix: Update README.md to reflect v5.2 plugin structure
```
