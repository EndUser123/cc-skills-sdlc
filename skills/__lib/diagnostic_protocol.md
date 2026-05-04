# Structured Diagnostic Protocol

## Hypotheses Template
Every investigation MUST list at least 3 hypotheses upfront.

```markdown
## Diagnostic Investigation

**Issue**: [brief problem description]

**Hypotheses**:
H1: [description]
H2: [description]
H3: [description]

**Test Results**:
H1: Test `[command]` → Result `[output]` → RULED OUT/CONFIRMED
H2: Test `[command]` → Result `[output]` → RULED OUT/CONFIRMED
H3: Test `[command]` → Result `[output]` → RULED OUT/CONFIRMED

**Conclusion**: H[confirmed] is the root cause
**Next Step**: [proposed fix]
```

## Enforcement Rules
- **3+ Hypotheses**: Minimum 3 listed before any testing begins.
- **Evidence-Based**: Each hypothesis must have a test command and actual output.
- **Mutual Exclusivity**: Mark as RULED OUT or CONFIRMED.
- **Scientific Method**: Conclusion only after testing. No "probably" or "likely" without data.

## Prohibited Behaviors
- Jumping to a solution before listing hypotheses.
- Testing only one hypothesis.
- Skipping the diagnostic path documentation.
- Accepting the first plausible explanation without ruling out others.
