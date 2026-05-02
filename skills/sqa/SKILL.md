---
name: sqa
description: Unified SQA Orchestrator — 11-layer Software Quality Assurance model (Checklist→Predictive→Syntactic→Semantic→Structural→Requirements→Security→Performance→Operational→E2E→Meta→Contracts) with contract-integrity, Contract Authority Packet alignment, and resume-integrity certification
version: 2.1.0
status: stable
category: quality
triggers:
  - /sqa
suggest:
  - /qr
entry_type: skill
requires_target: false
enforcement: strict
workflow_steps:
  - L0_CHECKLIST
  - L0_PREDICTIVE
  - L1_SYNTACTIC
  - L2_SEMANTIC
  - L3_STRUCTURAL
  - L4_REQUIREMENTS
  - L5_SECURITY
  - L6_PERFORMANCE
  - L7_OPERATIONAL
  - L8_E2E
  - L8_META_SYNTHESIS
  - L9_CONTRACTS
# Extensions to SKILL_SCHEMA (not enumerated in schema):
#   version: skill version string
#   status: stable|experimental|deprecated
#   entry_type: skill|agent|hook
#   requires_target: true|false (auto-detect behavior)
#   enforcement: strict|advisory|none
---

# /sqa — Unified SQA Orchestrator

Execute an 11-layer sequential quality analysis pipeline against a target codebase.

For workflow infrastructure, SQA must certify contract integrity, resume integrity, and stale-data immunity, not just generic quality.

## Usage

```
/sqa <target-path>               # explicit target
/sqa                             # auto-detect target via semantic intent resolution
/sqa --layer=N                   # run specific layer only (0-9, META, CONTRACTS)
/sqa --focus <lens>              # apply focus lens (see Focus Lenses below)
/sqa --halt-on <severity>        # halt after layer if findings exceed threshold (default: HIGH)
/sqa --fix                       # auto-fix safe issues in L1/L2 (formatting, imports, lint)
/sqa --dry-run                   # detection-only: report what would run without executing
/sqa --evidence                  # write structured JSON results to terminal-isolated path
/sqa --quick                     # only analyze files from current session context
```

**`--halt-on` severity threshold:**
| Value | Behavior |
|-------|----------|
| `HIGH` | **(default)** Halt after a layer if any HIGH or CRITICAL findings exist |
| `CRITICAL` | Halt only on CRITICAL findings |
| `MEDIUM` | Halt on MEDIUM, HIGH, or CRITICAL |
| `NONE` | Run all layers regardless — collect all findings |

**Focus lenses** (same as `/p` `--focus`):
| Lens | Effect |
|------|--------|
| `risk` | Pre-mortem failure mode analysis |
| `gaps` | Completeness check — missing items, unhandled cases |
| `opportunities` | Optimization and value identification |
| `security` | Prioritize adversarial-security and path traversal |
| `complexity` | Flag high-cyclomatic-complexity functions |
| `duplicates` | Run duplicate detection |
| `quality` | Emphasize code smells and conventions |
| `performance` | Run with profiling awareness |
| `architecture` | Architectural perspective and cross-module deps |
| `test` | Focus on test quality and coverage gaps |
| `library` | Dependency analysis and CVE checks |
| `comprehensive` | ALL lenses elevated to blocking |

### Auto-Detect Target (if no argument provided)

Resolve target via semantic intent, not archaeology:

1. **Named outputs** (highest priority): If user references a named output from conversation (e.g., "sqa the hook system we built") → use that
2. **Active task context**: If `/code` or `/planning` was recently running → the feature/plan they were working on
3. **Conversation semantic**: What were we discussing when `/sqa` was invoked? What was just implemented or modified?
4. **Recent changes as fallback**: Files modified in last 5-10 turns — weight by semantic relevance, not recency alone
5. **Only ask if genuinely ambiguous**: When >3 semantically-distinct targets exist with no clear intent signal

State assumption: "Certifying [X] — assumption based on [signal]. Correct?" Only prompt for confirmation if intent is unclear.

**Phase/State Detection** (optional smart routing — implement if needed):

| Signal | Layer |
|--------|-------|
| No tests or tests failing | L1 SYNTACTIC + L2 SEMANTIC |
| Tests pass, never reviewed | L3 STRUCTURAL |
| Reviewed, files changed since | L3 STRUCTURAL (re-review) |
| Reviewed, never validated | L7 OPERATIONAL |
| All complete, no changes | Report "Ready" |

**Focus lenses** propagate to Agent-based layers (L0, L5, L6) adjusting agent priority and confidence thresholds.

## Layers

| Layer | Name | Tool | Dispatch | Hard Dependency |
|-------|------|------|---------|----------------|
| 0 | CHECKLIST | Fast-fail config/structure check (from /verify Tier 0) | Python/CLI | — |
| 0 | PREDICTIVE | 16 adversarial specialists (conditional invocation based on target characteristics) | **Agent** (skill-level dispatch only — Python layer returns empty list) | L0_CHECKLIST |
| 1 | SYNTACTIC | ruff, mypy, AI Distiller | Python/CLI | — |
| 2 | SEMANTIC | verify (pytest), diagnose | Python/CLI | — |
| 3 | STRUCTURAL | meta-review, harden, apply_safety_patterns | Python/CLI | — |
| 4 | REQUIREMENTS | gto, spec-compliance | Python/CLI | Layer 2 |
| 5 | SECURITY | adversarial-security, path traversal check, data-safety-vcs, CVE/API deprecation scan | **Agent** + Python/CLI (dispatch via Agent tool, not subprocess) | — |
| 6 | PERFORMANCE | perf, adversarial-performance | **Agent** + CLI (dispatch via Agent tool, not subprocess) | — |
| 7 | OPERATIONAL | verify (hook chain), hook-audit, hook-inventory, recursive_failure_detector | Python/CLI | — |
| 8 | E2E | Actual skill/workflow invocation (from /verify Tier 3) | Agent/CLI | — |
| META | META-SYNTHESIS | consensus detection, blind-spot detection, evidence quality | Python | All |
| 9 | CONTRACTS | Contract integrity check (from /verify Contract Check) | Python/CLI | META |

### Execution Model

**The LLM is the conductor.** SKILL.md is the score — I execute the workflow by:

