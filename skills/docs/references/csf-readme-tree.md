# CSF README Tree Structure

The CSF project uses a hierarchical README structure for documentation:

```
P:/
├── README.md                    # Main CSF documentation hub
├── __csf/
│   └── README.md                # Project-specific (modules, commands)
├── packages/
│   ├── README.md                # Packages catalog
│   └── */README.md              # Individual package docs
├── .claude/
│   ├── README.md                # Claude config overview (if exists)
│   ├── hooks/
│   │   └── README.md            # Hooks catalog
│   └── skills/
│       └── README.md            # Skills index
└── docs/
    └── README.md                # Design docs index (if exists)
```

## Documentation Update Rules

When modifying files in these locations:

| Modified Path | Check Documentation |
|---------------|-------------------|
| `P:\*` (root files) | `P:\README.md` (main hub) |
| `P:\__csf\*` | `P:\__csf\README.md` |
| `P:\packages\*` | `P:\packages\README.md` + specific package README |
| `P:\.claude\hooks\*` | `P:\\.claude\hooks\README.md` |
| `P:\.claude\skills\*` | `P:\.claude\skills\README.md` |

## Cross-Reference Updates

When creating NEW documentation:
- Update parent README's "Documentation" section
- Add to appropriate catalog/index
- Maintain tree structure consistency

**Example:** Creating `packages/new-package/` -> Update `P:\packages\README.md` AND `P:\README.md`

## Skill-Specific Documentation

**When modifying `SKILL.md` in a skill directory:**

Check for skill-specific README and ensure consistency:

| Modified File | Also Check | Update Rule |
|---------------|------------|-------------|
| `.claude/skills/<name>/SKILL.md` | `.claude/skills/<name>/README.md` | If SKILL.md adds new workflow sections, update README.md |
| `.claude/skills/<name>/SKILL.md` | `.claude/skills/<name>/README.md` | If SKILL.md changes intent detection, update README.md examples |

**Action when SKILL.md is modified:**
1. Read both `SKILL.md` and `README.md` in the skill directory
2. Compare: Does SKILL.md have new sections not reflected in README.md?
3. If YES: Update README.md to include new sections (Intent Detection, Workflows, Constraints, etc.)
4. If README.md is missing: Create it with summary of key sections from SKILL.md

**Pattern:** When enhancing a skill's capabilities, ensure the companion README reflects the full workflow.
