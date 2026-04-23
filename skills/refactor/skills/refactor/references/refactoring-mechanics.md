# Named Refactoring Mechanics

Mechanical recipes for each code smell category. Each recipe specifies the exact steps to safely apply the transformation without changing behavior.

## Bloaters

### Long Method → Extract Method

1. Identify a coherent block within the method (often delimited by a comment)
2. Copy the block to a new function
3. Pass local variables as parameters; assign return values back
4. Replace the original block with a call to the new function
5. Run tests — behavior must be identical
6. Name the function after what the block does (not how it does it)

Heuristic: If you need a comment to explain a block, extract it and use the comment text as the function name.

### Large Class → Extract Class

1. Identify a subset of fields and methods that serve one responsibility
2. Create a new class with those fields and methods
3. In the original class, hold a reference to the new class
4. Delegate calls from the original class to the new class
5. Run tests — behavior must be identical
6. Remove the delegation gradually by updating callers to use the new class directly

Heuristic: If a class has methods that use disjoint subsets of fields, it does two things.

### Long Parameter List → Introduce Parameter Object

1. Identify a group of parameters that naturally belong together (e.g., `start_date, end_date`)
2. Create a class/NamedTuple/dataclass with those fields
3. Replace the parameter group with the new object in the function signature
4. Update all callers to construct the object
5. Run tests — behavior must be identical
6. Move related validation logic into the parameter object

Heuristic: 4+ parameters, or parameters that always appear together across multiple functions.

### Primitive Obsession → Replace Primitive with Object

1. Identify a raw value (string, int, float) that has domain meaning (e.g., email, currency, temperature)
2. Create a class that wraps the value
3. Add validation to the constructor (e.g., email format check)
4. Add domain behavior as methods (e.g., `Money.add()`, `EmailAddress.domain()`)
5. Replace raw usage with the new type
6. Run tests — behavior must be identical

## OO Abusers

### Switch on Type Code → Replace Conditional with Polymorphism

1. Create subclasses for each case in the switch/if-elif chain
2. Move the conditional logic into an overridden method on each subclass
3. Replace the switch with a method call on the base class
4. Factory method constructs the correct subclass based on type code
5. Run tests — behavior must be identical

Heuristic: If a switch statement appears more than once on the same variable, the polymorphism payoff is immediate.

### Temporary Fields → Extract Class

1. Identify fields that are only set in certain states
2. Create a new class holding those fields plus the methods that use them
3. Replace the fields with a reference to the new class (or None)
4. Run tests — behavior must be identical

### Refused Bequest → Replace Inheritance with Delegation

1. Create a field holding an instance of the parent class
2. Delegate methods that the subclass actually uses to the parent instance
3. Remove the inheritance relationship
4. Run tests — behavior must be identical

Heuristic: If a subclass overrides most parent methods with empty bodies or raises NotImplementedError, inheritance is wrong.

## Change Preventers

### Divergent Change → Extract Class

(See Large Class → Extract Class above)

Key signal: One class changes for multiple unrelated reasons. Split along the axis of change — each class should change for one reason.

### Shotgun Surgery → Move Method/Field

1. Identify the class that should own the method/field (where is its data?)
2. Copy the method to the target class
3. Create a delegating call from the original class
4. Update callers one at a time
5. Remove the delegation once all callers target the new location
6. Run tests after each caller update

Key signal: One conceptual change requires edits across 3+ files. Consolidate by moving responsibilities to where the data lives.

### Parallel Inheritance Hierarchies → Collapse

1. Make one hierarchy refer to instances of the other (composition)
2. Move methods from one hierarchy into the other
3. Remove the now-empty hierarchy
4. Run tests — behavior must be identical

## Couplers

### Feature Envy → Move Method

(See Shotgun Surgery → Move Method above)

Key signal: A method uses more fields/methods of another class than its own. It belongs there.

### Inappropriate Intimacy → Hide Delegate / Extract Interface

1. If class A accesses B's internals directly: add a method on B that encapsulates the access
2. If bidirectional dependencies exist: extract an interface to break the cycle
3. Run tests — behavior must be identical

### Message Chains → Hide Delegate

1. Replace `a.getB().getC().doThing()` with `a.doThingViaBAndC()`
2. The new method on `a` handles the chain internally
3. Run tests — behavior must be identical

Heuristic: Law of Demeter violation. A method should only talk to its immediate friends, not friends of friends.

## Dispensables

### Dead Code → Delete

1. Verify zero callers via `Grep` for the symbol name
2. Delete the function/class/variable
3. Run tests — if they pass, the code was truly dead
4. If tests fail, the code had a hidden caller — restore and investigate

### Speculative Generality → Inline / Remove

1. Identify unused parameters, abstract base classes with one implementation, or "for future use" code
2. Remove unused parameters from function signatures
3. Inline single-implementation abstract classes
4. Delete commented-out code and TODO markers
5. Run tests — behavior must be identical

### Lazy Class → Inline Class

1. Move all methods and fields into the calling class
2. Remove the now-empty class
3. Run tests — behavior must be identical

Heuristic: A class that exists only to hold two fields and has no behavior. Use a NamedTuple or dataclass inline instead.

## Debt Types

| Type | Description | Examples |
|------|-------------|----------|
| `design_debt` | Architecture issues | Coupling, missing abstractions, boundary violations |
| `code_debt` | Implementation issues | Duplication, complexity, dead code, naming |
| `test_debt` | Test quality issues | Missing tests, brittle tests, uncovered edge cases |
| `documentation_debt` | Documentation issues | Stale docs, missing docstrings, misleading comments |
| `migration_debt` | Structural issues | Old import paths, stale re-exports, callers not yet migrated to new module paths |

## Safety Rules

1. **One transformation per commit** — never combine two refactorings
2. **Tests pass after each step** — if they don't, revert and try a smaller step
3. **AST over regex** — use `rope`, `LibCST`, or `ast` module for automated refactorings (see `ast-refactoring.md`)
4. **Verify before claiming** — read the actual file at the reported line before acting on a finding
