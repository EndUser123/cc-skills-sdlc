---
name: qmd-wiki
version: "1.0.0"
status: "draft"
category: knowledge
enforcement: advisory
description: Ingest, query, lint, and index QMD wiki pages from an Obsidian vault.
workflow_steps:
  - ingest
  - query
  - lint
  - index
---

# qmd-wiki

**Goal:** Manage a QMD wiki — ingest sources, query pages, lint frontmatter, and build an index.

**Graceful degradation:** When `qmd` is unavailable, operations fall back to glob+grep over the vault path.

---

## Configuration

Read from `settings.json`:

| Key | Description |
|-----|-------------|
| `OBSIDIAN_VAULT_PATH` | Root path of the Obsidian vault |
| `QMD_WIKI_SOURCES` | List of source globs to ingest |
| `QMD_WIKI_SCOPE` | wiki scope subdirectory (default: `wiki/`) |

---

## Operations

### ingest

Ingest a source file or URL into the wiki.

1. Fetch source content
2. Parse YAML frontmatter
3. Write to `wiki/sources/<slug>.md` with frontmatter + content
4. Log entry: `## [YYYY-MM-DD] ingest | Title`

**YAML frontmatter security:** All frontmatter is written using `yaml.safe_dump`. No raw YAML strings.

### query

Search wiki pages by tag, entity, or concept.

1. Glob `wiki/**/*.md`
2. Parse frontmatter with `yaml.safe_load`
3. Filter by tag/entity/concept
4. Return matching pages with summaries

**Fallback:** If `qmd` unavailable, use glob+grep over `OBSIDIAN_VAULT_PATH`.

### lint

Validate frontmatter schema on wiki pages.

Checks:
- Required fields: `tags`, `created`, `sources`, `summary`
- `tags` is a list
- `sources` is a list of source references
- `summary` is a string

### index

Build a searchable index of all wiki pages.

Output: `wiki/index.json` with page titles, tags, entities, concepts, and paths.

---

## Directory Structure

```
wiki/
  entities/      # Entity pages (people, places, tools)
  concepts/     # Concept pages (ideas, patterns, techniques)
  sources/      # Immutable raw sources (ingest target)
  comparisons/  # Comparison pages (X vs Y)
  index.json    # Search index
```

---

## Frontmatter Schema

Every wiki page requires:

```yaml
tags:
  - tag1
  - tag2
created: YYYY-MM-DD
sources:
  - source-ref
summary: One-line description of the page content.
```

Optional fields:
- `entity`: Entity type (person, place, tool, etc.)
- `concept`: Concept classification
