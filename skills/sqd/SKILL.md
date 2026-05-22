---
name: sqd
description: SDLC Quality Dispatcher — parallel multi-LLM adversarial review dispatcher. Use when running adversarial review across multiple LLM providers simultaneously, or when a single review needs to be stress-tested by competing perspectives from DeepSeek, Gemini, Claude, and GPT models.
---
# /sqd — SDLC Quality Dispatcher

## Purpose

Parallel multi-LLM adversarial review dispatcher. Spawns adversarial review agents across multiple LLM providers (DeepSeek, Gemini, Claude, GPT) simultaneously and synthesizes their competing findings.

## When to Use

- `/sqd <target>` — Run adversarial review with multiple LLM perspectives in parallel
- When a single model's review might miss systemic issues
- When adversarial consensus needs to be established before shipping

## Execution

```bash
cd "P:\\\\\\packages/cc-skills-sdlc" && python -m sqd dispatch --target "<path or description>" --models deepseek gemini claude --parallel
```

## Execution Phases

### Phase 1 — dispatch_agents

**Type:** generation

Spawn adversarial review agents across multiple LLM providers (DeepSeek, Gemini, Claude, GPT) simultaneously. Each agent independently inspects the dispatch target and produces findings. Parallel execution maximizes coverage while minimizing wall clock time.

**Completion gate:** All dispatched agents have returned findings OR a timeout threshold has been reached.

---

### Phase 2 — collect_findings

**Type:** validation of dispatch output

Aggregate and validate the raw findings from each dispatched agent. Check for:
- Response completeness (agent produced structured output, not an error or empty result)
- Coverage of the target (findings address the dispatch scope)
- Conflicts and agreements between agents

If any agent failed to respond, record the failure and continue with the available findings. The phase succeeds if at least one agent returned valid findings.

**Completion gate:** Aggregated findings are stored in `findings/` with one artifact per agent.

---

### Phase 3 — synthesize_results

**Type:** generation of final output

Compare, contrast, and reconcile competing findings across agents. Produce a synthesis report that:
- Maps each finding to the agent(s) that produced it
- Identifies consensus positions (multiple agents agree)
- Highlights divergent positions (single agent or minority view)
- Provides a final disposition: consensus, divergence requiring human resolution, or failure

**Completion gate:** Synthesis report written to `findings/` and exit code set accordingly.

---

## Phase Gates

| Gate | Condition to Proceed |
|------|---------------------|
| **G1: Post-dispatch** | All agents returned findings, OR timeout reached, OR at least one agent returned valid findings |
| **G2: Post-collection** | Findings aggregated in `findings/`, failures logged, coverage validated |
| **G3: Post-synthesis** | Synthesis report written to `findings/`, exit code set (0 = consensus, 1 = divergence, 2 = agent failure, 3 = target not found) |

Each gate is a STOP checkpoint. If the gate condition is not met, the skill halts and returns the current exit code rather than proceeding to the next phase.

## Architecture

```
sqd/
├── SKILL.md           ← This file
├── layers/            ← Review dispatch layers
│   ├── __init__.py
│   └── dispatcher.py  ← Parallel spawn + synthesis
├── lib/               ← Shared utilities
│   └── __init__.py
├── hooks/             ← Pre/post dispatch hooks
├── findings/          ← Output artifacts
└── tests/            ← Test suite
```

## Exit Codes

- 0: All models returned consensus (or all agreed no issue)
- 1: Divergent findings — synthesis report written to `findings/`
- 2: One or more models failed to respond
- 3: Dispatch target not found or inaccessible

## Related Skills

- `/sqa` — Sequential quality assurance (single-model, audit mode)
- `/planning` — Planning with adversarial review slot
- `/arch` — Architecture review with ADR critic

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious
