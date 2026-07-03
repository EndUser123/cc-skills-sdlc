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
        ['Must show direct invocation stdout (not just return value)', 'Must show negative case ran without blocking'],
    ),
    (
        ('/go change', 'go change', '/go', 'orchestrator change', 'orchestrate.py', 'common_tail', 'worker prompt', 'task_prompt'),
        ['Mutating active-task file during dry-run', 'Changing dispatch behavior without updating CLI smoke test', 'Breaking plan/planless branch split logic'],
        ['Read orchestrate.py CLI entry points before editing', 'Confirm which branch (prompt/plan/recon-bypass) is affected'],
        ['grep function call sites of any changed function', 'Read the test file for the affected code path'],
        ['Active-task JSON must NOT be mutated by --recon-bypass or --preflight-only', 'orchestrate.py --help must exit 0 after change'],
        ['Must show active-task diff (or no-diff assertion) between pre/post dry-run'],
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


def _normalize(prompt: str) -> str:
    return " ".join(prompt.split()).strip()


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


def generate_proposal(
    prompt: str,
    run_id: str,
    terminal_id: str,
) -> dict[str, Any]:
    """Build the proposal dict. Matches the spec'd JSON shape exactly."""
    rewritten = rewrite_goal(prompt)
    dispatch, local_eligible, requires_approval = classify_dispatch(rewritten)
    return {
        "runid": run_id,
        "terminalid": terminal_id,
        "source": "cli-preflight",
        "originalPrompt": prompt,
        "rewrittenGoal": rewritten,
        "suggestedDispatch": dispatch,
        "localEligible": local_eligible,
        "requiresApproval": requires_approval,
        "verificationSuggestions": verification_suggestions(rewritten),
        "verificationPolicy": _verification_policy_key(rewritten),
        "notes": [
            "Deterministic heuristic (no LLM). dispatch="
            f"{dispatch} localEligible={local_eligible}",
        ],
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
    """
    proposal = generate_proposal(args.prompt, run_id, terminal_id)
    artifact = state_dir / f"task-proposal_{run_id}.json"
    _atomic_write_json(artifact, proposal)
    return artifact


if __name__ == "__main__":
    # ponytail self-check
    sample = "can you fix the parser to handle None in foo.py?"
    out = generate_proposal(sample, "run-self", "tid-self")
    assert out["suggestedDispatch"] in ("pi", "local", "claude")
    assert "rewrittenGoal" in out and out["rewrittenGoal"].startswith("fix")
    print(f"preflight_propose: self-check OK (dispatch={out['suggestedDispatch']})")
