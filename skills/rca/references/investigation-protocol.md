# Investigation Protocol - Detailed Steps

## Step -1: Surgical First Response (MANDATORY)

**When user reports an error with a fragment or paste:**

**Do this IMMEDIATELY (no questions, no theater):**

1. **Grep exact strings** from error message
   ```bash
   grep -r "exact_error_text" "relevant_dir/"
   ```

2. **Read matching files** -- all of them

3. **State findings:**
   - "Found X matches at [file:line]"
   - "Investigating now" or "Here's what I found: [brief summary]"

**BANNED behaviors (pre-diagnosis):**
- "Can you clarify?" -- grep first, then ask if needed
- "NOT A BUG" -- trust user report
- Verbose RCA (tables, confidence scores, causal chains) -- save for post-fix
- Happy-path testing -- test real execution context

**REQUIRED behaviors:**
- Immediate grep for exact error strings
- Assume user's report is ground truth
- Read actual code before forming hypotheses
- Test real execution path (check settings.json/configs, not `python file.py`)

**User pushback protocol:**
When user says "I told you X" or "why are you pretending":
1. STOP current approach immediately
2. ACKNOWLEDGE: "You're right -- I was testing [wrong path]"
3. PIVOT to correct action: grep/test real context
4. NO more wrong tests after acknowledgment

**Then proceed to:** Step 0: Pre-Flight Checks

---

## Step 0: Pre-Flight Checks

**Check for prior knowledge** -- search CKS/CHS and read `memory/MEMORY.md` for similar past problems

### Step 0.5: Cognitive Stack Integration

**After checking prior knowledge, classify the problem type:**

1. Review the Cognitive Stack Integration section (see references/cognitive-stack-and-tot.md)
2. Identify problem type: ERROR, PERFORMANCE, CRASH, SECURITY, INTEGRATION, INTERMITTENT, or NEW/NOVEL
3. Select appropriate mental models based on problem type
4. Document selected mental models in RCA output

**Example:**
```
Problem type: PERFORMANCE (slow/flashing UI)
Mental models: Systems Thinking (+15%), First Principles (+10%)
Total boost: +25%
```

### Step 0.75: Internet Research (MANDATORY)

**MANDATORY: Before forming hypotheses, research the relevant technologies/frameworks.**

1. **Identify key technologies** involved in the symptom
   - Libraries/frameworks (e.g., ThreadPoolExecutor, Rich Live, Django, React)
   - APIs/interfaces being used
   - Platform-specific behaviors (Windows signal handling, Linux signals)

2. **Research official documentation:**
   ```bash
   # Use WebSearch to find official docs
   WebSearch("[technology] official documentation KeyboardInterrupt signal handling")
   WebSearch("[library] how to handle Ctrl-C SIGINT")
   ```

3. **Research known issues/patterns:**
   ```bash
   WebSearch("[technology] KeyboardInterrupt not working slow")
   WebSearch("[library] signal handling best practices")
   ```

4. **Document findings in RCA output:**
   ```markdown
   ### External Research
   | Source | Finding | Relevance |
   |--------|---------|-----------|
   | [URL] | ThreadPoolExecutor context manager calls shutdown(wait=True) on exception | Confirms hypothesis |
   ```

**Why this matters:**
- Static code analysis (Tier 2 evidence) can miss framework-specific behaviors
- Official docs clarify expected behavior vs actual implementation
- Prevents "reinventing the wheel" - someone else has likely encountered this
- Distinguishes "bug in my code" from "bug in framework" or "expected behavior"

**Confidence boost:** External documentation raises evidence tier from Tier 2 (75%) to Tier 2+ (80-85%).

---

## Step 1: Start with Falsifiable Symptom

**Define exactly what is wrong:**
- What is the observable behavior?
- What should happen instead?
- When did it start?

### Step 1.5: Telemetry Discovery (FIRST-PASS SWEEP) — MANDATORY FOR HOOK ERRORS

**MANDATORY when symptom involves hook errors, blocks, or unexpected tool denials.**

