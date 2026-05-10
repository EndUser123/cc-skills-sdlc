# Workflow State Validation (MANDATORY BEFORE COMPLETION)

**Before declaring RCA complete, you MUST check the authoritative workflow state:**

```bash
# Read workflow state
cat ~/.claude/state/rca/rca_workflow.json
```

**Required validation:**

1. **Check `delegation_satisfied`:**
   - If `false`: You MUST complete specialist delegation before declaring completion
   - Use `Agent(general-purpose, ...)` or appropriate specialist
   - Update workflow state to `delegation_satisfied: true`

2. **Check `complete`:**
   - Only set `complete: true` when ALL requirements satisfied:
     - Root cause identified and documented
     - Fix recommended (or fix verified as applied)
     - Delegation completed
     - Findings recorded (if required)

3. **Document status must match workflow state:**
   - FORBIDDEN: Document says "RCA Complete" when `delegation_satisfied: false`
   - FORBIDDEN: Document says "FIX APPLIED" when workflow incomplete
   - REQUIRED: Check workflow state FIRST, then write document status accordingly
   - ACCEPTABLE: "IN PROGRESS - Delegation pending" when `delegation_satisfied: false`

**Why this matters:**

After session compaction/restoration, the conversation context includes your RCA document but NOT the workflow state file. If you claim "RCA Complete" in the document but the workflow state shows `delegation_satisfied: false`, the StopHook will correctly block completion with:

> RCA WORKFLOW INCOMPLETE
> You invoked /rca but did not complete: specialist delegation

This prevents premature completion claims that don't survive session restoration.

**Before declaring RCA complete:**

```bash
# 1. Read current state
state=$(cat ~/.claude/state/rca/rca_workflow.json)

# 2. Check delegation_satisfied
echo "$state" | jq '.delegation_satisfied'
# Expected: true

# 3. Check complete
echo "$state" | jq '.complete'
# Expected: true (you will set this)

# 4. Update state to complete
echo "$state" | jq '.complete = true' > ~/.claude/state/rca/rca_workflow.json
```

**Do not** infer hook registration from `~/.claude/hooks` when investigating `/rca`. Hook registration authority lives in `P:\\\\\\.claude/settings.json`; this workflow file is only about RCA session state.
