"""Design v1.1 schemas — DesignPayload, ContractAuthorityPacket, ContractBoundary, CriticFinding."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    DEFERRED = "deferred"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ContractBoundary:
    boundary_id: str
    producer: str
    consumer: str
    input_schema_id: str
    output_schema_id: str
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    freshness_authority: str = "producer"
    invalidation_trigger: str = "explicit_invalidate"
    failure_behavior: str = "block"
    transcript_vs_artifact_precedence: str = "artifact"
    validator_owner: str = ""
    proof_owner: str = ""
    downstream_consumers: list[str] = field(default_factory=list)


@dataclass
class ContractAuthorityPacket:
    identity_model: str = "session_id"
    ordering_strategy: str = "append"
    dedupe_mechanism: str = "none"
    freshness_authority: str = "producer"
    event_source_of_truth: str = "transcript"
    decision_closure_status: str = "open"
    boundaries: list[ContractBoundary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_model": self.identity_model,
            "ordering_strategy": self.ordering_strategy,
            "dedupe_mechanism": self.dedupe_mechanism,
            "freshness_authority": self.freshness_authority,
            "event_source_of_truth": self.event_source_of_truth,
            "decision_closure_status": self.decision_closure_status,
            "boundaries": [
                {
                    "boundary_id": b.boundary_id,
                    "producer": b.producer,
                    "consumer": b.consumer,
                    "input_schema_id": b.input_schema_id,
                    "output_schema_id": b.output_schema_id,
                    "required_fields": b.required_fields,
                    "optional_fields": b.optional_fields,
                    "freshness_authority": b.freshness_authority,
                    "invalidation_trigger": b.invalidation_trigger,
                    "failure_behavior": b.failure_behavior,
                    "transcript_vs_artifact_precedence": b.transcript_vs_artifact_precedence,
                    "validator_owner": b.validator_owner,
                    "proof_owner": b.proof_owner,
                    "downstream_consumers": b.downstream_consumers,
                }
                for b in self.boundaries
            ],
        }


@dataclass
class CriticFinding:
    severity: Severity
    category: str
    description: str
    location: str = ""
    suggestion: str = ""
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "description": self.description,
            "location": self.location,
            "suggestion": self.suggestion,
            "verified": self.verified,
        }


@dataclass
class DesignPayload:
    run_id: str
    mode: str
    scope: str
    user_query: str
    ast_summary: str
    sop: str
    template_name: str
    cap: ContractAuthorityPacket
    critic_findings: list[CriticFinding]
    adr_markdown: str
    planning_handoff: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "scope": self.scope,
            "user_query": self.user_query,
            "ast_summary": self.ast_summary,
            "sop": self.sop,
            "template_name": self.template_name,
            "cap": self.cap.to_dict(),
            "critic_findings": [f.to_dict() for f in self.critic_findings],
            "adr_markdown": self.adr_markdown,
            "planning_handoff": self.planning_handoff,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DesignPayload:
        cap_data = data.get("cap", {})
        boundaries = [
            ContractBoundary(**b) for b in cap_data.get("boundaries", [])
        ]
        cap = ContractAuthorityPacket(
            identity_model=cap_data.get("identity_model", "session_id"),
            ordering_strategy=cap_data.get("ordering_strategy", "append"),
            dedupe_mechanism=cap_data.get("dedupe_mechanism", "none"),
            freshness_authority=cap_data.get("freshness_authority", "producer"),
            event_source_of_truth=cap_data.get("event_source_of_truth", "transcript"),
            decision_closure_status=cap_data.get("decision_closure_status", "open"),
            boundaries=boundaries,
        )
        findings = [
            CriticFinding(
                severity=Severity(f["severity"]),
                category=f["category"],
                description=f["description"],
                location=f.get("location", ""),
                suggestion=f.get("suggestion", ""),
                verified=f.get("verified", False),
            )
            for f in data.get("critic_findings", [])
        ]
        return cls(
            run_id=data["run_id"],
            mode=data["mode"],
            scope=data["scope"],
            user_query=data["user_query"],
            ast_summary=data["ast_summary"],
            sop=data["sop"],
            template_name=data["template_name"],
            cap=cap,
            critic_findings=findings,
            adr_markdown=data["adr_markdown"],
            planning_handoff=data.get("planning_handoff"),
        )


# Alias for convenience
DesignPayloadDict = dict[str, Any]
