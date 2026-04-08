# Core Plan v1 Integration (v2.25.0)

Three integrated enhancements that work together to provide comprehensive workflow tracking and optimization.

## 1. Evidence Tracking Integration

The `/code` skill now integrates with the `/tdd` evidence tracking system to create timestamped artifacts for TDD phases.

**Evidence artifacts created:**
- **RED phase evidence**: Test files written, test output showing failures
- **GREEN phase evidence**: Implementation passes tests
- **REFACTOR phase evidence**: Code cleanup, tests still passing

**Artifact location:** `.evidence/TASK-{id}_{PHASE}_{timestamp}.md`

**Example usage:**
```python
from tdd.lib.evidence_writer import generate_evidence_artifact

# RED phase: Write failing test
red_evidence = generate_evidence_artifact(
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

# GREEN phase: Implementation passes
green_evidence = generate_evidence_artifact(
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

# REFACTOR phase: Code cleanup
refactor_evidence = generate_evidence_artifact(
    task_id="TASK-001",
    phase="REFACTOR",
    evidence={
        "refactoring": "Code cleaned up",
        "test_status": "STILL_PASSING"
    },
    skill_dir=project_root,
    terminal_id="console_abc123"
)
```

**Automatic cleanup:** Evidence artifacts older than 7 days are automatically removed to prevent disk bloat.

## 2. Pre-Execution Checklist Validation

The pre-execution checklist (5 questions) now includes validation to ensure all answers are non-empty.

**Gap Analysis: Why New Checklist vs Existing Validation**

The /code workflow has two existing validation steps that might seem redundant with the new pre-execution checklist:

| Aspect | Existing (`requirements_clarity_check` + `preflight_context_validation`) | New Pre-Execution Checklist |
|--------|-------------------------------------------------------------------------------|---------------------------|
| **Location in SKILL.md** | Lines 719-769 (Phase 1 and Phase 2) | Lines 263-275 (validation API) |
| **Implementation** | Workflow guidance (manual) | Programmatic validation (enforced) |
| **Format** | "Two Questions (simplified)" approach | Structured 5-question system |
| **Dependency** | External file: `.claude/checklists/pre_implementation.md` | Built-in module: `lib/checklist.py` |
| **Validation** | Self-verified (no enforcement) | Enforced (non-empty answers required) |
| **Evidence Logging** | Manual (user notes evidence) | Automatic (writes to `.evidence/pre_execution.md`) |

**Why Existing Validation Is Insufficient:**

1. **No Enforcement**: `requirements_clarity_check` relies on self-verification with "Two Questions" that can be skipped without consequences
2. **Manual Process**: `preflight_context_validation` is workflow guidance without programmatic checks
3. **External Dependency**: Relies on `.claude/checklists/pre_implementation.md` which may not exist or be outdated
4. **No Evidence Trail**: No automatic logging of validation results to `.evidence/`
5. **Ambiguous Criteria**: "Quick Check (2 minutes)" doesn't define specific acceptance criteria

**How New Checklist Integrates:**

The new pre-execution checklist **replaces and enforces** the existing validation:
- **Structured questions**: 5 specific questions (vs. "Two Questions")
- **Programmatic validation**: `validate_checklist()` API enforces non-empty answers
- **Evidence logging**: `log_checklist_answers()` writes to `.evidence/pre_execution.md`
- **No external dependencies**: Built-in `lib/checklist.py` module
- **Clear acceptance criteria**: All 5 questions must pass validation

**Transition:**
- Old guidance (lines 719-769) remains for reference but is superseded by programmatic checklist
- New checklist is the authoritative validation method (called in workflow_steps before `analyze_query_intent`)

**Validation rules:**
- All 5 questions must be answered
- Empty answers are rejected with specific error messages
- Missing answers trigger validation failure

**Validation API:**
```python
from lib.checklist import validate_checklist

# User answers
checklist_answers = {
    1: "Implement feature X",
    2: "Context",
    3: "Approach",
    4: "Tests pass",
    5: "Verification"
}

# Validate (returns: ValidationResult)
result = validate_checklist(checklist_answers)

if result.passed:
    # Proceed with development
    print("Checklist validated")
else:
    # Show missing answers
    print(f"Missing: {result.missing_answers}")
    print(f"Errors: {result.errors}")
```

**ValidationResult fields:**
- `passed`: Boolean indicating validation passed
- `missing_answers`: List of question numbers with missing/empty answers
- `errors`: List of validation error messages

## 3. Ralph Loop Auto-Enable Based on Task Detection

**Default behavior:** When `--loop` mode is active (which is the default), Ralph Loop is automatically enabled or disabled based on task type detection.

**Task type detection:**
- **Implementation tasks** -> Auto-enable Ralph Loop
  - Keywords: implement, refactor, fix, add, create, build, develop
- **Research tasks** -> Auto-disable Ralph Loop
  - Keywords: research, analyze, document, explore, investigate, study, review

**Detection logged to:** `.evidence/ralph_auto_detection.md`

**Detection API:**
```python
from lib.task_detector import detect_task_type, log_detection_decision

# Detect task type
result = detect_task_type("implement user authentication")

# Result fields:
# - task_type: TaskType.IMPLEMENTATION or TaskType.RESEARCH
# - enable_ralph_loop: True for implementation, False for research
# - confidence: Float 0.0-1.0 indicating detection confidence
# - reasoning: String explaining the detection

# Log decision to evidence
log_detection_decision(
    result=result,
    query="implement user authentication",
    project_root=project_root
)
```

**Override flags:**
- `--ralph-enable`: Force enable Ralph Loop (bypass auto-detection)
- `--ralph-disable`: Force disable Ralph Loop (bypass auto-detection)

## How All Three Features Work Together

The Core Plan v1 features integrate seamlessly in the `/code` workflow:

```
1. User invokes /code with task description
   |
2. Pre-execution checklist presented (5 questions)
   |-- Answers validated (non-empty check)
   +-- Evidence logged to .evidence/pre_execution.md
   |
3. Task type detection runs automatically
   |-- Task classified as IMPLEMENTATION or RESEARCH
   |-- Ralph Loop auto-enabled/disabled
   +-- Decision logged to .evidence/ralph_auto_detection.md
   |
4. TDD phases create timestamped evidence
   |-- RED: .evidence/TASK-{id}_RED_{timestamp}.md
   |-- GREEN: .evidence/TASK-{id}_GREEN_{timestamp}.md
   +-- REFACTOR: .evidence/TASK-{id}_REFACTOR_{timestamp}.md
   |
5. Evidence cleanup (automatic)
   +-- Removes artifacts older than 7 days
```

**Benefits:**
- **Audit trail**: Complete history of development decisions and TDD phases
- **Quality assurance**: Pre-execution checklist ensures clarity before coding
- **Workflow optimization**: Ralph Loop auto-detection matches task type to execution strategy
- **Disk management**: Automatic 7-day cleanup prevents evidence bloat
