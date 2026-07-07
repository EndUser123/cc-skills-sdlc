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

## Default (no argument)

When invoked as `/wiki` with no operation and no argument, **default to session-ingest**: distill the current session's unique, durable findings into one or more wiki pages.

**Why default to session-ingest**: the conversation is the freshest possible source, and the wiki's purpose is persistence of exactly this kind of finding. The session always exists; file-based sources (Downloads, yt-is) require files to be present. The constitution is explicit — "LLM has conversation history" — so synthesize from context, do not build a transcript parser.

**Procedure (main session, no subagent dispatch)**:
1. Scan the conversation for durable findings: non-obvious fixes/root causes, measured benchmark results, decisions with rationale not in code/commits, and rejected alternatives with the rejection reason.
2. **Deduplicate against existing wiki** before writing. Grep `P:/.data/wiki/concepts/` and `P:/.data/wiki/log.md` for slugs, titles, or content that already captures each finding. Read candidates to confirm overlap, not just title match.
3. If nothing unique survives dedup → report "nothing new to ingest" with the 1-2 candidates considered, and stop. Do NOT write a low-value page just to write something.
4. If multiple distinct findings survive → write one page per finding (Option A, one-page-per-unit). Do not aggregate unrelated findings into a single session-recap page.
5. Write each page using the standard wiki page format defined under Ingest (YAML frontmatter + Summary / Key Findings / Related / Sources body sections). `source: session-<YYYY-MM-DD>`.
6. Append to `P:/.data/wiki/log.md` for each page:
   `## [YYYY-MM-DD] ingest | <title>\nSource: session\nTranscript: <transcript_path>\n`
7. Run the post-phase QMD update:
   ```powershell
   pwsh -NoProfile -File "P:/.claude/hooks/scripts/qmd_update_wrapper.ps1"
   ```
8. Report: pages written (title → path) and pages skipped (which finding, which existing page covered it).

**What counts as unique/durable**:
- A non-obvious fix or root cause (e.g., "cc-ccr probe was hitting LM Studio port, not llama.cpp")
- A measured benchmark result future sessions would benefit from (numbers + conditions)
- A decision with rationale that isn't in code, commit messages, or CLAUDE.md
- A rejected alternative with the rejection reason

**What does NOT count (skip these)**:
- Ephemeral task state, in-progress work, narrative session summaries without durable insight
- Findings already documented in CLAUDE.md, code comments, existing wiki pages, or commit messages
- Debugging recipes that live in the commit, not the wiki

Usage: `/wiki`

## Operations

### Signal-extract (bulk noisy sources)

For directories full of session dumps, chat exports, or other noisy text where
whole-file LLM-skim agents miss gems buried past line 150. Two-script deterministic
pipeline — NO LLM in the loop until the final triage step.

**When to use**: source has 100+ files where most yield nothing and a few have
buried root-cause / measurement / decision nuggets (e.g. `C:/Users/brsth/Downloads`).
**When NOT to use**: curated single-author docs, YouTube transcripts, design docs —
use the regular `Ingest` operation below (one page per source).

```bash
# Stage 1: scan all files, dedupe candidates vs existing wiki (4-shingle overlap)
python skills/wiki/scripts/wiki_signal_extract.py \
  --source C:/Users/brsth/Downloads \
  --wiki P:/.data/wiki/concepts \
  --out P:/.data/wiki/_incoming/signal_candidates.json \
  --report P:/.data/wiki/_incoming/signal_report.md

# Stage 2: filter — drop tool-output noise + require durable-claim signature
python skills/wiki/scripts/wiki_signal_filter.py \
  --in P:/.data/wiki/_incoming/signal_candidates.json \
  --wiki P:/.data/wiki/concepts \
  --out P:/.data/wiki/_incoming/durable_candidates.json \
  --report P:/.data/wiki/_incoming/durable_report.md
```

**Stage 3 (chunk for LLM distillation)** — group survivors into self-contained
verification chunks. Each chunk carries the candidate sentence + ±N lines of
source context, so the reviewer never needs to load a full 500KB source file:

