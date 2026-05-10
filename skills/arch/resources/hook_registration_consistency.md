# Hook Registration Consistency Check

## Purpose

Detect architectural inconsistencies in hook registration patterns across the codebase.

## Problem Statement

Hook registration inconsistencies occur when hooks of the same type or category use different registration mechanisms:

- **Standalone hooks**: Registered directly in `settings.json` with command invocations
- **Router-based hooks**: Registered via router pattern (UNIVERSAL/TOOL_HOOKS lists)
- **Modular registry hooks**: Registered via decorator pattern (`@register_hook`)

When similar hooks use inconsistent registration patterns, it creates:
1. **Maintenance burden** - Different patterns require different update procedures
2. **Architectural confusion** - Unclear which pattern to use for new hooks
3. **Hidden failures** - Dead hooks that appear to exist but never execute
4. **Registration debt** - Accumulated inconsistencies become harder to fix over time

## Detection Logic

### Step 1: Scan Registration Sources

```python
import json
from pathlib import Path
from typing import Dict, List, Set

def scan_hook_registrations() -> Dict[str, List[Dict]]:
    """Scan all hook registration sources and return categorized inventory."""

    registrations = {
        "settings_json": [],
        "routers": [],
        "modular_registry": [],
        "standalone_files": []
    }

    # 1. Scan settings.json
    settings_path = Path.home() / ".claude" / "settings.json"
    project_settings = Path.cwd() / ".claude" / "settings.json"

    for settings_file in [settings_path, project_settings]:
        if settings_file.exists():
            with open(settings_file) as f:
                settings = json.load(f)
                hooks = settings.get("hooks", {})
                for event_name, hook_configs in hooks.items():
                    for config in hook_configs:
                        for hook in config.get("hooks", []):
                            command = hook.get("command", "")
                            registrations["settings_json"].append({
                                "event": event_name,
                                "command": command,
                                "source": str(settings_file),
                                "type": "standalone"
                            })

    # 2. Scan router files
    hooks_dir = Path.cwd() / ".claude" / "hooks"
    for router_file in hooks_dir.glob("*_router.py"):
        content = router_file.read_text()
        # Extract UNIVERSAL and TOOL_HOOKS lists
        # Store registered hook names

    # 3. Scan modular registry (UserPromptSubmit_modules/registry.py)
    registry_file = hooks_dir / "UserPromptSubmit_modules" / "registry.py"
    if registry_file.exists():
        content = registry_file.read_text()
        # Extract core_hook_modules list
        # Store registered module names

    return registrations
```

### Step 2: Group by Hook Type

```python
def group_by_hook_type(registrations: Dict) -> Dict[str, Dict]:
    """Group hooks by their functional type for comparison."""

    grouped = {}

    # Group by event type (UserPromptSubmit, PreToolUse, etc.)
    for source, hooks in registrations.items():
        for hook in hooks:
            event = hook["event"]
            if event not in grouped:
                grouped[event] = {"standalone": [], "router": [], "modular": []}

            if source == "settings_json":
                grouped[event]["standalone"].append(hook)
            elif "router" in source:
                grouped[event]["router"].append(hook)
            elif "modular" in source:
                grouped[event]["modular"].append(hook)

    return grouped
```

### Step 3: Detect Inconsistencies

```python
HOOK_EVENT_PATTERNS = {
    "UserPromptSubmit": "prefer_modular_registry",  # Decorator pattern preferred
    "PreToolUse": "prefer_router",                   # Router pattern preferred
    "PostToolUse": "prefer_router",                  # Router pattern preferred
    "Stop": "prefer_router",                         # Router pattern preferred
    "SessionStart": "allow_standalone",              # settings.json OK
    "SessionEnd": "allow_standalone"                 # settings.json OK
}

def detect_inconsistencies(grouped: Dict) -> List[Dict]:
    """Detect architectural inconsistencies in hook registration."""

    inconsistencies = []

    for event, patterns in grouped.items():
        preferred = HOOK_EVENT_PATTERNS.get(event)
        if not preferred:
            continue

        # Check if hooks use non-preferred pattern
        if preferred == "prefer_modular_registry":
            # UserPromptSubmit should use modular registry
            standalone = [h for h in patterns["standalone"]
                         if not any(x in h["command"]
                                   for x in ["hook_importer", "hook_runner"])]
            if standalone:
                inconsistencies.append({
                    "event": event,
                    "severity": "warning",
                    "issue": f"{len(standalone)} UserPromptSubmit hook(s) registered via settings.json instead of modular registry",
                    "hooks": standalone,
                    "recommendation": "Refactor to use @register_hook decorator pattern in UserPromptSubmit_modules/"
                })

        elif preferred == "prefer_router":
            # PreToolUse/PostToolUse/Stop should use router
            standalone = patterns["standalone"]
            if standalone:
                inconsistencies.append({
                    "event": event,
                    "severity": "warning",
                    "issue": f"{len(standalone)} {event} hook(s) registered via settings.json instead of router",
                    "hooks": standalone,
                    "recommendation": f"Add to UNIVERSAL or TOOL_HOOKS in {event}_router.py or PreToolUse.py"
                })

    return inconsistencies
```

