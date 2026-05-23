---
Status: Completed
Date: 2025-02-05
Completed: true
Last Reviewed: 2025-02-05
---

# TDD Hook Migration: settings.json → Skill-Based Hooks

## Context

TDD enforcement in the codebase suffers from three architectural flaws causing false positives and state corruption. The migration to skill-based hooks with terminal isolation will fix cross-process cache invalidation issues and provide proper multi-terminal support.

## Problem Statement

Three interconnected issues with TDD enforcement:

1. **Global enforcement via settings.json** — `pretooluse_tdd_gate.py` runs on EVERY Write/Edit regardless of whether `/tdd` was invoked, causing false positive blocks
2. **Cross-process stale state** — `TDDState` uses 30s in-memory cache (`threading.Lock`) but PreToolUse gate and PostToolUse router run in separate OS processes, so cache invalidation in one process is invisible to another
3. **No terminal isolation** — State files keyed by `{cwd}:{test_file}` MD5 hash, meaning two terminals working on the same project collide on state

## Corrected Understanding

- `PostToolUse_tdd_state.py` standalone main() is truncated/broken, BUT the `TDDStateHook` in-process adapter (`posttooluse/tdd_state_hook.py`) IS registered in `posttooluse/__init__.py:82` and runs via `PostToolUse_router.py:166-167`
- Phase transitions DO happen — the problem is the PreToolUse gate reads stale cached state from a different process
- `UserPromptSubmit_tdd_eval.py` runs via `UserPromptSubmit_router.py` (priority 6) for skill activation detection

## Context Analysis

**Reversibility:** [R:2] - Moderate cost. Changes to `tdd_core.py` affect the core state management system. Can roll back by restoring original files from git. Skill hooks can be disabled by removing frontmatter. Settings.json changes are reversible.

**Blast radius:**
- `/tdd` skill - adds hook frontmatter
- `.claude/hooks/tdd_core.py` - core state management
- `.claude/settings.json` - global hook configuration
- `.claude/hooks/posttooluse/tdd_state_hook.py` - in-process adapter
- Multi-terminal TDD workflows

**Evidence tier:** Tier 2 - Root cause analysis of existing code and architecture. Assumptions about terminal isolation behavior need verification.

**Assumptions with verification plan:**
1. Terminal ID detection works reliably → Test: `python -c "from terminal_detection import detect_terminal_id; print(detect_terminal_id())"`
2. File locking prevents race conditions → Test: Concurrent writes to state file from multiple terminals
3. `terminal_detection` module exists → Verification: File exists at `.claude/hooks/__lib/terminal_detection.py`

## Existing Implementation Discovery

**Search terms used:**
- `tdd_core`, `TDDState`, `pretooluse_tdd_gate`, `tdd_state_hook`
- `terminal_detection`, `detect_terminal_id`
- `hooks frontmatter`, `skill hooks`

**Results found:**
- `.claude/hooks/tdd_core.py` - Core TDD state management with cache (lines 407-496)
- `.claude/hooks/pretooluse_tdd_gate.py` - Global TDD gate with lru_cache on line 30
- `.claude/hooks/posttooluse/tdd_state_hook.py` - In-process adapter (registered line 82)
- `.claude/hooks/PostToolUse_tdd_state.py` - Function library with truncated main()
- `.claude/skills/tdd/SKILL.md` - TDD skill definition (no hooks frontmatter yet)
- `.claude/hooks/__lib/terminal_detection.py` - Terminal ID detection module

**Reusability assessment:**
- `tdd_core.py` - Needs modification (remove cache, add terminal isolation)
- `PostToolUse_tdd_state.py` - Functions reusable, main() needs rewrite
- `terminal_detection.py` - Fully reusable
- `pretooluse_tdd_gate.py` - Template for skill version (needs cache removal)

## Test Discovery

**Existing tests found:**
- No dedicated TDD hook test files discovered in codebase search
- Manual verification procedures exist in plan (Verification section)

**Test gaps identified:**
1. No unit tests for `TDDState` class methods
2. No integration tests for cross-process state consistency
3. No tests for terminal isolation behavior
4. No tests for concurrent access to state files

**Test files to create:**
- `tests/test_tdd_state_isolation.py` - Terminal isolation tests
- `tests/test_tdd_concurrent_access.py` - Concurrent file access tests
- `tests/test_tdd_hook_integration.py` - End-to-end hook workflow tests

## Proposed Solution

**Option A: Skill-based hooks with terminal isolation (Recommended)**

- **Pro:** Fixes all three issues (false positives, stale cache, terminal collision)
- **Pro:** Minimal changes to existing architecture (additive, not replacing)
- **Pro:** Global gate still works for non-skill TDD enforcement
- **Con:** Requires `terminal_detection` dependency (assumed to exist)
- **Con:** R:2 reversibility due to tdd_core.py changes

