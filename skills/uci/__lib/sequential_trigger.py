"""
Intelligent Sequential Execution Trigger for UCI Multi-Lens Adversarial

Determines when sequential execution (agents run in series, each seeing previous findings)
is justified despite 600% overhead, based on code characteristics and early findings.

Phase 0.75 Performance Baseline:
- Parallel execution: ~30 seconds (4 agents in parallel)
- Sequential execution: ~180 seconds (4 agents in series)
- Overhead: 600% (5x slower)
- Acceptable threshold: 30% overhead

Sequential is ONLY justified when expected detection improvement exceeds 600% cost.
"""

import re
from dataclasses import dataclass
from enum import Enum


class TriggerCondition(Enum):
    """Conditions that justify sequential execution."""

    # Codebase characteristics (evaluated before any agents run)
    STATE_MACHINE_HEAVY = "state_machine_heavy"
    CONCURRENCY_HEAVY = "concurrency_heavy"
    SECURITY_CRITICAL = "security_critical"
    COMPLEX_CONTROL_FLOW = "complex_control_flow"

    # Early finding patterns (evaluated after first wave of agents)
    HIGH_FINDING_DENSITY = "high_finding_density"
    CRITICAL_SEVERITY_CLUSTER = "critical_severity_cluster"
    COUPLED_BUG_TYPES = "coupled_bug_types"

    # Never justify sequential
    NOT_WORTH_COST = "not_worth_cost"


@dataclass
class TriggerResult:
    """Result of sequential trigger evaluation."""

    should_trigger_sequential: bool
    reason: str
    conditions_met: list[TriggerCondition]
    confidence: float  # 0.0 to 1.0
    expected_improvement: str  # Qualitative: "high" | "medium" | "low"


