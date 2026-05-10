# rca Tier 1 - Python Package

Evidence saturation detection, phase state persistence, and hypothesis scoring for root cause analysis debugging workflows.

## Version

**v1.0.0** - Tier 1 Implementation

## Overview

rca provides systematic debugging capabilities through:

- **Evidence Saturation Detection** - Detects when sufficient evidence has been gathered
- **Phase State Persistence** - Manages resumable RCA sessions
- **Tool Availability Gate** - Ensures required tools are available
- **Hypothesis Scoring** - Bayesian updating for hypothesis confidence
- **Local-Only Fallback Mode** - Quality estimation when web tools unavailable

## Installation

```bash
pip install rca
```

Or from source:

```bash
cd P:\\\\\\packages/rca
pip install -e .
```

## Module Reference

### Evidence Saturation (`evidence_saturation.py`)

Detects when evidence gathering has reached saturation point using semantic similarity and Jaccard keyword overlap.

```python
from rca import EvidenceSaturationDetector

detector = EvidenceSaturationDetector(threshold=0.75)

# Check if new evidence is redundant
is_saturated = detector.check_saturation(
    existing_evidence=["database timeout", "connection pool exhausted"],
    new_evidence=["database connection issues"]
)

# Detect diminishing returns in evidence history
history = ["error in auth", "auth failure", "authentication problem"]
is_diminishing = detector.detect_diminishing_returns(history)
```

### Phase State Manager (`phase_state_manager.py`)

Manages persistence of phase outputs for resumable RCA sessions.

```python
from rca import PhaseStateManager

manager = PhaseStateManager()

# Save phase output
state_id = manager.save("gather", {"evidence": [...]}, "session-123")

# Restore phase state
state = manager.restore(state_id)

# List completed phases
phases = manager.list_phases("session-123")  # ["gather", "isolate"]

# Get resume point
next_phase = manager.get_resume_point("session-123")  # "hypothesize"

# Export entire session
export = manager.export_session("session-123")
```

### Hypothesis Scorer (`hypothesis_scorer.py`)

Bayesian updating for hypothesis confidence tracking with weighted ranking.

```python
from rca import HypothesisScorer

scorer = HypothesisScorer()

# Set prior probability
scorer.set_prior("database_leak", 0.3)

# Update with evidence
scorer.update("database_leak", likelihood_ratio=2.0, evidence="Found connection leaks")

# Get confidence
confidence = scorer.get_confidence("database_leak")  # 0.6

# Rank hypotheses
hypotheses = [
    {"name": "database_leak", "reproducibility": 0.8, "recency": 0.5, "impact": 0.9},
    {"name": "cache_issue", "reproducibility": 0.5, "recency": 0.9, "impact": 0.3},
]
ranked = scorer.rank(hypotheses)
```

### Local Fallback Mode (`local_fallback_mode.py`)

Quality estimation and tool adaptation when web tools are unavailable.

```python
from rca import LocalFallbackMode, estimate_quality_coverage

# Check available tools
mode = LocalFallbackMode()  # Auto-detects local-only mode
tools = mode.get_available_tools()  # ["Grep", "Read", "Bash"]

# Estimate quality coverage
quality = estimate_quality_coverage(
    issue_type="syntax_error",
    available_tools=tools
)

# Adapt phase for local workflow
adapted = mode.adapt_phase("gather", {
    "description": "Gather evidence from logs",
    "required_tools": ["WebSearch", "Grep"]
})
```

### Tool Checker (`tool_checker.py`)

Detects available tools for rca execution.

```python
from rca.tool_checker import check_tool_availability

availability = check_tool_availability()

if availability["available"]:
    print("All required tools available")
else:
    print(f"Missing tools: {availability['missing']}")
    print(f"Mode: {availability['mode']}")  # "local" or "full"
```

### Quality Estimator (`quality_estimator.py`)

Estimates analysis quality based on issue type and available tools.

```python
from rca import QualityEstimator

estimator = QualityEstimator()

# Calculate coverage score
score = estimator.calculate_coverage(
    issue_type="runtime_error",
    available_tools=["Grep", "Read", "Bash"],
    evidence_count=10
)

# Get quality summary
summary = estimator.get_quality_summary(score)
```

### Confidence Tracker (`confidence_tracker.py`)

Low-level confidence tracking with Bayesian updates.

```python
from rca import ConfidenceTracker

tracker = ConfidenceTracker()

# Set prior
tracker.set_prior("hypothesis_1", 0.5)

# Bayesian update
tracker.bayesian_update("hypothesis_1", likelihood_ratio=2.5)

# Get posterior
posterior = tracker.get_posterior("hypothesis_1")  # ~0.71

# Batch update
tracker.batch_update({
    "hypothesis_1": 2.0,
    "hypothesis_2": 0.5
})
```

### Local Tool Adapter (`local_tool_adapter.py`)

Adapts remote tools to local equivalents.

```python
from rca import LocalToolAdapter

adapter = LocalToolAdapter()

# Local search (replaces WebSearch)
results = adapter.search("error pattern", path="P:\\\\\\src")

# Local read (replaces remote file fetch)
content = adapter.read("P:\\\\\\src/file.py")

# Local execute (replaces remote execution)
output = adapter.execute("python test.py")
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBUGRCA_LOCAL_ONLY` | unset | Enable local-only mode (set to "1") |
| `DEBUGRCA_SATURATION_THRESHOLD` | 0.75 | Evidence saturation threshold (0.0-1.0) |
| `DEBUGRCA_STATE_DIR` | `P:\\\\\\.claude/state/rca` | State directory for persistence |
| `DEBUGRCA_TOOL_GATE_ENABLED` | true | Enable tool availability gate |

## Tool Requirements

### Full Mode
- Grep (code search)
- Read (file reading)
- Bash (command execution)
- WebSearch (remote search) - optional but recommended

### Local-Only Mode
- Grep (code search)
- Read (file reading)
- Bash (command execution)
- WebSearch not required

## Testing

```bash
# Run all tests
cd P:\\\\\\packages/rca
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Run specific test module
pytest tests/test_evidence_saturation.py -v
```

## Coverage

Current test coverage: **83%** (175 tests passing)

## License

MIT License - See LICENSE file for details.