```bash
python skills/wiki/scripts/wiki_signal_distill.py \
  --in P:/.data/wiki/_incoming/durable_candidates.json \
  --source C:/Users/brsth/Downloads \
  --out-dir P:/.data/wiki/_incoming/distill_chunks \
  --context-lines 15
```
Emits one `<source-stem>.json` per source file + a `_manifest.json`. Chunks are
2–8KB each — small enough for any consumer.

**Stage 4 (dispatch distillation — choose one):**

```bash
# Emits a markdown dispatch plan with one pre-filled Task-tool block per chunk.
python skills/wiki/scripts/wiki_signal_dispatch.py \
  --manifest P:/.data/wiki/_incoming/distill_chunks/_manifest.json \
  --chunks-dir P:/.data/wiki/_incoming/distill_chunks \
  --out P:/.data/wiki/_incoming/dispatch_plan.md \
  --vault P:/.data/wiki/concepts \
  --max-chunks 30
```

Then execute the plan:
- **Claude subagents** (highest fidelity): for each chunk block in `dispatch_plan.md`,
  spawn one Task-tool subagent with the block as its prompt. Each subagent verifies
  candidates against their `context_snippet`, generalizes durable claims, and writes
  real concept pages to `P:/.data/wiki/concepts/<slug>.md`.
- **Local/cheap LLM** (volume): re-run with `--mode ai-cli` to emit one shell
  command per chunk piping to `/ai-cli`. Run them in parallel. Each chunk is
  self-contained (sentence + context + source path) so no shared state is needed.
- **Manual triage** (highest precision): read `durable_report.md`, hand-pick
  the strongest 10–20 candidates, dispatch targeted subagents for just those.

Do NOT ingest raw candidate sentences as pages — they are unverified classifier
output. Every survivor must be verified against its source before promotion.

**Tunables**:
- `--wiki-overlap 0.5` (extractor): raise to keep more wiki-adjacent sentences, lower for stricter novelty.
- `--noise-threshold 2` (filter): tool-output pattern hits to skip (2 = strict, 3 = loose).
- `--context-lines 15` (distill): lines of source context per candidate.
- `--max-per-chunk 20` (distill): split a file's candidates into multiple chunks above this count.

Usage: `/wiki signal-extract <source-dir>`

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
6. Run the shared auto-link step: `python skills/wiki/scripts/wiki_after_write.py <VAULT/concepts/slug.md>`. This queries QMD for top-K semantically similar existing concept pages and injects a `## Auto-related` section. Best-effort; no-op if QMD returns nothing. Never touches a hand-authored `## Related` section.
7. Append to <LOG_FILE>: "## [YYYY-MM-DD] ingest | <title>\nSource: <original_filename>\nSHA256: <hash>\n"

 PHASE 3: COMPLETION REPORT (separate from generation) 

8. Update manifest entry to status=done.

NOTICE: Steps 4-6 are generation (write + auto-link). Step 8 is completion reporting.
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

**Auto-linking phase**: After writing the page, run `python skills/wiki/scripts/wiki_after_write.py <page-path>`. The script reads the page's title+summary frontmatter, queries QMD for top-K (default 5) semantically similar existing concept pages, and injects `[[wikilinks]]` into a `## Auto-related` section. This is the **shared post-write step** called by every write path — Ingest subagent (Phase 2 step 6) and Query-section auto-save. Best-effort: QMD similarity quality determines candidates; pages with weak token overlap to their conceptual neighbors get no auto-links and should keep a hand-authored `## Related` section. Hand-authored `## Related` is never touched. Re-run the script anytime to regenerate `## Auto-related` from current QMD state.

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

**Step 1 — Scope routing (DEFAULT TO SESSION).** Classify the query BEFORE searching. The Constitution is explicit: "LLM has conversation history — don't build parsers for what's already in context." Running QMD/web for a question the session already answers is the anti-pattern this step exists to prevent.

