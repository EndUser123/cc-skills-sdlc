# Changelog

## [Unreleased]

### Worktree lifecycle — 2026-08-05
- Worktree cleanup now refreshes an existing repository `HANDOFF.md` worktree-status block after successful removal, and reports a distinct error when cleanup succeeds but the refresh fails.
- Verification: focused `worktree_cleanup` and `handoff_sync` tests.

### Evidence / Design — 2026-07-12T16:39:31.864410Z — PROV-20260712T-lightweight-evidence
- Summary: Adopt lightweight knowledge-validation and material changelog records for implementation-ready plans
- Sources / checks: /planning, focused pytest
- Claims supported: implementation-ready plans disclose source usage and link material decisions to CHANGELOG.md
- Evidence: skills/planning/tests/test_evidence_gate.py; skills/planning/tests/test_record_changelog.py
