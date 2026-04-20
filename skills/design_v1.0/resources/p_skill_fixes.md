# /p Skill - Architectural Fix Solutions

## Executive Summary

Analysis of the `/p` Code Maturation Pipeline skill revealed **12 gaps** across three impact tiers. Below are prioritized architectural solutions for each issue.

---

## Fix-Now Issues (High-Impact)

### Issue #1: HALT Format Validator Misalignment

**Problem:** `StopHook_p_halt_format_validator.py` (lines 87-94) checks for specific format strings that don't match SKILL.md spec (lines 451-461).

**Root Cause:** Hook was written against an earlier draft of the halt format spec. The spec evolved but the hook didn't.

**Solution:** Make the validator pattern-based rather than string-exact.

```python
# STOPHook_p_halt_format_validator.py - REPLACEMENT LOGIC

# OLD (brittle exact strings):
numbered_format_checks = [
    r"1\s*-\s*/tdd Fix",
    r"2\s*-\s*/tdd Fix CRITICAL",
    r"3\s*-\s*/tdd Fix HIGH",
    r"4\s*-\s*/tdd Fix all findings",
    r"x\s*-\s*Fix all verified findings:",
    r"Then re-run:\s*/p",
]

# NEW (pattern-based that works for both formats):
def check_halt_action_items(response_text: str) -> tuple[bool, list[str]]:
    """
    Validate halt response contains actionable next steps.
    Returns (is_valid, missing_elements)
    """
    required_elements = {
        "numbered_list": r"\d+\s*-\s*/tdd",  # "0 - /tdd all" or "1 - /tdd Fix Security"
        "tdd_command": r"/tdd\s+(Fix|all)",  # Any /tdd invocation
        "rerun_instruction": r"re-run:\s*/p|Then run /p again",  # Continuation path
    }

    missing = []
    for elem_name, pattern in required_elements.items():
        if not re.search(pattern, response_text, re.IGNORECASE):
            missing.append(elem_name)

    return len(missing) == 0, missing

# Integration in main():
if has_halt:
    valid, missing = check_halt_action_items(response_text)
    if not valid:
        errors.append(
            f"Missing required HALT action items: {', '.join(missing)}. "
            "HALT responses must include numbered /tdd commands and re-run instructions."
        )
```

**Why This Works:**
- Accepts BOTH "0 - /tdd all" AND "1 - /tdd Fix Security" formats
- Future-proof: allows format evolution without breaking the hook
- Focuses on semantic intent (actionable /tdd commands) not exact strings

---

### Issue #2: Duplicate "Step 4" Labeling

**Problem:** Two sections labeled "Step 4" (lines 282 and 313).

**Root Cause:** Section was inserted without renumbering subsequent steps.

**Solution:**
```markdown
### Step 4: Invoke Appropriate Phase
[Content stays at lines 282-311]

### Step 5: Check for Blocking Errors (HALT Condition)
[Content moves from current line 313]

### Step 6: Report and Continue
[Content from current line 330+]
```

**Implementation:**
1. Replace "### Step 4:" at line 313 with "### Step 5:"
2. Replace "### Step 5:" at line 330 with "### Step 6:"
3. Verify all internal cross-references update accordingly

---

### Issue #3: Detection Subagent 3 Doesn't Check Marker Files

**Problem:** Detection table (lines 247-252) lists marker files, but Subagent 3's commands don't check them.

**Root Cause:** Subagent commands were written for generic project inspection, not marker-aware detection.

**Solution:** Add marker-aware detection to Step 2.

**Insert after line 246:**

```markdown
### Step 2.5: Marker File Detection (Inline)

**CRITICAL:** Before routing to subagents, check marker files directly:

```python
# PSEUDOCODE for inline marker detection
marker_checks = {
    "review_complete": [
        ".claude/findings/adversarial-review.json",
        ".claude/state/review-complete.marker"
    ],
    "validation_complete": [
        ".claude/state/validation-complete.marker",
        ".claude/reports/validation-report.md"
    ],
    "publish_complete": [
        ".claude/state/publish-complete.marker",
        "README.md"  # Publish phase creates README
    ]
}

