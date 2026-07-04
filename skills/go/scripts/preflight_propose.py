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
    "hook", "gate", "stop hook", "pretooluse", "posttooluse", "pre tool use",
    "post tool use", "sessionstart", "sessionend",
    "identity", "dispatch", "router", "settings.json", "hooks.json",
    "cache rebuild", "plugin cache", "plugin.json", "state dir",
    "authorization", "credentials", "auth token",
)

_PROMPT_REVIEW_SUPPORT = "absent"  # no prompt-review artifact gate exists in go/ yet

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

_MUTATION_KEYWORDS = {"quarantine", "move", "delete", "git mv", "git rm", "cleanup"}
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
    has_design_ambiguity = any(kw in p for kw in ("refactor", "design", "architect", "rout"))

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

    if is_mutation:
        mode = "analysis-parallel-mutation-serialized"
        mutation_policy = "parent-only unless isolated worktree or patch bundle"
    else:
        mode = "analysis-parallel-mutation-serialized"
        mutation_policy = "serialized"

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


def derive_execution_tier(task_intent, dispatch, local_eligible, requires_approval, risk) -> str:
    """Pick the minimum sufficient ceremony.

    Tiers: direct_answer | local_surgical | local_rigorous | full_go |
    pause_for_authorization. decide always pauses. High-risk + absent
    prompt-review support forces pause so dispatch cannot silently skip review.
    """
    high_risk = bool(risk.get("high_risk"))
    if task_intent == "decide":
        return "pause_for_authorization"
    if high_risk and _PROMPT_REVIEW_SUPPORT == "absent":
        return "pause_for_authorization"
    if requires_approval:
        return "pause_for_authorization"
    if task_intent in ("investigate", "validate"):
        return "local_surgical" if local_eligible else "direct_answer"
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


def derive_report_gate(task_intent, execution_tier) -> dict:
    """Completion-claim eligibility (goal req. 8).

    investigate/validate/decide never enable implementation-completion claims.
    mixed must defer unauthorized children. implement may claim completion only
    at full_go / local_rigorous; local_surgical may claim a targeted fix only.
    """
    allow_completion = task_intent == "implement" and execution_tier in (
        "full_go", "local_rigorous", "local_surgical",
    )
    allow_targeted_fix_only = task_intent == "implement" and execution_tier == "local_surgical"
    return {
        "allow_implementation_completion_claim": allow_completion,
        "allow_targeted_fix_claim_only": allow_targeted_fix_only,
        "must_defer_unauthorized_children": task_intent == "mixed",
        "rule": (
            "investigate/validate/decide emit evidence/advisory only, no implementation-completion claim. "
            "mixed reports split + deferred items, no bundled completion claim."
        ),
    }


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
    execution_tier = derive_execution_tier(
        task_intent, dispatch, local_eligible, requires_approval, risk
    )
    report_gate = derive_report_gate(task_intent, execution_tier)
    decision_advisory = build_decision_advisory(rewritten, task_intent, execution_tier)
    prompt_review_required = bool(risk["prompt_review_required"])
    notes = [
        "Deterministic heuristic (no LLM). dispatch="
        f"{dispatch} localEligible={local_eligible}",
        f"task_intent={task_intent} execution_tier={execution_tier} "
        f"prompt_review_required={prompt_review_required}",
    ]
    if execution_tier == "pause_for_authorization":
        notes.append(
            "PAUSE: emit decision_advisory before any dispatch; do not proceed "
            "without director authorization."
        )
    return {
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
        "prompt_review_required": prompt_review_required,
        "prompt_review_support": _PROMPT_REVIEW_SUPPORT,
        "report_gate": report_gate,
        "decision_advisory": decision_advisory,
        "verificationSuggestions": verification_suggestions(rewritten),
        "verificationPolicy": _verification_policy_key(rewritten),
        "freshness": {"run_id": run_id, "must_match_run_id": True},
        "notes": notes,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


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
    assert_fresh(out, "run-self")  # freshness contract holds for current run
    # investigate prompts must not enable completion claims.
    inv = generate_proposal("investigate why the hook double-fires", "run-inv", "tid")
    assert inv["task_intent"] in ("investigate", "mixed")
    assert not inv["report_gate"]["allow_implementation_completion_claim"]
    print(
        f"preflight_propose: self-check OK (dispatch={out['suggestedDispatch']}, "
        f"intent={out['task_intent']}, tier={out['execution_tier']})"
    )
