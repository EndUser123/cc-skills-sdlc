# Version History

**v5.5.2** (2026-04-06): Generic source intake contract for `/planning`
- Added `Planning Source Packet` as an authoritative extraction surface for non-ADR source artifacts
- Clarified that transcripts, solution notes, and other unstructured sources must be normalized into canonical v2 plan sections before readiness routing
- Documented that shallow source-to-plan transcription errors stay local to `/planning`

**v5.5.1** (2026-04-05): Explicit `/arch` -> `/planning` handoff contract for ADR ingestion
- Added Planning Handoff Packet requirement for `/arch` outputs intended to feed `/planning`
- Clarified that ADR headings are source material, not valid plan section names
- Added ADR ingestion rule: `/planning` must canonicalize ADR-derived drafts before routing remaining blockers to `/arch`
- Documented that shallow ADR transcription errors stay local to `/planning`

**v5.0.6** (2026-03-28): Rate limit retry protocol for adversarial agents
- Added Step 4b-retry: Automatic retry when adversarial agents hit 429 rate limits
- Maximum 3 total attempts (initial + 2 retries) per agent before giving up
- Leverages existing idempotency pre-flight check -- completed agents skip instantly on re-dispatch
- Graceful degradation: proceed with available findings if retries exhausted
- Review summary notes which agents failed after all attempts

**v5.0.5** (2026-03-27): Remove deprecated `/planning-v2` alias references
- Removed `/planning-v2` from triggers and aliases in SKILL.md frontmatter
- Updated all command examples and usage strings from `/planning-v2` to `/planning`
- Updated usage paths in auto_verify.py and auto_fix.py docstrings from `planning-v2` to `planning`

**v5.0.4** (2026-03-27): Clarify "most recent" disambiguation for transcript scan
- Step 1 now explicitly uses file mtime as primary tiebreaker (most recently modified wins)
- When mtime is unavailable, transcript position is secondary signal (mentioned last = highest priority)
- Prevents picking a plan from earlier in transcript when a more recent one exists

**v5.0.3** (2026-03-27): Transcript-first context inference
- Context-aware behavior now checks session transcript for recently saved ADR/plan paths before falling back to glob counting
- Step 1: Scan transcript for ADR paths or plan references from this session
- Step 2: Prefer most-recently-modified plan files (mtime)
- Only asks user if multiple candidates exist AND no transcript signal

**v5.0.2** (2026-03-27): Idempotency stale-file deletion fix
- All 6 adversarial agent prompts: when `plan_path` mismatches OR file age >= 86400s, the stale file is now deleted before running the agent (previously only checked age as fallback after plan_path match, causing stale files with wrong plan_path to be treated as valid)

**v5.0.1** (2026-03-25): Compaction resilience fixes (RSN Actions 1-2)
- Per-plan subdirectory isolation: findings written to `plans/adversarial/{sanitized_plan_name}/` instead of flat namespace (prevents cross-plan collisions after compaction)
- All 6 adversarial agent prompts: upgraded idempotency check from prose "file exists AND non-empty" to programmatic Python validation (valid JSON + plan_path match + age < 86400s)
- auto_verify.load_review_findings(): wrapped json.loads() in try/except for json.JSONDecodeError and OSError (SEC-ADV-005, QA-003 fix)

**v5.0.0** (2026-03-25): Complete redesign for implementation-ready plans
- Artifact separation: plan only; findings in separate files
- Status header: `draft` -> `in-review` -> `implementation-ready`
- auto_fix limited to non-semantic repairs only
- New verification checks: placeholder detection, contradiction, disposition, plan-purity
- Synthesis step added after adversarial review
- auto_verify: ADDED placeholder detection, contradiction checks, disposition checks, plan-purity checks
- auto_verify: REMOVED normalization (draft stays draft until concrete content replaces scaffolding)
- Path selection: tightened to require explicit path when multiple candidates exist
