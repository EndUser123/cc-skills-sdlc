# Hooks/Skills Specialization of Generic Debugging Protocol

**Status**: Adopted 2026-03-11
**Version**: 1.0.0
**Domain**: Claude Code hooks and skills debugging
**Base Protocol**: GENERIC_PROTOCOL.md

---

## Domain Observables

What can be measured in the hooks/skills domain:

### Tool Events (Tier 3-4 evidence)
- `Skill()` tool invocations: timestamp, skill_name, arguments
- `Read()`/`Write()`/`Edit()` tool calls within skill execution
- Tool response: success/failure, returned data

### Hook Execution (Tier 3-4 evidence)
- Hook enabled/disabled state per hook type
- Hook process() method execution
- Hook stdout (data returned to Claude Code)
- Hook stderr (treated as error by Claude Code)

### Runtime State (Tier 2-3 evidence)
- State files: `P:/.claude/hooks/state/{hook-name}-state.json`
- Skill invocation log: `P:/.claude/state/skill_invocations.jsonl`
- Environment variables: `{HOOK_NAME}_ENABLED`

### Static Analysis (Tier 1 evidence)
- Hook file existence and structure
- Code review of hook logic
- Configuration files

---

## State Artifacts

Where system state is stored:

### Hook State
- **Location**: `P:/.claude/hooks/state/`
- **Format**: JSON files per hook type
- **Content**: `enabled` boolean, `executed_count`, `last_execution_timestamp`
- **Usage**: Track hook lifecycle and execution history

### Skill Invocation Log
- **Location**: `P:/.claude/state/skill_invocations.jsonl`
- **Format**: JSONL (one JSON object per line)
- **Content**:
  ```json
  {
    "timestamp": "ISO-8601",
    "skill_name": "skill-name",
    "arguments": {...},
    "session_id": "uuid",
    "terminal_id": "uuid"
  }
  ```
- **Usage**: Tier 3 evidence for skill execution claims

### Hook Registration
- **Authority**: `P:/.claude/settings.json` is the source of truth for which hooks are actually registered
- **Location**: `P:/.claude/hooks/{hook-type}/`
- **Format**: Python files with `*Hook` classes
- **Metadata**: Hook class attributes define behavior
  - `env_var`: Environment variable for enable/disable
  - `default_enabled`: Boolean
  - `tool_matcher`: Set of tool names to match
- **Rule**: Do not infer hook absence from `~/.claude/hooks`; inspect the registered commands in `P:/.claude/settings.json` first

---

## Pipeline Stages

### Skill Invocation Flow
1. **Agent invokes skill**: `Skill(tool="skill-name", args="...")`
2. **Skill file loads**: Python code executed
3. **Tool calls within skill**: Read/Write/Edit/Bash/etc.
4. **PostToolUse hooks trigger**: After each tool call
5. **Skill returns output**: Text response to agent

### Hook Execution Flow
1. **Hook type determined**: PreToolUse / PostToolUse / etc.
2. **Hook enabled check**: `env_var` or `default_enabled`
3. **Tool matcher check**: Does `tool_matcher` include current tool?
4. **process() method called**: With tool_name, tool_input, tool_response
5. **Stdout returned**: Modifications to tool response (if any)
6. **Stderr checked**: Any stderr = error (Claude Code behavior)

