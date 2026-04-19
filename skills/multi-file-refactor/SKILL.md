---
name: multi-file-refactor
description: Multi-file refactoring with synergy detection and confidence scoring.
version: 1.0.0
status: stable
category: development
tags: ['refactoring', 'multi-file', 'code-analysis', 'python-2025', 'synergy-detection']
triggers:
  - '/multi-file-refactor'
aliases:
  - '/multi-file-refactor'

suggest:
  - /refactor
  - /test
  - /comply
---

## Code Editing Patterns

For Python code editing patterns and anti-patterns:
- **Authority**: /p Neural Cache
- **Example**: `/search "ThreadPoolExecutor KeyboardInterrupt immediate cleanup"`
- **Example**: `/search "string manipulation AST LibCST code editing"`

Reflect automatically propagates code editing learnings to /p. Query CKS for patterns.



# Multi-File Refactor

**Role**: Detect cross-file refactoring opportunities that benefit multiple files simultaneously, avoiding the "separate UserService in 3 files" problem.

## Purpose

Detect cross-file refactoring synergies to avoid duplicate extractions.

## Project Context

### Constitution/Constraints
- Evidence-first: Verify file paths before analysis
- Source code location rules: Always search in src/, never project root

### Technical Context
- Synergy detection with confidence scoring (80% default threshold)
- Priority ordering: P0 (bugs) → P1 (error handling) → P2 (DRY) → P3 (conventions)
- Parallel execution: 3 code-reviewer agents for 3+ files

### Architecture Alignment
- Auto-invokes /p for .py files
- Integrates with /aid for single-file deep dives
- Uses /design for architecture decision framework

## Your Workflow

1. Detect file types → Auto-invoke /p if .py
2. Validate all file paths contain src/ (reject .venv/, node_modules/)
3. Read all specified files
4. If 3+ files: Launch 3 parallel code-reviewer agents with different focus
5. Perform synergy detection with confidence scoring
6. Output findings in mandatory priority order (P0 → P1 → P2 → P3)

## Validation Rules

### Prohibited Actions
- Do NOT analyze files outside src/ directory
- Do NOT accept paths with .venv/, node_modules/, __pycache__/
- Do NOT use single agent for 3+ file analysis
- Do NOT report findings out of priority order
- Do NOT skip confidence filtering (unless --no-confidence-filter)

## When to Use

Use `/refactor` (invokes this skill) when you need to:
- Find bugs and race conditions across multiple files
- Extract shared logic into common modules
- Merge similar interfaces
- Consolidate scattered patterns (config access, error handling)
- Standardize inconsistent patterns across files

## Key Difference from Single-File Analysis

**Single-file (e.g., `/aid refactor`)**:
```
file_a.py: "Extract UserService class"
file_b.py: "Extract UserService class"
file_c.py: "Extract UserService class"
→ Result: 3 SEPARATE UserService classes created ❌
```

**Multi-file (this skill)**:
```
Detects: All 3 files need UserService
Synergy: Create ONE shared UserService
→ Result: Single shared module, 3 files import it ✅
```

## ⚡ EXECUTION DIRECTIVE

**CRITICAL: Source Code Location Rules**

When searching for files (e.g., "largest N files", "all Python files"):
1. **USE /search FIRST** - Don't let agents discover files themselves
2. **ALWAYS search in `src/` directory** - Never search project root
3. **Comprehensive EXCLUDE list**:
   - Virtual envs: `.venv/`, `venv/`, `node_modules/`
   - Python cache: `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.hypothesis/`
   - Build artifacts: `dist/`, `build/`, `*.egg-info/`, `.eggs/`
   - VCS: `.git/`, `.sl/`
   - IDE: `.vscode/`, `.idea/`
   - Coverage: `.coverage/`, `htmlcov/`
   - Data/runtime: `data/`, `logs/`, `tmp/`, `temp/`
   - Media: `*.mp4`, `*.mkv`, `*.avi`, `*.mp3`
