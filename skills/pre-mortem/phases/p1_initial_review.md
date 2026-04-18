# Phase 1: Triage + Specialist Dispatch

> **NOTE:** This is an orchestrator prompt template. Variables `{WORK_FILE}`, `{session_dir}`, and `{specialist}` must be substituted by the calling `/pre-mortem` SKILL.md workflow before use. This file cannot execute as a standalone procedure.

## Your Job

You are a triage agent. Your job is NOT to critique the work yourself — it is to classify the target, select the most useful specialist subagents, dispatch them in parallel, and consolidate their findings.

## Step 1: Classify the Target

Read the work (`{WORK_FILE}`) and classify it into one of:

- **skill** — A Claude Code skill with SKILL.md, phases, triggers
- **code** — Source code files (Python, JS, etc.)
- **plan** — An implementation plan, design document
- **document** — A markdown doc, README, policy
- **hook** — A hook script (PreToolUse, PostToolUse, Stop)
- **agent** — An agent definition file
- **failure / RCA** — A failure mode or root-cause analysis (uses full 7-specialist parallel dispatch)

## Step 2: Select Relevant Specialists

Based on the target type and content, select the 2-4 most relevant specialists:

**For skills:**
- `adversarial-critic` — reasoning quality, phase logic, trigger matching
- `adversarial-compliance` — YAML frontmatter, hook registration, schema
- `adversarial-quality` — maintainability, skill structure

**For code (Python, JS, etc.):**
- `adversarial-security` — data access, auth, I/O, injection
- `adversarial-performance` — hot paths, loops, DB queries
- `adversarial-logic` — off-by-one, wrong operators, conditionals
- `adversarial-state-machine` — status fields, lifecycle
- `adversarial-io-validation` — path validation, external calls
- `adversarial-compliance` — API contracts, schema
- `adversarial-quality` — tech debt, maintainability
- `adversarial-testing` — test coverage, missing scenarios

**For plans:**
- `adversarial-critic` — reasoning quality, bias, feasibility
- `adversarial-compliance` — spec alignment, completeness

**For documents:**
- `adversarial-critic` — clarity, precision vs recall in claims
- `adversarial-quality` — structure, completeness

**For hooks:**
- `adversarial-security` — path injection, command execution
- `adversarial-compliance` — hook registration, exit code handling
- `adversarial-io-validation` — file operations, external calls

**For agents:**
- `adversarial-critic` — reasoning quality, bias
- `adversarial-compliance` — YAML frontmatter, parameter validation

**For failure / RCA:**
- All 7 specialists run in parallel (adversarial-compliance, adversarial-logic, adversarial-performance, adversarial-security, adversarial-testing, adversarial-quality, adversarial-rca)

## Step 3: Ensure Specialists Directory

**Defensive check before dispatching agents.** `setup()` already creates `specialists/` when the session is initialized (via `get_specialists_dir()`), but make the directory unconditionally as a safety net — it is safe to call on an existing directory.

```python
from pathlib import Path
specialists_dir = Path("{session_dir}") / "specialists"
specialists_dir.mkdir(exist_ok=True)
```

This must run before Step 4 so that the specialists directory exists for the idempotency check.

## Step 4: Check for Prior Output (Idempotent Dispatch)

Before dispatching specialists, check whether their output files already exist at the canonical path and read any existing dispatch manifest.

**Expected output path pattern:** `P:/{session_dir}/specialists/{specialist-name}-findings.json`

For each selected specialist, check if `P:/{session_dir}/specialists/{specialist-name}-findings.json` already exists and contains valid JSON (validation is implemented in Step 5c).

- If ALL specialist output files exist and are valid, skip dispatch entirely and proceed directly to Step 6 (consolidation).
- If ANY output file is missing or invalid, dispatch ONLY the missing or invalid specialists.

**Also check for an existing dispatch manifest** from a prior interrupted run. If `P:/{session_dir}/specialists/dispatch_manifest.json` exists, read it to know which specialists were already dispatched in the interrupted run. Use this to skip them on re-run.

