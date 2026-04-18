# QMD Wiki Conventions

## Schema Conventions

Every wiki page has YAML frontmatter with:
- `tags`: List of tag strings
- `created`: ISO date string (YYYY-MM-DD)
- `sources`: List of source references
- `summary`: One-line description

## Directory Structure

| Path | Purpose |
|------|---------|
| `wiki/entities/` | Entity pages (people, places, tools) |
| `wiki/concepts/` | Concept pages (ideas, patterns, techniques) |
| `sources/` | Immutable raw sources |
| `wiki/comparisons/` | Comparison pages (X vs Y) |

## Log Entries

Ingest log format:
```
## [YYYY-MM-DD] ingest | Title
```

## Page Naming

- Entity pages: `wiki/entities/<name>.md`
- Concept pages: `wiki/concepts/<concept>.md`
- Comparison pages: `wiki/comparisons/<x>-vs-<y>.md`
- Sources: `wiki/sources/<slug>.md`

## Operations

- `ingest`: Fetch source, write to `wiki/sources/` with frontmatter
- `query`: Search by tag/entity/concept using glob+grep fallback
- `lint`: Validate frontmatter schema on wiki pages
- `index`: Build `wiki/index.json` from all wiki pages

## YAML Security

All frontmatter is written using `yaml.safe_dump`. Never use raw YAML strings.