class SequentialTrigger:
    """
    Evaluates whether to trigger sequential execution based on code characteristics
    and early agent findings.

    QUALITY-FIRST MODE: Triggers sequential whenever it improves detection quality,
    regardless of performance overhead. The 600% overhead is acceptable when
    it means catching more bugs.
    """

    # Patterns that indicate state-machine heavy code
    STATE_PATTERNS = [
        r"\bstate\s*=\s*['\"][\w]+['\"]",  # Direct state assignment
        r"\.transition\(",  # State transition methods
        r"\b(StateMachine|StateMachine|FiniteStateMachine)\b",
        r"\b(pending|in_progress|completed|failed|success)\b",  # Common state values
        r"asyncio\.(Event|Lock|Semaphore|Queue)",  # Async state primitives
    ]

    # Patterns that indicate concurrency
    CONCURRENCY_PATTERNS = [
        r"\b(async\s+def|await|asyncio)\b",
        r"\b(threading|Thread|Lock|Semaphore)\b",
        r"\b(multiprocessing|Process|Queue|Pool)\b",
        r"\bconcurrent\.futures\b",
        r"\.start\(\)|\.join\(\)",  # Thread/process methods
    ]

    # Patterns that indicate security-critical code
    SECURITY_PATTERNS = [
        r"\b(auth|password|token|jwt|session|csrf)\b",
        r"\b(encrypt|decrypt|hash|salt|cipher)\b",
        r"\b(sql|query|execute|cursor)\b",  # Database access
        r"\b(request\.|form\.|args\.|cookies\.)",  # User input
        r"\b(os\.system|subprocess|shell|exec)\b",  # Command execution
    ]

    # Patterns that indicate complex control flow
    COMPLEX_FLOW_PATTERNS = [
        r"\b(if\s+.*:\s*if\s+|for\s+.*:\s*for\s+)",  # Nested loops/conditionals
        r"\b(try:.*:except.*:finally|try:.*:except.*:except)",  # Multiple exception handlers
        r"\b(while\s+.*:\s*if\s+.*:\s*break)",  # Loop with complex exit
    ]

    # File paths that indicate security-critical areas
    SECURITY_PATH_PATTERNS = [
        r"auth",
        r"login",
        r"password",
        r"token",
        r"session",
        r"payment",
        r"transaction",
        r"admin",
        r"permission",
        r"access",
    ]

    def __init__(self, quality_first: bool = True):
        """
        Args:
            quality_first: If True (default), trigger sequential whenever quality improves,
                ignoring performance cost. If False, use cost-constrained triggering (30% threshold).
        """
        self.quality_first = quality_first
        self.overhead_threshold = 0.30  # Only used when quality_first=False

    def evaluate_codebase_characteristics(
        self,
        code_diff: str,
        file_paths: list[str],
    ) -> list[TriggerCondition]:
        """
        Evaluate codebase characteristics BEFORE any agents run.

        Returns list of conditions that would justify sequential execution.
        """
        conditions = []

        # Check for state-machine heavy code (lowered threshold from 5 to 1)
        state_score = sum(
            len(re.findall(pattern, code_diff, re.IGNORECASE)) for pattern in self.STATE_PATTERNS
        )
        if state_score >= 1:  # Threshold: 1+ state-related patterns (was 5)
            conditions.append(TriggerCondition.STATE_MACHINE_HEAVY)

        # Check for concurrency (lowered threshold from 3 to 1)
        concurrency_score = sum(
            len(re.findall(pattern, code_diff, re.IGNORECASE))
            for pattern in self.CONCURRENCY_PATTERNS
        )
        if concurrency_score >= 1:  # Threshold: 1+ concurrency patterns (was 3)
            conditions.append(TriggerCondition.CONCURRENCY_HEAVY)

        # Check for security-critical code (lowered threshold from 5 to 2, path from 2 to 1)
        security_score = sum(
            len(re.findall(pattern, code_diff, re.IGNORECASE)) for pattern in self.SECURITY_PATTERNS
        )
        security_path_score = sum(
            any(re.search(pattern, path, re.IGNORECASE) for pattern in self.SECURITY_PATH_PATTERNS)
            for path in file_paths
        )

        if security_score >= 2 or security_path_score >= 1:  # Lowered thresholds (was 5, 2)
            conditions.append(TriggerCondition.SECURITY_CRITICAL)

        # Check for complex control flow (lowered threshold from 3 to 1)
        complexity_score = sum(
            len(re.findall(pattern, code_diff, re.IGNORECASE))
            for pattern in self.COMPLEX_FLOW_PATTERNS
        )
        if complexity_score >= 1:  # Threshold: 1+ complex patterns (was 3)
            conditions.append(TriggerCondition.COMPLEX_CONTROL_FLOW)

        return conditions

    def evaluate_early_findings(
        self,
        first_wave_findings: list[dict],
    ) -> list[TriggerCondition]:
        """
        Evaluate early agent findings AFTER first wave of parallel agents.

        Returns list of conditions that would justify sequential execution for remaining agents.
        """
        conditions = []

        if not first_wave_findings:
            # No findings means sequential won't help
            return [TriggerCondition.NOT_WORTH_COST]

        # Count findings by severity
        critical_count = sum(
            1 for f in first_wave_findings if f.get("severity") in ["critical", "blocker"]
        )

        # High finding density: 3+ critical/high findings per 100 LOC
        finding_density = len(first_wave_findings)
        if finding_density >= 3:  # Threshold: 3+ findings in first wave
            conditions.append(TriggerCondition.HIGH_FINDING_DENSITY)

        # Critical severity cluster: 2+ critical findings
        if critical_count >= 2:
            conditions.append(TriggerCondition.CRITICAL_SEVERITY_CLUSTER)

        # Coupled bug types: multiple agents finding issues in same file/lines
        file_counts = {}
        for finding in first_wave_findings:
            location = finding.get("location", "")
            if location:
                file_counts[location] = file_counts.get(location, 0) + 1

        # If any file has 3+ findings from different agents, bugs are coupled
        if any(count >= 3 for count in file_counts.values()):
            conditions.append(TriggerCondition.COUPLED_BUG_TYPES)

        return conditions

    def should_trigger_sequential(
        self,
        code_diff: str,
        file_paths: list[str],
        first_wave_findings: list[dict] | None = None,
    ) -> TriggerResult:
        """
        Decide whether to trigger sequential execution.

        QUALITY-FIRST MODE (default): Triggers sequential whenever ANY condition suggests
        improved detection quality, regardless of performance overhead.

        Two-phase evaluation:
        1. Before agents run: Check codebase characteristics
        2. After first wave: Check early finding patterns (if provided)

        Returns:
            TriggerResult with decision and reasoning.
        """
        pre_conditions = self.evaluate_codebase_characteristics(code_diff, file_paths)

        # If no early findings provided, use only codebase characteristics
        if first_wave_findings is None:
            if not pre_conditions:
                return TriggerResult(
                    should_trigger_sequential=False,
                    reason="No codebase characteristics suggest sequential would improve quality",
                    conditions_met=[],
                    confidence=0.9,
                    expected_improvement="low",
                )

            # QUALITY-FIRST: Trigger sequential if ANY characteristic suggests benefit
            if self.quality_first and pre_conditions:
                return TriggerResult(
                    should_trigger_sequential=True,
                    reason=f"Codebase characteristics ({', '.join(c.value for c in pre_conditions)}) suggest sequential would improve detection quality",
                    conditions_met=pre_conditions,
                    confidence=0.7,
                    expected_improvement="medium",
                )

            # COST-CONSTRAINED: Only trigger if multiple characteristics together justify
            if len(pre_conditions) >= 2:
                return TriggerResult(
                    should_trigger_sequential=True,
                    reason="Multiple codebase characteristics suggest sequential would improve detection quality",
                    conditions_met=pre_conditions,
                    confidence=0.6,
                    expected_improvement="medium",
                )

            return TriggerResult(
                should_trigger_sequential=False,
                reason=f"Codebase characteristics ({', '.join(c.value for c in pre_conditions)}) don't justify sequential execution",
                conditions_met=pre_conditions,
                confidence=0.8,
                expected_improvement="low",
            )

        # If early findings provided, use both phases
        post_conditions = self.evaluate_early_findings(first_wave_findings)
        all_conditions = pre_conditions + post_conditions

        # Check if sequential is worth the cost (this rule is universal - no findings = no benefit)
        if TriggerCondition.NOT_WORTH_COST in post_conditions:
            return TriggerResult(
                should_trigger_sequential=False,
                reason="No early findings - sequential won't improve detection",
                conditions_met=all_conditions,
                confidence=0.95,
                expected_improvement="none",
            )

        # QUALITY-FIRST: Trigger sequential if ANY condition suggests improved quality
        if self.quality_first:
            # Check if ANY condition justifies sequential
            if post_conditions or pre_conditions:
                # Determine expected improvement based on conditions
                has_critical = TriggerCondition.CRITICAL_SEVERITY_CLUSTER in post_conditions
                has_coupled = TriggerCondition.COUPLED_BUG_TYPES in post_conditions
                has_density = TriggerCondition.HIGH_FINDING_DENSITY in post_conditions
                has_security = TriggerCondition.SECURITY_CRITICAL in pre_conditions
                has_state = TriggerCondition.STATE_MACHINE_HEAVY in pre_conditions
                has_concurrency = TriggerCondition.CONCURRENCY_HEAVY in pre_conditions
                has_complex = TriggerCondition.COMPLEX_CONTROL_FLOW in pre_conditions

                # Calculate improvement level
                if has_critical or (has_coupled and has_density):
                    improvement = "high"
                    confidence = 0.9
                elif has_coupled or has_security or (has_state and has_concurrency):
                    improvement = "high"
                    confidence = 0.85
                elif has_density or has_state or has_concurrency or has_complex:
                    improvement = "medium"
                    confidence = 0.75
                else:
                    improvement = "medium"
                    confidence = 0.7

                # Build reason string
                reasons = []
                if post_conditions:
                    reasons.append(
                        f"early findings ({', '.join(c.value for c in post_conditions)})"
                    )
                if pre_conditions:
                    reasons.append(
                        f"codebase characteristics ({', '.join(c.value for c in pre_conditions)})"
                    )

                return TriggerResult(
                    should_trigger_sequential=True,
                    reason=f"Quality-first mode: {' + '.join(reasons)} suggest sequential would improve detection quality (600% overhead acceptable for better quality)",
                    conditions_met=all_conditions,
                    confidence=confidence,
                    expected_improvement=improvement,
                )

        # COST-CONSTRAINED: Only trigger if conditions together justify the 600% overhead
        critical_cluster = TriggerCondition.CRITICAL_SEVERITY_CLUSTER in post_conditions
        high_density = TriggerCondition.HIGH_FINDING_DENSITY in post_conditions
        coupled_bugs = TriggerCondition.COUPLED_BUG_TYPES in post_conditions
        state_heavy = TriggerCondition.STATE_MACHINE_HEAVY in pre_conditions
        security_critical = TriggerCondition.SECURITY_CRITICAL in pre_conditions

        # Critical cluster → always sequential (regardless of other factors)
        if critical_cluster:
            return TriggerResult(
                should_trigger_sequential=True,
                reason=f"Critical severity cluster ({sum(1 for f in first_wave_findings if f.get('severity') in ['critical', 'blocker'])} critical findings) justifies sequential execution",
                conditions_met=all_conditions,
                confidence=0.9,
                expected_improvement="high",
            )

        # High density + (state-heavy OR security-critical OR coupled) → sequential
        if high_density and (state_heavy or security_critical or coupled_bugs):
            improvement = "high" if coupled_bugs else "medium"
            confidence = 0.85 if coupled_bugs else 0.7

            return TriggerResult(
                should_trigger_sequential=True,
                reason=f"High finding density ({len(first_wave_findings)} issues) in {'security-critical' if security_critical else 'state-heavy' if state_heavy else 'coupled'} code justifies sequential execution",
                conditions_met=all_conditions,
                confidence=confidence,
                expected_improvement=improvement,
            )

        # Otherwise, not worth the 600% overhead
        return TriggerResult(
            should_trigger_sequential=False,
            reason=f"Conditions don't justify 600% overhead: {', '.join(c.value for c in all_conditions)}",
            conditions_met=all_conditions,
            confidence=0.85,
            expected_improvement="low",
        )