1. **For hook/block errors: query pretooluse_blocks.jsonl FIRST (highest priority)**
   ```bash
   # Get recent blocks for the session/terminal from the error
   python - <<'PY'
   import json
   from pathlib import Path
   blocks = Path("P:\\\\\\.claude/hooks/logs/diagnostics/pretooluse_blocks.jsonl")
   if blocks.exists():
       with open(blocks) as f:
           lines = f.readlines()
       # Get last 50 blocks
       recent = [json.loads(l) for l in lines[-50:]]
       for b in recent[-10:]:
           print(f"{b['ts']} | {b['tool_name']} | {b['blocking_hook']} | {b.get('event_kind','')}")
   PY
   ```

2. **Query importer diagnostics for hook load/execute errors**
   ```bash
   python - <<'PY'
   import sqlite3, datetime
   conn = sqlite3.connect(r"P:\\\\\\.claude/hooks/logs/diagnostics/diagnostics.db")
   cur = conn.cursor()
   cur.execute("""
       SELECT timestamp, hook_name, phase, session_id, error_text
       FROM importer_diagnostics
       ORDER BY id DESC LIMIT 20
   """)
   for row in cur.fetchall(): print(row)
   PY
   ```

3. **Enumerate all available sources:**
   - Hook execution logs (`P:\\\\\\.claude/hooks/logs/`)
   - Session/terminal state files (`P:\\\\\\.claude/hooks/state/`)
   - Skill invocation audit log (`P:\\\\\\.claude/state/skill_invocations.jsonl`)
   - Evidence store database (`P:\\\\\\__csf/data/cks.db`)
   - Session transcript files (`P:\\\\\\.claude/transcripts/`)
   - RCA workflow state (`~/.claude/state/rca/rca_workflow.json`)
   - Pending intent files (`P:\\\\\\.claude/hooks/state/pending_command_intent_*.json`)
   - **Hook events database** (`P:\\\\\\.claude/hooks/events.db`)
   - **Hook diagnostics DB** (`P:\\\\\\.claude/hooks/logs/diagnostics/diagnostics.db`) — importer errors, load failures

4. **Search relevant logs for symptom keywords:**
   ```bash
   python $CLAUDE_ROOT/skills\rca\tools\telemetry_discovery.py --match "error_keyword" --since 7
   ```

5. **Query hook events DB for TruthValidation/BloatAnalysis:**
   ```bash
   python $CLAUDE_ROOT/skills\rca\tools\telemetry_discovery.py --events-db "TruthValidation"
   python $CLAUDE_ROOT/skills\rca\tools\telemetry_discovery.py --events-db "BloatAnalysis"
   ```

6. **Add telemetry findings to evidence buckets BEFORE forming hypotheses:**
   - **Bucket 1 (Mechanism)**: Hook logs showing code path execution
   - **Bucket 2 (State)**: Session state, intent files, workflow state
   - **Bucket 3 (Outcome)**: Skill invocations, transcript events
   - **Bucket 4 (Hook Events)**: events.db constitutional_events filtered by symptom keyword
   - **Bucket 0 (Authority)**: `P:\\\\\\.claude/settings.json` when the symptom involves hook registration or enforcement

**Why this matters:**
- Telemetry is Tier 1 evidence (highest confidence) — logs don't lie
- `pretooluse_blocks.jsonl` shows EXACTLY which hook blocked, when, and why (in `reason` field)
- `diagnostics.db` shows hook load failures (SyntaxError, ImportError) that cause silent degradation
- Symptom time window focuses the search — don't read 1000 logs when 3 are relevant
- Hook logs often reveal exactly which branch was taken, what inputs were received
- Session state reveals whether hooks fired, whether state was written

**Evidence tier:** Direct log access = Tier 1 (95%). If telemetry unavailable, note: "Telemetry unavailable — proceeding with code analysis (Tier 3)."