1. **Validate target** via `_validate_target()` utility
2. **Run L0_CHECKLIST** (fast-fail pre-check) — if fails, halt immediately
3. **Dispatch Agent-based layers** via Agent tool (file-based handoff, not inline findings):
   - L0 (PREDICTIVE): Dispatch 7 specialists in parallel via Agent tool (run_in_background=True), each writing JSON to session file. After all complete, dispatch `adversarial-critic` for synthesis.
   - L5 (SECURITY): Dispatch `Agent('adversarial-security')` with file output; run path traversal check via Python utility
   - L6 (PERFORMANCE): Dispatch `Agent('adversarial-performance')` with file output; run perf checks via Python utility
4. **Run Python/CLI layers** via Bash subprocess:
   - L1 (SYNTACTIC): `ruff check`, `mypy`
   - L2 (SEMANTIC): `verify` (pytest), `diagnose`
   - L3 (STRUCTURAL): `meta-review`, `harden`, `apply_safety_patterns`
   - L4 (REQUIREMENTS): `gto`, `spec-compliance` — SKIP if L2 had failures
   - L7 (OPERATIONAL): `hook-audit`, `hook-inventory`, `recursive_failure_detector`
5. **Run L8_E2E** — Actual skill/workflow invocation verification
6. **Synthesize META** — consensus detection, blind-spot detection, evidence quality
7. **Run L9_CONTRACTS** — Contract integrity check (producer/consumer boundary proof)

**Orchestrator.py** is a **pure utilities module** — it provides `_validate_target`, `_atomic_write`, `L2State`, `SQAReport`, `save_report`. It contains **no orchestration logic**. Do not run `orchestrator.py` directly.

## Test Selection Contract

Choose the smallest sufficient test mix for the target and layer:

- Use **unit tests** for pure logic, local invariants, and deterministic transforms.
- Use **regression tests** for exact bug paths, restored behavior, and fixes that must not recur.
- Use **integration tests** for boundaries, state, persistence, hooks, cross-module flows, or I/O that unit tests can mock away.
- Use **smoke proofs** for hooks, routers, resumable workflows, and workflow-infrastructure boundaries.
- Use **snapshot tests** for rendered reports, generated docs, hook-injected text, and skill bodies; use unit tests for the logic that produces that output.
- If a defect can be falsified by a smaller layer, do not jump to a larger one.
- If a defect crosses a boundary or state, do not stop at unit tests.
- Before presenting a plan, say which layer proves what and what a lower layer would miss.

### Findings Accumulation Model

**IMPORTANT:** Findings from each layer are accumulated and presented in RNS format only when a halt condition is triggered or when the skill completes. This prevents presentation noise on clean layers while ensuring no findings are lost.

**Accumulation Rules:**
1. After each layer completes, findings are added to the accumulated list via `add_findings(layer, findings)`
2. If a layer triggers halt, ALL accumulated findings (current layer + all prior non-halted layers) are presented in RNS format
3. If no halt occurs, findings continue accumulating
4. On skill completion, ALL accumulated findings are presented in RNS format

**RNS Presentation Triggers:**
- `[HALT CHECK]` after any layer → Present ALL accumulated findings in RNS format, then stop
- Final step completion (Step 12) → Present ALL accumulated findings in RNS format

## Your Workflow

When /sqa is invoked:

### Step 0: Validate Target
Run `_validate_target()` utility to ensure path exists, is not symlink, within allowed roots.
Initialize state: `from sqa_state_tracker import init_state; state = init_state(target, halt_on="HIGH")`

### Step 0a: L0_CHECKLIST (Fast-Fail Pre-Check)
Run fast-fail structural verification to catch configuration/structure issues before expensive analysis.

**Checklist verification** (from /verify Tier 0):
- For skills: SKILL.md exists, valid frontmatter, required fields present
- For hooks: Hook file exists, valid registration, required dependencies available
- For features: Plan artifact exists, workflow steps defined, acceptance criteria present
- For code: File exists, valid syntax, imports resolvable

Run via Python utility or subprocess:
```bash
python -c "
from pathlib import Path
from sqa_checklist import run_checklist
result = run_checklist(target)
print(result.json_output())
"
```

**Fast-fail behavior**: If L0_CHECKLIST fails, halt immediately with finding. No need to run expensive L0_PREDICTIVE or deeper layers on broken targets.

Record completion: `record_layer_complete("L0_CHECKLIST", findings=N, pass_fail=result.passed)`

### [HALT CHECK] After Step 0a
If L0_CHECKLIST fails: EMIT `[HALT]`, run `record_halt("L0_CHECKLIST")`, present findings in RNS format, and stop.

### Step 1: PREDICTIVE (Optional - skip for fast-path)

**Phase 1a: Determine applicable specialists**

All 16 adversarial specialists are available, but only relevant ones run based on target characteristics:

| Specialist | Runs When | Applicability Criteria |
|------------|-----------|----------------------|
| adversarial-logic | Always | Pure logic errors (off-by-one, wrong operators, inverted conditionals) |
| adversarial-quality | Always | Code smells, technical debt, maintainability risks, over/under-engineering |
| adversarial-io-validation | Always | File operations, path validation, external I/O assumptions |
| adversarial-security | Always | Data leaks, access control gaps, encryption issues |
| adversarial-performance | Always | Timeouts, bottlenecks, N+1 patterns |
| adversarial-testing | Always | Missing scenarios, brittle tests, coverage gaps |
| adversarial-state-machine | When stateful | State transitions, lifecycle management, status fields |
| **adversarial-compliance** | When specs exist | Has `.adr/`, `requirements/`, `api.yaml`, `openapi.json`, formal contracts |
| **adversarial-failure-modes** | When complex | >100 files OR state/data management OR critical infrastructure |
| **adversarial-invariants** | When entities | Has entity-like code OR database/ORM usage OR data models |
| **adversarial-qa** | When tested | Has `tests/` directory |
| **adversarial-domain-patterns** | Always | Domain-specific best practices, patterns via /all (wiki+CKS+web) |
| **adversarial-tech-fit** | When complex | Technology choice validation vs problem domain |
| **adversarial-library-strategy** | Always | CVE detection, deprecated API detection, modern alternatives |
| adversarial-review | Fallback | General adversarial review if no specific criteria apply |

