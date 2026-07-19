---
name: wiki
description: Persistent knowledge system using Obsidian wiki + QMD search
required_artifacts: []
response_requirements: {}
contract_type: workflow-execution
---
# /wiki — Claude Code Wiki Skill (thin orchestrator)

> **Canonical conventions live at `P:/.data/wiki/SCHEMA.md`.**
> This file contains Claude-Code-specific orchestration only. For page format,
> frontmatter fields, quality gate, link density, log protocol, typed wikilinks,
> speculative linking, evidence principles, and cadence — **read SCHEMA.md.**

## Purpose

Persistent knowledge management: LLM maintains an Obsidian wiki (ingest/synthesize/lint), searchable via QMD CLI, exposed as `search-research` backend `QMD_WIKI`.

## Default (no argument)

When invoked as `/wiki` with no operation and no argument, **default to session-ingest**: distill the current session's unique, durable findings into one or more wiki pages. Follow SCHEMA.md §10 (Ingest) for the procedure.

**What counts as unique/durable**: non-obvious fixes/root causes, measured benchmarks, decisions with rationale not in code/commits, rejected alternatives with the rejection reason.

**What does NOT count**: ephemeral task state, findings already in CLAUDE.md/code/commits, debugging recipes that live in the commit.

Usage: `/wiki`

## Operations

### Signal-extract (bulk noisy sources)

For directories full of session dumps, chat exports, or other noisy text where
whole-file LLM-skim agents miss gems buried past line 150. Two-script deterministic
pipeline — NO LLM in the loop until the final triage step.

**When to use**: source has 100+ files where most yield nothing and a few have
buried root-cause / measurement / decision nuggets (e.g. `C:/Users/brsth/Downloads`).
**When NOT to use**: curated single-author docs, YouTube transcripts, design docs —
use the regular `Ingest` operation below.

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
source context.

```bash
python skills/wiki/scripts/wiki_signal_distill.py \
  --in P:/.data/wiki/_incoming/durable_candidates.json \
  --source C:/Users/brsth/Downloads \
  --out-dir P:/.data/wiki/_incoming/distill_chunks \
  --context-lines 15
```

**Stage 4 (dispatch distillation):**

> ⚠️ **LLM agents are Stage 4 ONLY.**
> Stages 1–3 are deterministic Python scripts. Never dispatch subagents to read source files for extraction.

```bash
python skills/wiki/scripts/wiki_signal_dispatch.py \
  --manifest P:/.data/wiki/_incoming/distill_chunks/_manifest.json \
  --chunks-dir P:/.data/wiki/_incoming/distill_chunks \
  --out P:/.data/wiki/_incoming/dispatch_plan.md \
  --vault P:/.data/wiki/concepts \
  --max-chunks 30
```

Usage: `/wiki signal-extract <source-dir>`

### Ingest

3-phase pipeline: **Pre-phase** (Python script, no LLM) → **Ingest phase** (parallel per-file subagents) → **Post-phase** (QMD update).

**Pre-phase — manifest generation:**
```powershell
python skills/wiki/scripts/wiki_manifest.py
# --source yt-is  → P:/.data/yt-is/
# --source <path> → explicit directory override
# (no arg)        → C:/Users/brsth/Downloads (.md files, default)
# --resume        → skip already-done entries
```

**Manifest schema**: `[{"path": "...", "size": 12345, "hash": "sha256:...", "status": "pending", "tier": "safe"}]`
**Idempotency**: SHA256 dedup via `log.md` check. Files already logged are skipped.

**Ingest phase — parallel per-file dispatch** (subagents, 1 file each):
- Dispatch one subagent per `status: pending` entry.
- Each subagent: reads file, verifies SHA256, skips if hash matches log, writes wiki page, appends to log.md, updates manifest.
- Safe files (`<200KB`): direct ingest. Large-warn (`200KB-500KB`): ingest with warning. Large-skip (`>500KB`): skip unless `--force`.

**Subagent prompt template:**
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
4. Distill file into a wiki page using SCHEMA.md §2 page format.
   For YouTube transcripts: include Video Title, Channel, Duration, URL as frontmatter.
   For all files: include Pillar Match Matrix scores and EVIDENCE_GAP flags if applicable.
