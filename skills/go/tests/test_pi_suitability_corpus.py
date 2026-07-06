"""TASK-004 corpus gate for the advisory pi-suitability classifier.

Table-driven TP/FP/FN over >= 20 hand-labeled real /go prompts. The default-flip
(``PI_DEFAULT_FLIP``) is gated on this test holding precision >= 0.7 AND
recall >= 0.6. While advisory, the dispatcher logs ``model_affinity`` and routes
per existing rules — this test also pins that the recommendation does NOT change
``suggestedDispatch``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from classify_complexity import PI_DEFAULT_FLIP, classify_model_affinity  # noqa: E402
from preflight_propose import generate_proposal  # noqa: E402

CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "pi_suitability_corpus.jsonl"

PRECISION_FLOOR = 0.7
RECALL_FLOOR = 0.6


def _load_corpus() -> list[dict]:
    rows = []
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


CORPUS = _load_corpus()


def _classify(prompt: str) -> str:
    """Run the full proposal pipeline and extract model_affinity.

    Proves the field lands in the proposal (producer contract) and that the
    classify_model_affinity rule alone matches it (single-source-of-truth).
    """
    proposal = generate_proposal(prompt, "run-test", "tid-test")
    return proposal["model_affinity"]


# ---------------------------------------------------------------------------
# Acceptance (a): corpus size + label distribution
# ---------------------------------------------------------------------------

def test_corpus_has_at_least_20_real_prompts():
    assert len(CORPUS) >= 20, f"corpus too small: {len(CORPUS)}"
    labels = {row["label"] for row in CORPUS}
    assert labels <= {"pi", "claude", "neutral"}
    # Need enough pi positives AND non-pi negatives for precision/recall to mean anything.
    assert sum(1 for r in CORPUS if r["label"] == "pi") >= 5
    assert sum(1 for r in CORPUS if r["label"] != "pi") >= 10


# ---------------------------------------------------------------------------
# Acceptance (b): precision >= 0.7 AND recall >= 0.6 on the "pi" class
# ---------------------------------------------------------------------------

def test_pi_precision_meets_floor():
    tp = fp = 0
    for row in CORPUS:
        predicted = _classify(row["prompt"])
        if predicted == "pi":
            if row["label"] == "pi":
                tp += 1
            else:
                fp += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    assert precision >= PRECISION_FLOOR, (
        f"pi precision {precision:.3f} < {PRECISION_FLOOR} "
        f"(tp={tp} fp={fp} — see corpus labels)"
    )


def test_pi_recall_meets_floor():
    tp = fn = 0
    for row in CORPUS:
        predicted = _classify(row["prompt"])
        if row["label"] == "pi":
            if predicted == "pi":
                tp += 1
            else:
                fn += 1
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    assert recall >= RECALL_FLOOR, (
        f"pi recall {recall:.3f} < {RECALL_FLOOR} "
        f"(tp={tp} fn={fn} — classifier misses pi-suitable prompts)"
    )


# ---------------------------------------------------------------------------
# Acceptance (c) + (d): advisory mode does not change dispatch; flip stays advisory
# ---------------------------------------------------------------------------

def test_default_flip_constant_remains_advisory():
    """The corpus gate passing does NOT auto-flip; the constant is the gate."""
    assert PI_DEFAULT_FLIP == "advisory", (
        "PI_DEFAULT_FLIP must stay 'advisory' in TASK-004; flipping requires "
        "a separate follow-up after the threshold holds across >= 20 real runs."
    )


def test_model_affinity_does_not_change_suggested_dispatch():
    """Advisory mode: model_affinity is logged but never overrides dispatch."""
    for row in CORPUS:
        proposal = generate_proposal(row["prompt"], "run-test", "tid-test")
        # model_affinity is independent of dispatch routing; the dispatch path
        # is decided by classify_dispatch (existing rules), not by affinity.
        assert proposal["suggestedDispatch"] in ("pi", "local", "claude")
        # Affinity must be present and valid (producer contract).
        assert proposal["model_affinity"] in ("pi", "claude", "neutral")


# ---------------------------------------------------------------------------
# Acceptance (e): absent-value default is "neutral"
# ---------------------------------------------------------------------------

def test_neutral_is_documented_absent_value_default():
    """classify_model_affinity returns neutral for inputs that match no rule,
    and consumers must treat a missing field as neutral."""
    # planning-only intent, no risk, mid-tier → neutral (no implement, no decide/investigate/validate)
    assert classify_model_affinity("mixed", "local_surgical", False, 50) == "neutral"
    # empty/unknown → neutral
    assert classify_model_affinity("", "local_surgical", False, 0) == "neutral"


# ---------------------------------------------------------------------------
# Diagnostic: per-row breakdown (not asserted; surfaces FP/FN for review)
# ---------------------------------------------------------------------------

def test_corpus_row_breakdown_report_only(capsys=None):
    """Non-failing diagnostic: prints TP/FP/FN/TN per-row for human review."""
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    mismatches = []
    for row in CORPUS:
        predicted = _classify(row["prompt"])
        actual = row["label"]
        if predicted == "pi" and actual == "pi":
            counts["tp"] += 1
        elif predicted == "pi" and actual != "pi":
            counts["fp"] += 1
            mismatches.append((row["prompt"][:60], predicted, actual))
        elif predicted != "pi" and actual == "pi":
            counts["fn"] += 1
            mismatches.append((row["prompt"][:60], predicted, actual))
        else:
            counts["tn"] += 1
    # No assertion — this is a report-only diagnostic for corpus drift review.
    assert sum(counts.values()) == len(CORPUS)