**Quick-path detection:**
```python
from pathlib import Path

target_path = Path(target)

# Detect characteristics
has_specs = any(
    (target_path / d).exists()
    for d in [".adr", "requirements", "docs/specs", "api.yaml", "openapi.json"]
)
has_tests = (target_path / "tests").exists()
has_entities = any(
    any(f.name.endswith(".py") for f in (target_path / d).glob("*.py")[:5])
    for d in ["core", "models", "entities", "schema"]
) if (target_path / "core").exists() else False
is_complex = sum(1 for _ in target_path.rglob("*.py")) > 100
has_state = any(
    "state" in f.name.lower() or "status" in f.name.lower()
    for f in target_path.rglob("*.py")[:20]
)  # sample first 20 files

# Build specialist list
specialists = [
    "adversarial-logic",      # always
    "adversarial-quality",    # always (now includes under-engineering detection)
    "adversarial-io-validation",  # always
    "adversarial-security",   # always
    "adversarial-performance",  # always
    "adversarial-testing",    # always
    "adversarial-domain-patterns",  # always - uses /all for wiki+CKS+web search
    "adversarial-library-strategy",  # always - CVE and deprecated API detection
]

if has_state:
    specialists.append("adversarial-state-machine")
if has_specs:
    specialists.append("adversarial-compliance")
if is_complex or has_state:
    specialists.append("adversarial-failure-modes")
    specialists.append("adversarial-tech-fit")  # technology fit assessment for complex systems
if has_entities:
    specialists.append("adversarial-invariants")
if has_tests:
    specialists.append("adversarial-qa")
```

**New Specialist Descriptions:**

| Specialist | Purpose | Implementation |
|------------|---------|----------------|
| **adversarial-domain-patterns** | Domain-specific best practices via unified search | Uses `/all` to search wiki, CKS, and web for industry patterns relevant to target codebase |
| **adversarial-tech-fit** | Technology choice validation | Evaluates whether chosen technology stack fits problem domain (only runs for complex systems) |
| **adversarial-library-strategy** | CVE and deprecated API detection | Scans dependencies for known vulnerabilities, deprecated APIs, and suggests modern alternatives |
| **adversarial-quality (enhanced)** | Over AND under-engineering detection | Now includes detection of missing abstractions, hardcoded values, and insufficient error handling |

**Domain Pattern Search Integration (/all):**

The `adversarial-domain-patterns` specialist uses `/all` to query multiple sources for domain-specific best practices:

```python
# During specialist dispatch, the domain-patterns specialist receives:
domain_query = f"Best practices and patterns for {detected_domain} architecture, anti-patterns, common pitfalls"

# The specialist then uses /all to search:
# 1. Wiki (P:/__csf/docs/, .adr/)
# 2. CKS (Constitutional Knowledge System)
# 3. Web (current documentation, industry standards)

# Results are merged and ranked by relevance, then applied to findings
```

**Technology Fit Assessment:**

The `adversarial-tech-fit` specialist (activated for complex systems) evaluates:
- Technology choice vs problem domain match
- Framework/library appropriateness
- Scalability concerns given chosen stack
- Known limitations of chosen technologies in target use case

**CVE and Deprecated API Detection:**

The `adversarial-library-strategy` specialist checks:
1. **Python:** `datetime.utcnow`, `asyncio.ensure_future` without context, deprecated stdlib modules
2. **Dependencies:** Known CVEs via pyup.io/snyk (for requirements.txt/pyproject.toml)
3. **Node.js:** npm audit results, deprecated packages
4. **General:** Outdated major versions with known security issues

**Under-Engineering Detection:**

The enhanced `adversarial-quality` specialist now detects:
- Missing abstraction layers (copy-paste code, repetitive patterns)
- Hardcoded configuration values (no environment variables)
- Insufficient error handling (bare except, generic exceptions)
- Missing input validation (user data used without sanitization)
- Inadequate logging for production systems

**Phase 1b: Parallel specialist dispatch via Agent tool**

Create session directory and dispatch manifest, then launch applicable specialists in parallel:

```python
import uuid, json
from pathlib import Path

session_id = uuid.uuid4().hex[:8]
sqa_dir = Path(f"P:/.claude/.evidence/sqa/{session_id}")
sqa_dir.mkdir(parents=True, exist_ok=True)
(sqa_dir / "specialists").mkdir(exist_ok=True)

# Dispatch manifest (idempotent — re-run skips already-dispatched specialists)
manifest_path = sqa_dir / "specialists" / "dispatch_manifest.json"

# Load prior dispatched from any interrupted run
dispatched = []
if manifest_path.exists():
    dispatched = json.loads(manifest_path.read_text()).get("dispatched", [])

# Dispatch specialists in parallel (sequential Agent calls = concurrent execution)
for specialist in specialists:
    if specialist not in dispatched:
        Agent(
            subagent_type="general-purpose",
            description=f"L0 {specialist} analysis",
            prompt=f"Read P:/.claude/agents/{specialist}.md and follow its instructions to review <target>. Write JSON findings to: {sqa_dir}/specialists/{specialist}-findings.json. Return ONLY the file path."
        )
        dispatched.append(specialist)
        manifest_path.write_text(json.dumps({"dispatched": dispatched, "session_id": session_id}))
```

**Each specialist:**
- Reads its agent definition from `P:/.claude/agents/{specialist}.md`
- Writes JSON findings to `{sqa_dir}/specialists/{specialist}-findings.json`
- Returns ONLY the file path (not inline findings)

**Phase 1b: Automatic wait loop with structured progress**

After launching all specialists, wait programmatically for completion. Emits machine-readable JSON events to stderr (captured in skill execution logs). Never prompts user to re-run.

