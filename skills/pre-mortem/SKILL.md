---
name: pre-mortem
disable-model-invocation: true
description: "DEPRECATED entry — use /red-team pre-mortem. 3-phase adaptive adversarial critique (triage+specialist → meta-critique → synthesis) with Health Score + RNS + blinded consumer-contract review."
version: "2.1.1"
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
enforcement: advisory
parallel_agents: true

# Evidence-bound verification (anti-confabulation)
verification:
  commands:
    - description: "Confirm p3.md synthesis exists"
      tool: "Bash"
      args:
        command: 'ls -la "P://.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p3.md" 2>/dev/null | tail -1 || echo "NO P3 FOUND"'
    - description: "Confirm Phase 1 findings exist"
      tool: "Bash"
      args:
        command: 'ls -la "P://.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p1_findings.md" 2>/dev/null | tail -1 || echo "NO P1 FOUND"'
    - description: "Confirm Phase 2 meta-critique exists"
      tool: "Bash"
      args:
        command: 'ls -la "P://.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p2.md" 2>/dev/null | tail -1 || echo "NO P2 FOUND"'
    - description: "Count findings with severity levels"
      tool: "Bash"
      args:
        command: 'grep -cP "\\[(CRITICAL|HIGH|MEDIUM|LOW)\\]" "P://.claude/.artifacts/$WT_SESSION/pre-mortem/pre-mortem-*/p3.md" 2>/dev/null || echo "0"'
  summary_mode: evidence_only
  expected_artifacts:
    - "P://.claude/.artifacts/{terminal_id}/pre-mortem/{session_id}/p1_findings.md"
    - "P://.claude/.artifacts/{terminal_id}/pre-mortem/{session_id}/p2.md"
    - "P://.claude/.artifacts/{terminal_id}/pre-mortem/{session_id}/p3.md"
---
# /pre-mortem — DEPRECATED entry (engine retained)

`/pre-mortem` is now `/red-team pre-mortem`:

```
/red-team pre-mortem <target>     # 3-phase adaptive critique: triage+specialist → meta-critique → synthesis
/red-team pre-mortem <target>     # Health Score (0–100) + RNS-format output + blinded consumer-contract review
```

The pre-mortem **engine is unchanged** — `/red-team pre-mortem` selects it. The 3-phase pipeline runs against the same artifacts (`p1_findings.md`, `p2.md`, `p3.md`) under the same session directory, with the same Health Score formula (`100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`) and the same "0 — Do ALL" execution directive. Engine internals preserved verbatim:

- Phase prompts (triage+dispatch, meta-critique, synthesis) → `references/phases/p1_initial_review.md`, `p2_meta_critique.md`, `p3_synthesis.md`
- Shared method, evidence contract, output contract, review lenses, decision model → `references/`
- Session I/O + dispatch manifest → `__lib/premortem_io.py`
- Specialist registry: `adversarial-{security,performance,logic,state-machine,io-validation,compliance,quality,testing,critic,rca}`
- Blinded consumer-contract review (producer promises vs consumer requirements vs validator location)
- Failure-mode self-check prompts (15 internal questions, surfaced only when genuinely blocked)
- External adapters: `.codex/SKILL.md`, `.pi/pre-mortem-contract.md`
- Boundary hooks + skill.json → `hooks/`, `skill.json`
- Verification block (above) is the live completion gate — `p1/p2/p3` artifacts must exist before the skill completes

`/pre-mortem` remains the **source of truth** for its phase prompts + blinded-review method + adapters — `/red-team` routes, does not vendor. The `verification` block on this skill stays live so direct `/pre-mortem` invocations still enforce artifact completion; `/red-team pre-mortem` inherits the same phase pipeline. This stub entry will be removed after one release cycle; the engine directory (`references/`, `__lib/`, `hooks/`, `.codex/`, `.pi/`) stays.

`/adversarial-review` (the deprecated agent-pipeline this skill already absorbed) remains routed here for historical compatibility — use `/red-team pre-mortem` for adaptive dispatch, `/red-team adversarial` for external-LLM divergence.