# Use Glob tool to check existence
for phase, markers in marker_checks.items():
    if any(Path(m).exists() for m in markers):
        current_phase = next_phase(phase)
```

**Why Inline:** Marker detection is a 5-second Glob check. Subagent overhead is unnecessary.

**Subagent 3's Actual Role:** Project structure analysis (package.json, go.mod, etc.) for language detection — NOT marker detection.
```

**Then update Subagent 3's responsibility description:**
```markdown
**Subagent 3: Language & Framework Detection**
- Detects: Python (pyproject.toml), JavaScript (package.json), Go (go.mod), Rust (Cargo.toml)
- Returns: Language, test framework, build system
- Does NOT check marker files (handled inline in Step 2.5)
```

---

## Next-Iteration Issues (Medium-Impact)

### Issue #4: No Non-Python Codebase Handling

**Problem:** P1 detection uses `pytest --collect-only`, assumes Python.

**Solution:** Add language-aware test detection to Step 2.

**Insert new section after line 230:**

```markdown
### Step 2.3: Language-Aware Test Detection

**Before running test detection, identify project language:**

| Language | Detection Signal | Test Command | Expected Output |
|----------|------------------|--------------|-----------------|
| Python | pyproject.toml, setup.py | `pytest --collect-only` | "collected N items" |
| JavaScript/TS | package.json | `npm test -- --listTests` (Jest) or `vitest run --listFiles` | List of test files |
| Go | go.mod | `go test ./... -list=.*` | List of test functions |
| Rust | Cargo.toml | `cargo test --no-run -- -Z unstable-options --list` | List of tests |
| Ruby | Gemfile | `rake test:directory` | Test directory listing |
| Java | pom.xml, build.gradle | `mvn test -Dtest=list` or `gradle tests --dry-run` | Test classes |

**Fallback:** If language detection fails, default to:
```bash
find . -name "*test*" -o -name "*.test.*" -o -name "*.spec.*" | head -20
```

**If zero tests found across all strategies:**
→ Route to P0 (Scaffold) with message: "No test framework detected. P0 can scaffold tests for your language."
```

---

### Issue #5: `--continue` Flag Referenced But Not Documented

**Problem:** Examples suggest `--continue`, but Usage section doesn't list it.

**Root Cause:** `--continue` was planned but never implemented.

**Solution A:** Remove `--continue` references (simpler)

**Solution B:** Implement `--continue` properly:

```markdown
### Usage

```
/p                    # Auto-detect and run what's needed (full file set)
/p <target>           # Target specified (path or natural-language scope description)
/p --quick            # Only check changed files (git diff)
/p --publish          # Halt on warnings (treat non-blocking warnings as blocking)
/p --continue         # Resume from last halted phase (reads .claude/state/p-halt.marker)
/p --quick --publish  # Combined: changed files only + halt on warnings
```

**How `--continue` works:**

1. On HALT, write `.claude/state/p-halt.marker`:
   ```json
   {
     "halted_at": "P2",
     "halted_reason": "CRITICAL findings remaining",
     "halted_timestamp": "2025-01-11T12:34:56Z"
   }
   ```

2. On `/p --continue`:
   - Read marker
   - Skip detection, jump directly to halted phase
   - Re-check halt condition (user may have fixed issues)
   - If still halted, re-output halt format
   - If passed, continue to next phase

3. On successful completion, delete marker
```

**Recommendation:** Implement Solution B — `--continue` is valuable for iterative workflows.

---

### Issue #6: `--phase=N` Described Twice Inconsistently

**Problem:** Two sections describe phase selection differently (lines 284-299 vs 1087-1101).

**Solution:** Consolidate into single canonical reference.

**Replace both sections with:**

