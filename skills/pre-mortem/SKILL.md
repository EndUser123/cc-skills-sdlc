---
name: pre-mortem
description: Adaptive adversarial critique — dynamically dispatches specialist subagents based on target type and content, including blinded consumer-contract review
version: "2.1.0"
status: "stable"
category: analysis
triggers:
  - /pre-mortem
workflow_steps:
  - Capture work input
  - Initialize file-based session
  - Launch Phase 1 (triage + specialist dispatch)
  - Launch Phase 2 (cross-agent meta-critique)
  - Launch Phase 3 (synthesis)
  - Deliver final output in RNS format
  - Evidence-bound verification
  - Log skill coverage
  - Execute "0 — Do ALL" directive
suggest:
enforcement: advisory
parallel_agents: true

# Evidence-bound verification (anti-confabulation)
verification:
  commands:
    - description: "Confirm p3.md synthesis exists"
      tool: "Bash"
      args:
        command: 'ls -la "P:\\\\\\.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p3.md" 2>/dev/null | tail -1 || echo "NO P3 FOUND"'
    - description: "Confirm Phase 1 findings exist"
      tool: "Bash"
      args:
        command: 'ls -la "P:\\\\\\.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p1_findings.md" 2>/dev/null | tail -1 || echo "NO P1 FOUND"'
    - description: "Confirm Phase 2 meta-critique exists"
      tool: "Bash"
      args:
        command: 'ls -la "P:\\\\\\.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p2.md" 2>/dev/null | tail -1 || echo "NO P2 FOUND"'
    - description: "Count findings with severity levels"
      tool: "Bash"
      args:
        command: 'grep -cP "\\[(CRITICAL|HIGH|MEDIUM|LOW)\\]" "P:\\\\\\.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p3.md" 2>/dev/null || echo "0"'
  summary_mode: evidence_only
  expected_artifacts:
    - "P:\\\\\\.claude/.artifacts/{terminal_id}/pre-mortem/{session_id}/p1_findings.md"
    - "P:\\\\\\.claude/.artifacts/{terminal_id}/pre-mortem/{session_id}/p2.md"
    - "P:\\\\\\.claude/.artifacts/{terminal_id}/pre-mortem/{session_id}/p3.md"
---
# Critique — Adaptive Adversarial Review

Dynamically dispatch specialist subagents based on what you're reviewing. Absorbs `/adversarial-review` — one adaptive skill instead of two overlapping pipelines.

## Package-Owned Layout

This skill folder is the source of truth for the pre-mortem capability across agent environments.

- Claude Code primary workflow: `SKILL.md`
- Shared method and contracts: `references/`
- Phase prompts: `references/phases/`
- Codex adapter: `.codex/SKILL.md`
- PI harness contract: `.pi/pre-mortem-contract.md`

Before changing the review contract, check the relevant shared reference files:

- `references/method.md` — common pre-mortem method and quality bar
- `references/failure-mode-checklist.md` — internal predictable-issue prompts
- `references/output-contract.md` — final critique and RNS requirements
- `references/evidence-contract.md` — evidence and verification requirements
- `references/modes.md` — quick, standard, and deep modes
- `references/investigation-types.md` — static vs non-static investigation boundaries
- `references/static-test-contract.md` — static checks that must cover package and prompt wiring
- `references/non-static-validation.md` — safe live/plugin validation and permission boundaries
- `references/review-lenses.md` — logic, state, safety, performance, testing, and observability lenses
- `references/project-profiles.md` — repo-local domain profile discovery and application
- `references/decision-model.md` — GO / watchpoint / no-go decisions
- `references/live-probe-planner.md` — exact runtime probe planning when static evidence is insufficient
- `references/finding-synthesis.md` — deduplication, evidence strength, falsifiers, and wrong-order risk
- `references/destructive-live-preflight.md` — hard gate for destructive or live operations
- `references/historical-regression-awareness.md` — prior-failure checks before readiness claims

The shared references are additive to the Claude workflow below. If a reference and this file conflict, preserve the stricter requirement until the conflict is resolved explicitly.

## Subagent Architecture

| Phase | Agent | Timing | Purpose |
|-------|-------|--------|---------|
| 1 | general-purpose (triage) | Orchestrator | Classify target, dispatch specialists in parallel |
| 1 | specialist subagents | Parallel | Domain-specific analysis (quality specialist uses external LLM when SDLC_MULTI_LLM=1) |
| 2 | general-purpose | After Phase 1 | Cross-agent meta-critique |
| 3 | general-purpose | After Phase 2 | Synthesized final critique |

