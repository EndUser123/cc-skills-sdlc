# /refactor - Multi-File Refactoring Orchestrator

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Advanced refactoring orchestration with rollback automation, test generation, synergy detection, and incremental refactoring support.

## 🎯 Purpose

Transform large-scale refactoring from a risky manual process into a safe, automated, and observable workflow. The refactor skill provides:

- **Rollback Automation**: Git-based safety nets with auto-generated rollback scripts
- **Test Generation**: TDD phases (RED → GREEN → REFACTOR) with automated test scaffolding
- **Synergy Detection**: Cross-file pattern analysis for DRY violations and extraction opportunities
- **Complexity Triage**: Risk-based prioritization using cyclomatic complexity scoring
- **Incremental Refactoring**: State persistence for resumable multi-session refactoring
- **Configuration Management**: CLI + YAML/JSON config with sensible defaults

## 🚀 Quick Start

### Claude Code Skill

```bash
# Create junction (Windows - no admin required)
# Run from the skills parent directory
mklink /J "$CLAUDE_ROOT/skills\refactor" "$CLAUDE_PLUGIN_ROOT/skills\refactor"

# Or create symlink (macOS/Linux)
ln -s "$(pwd)" ~/.claude/skills/refactor
```

The skill is accessed via `/refactor` in Claude Code.

### Three Deployment Models

**IMPORTANT**: This package supports three different deployment modes. Choose the right one for your use case.

#### 1. SKILLS (Dev Deployment) ⭐ **Recommended for Development**

**For**: When you're actively developing this package and want instant feedback.

**Setup:**
```powershell
# Windows (Junction - No admin required)
# For plugins with skills: Junction to the skills/ subdirectory

# IMPORTANT: Sanitize the junction name to remove problematic characters
$junctionName = "refactor" -replace '[@?*:<>|+]', ''

New-Item -ItemType Junction -Path "$CLAUDE_ROOT/skills\$junctionName" -Target "$CLAUDE_PLUGIN_ROOT/skills\refactor"
```

**Key points:**
- ✅ Edit in `P:\\\\\\packages/cc-skills-sdlc/skills/refactor/`, changes work immediately
- ✅ No reinstallation required - skills auto-discover from `P:\\\\\\.claude/skills/`
- ✅ Perfect for active development

#### 2. HOOKS (Dev Deployment - Hook Files Only)

**For**: When this package has hook files (`.py` files in `scripts/hooks/`) you want to test.

**Setup:**
```powershell
# Symlink individual hook files to P:\\\\\\.claude/hooks/
cd P:\\\\\\.claude/hooks
cmd /c "mklink HookName.py P:\\\\\\packages/cc-skills-sdlc/skills/refactor/scripts/hooks/HookName.py"
```

#### 3. PLUGINS (End User Deployment)

**For**: Distributing this package to other users via marketplace or GitHub.

**Setup:**
```bash
# End users install via /plugin command
/plugin P:\\\\\\packages/cc-skills-sdlc/skills/refactor
```

## 🏗️ Architecture

### System Overview

```mermaid
graph TD
    A[User invokes /refactor] --> B[Skill Interface]
    B --> C{Mode Selection}
    C -->|Discovery| D[Pattern Detection]
    C -->|TDD| E[Test Generation]
    C -->|Rollback| F[Git State Capture]
    C -->|Analysis| G[Complexity Triage]
    C -->|Incremental| H[State Persistence]

    D --> I[Synergy Detector]
    E --> J[Test Generator]
    F --> K[Rollback Manager]
    G --> L[Complexity Scorer]
    H --> M[State Manager]

    I --> N[Report Generation]
    J --> N
    K --> N
    L --> N
    M --> N

    style B fill:#e1f5ff
    style N fill:#c8e6c9
```

### Module Structure

```
refactor/
├── SKILL.md                 # Skill definition and usage
├── __init__.py              # Public API exports
├── README.md                # This file
├── CHANGELOG.md             # Version history
├── LICENSE                  # MIT License
├── plan.md                  # Implementation roadmap
│
├── lib/                     # Python skill modules
│   ├── plan_review.py       # Plan review and validation
│   └── refactor_plan.py     # Refactoring plan generation
│
└── scripts/                 # Utility scripts
    ├── code_scanner.py      # Code analysis scanner
    └── install-dev.bat      # Windows junction automation
```

### Key Components