```markdown
### Phase Selection

**Direct invocation (bypasses detection):**
```
/p0                   # Force P0 (Scaffold)
/p1 <target>          # Force P1 (Build)
/p2 <target>          # Force P2 (Review)
/p3 <target>          # Force P3 (Validate)
/p4 <target>          # Force P4 (Publish)
/p5 <target>          # Force P5 (Certify)
/p6 <target>          # Force P6 (Security)
```

**Flag-based invocation (legacy):**
```
/p --phase=1 <target>  # Equivalent to /p1 <target>
/p --phase=2 <target>  # Equivalent to /p2 <target>
```

**Recommendation:** Use direct invocation (`/p1`, `/p2`) — clearer and discoverable via `/p` tab-completion.

**With file scope flags:**
```
/p1 --quick src/      # Run P1 on changed files only
/p2 --publish src/    # Run P2, then P3 with --publish behavior
```
```

---

### Issue #7: Scope Inference Has No Timeout/Fallback

**Problem:** Step 0 suggests `query: get_files_from investigation-ledger` as fallback, but if ledger fails, asks user immediately.

**Solution:** Add fallback chain before user escalation.

**Replace Step 0 logic with:**

```markdown
### Step 0: Scope Inference with Fallback Chain

**Priority:**
1. **Explicit target argument** (if provided)
2. **Investigation ledger** (if available and recent < 1 hour)
3. **Git diff** (if on a branch with changes)
4. **Current working directory** (cwd)
5. **User prompt** (last resort)

**Implementation:**
```python
# PSEUDOCODE
def infer_scope(user_arg, ledger, cwd):
    # 1. Explicit argument
    if user_arg:
        return resolve_path(user_arg)

    # 2. Investigation ledger (with timeout)
    try:
        ledger_entry = ledger.get_last_entry(timeout=1.0)  # 1 second timeout
        if ledger_entry and ledger_entry.age < 3600:  # < 1 hour old
            return ledger_entry.files
    except (TimeoutError, LedgerUnavailable):
        pass  # Fall through to next strategy

    # 3. Git diff (if branch has changes)
    if has_git_changes():
        return get_git_diff_files()

    # 4. Current directory
    if cwd and is_valid_project_dir(cwd):
        return cwd

    # 5. Ask user
    return prompt_user("What should /p analyze?")
```

**Why This Works:**
- Ledger failures don't block — timeouts prevent hanging
- Git diff is a reasonable default for active development
- Fallback to cwd is sensible for project-root usage
- User prompt only when all automation fails
```

---

## Consider Issues (Low-Impact / Opportunities)

### Issue #8: `--reverse` Effort Estimates Are Fabricated

**Problem:** Example shows "Estimated effort: 2-4 hours" but skill has no basis for this.

**Solution A:** Remove effort estimates entirely (simplest)

**Solution B:** Make estimates explicitly heuristic and conditional:

```markdown
**Example output (with --reverse):**
```
## Pipeline Status: COMPLETE (Reverse Order)

**Status:** ✅ ALL PHASES PASSED
**Route:** P5 → P4 → P3 → P2 → P1 → P0
**Duration:** 12 minutes 34 seconds

**Effort Estimate:** (if enabled)
- Rough heuristic based on test count + findings count
- Range: 1-2 hours (for 50 tests, 8 findings)
- Accuracy: ±50% — highly variable by codebase complexity
- To disable: `export P_NO_ESTIMATE=1`
```

**Recommendation:** Solution A — remove estimates. They're not reliable and create false expectations.

---

### Issue #9: P6 Missing from `suggest:` / `depends_on_skills`

**Problem:** P6 appears in detection table and pipeline diagram but not YAML header.

**Solution:** Add P6 to YAML header.

```yaml
suggest:
  - /p1
  - /p2
  - /p3
  - /p4
  - /p5
  - /p6

depends_on_skills:
  - /p0
  - /p1
  - /p2
  - /p3
  - /p4
  - /p5
  - /p6
