# Phase 1: Specialist Dispatch

## Your Job

Dispatch specialist agents in parallel to analyze the code target, then consolidate findings.

## Step 1: Identify Target Files

Read the work file to understand what files need review:

```bash
cat "P:\\\\\\{session_dir}/work.md"
```

## Step 2: Select Appropriate Specialists

Based on file types detected:

**Python files:**
- `adversarial-security` — data access, auth, I/O, injection vectors
- `adversarial-logic` — off-by-one, wrong operators, conditionals
- `adversarial-performance` — hot paths, loops, N+1 queries
- `adversarial-io-validation` — path validation, file operations

**JavaScript/TypeScript files:**
- `adversarial-security` — XSS, injection, auth issues
- `adversarial-logic` — async issues, error handling

**All file types:**
- `adversarial-quality` — tech debt, maintainability
- `adversarial-testing` — test coverage, edge cases

## Step 3: Dispatch Specialist Agents

For each selected specialist, dispatch a Task in parallel:

```bash
Task(
  subagent_type="general-purpose",
  description="Review the code at: P:\\\\\\{session_dir}/work.md for [specialist-domain]. Write findings to: P:\\\\\\{session_dir}/specialists/[specialist-name}.md"
)
```

**Wait for all specialist agents to complete before continuing.**

## Step 4: Consolidate Findings

After all specialists complete, read their outputs and create consolidated findings:

```bash
cat "P:\\\\\\{session_dir}/specialists/"*.md
```

**Output format** (write to `P:\\\\\\{session_dir}/p1_findings.md`):

```markdown
## Triage Classification
[type] — [brief justification]

## Dispatched Specialists
- [specialist name]: [what they analyzed]

## Specialist Findings Summary

### [Specialist 1 Name]
**Domain:** [what they cover]
**Key findings:**
- [HIGH] finding description
- [MEDIUM] finding description
- [LOW] finding description

## Consolidated Findings

### Critical Issues
1. [CRITICAL] issue (source: specialist-name)

### High Priority
1. [HIGH] issue (source: specialist-name)

### Medium Priority
1. [MEDIUM] issue (source: specialist-name)

### Low Priority
1. [LOW] issue (source: specialist-name)

### No Significant Issues
- [specialist]: No significant issues found
```
