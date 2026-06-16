"""Tests for the hedged-root-cause guard in StopHook_rca_contract.

Catches the failure mode: emitting Root Cause qualified with 'most likely' /
'probably' / 'I think' when the discriminating test for the top hypothesis
has not been run this turn. Per the rca iron law, the smallest test that
falsifies the top hypothesis must be run before Root Cause is written.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "StopHook_rca_contract.py"
)


def _load_module():
    """Load the hook module without registering the package globals."""
    spec = importlib.util.spec_from_file_location(
        "StopHook_rca_contract_under_test", HOOK_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


class TestContainsHedgeToken:
    """Direct unit tests for the hedge regex."""

    def test_most_likely(self, mod):
        assert mod._contains_hedge_token("The most likely cause is a missing import.")
        assert mod._contains_hedge_token("Most likely: a missing dependency.")

    def test_probably(self, mod):
        assert mod._contains_hedge_token("This is probably the bug.")
        assert mod._contains_hedge_token("Probably a race condition.")

    def test_i_think(self, mod):
        assert mod._contains_hedge_token("I think the issue is in the parser.")
        assert mod._contains_hedge_token("I think this is correct.")

    def test_i_believe(self, mod):
        assert mod._contains_hedge_token("I believe the hook failed silently.")

    def test_likely_cause_compound(self, mod):
        assert mod._contains_hedge_token("The likely cause is a race.")
        assert mod._contains_hedge_token("Likely root: a missing config file.")

    def test_appears_likely(self, mod):
        assert mod._contains_hedge_token("It appears likely that the daemon is stale.")

    def test_no_hedge(self, mod):
        # Direct, evidence-backed claims must not trigger the guard
        assert not mod._contains_hedge_token("The hook returns 0 and stdout matches expected JSON.")
        assert not mod._contains_hedge_token("Direct test: python model_router_init.py exited 0.")

    def test_unrelated_word_likely(self, mod):
        # "likely" alone, not bound to a hedge pattern, must not trigger
        # The pattern requires the compound forms or explicit hedge words.
        assert not mod._contains_hedge_token("Re-run is more likely than a fresh start.")
        # The above is borderline; we accept it (catches fewer false positives).
        # Only specific hedge compounds trigger.

    def test_falsifier_section_can_use_hedge(self, mod):
        # The guard is enforced against Root Cause only. Falsifier can say
        # 'this seems likely' when describing what was falsified. The
        # helper itself is section-agnostic; the gate-level wiring in
        # validate_rca_turn only inspects root_cause.
        assert mod._contains_hedge_token("H2 seems likely but was falsified by the test run.")


class TestRanDiscriminatingTest:
    """The companion guard: did the model run a tool that could falsify the hypothesis?"""

    def test_no_tools(self, mod):
        assert mod._ran_discriminating_test([]) is False

    def test_only_skill_tools(self, mod):
        # Skill and Task alone are not discriminating
        events = [{"name": "Skill"}, {"name": "Task"}]
        assert mod._ran_discriminating_test(events) is False

    def test_bash_discriminates(self, mod):
        # A Bash invocation is the canonical discriminating test
        events = [{"name": "Bash", "command": "python model_router_init.py"}]
        assert mod._ran_discriminating_test(events) is True

    def test_read_discriminates(self, mod):
        # Read of the target file counts as evidence
        events = [{"name": "Read", "file_path": "/path/to/hook.py"}]
        assert mod._ran_discriminating_test(events) is True

    def test_grep_discriminates(self, mod):
        events = [{"name": "Grep", "pattern": "foo"}]
        assert mod._ran_discriminating_test(events) is True


def _build_minimal_rca_response(root_cause_text: str) -> str:
    """Build a response with the 9 required sections populated enough to
    reach the hedge-guard check. Sections that the validator requires
    are filled with minimal content; only Root Cause varies."""
    return f"""## Symptom
User reports a hook error.

## Evidence
[direct test this turn] Bash: command_output

## Executed Path
1. Foo
2. Bar

## Alternative Hypothesis
- H1: a
- H2: b

## Falsifier
H1 disproved by test.

## Ruled Out
- H2: reason

## Root Cause
{root_cause_text}

## Fix
Do X.

## Verification
Run Y.
"""


class TestValidateIntegration:
    """End-to-end: feed a synthetic RCA turn through the validator and
    check that the hedge guard fires (or does not fire) as expected."""

    def _validate(self, mod, response: str, tool_events: list) -> tuple[bool, list]:
        # Call the internal validator directly. _validate_rca_contract is
        # the named entry point used by the public check() function.
        return mod._validate_rca_contract(
            data={"rca_turn": True},
            response=response,
            tool_events=tool_events,
            rca_turn=True,
            session_id="test-session",
            terminal_id="test-terminal",
        )

    def test_hedge_without_discriminating_tool_blocks(self, mod):
        response = _build_minimal_rca_response(
            "The most likely cause is a missing import in the dispatcher."
        )
        ok, reasons = self._validate(mod, response, tool_events=[])
        assert ok is False, f"expected block, got ok=True; reasons={reasons}"
        assert any("hedge" in r.lower() for r in reasons), (
            f"expected hedged-root-cause-no-discriminating-test in reasons: {reasons}"
        )

    def test_hedge_with_discriminating_tool_passes(self, mod):
        response = _build_minimal_rca_response(
            "The most likely cause is a missing import in the dispatcher."
        )
        tool_events = [{"name": "Bash", "command": "python dispatcher.py"}]
        ok, reasons = self._validate(mod, response, tool_events=tool_events)
        # The hedge rule should NOT fire; other rules may still fail because
        # our minimal response lacks full evidence. We only check that the
        # hedge rule is absent.
        assert not any("hedge" in r.lower() for r in reasons), (
            f"hedge rule fired despite Bash tool present: {reasons}"
        )

    def test_no_hedge_no_tool_passes_hedge_check(self, mod):
        response = _build_minimal_rca_response(
            "The dispatcher exits 0 with the expected JSON output."
        )
        ok, reasons = self._validate(mod, response, tool_events=[])
        assert not any("hedge" in r.lower() for r in reasons), (
            f"hedge rule fired on direct claim: {reasons}"
        )

    def test_i_believe_blocks(self, mod):
        # Different hedge form, same failure mode
        response = _build_minimal_rca_response("I believe the dispatcher is at fault.")
        ok, reasons = self._validate(mod, response, tool_events=[])
        assert any("hedge" in r.lower() for r in reasons), (
            f"expected block for 'I believe' hedge: {reasons}"
        )

    def test_appears_likely_blocks(self, mod):
        response = _build_minimal_rca_response("It appears likely the daemon is stale.")
        ok, reasons = self._validate(mod, response, tool_events=[])
        assert any("hedge" in r.lower() for r in reasons)