**Option B: Replace global gate with skill-only enforcement**

- **Pro:** Simpler architecture (single enforcement path)
- **Pro:** No settings.json changes needed
- **Con:** Loses global TDD protection for non-skill workflows
- **Con:** R:3 higher reversibility (requires removing skill hooks to revert)
- **Con:** Breaks existing user expectations about global TDD enforcement

**Option C: Fix cache only, keep cwd-based state keys**

- **Pro:** Minimal changes (remove cache, keep state path logic)
- **Pro:** R:1 lower reversibility
- **Con:** Doesn't fix terminal collision issue
- **Con:** Multi-terminal workflows remain broken

**Recommendation:** Option A wins because it fixes all three identified issues with acceptable reversibility cost while preserving backward compatibility with global TDD enforcement.

## Risk Assessment

**Pre-mortem (Future hindsight):**
- Terminal ID detection returns same value for different terminals → state collision persists
- File locking doesn't work on Windows → race conditions in state writes
- Removing cache causes performance regression → hooks become too slow

**Inversion analysis (Easiest failure mode):**
- Forgetting to update settings.json path → old broken hook still runs
- Typos in YAML frontmatter → skill hooks don't load, no error shown
- Terminal isolation breaks existing state files → users lose active TDD cycles

**Blast radius (Dependencies):**
- Any code using `TDDState.load()` directly → gets no cache (possible perf impact)
- `.claude/state/tdd/` directory structure changes → old state files become orphaned
- Global TDD gate depends on fixed `tdd_core.py`

**Rollback plan:**
1. Remove hooks frontmatter from `.claude/skills/tdd/SKILL.md`
2. Restore `.claude/hooks/tdd_core.py` from git
3. Revert settings.json path changes
4. Delete `.claude/skills/tdd/hooks/` directory

**Second-order effects:**
- Users with active TDD cycles lose state → need to restart /tdd
- Old state files accumulate → need cleanup strategy
- Other skills may adopt similar pattern → establish precedent

**Mitigation strategies:**
- Add migration script to preserve existing state files
- Log warnings when using old state file format
- Add fallback to old behavior if terminal detection fails

## Implementation Plan

### Step 1: Add hooks to SKILL.md frontmatter [R:1]

**File:** `P://.claude/skills/tdd/SKILL.md`

Add `hooks:` section to YAML frontmatter (after line 15, before `---` closing):

```yaml
hooks:
  # No PreToolUse — global settings.json gate handles enforcement for all Write/Edit.
  # Adding it here would cause double execution during /tdd sessions.
  PostToolUse:
    - matcher: "Write|Edit|Bash"
      hooks:
        - type: command
          command: python ".claude/skills/tdd/hooks/PostToolUse_tdd_state.py"
          timeout: 5
  SessionEnd:
    - matcher: ".*"
      hooks:
        - type: command
          command: python ".claude/skills/tdd/hooks/SessionEnd_tdd_cleanup.py"
          timeout: 3
```

### Step 2: Create skill hook directory and files

**Create directory:** `P://.claude/skills/tdd/hooks/`

#### 2a: `PreToolUse_tdd_gate.py` — Migrate from `P://.claude/hooks/pretooluse_tdd_gate.py`

Changes from original:
- Remove `@lru_cache` on `is_tdd_exempt()` (line 30) — prevents stale exemption decisions
- In `get_tdd_state_for_file()`: read state with NO cache (direct file read every time)
- Add `sys.path.insert(0, str(Path("P://.claude/hooks")))` to access `tdd_core`
- Use `terminal_detection.detect_terminal_id()` for state path resolution

#### 2b: `PostToolUse_tdd_state.py` — New standalone hook with complete main()

The standalone `P://.claude/hooks/PostToolUse_tdd_state.py` has a truncated `main()`. Create a complete standalone version that:
- Reads hook input from stdin (tool_name, tool_input, tool_response)
- Dispatches to existing `handle_test_file_write()`, `handle_test_run()`, `handle_impl_file_write()` functions (imported from original module)
- Outputs JSON result to stdout

#### 2c: `SessionEnd_tdd_cleanup.py` — New

- Delete state files older than 24h from current terminal's state directory
- Pattern: same as `/v` skill's `SessionEnd_v_cleanup.py`

### Step 3: Fix state management in `tdd_core.py` [R:2]

**File:** `P://.claude/hooks/tdd_core.py`

#### 3a: Remove in-memory cache

Delete from `TDDState`:
- `self._cache` dict (lines 407-412)
- `self._cache_lock` (line 413)
- Cache hit logic in `load()` (lines 439-446)
- Cache update in `load()` (lines 467-469)
- Cache invalidation in `save()` (lines 513-516)
- `get_cache_metrics()` (lines 480-486)
- `clear_cache()` (lines 488-492)
- `get_cache_ttl()` (lines 494-496)
- `CACHE_TTL_SECONDS` constant (line 152)

