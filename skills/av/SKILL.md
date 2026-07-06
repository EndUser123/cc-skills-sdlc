---
name: av
description: "DEPRECATED entry — use /skill-audit generate-hooks. Classifies skill type (EXECUTION/KNOWLEDGE/PROCEDURE) + scores hook need + generates a complete hook package (templates: PostToolUse validator, state manager, PreToolUse gate, PostToolUse transition, + 3 SKILL.md scaffolds)."
version: "2.0.0"
status: "stable"
category: analysis
triggers:
  - /av
workflow_steps: []
enforcement: advisory
---

# /av — DEPRECATED entry (engine retained)

`/av` is now `/skill-audit generate-hooks`:

```
/skill-audit generate-hooks <path>     # classify + score + recommend + write hook package
```

The `/av` **engine is unchanged** — `/skill-audit generate-hooks` reads these reference files directly:

- 7 hook templates (PostToolUse validator, state manager, PreToolUse gate, PostToolUse transition, + EXECUTION/KNOWLEDGE/PROCEDURE SKILL.md scaffolds) → `references/hook-templates.md`
- 6-section validation checklist (Skill Type / Execution Directive / Structure / Evidence / Hook Detection / Execution Registry / Layer 1 Governance) → `references/validation-checklist.md`
- Output packages + architecture (Simple / Hooks / Both; why two skills; when NOT to add hooks) → `references/output-package-and-architecture.md`
- Integration checklist (validator example, generated checklist, frontmatter-vs-legacy, testing + rollback) → `references/integration-checklist.md`

**Classification + scoring rubric (canonical):**
- Type: `EXECUTION` (external tool/CLI/subagent) / `KNOWLEDGE` (reference) / `PROCEDURE` (multi-step workflow with decision points).
- Complexity: multi-phase (+3), state transitions (+3), critical enforcement (+2), single command (−2), reference-only (−2). Score ≥1 → hooks recommended; ≤0 → simple recommended.

`/av` remains the **source of truth** for its hook templates + validation checklist — `/skill-audit` reads them, does not vendor. This stub entry will be removed after one release cycle; the `references/` directory stays as the canonical template library.

The templates still emit the standard hook frontmatter shape:

```yaml
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/{skill}/hooks/PreToolUse_{skill}_gate.py\""
          timeout: 10
  PostToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/{skill}/hooks/PostToolUse_{skill}_validator.py\""
          timeout: 10
```
