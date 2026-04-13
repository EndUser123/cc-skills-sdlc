---
name: adversarial-agent-prompts
description: Dispatch prompts for 5 phase-1 adversarial agents + critic, with idempotency checks and mandatory Write-tool enforcement
contract: response text must contain ONLY the file path
---

# Adversarial Agent Dispatch Prompts

Reference for Step 4b: Dispatch the 5 phase-1 agents in one parallel batch, then dispatch the critic in a second phase.

## Compaction Resilience -- Idempotent Agents

Each agent prompt prepends a pre-flight check: if its output file already exists and is non-empty, skip execution and return the path immediately. This means:
- Agents that completed before compaction return existing file path instantly (no re-run)
- Agents that didn't run execute normally
- After compaction, re-dispatch the same 6 agents with the same prompts; already-complete agents skip themselves
- The orchestrator only needs to check which output files exist to know what's done

## Agent Prompts

```python
# Phase 1: dispatch the 5 non-critic agents in one batch.
# Phase 2: dispatch the critic after the phase-1 findings exist.
# Each writes findings to file and returns ONLY the path.
# Each agent checks: if output file exists, skip and return path immediately.
#
# MANDATORY SUBSTITUTIONS BEFORE DISPATCH:
# - <plan_path>     = exact absolute plan path
# - <findings_dir>  = exact absolute per-plan/per-terminal adversarial directory
# - <findings_path> = exact absolute findings file path for the current agent
#
# Never dispatch a prompt containing the old sanitized-plan token. That means
# the orchestrator skipped path resolution and the agent may write to the wrong place.

Task(subagent_type="adversarial-compliance",
     description="Compliance review",
     prompt="""MANDATORY: You MUST review ONLY the plan at this exact path:
<plan_path>

Validate idempotency before running — skip if valid findings already exist:
python -c "
import sys, json, time, os
fpath = r'<findings_path>'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('plan_path') == r'<plan_path>' and age < 86400:
        print(fpath)
        sys.exit(0)
    # plan_path mismatch or file too old — delete stale file and run agent
    os.remove(fpath)
except (json.JSONDecodeError, KeyError, OSError):
    if os.path.exists(fpath):
        os.remove(fpath)
pass
sys.exit(1)
"
If the above script prints a path, return ONLY that path.

Do NOT assume or infer the plan content. Read the file at <plan_path> first.

1. Review the plan at <plan_path> for specification violations and solo-dev constraints.
   - For stateful/history/provider/multi-terminal plans, explicitly check identity model completeness, source-of-truth declarations, and unresolved implementation-shaping open questions.
2. Use the Write tool to save findings to: <findings_path>

   MANDATORY JSON SCHEMA (top-level keys must be exactly these):
   {
     "plan_path": "<plan_path>",
     "findings": [
       {
         "id": "COMP-XXX",
         "severity": "BLOCKER | HIGH | MEDIUM | LOW",
         "title": "short title",
         "description": "what is wrong and why it matters",
         "location": "file:line or plan section",
         "remediation": "specific fix required"
       }
     ],
     "overall_assessment": "one-sentence summary",
     "open_questions": [],
     "handoff": {}
   }

   IMPORTANT: plan_path MUST be a top-level field, not nested. Do NOT use any other top-level key names.
3. Return ONLY: "<findings_path>" """)

Task(subagent_type="adversarial-logic",
     description="Logic review",
     prompt="""MANDATORY: You MUST review ONLY the plan at this exact path:
<plan_path>

Validate idempotency before running — skip if valid findings already exist:
python -c "
import sys, json, time, os
fpath = r'<findings_path>'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('plan_path') == r'<plan_path>' and age < 86400:
        print(fpath)
        sys.exit(0)
    # plan_path mismatch or file too old — delete stale file and run agent
    os.remove(fpath)
except (json.JSONDecodeError, KeyError, OSError):
    if os.path.exists(fpath):
        os.remove(fpath)
pass
sys.exit(1)
"
If the above script prints a path, return ONLY that path.

Do NOT assume or infer the plan content. Read the file at <plan_path> first.

1. Review the plan at <plan_path> for pure logic errors, race conditions, and off-by-one bugs.
   - For stateful/history/provider/multi-terminal plans, explicitly compare prose behavior against keys, schema snippets, and contract sections.
   - Flag contradictory ordering rules, dedupe rules, or identity semantics as logic findings.
2. Use the Write tool to save findings to: <findings_path>

   MANDATORY JSON SCHEMA (top-level keys must be exactly these):
   {
     "plan_path": "<plan_path>",
     "findings": [
       {
         "id": "L-XXX",
         "severity": "BLOCKER | HIGH | MEDIUM | LOW",
         "title": "short title",
         "description": "what is wrong and why it matters",
         "location": "file:line or plan section",
         "remediation": "specific fix required"
       }
     ],
     "overall_assessment": "one-sentence summary",
     "open_questions": [],
     "handoff": {}
   }

   IMPORTANT: plan_path MUST be a top-level field, not nested. Do NOT use any other top-level key names.
3. Return ONLY: "<findings_path>" """)

Task(subagent_type="adversarial-testing",
     description="Testing review",
     prompt="""MANDATORY: You MUST review ONLY the plan at this exact path:
<plan_path>

Validate idempotency before running — skip if valid findings already exist:
python -c "
import sys, json, time, os
fpath = r'<findings_path>'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('plan_path') == r'<plan_path>' and age < 86400:
        print(fpath)
        sys.exit(0)
    # plan_path mismatch or file too old — delete stale file and run agent
    os.remove(fpath)
except (json.JSONDecodeError, KeyError, OSError):
    if os.path.exists(fpath):
        os.remove(fpath)
pass
sys.exit(1)
"
If the above script prints a path, return ONLY that path.

Do NOT assume or infer the plan content. Read the file at <plan_path> first.

1. Review the plan at <plan_path> for coverage gaps and brittle tests.
2. Use the Write tool to save findings to: <findings_path>

   MANDATORY JSON SCHEMA -- top-level keys MUST be exactly these:
   {
     "plan_path": "<plan_path>",
     "findings": [
       {
         "id": "TEST-XXX",
         "severity": "BLOCKER | HIGH | MEDIUM | LOW",
         "title": "short title",
         "description": "what is wrong and why it matters",
         "location": "file:line or plan section",
         "remediation": "specific fix required"
       }
     ],
     "overall_assessment": "one-sentence summary",
     "open_questions": [],
     "handoff": {}
   }

   IMPORTANT: plan_path MUST be a top-level field, not nested. Do NOT use any other top-level key names.
3. Return ONLY: "<findings_path>" """)

Task(subagent_type="adversarial-security",
     description="Security review",
     prompt="""MANDATORY: You MUST review ONLY the plan at this exact path:
<plan_path>

Validate idempotency before running — skip if valid findings already exist:
python -c "
import sys, json, time, os
fpath = r'<findings_path>'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('plan_path') == r'<plan_path>' and age < 86400:
        print(fpath)
        sys.exit(0)
    # plan_path mismatch or file too old — delete stale file and run agent
    os.remove(fpath)
except (json.JSONDecodeError, KeyError, OSError):
    if os.path.exists(fpath):
        os.remove(fpath)
pass
sys.exit(1)
"
If the above script prints a path, return ONLY that path.

Do NOT assume or infer the plan content. Read the file at <plan_path> first.

1. Review the plan at <plan_path> for data exposure and access control issues.
2. Use the Write tool to save findings to: <findings_path>

   MANDATORY JSON SCHEMA -- top-level keys MUST be exactly these:
   {
     "plan_path": "<plan_path>",
     "findings": [
       {
         "id": "SEC-XXX",
         "severity": "BLOCKER | HIGH | MEDIUM | LOW",
         "title": "short title",
         "description": "what is wrong and why it matters",
         "location": "file:line or plan section",
         "remediation": "specific fix required"
       }
     ],
     "overall_assessment": "one-sentence summary",
     "open_questions": [],
     "handoff": {}
   }

   IMPORTANT: plan_path MUST be a top-level field, not nested. Do NOT use any other top-level key names.
3. Return ONLY: "<findings_path>" """)

Task(subagent_type="adversarial-failure-modes",
     description="Failure modes review",
     prompt="""MANDATORY: You MUST review ONLY the plan at this exact path:
<plan_path>

Validate idempotency before running — skip if valid findings already exist:
python -c "
import sys, json, time, os
fpath = r'<findings_path>'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('plan_path') == r'<plan_path>' and age < 86400:
        print(fpath)
        sys.exit(0)
    # plan_path mismatch or file too old — delete stale file and run agent
    os.remove(fpath)
except (json.JSONDecodeError, KeyError, OSError):
    if os.path.exists(fpath):
        os.remove(fpath)
pass
sys.exit(1)
"
If the above script prints a path, return ONLY that path.

Do NOT assume or infer the plan content. Read the file at <plan_path> first.

1. Review the plan at <plan_path> for domain-aware failure mode discovery.
   - For stateful/history/provider/multi-terminal plans, explicitly check stale-data invalidation, replay triggers, watermark advancement, and cache/archive authority boundaries.
   - Deferred freshness semantics count as blocker/high findings when the plan claims stale-data immunity or durable retention.
2. Use the Write tool to save findings to: <findings_path>

   MANDATORY JSON SCHEMA -- top-level keys MUST be exactly these:
   {
     "plan_path": "<plan_path>",
     "findings": [
       {
         "id": "F-XXX",
         "severity": "BLOCKER | HIGH | MEDIUM | LOW",
         "title": "short title",
         "description": "what is wrong and why it matters",
         "location": "file:line or plan section",
         "remediation": "specific fix required"
       }
     ],
     "overall_assessment": "one-sentence summary",
     "open_questions": [],
     "handoff": {}
   }

   IMPORTANT: plan_path MUST be a top-level field, not nested. Do NOT use any other top-level key names.
3. Return ONLY: "<findings_path>" """)

Task(subagent_type="adversarial-critic",
     description="Critic review",
     prompt="""MANDATORY: You MUST analyze findings from this specific plan review:
<plan_path>

Validate idempotency before running — skip if valid findings already exist:
python -c "
import sys, json, time, os
fpath = r'<findings_path>'
if not os.path.exists(fpath):
    sys.exit(1)
try:
    data = json.loads(open(fpath, encoding='utf-8').read())
    age = time.time() - os.path.getmtime(fpath)
    if data.get('plan_path') == r'<plan_path>' and age < 86400:
        print(fpath)
        sys.exit(0)
    # plan_path mismatch or file too old — delete stale file and run agent
    os.remove(fpath)
except (json.JSONDecodeError, KeyError, OSError):
    if os.path.exists(fpath):
        os.remove(fpath)
pass
sys.exit(1)
"
If the above script prints a path, return ONLY that path.

1. Read all adversarial findings files from: <findings_dir>
   - SKIP any file whose plan_path field does not match <plan_path>
2. Perform meta-analysis of consensus, blind spots, calibration for the plan at <plan_path>
   - Specifically look for consensus gaps around identity model, ordering, dedupe, invalidation, event source-of-truth, and isolation boundaries.
3. Use the Write tool to save findings to: <findings_path>

   MANDATORY JSON SCHEMA -- top-level keys MUST be exactly these:
   {
     "plan_path": "<plan_path>",
     "review_metadata": {
       "skill": "adversarial-critic",
       "review_type": "meta-analysis",
       "agents_analyzed": ["compliance", "logic", "testing", "security", "failure-modes"],
       "total_findings": 0,
       "consensus_count": 0,
       "blind_spot_count": 0
     },
     "meta_findings": [
       {
         "meta_type": "consensus | blind_spot | bias | contradiction | quality_calibration",
         "severity": "CRITICAL | HIGH | MEDIUM | LOW",
         "title": "short title",
         "description": "what was found across agents",
         "location": "file:line or plan section",
         "why_missed": "why this wasn't caught by individual agents",
         "recommendation": "specific fix required"
       }
     ],
     "summary": {
       "blockers": [],
       "critical_issues": [],
       "high_priority_issues": []
     }
   }

   IMPORTANT: plan_path MUST be a top-level field, not nested. Do NOT use any other top-level key names.
4. Return ONLY: "<findings_path>" """)
```

