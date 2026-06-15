#!/usr/bin/env python3
"""
Enforcement configs for all skills that opt into the shared enforce layer.

Schema per phase entry:
  name               str   — phase identifier
  gate_type          str   — "hard" or "advisory"
  evidence           dict  — evidence source:
    type              str  — "ledger_only" | "file_flag" | "json_file" | "command"
    # ledger_only:
    #   (no extra fields)
    # file_flag:
    #   files       list[str]  — paths; {run_id} and {terminal_id} are substituted
    #   all         bool       — True=ALL must exist; False=ANY one suffices
    # json_file:
    #   path        str        — JSON file path with {run_id} substitution
    #   key         str        — top-level key to read
    #   expected    str|int|bool — expected value (exact match)
    # command:
    #   cmd         list[str]  — command + args
    #   expected    int|list[int] — required exit code(s)
    #   cwd         str        — optional working directory
  fast_mode_behavior str   — optional: "skip_allowed" | "skip_forbidden"
                              Default "skip_forbidden" means hard phases
                              are never skipped.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# code-ef — evidence-first feature development (canonical name)
# evidence-first: hard gates only when backed by concrete machine-checkable evidence
# Backward-compat alias: code_v4.0
# ---------------------------------------------------------------------------

CODE_EF_PHASES: list[dict[str, Any]] = [
    {
        "name": "consumer_contract_precheck",
        "gate_type": "hard",
        "evidence": {"type": "ledger_only"},
    },
    {
        "name": "smoke_validation",
        "gate_type": "hard",
        "evidence": {"type": "ledger_only"},
    },
    {
        "name": "full_test_suite",
        "gate_type": "hard",
        "evidence": {"type": "ledger_only"},
        "fast_mode_behavior": "skip_allowed",  # --fast skips full suite
    },
    {
        "name": "audit_quality_checks",
        "gate_type": "hard",
        "evidence": {"type": "ledger_only"},
    },
    # Advisory: phases with no robust machine-checkable evidence yet
    {
        "name": "producer_consumer_trace_verification",
        "gate_type": "advisory",
        "evidence": {"type": "ledger_only"},
    },
    {
        "name": "trace_manual_verification",
        "gate_type": "advisory",
        "evidence": {"type": "ledger_only"},
    },
]


# ---------------------------------------------------------------------------
# go — evidence-first thin orchestrator (canonical name)
# evidence-first: hard gates only when backed by concrete machine-checkable evidence
# Backward-compat aliases: go-ef, go_v3.0
# State: .claude/.artifacts/{TERMINAL_ID}/go/
# Artifact convention: flags like .verified_{RUN_ID}, JSON files like
# task-result_{RUN_ID}.json
# ---------------------------------------------------------------------------

GO_EF_PHASES: list[dict[str, Any]] = [
    {
        "name": "worktree_ready",
        "gate_type": "hard",
        "evidence": {
            "type": "file_flag",
            "files": [".claude/.artifacts/{terminal_id}/go/.worktree-ready_{run_id}"],
            "all": True,
        },
    },
    {
        "name": "task_selected",
        "gate_type": "hard",
        "evidence": {
            "type": "file_flag",
            "files": [".claude/.artifacts/{terminal_id}/go/.task-selected_{run_id}"],
            "all": True,
        },
    },
    {
        "name": "code_completed",
        "gate_type": "hard",
        "evidence": [
            {
                "type": "file_flag",
                "files": [".claude/.artifacts/{terminal_id}/go/.coded_{run_id}"],
                "all": True,
            },
            {
                "type": "json_file",
                "path": ".claude/.artifacts/{terminal_id}/go/task-result_{run_id}.json",
                "key": "status",
                "expected": "pr_ready",
            },
        ],
    },
    {
        "name": "verified",
        "gate_type": "hard",
        "evidence": [
            {
                "type": "file_flag",
                "files": [".claude/.artifacts/{terminal_id}/go/.verified_{run_id}"],
                "all": True,
            },
            {
                "type": "json_file",
                "path": ".claude/.artifacts/{terminal_id}/go/verification-summary_{run_id}.json",
                "key": "verified",
                "expected": True,
            },
        ],
    },
    {
        "name": "simplified",
        "gate_type": "hard",
        "evidence": {
            "type": "file_flag",
            "files": [".claude/.artifacts/{terminal_id}/go/.simplified_{run_id}"],
            "all": True,
        },
    },
    {
        "name": "reviews_passed",
        "gate_type": "hard",
        "evidence": {
            "type": "file_flag",
            "files": [".claude/.artifacts/{terminal_id}/go/.reviews-passed_{run_id}"],
            "all": True,
        },
    },
    {
        "name": "qa_passed",
        "gate_type": "hard",
        "evidence": [
            {
                "type": "file_flag",
                "files": [".claude/.artifacts/{terminal_id}/go/.qa-passed_{run_id}"],
                "all": True,
            },
            {
                "type": "json_file",
                "path": ".claude/.artifacts/{terminal_id}/go/qa-verdict-{run_id}.json",
                "key": "qa_status",
                "expected": "skipped",
            },
        ],
    },
    {
        "name": "pr_ready",
        "gate_type": "hard",
        "evidence": [
            {
                "type": "file_flag",
                "files": [".claude/.artifacts/{terminal_id}/go/.pr-ready_{run_id}"],
                "all": True,
            },
            {
                "type": "file_flag",
                "files": [
                    ".claude/.artifacts/{terminal_id}/go/pr-body_{run_id}.md",
                    ".claude/.artifacts/{terminal_id}/go/pr-title_{run_id}.txt",
                ],
                "all": False,  # ANY artifact suffices to confirm PR context
            },
        ],
    },
    # Advisory: higher-level loop health checks (prose-defined only for now)
    {
        "name": "loop_sanity_check",
        "gate_type": "advisory",
        "evidence": {"type": "ledger_only"},  # Placeholder — no real evidence yet
    },
    {
        "name": "trace_verification",
        "gate_type": "advisory",
        "evidence": {"type": "ledger_only"},  # Placeholder — no real evidence yet
    },
]


# ---------------------------------------------------------------------------
# Registry
# Canonical -ef names, numeric versions as backward-compat aliases
# ---------------------------------------------------------------------------

ENFORCE_CONFIGS: dict[str, list[dict[str, Any]]] = {
    # Canonical evidence-first names
    "code-ef": CODE_EF_PHASES,
    "go": GO_EF_PHASES,
    # Consolidated skill aliases
    "code": CODE_EF_PHASES,
    "go-ef": GO_EF_PHASES,
    # Backward-compat aliases (numeric version naming)
    "code_v4.0": CODE_EF_PHASES,
    "go_v3.0": GO_EF_PHASES,
    # Entry created by migrate_to_ef.py
    # Entry created by migrate_to_ef.py
    # Entry created by migrate_to_ef.py
    # Entry created by migrate_to_ef.py
    # Entry created by migrate_to_ef.py
    # Entry created by migrate_to_ef.py
    # Entry created by migrate_to_ef.py
}