```python
import time, json, sys
from pathlib import Path
from lib.sqa_state_tracker import record_layer_complete

SPECIALIST_TIMEOUT = 300  # 5 minutes max wait
CHECK_INTERVAL_BASE = 10  # seconds, exponential backoff
CHECK_INTERVAL_MAX = 60

def _emit(event: dict):
    """Emit machine-readable JSON event to stderr."""
    print(json.dumps(event), file=sys.stderr, flush=True)

def _wait_for_specialists(sqa_dir, dispatched, timeout=SPECIALIST_TIMEOUT):
    """Programmatic wait loop — no user prompts, no "re-run" text."""
    start = time.monotonic()
    interval = CHECK_INTERVAL_BASE
    completed = set()

    # Load prior completions if any (idempotent resume)
    manifest = json.loads((sqa_dir / "specialists" / "dispatch_manifest.json").read_text())
    prior_completed = manifest.get("completed", [])
    completed.update(prior_completed)

    while time.monotonic() - start < timeout:
        # Check which specialists have written valid JSON
        available = []
        for specialist in dispatched:
            json_path = sqa_dir / "specialists" / f"{specialist}-findings.json"
            if json_path.exists():
                try:
                    data = json.loads(json_path.read_text())
                    if specialist not in completed:
                        elapsed = int(time.monotonic() - start)
                        _emit({
                            "event": "specialist_complete",
                            "name": specialist,
                            "elapsed_s": elapsed,
                        })
                        completed.add(specialist)
                    available.append(specialist)
                except (json.JSONDecodeError, OSError):
                    pass  # Incomplete file, wait

        _emit({
            "event": "progress",
            "completed": len(completed),
            "total": len(dispatched),
            "running": [s for s in dispatched if s not in completed],
            "elapsed_s": int(time.monotonic() - start),
        })

        if len(available) == len(dispatched) and available:
            _emit({"event": "all_specialists_complete", "total": len(dispatched)})
            # Update manifest with completion list
            manifest["completed"] = list(completed)
            (sqa_dir / "specialists" / "dispatch_manifest.json").write_text(
                json.dumps(manifest)
            )
            return list(completed)

        # Exponential backoff: 10, 20, 40, 60 (cap)
        time.sleep(interval)
        interval = min(interval * 2, CHECK_INTERVAL_MAX)

    # Timeout — partial results still usable
    _emit({
        "event": "specialist_timeout",
        "completed": list(completed),
        "missing": [s for s in dispatched if s not in completed],
    })
    return list(completed)

completed = _wait_for_specialists(sqa_dir, dispatched)
print(f"L0 PREDICTIVE: {len(completed)}/{len(dispatched)} specialists completed.", flush=True)
```

**Phase 1c: Failure-mode prompts (internal)**

Before synthesizing, run this internal check against the specialist findings:

```
Internal failure-mode check:
- What is the most plausible way this target still fails even if the happy path passes?
- What am I treating as safe because the producer succeeds, even though the consumer could still fail?
- What hidden assumption would most likely break under stale data, workflow interruption, or multi-terminal use?
- What blind spot is shared across multiple specialists rather than isolated to one agent?
- What risk am I underweighting because it is operational, temporal, or only appears on resume/handoff?
```

**Phase 1d: Gate handled by wait loop**

The `_wait_for_specialists()` call in Phase 1b already validates all JSONs before returning. If it returns, all specialists completed or timeout was reached with partial results.

**Phase 1e: Critic synthesis**

After all specialist JSONs are available, dispatch `adversarial-critic` to synthesize:

```python
Agent('adversarial-critic', prompt=f"Read all {len(dispatched)} dispatched specialist JSONs in {sqa_dir}/specialists/. Synthesize into a unified L0 findings list: dedupe by (file, line, category), resolve severity conflicts, detect consensus (2+ specialists agree). Write synthesis to {sqa_dir}/L0_synthesis.json.")
```

**Phase 1f: Record L0 completion and accumulate findings**

Load synthesis, count findings, and add to accumulated findings:
```python
from sqa_state_tracker import record_layer_complete, add_findings
synthesis = json.loads((sqa_dir / "L0_synthesis.json").read_text())
findings_list = synthesis.get("consolidated_findings", synthesis.get("findings", []))
record_layer_complete("L0", findings=len(findings_list))
add_findings("L0", findings_list)
```

If fast-path: `record_layer_complete("L0", skipped=True, reason="fast-path")`

### [HALT CHECK] After Step 1
Check if any findings at or above `--halt-on` threshold (default: HIGH):
```python
from sqa_state_tracker import get_rns_summary, record_halt

# Check severity threshold
severity_order = ["CRITICAL", "BLOCKER", "HIGH", "MEDIUM", "LOW"]
threshold_index = severity_order.index(state.halt_on)
for f in findings_list:
    if severity_order.index(f.get("severity", "LOW").upper()) <= threshold_index:
        # Halt triggered - present RNS with ALL accumulated findings
        record_halt("L0")
        print("[HALT] L0 PREDICTIVE exceeded --halt-on threshold")
        
        # Present RNS format
        summary = get_rns_summary()
        for domain, findings in summary["grouped"].items():
            emoji = summary["domain_mapping"].get(domain, "📌")
            print(f"\n{emoji} {domain.upper()} ({len(findings)})")
            for i, f in enumerate(findings, 1):
                sev = f.get("severity", "LOW").upper()
                print(f"  {i}. [{sev}] {f.get('title', f.get('finding_id', ''))}")
        
        sys.exit(1)
```

Otherwise continue to next layer.

### Step 2: SYNTACTIC
Run via Bash subprocess using `layer1_syntactic.py`:
- `ruff check <target>` (via `_run_ruff()`)
- `mypy <target>` (via `_run_mypy()`, if Python)
- `aid distill <target>` (via `_run_aid()`, if available)

**Implementation:** `layers/layer1_syntactic.py:run()` returns structured `Finding` objects directly.

**Exit validation:** Verify exit codes are 0. If not, this is a FAIL even if findings are below halt threshold.

Accumulate findings:
```python
from layers.layer1_syntactic import run as run_l1_syntactic
from sqa_state_tracker import record_layer_complete, add_findings

# Run L1 and get structured findings
findings_list = run_l1_syntactic(Path(target))
record_layer_complete("L1", findings=len(findings_list))
add_findings("L1", findings_list)
```

