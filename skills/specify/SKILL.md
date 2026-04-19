---
name: specify
description: Generate detailed specification from PRD requirements
version: 1.0.0
status: stable
enforcement: advisory
category: specification
triggers:
  - /specify

suggest:
  - /prd

workflow_steps:
  - read_prd
  - expand_requirements
  - write_specify_md
  - review_with_user
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

## Your Workflow

### 1. Read PRD
Check if `prd.md` exists in the current project. If not, ask the user for requirements input.

### 2. Expand Requirements
For each FR/NF from PRD:
- Add acceptance criteria (specific, testable conditions)
- Add technical constraints (API contracts, data schemas, error codes)
- Add user stories with Given/When/Then format

### 3. Write specify.md
```
## Functional Requirements
- FR-1: [requirement] — Acceptance: [criteria]

## Non-Functional Requirements
- NFR-1: [requirement] — Acceptance: [criteria]

## User Stories
### US-1: [title]
**Given** [context]
**When** [action]
**Then** [outcome]

## Technical Constraints
- [API contracts, data formats, error codes]
```

### 4. Review
Present specification to user. Confirm scope before proceeding to `/design` or `/planning`.

## Validation Rules

### Prohibited Actions
- Skipping acceptance criteria (must be specific and testable)
- Creating user stories without clear Given/When/Then
- Skipping error handling paths

### Required Coverage
- All FRs from PRD must appear with acceptance criteria
- All NFRs from PRD must appear with measurable criteria
- At least one user story per major feature
- Error paths documented for all user interactions

## Tell the User

After writing the specification, tell them:
- What `/specify` suggests next (`/design` for architecture, `/planning` for implementation)
- That they can edit specify.md directly
- That `/prd` is the input source if requirements change
