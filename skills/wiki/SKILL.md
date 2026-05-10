---
name: wiki
description: Persistent knowledge system using Obsidian wiki + QMD search
version: 1.2.0
type: skill
enforcement: none
workflow_steps:
  - ingest: "3-phase pipeline: manifest (script) → per-file parallel ingest (subagents) → post-phase (script). Handles large files via tiered strategy."
  - query: "Accept question, search wiki via QMD_WIKI backend, synthesize answer"
  - lint: "Health-check wiki for contradictions, orphans, missing cross-refs"
  - index: "Rebuild index.md catalog from current wiki state"
  - update: "Discover stale pages by age + search frequency, offer web-based refresh with SHA256 dedup"
---

# /wiki — Obsidian Wiki + QMD Search Skill

## Purpose

Persistent knowledge management: LLM maintains an Obsidian wiki (ingest/synthesize/lint), searchable via QMD CLI, exposed as `search-research` backend `QMD_WIKI`.

## Operations

### Ingest

3-phase pipeline: **Pre-phase** (Python script, no LLM) → **Ingest phase** (parallel per-file subagents) → **Post-phase** (QMD update, no file content).

**Pre-phase — manifest generation** (main session, script, no LLM content):
```powershell
python - <<'PY'
import json, hashlib, pathlib, re

VAULT_DIR = pathlib.Path("P:/.data/wiki")
LOG_FILE  = VAULT_DIR / "log.md"
MANIFEST  = pathlib.Path("/tmp/wiki_ingest_manifest.json")
SRC_DIR   = pathlib.Path("C:/Users/brsth/Downloads")
MAX_SAFE  = 200_000   # bytes — safe for single LLM call
MAX_WARN = 500_000   # bytes — warn but attempt ingest
SALT     = "SHA256:" # log entry prefix for dedup check

existing = set()
if LOG_FILE.exists():
    text = LOG_FILE.read_text(encoding="utf-8")
    existing = set(re.findall(r"SHA256:([a-f0-9]{64})", text))

entries = []
for f in sorted(SRC_DIR.glob("*.md"), key=lambda p: p.stat().st_size, reverse=True):
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    if h in existing:
        entries.append({"path": str(f), "size": f.stat().st_size, "hash": h, "status": "skipped"})
        continue
    sz = f.stat().st_size
    tier = "large_skip" if sz > MAX_WARN else ("large_warn" if sz > MAX_SAFE else "safe")
    entries.append({"path": str(f), "size": sz, "hash": h, "status": "pending", "tier": tier})

MANIFEST.write_text(json.dumps(entries, indent=2), encoding="utf-8")
print(f"Manifest: {len(entries)} files — safe={sum(1 for e in entries if e['tier']=='safe')} "
      f"large_warn={sum(1 for e in entries if e['tier']=='large_warn')} "
      f"large_skip={sum(1 for e in entries if e['tier']=='large_skip')} "
      f"skipped={sum(1 for e in entries if e['status']=='skipped')}")
PY
```
Running this produces `/tmp/wiki_ingest_manifest.json` with all Downloads .md files, their hashes, sizes, and tier. The script reads file bytes only for hashing — no LLM context involvement.

**Ingest phase — parallel per-file dispatch** (subagents, 1 file each):
- Dispatch one subagent per `status: pending` entry from the manifest.
- Each subagent: reads exactly one file, verifies SHA256 against manifest, skips if hash matches log, writes wiki page to `P:/.data/wiki/concepts/<slug>.md`, updates manifest entry to `status: done` or `status: failed`.
- **Failure handling**: If a subagent hits a context window error, it writes `status: failed` to the manifest with `error: context_limit`. The coordinator re-queues failed entries for retry with a warning.
- Safe files (`<200KB`): direct ingest.
- Large-warn files (`200KB-500KB`): ingest with explicit size warning in output.
- Large-skip files (`>500KB`): subagent reports `status: skipped` + reason "file exceeds 500KB". User can override with explicit `/wiki ingest <path>` or `/wiki ingest --force <path>`.

**Subagent prompt template** (one file per call):
```
Read: <file_path from manifest>
Hash: <hash from manifest>
Vault: P:/.data/wiki/concepts/
Log:   P:/.data/wiki/log.md

1. Read the file at <file_path>.
2. Verify SHA256 matches <hash>. If not, skip and report status=failed, reason=hash_mismatch.
3. Check <LOG_FILE> for existing SHA256:<hash>. If found, report status=skipped, reason=already_ingested.
4. Distill file into a wiki page: YAML frontmatter (title, tags, summary, created), body with ## Summary + ## Key Findings + ## Related.
5. Write to <VAULT/concepts/slug.md>. Slug = lowercase alphanumeric + hyphens from filename.
6. Append to <LOG_FILE>: "## [YYYY-MM-DD] ingest | <title>\nSource: <original_filename>\nSHA256: <hash>\n"
7. Update manifest entry to status=done.
```

**Post-phase — index update** (main session, single call):
```powershell
qmd update wiki --lang en 2>$null; if ($LASTEXITCODE -ne 0) { qmd update wiki }
```
Then report summary: done / failed / skipped counts.