## Specialist Subagent Registry

**Code/Module Review:**
| Subagent | Best For |
|----------|----------|
| `adversarial-security` | Data access, auth, I/O, injection vectors |
| `adversarial-performance` | Hot paths, loops, DB queries, N+1 |
| `adversarial-logic` | Off-by-one, wrong operators, inverted conditionals |
| `adversarial-state-machine` | Status fields, lifecycle, transitions |
| `adversarial-io-validation` | Path validation, file existence, external calls |
| `adversarial-compliance` | Schema, API contracts, specs |

**Broader Analysis:**
| Subagent | Best For |
|----------|----------|
| `adversarial-quality` | Tech debt, maintainability risks |
| `adversarial-testing` | Missing tests, coverage gaps, brittle tests |
| `adversarial-critic` | Meta-analysis: consensus, blind spots, contradictions |
| `adversarial-rca` | Root cause analysis, causal chains |

**Skills/Plans/Documents:**
| Subagent | Best For |
|----------|----------|
| `adversarial-critic` | Reasoning quality, bias, over/under-statement |
| `adversarial-compliance` | Schema, spec, API contract compliance |

## Blinded Consumer Review

For stateful, resumable, hook, artifact, or handoff targets, Phase 1 must include a blinded consumer-contract review.

The blinded review asks:

- what does the producer promise?
- what does the consumer actually require?
- where is the validator?
- what happens when required fields are missing or stale?
- is the design proving only producer success instead of consumer success?

## Failure-Mode Prompts

Before synthesizing a critique, `/pre-mortem` should run a short internal failure-mode check:

- What is the most plausible way this target still fails even if the happy path passes?
- What am I treating as safe because the producer succeeds, even though the consumer could still fail?
- What hidden assumption would most likely break under stale data, workflow interruption, or multi-terminal use?
- What recommendation becomes dangerous if it is low-reversibility or applied out of order?
- What evidence is missing that would meaningfully downgrade or overturn a high-severity finding?
- What blind spot is shared across multiple specialists rather than isolated to one agent?
- What risk am I underweighting because it is operational, temporal, or only appears on resume/handoff?
- What recommendation is really architecture work, not a local patch?
- What would a faster or more literal model fail to challenge in this critique?
- What change here reduces one failure mode but creates a new one elsewhere?
- Do we have any predictable issues in primary and related code, or dependent or supporting code/files?
- Does this target's dependency chain extend beyond what was reviewed?
- What could break if recommendations are applied at the wrong scope?
- Is the target in a valid critiqueable state (not mid-edit, not stale)?
- Is this the right priority — are we optimizing something unimportant?

These are internal self-check prompts. They are not default user-facing questions and should only surface to the user when `/pre-mortem` is genuinely blocked and cannot proceed safely without clarification.

## Your Workflow

### Step 1: Capture Work Input

Use conversation context to determine what to critique:

**Context-Aware Resolution (in priority order):**

1. **Args specifies target** — If args contains a skill name (e.g., `on /pre-mortem`) or is a path/description of work, use that.
2. **Recent session focus** — If args is empty, check what was just worked on. Recent file edits, skill modifications, or conversation focus indicate the target.
3. **Only ask if genuinely ambiguous** — If multiple possible targets exist in recent context, ask the user to clarify. Never ask when context is obvious.

**Examples:**
- `/pre-mortem on /pre-mortem` → Pre-mortem the /pre-mortem skill
- `/pre-mortem` (after editing a skill) → Pre-mortem that skill
- `/pre-mortem` (after no recent work) → Ask for input

### Step 2: Initialize File-Based Session

Create a pre-mortem session for token-efficient file passing:

```
python -c "
from pathlib import Path
import sys
candidate_lib_dirs = [
    Path('P:/packages/cc-skills-sdlc/skills/pre-mortem/__lib'),
    Path('P:/.claude/skills/pre-mortem/__lib'),
]
for lib_dir in candidate_lib_dirs:
    if lib_dir.exists():
        sys.path.insert(0, str(lib_dir))
        break
from premortem_io import PreMortemSession
session = PreMortemSession.find_or_create_session()
session.setup()
session.write_work(sys.argv[1] if len(sys.argv) > 1 else '')
print(session.get_session_dir())
" "{WORK_INPUT}"
```

**Note:** If `WORK_INPUT` contains double quotes or shell-sensitive characters, this inline-python pattern may fail on Windows due to `cmd.exe` quoting rules. Workaround: pass content via file reference or escape double quotes in the input before invocation.

This creates: `{session_dir}/work.md`

### Step 2b: Idempotency Check