### [HALT CHECK] After Step 2
Check if findings exceed threshold and present RNS with ALL accumulated findings:
```python
severity_order = ["CRITICAL", "BLOCKER", "HIGH", "MEDIUM", "LOW"]
threshold_index = severity_order.index(state.halt_on)
accumulated = get_accumulated_findings()  # L0 + L1 findings

for f in accumulated:
    if severity_order.index(f.get("severity", "LOW").upper()) <= threshold_index:
        record_halt("L1")
        print("[HALT] L1 SYNTACTIC exceeded --halt-on threshold")
        
        # Present RNS
        summary = get_rns_summary()
        for domain, findings in summary["grouped"].items():
            emoji = summary["domain_mapping"].get(domain, "📌")
            print(f"\n{emoji} {domain.upper()} ({len(findings)})")
            for i, f in enumerate(findings, 1):
                sev = f.get("severity", "LOW").upper()
                print(f"  {i}. [{sev}] {f.get('title', f.get('finding_id', ''))}")
        
        sys.exit(1)
```

If `--fix` was passed, attempt fixes and recheck. Otherwise continue to next layer.

### Step 3: SEMANTIC (TDD BUILD)

**Phase 3a: Test Discovery**
Discover existing test coverage:
```python
import subprocess
from pathlib import Path

result = subprocess.run(
    ["python", "-m", "pytest", "--collect-only", "-q", target],
    capture_output=True,
    text=True,
    timeout=30
)
test_count = len([line for line in result.stdout.split('\n') if "::test_" in line])
print(f"Found {test_count} tests")
```

**Phase 3b: Test Quality Check**
Run pytest with coverage:
```bash
cd <target> && python -m pytest --cov=. --cov-report=term-missing 2>&1 | head -50
```
Check for:
- Coverage percentage below 80%
- Tests with no assertions (empty asserts)
- Tests marked as xfail/skip

**Phase 3c: TDD (if coverage gaps)**
If coverage is insufficient, invoke `/tdd`:
```bash
/tdd <target> --phase=red
```

**Phase 3d: Run Tests**
Verify tests actually pass:
```bash
cd <target> && python -m pytest -v 2>&1 | head -30
```

**Phase 3e: Code Simplification (if tests pass)**
After tests pass, simplify code:
```python
Agent(
    subagent_type="code-simplifier",
    prompt=f"Review and simplify Python code in {target} for clarity, consistency, and maintainability. Focus on recently modified code while preserving all functionality.",
    description="Code simplification review"
)
```

**Note:** `/tdd` is a skill — invoke via Skill tool. `verify` is a skill — invoke via Skill tool. `/fix` functionality is provided by `/code` skill.

**Exit Criteria:**
- All tests pass
- No high-severity test quality issues
- Known bugs fixed with regression tests
- Integration verified

Record completion: `record_layer_complete("L2", findings=N)`

### [HALT CHECK] After Step 3
If findings at or above `--halt-on` threshold (default: HIGH): EMIT `[HALT]`, run `record_halt("L2")`, and stop. Otherwise continue.

### Step 4: STRUCTURAL
Run via Bash subprocess using `layer3_structural.py`:
- `meta-review --analyze=imports <target>` (circular deps)
- `harden --check=guards <target>` (assertion guards)
- `apply_safety_patterns --verify <target>` (safety patterns)

**Implementation:** `layers/layer3_structural.py:run()` returns structured `Finding` objects directly.

# Combine findings
findings = pt_findings['findings'] + ig_findings['findings'] + dc_findings['findings']
```

Record completion: `record_layer_complete("L3", findings=len(findings))`

### [HALT CHECK] After Step 4
If any findings at or above `--halt-on` threshold (default: HIGH): EMIT `[HALT]`, run `record_halt("L3")`, and stop. Otherwise continue.

### Step 5: REQUIREMENTS (skip if L2 had failures)
Run via Bash subprocess:
- `gto <target>`
- `spec-compliance <target>`

Record completion: `record_layer_complete("L4", findings=N)` (or `skipped=True, reason="L2 had failures"` if skipped)

### [HALT CHECK] After Step 5
If any findings at or above `--halt-on` threshold (default: HIGH): EMIT `[HALT]`, run `record_halt("L4")`, and stop. Otherwise continue.

### Step 6: SECURITY
1. Dispatch `Agent('adversarial-security')` via Agent tool
2. Run path traversal check via Python utility
3. Run `data-safety-vcs` for anti-bleed gates
4. **NEW:** CVE and deprecated API scanning via `adversarial-library-strategy` specialist

**CVE/API Deprecation Scan:**
```python
# Collect dependency files (requirements.txt, pyproject.toml, package.json, go.mod)
import subprocess
from pathlib import Path

dep_files = []
for pattern in ["*requirements*.txt", "pyproject.toml", "package.json", "go.mod", "Cargo.toml"]:
    dep_files.extend(Path(target).rglob(pattern))

# For Python: check for known vulnerabilities and deprecated APIs
if dep_files:
    Agent(
        subagent_type="general-purpose",
        description="CVE and deprecated API scanning",
        prompt=f"""Analyze dependencies in {target} for:
1. Known CVE vulnerabilities (check pyup.io, snyk, npm audit for relevant ecosystems)
2. Deprecated API usage (e.g., datetime.utcnow, async coroutines without async/await)
3. Modern alternatives available

Write findings to: {sqa_dir}/L5_cve_api_findings.json"""
    )
```

Record completion: `record_layer_complete("L5", findings=N)`

### [HALT CHECK] After Step 6
If any findings at or above `--halt-on` threshold (default: HIGH): EMIT `[HALT]`, run `record_halt("L5")`, and stop. Otherwise continue.

### Step 7: PERFORMANCE
1. Dispatch `Agent('adversarial-performance')` via Agent tool
2. Run `perf` for ThreadPoolExecutor tracing

Record completion: `record_layer_complete("L6", findings=N)`

### [HALT CHECK] After Step 7
If any findings at or above `--halt-on` threshold (default: HIGH): EMIT `[HALT]`, run `record_halt("L6")`, and stop. Otherwise continue.

### Step 8: OPERATIONAL
Run via Bash subprocess:
- `verify --tier=2 <target>` (hook chain + router)
- `hook-audit <target>`
- `hook-inventory <target>`
- `recursive_failure_detector.py <target>`

Record completion: `record_layer_complete("L7", findings=N)`

### [HALT CHECK] After Step 8
If any findings at or above `--halt-on` threshold (default: HIGH): EMIT `[HALT]`, run `record_halt("L7")`, and stop. Otherwise continue.

### Step 8a: L8_E2E (End-to-End Verification)
Run actual skill/workflow invocation verification (from /verify Tier 3).

**E2E verification** ensures the target works in practice, not just in theory:
- For skills: Invoke the skill with test input, verify expected output
- For hooks: Trigger hook via actual workflow, verify side effects
- For features: Execute the workflow, verify end-to-end behavior
- For code: Run integration tests or manual execution scenarios

Run via appropriate method:
```bash
# For skills
/skill <test-input> --target <target>

