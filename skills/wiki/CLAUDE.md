---
name: wiki-architecture
description: Wiki skill architecture and schema conventions
---

# Wiki Architecture

## Identity Model

`vault_page_id` = vault-relative path (e.g. `wiki/entities/session-chain.md`). Globally unique within vault namespace.

## State Model

**Ordering**: mtime-based (file modification time). All operations sequenced by wall-clock mtime.

**Dedupe**: Page identity = vault-relative path. LLM is sole writer. Log entries deduplicated by `[YYYY-MM-DD] ingest | {title}` prefix.

**Freshness**: Filesystem mtime is authoritative for wiki page freshness. QMD index freshness = QMD index file mtime. If index mtime < vault mtime → stale, rebuild triggered.

**Auto-linking**: On ingest, after writing the page, QMD is queried with the new page's title+summary to find top-K (K=5) semantically similar existing pages. `[[wikilinks]]` to those pages are injected into a `## Related` section in the new page. This is best-effort — QMD similarity scoring determines candidates.

**Speculative linking**: Links to non-existent pages are kept (Obsidian "red links"). They resolve when the target page is ingested. Never suppress a wikilink because the target doesn't exist yet.

**Typed wikilinks**: `[[Page]]@supports`, `[[Page]]@contradicts`, etc. Relationships also recorded in frontmatter `relations:` field.

**Auto-save**: High-value query syntheses are saved directly to the wiki without asking. Only ask if synthesis is uncertain.

## Operations Contract

| Operation | Input | Output | Side Effects |
|-----------|-------|--------|--------------|
| Ingest | file path, URL, or text | wiki page written with auto-links | log.md appended, wikilinks injected, index.md updated |
| Query | question string | synthesized answer | optionally writes wiki page |
| Lint | none | health report | none (read-only) |
| Index | none | index.md rebuilt | index.md written |

## Graceful Degradation

When `qmd` CLI is unavailable:
- Search falls back to `glob("wiki/**/*.md")` + `grep` content match
- Ingest still works (filesystem write)
- Lint still works (filesystem read)

## Security Notes

- YAML frontmatter uses `yaml.safe_dump` exclusively
- Query sanitization: limited to 500 chars, strips non-printable
- Path traversal prevention: resolved paths validated against vault root