# TDD Checkpoint Implementation

**Purpose**: Detailed TDD enforcement flow, exemption detection, and phase implementation code.

## TDD Enforcement Flow

```
For each refactoring finding:
    ↓
1. Check exemption status
    ├─ Exempt? → Skip TDD (docs, config, .staging/)
    └─ Not exempt? → Continue
    ↓
2. RED Phase: Write/find characterization test
    └─ Verify test FAILS (must fail before changes)
    ↓
3. Apply refactoring changes
    ↓
4. GREEN Phase: Verify test PASSES
    └─ Verify test PASSES (must pass after changes)
    ↓
5. REGRESSION Phase: Run related tests
    └─ Verify no new failures
    ↓
6. Store evidence in .evidence/
```

## Exemption Detection

**These file types are EXEMPT from TDD:**

| Pattern | Rationale |
|---------|-----------|
| `.md`, `.rst` | Documentation - no code behavior |
| `.json`, `.yaml`, `.toml`, `.ini` | Configuration - data only |
| `tests/` | Test files themselves |
| `.staging/`, `scripts/` | Exploratory/temporary code |

**Implementation:**

```python
def is_exempt_from_tdd(file_path: str) -> bool:
    """Check if file is exempt from TDD requirement."""
    exempt_patterns = [
        '.md', '.rst',  # Documentation
        '.json', '.yaml', '.yml', '.toml', '.ini',  # Config files
        'tests/',  # Test files themselves
        '.staging/', 'scripts/',  # Exploratory/temporary
    ]

    file_path_lower = file_path.lower()
    return any(file_path_lower.endswith(p) or f'/{p}' in file_path_lower for p in exempt_patterns)
```

## TDD Phase Implementation

