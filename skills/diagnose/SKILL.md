---
name: diagnose
description: Structured diagnostic protocol enforcing systematic hypothesis testing when investigating issues.
version: "1.0.0"
status: "stable"
category: analysis
---

# Structured Diagnostic Protocol

## Overview
Structured investigation enforcing systematic hypothesis testing.

**Mandatory Protocol:** See `__lib/diagnostic_protocol.md` for the H1-H3 template and enforcement rules.

## AID Integration (v1.1.0)

**Bug hunting assistance via AI Distiller (AID):**

```bash
# Systematically search for bugs
aid <path> --ai-action prompt-for-bug-hunting
```

**When to use AID for diagnosis:**
- Pre-mortem analysis (investigate before incident)
- Legacy code bug discovery
- Test gap analysis

**Integration**: Run AID bug hunting before hypothesis generation to inform H1-H3 list.

## When to Use
- Investigating bugs, errors, or unexpected behavior.
- Analyzing system failures or race conditions.

**When NOT to use**:
- Simple fixes (obvious typo).
- Feature implementation (use /code).

## Quick Reference

| Violation | Detection | Correction |
|-----------|-----------|------------|
| Single hypothesis | Only H1 listed | Add H2, H3 upfront |
| Untested claim | "Probably caused by X" | Show test output |
| Missing conclusion | Tests but no winner | State confirmed hypothesis |
| Premature fix | "Let's try X" before tests | Complete protocol first |

---
**Version**: 1.0.0
**Enforcement**: Stop hook checks for violations
