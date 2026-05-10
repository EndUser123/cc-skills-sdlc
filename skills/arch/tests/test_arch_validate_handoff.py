from __future__ import annotations

from pathlib import Path

from arch_validate import validate_adr


def test_planning_bound_adr_requires_planning_handoff_packet(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-003-example.md"
    adr.write_text(
        """# ADR-003: Example

## Context

Example context.

## Contract Authority Packet

```yaml
contract_authority_packet:
  packet_version: "1"
  contract_sensitive: true
  authority:
    closure_source: "contract_authority_packet"
    prose_role: "explanatory_only"
  boundaries:
    - boundary_id: "plan-artifact"
      producer: "/planning"
      consumer: "/code"
      schema:
        id: "plan-artifact"
        version: "1"
      required_fields: ["status"]
      optional_fields: []
      freshness_authority: "plan frontmatter"
      invalidation_trigger: "plan rewrite"
      precedence_rule: "newer plan wins"
      failure_behavior: "Blocking gate in /planning before implementation-ready; blocker for /code and /verify"
      validator_owner: "/planning"
      proof_owner: "/verify"
      downstream_consumers: ["/code"]
```

## Implementation Sequence

| Order | Component |
|-------|-----------|
| 1 | Build it |
""",
        encoding="utf-8",
    )

    result = validate_adr(str(adr))

    assert result["status"] == "BLOCKED"
    finding_ids = {finding["id"] for finding in result["findings"]}
    assert "ADR-003" in finding_ids


def test_planning_bound_adr_with_handoff_packet_passes_handoff_check(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-004-example.md"
    adr.write_text(
        """# ADR-004: Example

## Contract Authority Packet

```yaml
contract_authority_packet:
  packet_version: "1"
  contract_sensitive: true
  authority:
    closure_source: "contract_authority_packet"
    prose_role: "explanatory_only"
  boundaries:
    - boundary_id: "plan-artifact"
      producer: "/planning"
      consumer: "/code"
      schema:
        id: "plan-artifact"
        version: "1"
      required_fields: ["status"]
      optional_fields: []
      freshness_authority: "plan frontmatter"
      invalidation_trigger: "plan rewrite"
      precedence_rule: "newer plan wins"
      failure_behavior: "Blocking gate in /planning before implementation-ready; blocker for /code and /verify"
      validator_owner: "/planning"
      proof_owner: "/verify"
      downstream_consumers: ["/code"]
```

## Planning Handoff Packet

```yaml
planning_handoff_packet:
  packet_version: "1"
  source_adr: "P:\\\\\\packages/example/arch_decisions/ADR-004-example.md"
  plan_title: "Example implementation"
  goal: "Implement the example change."
  implementation_changes:
    - task_id: "TASK-001"
      title: "Do the thing"
  contract_authority_reference:
    contract_sensitive: true
```

INSTRUCTION: Execute skill planning

Step 1: Call Skill("planning") to load the planning workflow
Step 2: Proceed with implementation planning using the closed architecture

## Implementation Sequence

| Order | Component |
|-------|-----------|
| 1 | Build it |
""",
        encoding="utf-8",
    )

    result = validate_adr(str(adr))

    assert result["status"] == "READY"
    assert result["planning_handoff_packet_version"] == "1"


def test_planning_bound_adr_without_instruction_or_return_to_caller_blocks(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-005-example.md"
    adr.write_text(
        """# ADR-005: Example

## Contract Authority Packet

```yaml
contract_authority_packet:
  packet_version: "1"
  contract_sensitive: true
  authority:
    closure_source: "contract_authority_packet"
    prose_role: "explanatory_only"
  boundaries:
    - boundary_id: "plan-artifact"
      producer: "/planning"
      consumer: "/code"
      schema:
        id: "plan-artifact"
        version: "1"
      required_fields: ["status"]
      optional_fields: []
      freshness_authority: "plan frontmatter"
      invalidation_trigger: "plan rewrite"
      precedence_rule: "newer plan wins"
      failure_behavior: "Blocking gate in /planning before implementation-ready; blocker for /code and /verify"
      validator_owner: "/planning"
      proof_owner: "/verify"
      downstream_consumers: ["/code"]
```

## Planning Handoff Packet

```yaml
planning_handoff_packet:
  packet_version: "1"
  source_adr: "P:\\\\\\packages/example/arch_decisions/ADR-005-example.md"
  plan_title: "Example implementation"
  goal: "Implement the example change."
  implementation_changes:
    - task_id: "TASK-001"
      title: "Do the thing"
  contract_authority_reference:
    contract_sensitive: true
```
""",
        encoding="utf-8",
    )

    result = validate_adr(str(adr))

    assert result["status"] == "BLOCKED"
    finding_ids = {finding["id"] for finding in result["findings"]}
    assert "ADR-HANDOFF-005" in finding_ids


def test_nested_planning_return_to_caller_satisfies_routing_contract(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-006-example.md"
    adr.write_text(
        """# ADR-006: Example

## Contract Authority Packet

```yaml
contract_authority_packet:
  packet_version: "1"
  contract_sensitive: true
  authority:
    closure_source: "contract_authority_packet"
    prose_role: "explanatory_only"
  boundaries:
    - boundary_id: "plan-artifact"
      producer: "/planning"
      consumer: "/code"
      schema:
        id: "plan-artifact"
        version: "1"
      required_fields: ["status"]
      optional_fields: []
      freshness_authority: "plan frontmatter"
      invalidation_trigger: "plan rewrite"
      precedence_rule: "newer plan wins"
      failure_behavior: "Blocking gate in /planning before implementation-ready; blocker for /code and /verify"
      validator_owner: "/planning"
      proof_owner: "/verify"
      downstream_consumers: ["/code"]
```

## Planning Handoff Packet

```yaml
planning_handoff_packet:
  packet_version: "1"
  source_adr: "P:\\\\\\packages/example/arch_decisions/ADR-006-example.md"
  plan_title: "Example implementation"
  goal: "Implement the example change."
  implementation_changes:
    - task_id: "TASK-001"
      title: "Do the thing"
  contract_authority_reference:
    contract_sensitive: true
```

RETURN TO CALLER: /planning
Resume policy: automatic
Caller action: consume packet, rewrite plan, rerun auto_verify
""",
        encoding="utf-8",
    )

    result = validate_adr(str(adr))

    assert result["status"] == "READY"
    assert result["planning_handoff_packet_version"] == "1"