## Integration into /arch Workflow

### Stage 0.2 Enhanced: Hook Registration Consistency

Add to `arch/SKILL.md` Stage 0.2 Self-Verification Check:

```markdown
### Step 0.2.5: Hook Registration Consistency (NEW)

**Trigger**: Architecture queries involving hooks, skills, or workflow systems.

**Check**: Scan hook registrations for architectural inconsistencies:

1. **Group by event type** - UserPromptSubmit, PreToolUse, PostToolUse, Stop
2. **Detect pattern violations**:
   - UserPromptSubmit hooks in settings.json (should use modular registry)
   - PreToolUse/PostToolUse/Stop hooks in settings.json (should use router)
3. **Report inconsistencies** with severity and remediation guidance

**Output format**:
```
HOOK REGISTRATION INCONSISTENCY DETECTED

Event: UserPromptSubmit
Severity: warning
Issue: 1 hook(s) registered via settings.json instead of modular registry
  • P:\\\\\\.claude/hooks/UserPromptSubmit_discovery_block.py

Recommendation: Refactor to use @register_hook decorator pattern
  1. Move to UserPromptSubmit_modules/discovery_block.py
  2. Add "discovery_block" to core_hook_modules in registry.py
  3. Remove settings.json registration

Architectural impact:
  • Current: Mixed registration patterns create maintenance burden
  • Proposed: Consistent modular registry for all UserPromptSubmit hooks
```

**When to skip**: Queries unrelated to hook architecture, external system design, or deployment infrastructure.
```

## Example Output

### Scenario: discovery_block Hook Inconsistency

```
/arch "review hook registration patterns for architectural consistency"

Stage 0.2: Hook Registration Consistency Check

SCANNING REGISTRATION SOURCES:
  ✓ P:\\\\\\.claude/settings.json
  ✓ P:\\\\\\.claude/hooks/PreToolUse.py (UNIVERSAL hooks)
  ✓ P:\\\\\\.claude/hooks/UserPromptSubmit_modules/registry.py

DETECTED INCONSISTENCIES:

Event: UserPromptSubmit
Severity: warning
Issue: 1 hook(s) registered via settings.json instead of modular registry
  • UserPromptSubmit_discovery_block.py (standalone)

Current registration:
  settings.json → UserPromptSubmit → python P:\\\\\\.claude/hooks/UserPromptSubmit_discovery_block.py

Architectural inconsistency:
  • Most UserPromptSubmit hooks use modular registry (@register_hook)
  • discovery_block uses standalone settings.json registration
  • Creates dual registration patterns to maintain

Recommendation:
  1. Refactor UserPromptSubmit_discovery_block.py to UserPromptSubmit_modules/discovery_block.py
  2. Add @register_hook("discovery_block", priority=6.0) decorator
  3. Add "discovery_block" to core_hook_modules in registry.py
  4. Remove settings.json registration

Benefits:
  • Consistent registration pattern across all UserPromptSubmit hooks
  • Centralized priority management in registry.py
  • Auto-loading via core_hook_modules list
  • Reduced settings.json complexity

Continue with architecture review? (Y/n)
```

## Test Cases

```python
def test_hook_registration_consistency():
    """Test hook registration consistency detection."""

    # Case 1: Consistent UserPromptSubmit registration
    # All hooks use modular registry → no warnings

    # Case 2: Inconsistent UserPromptSubmit registration
    # Mix of modular and standalone → warning detected

    # Case 3: Consistent PreToolUse registration
    # All hooks in router → no warnings

    # Case 4: Legacy standalone hook detected
    # Old pattern in settings.json → recommendation provided
```

## Implementation Priority

| Priority | Task | Status |
|----------|------|--------|
| P0 | Create hook_registration_consistency.py module | Pending |
| P1 | Integrate into /arch Stage 0.2 | Pending |
| P2 | Add test coverage | Pending |
| P3 | Update CLAUDE.md with findings | Pending |

## Related Documentation

- `P:\\\\\\.claude/hooks/CLAUDE.md` - Hook Registration Pattern section
- `P:\\\\\\.claude/hooks/UserPromptSubmit_modules/registry.py` - Modular registry pattern
- `P:\\\\\\.claude/hooks/PreToolUse.py` - Router pattern (UNIVERSAL hooks)

## Version History

- v1.0 (2026-04-09) - Initial specification for hook registration consistency checking
