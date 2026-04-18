"""
Tests for intelligent sequential trigger logic (user insight enhancement).

Tests the conditional triggering system that determines when sequential execution
is justified despite 600% overhead.

Key insight: Sequential execution should NOT be a blanket "always" or "never"
decision. It should be conditionally triggered based on:
- Codebase characteristics (state-heavy, concurrency, security-critical)
- Early finding patterns (high density, critical severity cluster, coupled bugs)
"""

import pytest

from lib.sequential_trigger import (
    SequentialTrigger,
    TriggerCondition,
)


class TestTriggerCodebaseCharacteristics:
    """Test codebase characteristic detection BEFORE any agents run."""

    def test_simple_code_no_triggers(self):
        """Simple code with no state/concurrency/security patterns."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_codebase_characteristics(
            code_diff="def foo():\n    return x\n\ndef bar():\n    return y",
            file_paths=["src/simple.py"],
        )
        assert conditions == []

    def test_state_machine_heavy_triggers(self):
        """State machine code with 5+ state-related patterns."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_codebase_characteristics(
            code_diff="""
            state = "pending"
            if state == "pending":
                state = "in_progress"
            def transition():
                global state
                state = "completed"
            async def process():
                await asyncio.sleep(1)
            """,
            file_paths=["src/state_machine.py"],
        )
        assert TriggerCondition.STATE_MACHINE_HEAVY in conditions

    def test_concurrency_heavy_triggers(self):
        """Async/concurrency code with 3+ patterns."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_codebase_characteristics(
            code_diff="""
            async def fetch():
                await client.get()
            threading.Thread(target=worker).start()
            with ThreadPoolExecutor() as pool:
                pool.submit(task)
            """,
            file_paths=["src/async.py"],
        )
        assert TriggerCondition.CONCURRENCY_HEAVY in conditions

    def test_security_critical_triggers(self):
        """Security-critical code patterns."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_codebase_characteristics(
            code_diff="""
            def auth(request):
                token = request.cookies.get('token')
                if not token:
                    return unauthorized
            """,
            file_paths=["src/auth/login.py"],
        )
        assert TriggerCondition.SECURITY_CRITICAL in conditions

    def test_security_critical_by_path(self):
        """Security-critical detected from file path patterns."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_codebase_characteristics(
            code_diff="def process(data):\n    return data",
            file_paths=["src/auth/session.py", "src/payment/transaction.py"],
        )
        assert TriggerCondition.SECURITY_CRITICAL in conditions

    def test_complex_control_flow_triggers(self):
        """Nested control flow patterns."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_codebase_characteristics(
            code_diff="""
            if condition:
                if nested:
                    for item in items:
                        if item.valid:
                            break
            try:
                risky_operation()
            except ValueError:
                handle_error()
            except KeyError:
                handle_missing()
            """,
            file_paths=["src/complex.py"],
        )
        assert TriggerCondition.COMPLEX_CONTROL_FLOW in conditions


