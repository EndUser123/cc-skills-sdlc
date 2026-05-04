# RCA Investigation Protocol

## Step -1: Surgical First Response (MANDATORY)
**Do this IMMEDIATELY (no questions, no theater):**
1. **Grep exact strings** from error message.
2. **Read matching files** -- all of them.
3. **State findings** immediately.

## Step 0: Pre-Flight & Research
- **Pre-Flight**: Check CKS/CHS for prior knowledge.
- **Cognitive Stack**: Classify problem type (ERROR, PERFORMANCE, etc.) and select mental models.
- **Internet Research**: Research official documentation before hypothesizing.

## Step 1: Start with Falsifiable Symptom
- Define what is wrong vs expected.
- **Step 1.5: Telemetry Discovery**: Query `pretooluse_blocks.jsonl` and `diagnostics.db` first. Enumerate logs, state, and skill invocations.
- **Step 1.6: Learned Patterns**: Check CKS for patterns from previous RCA sessions.
- **Step 1.7: Multi-Angle Search**: Use symptom-type templates (PERFORMANCE, ERROR, INTEGRATION, INTERMITTENT, SECURITY).
- **Step 1.8: Trace Execution Path**: MANDATORY for hangs/timeouts. Use logging to find exactly where it stops.
- **Step 1.85: Runtime State Inspection**: Inspect live state if failure is silent.

## Step 1.9: Hypothesis Generation (ToT)
- Generate 3-7 hypotheses.
- Score each: Reproducibility(0.3) x Recency(0.2) x Impact(0.5).
- Prune Score < 0.3. Rank and test in order.

## Step 2: Symbol-Level Trace
- Use Serena MCP for data flow tracing (`find_referencing_symbols`).
- **Step 2.5: First Divergence**: Identify the earliest mismatch point.

## Step 3-9: Principles
- Change one variable at a time.
- Prefer instrumentation over intuition.
- Minimize and reproduce.
- Validate interfaces.
- Fix structure before safeguards.
- Verify on failure path.
- Capture lesson in CKS.
