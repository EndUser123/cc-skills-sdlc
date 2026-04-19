# Domain-Specific Guidelines

## Severity Examples

| Severity     | Business Logic Examples                                                                                           |
| ------------ | ----------------------------------------------------------------------------------------------------------------- |
| **CRITICAL** | Financial calculation errors (float for money), data corruption, regulatory violations, invalid state transitions |
| **HIGH**     | Missing required validation, incomplete workflows, unhandled critical edge cases                                  |
| **MEDIUM**   | Suboptimal UX, missing error context, non-critical validation gaps                                                |
| **LOW**      | Code organization, additional test coverage, documentation                                                        |

---

## Non-Negotiables

| Requirement                                | Why Non-Negotiable                        |
| ------------------------------------------ | ----------------------------------------- |
| **Mental Execution section REQUIRED**      | Core value of this reviewer               |
| **Financial calculations use Decimal**     | Float causes money rounding errors        |
| **State transitions explicitly validated** | State machines cannot allow invalid paths |
| **All 8 output sections included**         | Schema compliance required                |

---

## Anti-Rationalization

| Rationalization                       | Required Action                                       |
| ------------------------------------- | ----------------------------------------------------- |
| "Business rules documented elsewhere" | **Verify implementation actually matches docs**       |
| "Edge cases unlikely"                 | **Check ALL: null, zero, negative, empty, boundary**  |
| "Mental execution can be brief"       | **Include detailed analysis with concrete scenarios** |
| "Tests cover business logic"          | **Independently verify through mental execution**     |
| "Requirements are self-evident"       | **Verify against actual requirements doc**            |
