# UCI Workflow Details

## 1. Scope Detection

The orchestrator automatically detects the review scope:
1. User-specified scope (`--scope=main...HEAD`)
2. Feature branch -> `git diff main...HEAD`
3. Staged changes -> `git diff --staged`
4. Latest commit -> `git show HEAD`

## 2. Intelligent Mode Detection

The mode detector analyzes context signals and selects appropriate mode:
- Collects signals: file count, line count, risk indicators, file types
- Calculates risk score from paths (auth, security, payments, etc.)
- Selects mode: triage/standard/deep/comprehensive
- Respects `--lite` (triage) and `--full` (comprehensive) override flags

## 3. Agent Selection

Based on detected mode, the orchestrator selects agents:
- **triage**: logic, tests, security
- **standard**: logic, tests, security, performance
- **deep**: All standard + conventions, quality, compliance, qa
- **comprehensive**: All deep + simplification, rca, failure-modes, deployment-safety, python-modernization, test-quality-roi

## 4. Parallel Execution

The orchestrator runs selected agents in parallel using Task tool calls:
- Each agent receives the same code context
- Agents generate findings with line-number evidence
- Circuit breaker monitors LLM provider health

## 5. Finding Aggregation

The formatter aggregates and enhances findings:
- Cross-agent validation (same location confirmed by multiple agents)
- Impact/Effort calculation
- Pre-existing issue detection
- Three-tier verdict synthesis

## 6. Output Generation

Results formatted as requested:
- **markdown**: Human-readable report with verdict, findings, recommendations
- **json**: Machine-readable with structured findings metadata
- **summary**: High-level verdict with top issues

## Assessment/Dry-Run Mode

- `--assessment`: Analyze code without generating output file
- `--dry-run`: Show which agents would run and scope, without execution

## Circuit Breaker

The circuit breaker pattern prevents cascading LLM failures:
- Tracks failure rates per provider
- Opens circuit after threshold exceeded
- Allows half-open state for testing recovery
- Automatic fallback to alternative providers