## Rate Limit Retry Protocol (Step 4b-retry)

After agents return from Step 4b, Claude MUST check which agents produced valid findings files. Rate limits (429 errors) are temporary -- retry automatically.

```python
# Retry check: After the expected agents for the current phase return, verify findings files exist
# For each agent, check: does <findings_dir>/{agent}-findings.json exist and contain valid JSON with matching plan_path?

import json, os, time

ADVERSARIAL_DIR = r'<findings_dir>'
PLAN_PATH = r'<plan_path>'

expected_agents = [
    'compliance', 'logic', 'testing',
    'security', 'failure-modes', 'critic'
]

def check_findings():
    """Return list of agents that did NOT produce valid findings."""
    missing = []
    for agent in expected_agents:
        fpath = os.path.join(ADVERSARIAL_DIR, f'{agent}-findings.json')
        if not os.path.exists(fpath):
            missing.append(agent)
            continue
        try:
            data = json.loads(open(fpath, encoding='utf-8').read())
            if data.get('plan_path') != PLAN_PATH:
                missing.append(agent)  # Wrong plan — stale file
        except (json.JSONDecodeError, OSError):
            missing.append(agent)  # Corrupt file
    return missing

missing = check_findings()
if missing:
    print(f"RETRY_NEEDED: {len(missing)} agents need retry: {missing}")
    # Re-dispatch ONLY the missing agents (same prompts, same plan_path)
    # The idempotency check in each prompt ensures completed agents skip themselves
else:
    print("ALL_COMPLETE: All expected adversarial reviews produced findings")
```

### Retry Procedure

1. **Check**: After the current phase returns, run the check script above
2. **Retry 1**: Re-dispatch ONLY the failed agents (same prompts, same `plan_path`). The idempotency pre-flight check ensures completed agents skip instantly.
3. **Retry 2**: If agents still fail after Retry 1, wait briefly and re-dispatch failed agents one more time
4. **Give up gracefully**: After 3 total attempts (initial + 2 retries), proceed with whatever findings exist. Write the review summary noting which agents failed: "Rate-limited after 3 attempts: [agent list]"
5. **Never block indefinitely**: Maximum 3 total attempts per agent. Do NOT loop forever.

**Why this works**: The idempotency pre-flight check (already in every agent prompt) means re-dispatching the current phase is safe -- completed agents return their existing file path instantly. You can re-dispatch the whole phase for simplicity, or just the failed agents for efficiency.

**Retry dispatch pattern**: Use the exact same prompts from Step 4b. No modifications needed -- the idempotency check handles deduplication.
