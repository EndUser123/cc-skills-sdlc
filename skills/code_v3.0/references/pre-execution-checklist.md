# Pre-Execution Checklist

**Before starting any development work**, answer these 5 questions to ensure clarity and preparedness. This prevents wasted effort on misunderstood requirements or incomplete context.

## The 5 Questions

1. **What is being asked for?**
   - Can you restate the requirement in your own words?
   - What does "success" look like for this feature?

2. **What context do you have?**
   - Have you searched for existing implementations? (`/search`)
   - Do you understand the constraints (CLAUDE.md, architecture patterns)?
   - What is the current state of the codebase?

3. **What is the implementation approach?**
   - Which files need to change?
   - What is the expected difficulty (trivial/moderate/complex)?
   - Are there any dependencies or blockers?

4. **What are the acceptance criteria?**
   - How will you know when the feature is complete?
   - What tests need to pass?
   - What are the edge cases to consider?

5. **What verification is needed?**
   - How will you test this (unit, integration, manual)?
   - What could go wrong (failure modes)?
   - What is the rollback strategy if needed?

## Usage

**Default behavior:** Checklist appears before `analyze_query_intent` step.

**Opt-out:** Use `--no-checklist` flag to bypass (e.g., for trivial changes or continued work):

```bash
/code "fix typo" --no-checklist
/code "continue task from yesterday" --no-checklist
```

**Evidence logging:** Checklist answers are logged to `.evidence/pre_execution.md` with timestamps for audit trail.
