# Output Package Example & Architecture

## Output Package Format

Claude analyzes complexity and generates options:

```
COMPLEXITY ANALYSIS:
- Multi-phase workflow: Yes (+3)
- State transitions: Yes (+3)
- Critical enforcement: Yes (+2)
- Single command: No
- Score: 8 → RECOMMEND: HOOKS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPTION 1: SIMPLE (Instructions Only)

Files:

Description: Clear instructions, no enforcement. Like /tdd.
Reversibility: 1.0 (trivial)

Use when: Simple workflow, instructions sufficient

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPTION 2: HOOKS (Separate Skill + Enforcement)

Files:
6. INTEGRATION_CHECKLIST.md

SKILL.md frontmatter includes:
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
  PostToolUse:
    - matcher: "Bash"
      hooks:
        - type: command

Description: Instructions + enforcement. Like /v.

Use when: Multi-phase, strict enforcement, state transitions


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECOMMENDATION: HOOKS (Option 2)

Reason: Multi-phase (+3), state transitions (+3), enforcement (+2) = score 8.
Hooks prevent phase skipping and ensure order.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPTION 3: BOTH (Two Skills Created)

Creates both Simple and Hooks skills as separate directories:

Use when: Want to try Simple first, switch to Hooks if needed.

Choose: 1 (simple), 2 (hooks), or 3 (both)?
```

**Hook location:** `.claude/skills/{skill}-hooks/hooks/` (separate skill per best practice)

---

## Architecture: Why Two Skills?

**Problem with conditional hooks (feature flag approach):**

PreToolUse gates CAN check for `--hooks` flag in user commands, but PostToolUse hooks CANNOT:
- PreToolUse sees `tool_input` (the command user typed)
- PostToolUse only sees `tool_response` (result after execution)
- No way for PostToolUse to know if user originally typed `--hooks`

**Result:** Mixed enforcement
- PreToolUse → conditional (enforces only if `--hooks`)
- PostToolUse → always runs (cannot be conditional)

**Two-skill solution (clean separation):**

```
P://.claude/skills/
├── main/              # Simple mode (no hooks)
└── main-hooks/        # Hooks mode (all hooks active)
```

**Benefits:**
- Both PreToolUse AND PostToolUse can be fully enforced
- No conditional logic complexity
- Clear separation — user knows which mode they're in
- Both skills coexist, user chooses per-session

**Best practice:** Use two separate skills when you need full enforcement control.

---

## When NOT to Add Hooks

**Skip hooks entirely for:**
- KNOWLEDGE skills (reference-only, no execution)
- Simple single-command skills with no state
- Skills where instruction-following is sufficient
- Exploratory/research skills with flexible paths

**Skip execution registry for:**
- Skills that don't delegate to external CLIs/tools
- Skills where Claude's own analysis IS the output
- Skills already in KNOWLEDGE_SKILLS set in the gate

**Complexity score guide:**
```
Score ≤ 0  → SIMPLE mode, no hooks needed
Score 1-3 → Optional hooks, user preference
Score ≥ 4 → HOOKS recommended for reliability
```

**Examples of skills that DON'T need hooks:**
- `/explain` - Claude provides explanation
- `/brainstorm` - Flexible exploration
- `/summarize` - Single-step analysis

**Examples of skills that DO need hooks:**
- `/tdd` - Multi-phase with strict ordering
- `/rca` - External tool delegation
- `/deploy` - Critical enforcement needed
- `/v` - State transitions required
