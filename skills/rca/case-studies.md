# rca Case Studies

Real-world Root Cause Analysis sessions using the 5-phase protocol.

---

## Case Study 1: SessionStart Hook Error (Recurring)

**Date**: 2026-02-15
**Problem**: Repeated "SessionStart:startup hook error" on Claude Code startup
**Impact**: High visibility - error appeared on every CLI launch
**Duration**: ~2 hours of investigation across multiple sessions

### Initial Problem Statement

```
/rca "SessionStart:startup hook error"
```

**Symptoms**:
- Error appeared on every Claude Code CLI startup
- No obvious functional degradation
- Blue terminal flash observed during startup
- Persists after fresh CLI restart

---

### Phase 1: GATHER

**Evidence Collected**:
1. Registered hook commands in `P:/.claude/settings.json` and matching implementation files in `P:/.claude/hooks/`
2. Hook execution logs from recent sessions
3. Error message pattern: consistent across all startups
4. Recent changes: plugin re-enablement in prior session

**Tools Used**:
- Local file search (Grep/Glob)
- Hook inventory (`/hook-inventory`)
- Session timeline analysis

**Key Finding**: Error appeared after re-enabling previously disabled plugins

**Authority Note**: The investigation used `P:/.claude/settings.json` as the source of truth for hook registration and `P:/.claude/hooks/` as the implementation tree. The presence or absence of files in `~/.claude/hooks` was not treated as evidence.

---

### Phase 2: ISOLATE

**Pattern Clustering**:
- Error originates from `SessionStart` hook trigger
- Multiple hook files involved in startup sequence
- stderr output from hooks treated as errors by Claude Code

**Hypothesis Generation**:
1. **H1**: Plugin hook writing to stderr (severity: HIGH, confidence: 0.7)
2. **H2**: Hook dependency version mismatch (severity: MEDIUM, confidence: 0.4)
3. **H3**: Hook execution order dependency (severity: MEDIUM, confidence: 0.3)
4. **H4**: ImportError fallback masking real issue (severity: HIGH, confidence: 0.6)

**Scoring** (`Reproducibility(0.3) * Recency(0.2) * Impact(0.5)`):
- H1: 0.9 * 0.8 * 0.7 = **0.504**
- H4: 0.8 * 0.9 * 0.6 = **0.432**

---

### Phase 3: HYPOTHESIZE

**Leading Hypothesis**: H1 - Plugin hook writing to stderr

**Mechanism**:
- Claude Code treats ANY stderr output from hooks as "hook error"
- Re-enabled plugins contain print statements or logging to stderr
- No functional issue, but triggers error classification

**Prediction**: If we find stderr writes in plugin hooks and remove them, error disappears.

---

### Phase 4: VERIFY

**Verification Steps**:
1. Searched all plugin hooks for `print(` and `sys.stderr` calls
2. Found stderr writes in plugin-related hooks
3. Created fix: Redirect output to stdout or remove entirely
4. Applied fix to affected hooks

**Result**: Error count reduced from 2 to 0 on subsequent startups

**Confirmation**: Hypothesis validated

---

### Phase 5: CONVERGE

**Root Cause**:
> Plugin hooks were writing diagnostic output to stderr. Claude Code classifies ANY stderr output from hooks as errors, regardless of actual functionality.

**Fix Applied**:
1. Removed `print()` statements from plugin hooks
2. Redirected logging to stdout where output was needed
3. Updated hook development documentation to clarify stderr prohibition

**Evidence**:
- Pre-fix: 2x "SessionStart:startup hook error" on every startup
- Post-fix: 0 errors
- Blue terminal flash eliminated

**Prevention**:
- Added "stderr = error" rule to MEMORY.md bugfixes.md
- Created hook development guidelines
- Added stderr check to `/testing-skills` validation

**Additional Findings**:
During RCA, discovered broader hook architecture issues:

### Technical Debt
- **[DEBT]** `PreToolUse_router.py`: Multiple hooks doing similar validation could consolidate into shared validation functions
- **[DEBT]** Error handling inconsistent across hooks — some raise exceptions, some return `{"continue": False}`

### Code Quality
- **[CLEANUP]** `Stop_next_step_suggester.py`: Duplicate next step detection logic exists in both template and hook — should unify
- **[REFACTOR]** `hook_tracker.py`: `is_hook_self_operation()` function has complex boolean logic that could simplify

### Documentation
- **[DOC]** Hook error message format inconsistent — should standardize user-facing error messages
- **[DOC]** Missing "Getting Started" guide for new hook developers

**Lessons Learned**:
1. **Silent ≠ Correct**: Lack of functional issues doesn't mean no problem
2. **Tool Semantics Matter**: Understanding Claude Code's error classification is crucial
3. **Reproducibility**: The error was 100% reproducible on startup, making it easier to verify the fix
4. **Meta-Lesson**: Document this pattern so future hook developers avoid stderr
5. **RCA Value**: Systematic investigation uncovered broader issues beyond immediate fix
6. **Hook Authority**: When diagnosing hook behavior, always anchor on `P:/.claude/settings.json` first and treat directory listings as implementation evidence only

---

## Case Study Template

Use this template to document future RCA sessions:

```markdown
## Case Study N: [Title]

**Date**: YYYY-MM-DD
**Problem**: [One-line description]
**Impact**: [Who/what affected]
**Duration**: [Time to resolve]

### Initial Problem Statement
```
[Exact /rca invocation or problem description]
```

**Symptoms**:
- [Bullet list of observable issues]

---

### Phase 1: GATHER
**Evidence Collected**:
- [What data/logs/files were examined]

**Tools Used**:
- [rca tools, external tools]

**Key Finding**: [Most important discovery]

---

### Phase 2: ISOLATE
**Pattern Clustering**:
- [Common themes/patterns]

**Hypothesis Generation**:
1. [H1 with severity, confidence]
2. [H2 with severity, confidence]

**Scoring**:
- H1: [score calculation]
- H2: [score calculation]

---

### Phase 3: HYPOTHESIZE
**Leading Hypothesis**: [Hx]

**Mechanism**:
- [How it works]

**Prediction**: [What we expect to see]

---

### Phase 4: VERIFY
**Verification Steps**:
1. [Step 1]
2. [Step 2]

**Result**: [What happened]

**Confirmation**: [Validated/Invalidated]

---

### Phase 5: CONVERGE
**Root Cause**:
> [One-sentence summary]

**Fix Applied**:
1. [Fix step 1]
2. [Fix step 2]

**Evidence**:
- [Pre/post comparison]

**Prevention**:
- [How to avoid recurrence]

**Additional Findings** (Optional):
During RCA, identified these opportunities beyond the immediate fix:

### Code Quality
- **[REFACTOR]** [file/area]: [description]
- **[CLEANUP]** [file/area]: [description]

### Technical Debt
- **[DEBT]** [area]: [description]

### Performance
- **[OPT]** [area]: [description]

### Documentation
- **[DOC]** [topic]: [description]

### Security
- **[SEC]** [area]: [description]

**Lessons Learned**:
1. [Lesson 1]
2. [Lesson 2]
```

---

## Contributing

To add a case study:

1. Run `/rca <problem>` on a real issue
2. Document each phase as you progress
3. Add to this file using the template above
4. Include `/rca` invocation for reproducibility

**Case studies are most valuable when**:
- The problem was non-trivial
- Multiple hypotheses were considered
- Verification was conclusive
- Prevention strategies were implemented
- Lessons are transferable to other domains
