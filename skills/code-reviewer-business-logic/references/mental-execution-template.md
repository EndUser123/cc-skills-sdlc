# Mental Execution Template

## Template

```markdown
### Mental Execution: [FunctionName]

**Scenario:** [Concrete business scenario with actual values]

**Initial State:**

- Variable X = [value]
- Database contains: [state]

**Execution Trace:**
Line 45: `if (amount > 0)` -> amount = 100, TRUE
Line 46: `balance -= amount` -> 500 -> 400
Line 47: `saveBalance(balance)` -> DB updated

**Final State:**

- balance = 400 (correct)
- Database: balance = 400 (consistent)

**Verdict:** Logic correct | Issue found
```

## How to Use

1. Pick a concrete business scenario with real data values
2. Trace the function line-by-line, tracking variable states at each step
3. Follow function calls into other functions when needed
4. Test boundary conditions: null, 0, negative, empty, max
5. Compare final state against expected business outcome
