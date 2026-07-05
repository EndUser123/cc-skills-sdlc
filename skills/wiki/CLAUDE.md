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
| Update | optional topic, --auto flag | stale candidates ranked by age + search frequency | log.md appended on refresh, wiki page rewritten, qmd index updated |

## Graceful Degradation

When `qmd` CLI is unavailable:
- Search falls back to `glob("wiki/**/*.md")` + `grep` content match
- Ingest still works (filesystem write)
- Lint still works (filesystem read)

## Wiki Search Contract (FTS5 safety)

FTS5 operator escaping for hyphenated/punctuated queries (`two-levers`, `foo*bar`) is **fixed at the root** in our forked `qmd.build_fts5_query`. The owned patch lives at `P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/qmd_fts5_patch.patch` and is applied in-place to the installed qmd package. See #1064.

Consequences:

- **Bare `qmd search` is safe** — no caller-side sanitize needed. All invocation paths (Python `QMDWikiBackend`, `wiki_after_write.py`, the `wiki_search.py` wrapper, ad-hoc CLI, the red-team planner prospect pass) go through the one root fix.
- **`wiki_search.py`** is now a thin wrapper retained only for the Windows subprocess capture+forward quirk — not for FTS5 safety.
- **Reinstall protocol**: `pip install --upgrade qmd` (or a Python reinstall) silently loses the patch. Re-apply from the `.patch` file; verify with `python -c "from qmd.core.retrieval import build_fts5_query as f; assert f('two-levers')=='two levers'"`. qmd is pinned to 0.1.1 — do not auto-upgrade.

## Security Notes

- YAML frontmatter uses `yaml.safe_dump` exclusively
- Query length: truncated to 500 chars; non-printables stripped by the base backend
- Path traversal prevention: resolved paths validated against vault root