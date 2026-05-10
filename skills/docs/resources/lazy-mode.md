# Lazy Mode (Default)

**Just type `/docs` and it figures out what needs updating.**

```bash
/docs
```

## What Lazy Mode Does

1. **Checks your working tree** (git status - uncommitted changes only)
2. **Checks for missing core documentation** (CLAUDE.md, README.md, ARCHITECTURE.md, CHANGELOG.md)
3. **Analyzes recent chat history** (what you discussed in THIS session)
4. **Cross-references documentation** (which docs mention your changed files)
5. **Auto-applies documentation updates** (default behavior)
6. **Shows summary of applied changes**

## Example Output

```
📋 Documentation Update Suggestions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files changed in your working tree:
  ✓ src/yt_fts/download/batch_downloader.py
  ✓ src/yt_fts/core/cli.py

Documentation affected:
  → ARCHITECTURE.md mentions "batch_downloader" (line 45)
  → DEVELOPING.md mentions "cli.py" (line 16)
  → CLAUDE.md mentions "Downloads:" section

Session context detected:
  • Added dual-sink logging integration
  • New FR-13 requirement in PRD
  • Updated stats format for channel display

Suggested updates:
  1. ARCHITECTURE.md → Add dual-sink logging section
  2. DEVELOPING.md → Update logging configuration
  3. CHANGELOG.md → Add v1.9.5 entry

🚀 Auto-applied changes:
  ✓ Updated CHANGELOG.md for v1.9.5
  ✓ Added docstring templates to batch_downloader.py

Run: /docs --verbose  (show detailed analysis)
```

## Dry Run Mode

`/docs --dry-run` shows what documentation would be updated WITHOUT making changes:

```
📋 Documentation Dry Run

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files changed in your working tree:
  ✓ .claude/hooks/SESSION_COMPACTION.md

📋 MISSING CORE DOCUMENTATION:
  ❌ .claude/hooks/CLAUDE.md
     → Run: /init .claude/hooks

  ❌ .claude/hooks/CHANGELOG.md
     → Consider creating for version history

  ✓ .claude/hooks/README.md exists

Documentation affected:
  → README.md mentions "session compaction" (could add link)

Recommended actions:
  1. Run /init .claude/hooks to create CLAUDE.md
  2. Add SESSION_COMPACTION.md link to README.md
  3. Consider creating CHANGELOG.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dry run complete - no files modified
```

## Core Documentation Checks

Dry run mode specifically checks for these required files in modified directories:

| File | Purpose | Required For |
|------|---------|--------------|
| `CLAUDE.md` | Module context for Claude Code | All code modules |
| `README.md` | General documentation | All public packages |
| `ARCHITECTURE.md` | System design | Complex systems |
| `CHANGELOG.md` | Version history | Libraries/packages |

## CSF README Tree Structure

The CSF project uses a hierarchical README structure for documentation:

```
P:\\\\\\
├── README.md                    # Main CSF documentation hub
├── __csf/
│   └── README.md                # Project-specific (modules, commands)
├── packages/
│   ├── README.md                # Packages catalog
│   └── */README.md              # Individual package docs
├── .claude/
│   ├── README.md                # Claude config overview
│   ├── hooks/
│   │   └── README.md            # Hooks catalog
│   └── skills/
│       └── README.md            # Skills index
└── docs/
    └── README.md                # Design docs index (if exists)
```

### Documentation Update Rules

When modifying files in these locations:

| Modified Path | Check Documentation |
|---------------|-------------------|
| `P:\\\\\\*` | `P:\\\\\\README.md` (main hub) |
| `P:\\\\\\__csf/*` | `P:\\\\\\__csf/README.md` |
| `P:\\\\\\packages/*` | `P:\\\\\\packages/README.md` + specific package README |
| `P:\\\\\\.claude/hooks/*` | `P:\\\\\\.claude/hooks/README.md` |
| `P:\\\\\\.claude/skills/*` | `P:\\\\\\.claude/skills/README.md` |

### Cross-Reference Updates

When creating NEW documentation:
- Update parent README's "Documentation" section
- Add to appropriate catalog/index
- Maintain tree structure consistency

Example: Creating `packages/new-package/` → Update `P:\\\\\\packages/README.md` AND `P:\\\\\\README.md`

## How It Filters Your Work (Not Other Devs')

In a 6-developer workspace, lazy mode only sees **YOUR changes**:

| Source       | What It Captures       | What It Ignores         |
| ------------ | ---------------------- | ----------------------- |
| Git status   | Your uncommitted files | Other devs' commits     |
| Chat history | THIS session only      | Other conversations     |
| File mtimes  | Files YOU touched      | Files changed by others |

## Options

```bash
/docs                    # Show suggestions (default)
/docs --apply            # Auto-generate documentation updates
/docs --verbose          # Show detailed analysis with evidence
/docs --dry-run          # Show what would be updated
/docs --scope {dir}      # Limit analysis to specific directory
```
