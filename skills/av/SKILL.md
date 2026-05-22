---
name: av
description: Analyze and improve skills - generates complete hook files automatically
---
# Skill Improvement Tool

## EXECUTION DIRECTIVE

**When invoked, IMMEDIATELY:**

1. READ `P:\\\\\\.claude/skills/<skill>/SKILL.md`
2. READ `P:\\\\\\.claude/docs/claude-hooks-v2.1.15.md` (lines 808-835 for skill hooks)
3. CLASSIFY skill type (see Skill Type Classification below)
4. RUN validation checklist (6 sections) -- see `references/validation-checklist.md`
5. ANALYZE complexity for recommendation:
   - Multi-phase workflow? (+3 hooks)
   - State transitions? (+3 hooks)
   - Critical enforcement needed? (+2 hooks)
   - Single command? (-2 simple)
   - Reference/documentation only? (-2 simple)
   - Score >=1 -> Hooks recommended, <=0 -> Simple recommended
6. DETECT hook needs from skill pattern
7. GENERATE packages based on skill type -- see `references/hook-templates.md`
8. SHOW packages with RECOMMENDATION based on analysis -- see `references/output-package-and-architecture.md`
9. WAIT for user choice
10. WRITE selected package(s)
    - If EXECUTION: Also update SKILL_EXECUTION_REGISTRY
11. SANITY CHECK (AUTOMATIC):
    a) Read modified SKILL.md file
    b) Check for common issues (inconsistencies, missing elements, broken links)
    c) Fix any issues found
    d) Report all fixes applied

**CRITICAL:** When generating improved SKILL.md, ADD hooks configuration to frontmatter:
```yaml
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/{skill}/hooks/PreToolUse_{skill}_gate.py\""
          timeout: 10
  PostToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/{skill}/hooks/PostToolUse_{skill}_validator.py\""
          timeout: 10
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/{skill}/hooks/PostToolUse_{skill}_transition.py\""
          timeout: 10
```

**DO NOT:**
- Only suggest patterns without generating files
- Reference external skills for templates
- Modify files without confirmation

---

## Skill Type Classification

| Type | Characteristics | Required Elements |
|------|-----------------|-------------------|
| **EXECUTION** | Runs external tool/CLI, delegates to subagent | Execution directive, anti-substitution block, registry entry |
| **KNOWLEDGE** | Provides reference info, definitions, patterns | Context sections, no execution required |
| **PROCEDURE** | Multi-step workflow with decision points | Steps with success criteria, phase gates |

---

## Documentation References

**Before generating hooks, READ:**
- `P:\\\\\\.claude/docs/claude-hooks-v2.1.15.md` -- Lines 808-835 (skill hooks), 142-163 (lifecycle), 168-200 (schemas)
- CKS queries: `/search "skill hooks frontmatter matcher"`, `/search "PreToolUse gate skill"`, `/search "PostToolUse validator transition"`

---

## Validation Checklist (Quick Reference)

Full checklist in `references/validation-checklist.md` (Sections 0-F).

| Section | Focus | Key Checks |
|---------|-------|------------|
| 0 | Skill Type | EXECUTION / KNOWLEDGE / PROCEDURE classification |
| A | Execution Directive | First 30 lines, full paths, anti-substitution block |
| B | Structure | Prose:Code <= 2:1, quick reference table, error handling |
| C | Evidence | No excuse patterns, no temporal hedging |
| D | Hook Detection | File ops -> validator, multi-phase -> transitions |
| E | Execution Registry | EXECUTION skills must register in `StopHook_skill_execution_gate.py` |
| F | Layer 1 Governance | PROCEDURE skills need governance markers in frontmatter |

---

## Hook Templates

7 templates for generating skill packages. Full code in `references/hook-templates.md`.

| Template | Purpose | When to Use |
|----------|---------|-------------|
| 1: PostToolUse Validator | Validate tool output for errors | File/Bash operations |
| 2: State Manager | Workflow state with expiration | Multi-phase workflows |
| 3: PreToolUse Gate | Block tools not allowed in current phase | Phase enforcement |
| 4: PostToolUse Transition | Advance workflow phase after steps | State transitions |
| 5: Execution Skill SKILL.md | Template for EXECUTION type skills | External tool invocation |
| 6: Knowledge Skill SKILL.md | Template for KNOWLEDGE type skills | Reference/documentation |
| 7: Procedure Skill SKILL.md | Template for PROCEDURE type skills | Multi-step workflows |

---

## Complexity Score Guide

```
Score <= 0  -> SIMPLE mode, no hooks needed
Score 1-3   -> Optional hooks, user preference
Score >= 4  -> HOOKS recommended for reliability
```

**Needs hooks:** /tdd, /rca, /deploy, /v (multi-phase, state, enforcement)
**No hooks needed:** /standards, /explain, /brainstorm, /summarize (knowledge, simple)

---

## Output Packages & Architecture

See `references/output-package-and-architecture.md` for:
- Complexity analysis output format (3 options: Simple, Hooks, Both)
- Why two skills (feature flag limitation with PostToolUse)
- When NOT to add hooks

---

## Integration Checklist

See `references/integration-checklist.md` for:
- Complete example validator code
- Auto-generated integration checklist template
- Hook location convention (frontmatter vs legacy)
- Testing and rollback steps

---

## Critical

**Hook generation is SELF-CONTAINED in /av:**
- Templates in `references/hook-templates.md` -- complete working code
- No external references needed
- Ready to deploy immediately

## Core Principle

**One command -> Complete package -> Zero manual work.**

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious
