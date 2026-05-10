# VERIFY Phase (MANDATORY - Integration Validation)

**CRITICAL:** After GREEN phase, you MUST verify the implementation is actually integrated and working end-to-end.

## What "NO VERIFICATION" Looks Like

These are **PROHIBITED** patterns that indicate missing verification:

| Pattern | Why It's Wrong | Correct Approach |
|---------|----------------|------------------|
| "Function implemented" | Doesn't prove it's called | Show code path reaches implementation |
| "Tests pass" | May be unit tests only | Run integration/e2e tests |
| "Should work" | Assumption without evidence | Run actual command with real data |
| "Code added to file" | Doesn't prove integration | Verify call chain is complete |

## Verification Requirements

**MANDATORY:** All implementations must verify:

1. **Baseline Capture** (before starting)
   ```bash
   # Capture baseline test results
   pytest tests/ --tb=no -q > /tmp/baseline.txt
   ```

2. **Integration Check** (after implementation)
   ```bash
   # Verify function is actually called in the codebase
   grep -r "function_name" --include="*.py" | grep -v "test_"

   # Or for methods:
   grep -r "\.method_name" --include="*.py" | grep -v "test_"
   ```

3. **End-to-End Test** (real data, no mocks)
   ```bash
   # Run actual command, not dry-run
   python -m module.command real_input.json

   # Or run integration tests
   pytest tests/test_integration.py -v
   ```

4. **Compare Results** (before/after)
   ```bash
   # Show improvement or fix
   echo "Before: $(cat /tmp/baseline.txt | grep passed)"
   echo "After: $(pytest tests/ --tb=no -q | grep passed)"
   ```

## Plan/Chat History Reference

**MANDATORY:** All verification MUST reference a plan file or chat history as the source of truth for requirements.

**Without a plan/chat reference, verification is impossible** -- there's no way to know what the intended state should be. This is exactly the gap that causes "implemented but not integrated" problems.

**Required workflow:**

1. **Identify the source** - What plan or chat history contains the requirements?
   - Plan file: `P:\\\\\\plans/plan-YYYYMMDD-name.md` or similar
   - Chat history: Current session or previous session reference

2. **Extract requirements** - List all requirements from the source
   ```
   Source: plan-20260130-session-continuity.md
   Requirements extracted:
   - Requirement 1: [exact text from plan]
   - Requirement 2: [exact text from plan]
   - Requirement 3: [exact text from plan]
   ```

3. **Verify each requirement** - Check implementation against each requirement
   ```
   OK Requirement 1: Implemented at path/to/file.py:123
   X  Requirement 2: NOT FOUND - needs implementation
   OK Requirement 3: SATISFIED (grep shows 3 call sites)
   ```

4. **Report completion status** with explicit source reference
   ```
   VERIFICATION COMPLETE:
   Source: plan-20260130-session-continuity.md
   Requirements: 2/3 implemented (1 missing)
   Integration: VERIFIED (grep shows X call sites)
   Tests: PASSING (Y passed, Z failed)
   ```

**If no plan or chat history reference exists:**
- HALT verification - cannot proceed without source of truth
- Create plan file with requirements BEFORE implementing
- OR document requirements in chat history with clear acceptance criteria

## Plan Discovery

**How to find the plan/chat reference for verification:**

**Ambiguity rule (MANDATORY):**
- If user says "implement the plan" (or "execute the plan") without a path and multiple candidate plans exist, STOP and ask user to choose.
- Present 2-3 concrete file choices (most recent candidates) plus one explicit path option.
- Do not assume based only on recency when multiple plausible plans exist.
- Resume only after the user selects a specific `.md` file.

**Priority order:**
1. **Same directory** (primary) - Look for `plan-*.md` next to implementation file
2. **README traversal** (secondary) - Follow README.md links to find plan
3. **Parent directory** (fallback) - Search parent dirs for `plan-*.md`
4. **TaskList metadata** (fallback) - Query task for `plan_id` field
5. **CHS search** (last resort) - Search chat history for requirements discussion
6. **FAIL** - No requirements source found, HALT verification

**Discovery commands:**
```bash
# 1. Same directory (primary)
find $(dirname src/terminal_detection.py) -name "plan-*.md"

# 2. README traversal (secondary)
cat $(dirname src/terminal_detection.py)/README.md | grep -o "plan-[^)]*\.md"

# 3. Parent directory (fallback)
find $(dirname $(dirname src/terminal_detection.py)) -name "plan-*.md"

# 4. TaskList (when task exists)
# Query via task system for plan_id metadata

# 5. CHS search (fallback)
/chs "feature-name requirements"
```

**Best practice:** When implementing from a plan, the plan file should be co-located with implementation:
```
P:\\\\\\__csf/src/daemons/
  README.md (links to plan)
  plan-20260130-session-continuity.md (this plan)
  terminal_detection.py (implementation)
```

## Evidence Format

**After verification, provide:**

```markdown
## Verification Results

**Source:** [plan-name.md or "chat history session"]
**Baseline:** X passed, Y failed
**After:** X+N passed, Y-Z failed

**Integration Check:**
- Function found at: path/to/file.py:line
- Called from: module1.py, module2.py
- NOT called from: module3.py (if expected, note why)

**Test Results:**
pytest output here

**Conclusion:** IMPLEMENTED / NOT INTEGRATED / PARTIAL
```

## Prohibited Responses

**DO NOT claim verification complete without ALL of:**

- Actual command output (no "should work")
- Integration check results (grep output or code location)
- Before/after comparison (baseline captured)
- **Plan/chat history reference (source of requirements)** - MANDATORY, verification is impossible without this

**HALT if no plan or chat history reference exists** - Cannot verify requirements without source of truth. This is exactly what causes "implemented but not integrated" gaps.
