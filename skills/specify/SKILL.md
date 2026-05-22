---
name: specify
description: Generate detailed specification from PRD requirements
---
# Specify — Detailed Specification

Generate detailed `specify.md` from PRD requirements.

## Purpose

`/specify` takes the FR/NF requirements from a PRD and flushes them into a detailed specification with functional requirements, user stories, acceptance criteria, and technical constraints.

## Project Context

### Constitution/Constraints
- **User in charge**: Confirm scope and priority with user before writing
- **Specificity**: Every requirement needs acceptance criteria
- **Completeness**: Cover all categories — functionality, data, security, performance, error handling

### Technical Context
- Specification lives next to PRD: `{project}/specify.md`
- Reads from: PRD file (`prd.md`) in same directory
- Format: FR-XXX for functional requirements, NFR-XXX for non-functional

### Architecture Alignment
- Input: `/prd` output (prd.md with FR/NF requirements)
- Output: `/design` or `/planning` for next steps
- Works with `/prd` → `/specify` → `/design` workflow

## Phase Structure

### PHASE 1: Requirements Reading
Read PRD, extract FR/NF requirements.

### PHASE 2: Specification Expansion
Expand each requirement into acceptance criteria, technical constraints, and user stories.

### PHASE 3: Presentation
Present the specification to user for review and confirmation.

---
### STOP GATE

**Between PHASE 2 and PHASE 3**: You MUST present the specification and wait for user confirmation before proceeding to /design or /planning.

**Do NOT:**
- Proceed to /design or /planning without user approval
- Mix generation and review in the same response
- Skip user review step

## Validation Rules

### Prohibited Actions
- Skipping acceptance criteria (must be specific and testable)
- Creating user stories without clear Given/When/Then
- Skipping error handling paths

### Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious

### Required Coverage
- All FRs from PRD must appear with acceptance criteria
- All NFRs from PRD must appear with measurable criteria
- At least one user story per major feature
- Error paths documented for all user interactions

## After User Approval

After the user approves the specification:
- Proceed to `/design` for architecture decisions
- Or proceed to `/planning` for implementation plan
- User can edit specify.md directly if changes are needed
- `/prd` is the input source if requirements change
