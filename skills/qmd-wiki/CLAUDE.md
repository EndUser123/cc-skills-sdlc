---
type: CLAUDE.md
title: QMD Wiki Skill
created: 2026-04-13
tags: [qmd, wiki, skill]
summary: QMD-based wiki integration for Claude Code wiki operations
---

# QMD Wiki Skill

## Purpose

QMD-based wiki integration for the wiki skill — provides persistent knowledge management via Obsidian-compatible Markdown pages with YAML frontmatter.

## Operations

| Command | Description |
|---------|-------------|
| `qmd ingest` | Fetch source, write to `wiki/sources/` with frontmatter |
| `qmd query` | Search by tag/entity/concept using glob+grep fallback |
| `qmd lint` | Validate frontmatter schema on wiki pages |
| `qmd update <collection>` | Rebuild search index (use `LANG=en_US.UTF-8` on Windows) |
| `qmd index` | Rebuild full vault index |

## Vault Location

`P://.data/wiki`

## Directory Structure

| Path | Purpose |
|------|---------|
| `wiki/entities/` | Entity pages (people, places, tools) |
| `wiki/concepts/` | Concept pages (ideas, patterns, techniques) |
| `wiki/comparisons/` | Comparison pages (X vs Y) |
| `sources/` | Immutable raw sources |

## Schema Conventions

Every wiki page has YAML frontmatter:
- `type`: `concept`, `entity`, or comparison
- `title`: Display name
- `created`: ISO date (YYYY-MM-DD)
- `tags`: List of tag strings
- `summary`: One-line description
- `relations`: Optional typed wikilinks (`supports`, `contradicts`, `refines`, `supersedes`, `related`)

## Typed Wikilinks

```markdown
[[Page Name]]@supports    -- Page provides supporting evidence
[[Page Name]]@contradicts -- Page contradicts this one
[[Page Name]]@refines     -- Page refines or clarifies
[[Page Name]]@supersedes -- Page supersedes this one
[[Page Name]]@related    -- General relationship
```

## Page Naming

- Entity pages: `wiki/entities/<name>.md`
- Concept pages: `wiki/concepts/<concept>.md`
- Comparison pages: `wiki/comparisons/<x>-vs-<y>.md`
- Sources: `wiki/sources/<slug>.md`

## Ingest Workflow

1. Compute SHA256 of source content
2. Check `log.md` for existing hash — skip if duplicate
3. Write page with YAML frontmatter
4. Run `qmd update wiki` (Windows: `$env:LANG='en_US.UTF-8'`)
5. Query vault for related pages → inject `[[wikilinks]]` into new page
6. Append entry to `log.md`

## Log Entry Format

```markdown
## [YYYY-MM-DD] ingest | Title
Source: <source path or URL>
Content: <brief description>
Page: <wiki page path>
Hash: <sha256>
```

## YAML Security

All frontmatter written via `yaml.safe_dump`. Never use raw YAML strings.

## Graceful Degradation

If QMD is unavailable:
- Fall back to direct file operations (read/write markdown)
- Wikilink injection skipped
- Search limited to grep

## Notes

- Speculative linking: create `[[wikilinks]]` to non-existent pages intentionally — "red links" in Obsidian, resolved when target page is later ingested
- Hash-based deduplication prevents re-processing identical sources