## Step 5: Dispatch Missing Specialists

**Dispatch pattern:** Pre-populate manifest, then dispatch all specialists in parallel foreground. Completion markers provide idempotency.

### 5a: Pre-populate Manifest (before dispatch loop)

```python
import json
from pathlib import Path

manifest_path = Path("{session_dir}") / "specialists" / "dispatch_manifest.json"
specialists_dir = Path("{session_dir}") / "specialists"

# Pre-populate manifest with ALL specialist names BEFORE dispatch
# This ensures if context compacts mid-loop, all specialists are recorded
manifest = {
    "dispatched": list(selected_specialists),  # ALL names, not incremental
    "session_dir": "{session_dir}"
}
with open(manifest_path, "w") as f:
    json.dump(manifest, f)
```

### 5b: Parallel Foreground Dispatch

Dispatch all specialists in parallel via multiple Agent calls in a single message. Wait for all to complete before proceeding to consolidation.

Launch ALL specialists in parallel by making multiple `Agent(...)` tool calls in a single message. For each specialist:

```json
Agent({
  "description": "Run specialist review",
  "prompt": "Read P:/.claude/agents/{specialist}.md and follow its instructions to review the work at: P:/{session_dir}/work.md. Write your JSON findings to: P:/{session_dir}/specialists/{specialist}-findings.json. When complete, write a completion marker to: P:/{session_dir}/specialists/{specialist}-complete.json containing: {\"specialist\": \"{specialist}\", \"complete\": true}. Return ONLY the file path in your response text.",
  "subagent_type": "general-purpose"
})
```

**Dispatch pattern for 4 specialists (example):**

```json
Agent({"description": "adversarial-logic specialist", "prompt": "Read P:/.claude/agents/adversarial-logic.md and follow its instructions to review the work at: P:/{session_dir}/work.md. Write your JSON findings to: P:/{session_dir}/specialists/adversarial-logic-findings.json. When complete, write a completion marker to: P:/{session_dir}/specialists/adversarial-logic-complete.json containing: {\"specialist\": \"adversarial-logic\", \"complete\": true}. Return ONLY the file path in your response text.", "subagent_type": "general-purpose"})
Agent({"description": "adversarial-compliance specialist", "prompt": "Read P:/.claude/agents/adversarial-compliance.md and follow its instructions to review the work at: P:/{session_dir}/work.md. Write your JSON findings to: P:/{session_dir}/specialists/adversarial-compliance-findings.json. When complete, write a completion marker to: P:/{session_dir}/specialists/adversarial-compliance-complete.json containing: {\"specialist\": \"adversarial-compliance\", \"complete\": true}. Return ONLY the file path in your response text.", "subagent_type": "general-purpose"})
Agent({"description": "adversarial-quality specialist", "prompt": "Read P:/.claude/agents/adversarial-quality.md and follow its instructions to review the work at: P:/{session_dir}/work.md. Write your JSON findings to: P:/{session_dir}/specialists/adversarial-quality-findings.json. When complete, write a completion marker to: P:/{session_dir}/specialists/adversarial-quality-complete.json containing: {\"specialist\": \"adversarial-quality\", \"complete\": true}. Return ONLY the file path in your response text.", "subagent_type": "general-purpose"})
Agent({"description": "adversarial-testing specialist", "prompt": "Read P:/.claude/agents/adversarial-testing.md and follow its instructions to review the work at: P:/{session_dir}/work.md. Write your JSON findings to: P:/{session_dir}/specialists/adversarial-testing-findings.json. When complete, write a completion marker to: P:/{session_dir}/specialists/adversarial-testing-complete.json containing: {\"specialist\": \"adversarial-testing\", \"complete\": true}. Return ONLY the file path in your response text.", "subagent_type": "general-purpose"})
```

