---
name: wiki
description: Persistent knowledge system using Obsidian wiki + QMD search
required_artifacts: []
response_requirements: {}
contract_type: workflow-execution
---
# /wiki — Obsidian Wiki + QMD Search Skill

## Purpose

Persistent knowledge management: LLM maintains an Obsidian wiki (ingest/synthesize/lint), searchable via QMD CLI, exposed as `search-research` backend `QMD_WIKI`.

## Operations

### Ingest

3-phase pipeline: **Pre-phase** (Python script, no LLM) → **Ingest phase** (parallel per-file subagents) → **Post-phase** (QMD update, no file content).

**Option A — one wiki page per video** (per user decision, 2026-05-11): each transcript produces one dedicated wiki page. Do not aggregate multiple videos into a single page.

**Pre-phase — manifest generation** (main session, script, no LLM content):

```powershell
# Script: skills/wiki/scripts/wiki_manifest.py
# --source yt-is  → P:/.data/yt-is/  (transcript_*.txt files, YouTube transcripts)
# --source <path> → explicit directory override  (.txt files)
# (no arg)        → C:/Users/brsth/Downloads  (.md files, default)
python skills/wiki/scripts/wiki_manifest.py

# For YouTube URL ingestion:
python skills/wiki/scripts/wiki_manifest.py --source yt-is

# For explicit path:
python skills/wiki/scripts/wiki_manifest.py --source /path/to/dir

# For retry/resume (skip already-done entries):
python skills/wiki/scripts/wiki_manifest.py --resume
```

The script reads file bytes only for hashing — no LLM context involvement.
Manifest is written to a tempfile when `--resume` is used (prevents cross-terminal collision).

**Manifest schema** (`/tmp/wiki_ingest_manifest.json`):
```json
[{"path": "...", "size": 12345, "hash": "sha256:...", "status": "pending", "tier": "safe"}]
```
Required fields: `path`, `hash`; Optional: `size`, `tier`; Valid `status`: `pending`, `done`, `failed`, `skipped`.

**Idempotency**: SHA256 dedup via `log.md` check — if a file's hash already appears in `log.md`, the subagent marks it `status: skipped` and skips ingest. On retry after crash, `pending` entries are re-dispatched; already-ingested files are safely skipped via the log check. This prevents true duplicates.

**Ingest phase — parallel per-file dispatch** (subagents, 1 file each):
- Dispatch one subagent per `status: pending` entry from the manifest.
- Each subagent: reads exactly one file, verifies SHA256 against manifest, skips if hash matches log, writes wiki page to `P:/.data/wiki/concepts/<slug>.md`, appends to `log.md`, updates manifest entry to `status: done` or `status: failed`.
- **Resume**: On re-run after crash, pass `--resume` or re-run the manifest script — `pending` entries are re-dispatched; log.md SHA256 check prevents duplicate ingest of already-processed files.
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

 PHASE 1: VERIFICATION (before any generation) 

1. Read the file at <file_path>.
2. Verify SHA256 matches <hash>. If not, skip and report status=failed, reason=hash_mismatch.
3. Check <LOG_FILE> for existing SHA256:<hash>. If found, report status=skipped, reason=already_ingested.

STOP GATE — If verification fails, do NOT proceed to generation.
Report the failure status and stop.

 PHASE 2: GENERATION (only after verification passes) 

4. Distill file into a wiki page with enhanced metadata and structured extraction (see below).
5. Write to <VAULT/concepts/slug>.md. For collision-safe slugs, use `make_collision_slug()` from `scripts/wiki_manifest.py` (slug = safe-slug + SHA256[:8]).
6. Append to <LOG_FILE>: "## [YYYY-MM-DD] ingest | <title>\nSource: <original_filename>\nSHA256: <hash>\n"

 PHASE 3: COMPLETION REPORT (separate from generation) 

7. Update manifest entry to status=done.

