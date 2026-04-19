---
name: step_6_5
description: Generate ORCHESTRATION.md from plan.md and tasks.json
version: "1.0.0"
status: stable
category: orchestration
triggers:
  - /step-6-5
aliases:
  - /step-6-5

suggest:
  - /build
  - /docs
  - /workflow
---

# Step 6.5 - Generate ORCHESTRATION.md

Transform plan.md into ORCHESTRATION.md for parallel agent execution.

## Purpose

Generate ORCHESTRATION.md from plan.md and tasks.json for parallel agent execution.

## Project Context

### Constitution/Constraints
- CWO workflow orchestration standards
- Phase-based task assignment for parallel execution
- TSK-based project tracking required

### Technical Context
- Transforms plan.md into ORCHESTRATION.md
- Assigns tasks to phases A-E based on task type
- Integrates with TaskMaster for TSK tracking
- Phase assignments: test=A, research/analyze/review=B, doc=E, everything else=C

### Architecture Alignment
- Part of CWO workflow (Step 6.5)
- Works with cwo-orchestrator for monitoring
- Integrates with plan (Step 5) and quadlet (Step 6)

## Your Workflow

1. **Find active TSK** - Identify current project context
2. **Read plan.md and tasks.json** - Get task definitions
3. **Generate ORCHESTRATION.md** - Create phase assignments with dependencies
4. **Display result** - Show generated orchestration

## Validation Rules

- All tasks must be assigned to a phase
- Phase assignments must follow keyword rules
- Dependencies must be respected
- Epic and TSK info must be included

---

## Usage

```bash
# Generate for active TSK
/step-6-5

# Generate for specific TSK
/step-6-5 TSK-ARCH-TIER1-20260103-075037
```

## What Happens

1. Finding active TSK
2. Reading plan.md and tasks.json
3. Generating ORCHESTRATION.md with phase assignments
4. Displaying result

## ORCHESTRATION.md Structure

- Overview with Epic and TSK info
- Task Legend (status, owners, heartbeat)
- Phases A-E for parallel execution
- Task assignments with dependencies

## Phase Assignments

| Keywords | Phase | Owner |
|----------|-------|-------|
| "test" | A | test-writer |
| "research", "analyze", "review" | B | research-analyst |
| "doc" | E | docs-writer |
| Everything else | C | implementer |

## Next Steps

1. Review ORCHESTRATION.md
2. Run /cwo-orchestrator to begin monitoring
3. Launch agents
4. Monitor progress

## Integration

CWO Workflow: Steps 0-6 - Complete, Step 6.5 - You are here, Phases A-E - Parallel execution

## See Also

- /cwo-orchestrator - Terminal A monitor
- /planning - Generate plan.md (Step 5)
- /quadlet - Atomic task decomposition (Step 6)
