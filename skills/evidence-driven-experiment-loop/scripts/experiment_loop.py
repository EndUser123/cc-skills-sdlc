#!/usr/bin/env python3
"""Deterministic state, delegated-goal, and handoff utilities."""

import argparse
import json
import os
import re
import sys


STATES = [
    "authority_check",
    "offline_attribution",
    "instrumentation",
    "decision_gate",
    "telemetry_validation",
    "mechanism_selection",
    "implementation",
    "throughput_validation",
    "closed",
]
HANDOFFS = [
    "in_progress",
    "needs_fix",
    "partial",
    "blocked",
    "ready_for_parent_review",
    "closed",
]
CLAIM_TYPES = {
    "verified_fact",
    "measured_metric",
    "inference",
    "hypothesis",
    "historical_context",
    "unsupported",
}
REQUIRED = [
    "schema_version",
    "objective",
    "workspace",
    "authority_paths",
    "headline_metric",
    "historical_best",
    "current_control",
    "candidate",
    "lifecycle_state",
    "allowed_actions",
    "forbidden_actions",
    "claims",
    "gates",
    "verification",
    "adversarial_review",
    "next_action",
    "handoff_status",
]
LIVE_ACTION_PATTERN = re.compile(
    r"\b(?:live benchmark|run live benchmark|launch telemetry validation|production changes)\b",
    re.IGNORECASE,
)


def read(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read JSON state {path}: {error}") from error


def requests_live_action(actions):
    """Return true only for explicit live-execution action language."""
    return any(
        isinstance(action, str) and LIVE_ACTION_PATTERN.search(action)
        for action in actions
    )


def validate(state):
    if not isinstance(state, dict):
        return ["state must be a JSON object"]

    errors = [
        f"missing required field: {field}"
        for field in REQUIRED
        if field not in state
    ]
    if errors:
        return errors

    if state["schema_version"] != 1 or isinstance(state["schema_version"], bool):
        errors.append("schema_version must be integer 1")
    for field in ("objective", "workspace", "next_action", "headline_metric"):
        if not isinstance(state[field], str) or not state[field].strip():
            errors.append(f"{field} must be a non-empty string")
    for field in ("authority_paths", "allowed_actions", "forbidden_actions", "claims"):
        if not isinstance(state[field], list):
            errors.append(f"{field} must be an array")
    for field in ("gates", "verification", "adversarial_review"):
        if not isinstance(state[field], dict):
            errors.append(f"{field} must be an object")
    if state["lifecycle_state"] not in STATES:
        errors.append("invalid lifecycle_state")
    if state["handoff_status"] not in HANDOFFS:
        errors.append("invalid handoff_status")

    workspace = state["workspace"]
    if isinstance(workspace, str) and workspace.strip():
        workspace_path = os.path.abspath(workspace)
    else:
        workspace_path = None
    paths = state["authority_paths"]
    if isinstance(paths, list):
        if not paths:
            errors.append(
                "authority_paths is empty; establish authority before relying on evidence"
            )
        elif workspace_path:
            missing = [
                path
                for path in paths
                if not isinstance(path, str)
                or not os.path.exists(os.path.join(workspace_path, path))
                if not os.path.isabs(path)
            ]
            missing.extend(
                path
                for path in paths
                if isinstance(path, str) and os.path.isabs(path) and not os.path.exists(path)
            )
            if missing:
                errors.append(
                    "authority path missing or invalid: "
                    + ", ".join(map(str, missing))
                )

    claims = state["claims"]
    if isinstance(claims, list):
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict) or claim.get("type") not in CLAIM_TYPES:
                errors.append(f"claim {index} has unsupported type")

    gates = state["gates"] if isinstance(state["gates"], dict) else {}
    actions = state["allowed_actions"]
    live_requested = isinstance(actions, list) and requests_live_action(actions)
    if live_requested and not gates.get("live_authorization"):
        errors.append("live action requires gates.live_authorization=true")
    if gates.get("live_authorization"):
        for field in ("falsifier", "abort_gate", "promotion_rule"):
            if not gates.get(field):
                errors.append(f"live authorization requires gates.{field}")
    if state["handoff_status"] == "ready_for_parent_review":
        for field in ("verification", "adversarial_review"):
            review = state[field] if isinstance(state[field], dict) else {}
            if review.get("status") not in ("complete", "completed"):
                errors.append(f"ready_for_parent_review requires {field} completion")
    return errors


