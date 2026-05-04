# Skill Writing Standards

## Purpose
Adapt Test-Driven Development (TDD) to process documentation and proven techniques.

## What is a Skill?
A reusable technique, pattern, or tool reference.
- **Skills are NOT**: Narratives about solving a specific problem.

## The Iron Law
```
NO SKILL WITHOUT A FAILING TEST FIRST
```
Applies to NEW skills and EDITS. If you didn't watch an agent fail without the skill, you don't know if the skill teaches the right thing.

## TDD Mapping for Skills
- **Test case**: Pressure scenario with subagent.
- **Production code**: Skill document (SKILL.md).
- **Test fails (RED)**: Agent violates rule without skill.
- **Test passes (GREEN)**: Agent complies with skill present.
- **Refactor**: Close loopholes while maintaining compliance.

## Frontmatter Schema
- `name`: hyphenated-name-only.
- `description`: Third-person, starts with "Use when...", focus on triggering symptoms.
- **CRITICAL**: Never summarize the process/workflow in the description.

## Bulletproofing Against Rationalization
- **Spirit vs Letter**: State "Violating the letter is violating the spirit."
- **Explicit Counters**: List common excuses (e.g., "too simple to test") and their reality.
- **Delete means delete**: For discipline-enforcing rules, forbid keeping bad code as "reference."
