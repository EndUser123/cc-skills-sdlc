"""
wiki_filter_calibration.py — Measure the filter's TP/FP rate on a labeled held-out set.

Per the gate-discrimination rule: a gate cannot ship as a *blocking* hook until
its TP/FP rate is measured on a real corpus. This script lets you build a small
labeled set, run the filter against it, and compute precision/recall on the
labels.

Held-out file format (JSONL, one object per line):
  {"sentence": "<candidate text>", "label": "durable" | "noise" | "ambiguous",
   "reason": "<optional one-line why>"}

Output (JSON):
  {
    "total": <int>, "durable_true": <int>, "noise_true": <int>, "ambiguous_true": <int>,
    "kept": <int>, "dropped": <int>, "kept_durable_correct": <int>,
    "precision_kept": <float>,   # TP / kept
    "recall_durable": <float>,    # TP / durable_true
    "false_negative_rate": <float>,  # dropped-but-durable / durable_true
    "false_positive_rate": <float>,  # kept-but-noise / kept
    "by_drop_reason": {...}      # breakdown of the wiki_signal_filter drop labels
  }

Usage:
    python wiki_filter_calibration.py \\
        --in P:/.data/wiki/_incoming/signal_candidates.json \\
        --labels P:/data/calibration/filter_labels.jsonl \\
        --out P:/data/calibration/filter_metrics.json \\
        [--wiki P:/.data/wiki/concepts]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Import the actual filter functions so the test exercises the same code path
sys.path.insert(0, str(Path(__file__).parent))
from wiki_signal_filter import is_tool_output_noise, has_durable_signature  # noqa: E402

WIKI_OVERLAP_DEFAULT = 0.95  # must match wiki_signal_filter.py hardcoded threshold


def _is_wiki_overlap_drop(sent: str, wiki_words: set[str], threshold: float) -> bool:
    """Check if a sentence would be dropped by the wiki-overlap gate."""
    words = {w for w in __import__("re").findall(r"[A-Za-z0-9]+", sent.lower()) if len(w) >= 4}
    if not words:
        return False
    return len(words & wiki_words) / len(words) >= threshold


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_path", required=True, help="Candidates JSON (from extract)")
    ap.add_argument("--labels", required=True, help="JSONL labeled held-out set")
    ap.add_argument("--out", required=True, help="Output metrics JSON path")
    ap.add_argument("--wiki", default="P:/.data/wiki/concepts", help="Wiki dir (for word-shard overlap)")
    ap.add_argument("--overlap", type=float, default=WIKI_OVERLAP_DEFAULT, help="Wiki overlap threshold")
    args = ap.parse_args()

    candidates = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    cand_by_sentence = {c["sentence"].strip(): c for c in candidates}

    # Load labels
    labels = []
    with open(args.labels, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            labels.append(json.loads(line))

    # Build wiki shingle set
    wiki_words: set[str] = set()
    wiki = Path(args.wiki)
    if wiki.is_dir():
        for p in wiki.glob("*.md"):
            try:
                tokens = {w for w in __import__("re").findall(r"[A-Za-z0-9]+", p.read_text(encoding="utf-8", errors="replace").lower()) if len(w) >= 4}
                wiki_words.update(tokens)
            except Exception:
                pass

    # Run the filter on every labeled sentence
    durable_true = sum(1 for l in labels if l["label"] == "durable")
    noise_true = sum(1 for l in labels if l["label"] == "noise")
    ambiguous_true = sum(1 for l in labels if l["label"] == "ambiguous")

    tp = fp = fn = tn = 0
    drop_reasons: dict[str, int] = {}
    for label_entry in labels:
        sent = label_entry["sentence"].strip()
        if sent not in cand_by_sentence:
            continue  # only evaluate candidates the filter actually saw
        is_noise, _ = is_tool_output_noise(sent)
        if is_noise:
            drop_reasons["tool-output-noise"] = drop_reasons.get("tool-output-noise", 0) + 1
            if label_entry["label"] == "durable":
                fn += 1
            else:
                tn += 1
            continue
        ok, _ = has_durable_signature(sent)
        if not ok:
            drop_reasons["no-durable-signature"] = drop_reasons.get("no-durable-signature", 0) + 1
            if label_entry["label"] == "durable":
                fn += 1
            else:
                tn += 1
            continue
        # Wiki overlap check
        words = {w for w in __import__("re").findall(r"[A-Za-z0-9]+", sent.lower()) if len(w) >= 4}
        if not words:
            drop_reasons["no-words"] = drop_reasons.get("no-words", 0) + 1
            if label_entry["label"] == "durable":
                fn += 1
            else:
                tn += 1
            continue
        if len(words & wiki_words) / len(words) >= args.overlap:
            drop_reasons["wiki-overlap"] = drop_reasons.get("wiki-overlap", 0) + 1
            if label_entry["label"] == "durable":
                fn += 1
            else:
                tn += 1
            continue
        # Kept
        if label_entry["label"] == "durable":
            tp += 1
        else:
            fp += 1

    kept = tp + fp

    # Compute recall excluding wiki-overlap drops (those sentences are already
    # in the wiki; dropping them is correct dedup, not a filter recall failure).
    # STATE-001 fix: separates "filter didn't recognize" from "wiki already has it".
    durable_wiki_overlap_drops = drop_reasons.get("wiki-overlap", 0)  # approx: some noise too
    durable_filter_fn = fn - sum(1 for l in labels if l["label"] == "durable" and l["sentence"].strip() in cand_by_sentence and _is_wiki_overlap_drop(l["sentence"].strip(), wiki_words, args.overlap))
    novel_durable = durable_true - durable_wiki_overlap_drops if durable_wiki_overlap_drops < durable_true else 1

    metrics = {
        "total": len(labels),
        "durable_true": durable_true,
        "noise_true": noise_true,
        "ambiguous_true": ambiguous_true,
        "kept": kept,
        "dropped": tp + fp + fn + tn - kept,
        "kept_durable_correct": tp,
        "precision_kept": (tp / kept) if kept else None,
        "recall_durable": (tp / durable_true) if durable_true else None,
        "recall_on_novel_only": (tp / novel_durable) if novel_durable > 0 else None,
        "false_negative_rate": (fn / durable_true) if durable_true else None,
        "false_positive_rate": (fp / kept) if kept else None,
        "by_drop_reason": drop_reasons,
        "thresholds": {"wiki_overlap": args.overlap, "noise_threshold": 2},
    }
    Path(args.out).write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote: {args.out}")
    print(f"  total labeled:        {len(labels)}")
    print(f"  durable_true:         {durable_true}")
    print(f"  noise_true:           {noise_true}")
    print(f"  TP (durable kept):   {tp}")
    print(f"  FP (noise kept):     {fp}")
    print(f"  FN (durable dropped): {fn}")
    print(f"  TN (noise dropped):  {tn}")
    if metrics["precision_kept"] is not None:
        print(f"  precision (kept):    {metrics['precision_kept']:.1%}")
    if metrics["recall_durable"] is not None:
        print(f"  recall (durable):    {metrics['recall_durable']:.1%}")
    print(f"  drop reasons:         {drop_reasons}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())