**Hook-specific rule:** If the RCA is about hooks, skill enforcement, or hook registration, inspect `P:\\\\\\.claude/settings.json` before drawing any conclusion from directory listings. The registered hook commands in settings are the authority; `P:\\\\\\.claude/hooks/` is only the implementation tree.

### Step 1.6: Check Learned Patterns (AUTO-LEARNING)

**Before searching, check CKS for patterns learned from previous RCA sessions.**

**Query CKS for learned patterns:**
```bash
Query shared/memory-system.md for "rca pattern [symptom_type]"
```

Or use the rca hook's automatic suggestion (if mechanism-only warning triggered).

**Apply learned patterns:**
```bash
# CKS might suggest: "When searching Progress(, also search: yt-api:, status:, %"
# Add these functional searches to your Step 1.7 multi-angle search
grep("yt-api:", "src/")      # Learned functional pattern
grep("status:", "src/")      # Learned functional pattern
grep("Progress(", "src/")     # Your mechanism search (already done)
```

**Why this matters:**
- **Pattern 1:** You search for `Progress(` implementation (mechanism)
- **Pattern 2:** System warns: "Add functional search: grep('yt-api:')"
- **Pattern 3:** You find bug in stdout write (functional pattern worked!)
- **Auto-Extract:** System stores "Progress( -> also search yt-api:" in CKS
- **Next Session:** CKS automatically suggests yt-api: when you search Progress(

**Project Memory:** Also check `memory/MEMORY.md` for relevant feedback patterns, bugfix history, or behavioral lessons from prior sessions.

**Pattern storage location:** `~/.claude/memory/cks/rca_patterns/`

---

## Step 1.7: Multi-Angle Search

**MANDATORY multi-angle search strategy: Use prescriptive templates.**

See `references/search-templates.md` for the 5 symptom-type templates (PERFORMANCE, ERROR, INTEGRATION, INTERMITTENT, SECURITY).

---

## Step 1.8: Trace Execution Path (MANDATORY for hangs/timeouts)

**Before forming hypotheses about hangs/timeouts/indefinite waits:**

1. **Add logging/blocking detection** at each function call in suspected path
   - Insert `print("[DEBUG] Before function_x")` before each call
   - Insert `print("[DEBUG] After function_x")` after each call
   - Use `flush=True` to ensure output before hang

2. **Execute and capture** which function never returns
   - Run the code with timeout
   - Note the last debug message before hang
   - The function after that message is the blocker

3. **Read the blocking function's source code**
   - Use Read/Grep to find what it calls
   - Look for subprocess calls, network requests, long operations
   - Check timeout parameters and error handling

4. **Only THEN form hypothesis** about root cause
   - "Function X at line Y blocks because Z" (Tier 1: observed)
   - NOT "Probably timeout issue" (Tier 3: speculation)

**Evidence tier upgrade:**
- With trace: Execution logs = Tier 1 (95% confidence)
- Without trace: Maximum Tier 2 (75% confidence) - must state "speculative"

**Anti-patterns to avoid:**
- Proposing timeout changes without identifying WHERE it blocks
- Adding skip/wrapper logic without tracing execution path
- Assuming subsystem X is slow without measuring
- Explaining hook behavior, gate firing, or claim validation from plausible code paths rather than the actual artifact

**Core epistemic discipline**: Inspect the artifact (telemetry, trace, log) before forming a conclusion about mechanism or enforcement behavior. Code-path plausibility is not evidence.

---

## Phase 2: Evidence Collection

**System Instrumentation**: Phase 2 leverages hooks/skills-specific observables:
- Tool events (Skill invocations, Read/Write/Edit calls)
- Hook execution state (enabled/disabled, execution counts)
- State artifacts (skill_invocations.jsonl, hook state files)

---

## Step 1.85: Runtime State Inspection (CONDITIONAL - Silent Failures Only)

**When there is no visible error but the feature "doesn't work", inspect live runtime state before theorizing.**

**Trigger Conditions** (MANDATORY inspection when ALL are true):
- No error message shown
- No exception/traceback visible
- User reports "doesn't work" or "not working"
- Feature appears to execute silently

**Cross-Platform State Inspection** (Python-based for Windows compatibility):

```bash
# Use the cross-platform Python tool
python $CLAUDE_ROOT/skills\rca\tools\inspect_runtime_state.py --analyze

# Or import and use programmatically
from P:.claude.skills.rca.tools.inspect_runtime_state import inspect_runtime_state
results = inspect_runtime_state()
```

**Skill Invocation Verification** (NEW in v2.8):

```bash
# Show last 5 skill invocations
python $CLAUDE_ROOT/skills\rca\tools\show_skill_invocations.py --limit 5

# Filter by session
python $CLAUDE_ROOT/skills\rca\tools\show_skill_invocations.py --session-id console_abc123
```

**What the tool inspects**:
1. **Session/Terminal State**: CLAUDE_SESSION_ID, CLAUDE_TERMINAL_ID, session files
2. **Pending Intents**: Command intent files, terminal IDs in intents
3. **Hook Logs**: Hook diagnostics availability, log files
4. **Evidence Store**: Database availability and size

**Error Handling**:
- Missing files -> Reported as "not_found" (graceful degradation)
- Corrupted JSON -> Reported as "invalid_json" with first 500 bytes for diagnosis
- Permission errors -> Reported as "permission_denied"

**State Analysis Patterns** (automatically detected by --analyze flag):

**Pattern 1: Terminal ID Mismatch**
- Check: Intent file terminal_id vs environment variable
- Root cause: CLAUDE_TERMINAL_ID not set, PID-based fallback fails
- Fix: Set CLAUDE_TERMINAL_ID in UserPromptSubmit hook

**Pattern 2: Stale State Files**
- Check: File count >10 indicates stale cleanup
- Root cause: Session cleanup not running, TTL not enforced
- Fix: Implement TTL enforcement in intent reading

**Pattern 3: Hook Chain Break**
- Check: Hook diagnostics show which hooks processed
- Root cause: Exception suppressed, stderr treated as error
- Fix: Add error logging to hook chain

**Evidence Tier**: Runtime state inspection = Tier 3 (85% confidence ceiling)

---

## Step 1.9: Hypothesis Generation with Tree-of-Thought

**MANDATORY after multi-angle search:** Generate 3-7 competing hypotheses enhanced with Tree-of-Thought branching analysis.

See `references/cognitive-stack-and-tot.md` for full ToT integration details.

**Quick process:**
1. Generate ToT branches using BranchGenerator
2. Score each hypothesis: Reproducibility(0.3) x Recency(0.2) x Impact(0.5)
3. Prune unlikely hypotheses (score < 0.3)
4. Rank by score (highest first)
5. Document in hypothesis ranking table
6. Test hypotheses in order (stop at root cause)

---

## Step 2: Trace Real Path with Symbol-Level Data Flow

**Use Serena MCP for precise flow tracing:**
- `find_symbol()` - Find function/class definitions
- `find_referencing_symbols()` - Find all callers
- Trace the actual execution path, not assumed path

## Step 2.5: Find First Divergence

**The earliest mismatch from expected behavior is the highest-leverage fix point.**
- Where did actual behavior diverge from expected?
- What code path produced the unexpected result?

## Step 2.85: Convergence Gate Check

**MANDATORY before declaring root cause:** Verify all 7 convergence gates pass.
See `references/verification-gates.md` for full details.

---

## Steps 3-9: Investigation Principles

| Step | Principle | Description |
|------|-----------|-------------|
| **3** | Change One Variable at a Time | Isolate causes, verify effect before next change |
| **4** | Prefer Instrumentation Over Intuition | Add logs/probes/counters, use actual data |
| **5** | Minimize and Reproduce | Build smallest reliable repro |
| **6** | Validate Interfaces Explicitly | Most bugs are boundary bugs |
| **7** | Fix Structure Before Safeguards | Correct flow first, then add guards |
| **8** | Verify on the Failure Path | Test where it broke, check regressions |
| **9** | Capture the Lesson | Convert root cause into guardrail, add to CKS |
