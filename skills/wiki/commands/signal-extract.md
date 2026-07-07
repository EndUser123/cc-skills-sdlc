---
name: signal-extract
description: Bulk-extract durable findings from a noisy source directory (Downloads, transcript dumps). 4-stage pipeline: extract → filter → distill → dispatch.
required_artifacts: [signal_candidates.json, durable_candidates.json, distill_chunks/, dispatch_plan.md]
response_requirements: {intermediate_files_in: P:/.data/wiki/_incoming/}
contract_type: workflow-execution
---

# /wiki signal-extract

Run the 4-stage signal-extract pipeline against a source directory. Each stage is
a deterministic script (no LLM until the final dispatch stage).

## Arguments

`<source-dir>` — directory to scan for signal candidates. Use absolute path.

## Procedure

Execute the 4 stages sequentially. If a stage yields zero candidates, stop and report — no point running downstream stages.

```bash
SCRIPTS="P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/wiki/scripts"
WIKI="P:/.data/wiki/concepts"
INC="P:/.data/wiki/_incoming"
SRC="$1"  # user-provided source dir

# Stage 1: extract — scan all files, dedupe vs existing wiki
python "$SCRIPTS/wiki_signal_extract.py" \
  --source "$SRC" \
  --wiki "$WIKI" \
  --out "$INC/signal_candidates.json" \
  --report "$INC/signal_report.md"
# If KEPT=0 from extract, stop here.

# Stage 2: filter — drop tool-output noise + require durable-claim signature
python "$SCRIPTS/wiki_signal_filter.py" \
  --in "$INC/signal_candidates.json" \
  --wiki "$WIKI" \
  --out "$INC/durable_candidates.json" \
  --report "$INC/durable_report.md"
# If KEPT=0, report "no new durable findings" and stop.

# Stage 3: distill — group into self-contained chunks with ±15 lines source context
python "$SCRIPTS/wiki_signal_distill.py" \
  --in "$INC/durable_candidates.json" \
  --source "$SRC" \
  --out-dir "$INC/distill_chunks" \
  --context-lines 15

# Stage 4: dispatch — emit a markdown plan with one pre-filled Task-tool block per chunk
python "$SCRIPTS/wiki_signal_dispatch.py" \
  --manifest "$INC/distill_chunks/_manifest.json" \
  --chunks-dir "$INC/distill_chunks" \
  --out "$INC/dispatch_plan.md" \
  --vault "$WIKI" \
  --max-chunks 30
```

## Report

Show: counts from each stage (candidates, durable, chunks), the dispatch plan path,
and the three execution options for stage 4 (Claude subagents / local LLM / manual triage).
Do NOT run the stage-4 LLM calls — that's the user's choice.
