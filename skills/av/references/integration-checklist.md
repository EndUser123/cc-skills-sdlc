# Integration Checklist & Complete Example

## Complete Example Output

```python
#!/usr/bin/env python3
"""
"""
import json, sys
from pathlib import Path

def validate_output(data: dict) -> dict:
    tool_name = data.get("tool_name", "")
    tool_output = data.get("tool_output", "")

    if tool_name == "Bash":
        if any(err in tool_output.lower() for err in ["error", "failed", "not found"]):
            return {
                "hookSpecificOutput": {
                }
            }

    return {}

def main():
    input_data = json.loads(sys.stdin.read())
    result = validate_output(input_data)
    print(json.dumps(result))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

**COMPLETE, WORKING, READY TO USE.** No manual copying needed.

---

## Integration Checklist (Auto-Generated)

```markdown

## Files Created

## Frontmatter Hooks Registration
- PreToolUse gate blocks Write/Edit during restricted phases
- PostToolUse validator checks Bash command output for errors
- PostToolUse transition advances workflow phases automatically

Hooks use \$CLAUDE_PROJECT_DIR for portable path references.

## Testing Steps
2. Check: Frontmatter hooks load automatically
3. Verify: PreToolUse gate restricts tools by phase
4. Confirm: Validator catches errors
5. Test: Transition advances phases correctly
6. Logs: P:\\\\\\.claude/logs/hooks.jsonl

## Rollback (if needed)
```bash
# Restore original

# Remove generated hooks
```

## Customization Points
Edit these files to customize validation:
```

---

## Hook Location Convention

**Frontmatter Hooks (recommended for skill-scoped hooks):**
- Hooks defined in SKILL.md frontmatter under `hooks:` key
- Scoped to skill lifecycle - only run when skill is active
- Auto-cleanup when skill completes
- Hook files stored in `.claude/skills/{skill}/hooks/`
- Uses `$CLAUDE_PROJECT_DIR` for portable path references
- Documented in: https://code.claude.com/docs/en/hooks (Hooks in skills and agents)

**Legacy hooks** (still supported):
- Hooks in `.claude/hooks/` root
- Used for cross-cutting concerns (TDD, constitutional enforcement)
- Registered in `~/.claude/settings.json` or `.claude/settings.json`
