"""
Unified Code Inspection Library

Core modules for /uci skill:
- agent_registry: Agent selection and configuration
- scope_detector: Git scope detection with priority
- intelligent_mode_detector: Context-aware auto mode selection
- impact_effort: Impact/effort matrix calculation
- verdict: Three-tier verdict synthesis
- orchestrator: Parallel agent orchestration
- formatter: Multi-format output generation
- circuit_breaker: LLM provider circuit breaker
"""

from .agent_registry import (
    AGENT_REGISTRY,
    MODE_AGENTS,
    get_agent_config,
    get_token_limit,
    select_agents,
    validate_agent_names,
)
from .assessment_mode import (
    AssessmentFinding,
    AssessmentMode,
    AssessmentReport,
    create_assessment_mode,
    run_assessment,
)
from .circuit_breaker import (
    CircuitBreakerConfig,
    CircuitState,
    LLMCircuitBreaker,
    ProviderState,
)
from .constitutional_filter import (
    ConstitutionalFilter,
    create_constitutional_filter,
    filter_constitutional_violations,
    validate_agent_registry_compliance,
)
from .cross_agent_validation import (
    CrossAgentValidator,
    LocationKey,
    ValidationResult,
    merge_validated_results,
    validate_findings,
)
from .formatter import (
    FormattedOutput,
    OutputFormat,
    UCIFormatter,
)
from .impact_effort import (
    Level,
    calculate_impact_effort,
    format_impact_effort,
    impact_effort_to_score,
    sort_findings_by_priority,
)
from .intelligent_mode_detector import (
    EXTENSION_RISK,
    RISK_PATTERNS,
    ContextSignals,
    ModeDetectionResult,
    detect_mode_from_context,
    format_mode_detection_message,
)
from .orchestrator import (
    AgentResult,
    OrchestratorConfig,
    ParallelAgentOrchestrator,
)
from .practicality_filter import (
    PracticalityAssessment,
    PracticalityFilter,
    assess_finding_practicality,
    create_practicality_filter,
    filter_practical_findings,
)
from .pre_existing import (
    PreExistingDetector,
    PreExistingResult,
    detect_pre_existing_issues,
)
from .scope_detector import detect_scope
from .sequential_trigger import (
    SequentialTrigger,
    TriggerCondition,
    TriggerResult,
)
from .verdict import (
    Verdict,
    format_verdict_summary,
    synthesize_verdict,
)

__all__ = [
    # Agent registry
    "AGENT_REGISTRY",
    "MODE_AGENTS",
    "select_agents",
    "get_agent_config",
    "get_token_limit",
    "validate_agent_names",
    # Circuit breaker
    "CircuitBreakerConfig",
    "CircuitState",
    "LLMCircuitBreaker",
    "ProviderState",
    # Constitutional filter
    "ConstitutionalFilter",
    "FilterResult",
    "create_constitutional_filter",
    "filter_constitutional_violations",
    "validate_agent_registry_compliance",
    # Cross-agent validation
    "CrossAgentValidator",
    "LocationKey",
    "ValidationResult",
    "merge_validated_results",
    "validate_findings",
    # Formatter
    "FormattedOutput",
    "OutputFormat",
    "UCIFormatter",
    # Impact/Effort
    "Level",
    "calculate_impact_effort",
    "format_impact_effort",
    "impact_effort_to_score",
    "sort_findings_by_priority",
    # Orchestrator
    "AgentResult",
    "OrchestratorConfig",
    "ParallelAgentOrchestrator",
    # Practicality filter
    "PracticalityAssessment",
    "PracticalityFilter",
    "assess_finding_practicality",
    "create_practicality_filter",
    "filter_practical_findings",
    # Pre-existing issue detection
    "PreExistingDetector",
    "PreExistingResult",
    "detect_pre_existing_issues",
    # Assessment mode
    "AssessmentFinding",
    "AssessmentMode",
    "AssessmentReport",
    "create_assessment_mode",
    "run_assessment",
    # Scope detector
    "detect_scope",
    # Intelligent sequential trigger
    "SequentialTrigger",
    "TriggerCondition",
    "TriggerResult",
    # Intelligent mode detector
    "ContextSignals",
    "EXTENSION_RISK",
    "RISK_PATTERNS",
    "ModeDetectionResult",
    "detect_mode_from_context",
    "format_mode_detection_message",
    # Verdict
    "Verdict",
    "format_verdict_summary",
    "synthesize_verdict",
]
