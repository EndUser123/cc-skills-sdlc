# Structural Migration Safety

Reference file for `/refactor` skill — Phase 0 PREFLIGHT checklist, compatibility shim patterns, boy scout rule, feature flags, static lint enforcement, and rollback playbook.

**When to use this file:**
- Import path changes (TID252, parent-module relative → absolute)
- Module relocation (file moved to new directory)
- Package boundary changes
- Any refactor that changes the public API surface of a module

**When NOT to use this file:**
- Pure code quality refactors (naming, DRY, complexity)
- Non-structural changes that don't affect import paths

---

## Compatibility Shim Pattern

A compatibility shim keeps old import paths working during migration. It is a temporary re-export layer that delegates to the new path.

```python
# old/module.py — COMPATIBILITY SHIM (delete after full migration)
from new.module import *

__all__ = ["SymbolA", "SymbolB"]  # explicit public API
```

### Shim requirements

| Requirement | Detail |
|---|---|
| **Location** | At the OLD path — the one callers currently use |
| **Content** | `from new.module import *` (or explicit re-exports) |
| **`__all__`** | Always explicit — controls what the old API surface exposes |
| **Lifetime** | Temporary — delete after all callers migrated and verified in production |
| **Tests** | Import from old path in a test — must succeed before DISCOVER proceeds |

### When shims are appropriate

- **Pure path-move**: Same API, new location → shim works
- **Semantic change**: Behavioral difference → shim not enough; use feature flags instead

### When shims are NOT appropriate

- Function signatures changed
- Return types differ
- Behavior diverges (even slightly)

In those cases, use **feature flags** (dark launch) instead — run old and new code paths side-by-side, migrate callers gradually.

---

## Boy Scout Rule

> From the moment migration begins, all NEW code must use the NEW import path.

**Enforcement:**
- ADVERSARIAL_REVIEW phase flags any file that introduces OLD path imports after shim creation
- A `ruff` custom rule (see Static Lint Enforcement below) catches violations during development

**Migration rule for callers:**
> If you touch a file that uses an OLD import path, migrate it as part of your change.

This prevents migration debt from accumulating. Every touch is a migration opportunity.

---

## Static Lint Enforcement

To prevent OLD path reintroduction, add a custom `ruff` rule or comment-based suppression in the target scope.

### Ruff check (TID252)

```bash
# Check for TID252 violations (prefer absolute over relative)
ruff check core/cks/integration/ --select=TID252
```

### Comment-based blocking

For a migration scope, add a ruff ignore directive at the top of files that must not use old paths:

```python
# ruff: noqa: TID252  # MIGRATION IN PROGRESS — use new/module not old.module
```

Alternatively, use a pyproject.toml override for the migration period:

```toml
[tool.ruff.lint.per-file-ignores]
"core/cks/integration/**" = ["TID252"]
```

---

## Feature Flags for Behavioral Changes

When migration involves behavioral changes (not just path moves), use feature flags to run both paths:

```python
import os

ENABLE_NEW_BEHAVIOR = os.getenv("NEW_BEHAVIOR", "false") == "true"

def get_items():
    if ENABLE_NEW_BEHAVIOR:
        return new_get_items()  # new implementation
    return old_get_items()       # legacy
```

**Migration phases with feature flags:**
1. Old path + old behavior (baseline)
2. Old path + new behavior (dark launch) — verify correctness
3. New path + new behavior (switchover)
4. Remove flag, delete old code

---

## Rollback Playbook

If migration goes wrong at any phase:

| Phase | Rollback action |
|---|---|
| **Shim created, no callers migrated** | Delete new module, restore old from git. Delete shim. |
| **Some callers migrated** | Revert callers to old path (git history). Delete new module. Delete shim. |
| **All callers migrated, but cleanup unsafe** | Leave shim in place. Do not delete old path. Investigate before proceeding. |

**Rollback boundary is the shim.** The shim is the last line of defense — as long as it exists, old code still works.

---

## TID252 Migration Playbook — Example

**Scenario:** `core/cks/integration/` has 47 TID252 violations (47 files using `from .. import` instead of absolute paths).

### Phase 1: Establish safety rails

1. Identify the target module: `core/cks/integration/`
2. Count callers: `grep -r "from core.cks.integration" --include="*.py" . | wc -l`
3. Create shim at OLD path (if OLD path exists) or verify NEW path is the canonical location
4. Verify shim: `python -c "from core.cks.integration import *; print('OK')"`

### Phase 2: Per-file migration

1. Pick a file with TID252 violations
2. Add characterization test if none exists (TDD RED phase)
3. Fix imports using `ruff check --select=TID252 --fix`
4. Verify tests pass
5. Commit with message: `[TID252] migrate core/cks/integration/file.py`
6. Boy scout: if any other old-path imports touched in same file, fix them too

### Phase 3: Cleanup

Trigger conditions for shim removal:
- All callers migrated (grep returns zero results for old path)
- Full test suite passes in CI
- Production verification complete

```bash
# Verify no callers remain
grep -r "from core.cks.integration" --include="*.py" . | grep -v "__pycache__"
# If empty → safe to delete shim and old path
```

---

## Migration Strategy Section (for PLAN step)

When `/refactor` runs on a structural change, the PLAN output must include:

```json
{
  "migration_strategy": {
    "shim_location": "old/path.py → new/path.py",
    "boy_scout_rule": "All new code uses NEW path. If you touch OLD path, migrate it.",
    "migration_scope": [
      "commit 1: migrate core/cks/integration/utils.py",
      "commit 2: migrate core/cks/integration/pipeline.py",
      "..."
    ],
    "rollback": {
      "phase_1": "delete new module, restore old from git",
      "phase_2": "revert callers to old path, delete new module"
    },
    "cleanup_trigger": "All callers migrated + prod verification + CI green"
  }
}
```

See `references/plan-and-review-libraries.md` for plan creation API.