### Debugging Flow
1. **Observe symptom**: What went wrong? (skill failed, hook didn't execute)
2. **Identify observables**: What can be measured? (tool events, state files)
3. **Collect evidence**: Check logs, state files, runtime behavior
4. **Map mechanism → state → outcome**: What should happen vs what did
5. **Identify mismatch**: Where is the gap?
6. **Verify fix**: Test that fix resolves symptom

---

## Tier Mapping (Domain-Specific)

### Tier 4: Code Review + Runtime Verification
- **Requirements for hooks/skills**:
  - Code review: Hook/skill file shows correct logic
  - Runtime: Hook executes (verified in state file)
  - Verification: Actual log output or tool response shows expected behavior
  - **Example**: "PostToolUse hook `skill_invocation_logger_hook.py` logs Skill invocations to `skill_invocations.jsonl`"
    - Evidence: Code review shows logging logic (Tier 1)
    - Evidence: State file shows hook enabled (Tier 2)
    - Evidence: `skill_invocations.jsonl` contains new entries after Skill() call (Tier 4)

### Tier 3: Runtime State + Logs
- **Requirements for hooks/skills**:
  - Runtime: Hook enabled, state file exists
  - Logs: Log file shows expected entries
  - **Example**: "Skill invocation logger is working"
    - Evidence: `skill_invocations.jsonl` file exists with recent timestamps
    - Evidence: State file shows hook executed N times

### Tier 2: Runtime State Only
- **Requirements for hooks/skills**:
  - Hook enabled: State file shows `enabled: true`
  - No log verification: Can't confirm logs have correct content
  - **Example**: "Hook is registered and enabled"
    - Evidence: State file at `P:/.claude/hooks/state/hook-name-state.json` shows `enabled: true`

### Tier 1: Static Analysis
- **Requirements for hooks/skills**:
  - Code review: Hook file exists and has correct structure
  - No runtime check: Haven't verified hook actually executes
  - **Example**: "Hook should work based on code review"
    - Evidence: Read `hook-file.py`, shows correct class definition and tool_matcher

### Tier 0: No Evidence (Speculation)
- **Requirements**: None
- **Example**: "This architecture should support X"
  - Evidence: None (claim based on design intent, not verification)

---

## Common Failure Modes

### 1. Hook Not Executing
**Symptoms**: Hook file exists but state file shows no executions
**Diagnosis**:
- Check hook enabled: Is `env_var` set or `default_enabled=True`?
- Check tool_matcher: Does it include the tool being called?
- Check hook type: Is it the right hook type for the event? (PreToolUse vs PostToolUse)
**Verification**: Trigger matching tool, check state file updates

### 2. Hook Producing Errors
**Symptoms**: Claude Code reports hook error or shows stderr
**Diagnosis**:
- Check hook stderr: Hook wrote to stderr instead of stdout
- Check hook exception: Unhandled exception in process() method
- Check hook dependencies: Missing imports or unavailable resources
**Verification**: Fix hook code, verify Claude Code no longer shows error

### 3. Skill Not Found
**Symptoms**: `Skill()` tool call returns "skill not found" error
**Diagnosis**:
- Check skill path: Is skill at `P:/.claude/skills/{skill-name}/SKILL.md`?
- Check skill name: Does invocation match directory name exactly?
- Check skill permissions: Is file readable?
**Verification**: `Skill()` call succeeds, skill executes

### 4. Circular Dependency
**Symptoms**: Phase 1 requires Phase 2, Phase 2 requires Phase 1
**Diagnosis**:
- Trace dependencies: What does each phase depend on?
- Identify minimal viable: What can be deployed independently?
**Verification**: Deploy minimal component, verify it works alone

### 5. Proxy Mismatch
**Symptoms**: Measuring proxy instead of actual observable
**Diagnosis**:
- Identify observable: What's the actual thing we care about? (e.g., hook executed)
- Identify proxy: What are we measuring instead? (e.g., file exists)
- Check validity: Does proxy accurately reflect observable?
**Verification**: Replace proxy with direct observable measurement

### 6. Wrong Hook Root
**Symptoms**: RCA concludes hooks do not exist or are advisory only because the wrong directory was inspected
**Diagnosis**:
- Check registered hooks first: `P:/.claude/settings.json`
- Confirm implementation path next: `P:/.claude/hooks/`
- Ignore `~/.claude/hooks` unless the settings file explicitly points there
**Verification**: The registered command in settings matches the implementation file path you inspected

### 7. Import Path Issues
**Symptoms**: `ImportError: attempted relative import with no known parent package`
**Diagnosis**:
- Check import path: Are you importing from package subdirectory?
- Check sys.path: Does Python know where package parent is?
- **Fix**: Add package parent to sys.path, not subdirectory
**Verification**: Import succeeds, test passes

### 8. Pytest Hanging
**Symptoms**: pytest test never completes, appears stuck
**Diagnosis**:
- Check cleanup: Is test properly cleaning up resources?
- Check background tasks: Are subprocesses or threads still running?
- Check timeouts: Is test waiting indefinitely?
**Verification**: All tests complete in reasonable time

### 9. Multi-Terminal Contamination
**Symptoms**: Test fails when run in parallel with other tests
**Diagnosis**:
- Check shared state: Are tests writing to same files?
- Check isolation: Do tests have unique identifiers?
- Check cleanup: Do tests clean up after themselves?
**Verification**: Run tests in parallel, all pass

---

## Case Studies

### Case 1: Skill Invocation Logger (Phase 2)
**Issue**: Needed to track Skill() invocations for debugging
**Mechanism**: PostToolUse hook with `tool_matcher={"Skill"}`
**State**: Hook enabled, state file tracks executions
**Outcome**: JSONL log file with skill invocation details
**Tier**: Tier 4 (code + runtime + log verification confirmed)
**Lessons**: Direct observable (tool event) better than proxy (file timestamp)

### Case 2: Import Path Bug in Tests
**Issue**: Tests failing with "attempted relative import" error
**Mechanism**: Tests importing from `P:/.claude/hooks/posttooluse`
**State**: Hook file uses `from .base import PostToolUseHook`
**Outcome**: Import fails because Python doesn't know package parent
**Fix**: Add `P:/.claude/hooks` to sys.path, import as `from posttooluse.skill_invocation_logger_hook import`
**Tier**: Tier 4 (fix verified by pytest: 70/70 passing)
**Lessons**: Python packages need parent directory in sys.path for relative imports

### Case 3: Circular Dependency in 3-Phase Design
**Issue**: Phase 1 (confidence tags) requires Phase 2 (instrumentation) for enforcement
**Mechanism**: Can't enforce Tier 3 claims without Tier 3 evidence collection
**State**: Design document describes phases sequentially
**Outcome**: Circular dependency - can't deploy Phase 1 without Phase 2
**Fix**: Refactor to generic-first architecture - universal protocol doesn't reference domain instrumentation
**Tier**: Tier 4 (architecture review approved refactored design)
**Lessons**: Generic-first approach resolves circular dependencies

---

## Specialization Notes

### Differences from Generic Protocol
- **Tier 3a/3b split removed**: Generic protocol uses single Tier 3 (85%)
  - Original design had Tier 3a (80%, runtime state only) and Tier 3b (85%, runtime + logs)
  - Refactored out due to cognitive load vs marginal value
- **Hook stderr behavior**: Claude Code treats any hook stderr as error
  - Hooks must use stdout for data output
  - Hooks must silence or suppress stderr
- **Import path requirements**: Python hook files require package parent in sys.path
  - Affects test imports and module loading

### When to Use This Specialization
Use this specialization when debugging issues related to:
- Hook execution or non-execution
- Skill invocation failures
- Claude Code tool behavior
- pytest test failures for hook/skill code
- State file inconsistencies

### When to Use Generic Protocol
Use generic protocol when:
- Issue is not specific to hooks/skills
- Working with different LLM system
- Need universal debugging principles
- Creating new domain specialization

---

## Maintenance

**Version history**:
- 2026-03-11: Initial specialization created from generic protocol

**Related files**:
- `GENERIC_PROTOCOL.md`: Base protocol
- `SKILL.md`: rca skill (uses this specialization)
- `../../hooks/tests/test_debugRca_protocols.py`: Automated tests for protocol compliance
- `../../hooks/posttooluse/skill_invocation_logger_hook.py`: Phase 2 instrumentation
