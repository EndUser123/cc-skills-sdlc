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

**Freshness**: Filesystem mtime is authoritative for wiki page freshness. FTS5 index freshness = `P:/.data/wiki/_state/wiki-index.db` mtime. If index mtime < vault mtime → stale, rebuild triggered (SessionStart hook `~/.grok/hooks/scripts/search_wiki_index_refresh.py`).

**Auto-linking**: On ingest, after writing the page, `wiki_after_write.py` extracts keywords from title+summary and finds top-K (K=5) neighbor pages via ripgrep over the vault. `[[wikilinks]]` are injected into `## Auto-related`. Best-effort — keyword overlap determines candidates (QMD semantic similarity retired with qmd, 2026-07-28; evaluated as marginal-or-negative for this corpus).

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
| Update | optional topic, --auto flag | stale candidates ranked by age + search frequency | log.md appended on refresh, wiki page rewritten, FTS5 index updated |

## Graceful Degradation

When the FTS5 engine (`P:/.agents/scripts/wiki_search.py`) or its index is unavailable:
- Search falls back to `glob("wiki/**/*.md")` + `grep` content match
- Ingest still works (filesystem write; index step reports failure, pipeline continues)
- Lint still works (filesystem read)

## Wiki Search Contract (canonical FTS5 engine)

**2026-08-16: the pip `qmd` package is uninstalled; all patch/reinstall machinery below is retired.** Ranked search = `P:/.agents/scripts/wiki_search.py` (stdlib sqlite3 FTS5, no external dependency) over `P:/.data/wiki/_state/wiki-index.db`.

- **FTS5 operator safety is built in**: the engine exports `sanitize_fts5_query` (per-token quoting — the fix formerly maintained as `qmd_fts5_patch.patch`, ported verbatim). Every engine call path is safe; callers need no local sanitize.
- **No patches, no reinstall protocol, no pinning**: the engine is workspace-owned source at `P:/.agents/scripts/`. The `.patch` files formerly in `cc-skills-utils/__lib/` are deleted.
- **Vector/semantic search is intentionally absent**: evaluated as marginal-or-negative for the ~1260-concept corpus (engine docstring, 2026-07-28 pivot decision). If corpus scale changes materially, re-evaluate — do not silently reintroduce embeddings.
- **Index freshness**: `wiki_ingest.py --post-write` adds each written page; the SessionStart hook rebuilds when stale (>24h or concept-count change). Full rebuild ≈ 6s.

## Security Notes

- YAML frontmatter uses `yaml.safe_dump` exclusively
- Query length: truncated to 500 chars; non-printables stripped by the base backend
- Path traversal prevention: resolved paths validated against vault root