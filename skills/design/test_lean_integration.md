# Test: Verify /arch Applies Lean System Design Principles

**Date:** 2026-03-10
**Purpose:** Verify that Lean System Design principles are automatically applied when using /arch

## Test Cases

### Test 1: Deep template with design query
**Query:** `/arch "design caching system for API responses" template=deep`

**Expected output should include:**
- ✅ Core goals alignment check (cross-file understanding / consolidation / runtime safety)
- ✅ Dependency audit (MUST/SHOULD/MAY classification)
- ✅ Consolidation check (duplicate mechanisms vs existing hooks)
- ✅ Core Plan (5-10 tasks, ~80% value)
- ✅ Extended Plan (marked optional)
- ✅ Environment & Preference Fit section

**Verification checklist:**
- [ ] "For each subsystem, how does it advance [cross-file understanding / consolidation / runtime safety]?"
- [ ] "Dependency audit: MUST / SHOULD / MAY"
- [ ] "Potential duplicate mechanisms I introduced vs existing hooks/policies"
- [ ] "Core Plan (minimal v1 to achieve goals)"
- [ ] "Extended Plan (optional, only if/when needed)"
- [ ] "Environment & Preference Fit"

### Test 2: Fast template with decision query
**Query:** `/arch "should I use Redis or Memcached" template=fast`

**Expected output should include:**
- ✅ Value justification (which goal this advances)
- ✅ Dependency audit (at least MUST-level dependencies)
- ✅ Consolidation check (against existing cache hooks if applicable)
- ✅ Core Plan (focused, 5-10 tasks)

**Verification checklist:**
- [ ] Clear value statement
- [ ] Dependency classification
- [ ] Core vs Extended plan separation
- [ ] No over-engineering

### Test 3: Python template with domain-specific query
**Query:** `/arch "design async task processing system" template=python`

**Expected output should include:**
- ✅ Domain frameworks applied (asyncio, type hints)
- ✅ Lean principles applied alongside domain concerns
- ✅ Python-specific dependency audit (asyncio, trio, curio)
- ✅ Core Plan focused on Python stdlib where possible

**Verification checklist:**
- [ ] "Frameworks applied: Lean System Design + Python-specific"
- [ ] Dependency audit includes Python stdlib preference
- [ ] Core Plan minimizes external dependencies
- [ ] Environment fit mentions Python 3.14+ compatibility

## Test Execution

**Status:** Pending execution

**Results will be recorded here after running tests.**

## Success Criteria

**Pass:** All test cases show lean principles applied in output
**Fail:** Lean principles missing from output
**Partial:** Some lean principles applied, others missing

---

**Next step:** Run Test 1 and record results
