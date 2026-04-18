---
name: prd
description: Generate PRD (Product Requirements Document) from conversation
version: 1.0.0
status: stable
enforcement: advisory
category: requirements
triggers:
  - /prd

suggest:
  - /specify

workflow_steps:
  - elicit
  - write
  - review

execution:
  directive: |
    Generate a PRD document from conversation.
    1. elicit: Gather requirements via conversational questioning.
    2. write: Write prd.md with FR (functional) and NF (non-functional) requirements.
    3. review: Present PRD to user for confirmation.
  default_args: "elicit"

do_not:
  - skip requirement categories (functionality, UX, data, security, performance, error handling)
  - use vague requirement language (always specify acceptance criteria)

output_template: |
  ## PRD: [project name]
  Generated: [date]

  ## Functional Requirements
  - FR-1: [requirement with acceptance criteria]
  - FR-N: [...]

  ## Non-Functional Requirements
  - NF-1: [requirement with acceptance criteria]
  - NF-N: [...]
---

# PRD — Product Requirements Document

Generate a structured PRD from conversation.

## Purpose

`/prd` elicits requirements through conversation and produces a `prd.md` file. Requirements come from discussion, not from importing existing documents.

## Project Context

### Constitution/Constraints
- **User in charge**: Never assume — confirm requirements with the user
- **Specificity**: Every requirement needs acceptance criteria, not just a label
- **Completeness**: Cover all categories — functionality, UX, data, security, performance, error handling

### Technical Context
- PRD files at project root: `{project}/prd.md`
- Format: FR-XXX for functional requirements, NF-XXX for non-functional
- Each requirement includes: description + acceptance criteria

### Architecture Alignment
- Feeds `/specify` for detailed specification
- Feeds `/design` when architectural decisions are needed

## Your Workflow

### 1. elicit — Gather requirements
Start a focused conversation to extract:
- **What** the system does (functional boundary)
- **Who** uses it and in what roles
- **What** constitutes done (acceptance criteria)
- **Constraints** (performance, security, compatibility)
- **Error handling** expectations

Ask one question at a time. Don't rush to write before you understand.

### 2. write — Draft prd.md
Structure the conversation into:
```
## Functional Requirements
- FR-1: [description] — Acceptance: [criteria]
- FR-2: [description] — Acceptance: [criteria]

## Non-Functional Requirements
- NF-1: Performance — [criterion]
- NF-2: Security — [criterion]
```

Each requirement must be specific enough that "did we meet this?" can be answered without debate.

### 3. review — Confirm with user
Present the draft. Confirm, refine, or add requirements. Iterate until user says the PRD is complete.

## Validation Rules

### Prohibited Actions
- Do NOT produce vague requirements ("system should be fast" — how fast?)
- Do NOT skip NF category (security, performance, reliability matter)
- Do NOT write requirements you haven't confirmed with the user

### Required Coverage
- Functional: What does it do? Who uses it? What are the inputs/outputs?
- Non-functional: Performance, security, compatibility, scalability
- Error handling: What happens when things go wrong?
- Edge cases: What unusual inputs or states must be handled?

## Quick Start

```bash
/prd
# Starts requirement elicitation conversation
```

## Output Location

PRD lives next to your project:
```
{project}/
├── prd.md          ← Product Requirements (this command)
├── specify.md      ← Detailed spec (from /specify)
└── README.md
```

## Tell the User

After writing the PRD, tell them:
- What `/prd` suggests next (`/specify` for flushing into detailed spec)
- That they can edit prd.md directly if they prefer
- That `/design` is available if architectural decisions are needed