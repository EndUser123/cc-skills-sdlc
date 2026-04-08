from __future__ import annotations

from dataclasses import dataclass, field
import re

REQUIRED_PLAN_MATRIX_FIELDS = [
    "Boundary",
    "Contract authority packet",
    "Producer",
    "Consumer",
    "Input Schema",
    "Output Schema",
    "Required Fields",
    "Freshness Authority",
    "Invalidation Trigger",
    "Failure Behavior",
    "Packet Alignment",
    "Test Binding",
]

REQUIRED_BOUNDARY_FIELDS = {
    "producer",
    "consumer",
    "schema.id",
    "schema.version",
    "required_fields",
    "freshness_authority",
    "invalidation_trigger",
    "precedence_rule",
    "failure_behavior",
    "validator_owner",
    "proof_owner",
}

PLACEHOLDER_BINDINGS = {
    "[tbd]",
    "[tbd per phase]",
    "tbd",
    "todo",
    "n/a",
}

ACTIVE_PLAN_ARTIFACT_FAILURE_BEHAVIOR = (
    "Blocking gate in /planning before implementation-ready; blocker for /code and /verify"
)


@dataclass(slots=True)
class BoundaryContract:
    boundary_id: str
    producer: str = ""
    consumer: str = ""
    schema_id: str = ""
    schema_version: str = ""
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    freshness_authority: str = ""
    invalidation_trigger: str = ""
    precedence_rule: str = ""
    failure_behavior: str = ""
    validator_owner: str = ""
    proof_owner: str = ""
    downstream_consumers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ContractAuthorityPacket:
    packet_version: str = ""
    boundaries: dict[str, BoundaryContract] = field(default_factory=dict)


@dataclass(slots=True)
class PlanningHandoffPacket:
    packet_version: str = ""
    source_adr: str = ""
    plan_title: str = ""
    goal: str = ""
    implementation_task_ids: list[str] = field(default_factory=list)
    contract_sensitive: bool | None = None
    open_questions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PlanningSourcePacket:
    packet_version: str = ""
    source_path: str = ""
    source_kind: str = ""
    plan_title: str = ""
    goal: str = ""
    implementation_task_ids: list[str] = field(default_factory=list)
    contract_sensitive: bool | None = None
    open_questions: list[str] = field(default_factory=list)


