# Phase 4: PLAN - Detailed Instructions

## Plan Structure (7 sections)
1. **Overview** - What we're building and why (2-3 sentences)
2. **Architecture** - Module structure, key components, interfaces (single solution, not multiple options)
3. **Data Flow** - How data moves through the system (diagram + description)
4. **Error Handling** - Error paths and recovery strategies
5. **Test Strategy** - Test scenarios (happy path, edge cases, integration)
6. **Standards Compliance** - Language-specific standards (Python: `//p`, TS: `/code-typescript`)
7. **Ramifications** - Impact on existing code, migrations, backwards compatibility

## Pre-mortem Step (5 minutes, before implementation)
1. Imagine: "It's 6 months from now and this feature failed. Why?"
2. List top 3 failure modes (e.g., "deadlock under load", "data corruption", "memory leak")
3. For each failure mode:
   - Identify root cause
   - Document preventive action (test case, guardrail, validation)
   - Add to TRACE scenarios and test strategy
4. Observability planning:
   - What metrics/logs will show if this is working? (error rate, latency, throughput)
   - What alert would detect the failure mode? (error spike, stuck process, data drift)
   - Where will we look first during diagnosis? (logs, traces, metrics, db state)
   - Add observability requirements to plan.md if needed

**Note:** Pre-mortem identifies potential failure modes -> TRACE phase verifies they don't exist in the actual implementation.

## Step 4.5: Execution Path Verification (MANDATORY for non-linear flows)

**Purpose**: Verify planned execution paths are reachable and complete before implementation begins.

**When to run** (auto-detected):
- **Mandatory**: Multi-turn lifecycles, state machines, hooks, handlers with control flow branches
- **Optional**: Complex conditional logic (> 3 branches), error handling with early exits
- **Skipped**: Linear single-path functions (< 20 lines), pure data transformations

**Verification process** (for non-linear flows):

1. **TRACE main() execution flow** (or equivalent entry point)
   - Walk through the function line by line
   - Track control flow branches (if/else, try/except, early returns)
   - Note state changes at each step

2. **Check reachability** (each branch must be executable)
   - Verify no `sys.exit()` or `return` statements skip critical logic
   - Confirm all branches can execute in expected sequence
   - Check that cleanup/verification steps aren't blocked by early exits

3. **Check multi-turn lifecycle** (if applicable)
   - Simulate Turn 1 (e.g., injection) -> Turn 2 (e.g., validation)
   - Verify state persists between turns (flags, files, context)
   - Confirm cleanup happens AFTER all turns complete

4. **Check marker/context conflicts** (for hooks, validation systems)
   - List all marker strings used for detection
   - Check against injected context, output format, error messages
   - Verify markers don't appear in places that cause false positives

5. **Document findings** (if issues found)
   - List each issue with: type, location, impact, fix recommendation
   - Update plan.md to address findings
   - Re-verify until all checks pass

**What this catches** (real examples from GAV Phase 2):
- Unreachable validation code (lifecycle bug: `sys.exit(0)` before validation call)
- False positive marker ("blocked" appeared in injected context itself)
- Missing state persistence (artifact deleted before validation could read it)
- Early exit skipping cleanup (return before resource release)

**Verification is PASS when**:
- All branches are reachable and execute in correct sequence, OR
- Flow is linear (verification skipped), OR
- Issues found, fixed in plan, re-verified

**Duration**: 2-5 minutes for non-linear flows (saves 10-30 minutes of rework)

## Step 4.6: Pattern Validation (REQUIRED for detector modules)

For all modules with word-set or regex-based detection patterns:

1. Copy `templates/pattern_validation.md` from `/code` skill
2. Complete for EACH detection pattern:
   - Positive examples (3+ that should trigger)
   - Negative examples (3+ that should NOT trigger)
   - Edge cases (empty, whitespace, malformed)
   - Pattern soundness analysis
3. Attach completed template to plan.md as Appendix A
4. Review with adversarial testing before implementation

**Purpose**: Prevents false positive bugs from bare/overly-broad patterns.

## Step 4.7: Graph-of-Thought (GoT) Enhancement

**Purpose**: Apply Graph-of-Thought reasoning to explore architecture-level relationships in plan.md.

**When**: After plan structure is complete, before proceeding to TDD phase.

**Opt-out**: Use `--no-got` flag to disable GoT enhancement.

**Execution**:

1. **Extract nodes** from plan.md Architecture section:
   ```python
   from utils.got_planner import GotPlanner
   planner = GotPlanner(plan_document)
   nodes = planner.extract_nodes()
   ```

   Nodes extracted:
   - **Constraints**: Requirements like "Must use JWT tokens", "API response time < 200ms"
   - **Ideas**: Implementation approaches like "Use Redis for token caching", "Implement OAuth 2.0"
   - **Risks**: Potential issues like "JWT secret key management is critical"

2. **Analyze edges** between nodes:
   ```python
   from utils.got_planner import GotEdgeAnalyzer
   edge_analyzer = GotEdgeAnalyzer(nodes)
   edges = edge_analyzer.analyze_edges()
   ```

   Edge types: **Supports**, **Contradicts**, **Unrelated**

3. **Detect cycles** in the graph:
   ```python
   cycles = edge_analyzer.detect_cycles()
   ```

4. **Document findings** in plan.md:
   - Add "GoT Analysis" section after "Architecture"
   - List extracted nodes with categories, edge relationships, cycles
   - Note architectural insights

**What this catches**:
- Hidden constraint conflicts
- Circular dependencies in ideas
- Unaddressed risks with no mitigation idea

**Duration**: 2-5 minutes for typical plans (extracts 5-15 nodes, 10-30 edges)
