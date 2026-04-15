# rca Tier 1 - Rollback Plan

## Overview

This document describes the rollback procedures for rca Tier 1 implementation.

## Rollback Triggers

Consider rollback if:
- Test coverage falls below 75%
- More than 10% of tests fail consistently
- Hook causes session start failures
- CKS integration causes data corruption

## Rollback Levels

### Level 1: Module Rollback (Safe)

Rollback individual modules without affecting system:

```bash
# Identify the problematic module
cd P:/.claude/skills/rca

# Revert specific module
git checkout HEAD~1 evidence_saturation.py
# or
git checkout HEAD~1 phase_state_manager.py

# Re-run tests
pytest tests/test_[module].py -v
```

### Level 2: Hook Rollback (Medium)

Disable the tool gate hook if it causes issues:

```bash
# Option 1: Disable via environment
export DEBUGRCA_TOOL_GATE_ENABLED=false

# Option 2: Remove hook registration
# Edit P:/.claude/settings.json and remove debugrca_tool_gate from PreToolUse

# Option 3: Delete hook file
rm P:/.claude/hooks/PreToolUse/debugrca_tool_gate.py
```

### Level 3: Full Rollback (Nuclear)

Complete rollback of Tier 1 implementation:

```bash
# 1. Disable all environment variables
unset DEBUGRCA_LOCAL_ONLY
unset DEBUGRCA_SATURATION_THRESHOLD
unset DEBUGRCA_STATE_DIR
export DEBUGRCA_TOOL_GATE_ENABLED=false

# 2. Uninstall Python package
pip uninstall rca -y

# 3. Remove hook
rm -f P:/.claude/hooks/PreToolUse/debugrca_tool_gate.py

# 4. Restore previous skill definition
cp P:/.claude/skills/rca.md.bak P:/.claude/skills/rca.md

# 5. Clean state directories
rm -rf P:/.claude/state/debugrca_phase_spool/
rm -rf P:/.claude/state/rca/
```

## Rollback Verification

After rollback, verify:

```bash
# 1. Check hooks work
python P:/.claude/hooks/hook_diagnostics.py

# 2. Check session start
# Start a new Claude Code session and verify no errors

# 3. Check basic operations
# Try basic commands like /debug, /rca, tool usage
```

## Data Recovery

### CKS Phase State Export

Before rollback, export phase states:

```python
from rca import PhaseStateManager

manager = PhaseStateManager()

# Export all sessions for a user
export = manager.export_session("session-id")
import json
print(json.dumps(export, indent=2))
```

### Spool Directory Recovery

The spool directory contains fallback storage:

```bash
# Check spool contents
ls -la P:/.claude/state/debugrca_phase_spool/

# Backup before rollback
cp -r P:/.claude/state/debugrca_phase_spool/ /tmp/debugrca_spool_backup/
```

## Known Issues and Workarounds

### Issue 1: CKS Deprecation Warnings

**Symptom**: DeprecationWarning during CKS import

**Workaround**: Warnings are filtered in conftest.py

```python
warnings.filterwarnings("ignore", category=DeprecationWarning)
```

### Issue 2: ResourceWarning for Database Connections

**Symptom**: Unclosed database warnings in tests

**Workaround**: Warnings filtered in conftest.py

```python
warnings.filterwarnings("ignore", category=ResourceWarning)
```

### Issue 3: Module Import Naming

**Symptom**: Import errors due to uppercase/lowercase naming

**Workaround**: Both import paths work:

```python
from rca import EvidenceSaturationDetector  # Uppercase
from debugrca import EvidenceSaturationDetector  # Lowercase
```

## Rollback Decision Tree

```
Is a test failing?
├─ Yes: Is it a hook test?
│  ├─ Yes: Disable hook (Level 2)
│  └─ No: Revert module (Level 1)
└─ No: Continue

Is session start failing?
├─ Yes: Is it the tool gate?
│  ├─ Yes: Disable tool gate (Level 2)
│  └─ No: Full rollback (Level 3)
└─ No: Continue

Is CKS data corrupted?
├─ Yes: Export data, then full rollback (Level 3)
└─ No: Continue
```

## Rollback Checklist

Before rollback:
- [ ] Identify rollback level needed
- [ ] Export any important phase states
- [ ] Backup spool directory
- [ ] Document the issue

After rollback:
- [ ] Verify hooks work
- [ ] Verify session start works
- [ ] Verify basic operations work
- [ ] Run diagnostic tests
- [ ] Document rollback reason

## Contact

For issues or questions about rollback:
- Check: `P:/.claude/skills/debugrca/README.md`
- Review: `P:/.claude/skills/rca/SKILL.md`
- Tests: `P:/.claude/skills/rca/tests/`
