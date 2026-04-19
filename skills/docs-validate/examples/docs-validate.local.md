---
mode: suggestive
severity_threshold: medium
auto_validate: true
---

# Documentation Validation Configuration

This configuration controls automatic documentation validation behavior.

## Mode Options

**suggestive** (default):
- Validation runs automatically on Write/Edit operations
- Warnings shown when issues found
- Write operations complete normally

**blocking**:
- Validation runs automatically on Write/Edit operations
- Write operations blocked when validation fails
- Returns `permissionDecision=deny` with reason

**off**:
- Automatic validation disabled
- Only manual `/docs-validate` commands available

## Severity Threshold

**low**: Report all issues
**medium**: Report MEDIUM and HIGH severity issues (default)
**high**: Report only HIGH severity issues

## Auto-Validate

**true**: Enable automatic validation on Write/Edit (default)
**false**: Disable automatic, use `/docs-validate` manually

## Examples

### Strict Validation (Development Mode)
```markdown
---
mode: blocking
severity_threshold: low
auto_validate: true
---
```

### Production-Ready Skill
```markdown
---
mode: suggestive
severity_threshold: high
auto_validate: true
---
```

### Opt-Out of Automatic Validation
```markdown
---
mode: off
auto_validate: false
---
```