```

---

### Issue #10: Adaptive Depth Table Is Vague

**Problem:** "What Runs" column lists outcomes but not detection signals.

**Solution:** Sharpen the table or remove it.

**Option A:** Remove the table (if it doesn't drive behavior)

**Option B:** Make it actionable:

```markdown
| Context                | Detection Signal                                  | What Runs                          |
|------------------------|---------------------------------------------------|------------------------------------|
| Local iteration        | `--quick` flag set                                | P1 (changed files only)            |
| Release branch         | Branch name matches `release/*` or `main`         | P1 → P2 → P3 → P6 (full pipeline)  |
| Hotfix                 | Branch name matches `hotfix/*`                     | P1 → P6 (build + security only)    |
| CI/CD                  | `CI=true` environment variable                    | P1 → P3 → P6 (no P2 review)        |
| Default (no context)   | None of the above                                 | P1 → P2 (build + review)           |

**Implementation:**
```python
# PSEUDOCODE
def detect_context():
    if flags.quick:
        return "local_iteration"
    if branch_name.startswith(("release/", "main")):
        return "release_branch"
    if branch_name.startswith("hotfix/"):
        return "hotfix"
    if os.getenv("CI") == "true":
        return "ci_cd"
    return "default"
```
```

**Recommendation:** Option B — make Adaptive Depth actually drive behavior or remove it.

---

### Issue #11: FABRICATION_PATTERNS Only Catches Box-Drawing Tables

**Problem:** Standard markdown tables (`| col | col |`) pass unchallenged.

**Solution:** Strengthen fabrication detection.

**Replace in `StopHook_p_halt_format_validator.py`:**

```python
# OLD (only box-drawing):
has_heavy_tables = bool(re.search(r"[┌├└│┐┤┘─┬┴┼]{10,}", response_text))

# NEW (all table formats + stricter evidence gate):
def check_for_fabricated_tables(text: str) -> tuple[bool, str]:
    """
    Detect fabricated results tables without execution evidence.
    Returns (is_fabricated, reason).
    """
    # Check for ANY table format (box-drawing OR markdown)
    has_box_tables = bool(re.search(r"[┌├└│┐┤┘─┬┴┼]{10,}", text))
    has_md_tables = bool(re.search(r"^\|.*\|$", text, re.MULTILINE))

    # Count evidence patterns (more strict)
    evidence_patterns = [
        (r"pytest", 1),                      # Test runner
        (r"PASSED|FAILED|ERROR", 2),         # Test results
        (r"git (status|diff|log)", 1),       # Git commands
        (r"collected \d+ items?", 2),        # pytest collection
        (r"\.py::\w+", 2),                   # Test paths
        (r"(Read|Glob|Bash|Task)\(", 1),     # Tool calls
        (r"Subagent \d+", 2),                # Subagent launches
        (r"exit code \d+", 1),               # Command results
    ]

    evidence_score = sum(
        weight for pattern, weight in evidence_patterns
        if re.search(pattern, text, re.IGNORECASE)
    )

    # Fabrication if: tables exist AND evidence_score < threshold
    EVIDENCE_THRESHOLD = 5  # Require 5 evidence points

    if (has_box_tables or has_md_tables) and evidence_score < EVIDENCE_THRESHOLD:
        return True, (
            f"FABRICATION DETECTED: Response contains formatted tables but lacks "
            f"execution evidence (evidence_score={evidence_score}, required={EVIDENCE_THRESHOLD}). "
            f"Tables require: pytest output, git commands, Bash results, or subagent launches. "
            f"Re-run with actual tool calls."
        )

    return False, ""

# Integration in main():
has_heavy_tables = False  # Old variable removed
is_fabricated, fabrication_reason = check_for_fabricated_tables(response_text)

if is_fabricated:
    print(json.dumps({"allow": False, "reason": fabrication_reason}))
    sys.exit(1)
```

**Why This Works:**
- Catches ALL table formats
- Evidence scoring is weighted (pytest output worth more than generic "git")
- Threshold of 5 requires multiple evidence types
- Clear feedback on what's missing

---

### Issue #12: No Session/Resume Concept

**Problem:** If pipeline halts and user fixes incrementally, `/p` reruns full detection.

**Solution:** Incremental re-validation via `--continue` flag (see Issue #5 Solution B).

**Additional enhancement:** Add targeted recheck.

```markdown
### Targeted Recheck (Post-HALT)

