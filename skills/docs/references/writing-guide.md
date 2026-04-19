# Documentation Writing Guide

## Documentation Philosophy

> **"Nobody reads 50-page docs. Make it scannable, actionable, and impossible to misunderstand."**

### Four Pillars
- **Scannable** - Headers, bullets, tables. No walls of text.
- **Actionable** - Every step is something you DO, not something you "consider"
- **Specific** - Numbers, names, thresholds. No "as needed" or "when appropriate"
- **Testable** - Clear success criteria. How do you know it worked?

### Be Specific: Writing Rules
| Don't Write | Write Instead |
|-------------|---------------|
| "Contact the team" | "Message @sarah in #ops-team" |
| "Wait until ready" | "Wait until status shows 'Complete' (~5 min)" |
| "Review carefully" | "Check items A, B, C in the dashboard" |
| "As appropriate" | "If value > 100" |
| "Regularly" | "Every Monday at 9am" |
| "Soon" | "Within 2 hours" |

### Definition of Done (Required Section)
Every documentation update must include near the top:
```markdown
## Definition of Done
This is complete when:
- [ ] [Primary outcome]
- [ ] [Verification step]
- [ ] [Any handoff/notification]
```

### DO These Instead
- Start with the most common path
- Put edge cases at the bottom
- Link to related docs instead of duplicating
- Use tables for reference info
- Use checklists for verification steps
- Include "I'm stuck" escape hatches

### DON'T Do These
- "Per company policy..." (just state what to do)
- "It is recommended that..." (just say "do X")
- "Please ensure..." (just say "check X")
- Passive voice ("the form should be submitted") -> Active ("submit the form")
- Describe what to do instead of showing it
- Walls of text with no structure

## Format Selection Guide

When creating documentation, ask yourself:
1. **Is this for emergencies?** -> Runbook
2. **Is this a complex multi-phase project?** -> Playbook
3. **Is this a simple repeated task?** -> Standard SOP or Checklist
4. **Does it have lots of if/then branching?** -> Decision Tree
5. **Is it for debugging?** -> Troubleshooting Guide
6. **Is it recording a decision?** -> ADR (Architecture Decision Record)
7. **Is it for someone new?** -> Onboarding Guide
8. **Is it general documentation?** -> README or CLAUDE.md

## Anti-Patterns

| Don't                                | Do Instead                                          |
| ------------------------------------ | --------------------------------------------------- |
| Modifying code without updating docs | Update `README.md` / `CLAUDE.md` in same PR/Session |
| Asking "Should I update docs?"       | **Just update them** if the change is significant   |
| Leaving "TODO: update docs"          | Update them now, or file a specific task            |
| Skipping CLAUDE.md for modules       | Run `/init <target>` to create it                   |
| Vague instructions ("contact team")  | Specific ("message @name in #channel")           |
| Passive voice ("should be submitted")   | Active voice ("submit the form")             |
| Walls of text                       | Tables, bullets, headers, numbered steps      |

## Code Documentation Best Practices

### Regex Pattern String Escaping

When documenting Python regex patterns with character classes containing quote characters (`['"`]`), note the delimiter matching requirement:

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

**Documentation note:** Always include the delimiter matching rule when documenting regex patterns with quote characters in character classes.