| Module | Responsibility | Key Features |
|--------|---------------|--------------|
| **RefactorConfig** | Configuration management | CLI + YAML/JSON, threshold customization |
| **RollbackManager** | Git-based safety | State capture, rollback script generation, cleanup |
| **TestGenerator** | TDD orchestration | RED → GREEN → REFACTOR phases, test result tracking |
| **SynergyDetector** | Cross-file analysis | DRY violation detection, extraction opportunity finding |
| **ComplexityTriage** | Risk prioritization | Cyclomatic complexity scoring, priority levels (P0-P3) |
| **StateManager** | Incremental progress | Terminal-isolated state persistence, atomic writes |

## 📖 Usage

### As Claude Code Skill

Invoke the refactor skill from Claude Code:

```bash
# Discover refactoring opportunities
/refactor

# Analyze specific files
/refactor --files src/**/*.py

# Enable incremental mode
/refactor --incremental --state-file P:\\\\\\.claude/state/refactor/refactor_<terminal_id>.json

# Custom complexity threshold
/refactor --cc-threshold 20
```

### As Python Library

```python
from pathlib import Path
from __csf.src.refactor import (
    RollbackManager,
    TestGenerator,
    SynergyDetector,
    ComplexityTriage,
    get_config,
)
from scripts import StateManager

# Load configuration
config = get_config(
    cc_threshold=20,
    incremental_mode=True,
    state_file=None  # uses the terminal-isolated default path
)

# Initialize components
rollback_mgr = RollbackManager(branch_name="refactor-safety")
test_gen = TestGenerator()
synergy_detector = SynergyDetector(min_similarity=0.75)
complexity_triage = ComplexityTriage(cc_threshold=20)
state_mgr = StateManager()

# Example: Rollback workflow
rollback_plan = rollback_mgr.capture_state(
    files=["src/module.py"],
    message="Before refactoring module"
)
print(f"Rollback branch: {rollback_plan.branch_name}")

# Example: TDD workflow
red_result = test_gen.red_phase(
    test_files=["tests/test_module.py"],
    expected_failures=3
)

green_result = test_gen.green_phase(
    implementation_files=["src/module.py"],
    timeout_seconds=300
)

# Example: Synergy detection
files = [Path("src/a.py"), Path("src/b.py")]
code_map = {f: f.read_text() for f in files}
synergy_report = synergy_detector.detect_patterns(files, code_map)

print(f"DRY violations: {synergy_report.dry_violations}")
print(f"Extraction opportunities: {synergy_report.extraction_opportunities}")
```

## 🧪 Testing

### Run All Tests

```bash
# Full test suite
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=__csf.src.refactor --cov-report=html

# Specific module
pytest tests/refactor/test_config.py -v
```

### Test Coverage

- **Configuration**: CLI overrides, file loading, defaults
- **Rollback Manager**: State capture, script generation, cleanup
- **Test Generator**: TDD phases, result tracking, timeouts
- **Synergy Detector**: Pattern detection, similarity calculation
- **Complexity Triage**: Scoring, prioritization, threshold flags
- **State Manager**: Persistence, thread safety, atomic writes

Current coverage: **[Coverage badge after CI run]**

## 🔧 Configuration

### CLI Arguments

```bash
/refactor [OPTIONS]

Options:
  --cc-threshold INT       Cyclomatic complexity threshold (default: 15)
  --incremental            Enable incremental refactoring mode
  --state-file PATH        State file for incremental mode (defaults to terminal-isolated path)
  --min-similarity FLOAT   Minimum similarity for synergy detection (default: 0.7)
  --config-file PATH       YAML/JSON configuration file
  --help                   Show help message
```

### Configuration File

Create `refactor-config.yaml`:

```yaml
# Complexity thresholds
cc_threshold: 15
usage_weight: 1.0
risk_weight: 1.0

# Incremental mode
incremental:
  enabled: true
  state_file: null  # defaults to the terminal-isolated path

# Synergy detection
synergy:
  min_similarity: 0.7
  enable_extraction_detection: true

# Test generation
tdd:
  timeout_seconds: 300
  max_attempts: 3

# Rollback
rollback:
  auto_cleanup: true
  branch_prefix: "refactor-"
```

Load in code:

```python
config = get_config(config_file=Path("refactor-config.yaml"))
```

## 🎨 Features

### 1. Rollback Automation

Automatically creates git branches and rollback scripts before refactoring:

```python
mgr = RollbackManager()
plan = mgr.capture_state(files=["src/module.py"], message="Pre-refactor")
# ... perform refactoring ...
if something_wrong:
    mgr.apply_rollback(plan)
else:
    mgr.cleanup(plan)
```

**Generates executable rollback script:**
```bash
#!/bin/bash
# Auto-generated rollback script
git checkout refactor-safety-20250111-174700
git branch -D main  # Switch back to main
```

### 2. Test Generation (TDD)

Automated RED → GREEN → REFACTOR cycle:

```python
gen = TestGenerator()

# RED: Write failing tests
red = gen.red_phase(["tests/test_feature.py"])
assert not red.success  # Tests should fail

# GREEN: Minimal implementation
green = gen.green_phase(["src/feature.py"])
assert green.success

# REFACTOR: Cleanup while tests pass
refactor = gen.refactor_phase(timeout_seconds=300)
assert refactor.success
```

### 3. Synergy Detection

Find cross-file refactoring opportunities:

```python
detector = SynergyDetector(min_similarity=0.8)

files = [Path("src/auth.py"), Path("src/user.py")]
code_map = {f: f.read_text() for f in files}

report = detector.detect_patterns(files, code_map)

for pattern in report.patterns:
    print(f"Pattern: {pattern.pattern_type}")
    print(f"Similarity: {pattern.similarity:.2f}")
    print(f"Files: {pattern.files}")
```

**Detects:**
- DRY violations (duplicate code blocks)
- Similar structures (extraction opportunities)
- Cross-cutting concerns (shared patterns)

### 4. Complexity Triage

Prioritize refactoring by risk:

```python
triage = ComplexityTriage(cc_threshold=15)

findings = [
    {"code": "def complex_func(): ...", "file": "src/a.py", "line": 42},
    {"code": "def simple_func(): ...", "file": "src/b.py", "line": 10},
]

scores = triage.prioritize(findings)

for score in scores:
    print(f"{score.file_path}:{score.line_number}")
    print(f"  CC: {score.cyclomatic_complexity}")
    print(f"  Risk: {score.risk_score:.2f}")
    print(f"  Priority: {score.priority}")
```

**Priority Levels:**
- **P0**: CC >= 30 (Critical complexity)
- **P1**: CC >= 15 (High complexity)
- **P2**: CC >= 8 (Medium complexity)
- **P3**: CC < 8 (Low complexity)

### 5. Incremental Refactoring

Resumable multi-session refactoring with state persistence:

```python
mgr = StateManager()

# Load previous state
state = mgr.load_state()
print(f"Completed: {len(state.completed_findings)}")
print(f"In Progress: {len(state.in_progress_findings)}")

# Mark items
mgr.mark_in_progress("finding-123")
# ... work on finding-123 ...
mgr.mark_completed("finding-123")

# Get pending work
all_findings = ["finding-123", "finding-456", "finding-789"]
pending = mgr.get_pending_findings(all_findings)
print(f"Remaining: {pending}")
```

**Thread-safe atomic writes** prevent corruption from concurrent access.

## 📊 Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Rollback capture | < 1s | Git branch creation |
| Synergy detection | 2-10s | Depends on file count |
| Complexity triage | < 1s | Linear scan |
| State persistence | < 100ms | Atomic file write |

**Optimization Tips:**
- Use `--cc-threshold` to filter low-complexity files early
- Limit synergy detection to specific directories
- Enable incremental mode for large codebases

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/refactor-skill.git
cd refactor-skill

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v

# Run linting
ruff check .
ruff format .
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🔗 Related Skills

- **[/code](https://github.com/yourusername/code-skill)** - Feature development workflow
- **[/arch](https://github.com/yourusername/arch-skill)** - Architecture advisor
- **[/trace](https://github.com/yourusername/trace-skill)** - Code verification
- **[/synergy](https://github.com/yourusername/synergy-skill)** - Cross-file pattern detection

## 📚 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## 🙏 Acknowledgments

Built with:
- [Claude Code](https://claude.ai/code) - AI-assisted development
- [Python 3.12+](https://www.python.org/) - Type hints, dataclasses, pathlib
- [pytest](https://docs.pytest.org/) - Testing framework
- [ruff](https://github.com/astral-sh/ruff) - Linting and formatting

---

**Version**: 1.0.0
**Status**: Production Ready ✅