**Key points:**
- Use foreground agents (no `run_in_background`) — wait for each to complete
- Dispatch all in one message for true parallelism
- Completion markers provide idempotency if context compacts mid-dispatch
- After each specialist agent returns, verify its findings JSON and completion marker exist before proceeding — do not wait until all agents return to check individual results
- After all agents return, check completion markers and JSONs before proceeding

### 5b-alt: External LLM Dispatch for Quality Specialist

**Conditional**: Only applies when `adversarial-quality` is one of the selected specialists AND `SDLC_MULTI_LLM=1`.

**Pre-flight check:**

```bash
python -c "import os; print(os.environ.get('SDLC_MULTI_LLM', '0'))"
```

If not `"1"`, use the standard Agent dispatch for all specialists (Step 5b).

**If enabled**, for `adversarial-quality` ONLY, dispatch via Bash instead of Agent. Remove `adversarial-quality` from the parallel Agent dispatch batch and handle it separately:

```bash
python "P:/packages/cc-skills-ai-cli/skills/ai-cli/ai_cli.py" "Review the work file at P:/{session_dir}/work.md for maintainability risks, tech debt, structural quality issues, and missing best practices. Output findings as a JSON array with severity (HIGH/MEDIUM/LOW), description, and location." --context "P:/{session_dir}/work.md" --gemini-only --output-format json --no-critic --timeout 120
```

**Transform output:** Parse the ai-cli JSON output and write to the canonical specialist findings path:

```python
import json
from pathlib import Path

ai_cli_json = Path("{ai_cli_output_path}")
raw = json.loads(ai_cli_json.read_text(encoding='utf-8'))
output_text = raw.get('output', '')

try:
    parsed = json.loads(output_text)
    if isinstance(parsed, list):
        findings = parsed
    elif isinstance(parsed, dict) and 'findings' in parsed:
        findings = parsed['findings']
    else:
        findings = [{'severity': 'MEDIUM', 'description': output_text}]
except json.JSONDecodeError:
    findings = [{'severity': 'MEDIUM', 'description': output_text}]

canonical = {
    'specialist': 'adversarial-quality',
    'findings': findings,
    'model': raw.get('model', {}).get('name', 'gemini-external'),
}
findings_path = Path('P:/{session_dir}/specialists/adversarial-quality-findings.json')
findings_path.write_text(json.dumps(canonical, indent=2), encoding='utf-8')
```

Write a completion marker to `P:/{session_dir}/specialists/adversarial-quality-complete.json` containing `{"specialist": "adversarial-quality", "complete": true}`.

**Fallback:** If ai-cli fails, fall back to the standard Claude agent dispatch:
```json
Agent({"description": "adversarial-quality specialist", "prompt": "Read P:/.claude/agents/adversarial-quality.md and follow its instructions to review the work at: P:/{session_dir}/work.md. Write your JSON findings to: P:/{session_dir}/specialists/adversarial-quality-findings.json. When complete, write a completion marker to: P:/{session_dir}/specialists/adversarial-quality-complete.json containing: {\"specialist\": \"adversarial-quality\", \"complete\": true}. Return ONLY the file path in your response text.", "subagent_type": "general-purpose"})
```

**All other specialists** remain Claude agent dispatches (unchanged).

### 5c: After Dispatch — Verify All Completed

```python
# Check which JSONs and completion markers exist
available = []
for specialist in selected_specialists:
    json_path = specialists_dir / f"{specialist}-findings.json"
    marker = specialists_dir / f"{specialist}-complete.json"
    if json_path.exists() and marker.exists():
        try:
            with open(json_path) as f:
                json.load(f)
            available.append(specialist)
        except (json.JSONDecodeError, OSError):
            pass

print(f"Specialists: {len(selected_specialists)}, JSONs available: {len(available)}")
if len(available) == len(selected_specialists):
    print("All specialist JSONs available — proceeding to consolidation.")
elif available:
    print(f"Partial results: {available}. Waiting for: {set(selected_specialists) - set(available)}")
    print("Re-run /pre-mortem to continue — completion markers ensure idempotent skip.")
else:
    print("No JSONs yet — re-run /pre-mortem after specialists complete.")
```

