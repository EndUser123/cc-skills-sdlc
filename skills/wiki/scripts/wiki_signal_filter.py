"""
wiki_signal_filter.py — Tighten signal-sentence candidates from a transcript scan
into genuine durable findings by classifying each candidate as tool-output noise
vs. extractable principle.

Two passes:
  1. tool-output classifier  — skip sentences that look like leaked tool stderr,
     health-check banners, benchmark dumps, JSON blobs, regex/code literals,
     or agent-thinking prose without a concrete claim.
  2. durable-claim classifier — keep only sentences with a verdict-shaped
     claim: root cause / fix / decision / rejected alternative / measured number
     attached to a concrete entity (file:line, function, hook, env var, etc.).

Reads: a signal-sentence JSON list produced by transcript_signal_extractor.py
        (shape: [{file, sentence, novelty}, ...]).
Writes: a filtered JSON list + a markdown digest.

Usage:
    python wiki_signal_filter.py --in P:/tmp/signal_candidates.json \\
        --wiki P:/.data/wiki/concepts --out P:/tmp/durable_candidates.json
    python wiki_signal_filter.py --help
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

# --- Pass 1: tool-output noise patterns ----------------------------------------
# Each pattern, if matched, contributes 1 point; >= 3 points = noise (skip).
TOOL_OUTPUT_PATTERNS: list[re.Pattern[str]] = [
    # Tool-output banners / framing
    re.compile(r"^\s*\[?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", re.I),  # ISO timestamps
    re.compile(r"^\s*\d+\s*[\|┃]\s+", re.M),                            # table rows
    re.compile(r"✅|❌|⚠️|⏺|⎿|💡|🟢|🔴|🚨"),                          # status emojis
    re.compile(r"^(?:EXIT|ERROR|WARN|INFO|DEBUG)_\w+", re.I),         # log levels
    re.compile(r"^---\s*$", re.M),                                     # yaml/frontmatter fences
    re.compile(r"^```", re.M),                                         # code fence lines
    re.compile(r"^\s*(?:pip|uv|poetry|npm|yarn|pnpm|cargo|make|cmake)\s+(?:install|run|build|test|add)", re.I),
    re.compile(r"\b\d+\.\d+\.\d+\b"),                                  # version strings (often in tool dumps)
    re.compile(r"\b(?:KB|MB|GB|MiB|GiB)\s*$", re.M),                  # trailing size units
    re.compile(r"^P:\\\\|^C:\\\\|^/tmp/|^/Users/"),                     # raw paths at start
    re.compile(r"^\s*[-•*]\s*[\[\(]?\d+[\]\)]?\s*[-•*]"),               # numbered lists of tool rows
    re.compile(r"^(?:User|Assistant|system|Human):\s", re.I),           # transcript role labels
    re.compile(r"\b(?:api[_-]?key|secret|token|password)\b", re.I),    # secrets (assume scraped)
    re.compile(r"\b[a-f0-9]{32,}\b"),                                  # long hex (hashes, tokens)
]

# Threshold: if a sentence matches >= NOISE_THRESHOLD patterns, it's noise.
# 2 = strict (skips only clearly-tool-output); 3 = loose (keeps more prose).
NOISE_THRESHOLD = 2

# --- Pass 2: durable-claim signatures -----------------------------------------
# A "durable claim" requires at least one DECISION verb and one CONCRETE ANCHOR.
# A "durable claim" requires at least one DECISION verb and one CONCRETE ANCHOR.
# The decision-verb regex is broad: any sentence that asserts a causal/recommendation/
# corrective/rejection/constraint fact counts, not just "the fix is X" templates.
DECISION_VERBS = re.compile(
    r"\b(?:root cause|the (?:real|actual|underlying)\s+(?:reason|cause|issue)|"
    r"the fix (?:is|was|was to)\b|fix(?:ed|es)? (?:by|via|requires?|is to)\b|"
    r"caused by\b|happens when\b|inverts?\b|silently\b.{0,40}(?:fail|drop|ignore|swallow|discard)|"
    r"never (?:fires?|runs?|reaches?|executes?|registered|wired)\b|"
    r"by design\b|cannot\b.{0,40}(?:rewrite|intercept|block|enforce|detect|read)|"
    r"dead code\b|orphan(?:ed)?\b|MUST NOT\b|MUST (?:not|emit|be|use)\b|"
    r"rejected (?:because|since)\b|trade-?off\b|"
    r"we (?:decided|chose|rejected|adopted)\b|"
    r"platform (?:limit|constraint)\b|in production|"
    r"this is (?:the (?:actual|real))?\s*(?:root cause|bug|fix)|"
    # broader captures seen in the corpus
    r"\b(?:triggers?|triggered) at\b|\b(?:mitigated by|mitigates|reduces? (?:overhead|context|token))|"
    r"\b(?:warning|warns?|block|blocks?|blocks?|fail|failed|fails?) (?:at|on|when|before|after)\b|"
    r"\bexceeds?\b.{0,40}\b(?:buffer|threshold|limit|cap)|"
    r"\b(?:skips?|skipped) (?:on|when|because)\b|"
    r"\b(?:fix (?:is|was) to)\b|"
    r"\b(?:Fabrication|Hallucination)\b.{0,30}:|"
    r"\b(?:provid|provid|provided|provides) (?:no|full|partial)\b.{0,20}\bcontrol|"
    r"\b(?:imports? from|imports? non-?existent)\b)",
    re.I,
)

ANCHOR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b[\w_]+\.py:\d+"),                  # file.py:line
    re.compile(r"\bHookSpecificOutput|hookEventName\b"),
    re.compile(r"\b(?:PreToolUse|PostToolUse|SessionStart|PreCompact|UserPromptSubmit)\b"),
    re.compile(r"\bsettings\.json\b"),
    re.compile(r"\b[\w_]+\.[A-Z]{2,5}\b"),           # module.CONST
    re.compile(r"\b(?:exit code|HTTP)\s*\d+"),
    re.compile(r"\b\d+\s*(?:ms|seconds?|tokens?|KB|MB|GB|%|×)\b"),
    re.compile(r"\b(?:env_?var|environment variable|ANTHROPIC_\w+|GO_RUN_ID|CLAUDE_GO_)\w*"),
    re.compile(r"\b(?:Stop_router|skill_first_gate|cdp_start|Stop\.py|main_health|Stop_aggregator|Stop_artifact_enforcement|Stop_semantic_critic|claim_patterns|cross_validator|unified_evidence_enforcer|hook_runner|preflight_propose|orchestrate\.py)\w*"),
    re.compile(r"\bline\s+\d{1,4}\b"),
    # Architectural anchors: hook lifecycle events with concrete names
    re.compile(r"\b(?:HandoffValidationError|EpistemicPolicyResult|HookEventName|additionalContext|permissionDecision|systemMessage)\b"),
    # Class / function / module names with PascalCase or camelCase boundary
    re.compile(r"\b(?:[A-Z][a-z]+(?:[A-Z][a-z]+)+)\b"),     # PascalCase
    re.compile(r"\b(?:apply_epistemic_policy|extract_targeted_context|resolve_terminal_key|load_raw_handoff|should_block_claim)\w*"),
]

# Minimum signature: 1 decision verb AND >= 1 anchor
def has_durable_signature(sent: str) -> tuple[bool, str]:
    if not DECISION_VERBS.search(sent):
        return False, "no-decision-verb"
    for pat in ANCHOR_PATTERNS:
        if pat.search(sent):
            return True, ""
    return False, "no-concrete-anchor"


def is_tool_output_noise(sent: str) -> tuple[bool, int]:
    hits = sum(1 for p in TOOL_OUTPUT_PATTERNS if p.search(sent))
    return hits >= NOISE_THRESHOLD, hits


def main() -> int:
    ap = argparse.ArgumentParser(description="Filter signal-sentence candidates into durable claims.")
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSON from transcript_signal_extractor.py")
    ap.add_argument("--wiki", dest="wiki_dir", default="P:/.data/wiki/concepts", help="Wiki vault for overlap dedup")
    ap.add_argument("--out", dest="out_path", required=True, help="Output JSON of durable candidates")
    ap.add_argument("--report", dest="report_path", default=None, help="Optional markdown digest path")
    ap.add_argument("--noise-threshold", type=int, default=NOISE_THRESHOLD, help="Tool-output pattern hits to skip")
    args = ap.parse_args()

    candidates: list[dict] = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    print(f"loaded {len(candidates)} candidates from {args.in_path}")

    # Build wiki shingle index for second-pass dedup (only against the most recent
    # wiki files since the input was already deduped against them by the extractor)
    wiki_shingles: set[str] = set()
    for p in Path(args.wiki_dir).glob("*.md"):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
            for line in re.findall(r"\b[a-z0-9]{4,}\b", t.lower()):
                wiki_shingles.add(line)
        except Exception:
            pass

    kept: list[dict] = []
    noise_dropped = 0
    claim_dropped = 0
    novel_dropped = 0
    for c in candidates:
        sent = c["sentence"]
        # Pass 1: tool-output noise
        is_noise, hits = is_tool_output_noise(sent)
        if is_noise:
            noise_dropped += 1
            continue
        # Pass 2: durable signature
        ok, reason = has_durable_signature(sent)
        if not ok:
            claim_dropped += 1
            continue
        # Already-covered check (cheap word-shard overlap; extractor used shingle Jaccard)
        words = set(re.findall(r"\b[a-z0-9]{4,}\b", sent.lower()))
        if len(words) < 5:
            continue
        overlap = len(words & wiki_shingles) / len(words)
        if overlap >= 0.95:
            novel_dropped += 1
            continue
        kept.append({**c, "tool_output_hits": hits, "novelty_words": round(1 - overlap, 3)})

    print(f"  noise (tool-output):  {noise_dropped} dropped")
    print(f"  claim (no signature): {claim_dropped} dropped")
    print(f"  novel (<70% wiki):    {novel_dropped} dropped")
    print(f"  KEPT: {len(kept)}")

    Path(args.out_path).write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {args.out_path}")

    if args.report_path:
        lines = [
            "# Durable candidates (post-classifier)",
            "",
            f"- Input: {args.in_path}",
            f"- Wiki: {args.wiki_dir} ({len(wiki_shingles)} unique words)",
            f"- Output: {args.out_path}",
            "",
            f"## Stats",
            f"- Input candidates: {len(candidates)}",
            f"- Dropped (tool-output noise): {noise_dropped}",
            f"- Dropped (no durable claim signature): {claim_dropped}",
            f"- Dropped (>=70% wiki overlap): {novel_dropped}",
            f"- KEPT: {len(kept)}",
            "",
            "## Top 50 (by novelty)",
            "",
        ]
        for c in sorted(kept, key=lambda x: -x.get("novelty_words", 0))[:50]:
            lines.append(f"### {c['file']} (novel={c['novelty_words']:.0%}, tool-out-hits={c['tool_output_hits']})")
            lines.append(f"- {c['sentence']}")
            lines.append("")
        Path(args.report_path).write_text("\n".join(lines), encoding="utf-8")
        print(f"  wrote {args.report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())