**URL handling with Crawl4AI**: When a URL is provided (starts with `http://` or `https://`), invoke the `/crawl` workflow:
```bash
/crawl <url> --max-pages 5 --collection wiki
```
The crawl skill handles all URL fetching, deduplication, wikilinks, and logging. Skip manual URL fetching.

**Hash-based deduplication**: The manifest pre-phase checks `log.md` for existing SHA256 hashes. Files already logged are marked `status: skipped`. Duplicate check is deterministic and requires no LLM involvement.

**Auto-linking phase**: After writing the page, query QMD for semantically similar existing pages using the new page's title and summary. Inject `[[Page Name]]` links to top-K (default K=5) related pages into the new page's body under a `## Related` section.

**Speculative linking**: When ingesting, if the content references pages that don't exist yet, create `[[wikilinks]]` to those pages anyway — they become "red links" in Obsidian. This is intentional: future ingest of those pages will resolve the links automatically. Never suppress a link because the target doesn't exist yet.

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

**No source provided — scan downloads**: When called without a source (`/wiki ingest`), runs the pre-phase manifest script and presents the results with file sizes and tiers. Default is `0` = ingest all safe files only. Use `/wiki ingest --all` to include large-warn files. Large-skip files are never included automatically.

**Selection format with size tiers**:
```
/wiki ingest
[0] ✳ ingest all SAFE files (size < 200KB)
[1] ingest all safe + large-warn files (200KB - 500KB)
[2] show all files including large-skip (> 500KB)

[FILE LIST with tier badges]:
  [A] Are there repos or solutions to claude code gettin.md (23KB, safe)
  [B] hooks_implementation_plan 2.md (228KB, large-warn)
  [C] My design skill made some lazy errors. __think (1).md (920KB, large-skip — manual split recommended)
Select files to ingest (press Enter for 0 = all safe): _
```

Usage: `/wiki ingest` (safe only), `/wiki ingest --all` (safe + large-warn), `/wiki ingest <path>` (explicit single file, skips size check), `/wiki ingest --force <path>` (force large file)

### Query
Accept question → run in parallel:
1. `search-research --mode quick "<question>"` (QMD_WIKI backend)
2. `Grep` against known local doc files matching the question domain (see Known Local Docs below)
→ First quality result wins → LLM synthesizes answer

**Known Local Docs**: Grep these in parallel with QMD when the question matches:
| Pattern | File |
|---|---|
| hook, stop, pretool, posttool, userprompt | `P:/.claude/docs/claude-hooks-v3.1.md` |
| skill, slash command, SKILL.md | `P:/.claude/docs/claude-skills-v3.0.md` |
| agent, subagent | `P:/.claude/docs/claude-agents-v1.0.md` |
| claude code, claude-code, settings, permissions | `P:/.claude/docs/claude-code-reference.md` |

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

### Update

Refresh stale wiki pages by detecting topics that need updating and offering web-based refresh.

**Phase 1 — Discovery**: Identify candidates via two signals:
1. **QMD search frequency**: Run `qmd search --collection wiki <topic>` and track which topics are re-searched (implies active interest)
2. **Age check**: Pages with `created:` frontmatter older than 90 days are candidates (configurable threshold)

**Phase 2 — Staleness scoring**: Rank candidates by:
- Days since last update (page mtime vs current date)
- External change signals: is the source URL (if any) returning different content?
- Search frequency: topics searched more often = higher priority

**Phase 3 — Offer to user**: Present top candidates ranked by staleness score:

```
/wiki update
=== Stale Knowledge Candidates (10 items) ===
[1] ● Claude Code Hooks Guide (stale: 127d, searched: 23x)
    Last updated: 2025-12-05
    Source: https://docs.anthropic.com/claude-code/hooks
    [U] update   [S] skip   [D] dismiss

[2] ○ FastAPI Best Practices (stale: 94d, searched: 8x)
    Last updated: 2026-01-06
    [U] update   [S] skip   [D] dismiss

Select items to refresh (e.g. "1,3,U" = update 1 & 3): _
```

**Phase 4 — Refresh pipeline**: For each selected item:
1. Fetch current source (URL or web search)
2. Compute new SHA256
3. Compare against log.md entry's SHA256
4. If changed: rewrite page, inject new wikilinks, update log entry, run `qmd update`
5. If unchanged: report "already current — no changes needed"

**Implementation details**:

- **Staleness threshold**: Default 90 days, configurable via `/wiki update --max-age 60`
- **Max candidates**: Default 20, configurable via `/wiki update --limit 15`
- **Sources to check**: Web search via `/research` for each topic, or direct URL fetch if source URL exists in frontmatter
- **Log entry update**: When page is refreshed, append new SHA256 to log.md with `## [YYYY-MM-DD] update | <title>` entry (NOT replacing the old ingest entry — preserves history)

**Interactivity levels**:
- `/wiki update` — interactive (offer selection)
- `/wiki update --auto` — auto-refresh all candidates without prompting
- `/wiki update <topic>` — update specific topic directly

**Token cost**: No in-context tokens during auto-refresh. Each page refresh is an independent subagent call (out-of-context).

Usage: `/wiki update [--auto] [--max-age <days>] [--limit <n>] [<topic>]