5. Write to <VAULT/concepts/slug>.md. For collision-safe slugs, use make_collision_slug() from wiki_manifest.py.
6. Run the shared auto-link step: python skills/wiki/scripts/wiki_after_write.py <page-path>
7. Append to <LOG_FILE>: "## [YYYY-MM-DD] ingest | <title>\nSource: <original_filename>\nSHA256: <hash>\n"

PHASE 3: COMPLETION REPORT (separate from generation)
8. Update manifest entry to status=done.

NOTICE: Steps 4-6 are generation. Step 8 is completion reporting.
Do NOT mix "page written successfully" with "page meets quality bar."
Quality assessment is a SEPARATE step handled by the coordinator.
```

**Post-phase — QMD update:**
```powershell
pwsh -NoProfile -File "P:/.claude/hooks/scripts/qmd_update_wrapper.ps1"
```

**URL handling**:

**YouTube URLs** (`youtube.com/@`, `/channel/`, `/c/`, `youtu.be/`, `/watch`):
1. **Channel already tracked** (`csf-source list`): run `python bin/csf-source fetch --source <url>` → check `transcripts.sqlite` → on failure, invoke Gemini CLI: `gemini -m gemini-2.5-flash -p "Summarize: <url>"`. Write to `P:/.data/yt-is/transcripts/`.
2. **Channel NOT tracked**: `python bin/csf-source add <url>` → then fetch.
3. **Single video URL**: extract ID → `csf-transcripts <video_id> --transcript` → if not cached: `csf-transcript-fetch` or Gemini CLI.
4. **After transcripts**: run manifest script targeting `P:/.data/yt-is/`.
5. **Failover**: fires when `transcripts.sqlite` shows `failure_reason: no_transcript`.

**Non-YouTube web URLs**: invoke `/crawl <url> --max-pages 5 --collection wiki`.

**File tier interactive selection** (when `/wiki ingest` called with no source):
```
[0] ingest all SAFE files (size < 200KB)     ← default
[1] ingest all safe + large-warn (200KB-500KB)
[2] show all including large-skip (>500KB)

[FILE LIST with tier badges]:
  [A] filename.md (23KB, safe)
  [B] bigfile.md (228KB, large-warn)
  [C] huge.md (920KB, large-skip — manual split recommended)
Select files (Enter for 0 = all safe): _
```

**Auto-linking detail**: After writing a page, run `wiki_after_write.py <page-path>`. The script reads the page's title+summary frontmatter, queries QMD for top-K (default 5) semantically similar existing concept pages, and injects `[[wikilinks]]` into `## Auto-related`. Best-effort: QMD similarity quality determines candidates; pages with weak token overlap to their conceptual neighbors get no auto-links — keep a hand-authored `## Related` section as fallback. Re-run anytime to regenerate from current QMD state. Never touches hand-authored `## Related`.

Usage: `/wiki ingest`, `/wiki ingest --all`, `/wiki ingest <path>`, `/wiki ingest --force <path>`

### Query

**Step 1 — Scope routing (DEFAULT TO SESSION).** Classify before searching. Session-scope (vague, conceptual, references current work) → synthesize from context. External-scope (names specific tool/concept/prior decision) → Step 2.

**Step 2 — Search (external scope only):**
1. `search-research --mode quick "<question>"` (QMD_WIKI backend)
2. Grep fallback under `P:/.claude/hooks/__lib/` or relevant plugin tree
3. Auto-save high-value results to wiki (SCHEMA.md §10 Query)

Usage: `/wiki query <question>`

### Lint

Two-layer health check: deterministic script + LLM judgment.

**Phase 1 — Deterministic:**
```bash
python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py [--json]
```

**Phase 2 — Judgment:** broken red-links, orphan triage, stale claims, contradictions. See SCHEMA.md §8 (speculative linking policy) and §10 (Lint).

**`--fix` mode:** safe deterministic repairs only (fuzzy-match ≥0.9, single candidate).
```bash
python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py --fix [--dry-run]
```