Before dispatching, check if this session already has completed work:

```python
from premortem_io import PreMortemSession

session = PreMortemSession.find_or_create_session()
session_dir = session.get_session_dir()
p1_findings = session_dir / "p1_findings.md"
p2_meta = session_dir / "p2.md"
p3_final = session_dir / "p3.md"

if p3_final.exists():
    print(f"Session {session_dir.name} already complete — reading from: {p3_final}")
elif p1_findings.exists() and not p2_meta.exists():
    print(f"Session {session_dir.name} has Phase 1 output — resume from Step 4")
elif p2_meta.exists() and not p3_final.exists():
    print(f"Session {session_dir.name} has Phase 2 output — resume from Step 5")
else:
    print(f"Session {session_dir.name} is new or incomplete — run Phase 1")
```

**Manifest-based resume:** The dispatch manifest at `{session_dir}/specialists/dispatch_manifest.json` tracks which specialists were already dispatched. Re-running `/pre-mortem` skips already-dispatched specialists.

### Step 3: Launch Phase 1 — Triage + Specialist Dispatch

Read the triage prompt, classify the work, select specialists, dispatch in parallel, consolidate findings.

```
Read `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p1_initial_review.md`
Read the work: cat "P:\\\\\\{session_dir}/work.md"
Follow the triage and dispatch instructions in p1_initial_review.md
Write consolidated findings to: P:\\\\\\{session_dir}/p1_findings.md
Output ONLY the path P:\\\\\\{session_dir}/p1_findings.md
```

Phase 1 agents dispatch specialists in parallel via Task tool. Each specialist writes its findings to the session dir. Phase 1 agent consolidates all specialist output into `p1_findings.md`.

**Dispatch failure tracking:** After launching specialist agents, the orchestrator must track which specialists were dispatched via the dispatch manifest. If a specialist was launched but produces no JSON output, that is a dispatch failure. After the dispatch loop, the orchestrator checks whether specialist JSONs are already available (idempotent resume). If all dispatched specialists have valid JSONs, it proceeds to consolidation. If partial or none, it prints guidance to re-run `/pre-mortem`.

**Phase 1 Completion Gate:** Before proceeding to Step 4, verify that ALL dispatched specialists (from the manifest) have valid JSONs in `P:\\\\\\{session_dir}/specialists/` and `p1_findings.md` exists. If any dispatched specialist's JSON is missing, re-run `/pre-mortem` — the manifest ensures already-dispatched agents are skipped. Do not proceed to Phase 2 with partial input.

### Step 4: Launch Phase 2 — Cross-Agent Meta-Critique

After Phase 1 specialists complete:

```
Read `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p2_meta_critique.md`
Read: cat "P:\\\\\\{session_dir}/work.md"
Read: cat "P:\\\\\\{session_dir}/p1_findings.md"
Follow the meta-critique instructions
Write meta-critique to: P:\\\\\\{session_dir}/p2.md
Output ONLY the path P:\\\\\\{session_dir}/p2.md
```

### Step 5: Launch Phase 3 — Synthesis

After Phase 2 complete:

```
Read `P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p3_synthesis.md`
Read: cat "P:\\\\\\{session_dir}/work.md"
Read: cat "P:\\\\\\{session_dir}/p1_findings.md"
Read: cat "P:\\\\\\{session_dir}/p2.md"
Follow the synthesis instructions
Write final critique to: P:\\\\\\{session_dir}/p3.md
Output ONLY the path P:\\\\\\{session_dir}/p3.md
```

### Step 6: Deliver Final Output — RNS Format

Read `P:\\\\\\{session_dir}/p3.md` and present it as the final output **reformatted as RNS**.

After presenting, log the skill coverage:

```
python -c "
import sys
from pathlib import Path
candidate_lib_dirs = [
    Path('P:/packages/cc-skills-sdlc/skills/pre-mortem/__lib'),
    Path('P:/.claude/skills/pre-mortem/__lib'),
]
for lib_dir in candidate_lib_dirs:
    if lib_dir.exists():
        sys.path.insert(0, str(lib_dir))
        break
sys.path.insert(0, 'P:\\\\\\.claude/skills/gto/lib')
from premortem_io import PreMortemSession, _get_terminal_id
from skill_coverage_detector import _append_skill_coverage

session = PreMortemSession.find_or_create_session()
work_content = session.read_work().strip()
target_key = work_content if work_content else 'unknown'

_append_skill_coverage(
    target_key=target_key,
    skill='/pre-mortem',
    terminal_id=_get_terminal_id(),
    git_sha=None,
)
"
```

