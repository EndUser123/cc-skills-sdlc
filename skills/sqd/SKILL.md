---
name: sqd
description: "Combined quality orchestration for /q strategic review, /r deterministic refinement, and /qr combined routing with /rns output"
version: 2.1.0
status: stable
category: quality
enforcement: advisory
triggers:
  - /sqd
  - /qr
  - /sqd --strategic-only
  - /sqd --refine-only
aliases:
  - /sqd
  - /qr

suggest:
  - /sqa
  - /s
  - /rns

depends_on_skills: []
workflow_steps:
  - auto_route: QR0 - Detect scope and select applicable checks
  - strategic_checks: QR1 - Run strategic quality with GoT+ToT enhancement
  - deterministic_checks: QR2 - Run deterministic refinement (omissions, plan validation)
  - synthesize: QR3 - Merge findings with GoT analysis, assess health
  - render_output: QR4 - Produce /rns-formatted output
  - decide_next: QR5 - Escalation decisions (/s, /p, /rns)

parameters:
  - name: mode
    description: "Run specific mode: strategic-only, refine-only, or full (auto)"
    type: string
    required: false
  - name: target
    description: "Target path or topic to analyze"
    type: string
    required: false

test_prompts:
  - description: "Full intelligent pipeline"
    prompt: "/sqd"
    expected_behavior: "Auto-detects scope, runs applicable strategic+deterministic checks, outputs /rns-formatted findings"
  - description: "Combined router compatibility"
    prompt: "/qr"
    expected_behavior: "Runs the same combined pipeline as /sqd, preserving /q, /r, and /qr behavior in one skill"
  - description: "Strategic only"
    prompt: "/sqd --strategic-only"
    expected_behavior: "Runs only the strategic /q review path with GoT/ToT enhancement, skips deterministic refinement"
  - description: "Refine only"
    prompt: "/sqd --refine-only"
    expected_behavior: "Runs only the deterministic /r refinement path (omissions, plan validation), skips strategic analysis"

do_not:
  - use "lock ordering" or "enterprise-grade" patterns
  - suggest background services or real-time metrics
  - suggest autonomous execution or self-healing
  - require team approval
  - recommend re-running /sqd as a next step (validation loops waste time)
  - run all checks regardless - use intelligent routing

---

# /sqd - Intelligent Quality Orchestration (v2.1)

## Purpose

**Intelligent quality orchestration** that combines the merged behavior of `/q`, `/r`, and `/qr` with auto-routing to skip unnecessary work.

**What it does:**
- Auto-detects scope and runs only applicable checks
- Strategic `/q` path: architecture soundness, design patterns, technology fit with GoT+ToT reasoning
- Deterministic `/r` path: omissions, plan validation, improvements
- Combined `/qr` path: runs both lanes, merges findings, and emits one `/rns` output
- Outputs /rns-formatted actions

**This skill absorbs /q, /r, and /qr**:
- QR1 = Strategic checks (formerly /q)
- QR2 = Deterministic checks (formerly /r)
- GoT+ToT enhancement integrated into QR1/QR3

**Scope boundary:**
- `/sqd` = Intelligent strategic + deterministic quality
- `/qr` = Combined compatibility entrypoint for the same pipeline
- `/sqa` = Code-focused 8-layer pipeline (syntax, semantic, structural, etc.)
- `/arch` = Architecture decisions and routing
- `/p` = Tactical implementation quality

**Anti-pattern:** Don't use `/sqd` for tactical implementation bugs. That's `/p`'s job.

## Graph-of-Thought (GoT) Integration

**Automatic in QR1/QR3 when strategic checks run:**

### GoT Requirement Constraint Extraction

Automatically extract and categorize requirement constraints from strategic findings:

**Node Types Extracted:**
- **Requirements**: Functional needs ("Must authenticate users", "API response < 200ms")
- **Constraints**: Limitations ("Must use PostgreSQL", "Budget < $X", "Timeline < 2 weeks")
- **Ideas**: Design approaches ("Use Redis for caching", "Implement OAuth 2.0")
- **Risks**: Strategic concerns ("OAuth latency", "Cache complexity", "Migration risk")
- **Components**: System boundaries ("Service A", "Database B", "Cache C")
- **Data flows**: Communication paths ("API → Service → Database")

**Relationship Types Detected:**
- **Supports**: One requirement enables another
- **Contradicts**: One requirement conflicts with another
- **Depends**: One requirement requires another
- **Unrelated**: No direct relationship

### GoT Cycle Detection

Warns about circular requirement dependencies that would cause implementation deadlock.

**Opt-out:** `export SQD_NO_GOT=true`

## Tree-of-Thought (ToT) Integration

**Automatic in QR1 subagent analysis:**

### ToT Question Branching

Automatically generate branching scenarios for strategic quality questions:

**Branch Types:**
- **Architecture Analysis**: sure/maybe/unlikely for layer separation
- **Design Pattern**: sure/maybe/unlikely for pattern appropriateness
- **Technology Fit**: sure/maybe/unlikely for tool selection

**Opt-out:** `export SQD_NO_TOT=true`

## Auto-Routing Logic

**QR0: Scope Detection determines which checks run:**

| Condition | Strategic Checks | Deterministic Checks |
|-----------|------------------|---------------------|
| Architecture/migration scope | ✓ | ✓ |
| New feature implementation | ✓ | ✓ |
| Bug fix only | ✗ | ✓ (omissions) |
| Documentation only | ✗ | ✓ (completeness) |
| Plan review only | ✓ | ✓ |
| Code review only | ✓ | ✓ |

**Override flags:**
- `--strategic-only`: Force strategic checks only
- `--refine-only`: Force deterministic checks only
- No flag: Auto-route based on scope detection

