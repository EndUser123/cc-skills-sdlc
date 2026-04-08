# Evidence-Based Decision System

**Purpose:** No strong recommendation without evidence. Timeless reasoning is cached; time-sensitive facts require current research.

## Claim Type Classification

```python
# What kind of claim is this answer going to make?
claim_types = {
    "timeless_reasoning": [
        "coupling analysis", "module boundary questions", "systems thinking",
        "trade-off structure", "mental model application"
    ],
    "time_sensitive": [
        "technology recommendation", "framework / library choice", "performance claim",
        "best practice opinion", "cloud service selection", "recent pattern (post-2023)"
    ],
    "mixed": [
        "should we refactor to X architecture?", "optimize using technique Y",
        "migrate to service Z"
    ]
}

# Decision logic:
# - timeless_reasoning → proceed without research gate
# - time_sensitive → BLOCK until research done
# - mixed → escalate to deep.md (needs timeless + current evidence)
```

## Research Gate Triggers

```python
trigger_research_gate = (
    "recommend" in query.lower() or
    "should we use" in query.lower() or
    "best practice" in query.lower() or
    "pattern" in query.lower() or
    "migrate to" in query.lower() or
    "switch from X to Y" in query.lower() or
    "optimize using" in query.lower() or
    any(tech in query.lower() for tech in [
        "kubernetes", "redis", "postgres", "event sourcing", "microservices",
        "serverless", "async", "grpc", "docker", "graphql"
    ])
)

# Bypass for timeless reasoning:
timeless_only = (
    "how do I think about" in query.lower() or
    "explain coupling" in query.lower() or
    "what are the trade-offs between" in query.lower() or
    "help me structure" in query.lower() or
    "module boundary" in query.lower() or
    "systems thinking" in query.lower()
)
```

## Evidence Quality Scorecard

```yaml
evidence_scorecard:
  source_credibility:
    high: "peer-reviewed, established vendor, recognized expert"
    medium: "reliable blog, community consensus"
    low: "personal opinion, unknown source"

  recency:
    high: "< 12 months old"
    medium: "12-24 months old"
    low: "> 24 months old"

  specificity:
    high: "specific to your scale/context with benchmarks"
    medium: "general but applicable"
    low: "vague generic advice"

  consensus:
    high: "all sources agree"
    medium: "mostly aligned with some caveats"
    low: "conflicting or no consensus"

  falsifiable:
    high: "testable claim with specific metrics"
    medium: "testable with some effort"
    low: "unfalsifiable opinion"

overall_quality:
  STRONG: "3+ criteria high"
  MEDIUM: "2 criteria high"
  WEAK: "0-1 criteria high"
```

## Gate Decision Based on Quality

```python
if overall_evidence_quality == "STRONG":
    proceed_to_template = True
    confidence_level = "HIGH"

elif overall_evidence_quality == "MEDIUM":
    proceed_to_template = True
    confidence_level = "MEDIUM"
    # Downgrade recommendation strength
    # Present as: "This appears to be..." not "This is..."
    # Highlight uncertainty, propose cheap experiment

elif overall_evidence_quality == "WEAK":
    # Do NOT proceed to normal template
    # Instead: Propose spike, defer to expert, or escalate to deep
    propose_spike_or_escalate()
```

## Citation Requirements

```yaml
# Every claim in fast.md or deep.md must cite one of:
citation_types:
  cks_entry: "[CKS: {failure_or_precedent}]"
  web_source: "[Web: {source}, {date}]"
  adr_precedent: "[ADR-{number}: {decision_name}]"
  user_constraint: "[Constraint: {constraint_name}]"
  first_principles: "[First Principles reasoning]"

# Template validation:
# ✅ PASS: "Cache at query layer [CKS: Redis worked for this pattern]"
# ❌ FAIL: "Cache at query layer" (no source)
# ❌ FAIL: "This is best practice" (vague, no evidence)
```

## Evidence Aging Warnings

```python
# Use /search skill to check recency of sources
if publication_date < 12_months_ago:
    add_note = "Note: Published {months} ago. Monitor for updates."

if publication_date < 24_months_ago:
    # Use /search to verify still current
    current_verification = search_web(f"{pattern} 2025", limit=1)
    if current_verification:
        add_note = "Source is {months} old. Search confirms still current."
    else:
        add_note = "Source is {months} old. Consider search to verify still current."

if publication_date < 36_months_ago:
    recommendation_strength = "DOWNGRADE"
    add_note = "Based on older sources. Strongly recommend /search to verify current best practices."
```

