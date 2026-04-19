# Configuration Reference

## Configuration File

**Location**: `{skill-root}/.claude/docs-validate.local.md`

**Structure** (YAML frontmatter + markdown body):
```markdown
---
mode: suggestive
severity_threshold: medium
auto_validate: true
---

# Configuration Notes

This skill uses suggestive mode. Validation warnings appear
but don't block write operations.
```

## Configuration Options

**mode** (default: `suggestive`):
- `suggestive` - Show warnings, allow write operations to complete
- `blocking` - Block write operations when validation fails (returns `permissionDecision=deny`)
- `off` - Disable automatic validation entirely

**severity_threshold** (default: `medium`):
- `low` - Report all issues
- `medium` - Report MEDIUM and HIGH severity issues
- `high` - Report only HIGH severity issues

**auto_validate** (default: `true`):
- `true` - Enable intelligent mode selection and DRY-RUN reports
- `false` - Use configured `mode` directly without recommendations

## Intelligent Mode Selection

When `auto_validate: true` (default), the system analyzes validation issues and recommends an appropriate mode:

**Recommendation Logic:**
- **3+ HIGH issues** -> Recommend `blocking` (serious quality problem)
- **1-2 HIGH issues** -> Recommend `suggestive` (warn but don't block)
- **5+ MEDIUM issues** -> Recommend `suggestive` (quality concern)
- **Fewer issues** -> Recommend `off` (skip validation, not worth interruption)

## DRY-RUN Reports

When issues are detected and `auto_validate: true`, the system shows a **DRY-RUN report** instead of immediately applying validation:

```
DRY-RUN: Documentation validation found issues
Issues: 2 HIGH, 3 MEDIUM
Recommended mode: SUGGESTIVE
Skill: my-skill

HIGH severity issues:
  - Circular reference detected
    File: concepts.md
    Fix: Remove circular link

MEDIUM severity issues:
  - Missing file reference
  - Outdated version tag
```

This dry-run behavior **occurs even when `mode: off`** because the system is designed to inform you about issues before applying validation. The recommendation prompts you to create a configuration file with explicit mode settings.

## How DRY-RUN Works

1. **Write/Edit Operation**: You modify a markdown file in a skills directory
2. **Validation Runs**: DocumentationValidator automatically checks the file
3. **Issues Detected**: If issues are found, intelligent mode selection recommends a mode
4. **DRY-RUN Display**: System shows recommendation instead of applying validation
5. **User Action**: Create `.claude/docs-validate.local.md` with recommended `mode`
6. **Re-run Write/Edit**: Operation completes with configured validation behavior

**Why mode=off shows DRY-RUN:**

Even when you have `mode: off` configured, the system will show a DRY-RUN report if issues are detected. This is intentional - it ensures you're informed about documentation quality issues before they accumulate, while still giving you control over whether to enable validation.

**Example DRY-RUN workflow:**

```bash
# First write: mode=off, issues detected
echo "# My Documentation" > my-skill/SKILL.md
# Output: DRY-RUN report with recommendations

# Create config to accept suggestion
cat > my-skill/.claude/docs-validate.local.md <<EOF
---
mode: suggestive
---
EOF

# Second write: validation applies with configured mode
echo "# Updated Documentation" > my-skill/SKILL.md
# Output: Validation warnings (suggestive mode, non-blocking)
```

## Configuration Examples

**Example 1: Accept recommendations (suggestive mode)**
```markdown
---
mode: suggestive
---
```

**Example 2: Strict validation during development**
```markdown
---
mode: blocking
severity_threshold: low
auto_validate: false
---

Blocking mode enabled for development. All issues reported,
write operations blocked until validation passes.
```

**Example 3: Production-ready skill**
```markdown
---
mode: suggestive
severity_threshold: high
auto_validate: true
---

Suggestive mode with HIGH severity threshold. Only critical
issues shown, warnings don't block workflow.
```

**Example 4: Opt-out of automatic validation**
```markdown
---
mode: off
auto_validate: false
---

Automatic validation disabled. Use `/docs-validate` manually
for pre-publish validation sweeps.
```
