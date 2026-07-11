# State Schema

The state is JSON with these required fields:

`schema_version` (integer), `objective` (string), `workspace` (string),
`authority_paths` (array of strings), `headline_metric` (string),
`historical_best`, `current_control`, `candidate`, `lifecycle_state` (enum),
`allowed_actions` (array), `forbidden_actions` (array), `claims` (array),
`gates` (object), `verification` (object), `adversarial_review` (object),
`next_action` (string), and `handoff_status` (enum).

Lifecycle enum: `authority_check`, `offline_attribution`, `instrumentation`,
`decision_gate`, `telemetry_validation`, `mechanism_selection`,
`implementation`, `throughput_validation`, `closed`.

Handoff enum: `in_progress`, `needs_fix`, `partial`, `blocked`,
`ready_for_parent_review`, `closed`.
Claim types: `verified_fact`, `measured_metric`, `inference`, `hypothesis`,
`historical_context`, `unsupported`.

Every claim requires non-empty `text` and `action_allowed`. Verified facts and
measured metrics additionally require non-empty `evidence`; inferences and
hypotheses require non-empty `falsifier`. Unsupported claims must set
`action_allowed` to `none`, `no_action`, or `not_action_eligible`.

To mark a state `ready_for_parent_review`, set verification status to
`complete` or `completed` with a non-empty `evidence` array. Set adversarial
review status to `complete` or `completed` with non-empty
`load_bearing_claims` and `falsification_attempts` arrays and a non-empty
`result` string.

Live authorization requires `gates.live_authorization: true`, a non-empty
`gates.falsifier`, `gates.abort_gate`, and `gates.promotion_rule`. Validation
also checks every authority path that is supplied.

Minimal valid offline state:

```json
{
  "schema_version": 1, "objective": "Compare two offline parsers",
  "workspace": ".", "authority_paths": ["."], "headline_metric": "latency_ms",
  "historical_best": null, "current_control": "parser-a", "candidate": "parser-b",
  "lifecycle_state": "offline_attribution", "allowed_actions": ["inspect offline artifacts"],
  "forbidden_actions": ["live benchmark"], "claims": [],
  "gates": {}, "verification": {"status": "pending"},
  "adversarial_review": {"status": "pending"}, "next_action": "collect offline evidence",
  "handoff_status": "in_progress"
}
```