```python
import json
import subprocess
from datetime import datetime
from pathlib import Path
from src.core.evidence_collector import collect_test_evidence, verify_tdd_red, verify_tdd_green

def create_rollback_plan(finding: dict) -> dict:
    """Generate rollback plan before refactoring."""
    timestamp = datetime.now().isoformat()
    finding_id = finding.get('id', 'unknown')

    git_commit_before = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'],
        text=True,
        cwd=Path.cwd()
    ).strip()

    rollback_plan = {
        'timestamp': timestamp,
        'files_changed': finding.get('files', []),
        'git_commit_before': git_commit_before,
        'rollback_command': f'git revert {git_commit_before}',
        'test_baseline': 'pytest tests/ -v',
        'finding_id': finding_id
    }

    rollback_dir = Path('.evidence/refactor/rollbacks')
    rollback_dir.mkdir(parents=True, exist_ok=True)
    rollback_file = rollback_dir / f'{timestamp.replace(":", "-")}_{finding_id}.json'
    rollback_file.write_text(json.dumps(rollback_plan, indent=2), encoding='utf-8')

    return rollback_plan

def cleanup_rollback_plan(timestamp: str) -> None:
    """Remove rollback plan after successful refactoring."""
    rollback_dir = Path('.evidence/refactor/rollbacks')
    if rollback_dir.exists():
        for plan_file in rollback_dir.glob(f'{timestamp.replace(":", "-")}_*.json'):
            plan_file.unlink()

def characterize_behavior(func, inputs):
    """Capture current behavior before refactoring."""
    import time
    from typing import Any

    state_before = get_state_snapshot()

    start_time = time.perf_counter()
    try:
        output = func(*inputs)
        success = True
    except Exception as e:
        output = str(e)
        success = False
    end_time = time.perf_counter()

    state_after = get_state_snapshot()
    side_effects = detect_state_changes(state_before, state_after)

    return {
        'input': inputs,
        'output': output,
        'success': success,
        'side_effects': side_effects,
        'duration_ms': (end_time - start_time) * 1000
    }

def verify_behavior_preserved(before: dict, after: dict) -> bool:
    """Verify behavior preserved after refactoring."""
    if before['output'] != after['output']:
        return False
    if after['duration_ms'] > before['duration_ms'] * 1.1:
        return False
    if set(after['side_effects']) - set(before['side_effects']):
        return False
    return True

def get_state_snapshot() -> dict:
    """Capture current system state for side-effect detection."""
    import os
    from pathlib import Path

    cwd_files = {
        str(p): p.stat().st_mtime
        for p in Path.cwd().rglob('*')
        if p.is_file() and not p.name.startswith('.')
    }

    env_snapshot = {
        'cwd': os.getcwd(),
        'python_path': os.environ.get('PYTHONPATH', ''),
    }

    return {
        'files': cwd_files,
        'env': env_snapshot,
        'timestamp': datetime.now().isoformat()
    }

def detect_state_changes(before: dict, after: dict) -> list:
    """Detect side-effects from state snapshots."""
    changes = []

    before_files = set(before['files'].keys())
    after_files = set(after['files'].keys())

    new_files = after_files - before_files
    if new_files:
        changes.append(f'created_files: {len(new_files)}')

    common_files = before_files & after_files
    modified = [
        f for f in common_files
        if before['files'][f] != after['files'][f]
    ]
    if modified:
        changes.append(f'modified_files: {len(modified)}')

    deleted_files = before_files - after_files
    if deleted_files:
        changes.append(f'deleted_files: {len(deleted_files)}')

    return changes

def red_phase(finding: dict) -> str:
    """RED: Write characterization test, verify it FAILS."""
    test_file = find_or_create_test(finding['file_path'], finding)
    artifact = collect_test_evidence(f"pytest {test_file} -v", description=f"RED: {finding['title']}")
    if not verify_tdd_red(artifact).is_verified:
        raise RuntimeError(f"TDD RED violated: {test_file} must FAIL before changes")
    return test_file

def green_phase(finding: dict, test_file: str):
    """GREEN: Verify test PASSES after refactoring."""
    artifact = collect_test_evidence(f"pytest {test_file} -v", description=f"GREEN: {finding['title']}")
    result = verify_tdd_green(artifact)
    if not result.is_verified:
        raise RuntimeError(f"TDD GREEN failed: {test_file} must PASS. Failures: {result.failure_output}")

def regression_phase(finding: dict):
    """REGRESSION: Run related tests, verify no new failures."""
    module = finding['file_path'].split('/')[-1].replace('.py', '')
    artifact = collect_test_evidence(f"pytest tests/ -k '{module}' -v", description=f"REGRESSION: {finding['title']}")
    failed = artifact.data.get('test_stats', {}).get('failed', 0)
    if failed > 0:
        raise RuntimeError(f"REGRESSION failed: {failed} new failures in {module}")

def find_or_create_test(file_path: str, finding: dict) -> str:
    """Find existing test or delegate to tdd-test-writer subagent."""
    module_name = file_path.split('/')[-1].replace('.py', '')
    for candidate in [f"tests/test_{module_name}.py", "tests/test_refactor_safety.py"]:
        if Path(candidate).exists():
            return candidate
    content = tdd_test_writer.create_characterization_test(file_path=file_path, finding=finding)
    test_file = f"tests/test_{module_name}.py"
    Path(test_file).write_text(content, encoding='utf-8')
    return test_file

def refactor_with_tdd(finding: dict):
    """Full TDD cycle: exemption → rollback → characterize → RED → refactor → GREEN → REGRESSION."""
    if is_exempt_from_tdd(finding['file_path']):
        apply_refactoring(finding)
        return

    rollback_plan = create_rollback_plan(finding)

    target_function = finding.get('target_function')
    test_inputs = finding.get('test_inputs', [])

    behavior_before = None
    if target_function and test_inputs:
        behavior_before = characterize_behavior(target_function, test_inputs)

    test_file = red_phase(finding)

    apply_refactoring(finding)

    behavior_after = None
    if target_function and test_inputs:
        behavior_after = characterize_behavior(target_function, test_inputs)
        if not verify_behavior_preserved(behavior_before, behavior_after):
            raise RuntimeError("Behavior changed unexpectedly - rollback required")

    green_phase(finding, test_file)

    regression_phase(finding)

    cleanup_rollback_plan(rollback_plan['timestamp'])
```

## Error Messages Reference

| Phase | Error Message | User Action |
|-------|--------------|-------------|
| **RED** | `TDD RED phase violated: {test_file} must FAIL before changes` | Write test that captures current behavior |
| **GREEN** | `TDD GREEN phase failed: {test_file} must PASS after changes` | Fix code to make test pass, or revert |
| **REGRESSION** | `REGRESSION phase failed: {N} new failures detected` | Fix regressions before completing |
