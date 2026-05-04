# RCA Output and Synthesis

## Synthesis Checkpoint
After 3-5 findings or convergence, STOP and synthesize:
1. List findings with sources.
2. Build causal chain: A -> B -> Root Cause.
3. State conclusion with confidence.
4. Propose fix (if confidence >= High).

## Output Format
All claims must include confidence tags: `(Tier [0-4], [0-100]%)`.

**RCA Structure Template:**
1. **Symptom**
2. **Evidence** (with time-scope labels)
3. **Executed Path**
4. **Alternative Hypotheses**
5. **Falsifier**
6. **Root Cause**
7. **Fix**
8. **Verification**

## Fix Level Classification
| Level | Signal |
|-------|--------|
| **Band-Aid** | "This will break again" - Catch exception, null check. |
| **Local Optimum** | "Cleaner but same shape" - Refactor for readability. |
| **Reframe** | "What if the problem is actually..." |
| **Redesign** | "Eliminate the failure class entirely." |

**Band-aid chain detection**: 3+ Band-Aids in one file = `XY-SUSPECT`.
