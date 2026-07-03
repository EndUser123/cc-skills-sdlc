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
    """Heuristic verification strings. Not wired to task contract yet."""
    low = rewritten.lower()
    out: list[str] = []
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