NOTICE: Steps 4-5 are generation. Step 7 is completion reporting.
Do NOT mix "page written successfully" with "page meets quality bar."
Quality assessment is a SEPARATE step handled by the coordinator.
```

Enhanced wiki page format:
- For YouTube transcript files: extract and include Video Title, Channel, Duration, URL as frontmatter fields.
- For all files: always include the Pillar Match Matrix scores and EVIDENCE_GAP flags (see below).

YAML frontmatter (required fields):

title: <title>
created: <YYYY-MM-DD>
source: <original_filename>
tags: [<relevant tags>]
summary: <2-3 sentence summary of the big idea>
pillar_scores:         # only for YouTube/video content
  vision_integration: <1-5>
  terminal_isolation: <1-5>
  wiki_integrity: <1-5>
  diagnostic_rigor: <1-5>
cognitive_load: <1-5>  # overall cognitive load for this content; clamped to 1-5 if out of range
evidence_gaps: [<list of evidence gaps — see body annotation syntax below>]
source_url: <YouTube URL if video source>
channel: <YouTube channel name>
duration: <video duration if known>


Body sections (in order):
## Summary
<2-3 sentence "big idea" — the single most important takeaway>

## Key Findings (Verbatim Extraction)
<List of specific techniques, claims, or insights extracted verbatim from the source.
Each item should be quoted exactly where possible.
For each item, annotate with cognitive load (1-5) and flag any EVIDENCE_GAP:
- EVIDENCE_GAP: <what evidence is missing or unverified>   # bullet syntax required
- Assumption: <what is assumed but not proven>             # bullet syntax required

## Related
<Auto-generated wikilinks to top-5 semantically similar existing pages>

## Sources
<List of source URLs, references, or material used to extract this content>
```

**Post-phase — index update** (main session, single call):
```powershell
pwsh -NoProfile -File "P:/.claude/hooks/scripts/qmd_update_wrapper.ps1"
```Then report summary: done / failed / skipped counts.

**URL handling with yt-is → yt-dlp → Selenium → Gemini CLI**: When a URL matches
`youtube.com/@`, `youtube.com/channel/`, `youtube.com/c/`, `youtu.be/`, or
`youtube.com/watch`:

1. **Channel already tracked** (`csf-source list` shows it):
   - Run `python bin/csf-source fetch --source <url>` to trigger yt-dlp → Selenium escalation
   - Check `transcripts.sqlite` for completion; on failure, invoke Gemini CLI as last resort:
     `gemini -m gemini-2.5-flash -p "Summarize the content of this YouTube video. Return a detailed summary: <url>"`
     Always specify `-m gemini-2.5-flash` — the default model may be slower or more expensive.
   - Write fetched transcripts to `P:/.data/yt-is/transcripts/` as individual `.txt` files
   - These `.txt` files become the input for the pre-phase manifest script

2. **Channel NOT tracked**:
   - Run `python bin/csf-source add <url>` to import channel and enumerate all videos
   - Then run `python bin/csf-source fetch --source <url>` (same as above)
   - Note: channel sync is required to refresh the pending queue (queue may be stale)

3. **Single video URL** (`/watch` or `youtu.be/`):
   - Extract video ID; use `csf-transcripts <video_id> --transcript` to check cache
   - If not cached: `csf-transcript-fetch --channel <video_url>` or prompt Gemini CLI directly
   - The single `.txt` transcript file becomes the input for the pre-phase manifest script

4. **After transcripts fetched**: run the manifest script targeting `P:/.data/yt-is/`:
   ```powershell
   "yt-is" | python skills/wiki/scripts/wiki_manifest.py --stdin-source --source yt-is
   ```
   Then proceed with standard pipeline (manifest → per-file subagents → QMD update).

5. **Failover to Gemini CLI**: fires when `transcripts.sqlite` shows `failure_reason: no_transcript`
   for all methods exhausted — invoke `gemini -m gemini-2.5-flash -p` with the video URL and parse the text response.

**Web URL handling (non-YouTube)**: When a URL is provided (http/https that doesn't match YouTube patterns),
invoke the `/crawl` workflow:
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
|||
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

## Evidence-First Principles

### E1 — Evidence before claims
Before claiming code is absent, unchanged, or non-existent — search the codebase and verify with tools first. Claims of absence are only valid after confirmed Read/Grep/git failures.

### E4 — Investigate before asking
Do NOT answer without reading relevant source files first. Do not ask the user for information you can obtain yourself via Read, Grep, Bash, git, or available MCP tools.

### E5 — Anti-lazy escape hatch
Prohibited:
- "I assume", "I think", "probably" without tool verification
- Claiming something doesn't exist without confirmed tool failure
- Skipping evidence gathering because the answer seems obvious
