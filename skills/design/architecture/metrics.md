# /arch Metrics

## Files

- `architecture/logs/decisions.jsonl` – one object per /arch invocation
- `architecture/logs/candidates.jsonl` – one object per candidate (VS + judge)

## Key Metrics

### 1. Invariant Protection
- **Source**: `judge.any_candidate_invariant_violation`, `judge.recommended_would_violate_without_judge`
- **Goal**: Recommended decisions never violate critical invariants
- **Tracking**: Percentage of decisions where judge catches violations

### 2. Option Diversity
- **Lens diversity**: Count distinct `vs.lens_survivors` per decision
- **Structural diversity**: Compute min/mean Jaccard distance on `vs.changes` from candidates.jsonl
- **Goal**: Most decisions have ≥2 distinct lenses represented

### 3. Tail Exploration
- **Fraction** of decisions where any survivor has `vs.is_tail == true`
- **Goal**: Non-zero but not dominant; some "interesting" options without flooding

### 4. Judge Vetoes
- **Rate** of `judge.all_candidates_rejected == true`
- **Goal**: Low veto rate indicates good VS conditioning

### 5. Graph / KG Utilization
- **Coverage**: Count unique `context.graph_nodes_considered` vs neighborhood size
- **Goal**: System consistently references the right neighborhood

### 6. Adoption
- **Distribution** of `user_outcome.adoption` (followed/modified/discarded)
- **Goal**: Raise "followed or lightly modified" share

## Logging

- Append one JSON object per line
- Timestamps in ISO 8601 UTC
- IDs stable and unique per decision

## Schema

### decisions.jsonl (per /arch invocation)

```json
{
  "timestamp": "2026-03-16T15:32:10Z",
  "id": "2026-03-16T15-32-10Z_improve-memory-system",
  "query": "improve memory system",
  "pattern": "pattern.improve_system",
  "high_stakes": false,
  "templates": {
    "primary": "skill.arch.fast",
    "chained": ["skill.arch.python"]
  },
  "context": {
    "graph_nodes_considered": ["comp.routing", "comp.persistence", "inv.multi_terminal_isolation"],
    "precedent_count": 4,
    "cks_used": true
  },
  "vs": {
    "k_generated": 4,
    "k_survivors": 3,
    "lens_survivors": ["lens.value_optimization", "lens.systems_thinking", "lens.multi_terminal"],
    "has_tail_candidate": true
  },
  "judge": {
    "any_candidate_invariant_violation": true,
    "recommended_would_violate_without_judge": false,
    "all_candidates_rejected": false
  },
  "diversity": {
    "min_structural_distance": 0.4,
    "mean_structural_distance": 0.6
  },
  "persistence": {
    "saved": true,
    "filepath": "arch_decisions/2026-03-16_fast_improve-memory-system.md",
    "cks_ingest_attempted": true,
    "cks_ingest_ok": true
  },
  "user_outcome": {
    "adoption": "followed",
    "notes": "Used option B with minor tweaks"
  }
}
```

### candidates.jsonl (per candidate, optional)

```json
{
  "decision_id": "2026-03-16T15-32-10Z_improve-memory-system",
  "candidate_id": "A",
  "vs": {
    "probability": 0.55,
    "lens": "lens.value_optimization",
    "changes": ["comp.routing", "comp.persistence"],
    "is_tail": false
  },
  "critic": {
    "invariants_ok": true,
    "violated_invariants": [],
    "risk_score": 0.25,
    "complexity_score": 0.4
  },
  "selection": {
    "survivor": true,
    "recommended": false
  }
}
```

## Usage

Metrics are logged automatically by the /arch persistence layer. Use these to:

1. Track decision quality over time
2. Identify patterns in VS effectiveness
3. Detect when judge is vetoing too often (needs VS adjustment)
4. Monitor adoption rates by template and pattern
