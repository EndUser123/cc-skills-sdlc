---
name: wiki
description: Persistent knowledge system using Obsidian wiki + QMD search
version: 1.0.0
type: skill
enforcement: none
workflow_steps:
  - ingest: "Accept source (file/URL/text) or scan ~/Downloads for new files (default: ingest all)"
  - query: "Accept question, search wiki via QMD_WIKI backend, synthesize answer"
  - lint: "Health-check wiki for contradictions, orphans, missing cross-refs"
  - index: "Rebuild index.md catalog from current wiki state"
---

# /wiki — Obsidian Wiki + QMD Search Skill

## Purpose

Persistent knowledge management: LLM maintains an Obsidian wiki (ingest/synthesize/lint), searchable via QMD CLI, exposed as `search-research` backend `QMD_WIKI`.

## Operations

### Ingest

Accept source (file path, URL, or text blob) → LLM reads source → **compute SHA256 hash** → **check log.md for existing hash (skip if duplicate)** → writes/updates wiki page with YAML frontmatter → **runs `qmd update <collection>`** (with English locale: `$env:LANG='en_US.UTF-8'`) to keep search index fresh → **searches vault for related pages → injects `[[wikilinks]]` into page body** → appends entry to `log.md`

**URL handling with Crawl4AI**: When a URL is provided (starts with `http://` or `https://`), invoke the `/crawl` workflow:
```bash
/crawl <url> --max-pages 5 --collection wiki
```
The crawl skill handles all URL fetching, deduplication, wikilinks, and logging. Skip manual URL fetching — let the crawl skill handle it.

**Hash-based deduplication**: Before ingesting, compute SHA256 of file content. If hash already exists in `log.md`, skip the ingest (already processed). Log entry includes hash for traceability.

**Auto-linking phase**: After writing the page, query QMD for semantically similar existing pages using the new page's title and summary. Inject `[[Page Name]]` links to top-K (default K=5) related pages into the new page's body under a `## Related` section.

**Speculative linking**: When ingesting, if the content references pages that don't exist yet, create `[[wikilinks]]` to those pages anyway — they become "red links" in Obsidian. This is intentional: future ingest of those pages will resolve the links automatically. Never suppress a link because the target doesn't exist.

**Typed wikilinks**: For explicit relationships, use typed wikilink syntax:
- `[[Page]]@supports` — Page provides supporting evidence
- `[[Page]]@contradicts` — Page contradicts this one
- `[[Page]]@refines` — Page refines or clarifies this one
- `[[Page]]@supersedes` — Page supersedes this one
- `[[Page]]@related` — general relationship

When using typed wikilinks, also record the relationship in the page's frontmatter under `relations:`:
```yaml
relations:
  - target: wiki/entities/SomePage
    type: supports
    reciprocal: contradicts  # the other page references this one
```

**No source provided — scan downloads**: When called without a source (`/wiki ingest`), scans `~/Downloads` for new markdown files and presents a selectable list. Default is `0` = ingest all.

**Workflow (no source):**
1. `find ~/Downloads -name "*.md" -newer <last_check_file>` — list new files
2. For each file, show: filename, size, usefulness keywords
3. Present numbered list — user selects (default: `0` = all)
4. Ingest selected files via the standard Ingest pipeline

**Usefulness keywords:**
- `claude code`, `hook`, `stop`, `pretool`, `posttool`, `userprompt` → hooks-related
- `test`, `pytest`, `flaky`, `timeout` → testing
- `session`, `transcript`, `jsonl`, `compact`, `history` → session-management
- `arch`, `adr`, `design`, `architecture` → architecture
- `subagent`, `agent`, `multi-agent` → agents
- `discovery`, `search`, `explore` → discovery patterns
- `python`, `windows` → python/windows

**Selection format:**
```
/wiki ingest
[0] ✳ ingest ALL new files
[1] Are there repos or solutions to claude code gettin.md (23kb, hooks,testing)
[2] I'm going to create a hook to enforce discovery be.md (15kb, hooks,discovery)
[3] session-chain-tracer.md (8kb, session-management)
Select files to ingest (press Enter for 0 = all): _
```

Usage: `/wiki ingest <source>` or `/wiki ingest` (scans downloads, default: all)

### Query
Accept question → `search-research --backend QMD_WIKI` → LLM synthesizes answer

**Auto-save high-value results**: If the synthesized answer is substantive (non-trivial insight, new connection, resolved ambiguity, or decision-relevant synthesis), save it directly to the wiki without asking. Write to `wiki/concepts/<slug>.md` with YAML frontmatter. Only ask the user if the synthesis is uncertain or incomplete.

Usage: `/wiki query <question>`

### Lint
Health-check wiki: contradictions, orphan pages, missing cross-references, stale claims

**Automated periodic linting**: `/wiki lint` is included in the `/main` health check workflow. It runs on every `/main` invocation.

Usage: `/wiki lint`

### Index
Rebuild `index.md` catalog from current wiki state

**Alternate method**: For raw QMD operations (`qmd ingest`, `qmd query`, `qmd lint`, `qmd index`), see `references/qmd-wiki.md` in this skill directory.

Usage: `/wiki index`