class TestTriggerEarlyFindings:
    """Test early finding pattern evaluation AFTER first wave of agents."""

    def test_no_findings_not_worth_cost(self):
        """No early findings means sequential won't help."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_early_findings(first_wave_findings=[])
        assert TriggerCondition.NOT_WORTH_COST in conditions

    def test_high_finding_density_triggers(self):
        """3+ findings in first wave triggers high density."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_early_findings(
            first_wave_findings=[
                {"severity": "high", "location": "src/file.py:10"},
                {"severity": "medium", "location": "src/file.py:20"},
                {"severity": "low", "location": "src/file.py:30"},
            ]
        )
        assert TriggerCondition.HIGH_FINDING_DENSITY in conditions

    def test_critical_severity_cluster_triggers(self):
        """2+ critical findings triggers cluster condition."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_early_findings(
            first_wave_findings=[
                {"severity": "critical", "location": "src/file.py:10"},
                {"severity": "critical", "location": "src/file.py:20"},
            ]
        )
        assert TriggerCondition.CRITICAL_SEVERITY_CLUSTER in conditions

    def test_coupled_bug_types_triggers(self):
        """Multiple findings in same location indicates coupled bugs."""
        trigger = SequentialTrigger()
        conditions = trigger.evaluate_early_findings(
            first_wave_findings=[
                {"severity": "high", "location": "src/file.py:10"},
                {"severity": "medium", "location": "src/file.py:10"},
                {"severity": "low", "location": "src/file.py:10"},
            ]
        )
        assert TriggerCondition.COUPLED_BUG_TYPES in conditions


class TestShouldTriggerSequential:
    """Test end-to-end trigger decision logic."""

    def test_simple_code_no_early_findings_parallel(self):
        """Simple code with no findings → parallel only."""
        trigger = SequentialTrigger()
        result = trigger.should_trigger_sequential(
            code_diff="def foo():\n    return x",
            file_paths=["src/simple.py"],
            first_wave_findings=None,
        )
        assert result.should_trigger_sequential is False
        assert "No codebase characteristics" in result.reason

    def test_state_machine_with_critical_findings_sequential(self):
        """State machine + critical findings → sequential justified."""
        trigger = SequentialTrigger()
        result = trigger.should_trigger_sequential(
            code_diff="state = 'pending'\nasync def transition():\n    state = 'completed'",
            file_paths=["src/auth/state.py"],
            first_wave_findings=[
                {"severity": "critical", "location": "src/auth/state.py:10"},
                {"severity": "critical", "location": "src/auth/state.py:15"},
                {"severity": "high", "location": "src/auth/state.py:20"},
            ],
        )
        assert result.should_trigger_sequential is True
        assert result.expected_improvement == "high"
        assert result.confidence >= 0.85

    def test_security_critical_state_machine_sequential(self):
        """Security-critical + state-heavy (before findings) → sequential."""
        trigger = SequentialTrigger()
        result = trigger.should_trigger_sequential(
            code_diff="""
            state = "authenticated"
            if state == "authenticated":
                token = request.cookies.get('token')
                await validate_token(token)
            """,
            file_paths=["src/auth/login.py"],
            first_wave_findings=None,
        )
        assert result.should_trigger_sequential is True
        assert result.expected_improvement == "medium"

    def test_utility_code_with_findings_sequential_quality_first(self):
        """Quality-first mode: Utility code with 3+ findings → sequential justified for quality."""
        trigger = SequentialTrigger(quality_first=True)
        result = trigger.should_trigger_sequential(
            code_diff="def parse_config(data):\n    return json.loads(data)",
            file_paths=["src/utils/config.py"],
            first_wave_findings=[
                {"severity": "medium", "location": "src/utils/config.py:10"},
                {"severity": "medium", "location": "src/utils/config.py:12"},
                {"severity": "low", "location": "src/utils/config.py:15"},
            ],
        )
        # Quality-first mode: high finding density (3+) triggers sequential for better quality
        assert result.should_trigger_sequential is True
        assert "Quality-first mode" in result.reason
        assert result.expected_improvement == "medium"

    def test_utility_code_with_findings_parallel_cost_constrained(self):
        """Cost-constrained mode: Utility code with findings → parallel preferred (not worth overhead)."""
        trigger = SequentialTrigger(quality_first=False)
        result = trigger.should_trigger_sequential(
            code_diff="def parse_config(data):\n    return json.loads(data)",
            file_paths=["src/utils/config.py"],
            first_wave_findings=[
                {"severity": "medium", "location": "src/utils/config.py:10"},
                {"severity": "medium", "location": "src/utils/config.py:12"},
                {"severity": "low", "location": "src/utils/config.py:15"},
            ],
        )
        # Cost-constrained mode: medium findings in utility code don't justify 600% overhead
        assert result.should_trigger_sequential is False
        assert "don't justify 600% overhead" in result.reason

    def test_no_early_findings_parallel(self):
        """No early findings → sequential won't help, use parallel."""
        trigger = SequentialTrigger()
        result = trigger.should_trigger_sequential(
            code_diff="state = 'pending'",
            file_paths=["src/state.py"],
            first_wave_findings=[],
        )
        assert result.should_trigger_sequential is False
        assert "No early findings" in result.reason

    def test_state_heavy_coupled_bugs_sequential(self):
        """State-heavy code + coupled bugs (same location hit multiple times)."""
        trigger = SequentialTrigger()
        result = trigger.should_trigger_sequential(
            code_diff="state = 'pending'\nif state == 'pending':\n    state = 'active'",
            file_paths=["src/state.py"],
            first_wave_findings=[
                {"severity": "high", "location": "src/state.py:10"},
                {"severity": "medium", "location": "src/state.py:10"},
                {"severity": "low", "location": "src/state.py:10"},
            ],
        )
        assert result.should_trigger_sequential is True
        assert result.expected_improvement == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