- **Session scope** (default — answer from chat, NO search): the prompt is
  vague, conceptual, or open-ended ("what's unique", "what's useful to know",
  "what should I know", "recap", "summary", "what's the state of", "what did
  we decide", "what's important here"), OR references current session work
  ("the proposal", "the current issue", "our work", "this", "that bug").
  → Synthesize the answer directly from conversation context. Do not invoke
  `search-research`, QMD, or web search. Cite session evidence by turn/topic.

- **External scope** (escalate to Step 2): the query names a specific tool,
  library, concept, or prior decision NOT present in the current session, OR
  explicitly asks for persistent/historical knowledge ("what does the wiki
  say", "search for", "look up", "research", "prior art", "previous note on").
  → Run Step 2.

- **Ambiguous → prefer session scope.** Give a one-line answer from context
  and note "say the word and I'll search the wiki/external" if they want
  more. Escalate only when the session answer is insufficient AND external
  knowledge is clearly wanted.

**Step 2 — Search (external scope only).**
1. `search-research --mode quick "<question>"` (QMD_WIKI backend) — primary path
2. If QMD returns nothing relevant and the question is about hook/skill/agent implementation detail, `Grep` directly under `P:/.claude/hooks/__lib/` or the relevant plugin tree
→ First quality result wins → LLM synthesizes answer

(An earlier "Known Local Docs" table pointing at `P:/.claude/docs/*.md` was removed 2026-07-06 — those files were deleted in a docs/ → staging+wiki migration but the table was never reconciled. QMD indexes the live wiki; do not reintroduce hand-maintained doc-path pointers.)

**Auto-save high-value results**: If the synthesized answer is substantive (non-trivial insight, new connection, resolved ambiguity, or decision-relevant synthesis), save it directly to the wiki without asking. Write to `wiki/concepts/<slug>.md` with YAML frontmatter. Then run the shared auto-link step: `python skills/wiki/scripts/wiki_after_write.py <page-path>` — this is the same post-write call every Ingest subagent makes, so auto-saved pages get the same `## Auto-related` treatment as ingested ones. Only ask the user if the synthesis is uncertain or incomplete.

Usage: `/wiki query <question>`

### Lint
Two-layer health check: deterministic graph+staleness via script, then LLM judgment on top.

**Phase 1 — Deterministic (script, no LLM):** Run the shared diagnostic engine that /main also uses:

```bash
python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py [--json]
```

Emits: broken wikilinks, orphan pages, duplicate slugs, missing frontmatter, stale page count (mtime > 90d). This is the same probe `/main` runs every invocation, so `/wiki lint` and `/main` never disagree on the graph.

**Phase 2 — Judgment (LLM, on top of Phase 1 output):** For each broken link the script could NOT safely auto-fix and each orphan cluster, apply judgment:
- Contradictions between pages that share a typed `@contradicts` link
- Stale claims (assertions referencing deprecated/renamed tools or APIs)
- Orphan triage: keep | merge into a related page | leave as intentional red-link seed

Per wiki policy (`CLAUDE.md:22`): **never suppress a broken red-link just because the target doesn't exist** — speculative links are intentional. Only flag a red-link for action when Phase 1 reports it as broken AND a clear fuzzy-match target exists.

**`/wiki lint --fix`** — runs Phase 1 in `--fix` mode (script applies ONLY safe deterministic repairs: unique fuzzy-match broken links at ≥0.9 confidence, single candidate), then surfaces the judgment-tail for Phase 2 review. The script's own `--fix` never deletes orphans or red-links.

```bash
python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py --fix [--dry-run]
```

**Automated periodic linting**: Phase 1 of `/wiki lint` is included in the `/main` health check workflow on every `/main` invocation; `/main --fix` applies the safe-subset through a **needs-based gate** — it re-runs only when the vault mtime fingerprint changed since the last fix (sentinel at `P:/.claude/.artifacts/_main/wiki_autofix_fingerprint.txt`). No time throttle: edit a page and the next `/main --fix` re-evaluates; leave the vault untouched and it skips.

Usage: `/wiki lint [--fix] [--dry-run]`

### Index
Rebuild `index.md` catalog from current wiki state

**Alternate method**: For raw QMD operations (`qmd ingest`, `qmd query`, `qmd lint`, `qmd index`), see `references/qmd-wiki.md` in this skill directory.

Usage: `/wiki index`

### Update

Refresh stale wiki pages by detecting topics that need updating and offering web-based refresh.

**Phase 1 — Discovery**: Identify candidates via four signals:
1. **Stale page list (deterministic, shared with /main):**
   ```bash
   python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py --stale [--max-age 90] [--limit 20] [--json]
   ```
   Lists pages by mtime age (oldest first). Same engine `/main` and `/wiki lint` use — single source of truth for staleness.
2. **Source drift (deterministic, opt-in):** For pages with a `source_url` frontmatter field, fetch the upstream URL, hash it, and flag drift vs the stored `source_hash`. This is the provenance-based trigger — it fires when the *source* changed, regardless of page age.
   ```bash
   python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py --source-drift [--source-timeout 5.0] [--json]
   ```
   Reports per-page reasons: `changed` (upstream content differs), `missing_hash` (page has `source_url` but no `source_hash` — needs initial population), `fetch_failed:<Error>` (network/HTTP). Pages without `source_url` are invisible to this scan.
3. **QMD search frequency**: Run `qmd search --collection wiki <topic>` and track which topics are re-searched (implies active interest) — overlay this signal on the stale + drift lists to prioritize.
4. **Git-commit delta (`--since <sha>`, deterministic):** pages whose `Sources:` frontmatter cites a file changed since `<sha>`. This catches doc-code drift the age and source-drift signals miss (a recently-edited page can still lag the code it documents). Pattern reused from `cc-skills-analysis/skills/top-problems/references/flags.md`:
   ```bash
   # changed files since the anchor sha
   git -C P:/packages/.claude-marketplace log <sha>..HEAD --name-only --pretty=format: | sort -u
   ```
   Intersect that list with the `Sources:` entries on each `P:/.data/wiki/concepts/*.md` page. Any page citing a changed file is a refresh candidate. Anchor = the sha recorded at the last `/wiki update` (store it in `.claude/.artifacts/<terminal_id>/wiki/last_update_sha`), or a known-good tag when no anchor exists.

**Phase 2 — Staleness scoring**: Rank candidates by:
- Days since last update (page mtime vs current date)
- Source drift: did `--source-drift` flag this page as `changed`? (strongest signal — upstream actually moved)
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

### Init
Seed the project `CLAUDE.md` with a Wiki Index pointer so every coding agent in the repo knows the wiki exists and how to query it — without re-explaining it each session. Idempotent: re-running updates the block, never duplicates it.

1. Resolve the project CLAUDE.md: `P:/CLAUDE.md` if it exists, else the repo root `CLAUDE.md`.
2. Inject (or replace) a fenced `<!-- BEGIN WIKI INDEX -->` … `<!-- END WIKI INDEX -->` block containing:
   - Vault location: `P:/.data/wiki/` (concepts in `concepts/`, log at `log.md`).
   - How to query: `/wiki query <question>` (QMD-backed; session-scope answers preferred for vague queries).
   - How to refresh: `/wiki update` (4 Discovery signals incl. `--since <sha>`); `/wiki lint` for health.
3. Do NOT rewrite the rest of CLAUDE.md — only the fenced block. If the markers already exist, replace only the content between them.

Usage: `/wiki init`

## Verification (cold-start)

```bash
# 1) The since-intersect test suite (3 tests: git-log, intersection, no false positive):
python -m pytest plugins/cc-skills-sdlc/skills/wiki/tests/test_since_intersect.py -q
# expect: 3 passed

# 2) The shared wiki_health_check.py (the same engine /wiki lint + /main use):
python plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py --stale --max-age 90 --json
# expect: a JSON list of pages with their mtime + the stale-by count.

# 3) Quick semantic check (no ffmpeg, no network): the Phase-1 Discovery with --since
# intersects a known git diff against `Sources:` frontmatter. See test_since_intersect.py.
```

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
