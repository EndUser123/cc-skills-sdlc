# Action Graph, Flow-of-Action & Triple-Collection Framework

## Action Graph Template (v2.4)

**What it is:** A lightweight table you fill out during investigation to track what you did and whether it matched expectations.

**When to use:** Fill out the Action Graph template in Synthesis Checkpoint as part of EVERY RCA.

**Why it matters:**
- **Divergence detection:** Spot where your expectations didn't match reality
- **Pattern learning:** Identify which search strategies work best for different problem types
- **Post-mortem value:** Full action history for Phase 7 retrospective

### Template

| Step | Action | Expected | Actual | Divergence? | Lesson |
|------|--------|----------|--------|-------------|--------|
| 1 | [Describe action] | [What you expected] | [What actually happened] | Yes/No | [What you learned] |
| 2 | ... | ... | ... | ... | ... |

### Example from flashing progress bar session:

| Step | Action | Expected | Actual | Divergence? | Lesson |
|------|--------|----------|--------|-------------|--------|
| 1 | Multi-angle search | Find all Progress contexts | Found 6 matches (4 Progress + 2 stdout) | No | Comprehensive search worked |
| 2 | Fix Hypothesis #1 | User confirms fixed | User: "Still flashing" | **Yes** | H1 wrong, need H2 |
| 3 | Gap analysis (Q: What does user see I haven't explained?) | All symptoms explained | User sees "yt-api: 54%" - need to find code producing this | No | Functional search needed |
| 4 | Functional search `grep("yt-api:")` | Find code producing visible output | Found 2 manual stdout writes | No | Should have done this first |
| 5 | Fix manual stdout writes | User confirms fixed | User: "Fixed" | No | Root cause found |

**First Divergence Point:** After initial fix, user revealed incomplete diagnosis
**Lesson:** Use multi-angle search for visible symptoms (mechanism + functional)

## Advanced: Flow-of-Action Paradigm

For complex multi-step investigations, you can model investigation as a directed graph:

**Nodes:** Actions (READ_FILE, SEARCH_CODE, TRACE_SYMBOL, FORM_HYPOTHESIS, VERIFY_HYPOTHESIS)
**Edges:** Causal dependencies between actions
**Divergence:** Where actual execution diverged from expected path

**Most users:** Use the simple table template above.
**Advanced users:** See `P:/packages/rca/design/flow_of_action_paradigm.md` for full formal specification.

## Triple-Collection Framework (v2.5)

**Explicit bucket mapping for Action Graph to ensure comprehensive evidence collection.**

**Framework Purpose**: Prevent incomplete investigations by requiring evidence from three distinct buckets before forming hypotheses.

**Bucket Mapping**:

| Action Graph Column | Triple-Collection Bucket | Example |
|---------------------|--------------------------|----------|
| **Action** | Mechanism | `grep("Progress(", "src/")` |
| **Expected vs Actual** | State | Expected: 'No stdout writes', Actual: 'Found 2 writes' |
| **Divergence?** | Outcome | Yes - state mismatch caused user-visible bug |

### Before hypothesis formation, collect from all 3 buckets:

**Bucket 1: Mechanism Evidence** (How is it implemented?)
- Code paths, function calls, API usage
- Grep for implementation: Use `rg` (ripgrep) with timeout for performance
- Read source files to understand logic
- Search for patterns like: `def`, `class`, `import`, `async def`

**Bucket 2: State Evidence** (What does runtime state look like?)
- State files: `P:\.claude\hooks\state\*.json`
- Environment variables: `CLAUDE_SESSION_ID`, `CLAUDE_TERMINAL_ID`
- Logs: `P:\.claude\hooks\logs\*.log`
- Pending intents: Count and check for stale files

**Bucket 3: Outcome Evidence** (What does user actually see?)
- Tool use transcripts: Skill calls, Bash outputs
- Hook execution logs: Hook diagnostics output
- User reports: Exact quotes from user describing observable
- Screenshots/errors: Actual error messages, not summaries

### Spec vs Observed Separation (REQUIRED in v2.6)

**CRITICAL**: Separate intended architecture from observed behavior to prevent "docstring-driven development"

**Two-Column Format**:

| Column A: Intended Architecture (Spec) | Column B: Observed Behavior (Reality) |
|----------------------------------------|----------------------------------------|
| Source: docs, comments, design notes, CLAUDE.md | Source: logs, state files, transcripts, tests |
| What SHOULD happen according to design | What ACTUALLY happens in runtime |

**Example** (skill-guard bug):

| Column A: Intended Architecture | Column B: Observed Behavior |
|--------------------------------|------------------------------|
| From docstring: "skill_enforcer enforces Skill tool usage" | From tool transcript: No Skill() event for /gto command |
| From CLAUDE.md: "AI must call Skill(gto) explicitly" | From state inspection: terminal_id mismatch prevents enforcement |
| From code comment: "Directive injected into prompt" | From logs: Directive present but Skill() not called |

**Rules**:
- FORBIDDEN: Root-cause statements citing ONLY Column A (docs/comments)
- REQUIRED: Column B evidence (runtime/state) for all behavioral claims
- WARNING: When Column A != Column B, the discrepancy IS the bug

**Hypothesis Formation Gate**:
- FORBIDDEN: Form hypothesis with < 3 buckets (without documenting why bucket is empty)
- REQUIRED: All 3 buckets collected OR empty bucket documented with stronger evidence from others

**Empty Bucket Protocol**:
- If bucket genuinely empty (e.g., no state files exist):
  1. Document WHY bucket is empty (e.g., "No state files - first session")
  2. Require 2x evidence from remaining buckets
  3. State confidence penalty: 1 bucket empty -> max 60%, 2 empty -> max 40%

**Performance Optimization**:
- Use `rg` (ripgrep) with `--max-count 20` instead of `grep -r` for faster searches
- Timeout: 5 seconds max per search
- Cache state metadata between Step 1.5 and Step 1.65 to avoid redundant I/O
- Fallback: If rg times out, try more specific search patterns

### Example Application (skill-guard bug):

**WRONG** (incomplete evidence):
```
Bucket 1 (Mechanism): Found breadcrumb_init.py creates indicator
-> Hypothesis: "Indicator missing, fixed"
-> User: "Still doesn't work"
-> Missed: No state inspection, no tool transcript check
```

**CORRECT** (triple-collection):
```
Bucket 1 (Mechanism): Found breadcrumb_init.py creates indicator
Bucket 2 (State): Checked intent files - terminal_id mismatch found
Bucket 3 (Outcome): User sees no Skill() in tool transcript
-> Hypothesis: "Terminal ID mismatch prevents Skill invocation"
-> Root cause found, fix works
```