# For hooks
bash -c "trigger workflow that exercises hook"

# For code
pytest tests/integration/test_<target>_e2e.py
```

Record completion: `record_layer_complete("L8_E2E", findings=N, pass_fail=result.passed)`

### [HALT CHECK] After Step 8a
If E2E verification fails: EMIT `[HALT]`, run `record_halt("L8_E2E")`, present findings in RNS format, and stop. Otherwise continue.

### Step 9: META-SYNTHESIS
- Consensus detection (2+ layers agree on same file:line:category)
- Blind-spot detection
- Evidence quality check per `evidence-tiers`

Record completion: `record_layer_complete("META", findings=N)`

### Step 10: P6 SECURITY CERTIFICATION
Run explicit security certification gate:

**Security Certification Checklist:**
- [ ] L5 adversarial-security findings: NONE at CRITICAL/HIGH
- [ ] Path traversal check: PASS
- [ ] Anti-bleed gates: VERIFIED
- [ ] Data safety VCS: CLEAN
- [ ] CVE vulnerabilities: NONE at CRITICAL/HIGH
- [ ] Deprecated API usage: NONE or documented migration plan

```python
security_check_pass = (
    l5_critical_high_count == 0 and
    path_traversal_check_passed and
    anti_bleed_gates_verified
)
if not security_check_pass:
    print("[P6 SECURITY CERTIFICATION FAILED]")
    print("Blocking certification until security issues resolved.")
    sys.exit(1)
print("[P6 SECURITY CERTIFICATION PASSED]")
```

### Step 11: P5 QUALITY CERTIFICATION
Issue final quality certification based on health score:

**Certification Thresholds:**
| Health Score | Certification |
|--------------|---------------|
| ≥80 | **CERTIFIED** — Excellent quality |
| 60-79 | **CONDITIONAL** — Address HIGH items |
| 40-59 | **UNSTABLE** — Major issues must be fixed |
| <40 | **REJECTED** — Unsafe for production use |

```python
if health_score >= 80:
    cert = "CERTIFIED"
elif health_score >= 60:
    cert = "CONDITIONAL"
elif health_score >= 40:
    cert = "UNSTABLE"
else:
    cert = "REJECTED"

print(f"[P5 QUALITY CERTIFICATION: {cert}]")
print(f"Health Score: {health_score}")
print(f"Layers Completed: {layers_completed}")

# Final verdict
if cert == "CERTIFIED":
    print("Package is production-ready.")
elif cert == "CONDITIONAL":
    print("Package is usable with known limitations.")
else:
    print("Package requires fixes before use.")
    sys.exit(1)
```

### Step 12: L9_CONTRACTS (Contract Integrity Check)
Run contract integrity check for targets that involve producer/consumer boundaries (from /verify Contract Check).

**Contract verification** ensures that producer and consumer agree on their interface:
- **For handoff/resume targets**: Verify handoff envelope fields, consumer validation, stale rejection
- **For skill/hook targets**: Verify contract primitives are complete and validated
- **For evidence/artifact targets**: Verify producer fields match consumer expectations

**Contract Authority Packet validation** (when present):
- Verify schema version matches expected
- Verify freshness authority is correct
- Verify invalidation semantics are defined
- Verify transcript-vs-artifact precedence is documented

Run via Python utility or manual verification:
```python
from sqa_contracts import verify_contract_integrity
result = verify_contract_integrity(target, contract_authority_packet)
print(result.json_output())
```

**Required proof** (from /verify Contract Check):
1. Producer emits the required fields
2. Consumer explicitly validates or depends on those fields
3. Missing required fields fail in the intended way
4. Stale or superseded artifacts are rejected or invalidated in the intended way
5. Transcript/workspace truth beats stale summary state where applicable

Record completion: `record_layer_complete("L9_CONTRACTS", findings=N, pass_fail=result.passed)`

### [FINAL HALT CHECK]
If L9_CONTRACTS fails or any prior findings remain unaddressed: EMIT `[FINAL HALT]`, present ALL accumulated findings in RNS format, and stop. Otherwise, certification is complete.

### FINAL [HALT CHECK] After Step 11
**Always present RNS with ALL accumulated findings at completion:**

```python
from sqa_state_tracker import get_rns_summary

print("\n" + "="*60)
print("SQA COMPLETE - FINAL RECOMMENDED NEXT STEPS")
print("="*60)

summary = get_rns_summary()
for domain, findings in summary["grouped"].items():
    emoji = summary["domain_mapping"].get(domain, "📌")
    print(f"\n{emoji} {domain.upper()} ({len(findings)})")
    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "LOW").upper()
        print(f"  {i}. [{sev}] {f.get('title', f.get('finding_id', ''))}")

print(f"\n0 — Do ALL Recommended Next Actions ({summary['total']} items)")
print("\n" + "="*60)
print(f"Certification: {cert}")
print(f"Health Score: {health_score}")
print(f"Layers Completed: {layers_completed}")
print("="*60)
```

**RNS is always presented at completion** — even if certification passed. This ensures all findings are visible for remediation planning.

## Target Validation (SEC-001)

Before any subprocess call, the target path is validated:

```python
from pathlib import Path
import os

# Exclude patterns for cache/build/docs/vendored directories
EXCLUDE_PATTERNS = [
    "*/.venv/*",
    "*/__pycache__/*",
    "*/.mypy_cache/*",
    "*/.pytest_cache/*",
    "*/.ruff_cache/*",
    "*/.cache/*",
    "*/node_modules/*",
    "*/.tox/*",
    "*/*.egg-info/*",
    "*/arch_decisions/*",
    "*/docs/*",
]