`load()` becomes: open file → shared lock → read JSON → unlock → return. No caching.

#### 3b: Add terminal isolation to state paths

Change `_resolve_state_file()` (lines 420-435):

```python
def _resolve_state_file(self, test_file: str | None) -> Path:
    from terminal_detection import detect_terminal_id
    terminal_id = detect_terminal_id()

    # Terminal-isolated state directory
    state_dir = Path("P://.claude/state/tdd") / terminal_id
    state_dir.mkdir(parents=True, exist_ok=True)

    if test_file:
        file_key = hashlib.md5(test_file.encode()).hexdigest()[:12]
        return state_dir / f"tdd.{file_key}.json"
    return state_dir / "tdd.default.json"
```

Drop `cwd` from hash — terminal_id provides isolation instead.

Update `STATE_DIR` references:
- `_ensure_state_dir()` — use dynamic path
- `cleanup_expired_states()` — scan all terminal dirs under `P://.claude/state/tdd/`
- Debug/audit log paths — keep in shared location or move to terminal dir

#### 3c: Update callers of STATE_DIR

Functions that reference the old `STATE_DIR` constant:
- `find_active_tdd_cycle()` — must scan terminal-specific dir
- `cleanup_expired_states()` — scan across all terminal dirs
- `debug_log()` — keep shared (logging doesn't need isolation)

### Step 4: Update settings.json global hook to use fixed tdd_core [R:1]

**File:** `P://.claude/settings.json`

KEEP the `pretooluse_tdd_gate.py` entry in settings.json (lines 156-163) — but update the command path to point to the NEW version in the skill hooks directory:

```json
{
  "type": "command",
  "command": "python P://.claude/hooks/__lib/hook_runner.py P://.claude/skills/tdd/hooks/PreToolUse_tdd_gate.py --timeout 3.0",
  "timeout": 3
}
```

This means both the global enforcement AND skill-based enforcement use the SAME fixed hook file (no lru_cache, terminal-isolated state). The original `P://.claude/hooks/pretooluse_tdd_gate.py` becomes dead code.

### Step 5: Remove TDDStateHook from PostToolUse router [R:1]

**File:** `P://.claude/hooks/posttooluse/__init__.py`

REMOVE `TDDStateHook` registration (line 82) and its import (line 37).

**Rationale:** The skill-based `PostToolUse_tdd_state.py` is now the sole state writer. This eliminates double execution entirely — no dedup guard needed. Outside of `/tdd` sessions, no phase transitions occur, so the global PreToolUse gate correctly blocks with "No active TDD cycle" (forcing `/tdd` invocation). Inside `/tdd` sessions, the skill PostToolUse hook handles all phase transitions.

This is cleaner than a dedup guard because:
- Single writer = no race conditions on state transitions
- No redundant file I/O from double execution
- Clear ownership: skill hooks own TDD state lifecycle

### Step 6: Keep UserPromptSubmit_tdd_eval.py as-is

The tdd_eval in UserPromptSubmit_router.py (priority 6) handles skill activation detection ("should I invoke /tdd?"). This is orthogonal to the skill hooks which enforce workflow AFTER /tdd is invoked. Keep it.

## Files Modified

| File | Action | Risk |
|------|--------|------|
| `.claude/skills/tdd/SKILL.md` | Add hooks frontmatter | R:1 |
| `.claude/skills/tdd/hooks/PreToolUse_tdd_gate.py` | New (migrated) | R:1 |
| `.claude/skills/tdd/hooks/PostToolUse_tdd_state.py` | New (complete standalone) | R:1 |
| `.claude/skills/tdd/hooks/SessionEnd_tdd_cleanup.py` | New | R:1 |
| `.claude/hooks/tdd_core.py` | Remove cache, add terminal isolation | R:2 |
| `.claude/settings.json` | Update path to new PreToolUse_tdd_gate.py | R:1 |
| `.claude/hooks/posttooluse/__init__.py` | Remove TDDStateHook registration | R:1 |

## What NOT to Change

- `UserPromptSubmit_tdd_eval.py` / router integration — keeps skill activation detection
- `PostToolUse_tdd_state.py` (original in hooks/) — kept as function library, imported by skill hook
- `posttooluse/tdd_state_hook.py` — kept as file on disk, just deregistered from __init__.py
- `tdd_core.py` location — stays in `.claude/hooks/` as shared infrastructure
- `settings.json` TDD config section (lines 505-565) — enforcement_mode, tiers, exclusions unchanged

## Verification

1. **Invoke `/tdd` and verify hooks activate:**
   ```
   # Start /tdd, write a test file → PreToolUse gate should allow
   # Try writing impl file before test fails → gate should BLOCK
   # Run test (fails) → PostToolUse should transition AWAITING_RED → RED_CONFIRMED
   # Write impl → gate should ALLOW (RED phase)
   # Run test (passes) → PostToolUse should transition → GREEN_CONFIRMED
   ```

2. **Verify global gate still blocks without /tdd:**
   ```
   # Edit a .py impl file WITHOUT invoking /tdd first
   # Global gate (settings.json) should STILL block — "No active TDD cycle"
   # But now uses terminal-isolated state and no stale cache
   ```

3. **Multi-terminal isolation:**
   ```
   # Terminal A: /tdd on test_foo.py → state in .claude/state/tdd/{terminal_A_id}/
   # Terminal B: /tdd on test_foo.py → state in .claude/state/tdd/{terminal_B_id}/
   # Verify no cross-contamination
   ```

4. **No stale state:**
   ```
   # Write test → run test (fail) → verify immediate RED_CONFIRMED
   # No 30-second delay from cache
   ```

5. **Run existing TDD tests if any exist in the codebase**

## Success Criteria + Documentation

**Must-have criteria:**
1. PreToolUse gate allows test file writes when /tdd is active
2. PreToolUse gate blocks impl file writes before test fails (RED phase enforcement)
3. PostToolUse transitions phases correctly: AWAITING_RED → RED_CONFIRMED → GREEN_CONFIRMED
4. State changes are immediately visible (no 30-second cache delay)
5. Multiple terminals working on same project have isolated state
6. Global gate still blocks non-/tdd file edits with terminal-isolated state

**Should-have criteria:**
1. Old state files are migrated to new format (not orphaned)
2. SessionEnd cleanup removes expired state files
3. No performance regression from removing cache
4. Hook execution time remains under 3 seconds for PreToolUse, 5 seconds for PostToolUse

**Documentation updates required:**
- Update `.claude/skills/tdd/SKILL.md` with hooks frontmatter documentation
- Document terminal isolation behavior in TDD skill docs
- Add migration notes for existing TDD users
- Update `.claude/README.md` if hook architecture is documented there

## Dependencies

**Required dependencies:**
- `.claude/hooks/__lib/terminal_detection.py` must exist and work correctly
- Claude Code version 2.1.0+ for skill-based hooks support
- Python 3.12+ for type hints in modified code

**Blocked by:**
- None identified

**Blocking:**
- None identified (this is an internal refactoring)

## Next Actions

0. **Verify terminal_detection dependency:**
   ```bash
   python -c "from .claude.hooks.__lib.terminal_detection import detect_terminal_id; print(detect_terminal_id())"
   ```

1. **Move plan to target directory:**
   ```bash
   mv "C:/Users/brsth/.claude/plans/twinkly-soaring-sunbeam.md" "P://.claude/skills/tdd/"
   ```

2. **Create/update README.md with plan link:**
   ```bash
   # Add to P://.claude/skills/tdd/README.md:
   # **Plan:** [plan-20250205-tdd-migration.md](twinkly-soaring-sunbeam.md)
   ```

3. **Run /r for deterministic pre-mortem validation:**
   ```
   /r "validate plan P://.claude/skills/tdd/twinkly-soaring-sunbeam.md"
   ```

4. **Adversarial review:**
   ```
   agent:adversarial-review - Review this plan for gaps, security issues, and architectural concerns
   ```

5. **Implement Step 1 (SKILL.md hooks frontmatter):** [R:1]
   ```bash
   # Edit P://.claude/skills/tdd/SKILL.md
   # Add hooks: section after line 15
   ```

6. **Implement Step 2 (Create skill hooks):** [R:1]
   ```bash
   mkdir -p P://.claude/skills/tdd/hooks
   # Create PreToolUse_tdd_gate.py, PostToolUse_tdd_state.py, SessionEnd_tdd_cleanup.py
   ```

7. **Implement Step 3 (Fix tdd_core.py):** [R:2]
   ```bash
   # Edit P://.claude/hooks/tdd_core.py
   # Remove cache (lines 407-496), add terminal isolation to _resolve_state_file()
   ```

8. **Implement Step 4 (Update settings.json):** [R:1]
   ```bash
   # Edit P://.claude/settings.json
   # Update pretooluse_tdd_gate.py path to skill hooks version
   ```

9. **Implement Step 5 (Remove TDDStateHook from router):** [R:1]
   ```bash
   # Edit P://.claude/hooks/posttooluse/__init__.py
   # Remove import line 37 and registration line 82
   ```

10. **Verification:**
    ```bash
    # Run through verification steps in plan
    # Test multi-terminal isolation
    # Verify no stale cache behavior
    ```

11. **Finalize plan:**
    ```
    /finalize P://.claude/skills/tdd/twinkly-soaring-sunbeam.md
    ```