**After fixing specific findings, user can recheck just those:**

```bash
# User fixed SEC-001 and SEC-002
/tdd Fix SEC-001 SEC-002

# Recheck ONLY those findings (not full pipeline)
/p --recheck SEC-001 SEC-002
```

**How `--recheck` works:**

1. Read `.claude/findings/adversarial-review.json`
2. Filter to findings with IDs in `--recheck` list
3. Run targeted validation:
   ```bash
   # If SEC-001 is "SQL injection in user_query()":
   pytest tests/test_user_query.py::test_sql_injection -v
   ```
4. Update finding status: `PASSED` or `FAILED`
5. Re-evaluate HALT condition:
   - If blocking findings remain → HALT again
   - If all blocking fixed → continue to next phase

**Benefits:**
- Faster feedback loop (seconds vs minutes)
- Encourages incremental fixes
- Avoids redundant full-pipeline runs
```

---

## Implementation Priority

### Phase 1: Critical Fixes (This Week)
1. ✅ Fix HALT format validator (Issue #1)
2. ✅ Renumber duplicate Step 4 (Issue #2)
3. ✅ Add inline marker detection (Issue #3)

### Phase 2: Medium-Priority (Next Iteration)
4. ✅ Add language-aware test detection (Issue #4)
5. ✅ Implement or remove `--continue` flag (Issue #5)
6. ✅ Consolidate `--phase=N` documentation (Issue #6)
7. ✅ Add scope inference fallback chain (Issue #7)

### Phase 3: Low-Priority / Consider
8. ⚠️ Remove or fix effort estimates (Issue #8)
9. ⚠️ Add P6 to YAML header (Issue #9)
10. ⚠️ Sharpen or remove Adaptive Depth table (Issue #10)
11. ⚠️ Strengthen fabrication detection (Issue #11)
12. ⚠️ Add session/resume concept (Issue #12)

---

## Testing Checklist

For each fix, verify:

- [ ] Hook validator passes with NEW format
- [ ] Hook validator fails with fabricated tables
- [ ] Step numbering is sequential
- [ ] Marker files are checked before subagent dispatch
- [ ] Non-Python projects detected correctly
- [ ] `--continue` flag resumes from correct phase
- [ ] Scope inference doesn't hang on ledger timeouts
- [ ] Effort estimates are either accurate or removed
- [ ] P6 appears in `/p` suggestions
- [ ] Adaptive Depth table drives actual behavior
- [ ] Fabrication detection catches markdown tables
- [ ] `--recheck` validates only specified findings

---

## Architectural Insights

### Pattern: Specification-Implementation Drift
**Issue #1 is a classic example:** Spec (SKILL.md) evolved, validator didn't.

**Prevention:** Establish a contract test:
```python
# test_halt_format_contract.py
def test_spec_matches_hook():
    """
    Ensures HALT format in SKILL.md matches hook validator.
    Run this test whenever SKILL.md halt format changes.
    """
    spec = extract_halt_format_from_skill_md()
    hook_patterns = extract_patterns_from_validator()

    assert spec.is_subset_of(hook_patterns), "SKILL.md format not accepted by hook"
```

### Pattern: Numbered Step Fragility
**Issue #2:** Manual numbering is error-prone.

**Prevention:** Use bullet points or automatic numbering:
```markdown
### Workflow Steps

**Step:** Invoke appropriate phase
[Content]

**Step:** Check for blocking errors
[Content]
```

### Pattern: Subagent Over-Engineering
**Issue #3:** Subagent for 5-second file checks.

**Prevention:** Decision tree before subagent dispatch:
```
Can this be done with Glob/Read in < 10 seconds?
  YES → Do it inline
  NO  → Subagent
```

---

## Conclusion

The `/p` skill is well-architected but suffers from **specification drift** and **over-engineering** in a few areas. The fixes above strengthen the contract between documentation, hooks, and execution while reducing unnecessary complexity.

**Highest ROI changes:** Issues #1, #3, and #11 — all relate to validation and fabrication detection, which are critical for trust in the pipeline's output.
