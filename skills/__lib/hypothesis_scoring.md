# Hypothesis Scoring and Ranking

## Scoring Formula
**Score = Reproducibility(0.3) x Recency(0.2) x Impact(0.5)**

| Factor | Weight | Criteria |
|--------|--------|----------|
| **Reproducibility** | 0.3 | 1.0=Can reproduce, 0.5=Sometimes, 0.1=Cannot |
| **Recency** | 0.2 | 1.0=Changed today, 0.5=This week, 0.1=Old |
| **Impact** | 0.5 | 1.0=Explains ALL symptoms, 0.5=Some, 0.1=Weak |

## Ranking Protocol
1. Generate 3-7 competing hypotheses.
2. Score each using the formula.
3. Prune unlikely hypotheses (Score < 0.3).
4. Rank by score (highest first).
5. Test in order until root cause is confirmed.

## Disconfirmation Format
For each hypothesis, define the **falsifier**: "If X happens, then Hypothesis Y is false."
Rule out before confirming.