4. **For yt-fts**: Search `P:\projects\yt-fts\src\` NOT `P:\projects\yt-fts\`
   - **Also exclude**: `yt-fts/data/` (contains DB files, videos, large media)
5. **For __csf**: Search `P:\__csf\src\` NOT `P:\__csf\`

**Parallel Execution for Multi-File Analysis**

When analyzing 3+ files:
- **Launch 3 parallel code-reviewer agents** with different focus areas:
  1. **Simplicity/DRY focus** - Code clarity, duplication
  2. **Bugs/Logic focus** - Functional correctness
  3. **Conventions focus** - Project patterns
- Aggregate findings - do NOT use single agent

**Execution Flow**:
1. Detect if files are .py → Auto-invoke /p skill FIRST
2. **VALIDATE**: Check all file paths contain `src/` - reject if `.venv/`, `node_modules/` found
3. Read ALL specified files
4. If 3+ files: Launch 3 parallel code-reviewer agents
5. Perform synergy detection with confidence scoring
6. Output findings in the specified format
7. DO NOT echo documentation - execute the analysis

**Validation Gate Example:**
```
Returned files:
- .venv/Lib/site-packages/torch/testing.py  ❌ REJECT (not in src/)
- src/yt_fts/download/handler.py          ✅ ACCEPT (in src/)
```

**Stop reading and start executing. The user invoked `/refactor` to get work done.**

---

## Execution Flow

When `/refactor <path>` is invoked:

1. **Detect file types** - Check if .py files → Auto-invoke `/p` first
2. **Read all specified files**
3. **Apply smart defaults**:
   - Confidence filtering (80% threshold, use `--no-confidence-filter` to disable)
   - Recent mode if git repo has changes (use `--no-recent` to disable)
   - Exploration for >20 files (use `--no-explore` to disable)
   - Multi-review ON by default (use `--no-multi-review` to disable)
4. **Detect synergies** - Cross-file duplicate detection, interface consolidation
5. **PRIORITIZE findings**: Bugs (P0) → Error handling (P1) → DRY (P2) → Conventions (P3)
6. **Output findings** - In specified format with priority ordering


## Priority Ranking (MANDATORY ORDER)

**FINDINGS MUST BE REPORTED IN THIS ORDER:**

| Priority | Category | Examples | Why First |
|----------|----------|----------|-----------|
| **P0 - CRITICAL** | Bugs & Race Conditions | Thread safety, data races, crashes | Breaks production |
| **P1 - HIGH** | Error Handling | Bare except, swallowed errors | Hides bugs |
| **P2 - MEDIUM** | DRY Violations | Duplicate code, extract opportunities | Maintenance burden |
| **P3 - LOW** | Conventions | Type hints, formatting, naming | Code quality |

**Output format MUST respect this ordering.** Bugs are always reported before DRY issues.

## Synergy Types

| Type | Priority | Description | Detection Method |
|------|----------|-------------|------------------|
| `bug` | **P0** | Race conditions, data races, crashes | Static analysis |
| `error` | **P1** | Bare except, swallowed errors | Exception analysis |
| `extract` | **P2** | Extract common code to shared module | AST-based comparison |
| `merge` | **P2** | Merge similar interfaces | Protocol comparison |
| `consolidate` | **P2** | Consolidate scattered patterns | Semantic similarity |
| `standardize` | **P3** | Standardize inconsistent patterns | Pattern variation |
| `restructure` | **P2** | Restructure to break cycles | Import graph DFS |

## Confidence Scoring

Each synergy scored 0-100:

| Score | Meaning | Default Action |
|-------|---------|----------------|
| 80-100 | Definite pattern - verified duplicate | Report |
| 50-79 | Needs verification | Report with `--include-uncertain` |
| 0-49 | Speculative - high false-positive risk | Suppress |

**Scoring factors:**
- Structural similarity: 40%
- Lines affected: 25%
- Cross-file consistency: 20%
- Type match: 15%

## Output Format

```markdown
## Refactoring Analysis

**Files analyzed**: N
**Issues found**: N bugs, N error handling, N DRY, N conventions
**Estimated effort**: X-Y hours

---

### P0 - CRITICAL (Fix First)

#### [BUG-001] Thread-Local Race Condition
**Files**: `file_a.py:1384`
**Issue**: Multiple threads can overwrite `_thread_local`
**Impact**: Data corruption, crashes
**Confidence**: 95%
**Effort**: medium (1 hour)

---

### P1 - HIGH (Error Handling)

#### [ERROR-001] Bare Except Swallows Errors
**Files**: `file_b.py:795`
**Issue**: `except Exception: pass` hides failures
**Impact**: Debugging impossible
**Confidence**: 88%
**Effort**: low (15 minutes)

---

### P2 - MEDIUM (DRY & Architecture)

#### [EXTRACT-001] Extract Common Validation Logic
**Files**: `file_a.py`, `file_b.py`, `file_c.py`
**Benefit**: Eliminates X lines of duplication
**Confidence**: 92%
**Effort**: low (15 minutes)

[Code details...]
```

## Integration with Other Tools

| Tool | When Used |
|------|-----------|
| `/p` | Auto-invoked for .py files |
| `/aid refactor` | For single-file deep dive |
| `code-explorer` | With `--explore` flag |
| `code-reviewer` | With `--multi-review` (default ON) |

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--priority P` | Filter by priority level (P0, P1, P2, P3) |
| `--synergy-type TYPE` | Filter by type (bug, error, extract, merge, etc.) |
| `--min-confidence N` | Only show synergies >= N (default: 80) |
| `--max-effort LEVEL` | Filter by effort (low, medium, high) |
| `--no-confidence-filter` | Disable confidence filtering |
| `--no-recent` | Disable recent mode (analyze all files) |
| `--no-explore` | Disable exploration phase |
| `--no-multi-review` | Disable multi-agent review |
| `--include-uncertain` | Include 50-79% confidence suggestions |
| `--include-complexity` | Include complexity analysis |
| `--include-aid` | Run /aid refactor on each file |

## See Also

- `/aid` - Single-file refactoring analysis
- `//p` - Python 2025 standards (auto-invoked)
- `/complexity` - Code complexity analysis
- `/design` - Architecture decision framework
