# Code Review Management (Request & Reception)

## 1. Requesting Review
**Core Principle:** Review early, review often. Preserving your own context by offloading evaluation to a specialized reviewer subagent.

### When to Request
- **Mandatory:** After each task (Subagent-driven) or after completing a major feature.
- **Trigger:** Before merging to `main`.
- **Checkpoint:** When stuck or before refactoring (baseline check).

### Execution Pattern
1. **Identify SHAs:** `git rev-parse HEAD~1` (Base) vs `git rev-parse HEAD` (Head).
2. **Dispatch:** Use the `Task` tool with the `code-reviewer` agent type.
3. **Context:** Provide the plan/requirements and the implementation summary. Do NOT provide your entire session history.

---

## 2. Receiving Review
**Core Principle:** Technical rigor over social comfort. External feedback = suggestions to evaluate, not orders to follow.

### The Reception Protocol
1. **READ**: Complete feedback without reacting.
2. **UNDERSTAND**: Restate requirements (or ask) if unclear.
3. **VERIFY**: Check against codebase reality.
4. **EVALUATE**: Is it technically sound for THIS stack?
5. **RESPOND**: Technical acknowledgment or reasoned pushback.
6. **IMPLEMENT**: One item at a time, testing each.

### Forbidden Responses (Performative)
- **NO**: "You're absolutely right!", "Great point!", "Excellent feedback!".
- **YES**: Restate the technical requirement, ask clarifying questions, or push back with reasoning.

### Pushback Criteria
- Suggestion breaks existing functionality.
- Reviewer lacks full context.
- Violates **YAGNI** (unused "professional" features).
- Technically incorrect for the environment.
- Conflicts with prior architectural decisions.

---

## 3. Implementation Order
1. **Blocking Issues**: Breaks, Security, Data Integrity.
2. **Simple Fixes**: Typos, Imports, Formatting.
3. **Complex Fixes**: Logic, Refactoring.
4. **Verification**: Individual tests + regression suite.