def _count_python_files(target: Path) -> int:
    """Count Python files excluding cache/build directories."""
    count = 0
    for py_file in target.rglob("*.py"):
        # Skip excluded patterns
        rel_path = py_file.relative_to(target)
        for pattern in EXCLUDE_PATTERNS:
            if rel_path.match(pattern):
                break
        else:
            count += 1
    return count

def _validate_target(target: str) -> Path:
    resolved = Path(os.path.realpath(target))
    assert resolved.exists() and resolved.is_dir(), f"Target {target} does not exist or is not a directory"
    assert not resolved.is_symlink(), f"Target {target} is a symlink"
    allowed_roots = [Path.cwd()]
    assert any(resolved.is_relative_to(r) for r in allowed_roots), f"Target {target} outside allowed roots"
    
    # Report actual file count (excluding caches)
    file_count = _count_python_files(resolved)
    print(f"Target: {target}")
    print(f"Python files (excluding caches): {file_count}")
    
    return resolved
```

## Findings Model

Every finding includes:
- `finding_id`: Unique ID (e.g., `L1-001`)
- `severity`: CRITICAL, HIGH, MEDIUM, LOW
- `layer`: L1–L7, META
- `title`: Short description
- `description`: Detailed explanation
- `location`: `file:line` when applicable
- `evidence_tier`: 1–4
- `consensus`: Number of layers that found this issue (default 1)
- `category`: quality category

## Health Score

```
health_score = max(-100, 100 - Σ(severity_weight × evidence_tier_factor))
```

Where:
- **Severity weights**: CRITICAL=20, HIGH=10, MEDIUM=5, LOW=2
- **Evidence tier factors**: T1=1.0x, T2=0.75x, T3=0.5x, T4=0.25x
- **Deduplication key**: (file, line, category, title) — keeping highest severity per key before scoring

Uses **deduplicated** severity counts (D4 deduplication removes consensus duplicates before scoring). Negative scores preserved for catastrophic severity differentiation.

## Output

`SQAReport` dataclass containing:
- `findings: List[Finding]` — all findings from all layers
- `health_score: int` — overall health score
- `layers_completed: List[str]` — completed layer names
- `audit_trail: List[AuditEntry]` — all skill invocations with timestamp, skill, exit code, finding count
- `target: str` — validated target path

Reports are saved with `chmod 600` (owner-read-write only). Findings do NOT include exact `file:line` in shared/exported output — only category and severity. A redaction option strips all `location` fields before export.

## Hard Dependencies

**Layer 2 → Layer 4**: If Layer 2 (SEMANTIC) reports failures, Layer 4 (REQUIREMENTS) **MUST NOT** execute. Skip with warning.

## Exit Criteria Validation (Step 4.5 Pattern)

After EVERY layer, run actual verification commands BEFORE trusting self-reported results. This prevents layers from incorrectly reporting PASS when they actually failed.

| Layer | What to Validate |
|-------|------------------|
| L0 | All dispatched specialist JSONs exist and parse |
| L1 | ruff/mypy exit codes are 0 |
| L2 | pytest exit code is 0 |
| L3 | All 3 analyzers (PathTraversalAnalyzer, ImportGraphAnalyzer, DocConsistencyAnalyzer) return findings |
| L4 | gto, spec-compliance exit 0 |
| L5 | adversarial-security JSON + path traversal check |
| L6 | adversarial-performance JSON + perf output |
| L7 | verify --tier=2, hook-audit, hook-inventory all pass |

**Validation command pattern:**
```python
import subprocess
result = subprocess.run(cmd, shell=True, capture_output=True)
if result.returncode != 0:
    print(f"[EXIT VALIDATION FAILED] {layer}: {cmd}")
    print(f"stdout: {result.stdout.decode()[:500]}")
    print(f"stderr: {result.stderr.decode()[:500]}")
    # HALT - do not proceed
```

**Bypass:** If layer was run with `--dry-run`, skip validation.

## Halt-on-Impact

Severity-based layer halting stops execution after a layer when findings at or above the threshold make continuing pointless.

**How it works:**
- After each layer completes, the conductor checks: "do raw (non-deduplicated) findings at or above `--halt-on` threshold make continuing pointless?"
- **HIGH** (default): Halt on any HIGH or CRITICAL findings
- **CRITICAL**: Halt only on CRITICAL findings
- **MEDIUM**: Halt on MEDIUM, HIGH, or CRITICAL
- **NONE**: Run all layers — collect all findings regardless

**Key distinction from health score:**
- Health score uses **deduplicated** counts (D4 consensus removes duplicates before scoring)
- Halt-on-impact uses **raw** counts (any CRITICAL/HIGH finding triggers halt, even if another layer also found it)

**Halt behavior (enforcement: strict):**
1. Surface all findings from current layer with file:line locations
2. Emit `[HALT] Layer N completed with X finding(s) exceeding --halt-on threshold`
3. Report health score based on deduplicated counts
4. **BLOCKED** — cannot proceed past this layer without explicit override
5. Override only with: `/sqa --halt-on NONE` (proceed with risk) or `/sqa --fix` (attempt auto-fix)

**--fix auto-fix loop (opt-in):**
When `/sqa --fix` halts, attempt Layer 1/2/3 fixes before retry:

| Layer | Confidence | Fix Type | Examples |
|-------|------------|----------|---------|
| Layer 1 | HIGH | Imports, style, formatting | `ruff check --fix`, `autoflake`, `pyupgrade` |
| Layer 2 | MEDIUM | LLM with findings + context | Generate fix patches, apply safest first |
| Layer 3 | LOW | Final LLM attempt | Architectural refactor recommendations |

**Fix loop:**
```
if --fix and halt_triggered:
    for attempt in range(1, 4):
        print(f"[FIX ATTEMPT {attempt}/3]")
        Layer_1_fixes()  # ruff --fix, etc.
        re-run layer
        if passes: break
        Layer_2_fixes()  # LLM with context
        re-run layer
        if passes: break
        Layer_3_fixes()  # Final LLM attempt
        re-run layer
        if passes: break
    if still failing:
        print("[FIX FAILED] Manual intervention required")
        print("Run `/sqa --halt-on NONE` to proceed anyway")
        sys.exit(1)
