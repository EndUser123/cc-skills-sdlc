# Agent Enhancement Specifications

## Complexity Triage (Agent 2 Enhancement)

**Agent 2: `adversarial-performance` — DRY/Simplicity focus** includes:

**Complexity triage process** (Priority 2 Enhancement):
For each file in target scope:
1. Calculate cyclomatic complexity (McCabe metric)
2. Flag files with CC ≥ 15 as HIGH_COMPLEXITY
3. Flag files with CC ≥ 20 as VERY_HIGH_COMPLEXITY
4. Recommend enhanced safety measures for high-complexity files:
   - Extra characterization tests
   - Smaller, incremental changes
   - Manual review before automated refactoring

**Output format:**
```
COMPLEXITY-001: HIGH_COMPLEXITY
File: src/complex_module.py
Cyclomatic Complexity: 18
Recommendation: Use smaller incremental changes, extra characterization tests
Priority: HIGH (complexity increases refactoring risk)
```

**Constitutional filter compliance:**
- Complexity detection is appropriate for professional quality standards
- Must not suggest "scalability requirements" or enterprise patterns
- Focus on code safety, not premature optimization

## Import Hygiene (Agent 3 Enhancement)

**Agent 3: `adversarial-quality` — Conventions focus** includes:

**Import hygiene checks** (Priority 2 Enhancement):
1. **Unused imports:** Detect imported modules never referenced in code
2. **Circular dependencies:** Detect modules that import each other
3. **Dead code:** Detect unused functions, classes, variables
4. **Import ordering:** Verify PEP 8 compliance (stdlib, third-party, local)

**Allowed patterns** (false positive prevention):
- `from typing import TYPE_CHECKING` (used for type hints only)
- `if TYPE_CHECKING:` blocks (type checking imports)
- `# noqa` comments (explicitly allowed)
- `# type: ignore` comments (explicitly allowed)

**Output format:**
```
IMPORT-001: Unused import detected
File: src/module.py:5
Import: `import os` (never referenced)
Action: Remove unused import
Impact: Cleaner code, faster imports
```

```
IMPORT-002: Circular dependency detected
Files: src/auth.py → src/user.py → src/auth.py
Action: Restructure to break cycle
Impact: Prevents import errors, improves testability
```

**Constitutional filter compliance:**
- Import hygiene is appropriate for code quality standards
- Must not suggest "service extraction" to fix circular dependencies
- Focus on local restructuring, not architectural changes