## Your Workflow

### QR0: Auto-Route (Scope Detection)

Detect what we're analyzing:

```python
# Scope detection signals
has_architecture = any(
    signal in prompt.lower()
    for signal in ["architecture", "design", "structure", "layer", "boundary"]
)
has_plan = any(
    signal in prompt.lower()
    for signal in ["plan", "spec", "requirement", "implementation"]
)
has_code = any(
    signal in prompt.lower()
    for signal in ["code", "implement", "function", "class", "file"]
)
is_bug_fix = any(
    signal in prompt.lower()
    for signal in ["bug", "fix", "error", "broken", "fail"]
)

# Route to applicable checks
run_strategic = has_architecture or has_plan or (has_code and not is_bug_fix)
run_deterministic = True  # Always useful for omissions
```

## Test Selection Contract

Choose the smallest sufficient test mix for the target:

- Use **unit tests** for pure logic, local invariants, and deterministic transforms.
- Use **regression tests** for exact bug paths, restored behavior, and fixes that must not recur.
- Use **integration tests** for boundaries, state, persistence, hooks, cross-module flows, or I/O that unit tests can mock away.
- Use **smoke proofs** for hooks, routers, resumable workflows, and workflow-infrastructure boundaries.
- Use **snapshot tests** for rendered quality reports, generated docs, hook-injected text, and skill bodies; use unit tests for the logic that produces that output.
- If the issue is mostly local logic, start at unit level and only escalate when a boundary exists.
- If the issue crosses a boundary or state, do not stop at unit tests.
- Before rendering advice, say which layer proves what and what a lower layer would miss.

### QR1: Strategic Checks (if routed)

Run 4 parallel subagents via Agent tool, preserving the old `/q` behavior:
1. **Architecture & Structure**: Layer separation, module boundaries, coupling
2. **Design Patterns & Domain**: Pattern usage, anti-patterns, domain logic
3. **Technology Fit & Engineering Balance**: Right tools, over/under-engineering
4. **Library Strategy**: Existing solutions, stdlib, codebase patterns

**GoT Integration (QR1 → QR3):**
- Normalize findings from all subagents
- GotPlanner extracts constraint nodes from findings
- GotEdgeAnalyzer detects relationships between constraints
- Cycle detection warns about circular dependencies

Synthesize findings, assess health (Sound/Concerning/Critical).

### QR2: Deterministic Checks (if routed)

Run applicable checks, preserving the old `/r` behavior:
- **Omission checklist**: Build from context/session activity
- **Scope classification**: trivial|moderate|significant|major
- **DUF-derived checks**: Distributed, Undoable, Fault-tolerant properties
- **SRPI protocol**: Searched? Read? Planned? Minimal?
- **Library-first**: Existing solutions, stdlib, codebase patterns
- **Plan validation**: If plan intent present
- **Standards audit**: If metadata in scope
- **Value completeness**: List excluded items, assign HIGH|MEDIUM|LOW

### QR3: Synthesize

Merge strategic and deterministic findings:
- Dedupe by (file, line, category)
- Resolve severity conflicts
- Detect consensus (2+ checks agree)
- **GoT Analysis**: Extract requirement constraints, detect relationships, identify cycles
- Generate deterministic improvements

**GoT Output Example:**
```
GoT Analysis: Requirement Constraints
======================================
Nodes extracted: 8
  - Requirements: 2 (Must authenticate users, API response < 200ms)
  - Constraints: 3 (Must use PostgreSQL, Budget < $X, Timeline < 2 weeks)
  - Ideas: 2 (Use Redis for caching, Implement OAuth 2.0)
  - Risks: 1 (OAuth latency concern)
Relationships detected: 5
  - Supports: 3 pairs
  - Contradicts: 1 pair (JWT vs Stateful sessions - CONFLICT)
  - Depends: 1 pair
Cycles detected: 0
Strategic Health: CONCERNING
Reason: Constraint conflict detected
```

### QR4: Render Output

**Always output /rns format:**

```
1 🔧 QUALITY (N)
  1a [recover/high] ...
  1b [prevent/med] ...

2 📄 DOCS (N)
  2a [realize/low] ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

0 — Do ALL Recommended Next Steps (N items)
```

### QR5: Decide Next

Emit escalation decision:
- `escalate_to_s: yes/no + reason` (if architecture/migration scope)
- `suggest_sqa: yes/no` (if code quality issues found)
- `next_commands: [/arch, /planning, /rns, /p, /sqa]`

## Escalation Rules

Set `escalate_to_s: yes` when:
- Architecture/migration/rewrite scope is implied
- Multiple high-risk signals are present
- Deterministic pass has low confidence or conflicting tradeoffs
- GoT analysis detects requirement conflicts

Suggest `/sqa` when:
- Code quality issues are found (syntax, semantic, structural)
- Test coverage gaps detected
- Implementation verification needed

## Backward Compatibility

Legacy shorthands still work:
- `/q` → Strategic `/q` path, now routed through the combined `/sqd` skill
- `/r` → Deterministic `/r` path, now routed through the combined `/sqd` skill
- `/qr` → Combined intelligent pipeline
- `/sqd` → Full intelligent pipeline
- `/sqd1` or `/sqd --strategic-only` → Strategic checks only
- `/sqd2` or `/sqd --refine-only` → Deterministic checks only

## What This Does NOT Do

- Does NOT check tactical implementation (tests, lint, bugs) — that's `/p` or `/sqa`
- Does NOT check for omissions in isolation — that's what deterministic checks are for
- Does NOT HALT — errors degrade gracefully
- Does NOT recommend re-running itself — user controls validation cadence
- Does NOT run all checks regardless — uses intelligent routing