```

**When halting is NOT triggered:**
- `--halt-on HIGH`: MEDIUM and LOW findings alone do not halt
- L4 (REQUIREMENTS) still skips if L2 had pytest failures (hard dependency, no flag override)
- L7 findings at any severity do not halt (OPERATIONAL is the final actionable layer)

If a layer's tool is unavailable and it is NOT a hard dependency for a subsequent layer, skip with warning and continue.

## Graceful Degradation

**ALL-tools-unavailable behavior**: If ALL tools for a layer are unavailable, log `ERROR: All tools unavailable for Layer N — cannot proceed` and skip all remaining layers.

## Resource Bounds

File counts and sizes are calculated **excluding** cache/build directories:
- Virtual environments: `.venv/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.cache/`
- Build artifacts: `*.egg-info/`, `node_modules/`, `.tox/`
- Documentation: `docs/`, `arch_decisions/`
- Backup files: `*.old`, `*.bak`

**Resource limits:**
- `file_count <= 10_000` (source files only, excluding above patterns)
- `total_size <= 100MB` (target directory size)

Reject oversized targets early with `Target exceeds resource limits`.

## Layer Details

### Layer 1 — SYNTACTIC
Runs: `ruff check`, `mypy` (if Python), AI Distiller structure analysis.
Non-Python files skip both tools gracefully.

### Layer 2 — SEMANTIC
Runs: `verify` Tier 1 (pytest) and Tier 3 (e2e) via subprocess.
If failures detected, runs `diagnose` structured hypothesis protocol.
Checks `test_*.py` files exist.

**Framework Syntax Verification (Context7):**
When diagnosing test failures or verifying pytest/Django/vitest assertions, invoke `/context7` to confirm framework-specific syntax is correct. Test diagnostics often surface outdated patterns (e.g., deprecated `assertEquals`, wrong `pytest.raises`签名).

**Query expansion pattern:**
| Scenario | Query Expansion |
|----------|-----------------|
| pytest failure | "pytest assert statement syntax for exception testing with raises" |
| Django test | "Django test assert methods status codes and JSON responses" |
| vitest failure | "vitest expect assertions for async functions with examples" |

**Mode:** `code_only` (familiar frameworks); `full` (unfamiliar or ambiguous failures)

### Layer 3 — STRUCTURAL
AST import graph analysis for circular deps (reuse `meta-review` ImportGraphAnalyzer).
Assertion guard and parameter validation scans (reuse `harden`).
Safety pattern verification (reuse `apply_safety_patterns`).

### Layer 4 — REQUIREMENTS
Runs: `gto` gap analysis, `spec-compliance` protocol check.
Checks artifact status (PRD/ARD/CHANGELOG/README sync).
HARD DEPENDENCY: Layer 4 MUST NOT execute if Layer 2 reported failures.

### Layer 5 — SECURITY
Path traversal check (reuse `meta-review` PathTraversalAnalyzer).
`adversarial-security` subagent.
Anti-bleed gates verification (reuse `data-safety-vcs`).
External skill calls use `ALLOWED_COMMANDS` allowlist.

### Layer 6 — PERFORMANCE
`perf` tracing for nested ThreadPoolExecutors and thread-to-CPU mismatches.
`adversarial-performance` bottleneck analysis.

### Layer 7 — OPERATIONAL
`verify` Tier 2 (hook chain + router).
`hook-audit`, `hook-inventory`.
`recursive_failure_detector.py` hook.

Layer 7 must also verify:

- contract validators exist at critical boundaries
- required `Contract Authority Packet` artifacts exist at contract-sensitive boundaries
- downstream validators and proofs consume packet semantics rather than contradictory prose
- multi-terminal isolation holds
- stale-data invalidation is defined and reachable
- compact/resume path does not proceed on partial state
- producer success is not mistaken for consumer success

**Two-Sided Enforcement Principle:**

Both write-time (producer) AND consume-time (consumer) validation are required for durable correctness:
- **Write-time without consume-time**: Stale artifacts survive contract changes. A hook validated at creation time may still be consumed after the contract drifted.
- **Consume-time without write-time**: Bad artifacts accumulate upstream. Consumers keep rejecting the same malformed inputs that were never caught at the source.

Layer 7 must verify that **both** sides exist at every critical boundary — not only that the producer ran successfully.

**Implementation note:** The verification check for both-sided enforcement is not yet implemented in the SQA orchestrator. Until then, flag "one-sided enforcement at boundary {name}" as a HIGH finding in Layer 7 reviews.

### Meta-Synthesis
Consensus detection (2+ layers agree on same file:line:category).
Blind-spot detection (no coverage for a quality category when layer WAS available but found nothing — NOT when layer was skipped via D5).
Evidence quality check per `evidence-tiers`.
Flag when a packet exists but is ignored, when prose and packet disagree, or when a packet is too underspecified to certify.

## Auto-Fix Mode

**`--fix`**: Auto-fix safe issues in L1/L2:
- Formatting (`ruff format`)
- Unused imports (`ruff --fix`)
- Lint violations (`ruff --fix`)

**Excluded from auto-fix**: logic errors, security issues, type mismatches, architectural changes.

**`--fix-all`** (iterative fix loop):
```
WHILE MEDIUM+ findings exist (max 5 iterations):
  1. /sqa runs detection (layers)
  2. /sqa parses findings by severity
  3. IF MEDIUM+ findings exist:
     - /sqa invokes /code with SPECIFIC issues to fix
     - /code fixes ONLY those specific issues
     - Record fixes applied
  4. ELSE: EXIT LOOP — quality threshold met
  5. SAFETY: Max 5 iterations
```

**Convergence criteria**: 0 CRITICAL, 0 HIGH, 0 MEDIUM findings (LOW ignored).

**Division of labor**: `/sqa` does detection; `/code` does fixing.

## Routing Behavior

`/sqa` certifies the system and should route findings to owning skills:

- `/arch` for architecture and contract-model failures
- `/planning` for plan/readiness and artifact-shape failures
- `/verify` for missing or insufficient proof
- `/code` for concrete implementation defects
- `/pre-mortem` for high-risk unresolved failure patterns

`/sqa` should not directly absorb those responsibilities.

## Examples

```bash
/sqa P:/packages/my-package
/sqa P:/hooks  # sqa the hook system
/sqa           # auto-detect target
```

**Do not run `orchestrator.py` directly** — it is a utilities module only.
