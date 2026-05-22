# yt-is Pipeline Reference

Pipeline for ingesting YouTube channel/video content into the wiki via `P:/packages/yt-is/`.

## Storage

**Data root**: `P:/.data/yt-is/` — this is the yt-is data root (NOT `P:/.data/yt-is/transcripts/`).

**transcript_cache table** (`P:/.data/yt-is/transcripts.sqlite`):
```
Columns: cache_key (TEXT PK), video_id (TEXT), lang (TEXT), source (TEXT),
         transcript (TEXT), metadata_json (TEXT), cached_at (TEXT), terminal_id (TEXT)
Sources: 'notebooklm' (NLM batch), 'selenium' (Selenium fetch), 'gemini' (Gemini CLI fallback)
```

**analysis_status table** (`P:/packages/yt-is/.data/yt-is/analysis_status.sqlite`):
```
Columns: video_id (TEXT PK), status, updated_at, source, published_at,
         last_stage, failure_reason (TEXT),
         has_captions, unavailable_reason, quality_metrics (JSON)
failure_reason values:
  'region_block'       — video blocked in fetching region
  'no_transcript'     — no captions/transcript available (primary Gemini CLI failover trigger)
  'quota_exceeded'    — API quota hit
  'auth_failed'       — authentication failure
  'captcha'           — CAPTCHA wall
  'unavailable'        — video unavailable/removed
  'materialization_wait_failed' — NLM batch/timestamp materialization timed out
  'source_add_failed'  — channel enumeration failed
  'source_count_probe_failed' — video count probe failed
  'dead_notebook_recreate_failed' — NLM notebook recreation failed
```

## Fetch Methods (in priority order)

### 1. yt-dlp (primary)
Fetches subtitles via `--write-subs --write-auto-subs`. Deterministic — no hallucination risk.

### 2. Selenium (fallback)
Browser automation to scrape YouTube transcript panel. Used when yt-dlp returns no subs. Bypasses TLS bot detection.

### 3. Gemini CLI (last resort)
`gemini -m gemini-2.5-flash -p "Summarize the content of this YouTube video. Return a detailed summary: <url>"`

**Model: always specify `-m gemini-2.5-flash`** — the default model may be slower or more expensive. The `gemini-2.5-flash` model is optimized for this use case.

**Known failure modes and mitigations** (Google issue tracker #1359, #1898):

| Failure | Cause | Mitigation |
|---------|-------|-------------|
| Timestamp drift (5-10min off on 30min video) | Gemini fetches YouTube URL differently than uploaded video | Prefer yt-dlp extraction first; Gemini is fallback only |
| Random truncation on first (uncached) request | Sampling rate issue | Set `fps=1.0` in video metadata when using SDK directly |
| Speaker hallucination / misattribution | Model fills gaps with plausible content | Pass title + description as context; verify against extracted captions |
| Text hallucination at scale | LLM trained on internet text | Chunk at ~512 words; use structured output schema for reliable format |

**Hybrid pipeline (preferred architecture)**:
```
yt-dlp extract (bit-perfect, no hallucination) → Gemini summarize (hallucination risk only in transform)
```
This limits hallucination to the transformation step, not the extraction step.

**Structured output for reliable timestamps** (when timestamps are needed):
Use `fps=1.0` in video metadata and format timestamps as `0m0s0ms` via structured output schema.

## Wiki Ingest Flow

```
/wiki ingest https://www.youtube.com/@channel
  → URL detected as YouTube
  → csf-source add <url>       (enumerate all videos; required for new channels)
  → csf-source fetch <url>      (yt-dlp → Selenium; writes transcript_*.txt to P:/.data/yt-is/)
  → manifest script --source yt-is
  → per-file subagents (1 per transcript_*.txt file)
  → QMD update
```

## Failover Trigger

Gemini CLI fires when `analysis_status.failure_reason = 'no_transcript'` for all three methods (yt-dlp, Selenium, direct API).

## Transcript File Output

- yt-dlp/Selenium path: `transcript_*.txt` files in `P:/.data/yt-is/` (NOT in a `transcripts/` subdirectory)
- NLM path: `combined_batch_*.md` in `P:/.data/yt-nlm/batches/`
- Gemini CLI: plain text response (no file; parsed from stdout)

## Slug Generation

Slug = lowercase ASCII alphanumeric + hyphens from filename. Unicode filenames are NFKD-normalized then ASCII-stripped; pure-CJK defaults to 'untitled'. Use `make_collision_slug()` (from `wiki_manifest.py`) for collision-safe slugs with SHA256[:8] suffix when ingesting files where name collisions are possible.