## Volatile Domain Watchlist

```python
# These domains auto-trigger deeper research:
volatile_domains = [
    "AI/ML tooling",           # Changes weekly
    "Cloud services",          # New offerings constantly
    "Container orchestration", # Kubernetes ecosystem
    "Data pipelines",          # ETL/streaming rapidly evolving
    "LLM architectures",       # Fast iteration
    "Observability",           # New tools, best practices shift
    "Performance optimization", # Benchmarks change with hardware
]

if query_domain in volatile_domains:
    force_web_search = True
    escalate_if_uncertain = True
```

## Web Search Integration via /search (Fail-Loud, Allow Continue)

```python
# ONLY if CKS quality < HIGH or CKS conflicts with intuition
if evidence_quality == "LOW" or evidence_quality == "MEDIUM":
    # Use /search skill to check current best practices
    search_patterns = [
        f"{technology} best practices 2025",
        f"{technology} common pitfalls failures 2024 2025",
        f"{technology} performance benchmarks",
        f"{technology} deprecation replacement 2025",
        f"{pattern_name} anti-pattern 2025",
    ]

    selected_patterns = prioritize(search_patterns, query)

    # Use /search skill for each pattern
    search_results = []
    for pattern in selected_patterns:
        # Invoke /search via Skill tool
        result = Skill(skill="search", args=f"{pattern}")
        search_results.extend(result)

    # FAIL LOUD: If /search fails, output all 3 options and proceed with first
    if not search_results or all_empty(search_results):
        output = f"""
        SEARCH FAILED: No results found for {selected_patterns}

        Proceeding with CKS evidence only. Quality: {cks_evidence_quality}

        Options:
        1. Use CKS-based recommendation (limited evidence)
        2. Manually verify: /search "{custom_query}"
        3. Escalate to deep.md for comprehensive analysis
        """
        # Proceed with option 1 by default (CKS-only)
```

## Evidence Conflict Resolution (Simplified)

```python
# If CKS and /search results contradict each other:
if cks_result and search_result and conflict(cks_result, search_result):
    # Example:
    #   CKS: "Used Redis for caching, 80% hit rate, worked well"
    #   /search: "Redis anti-pattern in 2025, switch to in-memory"

    conflict_resolution = "ESCALATE_TO_DEEP"

    output = f"""
    ## Evidence Conflict Detected

    Your system (CKS): {cks_finding}
    Current best practice (/search): {search_finding}

    Escalating to deep.md for conflict resolution.
    Possible reasons for divergence:
    - Your use case differs from industry standard
    - Recent changes in technology (deprecation, new version)
    - Different scale / performance requirements
    """
    escalate_to_deep_md(evidence_conflict=True)
```

## Output Contract with Evidence

```python
response_contract = {
    "no_strong_claim_without_source": (
        # Every recommendation cites CKS, ADR, web, or constraint
        all(claim.has_citation() for claim in response.claims)
    ),
    "conflict_flagged": (
        # If CKS conflicts with web, explicitly noted
        if conflict_exists: conflict_explained
    ),
    "confidence_calibrated": (
        # Strength matches evidence quality
        if evidence == "MEDIUM": not_stated_as_certain
        if evidence == "LOW": proposed_experiment_instead
    ),
    "recency_acknowledged": (
        # If using web source >12 months old, flagged
        if source_old: aging_note_present
    ),
    "reversibility_clear": (
        # If this locks in a direction, costs clear
        if breaking_changes: rollback_plan_present
    ),
}
```

## How This Protects Against Stale Training Data

```yaml
problem:
  - LLM training data has cutoff (April 2024, Jan 2025, etc.)
  - Post-cutoff changes: deprecations, new best practices, performance changes

mitigation:
  1. Gate: Any tech recommendation requires research
  2. CKS first: Your actual experience > training data
  3. Web second: Catch post-cutoff changes (fail-loud, allow continue)
  4. Quality check: Don't trust weak evidence
  5. Citations: Every claim traceable to source
  6. Aging: Flag stale sources
  7. Volatility: Auto-escalate risky domains

result: "Model cannot confidently recommend something without current evidence"
```