def init(args):
    if os.path.exists(args.state):
        raise ValueError(f"state file already exists: {args.state}")
    state = {
        "schema_version": 1,
        "objective": args.objective,
        "workspace": args.workspace,
        "authority_paths": [],
        "headline_metric": "",
        "historical_best": None,
        "current_control": None,
        "candidate": None,
        "lifecycle_state": "authority_check",
        "allowed_actions": ["inspect offline artifacts"],
        "forbidden_actions": ["live benchmark", "production changes"],
        "claims": [],
        "gates": {},
        "verification": {"status": "pending"},
        "adversarial_review": {"status": "pending"},
        "next_action": "identify authority paths",
        "handoff_status": "in_progress",
    }
    with open(args.state, "x", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2)
        stream.write("\n")
    print(args.state)


def goal(state, limit):
    parts = [
        "DELEGATED GOAL",
        f"Objective: {state['objective']}",
        f"Workspace: {state['workspace']}",
        f"Current state: {state['lifecycle_state']}",
        f"Authority paths: {json.dumps(state['authority_paths'], separators=(',', ':'))}",
        f"Allowed actions: {json.dumps(state['allowed_actions'], separators=(',', ':'))}",
        f"Forbidden actions: {json.dumps(state['forbidden_actions'], separators=(',', ':'))}",
        f"Next action: {state['next_action']}",
        f"Stop conditions/gates: {json.dumps(state['gates'], separators=(',', ':'))}",
        f"Verification: {json.dumps(state['verification'], separators=(',', ':'))}",
        f"Adversarial review: {json.dumps(state['adversarial_review'], separators=(',', ':'))}",
        "Return final packet schema: status; verified evidence; unresolved claims; next action; forbidden actions; live authorization.",
    ]
    output = "\n".join(parts)
    if len(output) > limit:
        raise ValueError(
            f"goal budget {limit} cannot contain essential safety fields (needs {len(output)})"
        )
    return output


def handoff(state):
    verified = [
        claim
        for claim in state["claims"]
        if claim.get("type") in ("verified_fact", "measured_metric")
    ]
    unresolved = [
        claim
        for claim in state["claims"]
        if claim.get("type") not in ("verified_fact", "measured_metric")
    ]
    packet = {
        "status": state["handoff_status"],
        "lifecycle_state": state["lifecycle_state"],
        "verified_evidence": verified,
        "unresolved_claims": unresolved,
        "next_action": state["next_action"],
        "forbidden_actions": state["forbidden_actions"],
        "live_work_authorized": bool(state["gates"].get("live_authorization")),
    }
    return json.dumps(packet, indent=2)


def build_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    initialize = subparsers.add_parser("init")
    initialize.add_argument("--state", required=True)
    initialize.add_argument("--objective", required=True)
    initialize.add_argument("--workspace", required=True)
    for name in ("validate", "handoff"):
        command = subparsers.add_parser(name)
        command.add_argument("--state", required=True)
    compile_goal = subparsers.add_parser("goal")
    compile_goal.add_argument("--state", required=True)
    compile_goal.add_argument("--max-chars", type=int, default=4000)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        if args.cmd == "init":
            init(args)
            return 0
        state = read(args.state)
        errors = validate(state)
        if args.cmd == "validate":
            if errors:
                print("\n".join(f"ERROR: {error}" for error in errors))
                return 1
            print("valid")
            return 0
        if errors:
            raise ValueError("state invalid:\n" + "\n".join(errors))
        if args.cmd == "goal":
            print(goal(state, args.max_chars))
        else:
            print(handoff(state))
        return 0
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
