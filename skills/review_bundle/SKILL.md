---
name: review_bundle
description: Create decision-ready review bundles for external architectural review with evidence quality controls
version: 1.0.0
status: stable
category: documentation
enforcement: advisory
triggers:
  - /review_bundle
aliases:
  - /review_bundle

parallel_agents: true
execution_mode: hybrid
---

# Review Bundle Creation

Create comprehensive context bundles for LLM question-answering about any system.

## Purpose

Generate one self-contained Markdown document with:
- accurate system context
- component inventory (what files exist)
- architecture overview (how pieces fit)
- design constraints (what can't change)
- known issues (what's broken)

## Project Context

### Constraints
- Hybrid execution mode based on file count
- Keep output concise but complete
- Focus on WHAT EXISTS, not what should be

### Technical Context
- Output directory: `P:\__csf\.staging\` (Windows path)
- Size-based routing: <10 files (single agent), 10-50 files (2 agents), 50+ files (4 agents)
- Parallel agents: Explorer, Core Reader, Config Reader, Dependency Scanner

---

# REVIEW BUNDLE CONTRACT

You are preparing a review bundle for LLM context gathering.

Goal: provide comprehensive system context so an LLM can answer questions accurately.

Generate a SINGLE Markdown file with the sections below.

---

## 1. PROJECT CONTEXT

### Bundle Metadata
- **Generated**: [timestamp]
- **Scope**: [directory/system]
- **File Count**: [N files]
- **Execution Mode**: [single-agent / 2-agents / 4-agents]

### Domain & Purpose
One short paragraph: what the system does, who uses it, and why it is critical.

### Scale Metrics
- LOC (if known)
- Number of major subsystems
- Deployment scope
- Change frequency

### Your Environment
- **OS and shell**
- **Primary languages and frameworks**
- **Package managers and build tools**
- **Databases or external services**

---

## 2. ARCHITECTURE OVERVIEW

Provide an ASCII diagram with primary data/control flow.

### For each major subsystem:
- Name and purpose
- Files/directories
- Main entry points
- Dependencies (upstream/downstream)
- Critical invariants

---

## 3. EXECUTION AND DATA FLOW

### Execution Sequences
- Trigger → handlers → side effects
- Mandatory ordering constraints

### State Management
- State stores and ownership
- Consistency model and isolation boundaries

### Error Handling
- Fail-open vs fail-closed policy
- Retry/timeout behavior

---

## 4. COMPONENT INVENTORY

List main components grouped by:
- Core Logic
- Utilities/Helpers
- Configuration
- Infrastructure

For each component include:
- Path and key functions/classes
- Responsibility
- Inputs/outputs
- Known limitations

---

## 5. DESIGN INTENT AND NON-NEGOTIABLES

### Architectural Pillars
### Technology Constraints
### Performance SLAs (if applicable)
### Things That Must NOT Change

---

## 6. KNOWN ISSUES

List current problems, ordered by impact:
- Scenario
- Expected vs actual
- Impact
- Current workaround (if any)

---

## 7. INTEGRATION POINTS

Where new solutions can plug in:
- Existing hooks/interfaces
- Invocation model
- Data exchange contracts
- Output/exit code expectations

---

## 8. INPUT/OUTPUT CONTRACT

Document what each agent/process receives at each phase. Required for any skill that dispatches agents.

### Per-Phase Data Flow
For each phase/stage:
- **What it reads** — file path, content source, or artifact name
- **What it writes** — output file or artifact name
- **Key constraint** — any critical ordering or gating requirements

### Agent Read Sources (CRITICAL)
For skills that dispatch agents in parallel, explicitly state what agents read:
- `analysis` = the operator's/intermediary output (NOT source code)
- `source` = actual source code under review
- `work` = user-provided work input

**Distinction matters**: Agents reading analysis build on operator errors. Agents reading source catch issues directly. Document which applies.

### Quality Gates
Document any post-completion or phase-completion gates:
- What the gate checks (headers present, JSON exists, evidence cited)
- What the gate does NOT check (content accuracy, file:line citations)
- When the gate runs (before dispatch, after completion)

---

## 9. AGENT DISPATCH DEFINITIONS

Full prompts for all dispatched agents. Required for any skill with parallel agent dispatch.

### Per-Agent Specification
For each agent, document:
- **Agent type/subagent_type** — exact name used in dispatch
- **Role** — what domain it reviews (security, logic, quality, etc.)
- **Prompt excerpt** — first 2-3 sentences of actual prompt
- **What it reads** — must match INPUT/OUTPUT CONTRACT
- **Output file** — where findings are written

### Dispatch Order
State parallel vs serial:
- Parallel = all agents run simultaneously
- Serial = runs after parallel agents complete (critic pattern)

### Falsification Mandate (if present)
If the skill requires agents to attempt empirical reproduction of HIGH findings, document:
- What falsification requires (test output, code:line verification, minimal reproduction)
- What happens when falsification fails (demotion, confidence ceiling)

---

## 10. FAILURE SCENARIOS

Concrete examples of how the system can fail. Required for adversarial analysis skills.

### Failure Chain Documentation
For each documented failure:
1. **Trigger** — what action started the failure
2. **Propagation** — how it spread through each phase/agent
3. **Detection point** — where/catch it was caught
4. **Actual vs expected** — what was claimed vs reality
5. **Root cause** — what principle or rule was violated

### Common Failure Patterns
Document patterns relevant to the skill type:
- For pre-mortem: evidence without verification, analysis without source reading
- For critique: dispatch failures, session recovery gaps, phase gate bypasses
- For any parallel dispatch: one bad premise poisoning all agents

### Verified Fixes
Any currently-applied fixes from prior failure investigations:
- What was changed
- What file/line
- What regression it prevents

---

## 11. APPENDIX: SAMPLE RUNS / LOGS (OPTIONAL)

Paste concrete logs/outputs tied to known issues.

---

## INSTRUCTION FOR GENERATOR

1. Scan the repo and extract as much as possible automatically.
2. Preserve exact file paths, commands, error messages, and exit codes.
3. Mark assumptions explicitly as `ASSUMPTION: ...`.
4. Focus on WHAT EXISTS (files, code, architecture) not WHAT SHOULD BE (opportunities, metrics).
5. **REQUIRED sections for skills that dispatch agents**:
   - Section 8 (INPUT/OUTPUT CONTRACT) — mandatory when skill dispatches parallel agents
   - Section 9 (AGENT DISPATCH DEFINITIONS) — mandatory when skill dispatches agents
   - Section 10 (FAILURE SCENARIOS) — mandatory for adversarial analysis skills (pre-mortem, critique, adversarial-review)
6. **For multi-skill bundles** (e.g., `/pre-mortem` and `/critique` together): include all three required sections for each skill, plus a comparison table highlighting architectural differences

Output a SINGLE Markdown file named: `review_bundle_[system_name]_[date].md`

---

## Your Workflow

1. **Scope Selection**: User selects system (hooks, skills, CSF, CHS, CKS, TaskMaster, custom)
2. **File Count & Mode**: Use Explorer to count files, route based on count
3. **Generate Bundle**: Write `review_bundle_[name].md` using the contract above
4. **Deliver**: Provide output location and file count

### Parallel Agent Strategy (when applicable)
- **Explorer**: Find all files, trace imports
- **Core Reader**: Read core logic files
- **Config Reader**: Read config/data files
- **Dependency Scanner**: Find env vars, deps

## Validation Rules

### Prohibited Actions
- Do NOT use parallel agents for <10 files (overhead exceeds benefit)
- Do NOT skip scope selection step
- Do NOT claim bundle created without Write tool verification

### Configuration
- `REVIEW_BUNDLE_OUTPUT_DIR`: Default `P:\__csf\.staging\`
- `REVIEW_BUNDLE_FORCE_SERIAL`: Force single-agent mode
- `REVIEW_BUNDLE_THRESHOLD_SMALL`: Files < N use single agent (default: 10)
- `REVIEW_BUNDLE_THRESHOLD_LARGE`: Files >= N use 4 agents (default: 50)

## Execution Mode: Hybrid

This skill uses size-based routing to optimize for both small and large scopes:

| File Count | Execution Mode | Rationale |
|------------|----------------|-----------|
| < 10 files | Single agent | Overhead of parallelization exceeds benefit |
| 10-50 files | 2 parallel agents | Balance speed vs coordination |
| 50+ files | 4 parallel agents | Max parallelization for large scopes |

## Execution Protocol

### Step 1: Scope Selection

Ask user which system to bundle:
```
Which system?
1 - Hooks (P:\.claude\hooks\)
2 - Skills (P:\.claude\skills\)
3 - CSF Infrastructure (P:\__csf\)
4 - CHS (P:\__csf\src\features\chs\)
5 - CKS (P:\__csf\src\features\cks\)
6 - TaskMaster (P:\__csf\src\features\taskmaster\)
7 - All (comprehensive)
8 - Custom path
```

### Step 2: File Count & Mode Selection

1. Use Explorer agent (or Glob) to count files in scope
2. Route based on count and apply the REVIEW BUNDLE CONTRACT above

### Step 3: Generate Bundle

Write `review_bundle_[name]_[date].md` to `P:\__csf\.staging\`.

## Usage

```bash
/review_bundle
# Select system from menu (auto-detects optimal mode)

/review_bundle hooks --serial
# Force single-agent mode

/review_bundle P:\custom\path
# Bundle custom directory
```
