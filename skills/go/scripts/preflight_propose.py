#!/usr/bin/env python3
"""Proposal-only generation for ``/go --preflight-only``.

Pure deterministic prompt classification. No LLM, no network, no shared state.
The orchestrator (``scripts/orchestrate.py``) imports :func:`run_preflight`
when ``--preflight-only`` is set; this module writes ONLY the proposal
artifact + leaves phase markers to the orchestrator so existing markers stay
consistent.

Public API
----------
- :func:`rewrite_goal`           — light prompt cleanup, preserves intent.
- :func:`classify_dispatch`      — (suggestedDispatch, localEligible, requiresApproval).
- :func:`verification_suggestions` — heuristic strings, NOT wired to task contract.
- :func:`generate_proposal`      — dict matching the spec'd shape.
- :func:`run_preflight`          — write the terminal-scoped proposal artifact.

Reuses stdlib only. No new dependencies. Reversible: deleting this file +
the ``--preflight-only`` flag is a complete rollback.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from classify_complexity import classify_model_affinity

# Heuristic markers — conservative. False-positives acceptable (telemetry-style
# probe per the agentic-reliability rollout discipline; never blocks dispatch).
_BROAD_MARKERS = (
    "design ", "design a", "design the",
    "architectur", "restructure", "migrat", "redesign",
    "overhaul", "audit", "evaluat",
    "should we", "compare ", "strateg", "plan ", "investigat",
    "diagnos", "triag", "feasibility", "scoping",
)
_BOUNDED_MARKERS = (
    "fix ", "add a test", "add tests", "add a flag", "rename ",
    "typo", "bump ", "wire ", "expose ",
    "set ", "configur", "update the ", "change x to y",
)
# Conversational prompts — status questions, assertions, pushback, clarifications.
# These keep dispatch="pi" but do NOT require approval. Detection is intentionally
# conservative: matched only when the prompt is NOT also broad or bounded, so a
# task verb ("audit the X", "investigate why Y") takes priority and still gets
# requiresApproval=true.
_CONVERSATIONAL_MARKERS = (
    "did you ", "do you ", "are you ",
    "is it ", "is there ", "is this ",
    "will it ", "will this ", "will they ", "will both ", "will the ",
    "can i ", "can we ", "should i ", "should we ",
    "what's ", "what is ", "what are ",
    "why ", "how ", "when ", "where ", "who ",
    "i think ", "i feel ", "i believe ",
    "thanks", "thank you",
    "great.", "perfect.", "good.", "ok.", "okay.",
)
_PATH_LIKE = re.compile(r"[\w./\\-]+\.(?:py|js|ts|md|json|toml|yaml|yml|sh)\b")
# Verification-mode markers — broad/discovery verbs that override the pytest default
# (which only fits implementation tasks). Review/critique prompts get an evidence-ledger
# suggestion; diagnose/investigate ones get the same.
_REVIEW_DECISION_MARKERS = ("review", "critique", "critically", "audit ", "evaluat", "optimal")
_EVIDENCE_LEDGER_MARKERS = ("diagnos", "investigat", "root cause", "rca")

# --- Task-intent classification (ceremony/rigor axis) -----------------------
# task_intent is distinct from the routing `task_type` enum in
# active-task.schema.json. task_intent controls *how* /go runs (ceremony,
# verification depth, completion-claim eligibility); task_type controls *where*
# a task routes (/code, /refactor, /design, /planning). The two are orthogonal.
_INTENT_MARKERS: dict[str, tuple[str, ...]] = {
    "decide": (
        "should we", "decide", "decision", "optimal", "recommend",
        "compare", "strateg", "choose", "pick between", "tradeoff",
        "trade-off", "which approach", "which option", "evaluate options",
    ),
    "investigate": (
        "investigat", "diagnos", "root cause", "rca", "why is", "why does",
        "why did", "figure out", "trace", "research", "look into",
        "find out", "understand why",
    ),
    "validate": (
        "review", "critique", "critically", "audit ", "validat", "verify",
        "inspect", "assess", "check status", "field-test", "field test",
        "sanity check", "confirm that",
    ),
    "implement": (
        "fix", "add ", "implement", "refactor", "update", "change", "wire",
        "expose", "rename", "bump ", "create", "build", "migrate", "patch",
        "remove", "delete",
    ),
}
_INTENT_VALUES = ("implement", "investigate", "validate", "decide", "mixed")

# High-risk surfaces: prompt_review_required=True when any match. Mirrors the
# FMM hook/gate row plus state/identity/dispatch/cache/plugin extensions.
_HIGH_RISK_MARKERS: tuple[str, ...] = (
    "hook", "stop hook", "pretooluse", "posttooluse", "pre tool use",
    "post tool use", "sessionstart", "sessionend",
    "identity", "dispatch", "router", "settings.json", "hooks.json",
    "cache rebuild", "plugin cache", "plugin.json", "state dir",
    "authorization", "credentials", "auth token",
)

_PROMPT_REVIEW_SUPPORT = "absent"  # no prompt-review artifact gate exists in go/ yet

# --- Capability-claim audit (consolidation/deprecation/routing tasks) ----------
# Trigger terms that activate the capability-claim audit. When any match,
# the proposal emits capability_claims and the report gate requires backend
# verification before "shipped"/"absorbed"/"production" wording.
_CAPABILITY_AUDIT_TRIGGER_TERMS: tuple[str, ...] = (
    "consolidat", "deprecat", "absorb", "rout", "stub", "cleanup",
    "command cleanup", "skill cleanup", "plugin cleanup", "mode migration",
    "visible surface", "command migration", "merge command", "replace command",
    "decommission", "sunset", "retire",
)
# Claimed statuses that require backend verification (not just visible-surface).
_CAPABILITY_AUDIT_VERIFIED_CLAIMS: frozenset[str] = frozenset({
    "absorbed", "shipped", "production",
})

# --- Layer-placement guard (hook/gate boundary) --------------------------------
# Stop hooks verify narrow session-bound evidence; preflight/report-gate owns
# broad analysis, pattern detection, promotion policy, dry-run refactor.
# This guard catches the misimplementation pattern that put pattern detection
# into Stop_enforce_gate.py (recovered 2026-07-07).
_LAYER_HOOK_FILE_MARKERS: tuple[str, ...] = (
    "stop_enforce_gate", "stop hook", "stop.py", "pretooluse", "pre tool use",
    "posttooluse", "post tool use", "sessionstart",
)
_LAYER_BROAD_BEHAVIOR_MARKERS: tuple[str, ...] = (
    "pattern detection", "pattern_candidate", "dry run", "dry-run",
    "refactor analysis", "cross-session state", "promotion policy",
    "promotion rule", "recommendation generation", "policy memory",
    "heuristic classification", "cross-session pattern",
)
_LAYER_NARROW_VERBS: tuple[str, ...] = (
    "verify", "check", "existence", "evidence", "marker",
    "completion", "artifact",
)

# --- Delegation policy (lightweight role/authority/freshness) ----------------
# /go can delegate to claude_main, claude_subagent, local_fast, agy, pi_ccr.
# This policy assigns bounded roles without a new multi-agent orchestrator.
_ROLE_VALUES = ("claude_main", "claude_subagent", "local_fast", "agy", "pi_ccr")
_MUTATION_AUTHORITY: dict[str, str] = {
    "claude_main": "final completion authority via /go evidence gates; integrates worker output",
    "claude_subagent": "bounded worker scope explicitly assigned by /go; no shared-state mutation outside scope",
    "local_fast": "local_surgical tasks only; no repo/shared-state mutation outside the bounded patch",
    "agy": "advisory only; cannot mutate repo or shared state",
    "pi_ccr": "isolated worktree / full_go path only; never mutates the main tree directly",
}
# Signals that the advisory review needs an outside / adversarial / model-diverse reviewer.
_ADVERSARIAL_MARKERS: tuple[str, ...] = (
    "adversarial", "pre-mortem", "premortem", "red team", "red-team",
    "roi", "decision", "should we", "compare", "tradeoff", "trade-off",
    "optimal", "strateg",
)
_MODEL_DIVERSITY_MARKERS: tuple[str, ...] = (
    "model-diverse", "model diverse", "cross-model", "second opinion",
    "second-opinion", "failover", "isolated harness", "worktree",
    "external model", "outside model", "pi ", "ccr",
)

# --- Mutation-authority enforcement (tool-call boundary) ---------------------
# Tools that mutate repo/shared state. The PreToolUse gate denies these for
# advisory roles and path-checks them for worker roles against worker_scope.
_MUTATING_TOOLS: tuple[str, ...] = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# Bash subcommands that touch shared state beyond the bounded patch. A worker
# role using one of these is denied (advisory roles are denied all mutating
# tools regardless).
_SHARED_STATE_TOOL_MARKERS: tuple[str, ...] = (
    "git push", "git commit", "git reset", "git checkout", "git rebase",
    "git stash", "git merge", "git tag", "git rm",
    "settings.json", "hooks.json", "plugin.json", "marketplace.json",
    "plugin-audit-and-fix", "--bump", "pip install", "npm install",
)
# Concrete-path extractor for worker_scope. Matches dotted relative paths
# (foo.py, src/bar/baz.py) and absolute Windows/POSIX paths. Intentionally
# narrow: false positives would over-bound legitimate edits.
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/][\w./\\-]+|"                # P:/... or C:\...
    r"(?:[\w.-]+/){1,6}[\w.-]+\.[A-Za-z]{1,8}|"    # src/foo/bar.py
    r"[\w-]+\.(?:py|md|json|sh|ts|tsx|js|toml|yaml|yml))"  # foo.py
)

# --- Mixed-work status + decision_kind classification (goal reqs 4-7) ---------
# Distinguish WHY /go pauses. "blocked_*" = do NOT ask the user to approve
# (state the blocker + the next evidence step); "pause_for_authorization" =
# genuine user authority (do ask); "partial_readonly_done" / "recommendation_ready"
# = safe to proceed / advisory ready. Collapsing all four into one pause is the
# decision-fatigue the goal removes.
# Gate-weakening intent = blocked by policy (never ask user to approve a guardrail
# reduction); missing-evidence = blocked by prerequisite; shared-state surface =
# genuine user authorization (req 16.g).
_POLICY_WEAKEN_MARKERS: tuple[str, ...] = (
    "weaken the gate", "weaken the hook", "demote to warn", "make advisory",
    "disable the gate", "disable the hook", "skip the gate", "bypass the gate",
    "fail-open", "fail open", "relax the gate", "loosen the gate",
    "soft block", "soft-block", "exempt from the gate",
)
_MISSING_EVIDENCE_MARKERS: tuple[str, ...] = (
    "missing corpus", "no corpus", "missing data", "no evidence",
    "missing transcript", "unavailable corpus", "no benchmark", "no baseline",
    "missing benchmark", "missing baseline", "no test corpus", "no held-out",
)
_SHARED_STATE_MARKERS: tuple[str, ...] = (
    "settings.json", "hooks.json", "plugin.json", "router.py",
    ".env", "provider-config", "marketplace.json",
)

# --- Closure check (reproduce-first + confirm-closed) -------------------------
# Bugfix/regression/hook-FP/stale-warning tasks must prove the original symptom
# is gone, not just that a related test passes. Detected at preflight; the worker
# fills command_or_procedure / expected_before / expected_after / evidence during
# the run. A task may NOT claim fixed/complete unless confirm_closed_passes()
# (or the report explicitly explains why direct closure is impossible).
_CLOSURE_SOURCE_VALUES = (
    "user_reported_symptom", "repro_command", "field_failure",
    "hook_fp", "regression", "none",
)
# Prompts that describe fixing a reported defect / broken behavior.
_BUGFIX_MARKERS: tuple[str, ...] = (
    "fix ", "fixes", "fixed", "bug", "defect", "broken", "crash", "crashes",
    "fails", "failure", "incorrect", "wrong result", "error when",
    "exception when", "no longer works", "stopped working",
)
# Regression: used-to-work framing — strongest closure signal.
_REGRESSION_MARKERS: tuple[str, ...] = (
    "regression", "used to work", "previously worked", "broke in",
    "broke after", "no longer", "regressed",
)
# Hook/gate false positive (matches FMM hook vocabulary).
_HOOK_FP_MARKERS: tuple[str, ...] = (
    "false positive", "false-positive", " fp ", "misfire", "misfires",
    "misfired", "spurious", "phantom", "overblocks", "over-blocks",
    "overfires", "over-fires", "wrongly blocks",
)
# Stale warning / reminder that keeps firing after its condition is satisfied.
_STALE_WARNING_MARKERS: tuple[str, ...] = (
    "stale warning", "stale reminder", "keeps firing", "re-fires",
    "refires", "re-firing", "still fires", "already satisfied",
    "already fixed", "already done",
)
# Source-classification markers — pick the closure_check.source enum value.
_USER_REPORTED_MARKERS: tuple[str, ...] = (
    "user reported", "user-reported", "reported symptom", "reports that",
    "they report", "director reports", "i report",
)
_FIELD_FAILURE_MARKERS: tuple[str, ...] = (
    "field-test", "field test", "in production", "in the field",
    "live failure", "live bug", "on a real",
)
# Reproduce-first gating: cannot-reproduce artifact allows a report but not a
# "Fixed" completion claim over the original symptom.
_CANNOT_REPRODUCE_MARKERS: tuple[str, ...] = (
    "cannot reproduce", "can't reproduce", "no repro", "not reproducible",
    "intermittent", "flaky", "non-deterministic", "nondeterministic",
    "race condition", "only happens sometimes",
)
# High-risk surface closure: confirm-closed must use the actual entry point or
# registered path where practical (req. 7). Reuses _HIGH_RISK_MARKERS.

# --- Discovery-first / lifecycle hygiene (goal: discovery-first + verification) ---
# Operational surfaces where /go must discover writer/storage/reader/lifecycle
# BEFORE prescribing implementation. Each entry: (markers, surface label).
_OPERATIONAL_SURFACES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("worktree", "work tree", "git worktree"), "worktree"),
    (("hook", "stop gate", "pretooluse", "posttooluse", "sessionstart"), "hook"),
    (("gate", "enforce", "router.py", "dispatcher", "dispatch"), "gate"),
    (("state dir", "go_state_dir", "session state", "state tree"), "state"),
    (("phase marker", "task-selected", ".dispatched", "marker file"), "markers"),
    (("plugin cache", "version-keyed cache", "cache copy", "stale cache", "cache"), "cache"),
    (("session pointer", "go-sessions", "pointer store", "session id"), "session"),
    (("export", "transcript", "session export"), "export"),
    (("artifact lifecycle", "temp artifact", ".artifacts"), "artifact-lifecycle"),
    (("branch", "feature branch", "merged branch"), "branch"),
)
# /go-created resources that carry a lifecycle/cleanup obligation.
_LIFECYCLE_RESOURCES: tuple[str, ...] = (
    "worktree", "branch", "state dir", "session pointer",
    "marker", "cache copy", "temporary export", "artifact",
)
# Safe worktree prune predicate (req. 6): ALL conditions must hold before /go
# will even propose prune. Dry-run/report-only first; never auto-delete.
_WORKTREE_PRUNE_PREDICATE: tuple[str, ...] = (
    "age >= threshold (default 14d since creation)",
    "git status clean (no uncommitted / unstaged work)",
    "branch merged into main OR explicitly marked disposable by director",
    "report-only dry run first (list, do not remove)",
    "no removal without explicit director approval",
)
# Verification paths ranked by confidence-per-effort (req. 4). Order matters:
# higher confidence first. The worker picks the highest affordable path.
_VERIFICATION_RANKING: tuple[tuple[str, str, str], ...] = (
    # (path, confidence, effort)
    ("empirical end-to-end reproduction against a real oracle",
     "highest", "high"),
    ("direct invocation of the registered entry point (hook/router)",
     "high", "medium"),
    ("integration test crossing the real state/dispatch boundary",
     "high", "medium"),
    ("targeted unit test on the pure-logic transform",
     "medium", "low"),
    ("static code trace (grep/read of the writer/reader path)",
     "medium-low", "low"),
)


def _word_boundary_match(marker: str, text: str) -> bool:
    """Token/word-boundary match so bare markers like "gate" don't fire inside
    "investi-gate-". Markers that start AND end with an alphanumeric use
    ``\\b…(s?)\\b`` (optional plural so "worktree" matches "worktrees");
    symbolic markers (``.artifacts``, ``router.py`` edges, etc.) fall back to
    literal substring since they can't collide with real words.
    """
    if marker and marker[0].isalnum() and marker[-1].isalnum():
        return re.search(r"\b" + re.escape(marker) + r"s?\b", text) is not None
    return marker in text


# Precompiled per-surface regexes are not used because matching must respect
# marker shape (alphabetic vs symbolic); _word_boundary_match handles both.
_PROVENANCE_TIERS = ("verified", "inference", "assumption")


def _discovery_evidence_passes(discovery_evidence: dict) -> bool:
    """Findings non-empty AND every finding carries a valid provenance tier."""
    de = discovery_evidence or {}
    findings = de.get("findings")
    if not isinstance(findings, list) or not findings:
        return False
    for f in findings:
        prov = (f or {}).get("provenance")
        if prov not in _PROVENANCE_TIERS:
            return False
    return True

# Phase 4: Verification Policy Matrix — maps prompt task-type keywords to the
# verification modes that should be suggested. Each entry is (keyword, suggestions).
# The suggestions override the generic keyword checks in verification_suggestions.
# Only matched when the prompt contains the keyword; if none match, normal fallback.
_VERIFICATION_POLICY_MATRIX: list[tuple[tuple[str, ...], list[str], str]] = [
    # (keywords, suggestions, note_key)
    (
        ("hook change", "gate change", "stop gate", "pretooluse", "posttooluse",
         "pre tool use", "post tool use", "sessionstart"),
        [
            "python .claude/hooks/<hook>.py < sample.json  # direct hook invocation",
            "python -m pytest <test_file>.py -q  # targeted negative test",
            "Verify fail-open/fail-closed: trigger the gate with valid/invalid input",
        ],
        "hook_gate",
    ),
    (
        ("/go change", "orchestrator change", "orchestrate.py", "common_tail"),
        [
            "python skills/go/scripts/orchestrate.py --help  # CLI smoke",
            "python -m pytest tests/test_orchestrate_dispatch.py -q  # artifact contract test",
            "No-dispatch/no-mutation assertion: confirm active-task is NOT mutated by dry-run",
        ],
        "orchestrator",
    ),
    (
        ("classifier change", "heuristic change", "classify_dispatch", "rewrite_goal",
         "verification_suggestion", "prompt classification", "preflight propose"),
        [
            "python -m pytest <test_file>.py -q  # table-driven behavior tests",
            "Add at least one mutation/sentinel: invert a classifier branch and confirm tests fail",
        ],
        "classifier",
    ),
    (
        ("telemetry change", "summarizer change", "telemetry summarizer", "log_event"),
        [
            "python -m pytest <test_file>.py -q  # read-only/idempotence test",
            "Verify: no mutation, no side effects, no crash on empty data",
        ],
        "telemetry",
    ),
    (
        ("claim change", "validation change", "claim-honesty", "evidence hook",
         "claim gap", "unverified claim"),
        [
            "python <hook>.py < sample.json  # positive case",
            "Run with hedged/not-run input — must suppress the warning",
            "Run with bare claim — must produce the warning (if promoted)",
        ],
        "claim_validation",
    ),
    (
        ("test drift", "test/source", "stale test", "expectation mismatch"),
        [
            "Record source-vs-test triage: observed source, observed test, which is authoritative, why",
            "Do not blindly change tests or source — classify as source bug, stale test, or missing coverage",
        ],
        "test_drift",
    ),
]


# ---
# Failure Mode Matrix -- proactive failure anticipation
# ---
_FMMRow = tuple[tuple[str, ...], list[str], list[str], list[str], list[str], list[str]]

_FAILURE_MODE_MATRIX: list[_FMMRow] = [
    (
        ('hook change', 'gate change', 'stop gate', 'pretooluse', 'posttooluse', 'pre tool use', 'post tool use', 'sessionstart', 'hook.py', 'hook gate', 'stop hook', 'stop.py', 'hook'),
        ['Wrong hook file or wrong event type', 'Invalid JSON output shape (Zod validation failure)', 'Overblocking on valid input', 'No fail-open path on exception'],
        ['Read hook dispatcher (router.py or hooks.json) before editing', 'Read the hook file to confirm event routing'],
        ['grep hook name in settings.json + all plugin hooks.json', 'Run direct invocation to capture real stdout'],
        ['Direct invocation invalid input must exit cleanly (fail-open)', 'Direct invocation valid input must emit schema-valid JSON', 'Negative test: gate condition that should NOT fire'],
        ['Must show direct invocation stdout (not just return value)', 'Must show negative case ran without blocking', 'Live Stop JSON validation failure prevents DONE claim'],
    ),
    (
        ('/go change', 'go change', '/go', 'orchestrator change', 'orchestrate.py', 'common_tail', 'worker prompt', 'task_prompt'),
        ['Mutating active-task file during dry-run', 'Changing dispatch behavior without updating CLI smoke test', 'Breaking plan/planless branch split logic', 'Delegated agents writing partial work into shared tree', 'Reclassifying results from truncated authoritative output'],
        ['Read orchestrate.py CLI entry points before editing', 'Confirm which branch (prompt/plan/recon-bypass) is affected', 'For multi-phase tasks: delegation requires isolation/patch/disjoint plan before mutation', 'Phase mutation needs permitted-files + proposed-changes + verification + rollback plan'],
        ['grep function call sites of any changed function', 'Read the test file for the affected code path'],
        ['Active-task JSON must NOT be mutated by --recon-bypass or --preflight-only', 'orchestrate.py --help must exit 0 after change', 'If phase says run-once-defines-result, save full output to file before classification', 'If authoritative output truncated, mark phase FAILED or restart once -- do not silently reclassify'],
        ['Must show active-task diff (or no-diff assertion) between pre/post dry-run', 'If user requested strict report format, final output must match it exactly', 'No live Stop JSON validation failure may remain when declaring DONE'],
    ),
    (
        ('classifier change', 'heuristic change', 'classify_dispatch', 'rewrite_goal', 'verification_suggestion', 'prompt classification', 'preflight propose', 'failure_mode'),
        ['Overmatching -- new rule matches unintended prompts', 'Undermatching -- new rule misses intended prompts', 'No adversarial/mutation test to prove detection is real'],
        ['Read full classify_dispatch function before editing', 'Read existing keyword lists for potential overlap'],
        ['Run classify_dispatch on 3+ prompts: one match, two no-match', 'Check keywords for collision with existing rules'],
        ['Table-driven tests: each rule >=1 positive + >=1 negative case', 'Mutation test: invert branch, confirm tests FAIL', 'Sentinel test: must-NOT-match prompt produces default'],
        ['Must show table-driven test results (positive + negative)', 'Must show mutation test confirmed detection is real'],
    ),
    (
        ('new helper', 'new hook', 'new skill', 'new script', 'add function', 'create module', 'helper function'),
        ['Duplicating existing functionality (search before creating)', 'Missing error handling or edge cases', 'No direct invocation test proving entry point works'],
        ['Search codebase for existing implementations of same function', 'Read the entry point that will call this helper'],
        ['grep similar function/module names before creating', 'Read calling module to understand expected interface'],
        ['Direct invocation test from CLI (not just import)', 'Negative test: invalid input, confirm clean error'],
        ['Must show grep results proving no duplicate (or justify new)', 'Must show direct invocation output'],
    ),
    (
        ('high risk', 'critical file', 'do not modify', 'forbidden file', 'protected file', 'security hook', 'permission'),
        ['Editing a file outside the intended scope', 'Changing behavior other systems depend on', 'Missing a dependency chain break'],
        ['Read the full file before editing', 'Identify all callers/consumers of the changed code'],
        ['grep imports/usages of the changed function/class', 'Read any file that imports the changed module'],
        ['Confirm all existing tests still pass after change', 'Verify no new warnings or behavior change in dependent code'],
        ['Must show grep of all import sites and confirm they are unaffected'],
    ),
    (
        ('telemetry change', 'telemetry', 'summarizer change', 'telemetry summarizer', 'log_event', 'log hook', 'agentic reliability'),
        ['Adding side effects to a read-only path', 'Crashing on empty/malformed data', 'Mutating state that should be append-only'],
        ['Read telemetry pipeline before editing', 'Confirm change is in a read or write path'],
        ['Run with empty input and empty log files', 'Check log format unchanged (append-only invariant)'],
        ['Run with empty data: must not crash', 'Run twice: must be idempotent', 'Verify no mutation of source data files'],
        ['Must show idempotence test result', 'Must show no side effects on source data'],
    ),
    (
        ('claim change', 'validation change', 'claim-honesty', 'evidence hook', 'claim gap', 'unverified claim', 'honesty gate'),
        ['Gate fires on hedged/not-run claims (false positive)', 'Gate misses bare unverified claims (false negative)', 'Gate blocks when it should only warn (wrong severity)'],
        ['Read the gate pattern list before editing', 'Read the gate decision path (block vs warn vs allow)'],
        ['Run with 3 cases: bare claim, hedged claim, evidence-backed claim', 'Check if gate is in ADVISORY or BLOCK mode'],
        ['Hedged claim must NOT trigger blocking action', 'Bare claim must trigger the gate action', 'Evidence-backed claim must pass cleanly'],
        ['Must show all three cases ran with expected outcomes'],
    ),
    (
        ('test drift', 'test/source', 'stale test', 'expectation mismatch', 'test failure', 'failing test', 'broken test'),
        ['Blindly editing the test to match a broken source', 'Blindly editing the source to match a broken test', 'Not classifying: source bug vs stale test vs missing coverage'],
        ['Record source-vs-test triage: what does source do, what does test expect', 'Determine which is authoritative and why'],
        ['Read the test file and the source file it tests', 'Check git blame/log for recent changes to either file'],
        ['Classify the failure before fixing: source bug, stale test, or missing coverage', 'Fix the authoritative side; update the other to match'],
        ['Must state triage classification before editing', 'Must show fix changed authoritative side (not just test)'],
    ),
    (
        ('generated', 'cache change', 'canonical source', 'auto-generated', 'bidir sync', 'cache rebuild', 'plugin cache'),
        ['Patching generated/cached artifact instead of canonical source', 'Forgetting to rebuild cache after source change', 'Source and cache diverge silently'],
        ['Identify canonical source file and its generation path', 'Read the generation/cache-build command'],
        ['grep generation command or bidir_sync config', 'Check if file is in source or cache (git status + path)'],
        ['Regenerate artifact from source and confirm match', 'If direct edit intentional, document why source path is bypassed'],
        ['Must state canonical source location before editing', 'Must run regeneration or explain bypass'],
    ),
    (
        ('review', 'audit', 'diagnosis', 'rca', 'root cause', 'investigate', 'check status', 'assess', 'inspect'),
        ['Reviewing prompt text only without reading actual source files', 'Making claims without citing file:line evidence', 'Missing actual failing path (only testing synthetic inputs)'],
        ['Read the actual files referenced in the review, not just summaries', 'Build an evidence ledger: each claim needs a file:line source'],
        ['For each claim, verify with grep/read on the real file', 'Distinguish observed (you ran it) vs inferred (you guessed)'],
        ['Each factual claim must cite a specific file:line or tool output', 'Claims marked as verified must have a discriminating test result', 'Uncertainty must be explicit'],
        ['Must show evidence ledger with file:line for each key claim', 'Must not use pytest as sole verification for non-test reviews'],
    ),
]


def failure_mode_guidance(prompt: str) -> dict[str, list[str]] | None:
    """Match a prompt against the Failure Mode Matrix and return guidance.

    Returns a dict with keys:
      failure_modes, required_recon, search_evidence,
      negative_tests, claim_requirements
    or None if no task-type match (trivial/ambiguous prompts get nothing).
    """
    p = " ".join(prompt.split()).strip().lower()
    if not p:
        return None
    best_score = 0
    best_row = None
    # _HOOK_GATE_IDX is the index of the hook/gate row (broadest, most keywords).
    # On tie, prefer the more-specific row (not hook/gate) to reduce false matches.
    _HOOK_GATE_IDX = 0
    for idx, row in enumerate(_FAILURE_MODE_MATRIX):
        hits = sum(1 for kw in row[0] if kw in p)
        if hits > best_score:
            best_score = hits
            best_row = row
        elif hits == best_score and hits > 0 and best_row is not None:
            # Tie: prefer the non-hook/gate row (more specific match)
            if idx != _HOOK_GATE_IDX:
                best_row = row
    if best_row is None or best_score == 0:
        return None
    # Very short prompts (<=3 words) with only 1 keyword: skip to avoid noise.
    if best_score < 2 and len(p.split()) <= 3:
        return None
    return {
        "failure_modes": best_row[1],
        "required_recon": best_row[2],
        "search_evidence": best_row[3],
        "negative_tests": best_row[4],
        "claim_requirements": best_row[5],
    }


def failure_mode_guidance_all(prompt: str) -> dict[str, list[str]] | None:
    """Like failure_mode_guidance() but includes up to 2 secondary rows.

    Returns a dict with the same keys as failure_mode_guidance() for the
    primary match, plus a "secondary" key containing a list of dicts with
    the same shape for up to 2 additional matching rows.

    Trivial/unmatched prompts return None (no noise).
    Secondary rows are capped at 2 and ordered by keyword hit count
    (most-relevant first).  The hook/gate row is excluded from secondaries
    when it would be a secondary (it is the broadest and least useful as
    additional context).
    """
    primary = failure_mode_guidance(prompt)
    if primary is None:
        return None

    p = " ".join(prompt.split()).strip().lower()
    _HOOK_GATE_IDX = 0

    # Collect all rows with hits, excluding the one that won primary.
    primary_fms = primary["failure_modes"]
    candidates = []  # (score, idx, row)
    for idx, row in enumerate(_FAILURE_MODE_MATRIX):
        if row[1] == primary_fms:
            continue
        hits = sum(1 for kw in row[0] if kw in p)
        if hits > 0:
            candidates.append((hits, idx, row))

    # Sort by score descending, then by specificity (prefer non-hook/gate)
    candidates.sort(key=lambda t: (-t[0], 0 if t[1] != _HOOK_GATE_IDX else 1))

    secondary = []
    for _score, _idx, row in candidates[:2]:
        secondary.append({
            "failure_modes": row[1],
            "required_recon": row[2],
            "search_evidence": row[3],
            "negative_tests": row[4],
            "claim_requirements": row[5],
        })

    result = dict(primary)
    result["secondary"] = secondary
    return result


# --- FMM-derived verificationPolicy fallback ---

# FMM row first-keyword to verification policy key.
# Only used when _verification_policy_key() returns None (no direct match).
_FMM_TO_POLICY: dict[str, str] = {
    "hook change": "hook_gate",
    "/go change": "orchestrator",
    "go change": "orchestrator",
    "classifier change": "classifier",
    "telemetry change": "telemetry",
    "claim change": "claim_validation",
    "test drift": "test_drift",
    "review": "claim_validation",
}


def verification_policy_from_fmm(prompt: str) -> tuple[str | None, str]:
    """Derive verificationPolicy from FMM primary row when direct match fails.

    Returns (policy_key, source) where source is one of:
      "direct-policy-match" -- _verification_policy_key returned a result
      "fmm-derived" -- fallback from FMM primary row mapping
      "none" -- no policy found
    """
    rewritten = rewrite_goal(prompt)

    # Step 1: try direct policy match (existing path)
    direct = _verification_policy_key(rewritten)
    if direct is not None:
        return direct, "direct-policy-match"

    # Step 2: FMM-derived fallback -- match prompt, map first keyword
    fmm_result = failure_mode_guidance(rewritten)
    if fmm_result is None:
        return None, "none"

    # Find which FMM row matched
    for row in _FAILURE_MODE_MATRIX:
        if row[1] == fmm_result["failure_modes"]:
            first_kw = row[0][0]
            fallback = _FMM_TO_POLICY.get(first_kw)
            if fallback is not None:
                return fallback, "fmm-derived"
            break

    return None, "none"


def _normalize(prompt: str) -> str:
    return " ".join(prompt.split()).strip()


# --- Goal-size guard ---

GOAL_MAX_CHARS = 4000


def compress_goal(text: str, max_chars: int = GOAL_MAX_CHARS) -> str:
    """Compress a goal/prompt to fit within max_chars.

    Preserves: goal statement, requirements, constraints, verification,
    deliverables. Drops verbose explanation and examples.
    Returns truncated text with 'Length: N / 4000' suffix when compressed.
    """
    if len(text) <= max_chars:
        return text

    priority_markers = (
        "mission:", "goal:", "requirements:", "constraints:", "verify",
        "test", "report:", "deliverables:", "do not", "must", "shall",
        "phase", "task", "blocked", "fence",
    )
    # Footer is ~25 chars: "\n\nLength: NNNN / 4000"
    footer_budget = 30
    lines = text.split("\n")
    kept: list[str] = []
    budget = max_chars - footer_budget

    # First pass: priority lines
    for line in lines:
        stripped = line.strip().lower()
        if any(m in stripped for m in priority_markers):
            if budget - len(line) - 1 > 0:
                kept.append(line)
                budget -= len(line) + 1
                budget -= len(line) + 1

    if budget > 100:
        for line in lines:
            if line not in kept:
                if budget - len(line) > 0:
                    kept.append(line)
                    budget -= len(line) + 1

    result = "\n".join(kept)
    # Ensure final output including footer fits within max_chars
    footer = f"\n\nLength: NNNN / {max_chars}"
    available = max_chars - len(footer)
    if len(result) > available:
        result = result[:available]

    # Recount actual length in footer
    return result + f"\n\nLength: {len(result) + len(footer)} / {max_chars}"


# --- Thought-partner enhancement ---

_THOUGHT_PARTNER_KEYWORDS = {
    "hook", "gate", "stop", "orchestrat", "rout", "refactor",
    "audit", "review", "rca", "diagnos", "design", "architect",
    "multi-phase", "quarantine", "migration", "classif",
}


def thought_partner_assessment(prompt: str) -> dict[str, object] | None:
    """Generate thought-partner assessment for nontrivial tasks.

    Returns None for trivial prompts. Otherwise returns a dict with:
      taskIntent, impliedRequirements, missingImprovements,
      unsafeAssumptions, missingVerification, recommendedStrategy,
      reasoningSummary
    """
    p = " ".join(prompt.split()).strip().lower()
    if not p or len(p.split()) < 4:
        return None

    matched = [kw for kw in _THOUGHT_PARTNER_KEYWORDS if kw in p]
    if not matched:
        return None

    intent = prompt.strip()
    if len(intent) > 200:
        intent = intent[:200] + "..."

    implied: list[str] = []
    if any(k in p for k in ("hook", "gate", "stop")):
        implied.append("schema-valid output for all registered hooks")
        implied.append("fail-open path on exception")
    if any(k in p for k in ("orchestrat", "rout")):
        implied.append("CLI smoke test after changes")
        implied.append("active-task JSON integrity")
    if any(k in p for k in ("review", "audit", "rca")):
        implied.append("evidence ledger with file:line citations")
        implied.append("distinction between observed vs inferred claims")
    if any(k in p for k in ("refactor", "design")):
        implied.append("backward-compatible or documented breakage")
        implied.append("existing tests still pass")

    missing: list[str] = []
    if "test" not in p and "pytest" not in p:
        missing.append("add targeted tests (not generic pytest)")
    if "verify" not in p and "check" not in p:
        missing.append("define verification commands")
    if "rollback" not in p and "revert" not in p:
        missing.append("define rollback strategy")
    if "plan" not in p and "phase" not in p:
        missing.append("break into phases if task is broad")

    assumptions: list[str] = []
    if any(k in p for k in ("hook", "gate")):
        assumptions.append("may assume current hook output is schema-valid without checking")
    if any(k in p for k in ("fix", "patch")):
        assumptions.append("may assume root cause without discriminating test")

    verification: list[str] = []
    if "test" not in p:
        verification.append("run existing test suite to confirm no regression")
    verification.append("verify changes against real data, not just synthetic fixtures")

    return {
        "taskIntent": intent,
        "impliedRequirements": implied[:5],
        "missingImprovements": missing[:4],
        "unsafeAssumptions": assumptions[:3],
        "missingVerification": verification[:3],
        "recommendedStrategy": "serialized-implementation-with-advisory-gates",
        "reasoningSummary": f"Matched task types: {', '.join(matched)}. "
        "Apply failure-mode-specific safeguards, verify against real data.",
    }


# --- Plan review ---

_PLAN_KEYWORDS = {"phase", "step", "stage", "task 1", "task 2", "first", "then", "after that", "finally"}


def plan_review(prompt: str) -> dict[str, object] | None:
    """Analyze a supplied plan and return improvement suggestions."""
    p = " ".join(prompt.split()).strip().lower()
    if not p:
        return None

    plan_signals = sum(p.count(kw) for kw in _PLAN_KEYWORDS)
    if plan_signals < 2:
        return None

    improvements: list[str] = []
    dependencies: list[str] = []
    conflicts: list[str] = []
    missing_tests: list[str] = []
    missing_rollback: list[str] = []
    unsafe: list[str] = []
    non_blocking: list[str] = []

    if any(kw in p for kw in ("orchestrat", "stop.py", "settings.json", "router")):
        conflicts.append("shared files: orchestrate.py, Stop.py, settings.json, router.py may conflict")
        improvements.append("use disjoint-file lock plan or sequential mutation for shared files")

    if "test" not in p and "verify" not in p:
        missing_tests.append("add verification step for each phase")
        improvements.append("add test/verify command after each phase completion")

    if "rollback" not in p and "revert" not in p:
        missing_rollback.append("define rollback command for each phase")
        improvements.append("add rollback strategy per phase (git restore / git checkout)")

    if any(kw in p for kw in ("move", "delete", "quarantine", "git mv")):
        unsafe.append("file move/delete operations need isolation")
        improvements.append("use isolated worktree or patch bundle for move/delete phases")

    if "phase" in p:
        improvements.append("explicitly list which phases block which others")
        dependencies.append("identify blocking dependencies between phases")

    if plan_signals >= 3:
        non_blocking.append("analysis/review/test-design lanes can run in parallel with implementation")
        improvements.append("parallelize non-mutating analysis lanes")

    if "authoritative" not in p and ("quarantine" in p or "move" in p or "delete" in p):
        improvements.append("capture authoritative source output before classification")
        non_blocking.append("evidence-scout lane for authoritative output capture")

    if not improvements:
        improvements.append("verify each phase produces expected artifact")

    return {
        "planProvided": True,
        "planImprovements": improvements[:6],
        "dependencies": dependencies[:3],
        "independentPhases": [],
        "sharedFileConflicts": conflicts[:2],
        "missingTests": missing_tests[:2],
        "missingRollback": missing_rollback[:2],
        "unsafeMutation": unsafe[:2],
        "betterExecutionOrder": [],
        "nonBlockingWork": non_blocking[:3],
    }


# --- Parallel strategy detection ---

_LANE_EVIDENCE_SCOUT: dict[str, object] = {
    "name": "evidence-scout",
    "mayMutate": False,
    "purpose": "map current code paths, references, existing behavior",
    "output": "evidence ledger",
}

_LANE_TEST_DESIGNER: dict[str, object] = {
    "name": "test-designer",
    "mayMutate": False,
    "purpose": "propose regression, negative, and behavioral tests",
    "output": "test plan",
}

_LANE_CRITIC: dict[str, object] = {
    "name": "critic",
    "mayMutate": False,
    "purpose": "critique plan/diff/final report against original request and known failure modes",
    "output": "review memo",
}

_LANE_ALTERNATIVE_DESIGNER: dict[str, object] = {
    "name": "alternative-designer",
    "mayMutate": False,
    "purpose": "compare bridge patch vs refactor vs larger architecture change",
    "output": "options memo",
}

_PARALLEL_KEYWORDS: dict[str, list[str]] = {
    "hook": ["evidence-scout", "test-designer", "critic"],
    "gate": ["evidence-scout", "test-designer", "critic"],
    "stop": ["evidence-scout", "test-designer", "critic"],
    "orchestrat": ["evidence-scout", "test-designer", "critic"],
    "rout": ["evidence-scout", "test-designer", "critic", "alternative-designer"],
    "refactor": ["evidence-scout", "test-designer", "critic", "alternative-designer"],
    "multi-phase": ["evidence-scout", "test-designer", "critic"],
    "audit": ["evidence-scout", "test-designer", "critic"],
    "review": ["evidence-scout", "test-designer", "critic"],
    "quarantine": ["evidence-scout", "test-designer", "critic"],
    "classif": ["evidence-scout", "test-designer", "critic"],
    "rca": ["evidence-scout", "test-designer", "critic"],
    "diagnos": ["evidence-scout", "test-designer", "critic"],
    "design": ["evidence-scout", "test-designer", "critic", "alternative-designer"],
    "architect": ["evidence-scout", "test-designer", "critic", "alternative-designer"],
}

_MUTATION_KEYWORDS = {
    "quarantine", "move", "delete", "git mv", "git rm", "cleanup",
    "refactor", "edit", "add", "modify", "rewrite", "replace", "update",
    "implement", "rename", "split", "extract",
}
# TASK-001.3: positive pure-analysis allowlist. A prompt is eligible for
# full-parallel ONLY when it matches read-only analysis AND carries no mutation
# verb. Caller-declared ``read_only`` envelope is the preferred future signal;
# this keyword set is the fallback discriminator.
_PURE_ANALYSIS_KEYWORDS = {
    "audit", "review", "investigate", "analyze", "inspect", "assess",
    "evaluate", "scan", "examine", "survey", "map", "trace",
}
# Word-boundary design-ambiguity detector. Replaces the bare substring list
# (the old ``"rout"`` matched route/routing but also routine/scout/throughout).
_DESIGN_AMBIGUITY_RE = re.compile(r"\b(?:refactor|design|architect|route|routes|routing|router)\b")
_TRIVIAL_KEYWORDS = {"typo", "rename variable", "fix whitespace", "update comment", "say hi"}

_LANE_MAP = {
    "evidence-scout": _LANE_EVIDENCE_SCOUT,
    "test-designer": _LANE_TEST_DESIGNER,
    "critic": _LANE_CRITIC,
    "alternative-designer": _LANE_ALTERNATIVE_DESIGNER,
}


def parallel_strategy_for_task(prompt: str) -> dict[str, object]:
    """Determine parallel-agent strategy for a task.

    Returns a dict with keys:
      recommended, reason, mode, lanes, mutationPolicy,
      spawnByDefault, overheadRisk
    """
    p = " ".join(prompt.split()).strip().lower()
    if not p:
        return {
            "recommended": False,
            "reason": "empty prompt",
            "mode": "none-trivial",
            "lanes": [],
            "mutationPolicy": "serialized",
            "spawnByDefault": False,
            "overheadRisk": "none",
        }

    for kw in _TRIVIAL_KEYWORDS:
        if kw in p:
            return {
                "recommended": False,
                "reason": f"trivial task (matched '{kw}')",
                "mode": "none-trivial",
                "lanes": [],
                "mutationPolicy": "serialized",
                "spawnByDefault": False,
                "overheadRisk": "none",
            }

    is_mutation = any(kw in p for kw in _MUTATION_KEYWORDS)
    has_design_ambiguity = bool(_DESIGN_AMBIGUITY_RE.search(p))

    matched_lanes: set[str] = set()
    for kw, lanes in _PARALLEL_KEYWORDS.items():
        if kw in p:
            matched_lanes.update(lanes)

    if not matched_lanes:
        return {
            "recommended": False,
            "reason": "no parallel-benefit task type detected",
            "mode": "none-trivial",
            "lanes": [],
            "mutationPolicy": "serialized",
            "spawnByDefault": False,
            "overheadRisk": "none",
        }

    if "alternative-designer" in matched_lanes and not has_design_ambiguity:
        matched_lanes.discard("alternative-designer")

    lanes = [_LANE_MAP[name] for name in sorted(matched_lanes) if name in _LANE_MAP]

    # TASK-001.3: full-parallel requires positive pure-analysis signal AND no
    # mutation verb. Anything else serializes mutations (no recombination
    # contract exists today — see plan-go-dispatch-safe-rollout decision #4).
    is_pure_analysis = any(kw in p for kw in _PURE_ANALYSIS_KEYWORDS)
    if is_pure_analysis and not is_mutation:
        mode = "full-parallel"
        mutation_policy = "parallel"
    else:
        mode = "analysis-parallel-mutation-serialized"
        mutation_policy = "parent-only unless isolated worktree or patch bundle"

    lane_count = len(lanes)
    if lane_count >= 4:
        overhead = "medium"
    elif lane_count >= 3:
        overhead = "low-medium"
    else:
        overhead = "low"

    reason_parts = []
    for kw in _PARALLEL_KEYWORDS:
        if kw in p:
            reason_parts.append(kw)
    reason = f"nontrivial task (matched: {', '.join(sorted(reason_parts))})"

    return {
        "recommended": True,
        "reason": reason,
        "mode": mode,
        "lanes": lanes,
        "mutationPolicy": mutation_policy,
        "spawnByDefault": True,
        "overheadRisk": overhead,
    }


# --- Mutation plan detection (explicit keyword scan) ---

_MUTATION_PLAN_KEYWORDS = {
    "quarantine": "quarantine",
    "move file": "move",
    "move test": "move",
    "git mv": "move",
    "delete file": "delete",
    "remove file": "delete",
    "git rm": "delete",
    "cleanup": "delete",
    "purge": "delete",
    "mass cleanup": "delete",
}


def requires_mutation_plan(prompt: str) -> dict[str, str] | None:
    """Detect whether a prompt requires a mutation plan (quarantine/move/delete).

    Returns a dict with keys 'reason' and 'kinds' if mutation plan is required,
    or None if the prompt is not a mutation-heavy task.

    This is explicit keyword detection -- NOT inferred from rendered prompt text.
    """
    p = " ".join(prompt.split()).strip().lower()
    if not p:
        return None

    matched_kinds: list[str] = []
    matched_reasons: list[str] = []
    for kw, kind in _MUTATION_PLAN_KEYWORDS.items():
        if kw in p:
            matched_kinds.append(kind)
            matched_reasons.append(kw)

    if not matched_kinds:
        return None

    unique_kinds = list(dict.fromkeys(matched_kinds))  # dedupe, preserve order
    return {
        "reason": f"Prompt contains mutation keywords: {chr(44).join(matched_reasons)}",
        "kinds": unique_kinds,
    }


def rewrite_goal(prompt: str) -> str:
    """Light cleanup that strips common request politeness prefixes only.

    Preserves the user's stated intent. Never narrows scope. Never rewrites
    substance. Returns the cleaned string verbatim.
    """
    p = _normalize(prompt)
    lowered = p.lower()
    for prefix in (
        "can you ",
        "could you ",
        "please ",
        "help me ",
        "i need you to ",
        "i need to ",
        "i need ",
        "i want to ",
        "i want ",
    ):
        if lowered.startswith(prefix):
            p = p[len(prefix):]
            break
    return p.strip()


def classify_dispatch(rewritten: str) -> tuple[str, bool, bool]:
    """Return ``(suggestedDispatch, localEligible, requiresApproval)``.

    Conservative. ``agy`` is never invented (not in ``VALID_DISPATCHES``).
    Defaults to ``pi`` for anything ambiguous. ``localEligible`` only when the
    request clearly looks bounded and implementation-oriented AND a concrete
    file path is cited (avoid promoting ambiguous prompts to local-only).
    """
    low = rewritten.lower()
    is_broad = any(m in low for m in _BROAD_MARKERS)
    path_hits = _PATH_LIKE.findall(rewritten)
    is_bounded = any(m in low for m in _BOUNDED_MARKERS)
    is_conversational = any(m in low for m in _CONVERSATIONAL_MARKERS)

    if is_broad:
        return ("pi", False, True)

    # Bounded implementation with a concrete file: consider local-eligible.
    if (is_bounded or path_hits) and path_hits and len(rewritten) < 240:
        return ("local", True, False)

    if is_bounded:
        return ("pi", False, False)

    # Conversational (status question / pushback / assertion) — pi dispatch,
    # no approval. Detection is conservative: only matches when neither broad
    # nor bounded markers fired, so a task verb in the same prompt still
    # routes to the right branch above.
    if is_conversational:
        return ("pi", False, False)

    # Default: ambiguous → pi, requires approval (no signal either way).
    return ("pi", False, True)


def verification_suggestions(rewritten: str) -> list[str]:
    """Heuristic verification strings. First checks the Verification Policy Matrix
    (phase 4), then falls back to keyword-level heuristics if no matrix entry matches."""
    low = rewritten.lower()
    out: list[str] = []

    # Review / critique / decision prompts must win over the policy matrix below,
    # because "review the hook change" is fundamentally a review task, not a
    # hook-creation task. Check this before the matrix.
    if any(m in low for m in _REVIEW_DECISION_MARKERS):
        out.append(
            "No automated verification applicable; verify by evidence ledger and user decision."
        )
        return out

    # Phase 4: check the Verification Policy Matrix next.
    for keywords, suggestions, _note in _VERIFICATION_POLICY_MATRIX:
        if any(k in low for k in keywords):
            out.extend(suggestions)
            return out

    # Review / critique / decision prompts — no automated verification.
    # pytest is the wrong default for "please critically review..." because
    # the work is judgment, not a unit-test change.
    if any(m in low for m in _REVIEW_DECISION_MARKERS):
        out.append(
            "No automated verification applicable; verify by evidence ledger and user decision."
        )
        return out
    # Diagnose / investigate / root-cause prompts — verify by evidence ledger.
    if any(m in low for m in _EVIDENCE_LEDGER_MARKERS):
        out.append(
            "Verify by evidence ledger: files read, commands run, findings, and uncertainty."
        )
        return out
    if "test" in low or ".py" in low:
        out.append("python -m pytest -q")
    if "hook" in low or "plugin" in low or "/go" in low:
        out.append("python .claude/hooks/<hook>.py < sample.json  # direct-invocation smoke")
    if "schema" in low or "contract" in low:
        out.append("validate generated artifact against expected schema")
    if not out:
        out.append("python -m pytest -q  # default smoke")
    return out


def _verification_policy_key(rewritten: str) -> str | None:
    """Return the Verification Policy Matrix key matching the prompt, or None."""
    low = rewritten.lower()
    for _keywords, _suggestions, note in _VERIFICATION_POLICY_MATRIX:
        if any(k in low for k in _keywords if isinstance(k, str)):
            return note
    return None


# --- Task-intent + execution-tier classification ----------------------------
# Formalizes what was implicit in classify_dispatch's marker sets. Pure
# deterministic transforms over the rewritten prompt.

def classify_intent(rewritten: str) -> str:
    """Classify prompt intent on the ceremony/rigor axis.

    decide/investigate/validate checked before implement (task verbs like
    "review the hook fix" outrank the implement-sounding "fix" inside them).
    >=2 non-implement intents, or implement + another intent => mixed.
    Ambiguous prompts default to implement (safe overkill: full gates apply).
    """
    low = rewritten.lower()
    matched = []
    for intent in ("decide", "investigate", "validate", "implement"):
        if any(m in low for m in _INTENT_MARKERS[intent]):
            matched.append(intent)
    if not matched:
        return "implement"
    non_implement = [i for i in matched if i != "implement"]
    if len(non_implement) >= 2:
        return "mixed"
    if len(non_implement) == 1 and "implement" in matched:
        return "mixed"
    return non_implement[0] if non_implement else "implement"


def detect_risk_signals(rewritten: str) -> dict:
    """Detect high-risk surfaces requiring prompt review."""
    low = rewritten.lower()
    matched = [m for m in _HIGH_RISK_MARKERS if m in low]
    high_risk = bool(matched)
    return {
        "high_risk": high_risk,
        "matched_markers": matched,
        "prompt_review_required": high_risk,
    }


# --- Capability-claim audit (consolidation/deprecation/routing tasks) ----------

def detect_capability_claims(rewritten: str) -> list[dict]:
    """Detect capability claims in the prompt for consolidation/deprecation tasks.

    Returns a list of claim dicts, each with 'command' and 'claimed_status'.
    Empty list means no capability-claim audit is needed.
    """
    low = rewritten.lower()
    matched_triggers = [t for t in _CAPABILITY_AUDIT_TRIGGER_TERMS if t in low]
    if not matched_triggers:
        return []

    # Extract command-like names from the prompt (quoted, slash-prefixed, or named)
    claims = []
    quoted = re.findall(r'[`"\']([/]?[\w-]+(?:\s[\w-]+)?)[`"\']', rewritten)
    slash_cmds = re.findall(r'/[\w-]+', rewritten)
    named = re.findall(r'\b(\w+(?:\s+\w+)?)\s+(?:command|skill|plugin|mode)\b', rewritten)

    seen = set()
    for name in quoted + slash_cmds + named:
        name_clean = name.strip().lower()
        if name_clean and name_clean not in seen and len(name_clean) > 1:
            seen.add(name_clean)
            claimed_status = _infer_claimed_status(rewritten, name)
            claims.append({
                "command": name,
                "claimed_status": claimed_status,
            })

    if not claims:
        claims.append({
            "command": "(task-level consolidation)",
            "claimed_status": "unknown",
        })

    return [{"trigger_terms": matched_triggers, "claims": claims}]


def _infer_claimed_status(rewritten: str, command_name: str) -> str:
    """Infer the claimed status of a command from surrounding context."""
    low = rewritten.lower()
    name_low = command_name.lower()

    sentences = re.split(r'[.!?\n]', low)
    context = ""
    for s in sentences:
        if name_low in s:
            context = s
            break

    if not context:
        return "unknown"

    if any(w in context for w in ("absorb", "absorbed", "merge into", "moved to")):
        return "absorbed"
    if any(w in context for w in ("shipped", "production", "live", "deployed")):
        return "shipped"
    if any(w in context for w in ("stub", "stubs", "no-op", "pass-through")):
        return "stub"
    if any(w in context for w in ("delet", "remov", "gone")):
        return "deleted"
    if any(w in context for w in ("rout", "delegat", "forward")):
        return "routed"
    if any(w in context for w in ("pending", "not yet", "unbuilt", "todo")):
        return "pending"

    return "unknown"


def classify_capability(command_claim: dict) -> str:
    """Classify a capability claim based on source inspection.

    Returns one of: true_stub, deprecation_header_on_retained_engine,
    retained_engine, routed_to_parent, pending_backend, deleted, unknown.
    """
    source_path = command_claim.get("source_path")
    backend_path = command_claim.get("backend_path")
    claimed = command_claim.get("claimed_status", "unknown")

    if not source_path:
        return "unknown"

    source = Path(source_path)
    if not source.exists():
        if claimed in ("absorbed", "routed"):
            return "routed_to_parent"
        return "deleted"

    try:
        content = source.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "unknown"

    content_lower = content.lower()

    stub_signals = ("pass through", "pass-through", "no-op", "noop",
                    "raise deprecation")
    has_stub_header = any(s in content_lower for s in stub_signals)

    has_deprecation = ("deprecat" in content_lower or "deprecated" in content_lower)
    has_real_logic = (
        len(content) > 100
        and ("def " in content or "class " in content or "async def" in content)
        and not has_stub_header
    )

    # Deprecation on retained engine: has deprecation warning AND real logic
    if has_deprecation and has_real_logic:
        return "deprecation_header_on_retained_engine"
    if has_stub_header and not has_real_logic:
        return "true_stub"
    if has_real_logic:
        return "retained_engine"

    if any(r in content_lower for r in ("parent", "forward to", "delegate to", "route to")):
        return "routed_to_parent"

    if backend_path:
        bp = Path(backend_path)
        if not bp.exists():
            return "pending_backend"

    return "unknown"


def derive_execution_tier(task_intent, dispatch, local_eligible, requires_approval, risk) -> str:
    """Pick the minimum sufficient ceremony.

    Tiers: direct_answer | local_surgical | local_rigorous | full_go |
    pause_for_authorization. decide always pauses. High-risk + absent
    prompt-review support forces pause so dispatch cannot silently skip review.
    """
    high_risk = bool(risk.get("high_risk"))
    if task_intent == "decide":
        return "pause_for_authorization"
    # Safe read-only narrowing (goal req. 6 / 16.d): investigate/validate make
    # no mutation, so they never require authorization regardless of an
    # ambiguous dispatch default. Checked BEFORE requires_approval so a
    # path-less "investigate why X" prompt does not collapse to pause.
    if task_intent in ("investigate", "validate"):
        return "local_surgical" if local_eligible else "direct_answer"
    if high_risk and _PROMPT_REVIEW_SUPPORT == "absent":
        return "pause_for_authorization"
    if requires_approval:
        return "pause_for_authorization"
    if dispatch == "local" and local_eligible:
        return "local_rigorous" if high_risk else "local_surgical"
    return "full_go"


def build_decision_advisory(rewritten, task_intent, execution_tier) -> dict:
    """Advisory emitted before any needs_decision / pause report (goal req. 6).

    options, recommendation, long_term_roi, reversibility,
    safest_low_regret_action, exact_authorization_needed.
    """
    snippet = rewritten if len(rewritten) <= 160 else rewritten[:160] + "..."
    options = {
        "decide": [
            "Pause and emit this advisory; defer the decision to the director.",
            "If agent_decidable (low-regret, reversible), proceed and record the rationale.",
        ],
        "mixed": [
            "Execute only the authorized low-risk implementation child now.",
            "Produce evidence for any investigation child.",
            "Defer every decide child with a recommendation.",
        ],
        "investigate": [
            "Read relevant files and produce an evidence ledger; make no code changes.",
            "If root cause is found, propose a follow-up implement task rather than fixing inline.",
        ],
        "validate": [
            "Run targeted verification and emit a validation artifact.",
            "Do not enter full SDLC implementation gates unless implementation is requested.",
        ],
        "implement": [
            "Proceed at the derived execution_tier with the tier's minimum verification.",
        ],
    }.get(task_intent, ["Proceed at the derived execution_tier."])
    recommendation = options[0]
    long_term_roi = (
        "Avoids false completion claims and ceremony mismatch; preserves reviewability."
    )
    reversibility = (
        "High: advisory + pause is reversible; director resumes by authorizing a child."
    )
    if execution_tier == "pause_for_authorization":
        safest_low_regret = (
            "pause_for_authorization: emit advisory, change nothing, await authorization."
        )
        authorization_needed = (
            "Director approval required to dispatch high-risk work without prompt-review support."
        )
    else:
        safest_low_regret = (
            f"Proceed at {execution_tier} with its minimum verification; defer anything undecided."
        )
        authorization_needed = (
            "None beyond the current /go invocation (tier is self-authorized by the prompt)."
        )
    return {
        "prompt_snippet": snippet,
        "options": options,
        "recommendation": recommendation,
        "long_term_roi": long_term_roi,
        "reversibility": reversibility,
        "safest_low_regret_action": safest_low_regret,
        "exact_authorization_needed": authorization_needed,
    }


def derive_report_gate(task_intent, execution_tier, closure_check=None,
                       operational_discovery=None, discovery_evidence=None,
                       capability_claims=None) -> dict:
    """Completion-claim eligibility (goal reqs. 4, 8, 9).

    investigate/validate/decide never enable implementation-completion claims.
    mixed must defer unauthorized children. implement may claim completion only
    at full_go / local_rigorous; local_surgical may claim a targeted fix only.
    When closure_check.required is true, completion is additionally gated by
    confirm_closed_passes() — a passing related test is NOT sufficient (req. 11).
    Missing/malformed closure_check on a required task blocks silent completion
    (req. 9): the worker must produce evidence or an explicit unavailable_reason.

    Discovery gate (discovery goal reqs. 4-6): when operational_discovery.required,
    a recommendation may not be presented as verified unless discovery_evidence
    has ≥1 finding and every finding carries a provenance tier (verified |
    inference | assumption). If incomplete, the report must say discovery_incomplete
    and present the recommendation as advisory, not verified.
    """
    cc = closure_check or {}
    cc_required = bool(cc.get("required"))
    cc_passes = confirm_closed_passes(cc)
    allow_completion = (
        task_intent == "implement"
        and execution_tier in ("full_go", "local_rigorous")
        and (not cc_required or cc_passes)
    )
    allow_targeted_fix_only = (
        task_intent == "implement"
        and execution_tier == "local_surgical"
        and (not cc_required or cc_passes)
    )
    od = operational_discovery or {}
    od_required = bool(od.get("required"))
    de_passes = _discovery_evidence_passes(discovery_evidence)
    discovery_incomplete = od_required and not de_passes
    allow_recommendation_as_verified = not discovery_incomplete

    # Capability-claim audit: blocks "shipped"/"absorbed"/"production" wording
    # when audit is required but not passed.
    cap_claims = capability_claims or []
    cap_audit_required = bool(cap_claims)

    return {
        "allow_implementation_completion_claim": allow_completion,
        "allow_targeted_fix_claim_only": allow_targeted_fix_only,
        "must_defer_unauthorized_children": task_intent == "mixed",
        "closure_check_required": cc_required,
        "confirm_closed_required": cc_required,
        "confirm_closed_passes": cc_passes,
        "unit_test_alone_is_insufficient": cc_required,  # req. 11
        "discovery_evidence_required": od_required,
        "discovery_evidence_passes": de_passes if od_required else True,
        "discovery_incomplete": discovery_incomplete,
        "allow_recommendation_as_verified": allow_recommendation_as_verified,
        "capability_claim_audit_required": cap_audit_required,
        "capability_claim_audit_passed": False,  # worker fills after audit
        "rule": (
            "investigate/validate/decide emit evidence/advisory only, no implementation-completion claim. "
            "mixed reports split + deferred items, no bundled completion claim. "
            + ("closure_check.required: a passing unit test alone does NOT authorize Fixed/Done; "
               "confirm-closed evidence (or an explicit unavailable_reason) is required. "
               if cc_required else "")
            + ("operational_discovery.required: recommendation must carry discovery_evidence "
               "with provenance (verified|inference|assumption); until then discovery_incomplete "
               "and the recommendation is advisory, NOT verified. "
               if od_required else "")
            + ("capability_claim_audit_required: visible-surface check alone is insufficient. "
               "Must verify backend runner/module/function paths exist before claiming "
               "'shipped'/'absorbed'/'production'. Reports must distinguish: visible "
               "consolidation complete | routing complete | backend implementation complete | "
               "pending capability intentionally deferred. "
               if cap_audit_required else "")
        ),
    }


def classify_mixed_work_status(
    rewritten: str, task_intent: str, execution_tier: str, risk: dict, prompt_review_support: str
) -> str:
    """Why /go pauses (goal req. 4). Splits the old single pause_for_authorization
    bucket into four:

    - blocked_policy / blocked_prerequisite — /go must NOT ask the user to
      approve (req. 7); state the blocker + the next evidence-gathering step.
    - pause_for_authorization — genuine user authority (e.g. shared-state
      mutation); /go MAY ask (req. 16.g).
    - recommendation_ready — decide intent; advisory produced, awaiting director.
    - partial_readonly_done — safe read-only narrowing already proceeded.

    Derives from existing classifier signals + three conservative marker sets so
    no new input surface is required. Defaults to partial_readonly_done when
    nothing forces a pause (the gate is silent, not blocking).
    """
    low = rewritten.lower()
    high_risk = bool(risk.get("high_risk"))
    weakens_policy = any(m in low for m in _POLICY_WEAKEN_MARKERS)
    missing_evidence = any(m in low for m in _MISSING_EVIDENCE_MARKERS)
    is_shared_state = any(m in low for m in _SHARED_STATE_MARKERS)
    if weakens_policy:
        return "blocked_policy"
    if missing_evidence:
        return "blocked_prerequisite"
    # High-risk surface that is NOT shared-state authorization + no review
    # support => missing-prerequisite block (cannot review before dispatch).
    if high_risk and not is_shared_state and prompt_review_support == "absent":
        return "blocked_prerequisite"
    # Shared-state mutation = genuine user authority (req. 16.g), even though
    # the surface is also high-risk.
    if is_shared_state and task_intent == "implement":
        return "pause_for_authorization"
    if task_intent == "decide" and execution_tier == "pause_for_authorization":
        return "recommendation_ready"
    if execution_tier == "pause_for_authorization":
        return "pause_for_authorization"
    return "partial_readonly_done"


def classify_decision_kind(
    rewritten: str, task_intent: str, execution_tier: str, risk: dict
) -> str:
    """Per-item authority classification for mixed work (goal req. 5).

    safe_readonly_next_step — read-only, auto-executes without pause (req. 6).
    agent_decidable — low-regret reversible implement at local tier.
    user_preference — needs the director (decide intent).
    shared_state_authorization — needs the director (shared config).
    blocked_by_missing_evidence / blocked_by_policy — never asked of the user;
    /go states the blocker and the next evidence step (req. 7).
    """
    low = rewritten.lower()
    high_risk = bool(risk.get("high_risk"))
    if any(m in low for m in _POLICY_WEAKEN_MARKERS):
        return "blocked_by_policy"
    if any(m in low for m in _MISSING_EVIDENCE_MARKERS):
        return "blocked_by_missing_evidence"
    if high_risk and any(m in low for m in _SHARED_STATE_MARKERS):
        return "shared_state_authorization"
    if task_intent == "decide":
        return "user_preference"
    if execution_tier == "direct_answer":
        return "safe_readonly_next_step"
    if task_intent in ("investigate", "validate"):
        return "safe_readonly_next_step"
    if execution_tier in ("local_surgical", "local_rigorous"):
        return "agent_decidable"
    return "user_preference"  # full_go / pause — defer to director


# --- Closure check (reproduce-first + confirm-closed) -------------------------

def _classify_closure_source(rewritten: str) -> str:
    """Pick the closure_check.source enum from prompt markers (req. 2).

    Order: hook_fp -> regression -> field_failure -> user_reported_symptom ->
    repro_command -> none. Hook-FP first so "regression of the FP hook" still
    anchors on the false positive.
    """
    low = rewritten.lower()
    if any(m in low for m in _HOOK_FP_MARKERS) or any(m in low for m in _STALE_WARNING_MARKERS):
        return "hook_fp"
    if any(m in low for m in _REGRESSION_MARKERS):
        return "regression"
    if any(m in low for m in _FIELD_FAILURE_MARKERS):
        return "field_failure"
    if any(m in low for m in _USER_REPORTED_MARKERS):
        return "user_reported_symptom"
    # Repro command: a quoted/inline shell command or pytest path present.
    if any(t in low for t in ("pytest ", "python -m", "repro ", "reproduce",
                              "to repro", "./", "repro command")):
        return "repro_command"
    return "none"


def classify_closure_check(rewritten: str, task_intent: str) -> dict:
    """Derive the default closure_check schema (goal reqs. 2, 3).

    required=true for bugfix/regression/hook-FP/stale-warning intents
    (including the implement children of a mixed prompt that name a defect).
    The worker fills command_or_procedure / expected_before / expected_after /
    evidence during the run; confirm_closed_passes() gates the completion claim.

    investigate/validate/decide tasks default to required=false (req. 8) — they
    emit evidence/advisory, not implementation-completion language.
    """
    low = rewritten.lower()
    is_bugfix = bool(
        task_intent in ("implement", "mixed")
        and any(m in low for m in _BUGFIX_MARKERS)
    )
    is_regression = any(m in low for m in _REGRESSION_MARKERS)
    is_hook_fp = any(m in low for m in _HOOK_FP_MARKERS)
    is_stale_warning = any(m in low for m in _STALE_WARNING_MARKERS)
    required = is_bugfix or is_regression or is_hook_fp or is_stale_warning
    source = _classify_closure_source(rewritten) if required else "none"
    cannot_reproduce = any(m in low for m in _CANNOT_REPRODUCE_MARKERS)
    high_risk_surface = any(m in low for m in _HIGH_RISK_MARKERS)
    return {
        "required": required,
        "source": source,
        "command_or_procedure": None,        # worker fills
        "expected_before": None,             # worker fills (failing repro / observed symptom)
        "expected_after": None,              # worker fills (symptom gone after fix)
        "evidence_path": None,               # path to pre-fix failing repro + post-fix passing evidence
        "evidence_summary": None,            # short summary when a path is impractical
        "unavailable_reason": None,          # set ONLY when direct closure is genuinely impossible
        "reproduce_first_required": required,            # req. 5: pre-fix failing repro expected
        "cannot_reproduce_artifact_allowed": cannot_reproduce,  # req. 5: cannot-reproduce is a valid artifact
        "registered_path_required": is_hook_fp or high_risk_surface,  # req. 7: use actual entry point
        "rule": (
            "A task may NOT claim fixed/complete unless confirm_closed_passes() OR the "
            "report explicitly explains why direct closure is impossible (unavailable_reason)."
        ),
    }


def derive_repro_policy(rewritten: str, task_intent: str, closure_check: dict) -> dict:
    """Reproduce-first policy for bugfix/regression tasks (goal req. 5).

    When required, the worker must produce either a pre-fix failing repro/test
    OR a cannot_reproduce / no_pre_fix_repro artifact with evidence. The artifact
    presence is what lets the report proceed; it does NOT by itself authorize a
    "Fixed" completion claim (that still needs confirm-closed).
    """
    required = bool(closure_check.get("required"))
    cannot_reproduce = bool(closure_check.get("cannot_reproduce_artifact_allowed"))
    if not required:
        return {
            "required": False,
            "artifact_required": "none",
            "rule": "reproduce-first not required for this task_intent.",
        }
    artifact = "cannot_reproduce_or_no_repro" if cannot_reproduce else "pre_fix_repro"
    return {
        "required": True,
        "artifact_required": artifact,
        "cannot_reproduce_allows_report_but_not_overclaim": cannot_reproduce,
        "rule": (
            "Produce a pre-fix failing repro/test. If that is not practical, produce a "
            "cannot_reproduce / no_pre_fix_repro artifact with evidence. A cannot-reproduce "
            "artifact lets the report proceed but does NOT authorize a Fixed claim over "
            "the original symptom."
        ),
    }


def confirm_closed_passes(closure_check: dict) -> bool:
    """Whether the report may claim fixed/complete (goal req. 4).

    Passes when closure_check is not required, OR when evidence
    (evidence_path/evidence_summary + expected_after) is present, OR when
    unavailable_reason is set (the report explicitly explains why direct closure
    is impossible — the task is reported, not claimed Fixed).
    """
    cc = closure_check or {}
    if not cc.get("required"):
        return True
    if cc.get("unavailable_reason"):
        return True  # report proceeds; SKILL rule forbids "Fixed" wording here
    has_evidence = bool(cc.get("evidence_path") or cc.get("evidence_summary"))
    has_after = bool(cc.get("expected_after"))
    return has_evidence and has_after


def classify_operational_discovery(rewritten: str, task_intent: str) -> dict:
    """Discovery-first + verification-ranking + lifecycle-hygiene policy.

    Operational questions (hooks/gates/worktrees/state/markers/cache/dispatch/
    sessions/exports/artifact lifecycle) get a discovery contract: identify
    writer/storage/reader/lifecycle/authority/stale-direction/observed-state
    BEFORE prescribing implementation, and rank verification paths by
    confidence-per-effort. Worktree and other /go-created resources carry a
    lifecycle/cleanup obligation; cleanup never auto-runs.
    """
    low = rewritten.lower()
    surfaces = sorted({label for markers, label in _OPERATIONAL_SURFACES
                       if any(_word_boundary_match(m, low) for m in markers)})
    required = bool(surfaces) and task_intent in ("investigate", "validate", "decide", "mixed", "implement")
    # Confidence uncertain ⇒ the worker must list ≥2 verification paths.
    confidence_uncertain = required and task_intent in ("investigate", "mixed", "decide")
    return {
        "required": required,
        "surfaces": surfaces,
        "identify_checklist": [
            "writer/creator", "storage/location", "reader/consumer",
            "lifecycle/cleanup path", "authority", "stale/failure direction",
            "observed current state (when cheap to inspect)",
        ] if required else [],
        "verification_paths": (
            [{"path": p, "confidence": c, "effort": e} for p, c, e in _VERIFICATION_RANKING]
            if confidence_uncertain else []
        ),
        "empirical_oracle_preferred": confidence_uncertain,
        "empirical_trace_gap": (
            "Empirical reproduction proves the symptom is gone for the tested path; "
            "it does NOT prove the writer/reader invariant holds in every branch or "
            "under concurrency. Code trace proves the invariant but not the runtime."
            if confidence_uncertain else ""
        ),
        "lifecycle_resources": [r for r in _LIFECYCLE_RESOURCES if r in low or any(r in s for s in surfaces)] if required else [],
        "worktree_prune_predicate": _WORKTREE_PRUNE_PREDICATE if "worktree" in surfaces else [],
        "cleanup_requires_approval": True,  # reqs. 6, 9: never auto-delete
        "rule": (
            "Before recommending implementation, identify the writer/storage/reader/"
            "lifecycle/authority/stale-direction, and (when cheap) inspect the actual "
            "current state. Rank ≥2 verification paths by confidence-per-effort; prefer "
            "empirical end-to-end reproduction against a real oracle. Cleanup of /go-"
            "created resources (worktrees, branches, state dirs, markers, cache, "
            "exports) is NEVER auto-run — report-only dry run, then director approval."
            if required else ""
        ),
    }


def build_plain_english_report(proposal: dict) -> dict:
    """Four-section plain-English report (goal reqs. 8, 10, 11).

    Section order is fixed: What I did -> What I recommend -> What is blocked ->
    What I need from you. Internal labels (pause_for_authorization,
    blocked_prerequisite, prompt_review_required, prompt_review_support=absent)
    may appear ONLY after these four sections. A "no mutation performed" claim
    requires ``git status --short`` (or equivalent) evidence (req. 14 / 16.l),
    surfaced via ``no_mutation_evidence_required``.
    """
    status = proposal.get("mixed_work_status", "partial_readonly_done")
    advisory = proposal.get("decision_advisory") or {}
    gate = proposal.get("report_gate") or {}
    intent = proposal.get("task_intent", "")
    recommendation = advisory.get(
        "recommendation", "Proceed at the derived execution tier."
    )

    what_i_did: list[str] = []
    if status == "partial_readonly_done" and intent in ("investigate", "validate", "mixed"):
        what_i_did.append(
            "Completed safe read-only narrowing — no code, docs, config, hooks, "
            "cache, env, or shared-state mutation."
        )
    elif intent in ("investigate", "validate"):
        what_i_did.append("Produced evidence/advisory only; no implementation-completion claim.")
    else:
        what_i_did.append("Ran preflight and derived the execution tier; no unauthorized mutation.")
    if intent == "mixed":
        what_i_did.append(
            "This is mixed work. I completed safe read-only checks, found blockers, "
            "and recommend the next low-risk step. I am not claiming blocked or "
            "decision-dependent work is done."
        )

    what_i_recommend: list[str] = [recommendation]
    if status == "blocked_prerequisite":
        what_i_recommend.append(
            "Next step is evidence-gathering, not approval: produce the missing "
            "prerequisite (corpus/baseline/transcript), then re-run."
        )
    elif status == "blocked_policy":
        what_i_recommend.append(
            "Policy block: /go will not weaken the gate. Propose the change as a "
            "separate, explicitly-authorized decision rather than asking to approve it inline."
        )
    # Discovery gate (discovery goal req. 6): if discovery is incomplete, the
    # recommendation is advisory — never presented as verified.
    discovery_incomplete = bool(gate.get("discovery_incomplete"))
    recommendation_is_advisory = discovery_incomplete
    if discovery_incomplete:
        what_i_recommend.insert(
            0,
            "Discovery incomplete — the recommendation below is advisory, NOT verified: "
            "discovery_evidence must list ≥1 finding with provenance "
            "(verified|inference|assumption) before it can be presented as verified."
        )

    what_is_blocked: list[str] = []
    if status == "blocked_prerequisite":
        what_is_blocked.append("Missing evidence/prerequisite — not asked of you (req. 7).")
    if status == "blocked_policy":
        what_is_blocked.append("Policy-blocked (gate weakening) — not asked of you (req. 7).")
    if gate.get("must_defer_unauthorized_children"):
        what_is_blocked.append(
            "Unauthorized / deferred children of the mixed request — not bundled into completion."
        )
    if discovery_incomplete:
        what_is_blocked.append(
            "discovery_incomplete — recommendation demoted to advisory; cannot be presented as verified."
        )

    if status == "pause_for_authorization":
        need = advisory.get(
            "exact_authorization_needed",
            "Director authorization required to mutate shared state.",
        )
    elif status == "recommendation_ready":
        need = advisory.get(
            "exact_authorization_needed",
            "Director decision required; advisory is ready.",
        )
    elif status in ("blocked_prerequisite", "blocked_policy"):
        need = "Nothing right now — unblock the prerequisite above; no approval is requested."
    else:
        need = "Nothing right now — proceed at the recommended tier."

    report: dict[str, object] = {
        "section_order": [
            "what_i_did",
            "what_i_recommend",
            "what_is_blocked",
            "what_i_need_from_you",
        ],
        "what_i_did": what_i_did,
        "what_i_recommend": what_i_recommend,
        "what_is_blocked": what_is_blocked,
        "what_i_need_from_you": [need],
        "labels_after_plain_english": True,
        "no_mutation_evidence_required": True,
        "discovery_incomplete": discovery_incomplete,
        "recommendation_is_advisory": recommendation_is_advisory,
    }

    # Closure report (reqs. 4, 6, 10): scaffolds the five required content
    # fields when closure_check is required. The worker fills the values during
    # the run; until then confirm_closed_passes is False and the report may NOT
    # use fixed/completed wording.
    closure = proposal.get("closure_check") or {}
    if closure.get("required"):
        report["closure_report"] = {
            "original_symptom": proposal.get("originalPrompt", ""),
            "reproduce_first_evidence": None,     # pre-fix failing repro OR why unavailable
            "reproduce_first_unavailable_reason": None,
            "verification_tests": None,           # the unit/integration tests actually run
            "confirm_closed_evidence": None,      # post-fix re-check of the ORIGINAL symptom
            "confirm_closed_via_registered_path": closure.get("registered_path_required", False),
            "remaining_risk": None,               # residual risk after the fix
            "may_claim_fixed": confirm_closed_passes(closure),
        }

    # Discovery evidence (reqs. 7, 8): scaffolds writer/storage/reader/lifecycle
    # findings BEFORE recommendations when the question is operational. Each
    # finding carries a provenance tier so verified fact, inference, and
    # assumption are visibly distinct — not flattened into one claim.
    disc = proposal.get("operational_discovery") or {}
    if disc.get("required"):
        report["discovery_evidence"] = {
            "section_order_position": "before what_i_recommend",
            "surfaces": disc.get("surfaces", []),
            "findings": [],  # worker fills: {item, value, provenance ∈ verified|inference|assumption, source}
            "identify_checklist": disc.get("identify_checklist", []),
            "verification_paths": disc.get("verification_paths", []),
            "empirical_oracle_preferred": disc.get("empirical_oracle_preferred", False),
            "empirical_trace_gap": disc.get("empirical_trace_gap", ""),
            "provenance_tiers": ["verified", "inference", "assumption"],
            "lifecycle_resources": disc.get("lifecycle_resources", []),
            "worktree_prune_predicate": disc.get("worktree_prune_predicate", []),
            "cleanup_requires_approval": disc.get("cleanup_requires_approval", True),
        }

    return report


def assert_fresh(proposal, run_id) -> None:
    """Artifact freshness contract (goal req. 9).

    A proposal authorizes dispatch / completion only when its runid matches the
    current run. Stale/mismatched proposals raise; callers regenerate.
    """
    prop_run = proposal.get("runid") or proposal.get("run_id")
    if prop_run != run_id:
        raise ValueError(
            f"stale proposal: runid={prop_run!r} != current run_id={run_id!r}; "
            "regenerate before dispatch or completion."
        )


def prompt_hash(rewritten: str) -> str:
    """Stable short hash of the rewritten prompt for advisory freshness."""
    import hashlib
    return hashlib.sha256(rewritten.encode("utf-8")).hexdigest()[:16]


def _extract_worker_scope(rewritten: str) -> list[str]:
    """Concrete path prefixes the worker may mutate, derived from the prompt.

    Used by the PreToolUse gate to path-bound worker edits. Returns [] when no
    concrete paths are resolvable — the gate then enforces tool-type
    restrictions only (advisory=read-only; local_fast=no-shared-state), not
    path bounds. We never claim path-bound enforcement we can't deliver.
    """
    seen: list[str] = []
    for m in _PATH_RE.finditer(rewritten):
        p = m.group(0).replace("\\", "/").rstrip(".,;:")
        # Keep the longest prefix that looks like a real path (drop bare exts).
        if p and p not in seen:
            seen.append(p)
    return seen[:8]  # bounded; a worker patch touching >8 paths is not "bounded"


def classify_layer_placement(rewritten: str) -> dict:
    """Layer-placement guard for hook/gate edits (reqs. 2-5).

    Detects when a prompt proposes broad behaviors (pattern detection,
    dry-run analysis, cross-session state, promotion policy) targeting a
    Stop/PreToolUse/PostToolUse hook — the wrong architectural layer.
    Stop hooks should narrowly verify session-bound artifacts/evidence;
    preflight/report-gate owns broad analysis and promotion.
    """
    lower = rewritten.lower()
    hook_hits = [m for m in _LAYER_HOOK_FILE_MARKERS if m in lower]
    broad_hits = [m for m in _LAYER_BROAD_BEHAVIOR_MARKERS if m in lower]
    narrow_hits = [m for m in _LAYER_NARROW_VERBS if _word_boundary_match(m, lower)]

    if not hook_hits:
        return {
            "required": False,
            "verdict": "not_applicable",
            "reason": "no hook/gate file mentioned",
        }

    if broad_hits and hook_hits:
        return {
            "required": True,
            "verdict": "wrong_layer",
            "proposed_behavior": broad_hits,
            "chosen_layer": "preflight/report-gate",
            "rejected_layers": ["stop_hook", "pretooluse_hook", "posttooluse_hook"],
            "reason": (
                "Broad behaviors (pattern detection, dry-run analysis, "
                "cross-session state, promotion policy) belong in preflight/"
                "report-gate, NOT in Stop/PreToolUse/PostToolUse hooks. "
                "Stop hooks verify narrow session-bound evidence only. "
                "Implementing broad logic in a Stop hook creates cross-session "
                "side effects, coupling the hook to non-session-scoped state, "
                "and makes the hook untestable in isolation."
            ),
            "must_not_happen_in_layer": [
                "cross-session state writes",
                "pattern detection or pattern_candidate emission",
                "dry-run refactor analysis",
                "promotion policy or recommendation generation",
                "heuristic classification beyond evidence-level mapping",
            ],
            "data_path": {
                "writer": "preflight_propose.classify_layer_placement",
                "storage": "task-proposal_{run_id}.json layer_placement",
                "reader": "/go orchestrator + report gate",
                "authority": "this function",
                "freshness": "same as proposal (run_id bound)",
                "failure_direction": "wrong_layer -> pause_for_authorization",
            },
            "hook_markers": hook_hits,
        }

    return {
        "required": True,
        "verdict": "allowed",
        "proposed_behavior": narrow_hits or ["evidence/artifact verification"],
        "chosen_layer": "stop_hook (narrow verification)",
        "rejected_layers": [],
        "reason": (
            "Narrow session-bound evidence/artifact verification is the correct "
            "layer for Stop hooks. No broad pattern detection, dry-run "
            "analysis, or cross-session state detected."
        ),
        "must_not_happen_in_layer": _LAYER_BROAD_BEHAVIOR_MARKERS,
        "data_path": {
            "writer": "preflight_propose.classify_layer_placement",
            "storage": "task-proposal_{run_id}.json layer_placement",
            "reader": "/go orchestrator + report gate",
            "authority": "this function",
            "freshness": "same as proposal (run_id bound)",
            "failure_direction": "allowed -> proceed",
        },
        "hook_markers": hook_hits,
    }


# --- Refactor-escalation detection ---------------------------------------------
_REFACTOR_ESCALATION_MARKERS: tuple[str, ...] = (
    "dead path", "dead code", "dead producer", "dead consumer",
    "inert code", "inert gate", "inert hook",
    "duplicated responsibility", "duplicate responsibility",
    "wrong layer", "wrong-layer",
    "repeated patching", "patching around",
    "state ownership", "identity ambiguity", "lifecycle ambiguity",
    "cross-file change", "broad refactor",
    "excessive setup", "design complexity",
    "structural issue", "fragile fix",
)
_REFACTOR_SCOPE_MAP = {
    "dead path": "module", "dead code": "module",
    "dead producer": "workflow", "dead consumer": "workflow",
    "inert code": "module", "inert gate": "plugin",
    "duplicated responsibility": "module",
    "wrong layer": "architecture",
    "repeated patching": "module",
    "state ownership": "architecture",
    "cross-file change": "plugin",
    "broad refactor": "architecture",
}


def classify_refactor_escalation(
    rewritten: str, task_intent: str, execution_tier: str,
    discovery_evidence: dict | None = None,
) -> dict:
    """Detect when discovery finds structural issues that warrant /refactor.

    Does NOT expand the current task. Produces a recommendation:
    continue_narrow_fix (safe to finish), pause_for_refactor (unsafe without),
    or finish_then_refactor (complete with risks noted).

    Merges two signal sources (req. 4):
    1. Prompt-based: substring markers in the rewritten goal text.
    2. Discovery-evidence-based: structural_issues in discovery_evidence
       findings, each carrying provenance (verified > inference > assumption).
    Discovery evidence may raise severity but never erases prompt evidence.
    """
    lower = rewritten.lower()
    prompt_hits = [m for m in _REFACTOR_ESCALATION_MARKERS if m in lower]

    # --- Discovery-evidence structural issues (reqs. 2, 3) ---
    discovery_issues: list[dict] = []
    de = discovery_evidence or {}
    for f in (de.get("findings") or []):
        si = (f or {}).get("structural_issues") or []
        prov = (f or {}).get("provenance", "inference")
        for issue in si:
            discovery_issues.append({
                "issue": issue,
                "provenance": prov if prov in _PROVENANCE_TIERS else "inference",
                "source": (f or {}).get("source", "runtime discovery"),
            })

    all_hits = list(prompt_hits)
    discovery_trigger_labels = []
    for di in discovery_issues:
        # Map structural_issue enum to prompt-marker equivalent for scope
        label = di["issue"].replace("_", " ")
        discovery_trigger_labels.append(label)
        if label not in all_hits:
            all_hits.append(label)

    if not all_hits:
        return {
            "required": False,
            "trigger_evidence": [],
            "current_task_scope": "narrow",
            "refactor_scope": "none",
            "recommendation": "continue_narrow_fix",
            "suggested_command": None,
            "reason": "no structural-issue markers detected",
            "risk_if_ignored": None,
            "discovery_issues": [],
            "prompt_evidence": [],
        }

    scope_hits = [_REFACTOR_SCOPE_MAP.get(h, "module") for h in all_hits]
    refactor_scope = "architecture" if "architecture" in scope_hits else (
        "plugin" if "plugin" in scope_hits else (
            "workflow" if "workflow" in scope_hits else "module"
        )
    )

    # --- Provenance-weighted confidence (req. 3) ---
    has_verified = any(di["provenance"] == "verified" for di in discovery_issues)
    has_inference = any(di["provenance"] == "inference" for di in discovery_issues)
    # Assumption-only does not hard-pause by itself (req. 10 test case).
    assumption_only = bool(discovery_issues) and not has_verified and not has_inference

    # --- Unsafe-fix indicators (req. 7) ---
    unsafe_indicators = {
        "wrong_layer_ownership", "dead_producer_consumer",
        "broad_cross_file_change_needed", "excessive_test_setup_due_to_design_complexity",
    }
    found_unsafe = any(di["issue"] in unsafe_indicators for di in discovery_issues)

    # --- Recommendation logic ---
    task_scope = "narrow"
    if execution_tier in ("full_go",):
        task_scope = "medium"
    if execution_tier in ("pause_for_authorization",):
        task_scope = "broad"

    if task_intent in ("decide", "mixed") and execution_tier == "pause_for_authorization":
        recommendation = "finish_then_refactor"
    elif found_unsafe and (has_verified or has_inference):
        # Verified/inference unsafe indicator -> pause (req. 5)
        recommendation = "pause_for_refactor"
    elif refactor_scope == "architecture" and not assumption_only:
        recommendation = "pause_for_refactor"
    elif refactor_scope in ("plugin", "workflow"):
        recommendation = "finish_then_refactor"
    elif assumption_only:
        # Assumption-only does not hard-pause (req. 10)
        recommendation = "finish_then_refactor"
    else:
        recommendation = "continue_narrow_fix"

    # Merge evidence: prompt evidence is never erased (req. 4)
    trigger_evidence = prompt_hits + discovery_trigger_labels

    return {
        "required": True,
        "trigger_evidence": trigger_evidence,
        "prompt_evidence": prompt_hits,
        "discovery_issues": discovery_issues,
        "current_task_scope": task_scope,
        "refactor_scope": refactor_scope,
        "recommendation": recommendation,
        "suggested_command": f"/refactor <{refactor_scope}>",
        "reason": (
            f"Found {len(trigger_evidence)} structural signal(s): "
            f"{', '.join(trigger_evidence[:3])}. "
            f"Prompt-based: {len(prompt_hits)}, discovery-based: {len(discovery_issues)}. "
            f"Scope: {task_scope} -> {refactor_scope}. "
            f"Recommendation: {recommendation}."
        ),
        "risk_if_ignored": (
            "The narrow fix may be fragile or incomplete without addressing "
            "the structural issue. Future changes to the same area will "
            "encounter the same difficulty. Tests may require excessive setup."
            if recommendation != "continue_narrow_fix" else
            "Low risk — the structural marker is localized."
        ),
    }


# --- Pattern candidate detection (preflight layer — NOT in Stop hooks) ---------
_KNOWN_FAILURE_SHAPES_PREFLIGHT: dict[str, dict] = {
    "cache_not_verified": {"missed_evidence": "cache_or_runtime_verified", "fix_type": "add cache rebuild step"},
    "advisory_not_enforced": {"missed_evidence": "real_entrypoint_smoked", "fix_type": "add enforcement gate"},
    "completion_without_packet": {"missed_evidence": "field_confirmed_against_original_symptom", "fix_type": "add verification packet"},
    "missing_backend": {"missed_evidence": "source_inspected", "fix_type": "add backend existence check"},
    "unit_test_only": {"missed_evidence": "real_entrypoint_smoked", "fix_type": "add entry-point smoke"},
}
_PATTERN_HIGH_RISK_SHAPES = frozenset({"cache_not_verified", "missing_backend"})


def classify_pattern_candidates(
    proposal: dict,
) -> list[dict]:
    """Detect pattern candidates from the proposal's evidence levels.

    Report-local only — no cross-session state, no persistence, no append-only
    files. Pattern candidates are emitted in the report and consumed by the
    receiving LLM or human. Recurrence counting is not done in this function.

    Returns a list of pattern_candidate dicts with promotion recommendations.
    """
    re_fields = proposal.get("refactor_escalation") or {}
    trigger_evidence = re_fields.get("trigger_evidence") or []
    candidates = []
    for shape, meta in _KNOWN_FAILURE_SHAPES_PREFLIGHT.items():
        marker = shape.replace("_", " ")
        if marker in " ".join(trigger_evidence).lower() or shape in str(trigger_evidence).lower():
            candidates.append({
                "failure_shape": shape,
                "boundary": "preflight/report-gate",
                "missed_evidence": meta["missed_evidence"],
                "detected_by": "preflight_propose.classify_pattern_candidates",
                "fix_type": meta["fix_type"],
                "recurrence_count": 1,
                "promotion_recommendation": (
                    "hook" if shape in _PATTERN_HIGH_RISK_SHAPES else "note"
                ),
            })
    return candidates


# --- Dry-run refactor analysis trigger (preflight layer) ----------------------
_DRY_RUN_TRIGGER_MARKERS: tuple[str, ...] = (
    "routing", "dispatch", "hook", "gate", "plugin", "cache", "state",
    "session", "identity", "artifact", "lifecycle", "consolidation",
    "migration", "model_routing", "refactor", "router", "settings.json",
)


def classify_dry_run_trigger(rewritten: str) -> dict:
    """Detect whether the task warrants dry-run refactor analysis.

    No-mutation by design. Returns a trigger dict with the checklist of
    analysis items the worker should perform.
    """
    lower = rewritten.lower()
    hits = [m for m in _DRY_RUN_TRIGGER_MARKERS if m in lower]
    if not hits:
        return {"triggered": False, "reason": "no dry-run markers detected"}
    return {
        "triggered": True,
        "trigger_markers": hits,
        "mode": "no_mutation",
        "analysis_checklist": [
            "architecture map: list modules/files touched and their consumers",
            "writer/storage/reader paths: identify each data-flow participant",
            "dead-code/dead-branch check: grep for unreferenced definitions",
            "inert-code check: find code that runs but has no observable effect",
            "duplicated-responsibility check: find overlapping logic across modules",
            "lifecycle/race/state risks: identify TOCTOU, stale-state, concurrency hazards",
            "real-entrypoint test gaps: identify paths not covered by registered-path smoke",
            "simplification options: delete | wire | consolidate | document | defer",
        ],
        "reason": (
            f"Task touches {len(hits)} dry-run surface(s): "
            f"{', '.join(hits[:3])}. Dry-run analysis is no-mutation by default."
        ),
    }


def derive_delegation_policy(rewritten, task_intent, execution_tier, risk, dispatch) -> dict:
    """Lightweight role/authority/freshness policy for /go delegation.

    Assigns bounded advisory/worker roles without a new multi-agent engine.
    Prefers claude_subagent over pi_ccr when only context protection is needed
    (goal req. 3). Mutation authority per role is fixed; final completion
    authority stays with /go evidence gates (goal req. 4).

    worker_scope (concrete path prefixes) lets the PreToolUse gate path-bound
    worker edits; worker_enforcement reports whether such bounds are available
    so callers never over-claim enforcement granularity.
    """
    low = rewritten.lower()
    high_risk = bool(risk.get("high_risk"))
    needs_adversarial = task_intent == "decide" or any(m in low for m in _ADVERSARIAL_MARKERS)
    needs_model_diversity = any(m in low for m in _MODEL_DIVERSITY_MARKERS)
    context_protection_only = (
        not high_risk and not needs_model_diversity
        and execution_tier in ("local_rigorous", "full_go")
    )

    # Worker role by execution_tier. pi_ccr only when model-diversity / failover
    # / isolated execution is explicitly needed (goal req. 4).
    if execution_tier == "direct_answer":
        worker = "claude_main"
    elif execution_tier == "local_surgical":
        worker = "local_fast" if dispatch == "local" else "claude_main"
    elif execution_tier == "local_rigorous":
        worker = "claude_subagent"
    elif execution_tier == "full_go":
        worker = "pi_ccr" if needs_model_diversity else "claude_subagent"
    else:  # pause_for_authorization
        worker = None  # no worker until director authorizes

    # Worker scope: path-bound when concrete paths are resolvable, else the gate
    # falls back to tool-type enforcement. pi_ccr's scope is the worktree (set
    # at dispatch by harness.py, not here).
    worker_scope = _extract_worker_scope(rewritten) if worker in (
        "claude_subagent", "local_fast") else []
    worker_enforcement = (
        "worktree" if worker == "pi_ccr"
        else ("path-bound" if worker_scope else "type-bound")
    )

    # Advisory reviewer selection.
    if needs_adversarial:
        advisory = "agy"               # outside-model adversarial reviewer
        advisory_fallback = "claude_subagent"
    elif needs_model_diversity:
        advisory = "pi_ccr"
        advisory_fallback = "claude_subagent"
    else:
        # context-protection-only OR low-risk: claude_subagent preferred over pi_ccr.
        advisory = "claude_subagent"
        advisory_fallback = "local_fast"

    required_review = high_risk  # high-risk hook/gate/state/identity/dispatch/cache/plugin
    blocking = bool(required_review and execution_tier == "pause_for_authorization")

    return {
        "roles": {
            "claude_main": "orchestrator, integrator, final reporter",
            "worker": worker,
            "advisory_reviewer": advisory,
            "advisory_fallback": advisory_fallback,
        },
        "worker": worker,
        "advisory_reviewer": advisory,
        "advisory_fallback": advisory_fallback,
        "prefer_claude_subagent_over_pi_ccr": context_protection_only,
        "mutation_authority": dict(_MUTATION_AUTHORITY),
        "worker_scope": worker_scope,
        "worker_enforcement": worker_enforcement,
        "enforcement": {
            "mutating_tools": list(_MUTATING_TOOLS),
            "shared_state_tool_markers": list(_SHARED_STATE_TOOL_MARKERS),
            "boundary": (
                "PreToolUse gate (Claude tool calls) + pi harness worktree assertion. "
                "Advisory roles: mutating tools denied. Workers: edits path-bounded "
                "when worker_scope resolvable, else tool-type only. pi_ccr: worktree only."
            ),
        },
        "enforcement_status": {
            "verified": [
                "writer: derive_delegation_policy emits mutation_authority + worker_scope",
                "marker/state: .delegation-{advisory,worker}_{run_id} written by orchestrate.py",
                "reader/gate: go_delegation_enforce_PreToolUse.py wired via SKILL.md frontmatter",
                "main-session PreToolUse: gate fires on Claude tool calls during /go",
                "pi dispatch path: harness.py worktree-branch assertion + .blocked_{run_id}",
            ],
            "advisory_or_unverified": [
                "Task-tool subagent propagation of PreToolUse: UNVERIFIED (research parked; "
                "mitigated by capability-layer tools: restriction, which IS hard enforcement)",
                "agy internal subprocess mutations: outside Claude's tool-call boundary "
                "(advisory at /go layer; agy runs in its own worktree)",
            ],
            "role_enforcement": {
                "claude_main": "verified (main-session PreToolUse)",
                "claude_subagent": "PreToolUse propagation unverified; use tools: restriction for hard enforcement",
                "local_fast": "PreToolUse propagation unverified; use tools: restriction for hard enforcement",
                "pi_ccr": "verified (harness.py worktree-branch assertion)",
                "agy": "advisory (own subprocess worktree, outside tool-call boundary)",
            },
            "declared_vs_verified_note": (
                "mutation_authority DECLARES per-role scope; runtime enforcement is VERIFIED "
                "only for paths in 'verified'. Do not claim all role mutation authority is enforced."
            ),
        },
        "final_authority": "/go evidence gates (not any worker)",
        "required_review": required_review,
        "blocking": blocking,
        "advisory_is_evidence_not_authority": True,
        "freshness": {
            "advisory_requires": ["run_id", "prompt_hash"],
            "diff_review_requires": ["run_id", "prompt_hash", "diff_hash"],
            "prompt_hash": prompt_hash(rewritten),
            "diff_hash": None,  # unknown at preflight; required when a diff-review artifact is produced
        },
        "rule": (
            "claude_subagent is the default bounded reviewer/worker (context protection). "
            "agy for adversarial/decision/ROI/design. pi_ccr only for model-diversity/failover/"
            "isolated full_go work. Advisory reviewers cannot mutate; workers mutate only in "
            "their tier scope. Final completion authority stays with /go evidence gates."
        ),
    }


def assert_advisory_fresh(artifact, run_id, expected_prompt_hash, diff_hash=None) -> None:
    """Advisory artifact freshness contract (goal req. 6).

    Advisory artifacts must match run_id AND prompt_hash. Diff reviews must
    also match diff_hash. Stale/mismatched artifacts raise; callers regenerate.
    """
    if artifact.get("run_id") != run_id:
        raise ValueError(
            f"stale advisory: run_id={artifact.get('run_id')!r} != {run_id!r}"
        )
    if artifact.get("prompt_hash") != expected_prompt_hash:
        raise ValueError(
            f"stale advisory: prompt_hash={artifact.get('prompt_hash')!r} != "
            f"{expected_prompt_hash!r} (prompt changed since review)"
        )
    if diff_hash is not None and artifact.get("diff_hash") not in (None, diff_hash):
        raise ValueError(
            f"stale advisory: diff_hash={artifact.get('diff_hash')!r} != {diff_hash!r}"
        )


def generate_proposal(
    prompt: str,
    run_id: str,
    terminal_id: str,
) -> dict[str, Any]:
    """Build the proposal dict. Matches the spec'd JSON shape exactly."""
    rewritten = rewrite_goal(prompt)
    dispatch, local_eligible, requires_approval = classify_dispatch(rewritten)
    task_intent = classify_intent(rewritten)
    risk = detect_risk_signals(rewritten)
    capability_claims_raw = detect_capability_claims(rewritten)
    execution_tier = derive_execution_tier(
        task_intent, dispatch, local_eligible, requires_approval, risk
    )
    closure_check = classify_closure_check(rewritten, task_intent)
    repro_policy = derive_repro_policy(rewritten, task_intent, closure_check)
    operational_discovery = classify_operational_discovery(rewritten, task_intent)
    report_gate = derive_report_gate(
        task_intent, execution_tier, closure_check,
        operational_discovery=operational_discovery,
        discovery_evidence=None,  # scaffold — worker fills findings during the run
        capability_claims=capability_claims_raw,
    )
    decision_advisory = build_decision_advisory(rewritten, task_intent, execution_tier)
    delegation_policy = derive_delegation_policy(
        rewritten, task_intent, execution_tier, risk, dispatch
    )
    layer_placement = classify_layer_placement(rewritten)
    refactor_escalation = classify_refactor_escalation(
        rewritten, task_intent, execution_tier
    )
    dry_run_trigger = classify_dry_run_trigger(rewritten)
    # Wrong-layer escalation: if pattern detection/dry-run is proposed for a
    # Stop hook, force pause_for_authorization before any implementation.
    _layer_note = None
    if layer_placement.get("verdict") == "wrong_layer":
        execution_tier = "pause_for_authorization"
        mixed_work_status_override = "blocked_policy"
        _layer_note = (
            f"LAYER_PLACEMENT wrong_layer: {layer_placement['reason']} "
            "Broad behaviors must move to preflight/report-gate. "
            "Do NOT implement in the Stop hook."
        )
    else:
        mixed_work_status_override = None
    mixed_work_status = classify_mixed_work_status(
        rewritten, task_intent, execution_tier, risk, _PROMPT_REVIEW_SUPPORT
    )
    if mixed_work_status_override:
        mixed_work_status = mixed_work_status_override
    decision_kind = classify_decision_kind(rewritten, task_intent, execution_tier, risk)
    prompt_review_required = bool(risk["prompt_review_required"])
    high_risk = bool(risk.get("high_risk"))
    model_affinity = classify_model_affinity(
        task_intent, execution_tier, high_risk, len(prompt), prompt
    )
    notes = [
        "Deterministic heuristic (no LLM). dispatch="
        f"{dispatch} localEligible={local_eligible}",
        f"task_intent={task_intent} execution_tier={execution_tier} "
        f"prompt_review_required={prompt_review_required}",
        f"mixed_work_status={mixed_work_status} decision_kind={decision_kind}",
        f"model_affinity={model_affinity} (advisory; PI_DEFAULT_FLIP=advisory — "
        "route per existing rules, do not auto-flip dispatch)",
    ]
    if _layer_note:
        notes.append(_layer_note)
    if execution_tier == "pause_for_authorization":
        notes.append(
            "PAUSE: emit decision_advisory before any dispatch; do not proceed "
            "without director authorization."
        )
    if mixed_work_status in ("blocked_prerequisite", "blocked_policy"):
        notes.append(
            f"BLOCKED ({mixed_work_status}): do NOT ask the user to approve. "
            "State the blocker and the next evidence-gathering step (req. 7)."
        )
    if closure_check["required"]:
        notes.append(
            f"CLOSURE_CHECK required (source={closure_check['source']}): "
            "reproduce-first + confirm-closed. A passing unit test alone does NOT "
            "authorize Fixed/Done; produce pre-fix repro + post-fix symptom-gone "
            "evidence, or an explicit cannot_reproduce/unavailable_reason artifact."
        )
    if operational_discovery["required"]:
        notes.append(
            f"DISCOVERY_FIRST required (surfaces={operational_discovery['surfaces']}): "
            "identify writer/storage/reader/lifecycle/authority/stale-direction + "
            "observed state before prescribing. Rank ≥2 verification paths by "
            "confidence-per-effort. Cleanup is report-only + approval-gated."
        )
    if capability_claims_raw:
        cap_claims = capability_claims_raw[0].get("claims", [])
        cap_triggers = capability_claims_raw[0].get("trigger_terms", [])
        notes.append(
            f"CAPABILITY_CLAIM_AUDIT required (triggers={cap_triggers}): "
            f"{len(cap_claims)} claim(s) detected. Visible-surface check alone is "
            "insufficient — must verify backend runner/module/function paths exist "
            "before claiming 'shipped'/'absorbed'/'production'. Reports must "
            "distinguish: visible consolidation complete | routing complete | "
            "backend implementation complete | pending capability intentionally deferred."
        )
    proposal = {
        "runid": run_id,
        "run_id": run_id,
        "terminalid": terminal_id,
        "source": "cli-preflight",
        "originalPrompt": prompt,
        "rewrittenGoal": rewritten,
        "suggestedDispatch": dispatch,
        "localEligible": local_eligible,
        "requiresApproval": requires_approval,
        "task_intent": task_intent,
        "execution_tier": execution_tier,
        "risk_signals": risk,
        "model_affinity": model_affinity,
        "prompt_review_required": prompt_review_required,
        "prompt_review_support": _PROMPT_REVIEW_SUPPORT,
        "report_gate": report_gate,
        "decision_advisory": decision_advisory,
        "delegation_policy": delegation_policy,
        "mixed_work_status": mixed_work_status,
        "decision_kind": decision_kind,
        "closure_check": closure_check,
        "repro_policy": repro_policy,
        "operational_discovery": operational_discovery,
        "layer_placement": layer_placement,
        "refactor_escalation": refactor_escalation,
        "dry_run_trigger": dry_run_trigger,
        "pattern_candidates": [],  # scaffold; filled at report time from discovery + evidence
        "capability_claims": capability_claims_raw[0] if capability_claims_raw else None,
        "verificationSuggestions": verification_suggestions(rewritten),
        "verificationPolicy": _verification_policy_key(rewritten),
        "freshness": {
            "run_id": run_id,
            "must_match_run_id": True,
            "prompt_hash": delegation_policy["freshness"]["prompt_hash"],
        },
        "notes": notes,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    proposal["plain_english_report"] = build_plain_english_report(proposal)
    return proposal


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def rebuild_with_discovery_evidence(proposal: dict, discovery_evidence: dict) -> dict:
    """Rebuild proposal's refactor_escalation + pattern_candidates using
    runtime discovery findings. Called after the worker fills discovery_evidence.

    This is the ONLY entry point for runtime discovery merge. Preflight emits
    discovery_evidence=None; this function fills it post-discovery.
    """
    rewritten = proposal.get("rewrittenGoal", "")
    task_intent = proposal.get("task_intent", "implement")
    execution_tier = proposal.get("execution_tier", "local_surgical")
    merged_refactor = classify_refactor_escalation(
        rewritten, task_intent, execution_tier,
        discovery_evidence=discovery_evidence,
    )
    # Preserve prompt-based fields that discovery evidence may raise
    # but never erase (merge requirement from goal req. 4).
    old_re = proposal.get("refactor_escalation", {})
    if old_re.get("required") and not merged_refactor.get("required"):
        merged_refactor["required"] = True
    if old_re.get("trigger_evidence"):
        existing = set(merged_refactor.get("trigger_evidence", []))
        for e in old_re["trigger_evidence"]:
            if e not in existing:
                merged_refactor["trigger_evidence"].append(e)
                existing.add(e)
    proposal["refactor_escalation"] = merged_refactor
    proposal["pattern_candidates"] = classify_pattern_candidates(proposal)
    return proposal



def apply_discovery_evidence_merge(state_dir: Path, run_id: str) -> bool:
    """Merge worker-filled discovery_evidence into the proposal.

    Reads task-proposal_{run_id}.json, looks for discovery_evidence in
    discovery-evidence_{run_id}.json (standard) or claude-task-result_{run_id}.json
    (worker result), calls rebuild_with_discovery_evidence if valid, rebuilds the
    plain_english_report, and writes the updated proposal back.

    Returns True on success or soft-skip (no discovery found).
    Returns False on hard failure (proposal unreadable, write failed).
    Does NOT block the pipeline -- callers should continue even on False.
    """
    proposal_file = state_dir / f"task-proposal_{run_id}.json"
    if not proposal_file.exists():
        return True  # no proposal to merge; preflight-only mode
    try:
        proposal = json.loads(proposal_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False  # proposal unreadable -- don't mask the error

    # Try standard discovery file first, then worker result file as fallback.
    discovery_evidence = None
    for candidate in (
        state_dir / f"discovery-evidence_{run_id}.json",
        state_dir / f"claude-task-result_{run_id}.json",
    ):
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            # Standard discovery file: {findings: [...]}. Worker result may wrap: {discovery_evidence: {findings: [...]}}.
            findings = data.get("findings") or (data.get("discovery_evidence") or data.get("discoveryEvidence", {})).get("findings")
            if findings:
                discovery_evidence = {"findings": findings}
                break
        except (OSError, ValueError):
            continue

    if not discovery_evidence:
        return True  # no discovery findings; preflight-only result is correct

    try:
        proposal = rebuild_with_discovery_evidence(proposal, discovery_evidence)
        proposal["plain_english_report"] = build_plain_english_report(proposal)
        _atomic_write_json(proposal_file, proposal)
        return True
    except Exception:
        return False  # rebuild failed -- keep preflight-only result


# Canonical structural-issue enum. The writer filters worker-reported issues to
# this set so the merge reader never sees an unknown shape. Keep in sync with
# unsafe_indicators at L2074 and _KNOWN_FAILURE_SHAPES_PREFLIGHT.
_STRUCTURAL_ISSUES_CANONICAL = frozenset({
    "dead_producer_consumer", "inert_code", "duplicated_responsibility",
    "wrong_layer_ownership", "repeated_patching", "state_identity_lifecycle_ambiguity",
    "broad_cross_file_change_needed", "excessive_test_setup_due_to_design_complexity",
})


def write_discovery_evidence(state_dir: Path, run_id: str, findings: list) -> object:
    """Write worker-discovered structural findings to the standard discovery file.

    Called by the worker path (claude subagent via SKILL.md, or pi harness) after
    the worker observes code-level structural issues. Validates schema and drops
    malformed entries rather than failing. Verified findings must carry concrete
    evidence (file/path/grep/test citation); inference/assumption may omit it.

    Returns the written Path on success, None if no valid findings (soft-fail).
    Does NOT raise on bad input -- the reader is fail-soft, so the writer is too.
    """
    if not findings:
        return None
    valid = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        provenance = f.get("provenance")
        source = f.get("source")
        summary = f.get("summary") or f.get("evidence")
        if provenance not in _PROVENANCE_TIERS or not source or not summary:
            continue
        if provenance == "verified" and not f.get("evidence"):
            continue
        si = [s for s in (f.get("structural_issues") or [])
               if s in _STRUCTURAL_ISSUES_CANONICAL]
        valid.append({
            "source": source,
            "provenance": provenance,
            "summary": summary,
            "evidence": f.get("evidence", ""),
            "structural_issues": si,
        })
    if not valid:
        return None
    out = state_dir / f"discovery-evidence_{run_id}.json"
    _atomic_write_json(out, {"findings": valid, "run_id": run_id})
    return out



def emit_discovery_evidence_telemetry(state_dir: Path, run_id: str) -> dict:
    """Run-local, non-blocking telemetry for discovery_evidence worker compliance.

    Reports whether the worker wrote discovery evidence, with the artifact path,
    finding counts, and source. This is the observability hook that lets us
    measure whether real Claude/pi workers actually emit the contract -- not a
    gate. Returns a dict that the common tail can log or append to the proposal.

    Failure direction: absent discovery_evidence is non-blocking. This function
    must NEVER raise; it must NEVER block; it must NEVER write a pattern DB.
    Side effects: optionally emits a single JSONL record to state_dir/
    telemetry-discovery-evidence_{run_id}.jsonl (one record per run, run-local,
    no cross-session recurrence).
    """
    import json as _json
    import time as _time
    record: dict = {
        "event": "discovery_evidence_status",
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "run_id": run_id,
        "state_dir": str(state_dir),
        "exists": False,
        "writer_attempted": "unknown",
        "writer_error": False,
        "writer_dropped_all": "unknown",
        "findings_count": 0,
        "structural_issue_count": 0,
        "source": "absent",
        "artifact_path": None,
        "failure_direction": "absent is non-blocking",
    }
    de_path = state_dir / f"discovery-evidence_{run_id}.json"
    ct_path = state_dir / f"claude-task-result_{run_id}.json"
    # Check for PI writer-error telemetry (multi-terminal safe: run_id-scoped).
    err_path = state_dir / f"telemetry-discovery-evidence-error_{run_id}.jsonl"
    if err_path.exists():
        record["writer_error"] = True
        record["source"] = "writer_error"
        record["failure_direction"] = "writer failure detected -- non-blocking"
    chosen = None
    chosen_path = None
    if de_path.exists():
        chosen, chosen_path = de_path, str(de_path)
        record["source"] = "discovery-evidence file"
    elif ct_path.exists():
        chosen, chosen_path = ct_path, str(ct_path)
        record["source"] = "claude-task-result fallback"
    if chosen is not None:
        try:
            data = _json.loads(chosen.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record["source"] = "absent"
            record["failure_direction"] = "malformed -- non-blocking"
        else:
            findings = (data.get("findings")
                        or (data.get("discovery_evidence") or {}).get("findings")
                        or [])
            if isinstance(findings, list) and findings:
                record["exists"] = True
                record["findings_count"] = len(findings)
                record["structural_issue_count"] = sum(
                    1 for f in findings
                    if isinstance(f, dict)
                    and isinstance(f.get("structural_issues"), list)
                    and f["structural_issues"]
                )
                record["artifact_path"] = chosen_path
            else:
                record["writer_dropped_all"] = True
                record["source"] = "absent"
                record["failure_direction"] = "artifact present, no findings -- non-blocking"
    # Run-local: one JSONL record per run, no cross-session state.
    try:
        tel_path = state_dir / f"telemetry-discovery-evidence_{run_id}.jsonl"
        with tel_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record) + "
")
    except OSError:
        pass  # telemetry is best-effort; never block
    return record


# ---------------------------------------------------------------------------
# PI Outcome Metrics -- advisory, run-local, multi-terminal safe.
# ---------------------------------------------------------------------------
_TASK_CLASSES_WITHOUT_PI = frozenset({"hook", "gate", "cache", "state", "migration"})
_RISK_CLASSES_AVOID_PI = frozenset({"high", "critical"})


def classify_pi_advisory(metrics: dict) -> str:
    """Classify PI suitability from run-local outcome metrics. Advisory only."""
    dispatch = metrics.get("dispatch_route", "")
    risk = metrics.get("risk_class", "")
    task_class = metrics.get("task_class", "")
    review = metrics.get("review_verdict", "")
    rescue = metrics.get("rescue_escalation_needed", False)
    writer_error = metrics.get("writer_error", False)

    if any(tc in task_class.lower() for tc in _TASK_CLASSES_WITHOUT_PI):
        return "avoid_pi"
    if risk in _RISK_CLASSES_AVOID_PI:
        return "avoid_pi"
    if rescue:
        return "pi_evidence_collector"
    if dispatch == "pi" and not writer_error:
        if review in ("clean", "clean_with_minor_warnings", ""):
            return "pi_strong_candidate"
        return "pi_ok_with_review"
    if dispatch == "pi" and writer_error:
        return "pi_evidence_collector"
    return "avoid_pi"


def record_pi_outcome(state_dir, run_id, dispatch_route: str = "", task_class: str = "",
                      risk_class: str = "", review_verdict: str = "",
                      rescue_escalation_needed: bool = False,
                      failure_shape: str = "", final_disposition: str = "",
                      writer_error: bool = False) -> dict:
    """Record PI outcome metrics to a run-local JSONL file.

    Writer: run_common_tail (Step 13).
    Storage: state_dir/pi-outcome_{run_id}.jsonl (run-local, run_id-scoped).
    Reader: manual inspection or future aggregate script (advisory-only).
    Authority: run-scoped; missing/corrupt metrics do not promote PI.
    Freshness: per-run; one record per invocation.
    Failure direction: never blocks the run.
    """
    import json as _json, time as _time

    proposal_file = state_dir / f"task-proposal_{run_id}.json"
    proposal = {}
    if proposal_file.exists():
        try:
            proposal = _json.loads(proposal_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    if not dispatch_route:
        dispatch_route = proposal.get("dispatch", proposal.get("suggestedDispatch", ""))
    if not task_class:
        task_class = proposal.get("task_type", proposal.get("task_intent", ""))
    if not risk_class:
        risk_class = proposal.get("risk", proposal.get("execution_tier", ""))

    de_tel_file = state_dir / f"telemetry-discovery-evidence_{run_id}.jsonl"
    de_record = {}
    if de_tel_file.exists():
        try:
            lines = de_tel_file.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                de_record = _json.loads(lines[-1])
        except (OSError, ValueError):
            pass
    discovery_emitted = de_record.get("exists", False)
    writer_error = writer_error or de_record.get("writer_error", False)

    files_touched = proposal.get("files_touched", [])
    pi_review_file = state_dir / f"pi-review_{run_id}.json"
    if not files_touched and pi_review_file.exists():
        try:
            pr = _json.loads(pi_review_file.read_text(encoding="utf-8"))
            files_touched = pr.get("files_read", []) + pr.get("files_written", [])
        except (OSError, ValueError):
            pass

    git_head = ""
    try:
        # Read .git/HEAD directly to avoid subprocess monkeypatch issues.
        head_file = Path.cwd() / ".git" / "HEAD"
        if head_file.exists():
            raw = head_file.read_text(encoding="utf-8").strip()
            if not raw.startswith("ref:"):
                git_head = raw[:12]
            else:
                ref = head_file.parent / raw.split()[1]
                if ref.exists():
                    git_head = ref.read_text(encoding="utf-8").strip()[:12]
    except Exception:
        pass

    plugin_version = ""
    pv_file = Path(__file__).resolve().parent.parent / "plugin.json"
    try:
        plugin_version = _json.loads(pv_file.read_text(encoding="utf-8")).get("version", "")
    except (OSError, ValueError):
        pass

    advisory = classify_pi_advisory({
        "dispatch_route": dispatch_route,
        "risk_class": risk_class,
        "task_class": task_class,
        "review_verdict": review_verdict,
        "rescue_escalation_needed": rescue_escalation_needed,
        "writer_error": writer_error,
        "discovery_emitted": discovery_emitted,
    })

    record = {
        "event": "pi_outcome",
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "run_id": run_id,
        "state_dir": str(state_dir),
        "git_head": git_head,
        "plugin_version": plugin_version,
        "dispatch_route": dispatch_route,
        "task_class": task_class,
        "risk_class": risk_class,
        "files_touched": files_touched[:20],
        "discovery_emitted": discovery_emitted,
        "writer_error": writer_error,
        "review_verdict": review_verdict,
        "rescue_escalation_needed": rescue_escalation_needed,
        "failure_shape": failure_shape,
        "final_disposition": final_disposition,
        "pi_advisory": advisory,
    }

    try:
        tel_path = state_dir / f"pi-outcome_{run_id}.jsonl"
        with tel_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record) + "
")
    except OSError:
        pass
    return record



# ---------------------------------------------------------------------------
# Local-model acceptance validation + failover telemetry.
# ---------------------------------------------------------------------------
_LOCAL_ACCEPT_TIMEOUT_S = 30
_LOCAL_ACCEPT_MIN_OUTPUT_CHARS = 20


def accept_local_candidate(pi_output: str) -> bool:
    """Validate that a local model response is usable (not thinking-only/empty).

    Returns True if the response has sufficient text output and is not
    malformed. Returns False if the response should be rejected in favor
    of the next candidate (M3 fallback).

    Local acceptance criteria:
      - Non-empty final text output
      - Minimum output length (>= _LOCAL_ACCEPT_MIN_OUTPUT_CHARS)
      - No malformed JSON when JSON output was expected
      - Thinking-only completion counts as failure (no visible text)
    """
    if not pi_output or not pi_output.strip():
        return False
    # Strip thinking/reasoning blocks — accept if remaining text is meaningful.
    stripped = pi_output.strip()
    if len(stripped) < _LOCAL_ACCEPT_MIN_OUTPUT_CHARS:
        return False
    return True


def record_failover_telemetry(state_dir, run_id: str, candidate_chain: list,
                              attempted_model: str, provider: str, outcome: str,
                              failure_reason: str = "", fallback_selected: str = "",
                              final_model: str = "", final_status: str = "") -> dict:
    """Record PI failover telemetry to a run-local JSONL file.

    Run-local, multi-terminal safe. All artifacts keyed by run_id.
    """
    import json as _json, time as _time
    record = {
        "event": "pi_failover",
        "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "run_id": run_id,
        "state_dir": str(state_dir),
        "candidate_chain": candidate_chain,
        "attempted_model": attempted_model,
        "provider": provider,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "fallback_selected": fallback_selected,
        "final_model": final_model,
        "final_status": final_status,
    }
    try:
        tel_path = state_dir / f"failover-telemetry_{run_id}.jsonl"
        with tel_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record) + "
")
    except OSError:
        pass
    return record

def run_preflight(args: Any, state_dir: Path, run_id: str, terminal_id: str) -> Path:
    """Build proposal + write ``task-proposal-<runid>.json`` (terminal-scoped).

    Returns the artifact path. The orchestrator owns phase markers and
    ``current-run.json`` updates so existing marker conventions stay coherent.

    When the prompt is high-risk (prompt_review_required) and prompt-review
    support is absent, also write a tracked prerequisite artifact so the gap is
    visible instead of silently skipped (goal req. 7).
    """
    proposal = generate_proposal(args.prompt, run_id, terminal_id)
    artifact = state_dir / f"task-proposal_{run_id}.json"
    _atomic_write_json(artifact, proposal)

    if (
        proposal.get("prompt_review_required")
        and proposal.get("prompt_review_support") == "absent"
    ):
        prereq = state_dir / f"prompt-review-prerequisite_{run_id}.json"
        _atomic_write_json(prereq, {
            "run_id": run_id,
            "terminal_id": terminal_id,
            "kind": "missing-prompt-review-support",
            "reason": (
                "High-risk surface detected but no prompt-review artifact gate "
                "exists in skills/go yet. High-risk dispatch must be blocked or "
                "authorized by the director; do not pretend review occurred."
            ),
            "matched_markers": proposal["risk_signals"]["matched_markers"],
            "execution_tier": proposal["execution_tier"],
            "blocking": proposal["execution_tier"] == "pause_for_authorization",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return artifact


if __name__ == "__main__":
    # ponytail self-check
    sample = "can you fix the parser to handle None in foo.py?"
    out = generate_proposal(sample, "run-self", "tid-self")
    assert out["suggestedDispatch"] in ("pi", "local", "claude")
    assert "rewrittenGoal" in out and out["rewrittenGoal"].startswith("fix")
    assert out["task_intent"] in _INTENT_VALUES
    assert out["execution_tier"] in (
        "direct_answer", "local_surgical", "local_rigorous", "full_go",
        "pause_for_authorization",
    )
    assert isinstance(out["report_gate"]["allow_implementation_completion_claim"], bool)
    dp = out["delegation_policy"]
    assert dp["worker"] in (None,) + _ROLE_VALUES
    assert dp["advisory_reviewer"] in _ROLE_VALUES
    assert dp["advisory_is_evidence_not_authority"] is True
    assert set(dp["mutation_authority"]) == set(_ROLE_VALUES)
    assert isinstance(dp["worker_scope"], list)
    assert dp["worker_enforcement"] in ("path-bound", "type-bound", "worktree")
    assert isinstance(dp["enforcement"]["mutating_tools"], list)
    assert_fresh(out, "run-self")  # freshness contract holds for current run
    # closure_check: bugfix prompts require closure + confirm-closed gating.
    cc = out["closure_check"]
    assert cc["required"] is True, "fix prompt must require closure_check"
    assert cc["source"] in _CLOSURE_SOURCE_VALUES
    assert out["report_gate"]["closure_check_required"] is True
    assert out["report_gate"]["confirm_closed_required"] is True
    assert out["report_gate"]["confirm_closed_passes"] is False  # no evidence yet
    # confirm_closed_passes: evidence + expected_after satisfy; unavailable_reason alone passes.
    cc_pass = dict(cc, evidence_summary="ran repro", expected_after="symptom gone")
    assert confirm_closed_passes(cc_pass) is True
    cc_unavail = dict(cc, unavailable_reason="flaky; cannot reproduce deterministically")
    assert confirm_closed_passes(cc_unavail) is True
    # investigate prompts must not enable completion claims.
    inv = generate_proposal("investigate why the hook double-fires", "run-inv", "tid")
    assert inv["task_intent"] in ("investigate", "mixed")
    assert not inv["report_gate"]["allow_implementation_completion_claim"]
    # investigate intent does NOT require closure_check (req. 8).
    assert inv["closure_check"]["required"] is False
    # operational discovery: the hook-double-fires investigate prompt hits a surface.
    od = inv["operational_discovery"]
    assert od["required"] is True, "hook investigate prompt must trigger discovery_first"
    assert "hook" in od["surfaces"]
    assert od["cleanup_requires_approval"] is True
    assert od["identify_checklist"] and od["empirical_oracle_preferred"] is True
    assert od["verification_paths"], "investigate must list ≥2 verification paths"
    assert od["verification_paths"][0]["path"].startswith("empirical")
    assert inv["plain_english_report"].get("discovery_evidence"), "report must scaffold discovery_evidence"
    # worktree lifecycle question → safe prune predicate, no blind deletion.
    wt = generate_proposal("do git worktrees accumulate over time?", "run-wt", "tid")
    assert wt["operational_discovery"]["required"] is True
    assert "worktree" in wt["operational_discovery"]["surfaces"]
    assert wt["operational_discovery"]["worktree_prune_predicate"]
    assert "explicit director approval" in " ".join(wt["operational_discovery"]["worktree_prune_predicate"]).lower()
    print(
        f"preflight_propose: self-check OK (dispatch={out['suggestedDispatch']}, "
        f"intent={out['task_intent']}, tier={out['execution_tier']}, "
        f"closure_required={out['closure_check']['required']}, "
        f"discovery_required={od['required']})"
    )
