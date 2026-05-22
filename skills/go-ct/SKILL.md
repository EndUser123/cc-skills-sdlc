---
name: go-ct
description: Execute a task from user input, plan file, or tasks.json queue and drive to completion
---
# /go v3.0 — Thin Orchestrator (Shared Enforce Layer)

## What changed from v2.0

v3.0 replaces the inline Python Stop hook with the **shared enforce layer** (`enforce/stop_gate.py`). The enforcement logic is identical — only the infrastructure moved to a reusable shared library.

Phase gates (Gen 2 artifacts):
- HARD (blocking if missing): `worktree_ready`, `task_selected`, `code_completed`, `verified`, `simplified`, `reviews_passed`, `pr_ready`
- ADVISORY (warning only): `loop_sanity_check`, `trace_verification`

Evidence checked via Gen 2 flag files + JSON artifacts in `.claude/.artifacts/{TERMINAL_ID}/go/`.