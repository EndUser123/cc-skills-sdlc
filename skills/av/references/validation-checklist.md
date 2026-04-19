# Validation Checklist

Run this checklist after analyzing a skill. Sections 0-F cover classification, structure, evidence, hooks, and governance.

---

## Section 0: Skill Type Classification

| Type | Characteristics | Required Elements |
|------|-----------------|-------------------|
| **EXECUTION** | Runs external tool/CLI, delegates to subagent, produces tool output | Full execution directive, anti-substitution block, execution registry entry |
| **KNOWLEDGE** | Provides reference info, definitions, patterns | Context sections, no execution required |
| **PROCEDURE** | Multi-step workflow with decision points | Steps with success criteria, phase gates |

- [ ] Skill type identified: EXECUTION / KNOWLEDGE / PROCEDURE
- [ ] If EXECUTION: Requires bash/task/external tool invocation
- [ ] If EXECUTION: Add to SKILL_EXECUTION_REGISTRY (see below)

---

## Section A: Execution Directive

- [ ] Directive in first 30 lines
- [ ] "EXECUTION DIRECTIVE" header
- [ ] Exact commands with FULL paths (not relative)
- [ ] MANDATORY block present with numbered steps
- [ ] DO NOT block with anti-substitution language:
  - [ ] "Provide your own analysis instead of running the command"
  - [ ] "Summarize this skill documentation"
  - [ ] "Substitute your capabilities for the external tool"
  - [ ] "Consider task complete until [tool] output is captured"
- [ ] DEFAULT behavior specified (what happens with no arguments)
- [ ] Failure handling: "Report exact error, do NOT fabricate results"
- [ ] Imperative voice throughout

---

## Section B: Structure

- [ ] Prose:Code <= 2:1
- [ ] No documentary phrasing
- [ ] Quick reference table
- [ ] Runnable examples
- [ ] Error handling

---

## Section C: Evidence

- [ ] No excuse patterns
- [ ] No temporal hedging
- [ ] No environmental excuses

---

## Section D: Hook Detection

- [ ] File ops (Write/Edit) -> PostToolUse validator
- [ ] Multi-phase -> State transitions
- [ ] Bash/Task -> Execution gates

---

## Section E: Execution Registry (EXECUTION skills only)

Location: `P:/.claude/hooks/StopHook_skill_execution_gate.py`

- [ ] Skill added to `SKILL_EXECUTION_REGISTRY` dict
- [ ] `tools` list specifies required execution tools (Bash, Task, Read, WebSearch, etc.)
- [ ] `pattern` regex matches expected command (or `None` if any tool use counts)
- [ ] `output_markers` list (optional) for output validation

**Registry Entry Format:**
```python
"{SKILL_NAME}": {
    "tools": ["Bash", "Task"],      # Tools that count as "executed"
    "pattern": r"script\.py|{SKILL_NAME}",  # Command pattern (None = any)
    "output_markers": ["expected"],  # Optional output validation
},
```

**Skip registry for:**
- KNOWLEDGE skills (reference/documentation only)
- Skills that don't delegate to external tools
- Skills already in `KNOWLEDGE_SKILLS` set

---

## Section F: Layer 1 Governance (PROCEDURE skills)

Skills with structured workflows (stages, phases, templates) should declare governance markers
to prevent Claude from bypassing the skill with its own interpretation.

**When to add governance:**
- Skill has numbered stages/phases (e.g., "Stage 0:", "Phase 1:")
- Skill has template selection (e.g., "Template: fast")
- Skill output has distinctive structural markers

**Check SKILL.md for stage/phase patterns:**
```bash
grep -E "Stage [0-9]|Phase [0-9]|Step [0-9]|Template:" SKILL.md
```

- [ ] If skill has stages/phases -> Add `governance` block to frontmatter
- [ ] `layer1_enforcement: true` if bypass prevention needed
- [ ] `usage_markers` list with distinctive output markers

**Governance Frontmatter Format:**
```yaml
governance:
  layer1_enforcement: true
  usage_markers:
    - "Stage 0:"
    - "Stage 1:"
    - "Template:"
    - "PREREQUISITE DETECTED"
```

**Marker Selection Guidelines:**
- Choose markers that ONLY appear when following the skill workflow
- Avoid generic words Claude might use anyway
- Include stage/phase headers, distinctive labels, structural markers
- 5-10 markers is typically sufficient

**Skip governance for:**
- Simple utility skills (commit, push, etc.)
- Skills that delegate entirely to external tools
- Skills with no structured workflow
