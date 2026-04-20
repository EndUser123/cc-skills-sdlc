# Evidence Collection Integration

**MANDATORY:** All TDD phases MUST collect evidence for verification.

## Core Plan v1 Evidence Tracking

The /tdd skill integrates with **Core Plan v1 Evidence Tracking** to create timestamped artifacts for each TDD phase.

**Evidence Location**: `.evidence/` directory in project root

**Artifact Format**: `TASK-{id}_{PHASE}_{timestamp}.md`

**Example artifact names**:
- `TASK-001_RED_20260315_143000.md`
- `TASK-001_GREEN_20260315_143500.md`
- `TASK-001_REFACTOR_20260315_144000.md`

**Evidence Content**:
```markdown
# TDD Evidence: TASK-001 - RED Phase

**Task ID**: TASK-001
**Phase**: RED
**Timestamp**: 2026-03-15T14:30:00Z
**Terminal**: console_abc123

## Evidence

- **Test Files**: test_feature.py
- **Test Status**: FAILING (expected)
- **Test Output**: [pytest output showing failures]

## Verification

- Tests written before implementation
- Tests fail as expected (RED phase confirmed)
```

## 7-Day Cleanup Policy

Evidence artifacts older than 7 days are automatically cleaned up to prevent disk bloat.

**Cleanup script**:
```python
from tdd.lib.evidence_writer import cleanup_old_evidence

# Run cleanup (removes artifacts older than 7 days)
cleaned_count = cleanup_old_evidence(project_root, max_days=7)
print(f"Cleaned {cleaned_count} old evidence files")
```

**Integration with /code workflow**:
- Evidence tracking automatically enabled when `/code` invokes `/tdd`
- Artifacts created in shared `.evidence/` directory
- Compatible with pre-execution checklist and task detection evidence

## Evidence Collection by Phase

### RED Phase (Test Writing)

After writing the test, collect evidence of test failure:

```python
from tdd.lib.evidence_writer import generate_evidence_artifact

# Create RED phase evidence artifact
artifact_path = generate_evidence_artifact(
    task_id="TASK-001",
    phase="RED",
    evidence={
        "test_files": ["test_feature.py"],
        "test_status": "FAILING",
        "test_output": "[pytest output showing failures]"
    },
    skill_dir=project_root,
    terminal_id="console_abc123"
)

# Verify artifact was created
assert artifact_path.exists(), "RED evidence artifact should exist"
```

### GREEN Phase (Implementation)

After implementing code, collect evidence of test passing:

```python
from tdd.lib.evidence_writer import generate_evidence_artifact

# Create GREEN phase evidence artifact
artifact_path = generate_evidence_artifact(
    task_id="TASK-001",
    phase="GREEN",
    evidence={
        "implementation": "Feature implemented",
        "test_status": "PASSING",
        "test_results": "All tests pass"
    },
    skill_dir=project_root,
    terminal_id="console_abc123"
)

# Verify artifact was created
assert artifact_path.exists(), "GREEN evidence artifact should exist"
```

**AST-based changes for Python structural modifications**:
```python
from packages.refactor.ast_refactor_helpers import safe_transform_file, LibCSTTransformer

class MyTransformer(LibCSTTransformer):
    def leave_Name(self, original_node, updated_node):
        # Transform logic
        return updated_node

success, error, count = safe_transform_file(
    "src/module.py",
    MyTransformer
)
```

**String-based changes** (only when safe):
- Full file replacement (Write tool)
- Comment-only changes
- String literal content changes

**Prohibited**:
- Partial code block `.replace()`
- Regex on code structure
- sed/awk for Python code

**Reference**: `/refactor` skill (see `packages/cc-skills-sdlc/skills/refactor/`)

### REFACTOR Phase (Cleanup)

After refactoring, collect evidence that tests still pass:

```python
from tdd.lib.evidence_writer import generate_evidence_artifact

# Create REFACTOR phase evidence artifact
artifact_path = generate_evidence_artifact(
    task_id="TASK-001",
    phase="REFACTOR",
    evidence={
        "refactoring": "Code cleaned up",
        "test_status": "STILL_PASSING",
        "verification": "Tests still pass after refactor"
    },
    skill_dir=project_root,
    terminal_id="console_abc123"
)

# Verify artifact was created
assert artifact_path.exists(), "REFACTOR evidence artifact should exist"
```

## Evidence Tracking API

**Evidence tracking is provided by `tdd.lib.evidence_writer` module:**

```python
from tdd.lib.evidence_writer import (
    generate_evidence_artifact,
    cleanup_old_evidence,
    is_evidence_tracking_enabled
)

# Check if evidence tracking is enabled
if is_evidence_tracking_enabled():
    # Generate evidence artifact
    artifact_path = generate_evidence_artifact(
        task_id="TASK-001",
        phase="RED",
        evidence={"test_files": ["test_feature.py"]},
        skill_dir=project_root,
        terminal_id="console_abc123"
    )

    # Cleanup old evidence (7-day policy)
    cleanup_old_evidence(project_root, max_days=7)
```
