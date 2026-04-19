---
name: code-review
description: Automate comprehensive code review workflows using parallel specialist agents. Dispatches security, logic, performance, and quality subagents to analyze code and synthesize actionable findings.
version: "1.0.0"
category: analysis
status: stable
triggers:
  - /review
  - "review code"
  - "review my code"
enforcement: advisory
parallel_agents: true
depends_on_skills: []
---

# Code Review — Automated Multi-Agent Review

A skill that automates code review by dispatching specialist agents in parallel and synthesizing their findings into actionable recommendations.

## Review Workflow

### Step 1: Capture Review Target

**Context-Aware Resolution (in priority order):**

1. **Args specifies target** — If args contains paths or file descriptions, use those.
2. **Recent session focus** — If args is empty, check what was recently edited or discussed.
3. **Ask if ambiguous** — Only ask if no clear target exists in context.

**Supported targets:**
- Single file: `P:/path/to/file.py`
- Multiple files: `P:/path/to/*.py`
- Directory: `P:/path/to/project/`
- Glob pattern: `**/*.js`

### Step 2: Initialize Review Session

Create a review session for file-efficient processing:

```bash
python -c "
from pathlib import Path
import sys
import uuid
import json

session_id = str(uuid.uuid4())[:8]
session_dir = Path('P:/.claude/.evidence/code-review/') / session_id
session_dir.mkdir(parents=True, exist_ok=True)

target = sys.argv[1] if len(sys.argv) > 1 else ''
work_file = session_dir / 'work.md'

if target:
    # Resolve target to actual files
    from pathlib import Path as P
    target_path = P(target)
    files = []
    if target_path.is_file():
        files = [target_path]
    elif target_path.is_dir():
        files = list(target_path.rglob('*.py')) + list(target_path.rglob('*.js'))
    elif '*' in target:
        import glob
        files = [P(f) for f in glob.glob(target, recursive=True)]

    content = f'# Review Target\n\nTarget: {target}\n\n'
    if files:
        content += f'Files ({len(files)}):\n'
        for f in files[:50]:  # Limit to 50 files
            content += f'- {f}\n'
        if len(files) > 50:
            content += f'- ... and {len(files) - 50} more\n'
    work_file.write_text(content)
else:
    work_file.write_text('# Review Target\n\nNo target specified.\n')

print(session_dir)
" "{TARGET}"
```

This creates: `{session_dir}/work.md`

### Step 3: Launch Parallel Specialist Agents

Dispatch specialist agents in parallel based on file types:

**For Python files:**
- `adversarial-security` — data access, auth, I/O, injection vectors
- `adversarial-logic` — off-by-one, wrong operators, conditionals
- `adversarial-performance` — hot paths, loops, N+1 queries
- `adversarial-io-validation` — path validation, file operations

**For JavaScript/TypeScript files:**
- `adversarial-security` — XSS, injection, auth issues
- `adversarial-logic` — async issues, error handling
- `adversarial-quality` — tech debt, maintainability

**Dispatch Pattern:**

```bash
# Create specialists directory
mkdir -p "P:/{session_dir}/specialists"

# Dispatch each specialist in parallel via Task tool
Task(
  subagent_type="general-purpose",
  description="Review the code at: P:/{session_dir}/work.md for [specialist-domain]. Write findings to: P:/{session_dir}/specialists/[specialist-name].md
  CRITICAL: After writing your findings to the file, your response must contain ONLY the file path. Do NOT include the full findings in your response."
)
```

Wait for all specialist agents to complete.

### Step 4: Synthesize Findings

After specialists complete, read all findings and create synthesized review:

```bash
cat "P:/{session_dir}/specialists/"*.md 2>/dev/null | head -500
```

**Output format** (write to `P:/{session_dir}/review.md`):

```markdown
# Code Review Report

**Target:** {target}
**Date:** {date}

## Summary

[2-3 sentences overview of findings]

## Health Score: XX%

Calculated as: `100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`, capped at 0-100.

| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |

## Findings

### Critical Issues

1. [CRITICAL] issue description (file:line)

### High Priority

1. [HIGH] issue description (file:line)

### Medium Priority

1. [MEDIUM] issue description (file:line)

### Low Priority

1. [LOW] issue description (file:line)

## Recommendations

1. [Priority order, actionable items]

## Files Reviewed

- file1.py
- file2.py
```

### Step 5: Deliver Final Output

Read `P:/{session_dir}/review.md` and present as final output.

### Step 6: Cleanup

Session directories persist at `P:/.claude/.evidence/code-review/` until manually removed.

## Output Structure

The final review uses severity-tagged findings with file:line citations where applicable.

**Health Score Interpretation:**
- 80-100: Healthy — Low risk, minor improvements possible
- 50-79: Warning — Significant issues, address HIGH items first
- Below 50: Critical — Systemic problems, do not deploy without fixes

## Specialist Agent Reference

| Agent | Focus | Applies To |
|-------|-------|------------|
| `adversarial-security` | Auth, injection, data exposure | All code |
| `adversarial-logic` | Conditionals, operators, flow | All code |
| `adversarial-performance` | Loops, DB, N+1, hot paths | Python, DB-heavy |
| `adversarial-io-validation` | Path traversal, file ops, external calls | All code |
| `adversarial-quality` | Tech debt, maintainability | All code |
| `adversarial-testing` | Test coverage, edge cases | All code |

## Session Persistence

Review sessions are stored at: `P:/.claude/.evidence/code-review/{session_id}/`

Contents:
- `work.md` — Target specification
- `specialists/` — Individual agent findings
- `review.md` — Synthesized final report