def demo_trigger_logic():
    """Demonstrate sequential trigger logic with examples."""

    trigger = SequentialTrigger()

    # Example 1: Simple code change (no sequential)
    print("=== Example 1: Simple variable rename ===")
    result = trigger.should_trigger_sequential(
        code_diff="def foo():\n    return x\n\ndef bar():\n    return y",
        file_paths=["src/simple.py"],
    )
    print(f"Trigger sequential: {result.should_trigger_sequential}")
    print(f"Reason: {result.reason}\n")

    # Example 2: State machine with early findings (sequential justified)
    print("=== Example 2: State machine with critical findings ===")
    result = trigger.should_trigger_sequential(
        code_diff="""
        state = "pending"
        async def transition():
            if state == "pending":
                state = "in_progress"
                await process()
                state = "completed"
        """,
        file_paths=["src/auth/state_machine.py"],
        first_wave_findings=[
            {"severity": "critical", "location": "src/auth/state_machine.py:15"},
            {"severity": "critical", "location": "src/auth/state_machine.py:18"},
            {"severity": "high", "location": "src/auth/state_machine.py:20"},
        ],
    )
    print(f"Trigger sequential: {result.should_trigger_sequential}")
    print(f"Reason: {result.reason}")
    print(f"Expected improvement: {result.expected_improvement}\n")

    # Example 3: High finding density in non-critical code (borderline)
    print("=== Example 3: High findings in utility code ===")
    result = trigger.should_trigger_sequential(
        code_diff="def parse_config(data):\n    return json.loads(data)",
        file_paths=["src/utils/config.py"],
        first_wave_findings=[
            {"severity": "medium", "location": "src/utils/config.py:10"},
            {"severity": "medium", "location": "src/utils/config.py:12"},
            {"severity": "low", "location": "src/utils/config.py:15"},
        ],
    )
    print(f"Trigger sequential: {result.should_trigger_sequential}")
    print(f"Reason: {result.reason}\n")


if __name__ == "__main__":
    demo_trigger_logic()
