"""TASK-001.4: role-enum drift contract between preflight_propose and the gate.

The authoritative role set is ``preflight_propose._ROLE_VALUES``. The
PreToolUse gate keeps its own ``_ROLE_POLICY`` dict (worker-mode per role).
If the two drift — a role added to one but not the other — the gate either
silently allows an unclassified role or denies a role the preflight lawfully
emits. This test pins them as co-mutating.

Class-A leak guard (memory: diagnostic-gate-warn-mode-class-a-leak): a gate
that hardcodes role literals silently goes inert when the producer's enum
grows. Drift detection is the structural fix.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import preflight_propose  # noqa: E402
import go_delegation_enforce_PreToolUse as gate  # noqa: E402


class TestRoleEnumContract:

    def test_role_policy_matches_role_values_exactly(self):
        """The single load-bearing drift assertion."""
        producer = set(preflight_propose._ROLE_VALUES)
        consumer = set(gate._ROLE_POLICY)
        assert producer == consumer, (
            "role-enum drift: preflight_propose._ROLE_VALUES and gate._ROLE_POLICY "
            f"diverged.\n  only in producer: {producer - consumer}\n"
            f"  only in consumer: {consumer - producer}"
        )

    def test_every_role_has_known_worker_mode(self):
        valid = {"orchestrator", "path_bound",
                 "path_bound_no_shared_state", "worktree_only"}
        for role, policy in gate._ROLE_POLICY.items():
            assert policy["worker_mode"] in valid, (
                f"role {role!r} has unknown worker_mode {policy['worker_mode']!r}"
            )

    def test_unknown_role_denies_drift_fail_closed(self):
        """A role emitted by preflight but absent from the gate must deny,
        not silently allow. We simulate drift by looking up a synthetic role."""
        # Use the gate's own _decide path indirectly: confirm _ROLE_POLICY.get
        # returns None for an unknown role (the fail-closed trigger condition).
        assert gate._ROLE_POLICY.get("synthetic_future_role") is None, (
            "unknown role resolved to a policy — fail-closed branch is unreachable"
        )

    def test_local_fast_and_subagent_are_path_bound_family(self):
        """Regression: local_fast was hardcoded at the call site; confirm it
        lands in the path-bound family (not worktree_only, not orchestrator)."""
        assert gate._ROLE_POLICY["local_fast"]["worker_mode"] == "path_bound_no_shared_state"
        assert gate._ROLE_POLICY["claude_subagent"]["worker_mode"] == "path_bound"

    def test_pi_ccr_and_agy_are_worktree_only(self):
        """Both external-harness roles mutate in their own worktree, never direct."""
        assert gate._ROLE_POLICY["pi_ccr"]["worker_mode"] == "worktree_only"
        assert gate._ROLE_POLICY["agy"]["worker_mode"] == "worktree_only"

    def test_claude_main_is_orchestrator(self):
        assert gate._ROLE_POLICY["claude_main"]["worker_mode"] == "orchestrator"