**Automated periodic linting**: Phase 1 of `/wiki lint` is included in the `/main` health check workflow on every `/main` invocation; `/main --fix` applies the safe-subset through a **needs-based gate** — it re-runs only when the vault mtime fingerprint changed since the last fix (sentinel at `P:/.claude/.artifacts/_main/wiki_autofix_fingerprint.txt`).

Usage: `/wiki lint [--fix] [--dry-run]`

### Index

Rebuild `index.md` catalog from current wiki state. For raw QMD operations, see `references/qmd-wiki.md`.

Usage: `/wiki index`

### Update

Refresh stale wiki pages. 4-phase: discovery → scoring → offer → refresh.

**Phase 1 — Discovery** (4 signals):
1. **Stale pages**: `wiki_health_check.py --stale [--max-age 90] [--limit 20] [--json]`
2. **Source drift**: `wiki_health_check.py --source-drift [--json]` (for pages with `source_url`)
3. **QMD search frequency**: overlay on stale + drift to prioritize
4. **Git-commit delta**: intersect changed files since `<sha>` with `Sources:` frontmatter

**Phase 2 — Staleness scoring**: Rank candidates by:
- Days since last update (page mtime)
- Source drift: did `--source-drift` flag as `changed`? (strongest signal)
- Search frequency: topics searched more often = higher priority

**Phase 3 — Offer to user** (interactive):
```
/wiki update
=== Stale Knowledge Candidates (10 items) ===
[1] Claude Code Hooks Guide (stale: 127d, searched: 23x)
    [U] update   [S] skip   [D] dismiss
[2] FastAPI Best Practices (stale: 94d, searched: 8x)
    [U] update   [S] skip   [D] dismiss
Select items to refresh (e.g. "1,3,U"): _
```

**Phase 4 — Refresh pipeline**: For each selected item: fetch current source → compute SHA256 → compare against log → if changed: rewrite page, inject new wikilinks, update log entry, run `qmd update` → if unchanged: report "already current".

**Interactivity levels**: `/wiki update` (interactive), `/wiki update --auto` (auto-refresh all), `/wiki update <topic>` (specific topic). Token cost: each page refresh is an independent subagent call (out-of-context).

Usage: `/wiki update [--auto] [--max-age <days>] [--limit <n>] [<topic>]`

### Init

Seed project `CLAUDE.md` with a Wiki Index pointer. Idempotent — re-running updates the block, never duplicates.

Usage: `/wiki init`

## Verification (cold-start)

```bash
# 1) Since-intersect test suite:
python -m pytest plugins/cc-skills-sdlc/skills/wiki/tests/test_since_intersect.py -q

# 2) Health check smoke test:
python plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py --stale --max-age 90 --json
```

## Thought Partner Addendum

When a `/wiki` session surfaces a broader recurring storage / persistence
pattern, a memory-routing gap, or a vault-conventions verification gap —
not for ordinary single-page ingest or query work — emit a Thought Partner
Addendum (TPA). Each item carries `observation`, `why_it_matters`,
`evidence`, `recommended_action`, `urgency: now | later | watch`. Omit the
section for routine ingest/query output. Canonical contract at
`debrief/references/thought-partner-addendum.md`. The TPA is prompt-advisory only.

## Partner Posture

`/wiki`'s posture is **Memory / Persistence Partner**. `/wiki` stores approved
durable lessons only — it does NOT auto-ingest candidates, does NOT silently
write to the vault on inferred intent, and routes storage decisions to the
calling command or explicit user confirmation. Posture is prompt-advisory.

## Quick reference to SCHEMA.md

- **Page format / frontmatter**: SCHEMA.md §2-3 (includes `verification:`, `cognitive_load`, `host:`, `agent:`)
- **Quality Gate**: SCHEMA.md §4
- **Link density (≥3 advisory)**: SCHEMA.md §5
- **Log protocol**: SCHEMA.md §6
- **Typed wikilinks**: SCHEMA.md §7
- **Speculative linking**: SCHEMA.md §8
- **Shared scripts**: SCHEMA.md §9
- **Operations overview**: SCHEMA.md §10
- **Recommended cadence**: SCHEMA.md §11
- **Evidence-first principles**: SCHEMA.md §12
- **Key principles**: SCHEMA.md §13