**If ALL specialists have valid JSONs + completion markers → proceed directly to Step 6 (consolidation).**
**If SOME available → re-run `/pre-mortem` (completion markers ensure already-finished specialists are skipped).**
**If NONE yet → re-run `/pre-mortem` after allowing time for agents to complete.**

**IMPORTANT — Skill target scope:** When the target is a skill, ensure specialists examine the full skill package — not just lib/*. This includes SKILL.md frontmatter validity, phases/ directory schema, and skill registration. Do NOT narrow focus to a single module without explicitly justifying why that module is the primary risk.

## Step 6: Consolidate Findings

After all specialists complete, read their JSON output files and produce a consolidated Phase 1 findings document.

**Input files:** Read all `P:/{session_dir}/specialists/{name}-findings.json` files that exist (the set dispatched in Step 5 is dynamic — do not hardcode a fixed list).

**Output format** (write to `P:/{session_dir}/p1_findings.md`):

```
## Triage Classification
[type] — [brief justification]

## Dispatched Specialists
- [specialist name]: [what they analyzed]

## Specialist Findings Summary

### [Specialist 1 Name]
**Domain:** [what they cover]
**Key findings:**
- [HIGH] finding description (file:line mandatory for code findings)
- [MEDIUM] finding description
...

### [Specialist 2 Name]
...

## Consolidated Findings

### Logical Gaps & Inconsistencies
1.1. [HIGH] (source: specialist-name) — issue (file:line)
1.2. [MEDIUM] (source: specialist-name) — issue
...

### Hidden Assumptions & Fragile Dependencies
2.1. [MEDIUM] (source: specialist-name) — issue
2.2. [LOW] (source: specialist-name) — issue
...

### Missing Obvious Actions / Best Practices
3.1. [HIGH] (source: specialist-name) — issue
3.2. [MEDIUM] (source: specialist-name) — issue
...

### Risks and Edge Cases
4.1. [MEDIUM] (source: specialist-name) — issue
4.2. [LOW] (source: specialist-name) — issue
...

### Concrete Recommendations
5.1. [specific change] (source: specialist-name)
5.2. [specific change] (source: specialist-name)
...

### Open Questions / Unknowns
6.1. [uncertainty] (source: specialist-name)
6.2. [LOW] (source: specialist-name) — uncertainty
...
```

**P1 #4 Citation requirement:** Every finding that references specific code MUST include a `file:line` citation. Findings without citations will be treated as unverified.

If a specialist found nothing notable in their domain, note: "No significant issues found in [domain]."

## Important Constraints

- Do NOT do your own critique — dispatch specialists and aggregate their output
- Each finding must cite which specialist found it
- Do not pad — if a specialist found nothing, say so
- Keep findings brief — this is a consolidation pass, not a re-analysis

## Phase 1 Completion Gate

**MANDATORY before proceeding to Phase 2.** If this gate fails, do not proceed.

> **Phase sequencing note:** Phase gating is enforced by the `/pre-mortem` SKILL.md orchestrator workflow, not by this file alone. This file defines the gate criteria but cannot self-enforce phase ordering.

**Gate criteria:** ALL dispatched specialists produced JSONs AND `p1_findings.md` exists.

**Verification steps:**
1. Read `P:/{session_dir}/specialists/dispatch_manifest.json` — extract the `dispatched` list
2. For each specialist in `dispatched`, verify `P:/{session_dir}/specialists/{name}-findings.json` exists
3. Verify `P:/{session_dir}/p1_findings.md` exists

**Failure modes:**
- `dispatch_manifest.json` missing → Orchestrator never ran or failed before writing manifest. Re-run from Step 5.
- Any specialist from `dispatched` list has no JSON → That specialist's Task failed or produced no output. Re-run from Step 5 (specialists with existing JSONs will be skipped per idempotent dispatch).
- `p1_findings.md` missing → Consolidation step (Step 6) never ran

**If gate fails:** Do not proceed to Phase 2 with partial input.