def _normalize_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def extract_markdown_table(section_text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Extract the first markdown table from a section."""
    lines = [line.rstrip() for line in section_text.splitlines() if line.strip()]
    header_idx = -1
    # Markdown table separator: row of only |, -, :, space (with optional leading/trailing |)
    # e.g. |---|---|---| or |---|:---|:---|  or |-------------|-----------------|
    for idx in range(len(lines) - 1):
        if lines[idx].startswith("|"):
            # Strip outer | delimiters; remaining chars must be valid separator content
            sep = lines[idx + 1]
            inner = sep[1:-1] if sep.startswith("|") and sep.endswith("|") else sep
            # Valid: whitespace, -, :, |
            if all(c in ("-", ":", " ", "|") for c in inner):
                header_idx = idx
                break

    if header_idx < 0:
        return [], []

    headers = [_normalize_cell(cell) for cell in lines[header_idx].strip("|").split("|")]
    rows: list[dict[str, str]] = []

    for raw_line in lines[header_idx + 2 :]:
        if not raw_line.startswith("|"):
            break
        cells = [_normalize_cell(cell) for cell in raw_line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells, strict=False)))

    return headers, rows


def find_contract_boundary_rows(plan_text: str) -> tuple[list[str], list[dict[str, str]]]:
    pattern = r"^##\s+Contract Boundary Matrix.*?(?=^##\s|\Z)"
    match = re.search(pattern, plan_text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return [], []
    return extract_markdown_table(match.group(0))


def parse_contract_authority_packet(markdown_text: str) -> ContractAuthorityPacket:
    """Parse the markdown-rendered packet block from an ADR.

    The packet is written as YAML-like markdown. This parser keeps to the
    stable fields that downstream validators need for alignment checks.
    """
    packet = ContractAuthorityPacket()
    packet_match = re.search(
        r"contract_authority_packet:\s*(.*?)(?=^```|\Z)",
        markdown_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not packet_match:
        return packet

    packet_body = packet_match.group(1)
    version_match = re.search(r"packet_version:\s*\"?([^\n\"]+)\"?", packet_body)
    if version_match:
        packet.packet_version = version_match.group(1).strip()

    boundary_pattern = re.compile(
        r"^\s*-\s+boundary_id:\s*\"([^\"]+)\"(.*?)(?=^\s*-\s+boundary_id:|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    for match in boundary_pattern.finditer(packet_body):
        boundary_id = match.group(1).strip()
        block = match.group(2)
        contract = BoundaryContract(boundary_id=boundary_id)

        simple_fields = {
            "producer": "producer",
            "consumer": "consumer",
            "freshness_authority": "freshness_authority",
            "invalidation_trigger": "invalidation_trigger",
            "precedence_rule": "precedence_rule",
            "failure_behavior": "failure_behavior",
            "validator_owner": "validator_owner",
            "proof_owner": "proof_owner",
        }
        for target, attr in simple_fields.items():
            field_match = re.search(rf"{re.escape(target)}:\s*\"([^\"]*)\"", block)
            if field_match:
                setattr(contract, attr, field_match.group(1).strip())

        id_match = re.search(r"schema:\s*.*?id:\s*\"([^\"]+)\"", block, flags=re.DOTALL)
        version_match = re.search(r"schema:\s*.*?version:\s*\"([^\"]+)\"", block, flags=re.DOTALL)
        if id_match:
            contract.schema_id = id_match.group(1).strip()
        if version_match:
            contract.schema_version = version_match.group(1).strip()

        for field_name, attr in (("required_fields", "required_fields"), ("optional_fields", "optional_fields"), ("downstream_consumers", "downstream_consumers")):
            list_match = re.search(rf"{field_name}:\s*\[(.*?)\]", block, flags=re.DOTALL)
            if list_match:
                values = [
                    _normalize_cell(item.strip("\"' "))
                    for item in list_match.group(1).split(",")
                    if item.strip()
                ]
                setattr(contract, attr, values)
            else:
                values = re.findall(rf"{field_name}:\s*\n((?:\s*-\s+[^\n]+\n?)*)", block, flags=re.DOTALL)
                if values:
                    items = [
                        _normalize_cell(item)
                        for item in re.findall(r"-\s+([^\n]+)", values[0])
                    ]
                    setattr(contract, attr, items)

        packet.boundaries[boundary_id] = contract

    return packet


def parse_planning_handoff_packet(markdown_text: str) -> PlanningHandoffPacket:
    """Parse the markdown-rendered planning handoff packet block from an ADR."""
    packet = PlanningHandoffPacket()
    packet_match = re.search(
        r"planning_handoff_packet:\s*(.*?)(?=^```|\Z)",
        markdown_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not packet_match:
        return packet

    body = packet_match.group(1)
    simple_fields = {
        "packet_version": "packet_version",
        "source_adr": "source_adr",
        "plan_title": "plan_title",
        "goal": "goal",
    }
    for field_name, attr in simple_fields.items():
        field_match = re.search(rf"{field_name}:\s*\"([^\"]*)\"", body)
        if not field_match:
            field_match = re.search(rf"{field_name}:\s*([^\n]+)", body)
        if field_match:
            setattr(packet, attr, _normalize_cell(field_match.group(1).strip("\"' ")))

    task_ids = re.findall(r"task_id:\s*\"?([^\n\"]+)\"?", body)
    packet.implementation_task_ids = [_normalize_cell(task_id) for task_id in task_ids if task_id.strip()]

    contract_sensitive_match = re.search(
        r"contract_authority_reference:\s*.*?contract_sensitive:\s*(true|false)",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if contract_sensitive_match:
        packet.contract_sensitive = contract_sensitive_match.group(1).lower() == "true"

    open_questions_block = re.search(r"open_questions:\s*\n((?:\s*-\s+[^\n]+\n?)*)", body, flags=re.DOTALL)
    if open_questions_block:
        packet.open_questions = [
            _normalize_cell(item)
            for item in re.findall(r"-\s+([^\n]+)", open_questions_block.group(1))
        ]

    return packet


def parse_planning_source_packet(markdown_text: str) -> PlanningSourcePacket:
    """Parse the markdown-rendered planning source packet block from a source artifact."""
    packet = PlanningSourcePacket()
    packet_match = re.search(
        r"planning_source_packet:\s*(.*?)(?=^```|\Z)",
        markdown_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not packet_match:
        return packet

    body = packet_match.group(1)
    simple_fields = {
        "packet_version": "packet_version",
        "source_path": "source_path",
        "source_kind": "source_kind",
        "plan_title": "plan_title",
        "goal": "goal",
    }
    for field_name, attr in simple_fields.items():
        field_match = re.search(rf"{field_name}:\s*\"([^\"]*)\"", body)
        if not field_match:
            field_match = re.search(rf"{field_name}:\s*([^\n]+)", body)
        if field_match:
            setattr(packet, attr, _normalize_cell(field_match.group(1).strip("\"' ")))

    task_ids = re.findall(r"task_id:\s*\"?([^\n\"]+)\"?", body)
    packet.implementation_task_ids = [_normalize_cell(task_id) for task_id in task_ids if task_id.strip()]

    contract_sensitive_match = re.search(
        r"contract_sensitive:\s*(true|false)",
        body,
        flags=re.IGNORECASE,
    )
    if contract_sensitive_match:
        packet.contract_sensitive = contract_sensitive_match.group(1).lower() == "true"

    open_questions_block = re.search(r"open_questions:\s*\n((?:\s*-\s+[^\n]+\n?)*)", body, flags=re.DOTALL)
    if open_questions_block:
        packet.open_questions = [
            _normalize_cell(item)
            for item in re.findall(r"-\s+([^\n]+)", open_questions_block.group(1))
        ]

    return packet


def adr_requires_planning_handoff(markdown_text: str) -> bool:
    """Return True when an ADR clearly looks intended to feed planning."""
    if re.search(r"INSTRUCTION:\s*Execute skill planning", markdown_text, re.IGNORECASE):
        return True
    return bool(re.search(r"^##\s+Implementation Sequence\b", markdown_text, re.MULTILINE))
