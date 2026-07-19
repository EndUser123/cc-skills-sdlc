---
name: wiki
description: Persistent knowledge system using Obsidian wiki + QMD search
required_artifacts: []
response_requirements: {}
contract_type: workflow-execution
---
# /wiki — Claude Code Wiki Skill

> **All conventions and operational procedures live at `P:/.data/wiki/SCHEMA.md`.**
> Read SCHEMA.md §10 for Ingest / Query / Lint / Update / Signal-extract procedures.
> This file lists only Claude-Code-specific notes.

## Purpose

Persistent knowledge management: LLM maintains an Obsidian wiki (ingest/synthesize/lint), searchable via QMD CLI, exposed as `search-research` backend `QMD_WIKI`.

## This host's automation

**Automated periodic linting**: Phase 1 of `/wiki lint` is included in the
`/main` health check workflow on every `/main` invocation; `/main --fix` applies
the safe-subset through a **needs-based gate** — it re-runs only when the vault
mtime fingerprint changed since the last fix (sentinel at
`P:/.claude/.artifacts/_main/wiki_autofix_fingerprint.txt`).

## Query backend

Primary search path: `search-research --mode quick "<question>"` (QMD_WIKI backend).
Grep fallback under `P:/.claude/hooks/__lib/` or the relevant plugin tree.

## Verification (cold-start)

```bash
# Since-intersect test suite:
python -m pytest plugins/cc-skills-sdlc/skills/wiki/tests/test_since_intersect.py -q
# Health check smoke test:
python plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py --stale --max-age 90 --json
```

## Thought Partner Addendum

When a `/wiki` session surfaces a broader recurring storage / persistence
pattern, a memory-routing gap, or a vault-conventions verification gap —
not for ordinary single-page ingest or query work — emit a Thought Partner
Addendum (TPA). Each item carries `observation`, `why_it_matters`,
`evidence`, `recommended_action`, `urgency: now | later | watch`. Omit the
section for routine ingest/query output. Canonical contract at
`debrief/references/thought-partner-addendum.md`. The TPA is prompt-advisory only.

## Partner Posture

`/wiki`'s posture is **Memory / Persistence Partner**. `/wiki` stores approved
durable lessons only — it does NOT auto-ingest candidates, does NOT silently
write to the vault on inferred intent, and routes storage decisions to the
calling command or explicit user confirmation. Posture is prompt-advisory.

## Quick reference to SCHEMA.md

- **Page format / frontmatter** (§2-3): includes `verification:`, `cognitive_load`, `host:`, `agent:`
- **Quality Gate** (§4)
- **Link density ≥3 advisory** (§5)
- **Log protocol** (§6)
- **Typed wikilinks** (§7)
- **Speculative linking** (§8)
- **Shared scripts** (§9)
- **Operations: Ingest / Query / Lint / Update / Signal-extract / Index / Init** (§10)
- **Recommended cadence** (§11)
- **Evidence-first principles** (§12)
- **Key principles** (§13)
