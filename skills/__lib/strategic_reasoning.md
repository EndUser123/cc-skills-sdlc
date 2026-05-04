# Strategic Reasoning Patterns

## GoT (Graph-of-Thought)
Used for constraint analysis when competing hypotheses have conflicting dependencies or hidden contradictions.
- **Trigger**: Multiple leads with complex "if X then Y" logic.
- **Action**: Map dependencies as a graph, identify bottlenecks or mutually exclusive states.

## Strategic Questioning
Blind-spot detection before converging on a final decision.
- **Trigger**: All nontrivial architectural or root-cause decisions.
- **Action**: Run an internal "blind-spot check" before stating a final conclusion.

## Technology Fit
Evaluate if a tool or pattern matches the workspace's architectural pillars.
- **Trigger**: Introducing new libraries or design patterns.
- **Action**: Compare against `architectural_pillars.yaml`.
