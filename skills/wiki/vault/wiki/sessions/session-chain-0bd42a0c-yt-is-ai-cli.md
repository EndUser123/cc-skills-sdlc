---
title: "Session Chain Export 0bd42a0c — yt-is code review"
date: 2026-04-20
source: C:\Users\brsth\.claude\exports\chain_20260420_225134.md
hash: 0c65eece3f90963a000afa511cf44e4ab3f5d22234b42fc497360ad95e4dac66
type: session-export
tags:
  - yt-is
  - csf-source
  - ai-cli
  - code-review
  - session-chain
session_id: 0bd42a0c-b199-429a-9543-e71814b1090a
---

# Session Chain Export 0bd42a0c — yt-is code review

**Root session:** 0bd42a0c-b199-429a-9543-e71814b1090a
**Exported:** 2026-04-20 22:51:34
**Sessions in chain:** 1

---

## Session 1 — `0bd42a0c-b199-429a-9543-e71814b1090a`

**Topic:** /ai-cli code review — yt-is repo logging and summary-field mismatches

**User query:** Review the yt-is repo, focused on logging and summary-field mismatches in:
- `P:/packages/yt-is/bin/csf-source`
- `P:/packages/yt-is/csf/transcript.py`
- `P:/packages/yt-is/csf/batch_status.py`
- `P:/packages/yt-is/tests/test_csf_source_fetch_timing.py`
- `P:/packages/yt-is/tests/test_transcript.py`

**Known context from user:**
- Routing split intended to be:
  - `terminal/unavailable/private/deleted` → terminal skip + negative cache
  - `live / live_stream / premiere` → transcript fallback
  - `captioned` and `no_captions` → NotebookLM
- Recently fixed:
  - translated transcripts cached under untranslated text
  - `lang=None` fallback mislabeled as English
  - `industrial_pending_count` changed to report `industrial_batches_processed` in one emit path
- Residual risk: payload builder path does not include `industrial_pending_count` at all → emitted summaries and direct builder output may be inconsistent

**What was requested:**
1. All fetch summary payload builders and emitters in `bin/csf-source`
2. Field name vs value source mismatches
3. Wrapper/signature mismatches between helper functions and callers
4. Duplicate fields where one may be placeholder for another
5. Logging paths where structured JSON summary and human-readable stdout/stderr disagree
6. Code paths where negative cache, terminal skips, or transcript fallback are logged differently across dry-run, no_pending, and completed runs

**Output requested:** Concrete findings ordered by severity, file + line numbers, real bug vs style issue, residual risk areas if none found.

---

**Full transcript:** `C:\Users\brsth\.claude\exports\chain_20260420_225134.md` (8499 lines)

## Related

[[yt-is-nlm-browser-control]]@related
[[yt-is-csf-source-logging]]@related