### Step 6b: Evidence-Bound Verification (MANDATORY)

Before cleanup, you MUST complete verification. Do NOT write a freeform summary.

1. Run each command from the `verification.commands` frontmatter
2. **Write results to artifact:** `P:\\\\\\.claude/.artifacts/{terminal_id}/pre-mortem/verification.json`
3. Paste each tool's output verbatim with PASS/FAIL status
4. Add NO interpretive claims not directly supported by tool output

**Prohibited:** Line numbers, file contents, or finding details not shown in this turn's tool output.

### Step 7: Cleanup

Session directories persist under `P:\\\\\\.claude/.artifacts/{terminal_id}/pre-mortem/` until manually removed.

## Output Structure

The final critique uses the 7-section structure with severity tags. Render markdown properly — use headings, bold, etc. Do NOT show raw syntax like `**bold**`.

```
## Intent Summary
[2-3 sentences]

## Health Score: XX%

**QA-002 Verification Criteria:**
- ≥80% = Healthy — Low risk, minor improvements possible
- 50-79% = Warning — Significant issues in 2+ domains, address HIGH items first
- <50% = Critical — Systemic problems, do not use without fixes

Health Score is computed as: `100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`, capped at 0-100.
1.1. [HIGH] issue (file:line)
...

## Hidden Assumptions & Fragile Dependencies
2.1. [MEDIUM] issue
...

For contract-heavy reviews, this section must explicitly call out:

- implied field dependencies
- unstated freshness rules
- missing consumer validators
- producer-only success proofs

## Missing Obvious Actions / Best Practices
3.1. [HIGH] issue
...

## Risks and Edge Cases
4.1. [MEDIUM] issue
...

## Concrete Recommendations
5.1. [MEDIUM] specific change
...

## Open Questions / Unknowns
6.1. [LOW] uncertainty
...

## Recommended Next Steps

Organize by domain using the 7 sections as domains. Severity is implied by domain order (domain 1 = most critical). Within each domain, sort sub-items by severity: CRITICAL > HIGH > MEDIUM > LOW.

**Format — RNS / GTO v2 compatible:**

```
1 (DOMAIN) - Brief domain description
  1a: Action → Manual - context (file:line)
  1b: Action → Use /skill - context

2 (DOMAIN) - Brief domain description
  2a: Action → Manual - context

0 — Do ALL Recommended Next Steps
```

**Requirements:**
- Domain headers: `1 (DOMAIN) - description` format
- Sub-items: `1a:`, `1b:`, `2a:`, etc.
- Action format: `- 1a: Action → Manual - context` or `- 1a: Action → Use /skill - context`
- Terminator: `0 — Do ALL Recommended Next Steps`
- No severity tags in sub-items (severity is implied by domain ordering)

**When you respond "0", the skill will begin implementing these fixes — starting with domain 1 items and working through each cluster. This is an execution directive, not a display request.**

## Handling "0 — Do ALL" (Step 8)

**QA-003 "0" Directive:** Responding "0" is an execution directive, not a display request. It means "begin implementing ALL recommended next steps now."

### Step 8 Execution Protocol

**Step 8a: Identify the target**

From work.md, determine what was reviewed:
- If a skill was reviewed, the target is `P:\\\\\\.claude/skills/{skill_name}/`
- If a plan was reviewed, the target is the plan file referenced
- If a module was reviewed, the target is that module's path

**Step 8c: Execute domain 1 items first, then domain 2, etc.**

Start with all items in domain 1. For each:
1. Read the relevant source file
2. Make the minimal fix
3. If tests exist, run them
4. Verify the fix

**Step 8d: Continue through subsequent domains**

After all domain 1 items complete, proceed through domain 2, etc.

**Step 8e: Report per-item status**

- `DONE` if implemented and verified
- `DEFERRED` if blocked by dependency
- `N/A` if the item is a documentation/process gap

### Constraints

- **Minimal changes**: Only fix what the pre-mortem identified
- **Verify before claiming**: Run relevant tests
- **Do not re-pre-mortem**: If a fix reveals new issues, mark DEFERRED
- **Authorship**: All fixes are your own commits

## Deprecation Notice

`/adversarial-review` is deprecated. `/pre-mortem` with adaptive dispatch provides the same capability with better phase structure. Use `/pre-mortem` for all adversarial review work.

## Routing Behavior

`/pre-mortem` may suggest:

- `/verify` when the main remaining issue is lack of proof
- `/reflect` when the pre-mortem exposed reusable workflow lessons

`/pre-mortem` should not rewrite architecture, plans, or implementation ownership boundaries implicitly.
