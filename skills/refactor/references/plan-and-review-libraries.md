# Plan and Review Libraries

**Location**: `lib/refactor_plan.py`, `lib/plan_review.py`

**Purpose**: Create and review refactoring plans before any code changes.

## refactor_plan.py

**Functions**:
```python
# Create structured plan from findings
plan = create_refactor_plan(
    findings=[...],
    target_path="src/",
    session_id="abc123"
)

# Convert plan to markdown for display
markdown = plan_to_markdown(plan)

# Save plan to JSON file
plan_file = save_plan(plan, output_dir=Path(".evidence/refactor/"))
```

**Plan structure**:
- `metadata`: Created timestamp, target path, session ID
- `overview`: Total findings, priority breakdown, effort estimate, risk level
- `changes_by_priority`: Changes grouped by P0/P1/P2/P3 with risk analysis and rollback strategies
- `execution_order`: Step-by-step execution plan with reasoning
- `validation_strategy`: Test approach, rollback trigger, validation tools

## plan_review.py

**Functions**:
```python
# Adversarial review of plan
review = adversarial_review_plan(plan)

# Convert review to markdown for display
markdown = review_to_markdown(review)
```

**Review findings**:
- `findings`: Specific concerns about individual changes (regex risk, missing rollback, etc.)
- `recommendations`: Actionable suggestions (use AST instead of regex, split into smaller sessions, etc.)
- `risk_factors`: Overall risk assessment (batch operations, effort vs risk mismatch, etc.)
- `overall_assessment`: APPROVED / CONDITIONAL / ADVISED

**What the review checks**:
- **RISK-001**: Regex changes marked as LOW risk (regex can introduce syntax errors)
- **ROLLBACK-001**: Insufficient rollback strategy
- **COMPLEX-001**: Batch operations (higher risk, recommend splitting)
- **IMPORT-001**: Import changes (can break module loading)
- **EFFORT-001**: Large refactorings (>8 hours, recommend splitting)
- **PRIORITY-001**: Too many P0 issues (fix bugs first, then refactor)

**This would have prevented the 8 syntax errors**:
The plan review would have flagged:
- "Batch consolidation using regex" → COMPLEX-001
- "Regex changes marked as LOW risk" → RISK-001
- Recommendation: "Use AST-based refactoring (LibCST) instead of regex"
