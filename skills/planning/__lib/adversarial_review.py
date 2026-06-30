from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# NOTE: Adversarial artifacts default to the project artifacts tree
# (<root>/<plan>/<terminal_id>/), where <root> is CLAUDE_ADVERSARIAL_ROOT or
# P:/.claude/.artifacts/adversarial. auto_verify.py searches this same root.
# The previous plan-parent coupling was retired because it dropped scratch
# into ~/.claude/plans/ when plans lived in the user home directory.
REFERENCE_PROMPTS_PATH = Path(__file__).resolve().parents[1] / "references" / "adversarial-agent-prompts.md"
AGENT_FINDINGS_FILENAMES = {
    "compliance": "compliance-findings.json",
    "logic": "logic-findings.json",
    "testing": "testing-findings.json",
    "security": "security-findings.json",
    "failure-modes": "failure-modes-findings.json",
    "critic": "critic-findings.json",
    "deepseek-adversarial": "deepseek-adversarial-findings.json",
}
PHASE1_AGENTS = ("compliance", "logic", "testing", "security", "failure-modes")
PHASE1_OPTIONAL_EXTERNAL = ("deepseek-adversarial",)
ALL_AGENTS = PHASE1_AGENTS + ("critic",) + PHASE1_OPTIONAL_EXTERNAL
UNRESOLVED_PROMPT_TOKENS = (
    "{sanitized_plan_name}",
    "<plan_path>",
    "<findings_dir>",
    "<findings_path>",
)
TASK_BLOCK_PATTERN = re.compile(
    r'Task\(subagent_type="(?P<subagent_type>[^"]+)",\s*'
    r'description="(?P<description>[^"]+)",\s*'
    r'prompt="""(?P<prompt>.*?)"""\)',
    re.DOTALL,
)


@dataclass(frozen=True)
class AdversarialReviewContext:
    plan_path: str
    terminal_id: str
    sanitized_plan_name: str
    base_dir: Path
    workflow_stage_path: Path
    findings_paths: dict[str, Path]

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_path": self.plan_path,
            "terminal_id": self.terminal_id,
            "sanitized_plan_name": self.sanitized_plan_name,
            "findings_dir": str(self.base_dir),
            "workflow_stage_path": str(self.workflow_stage_path),
            "findings_paths": {
                agent: str(path) for agent, path in self.findings_paths.items()
            },
        }


@dataclass(frozen=True)
class DispatchSpec:
    agent: str
    subagent_type: str
    description: str
    findings_path: Path
    prompt: str


def is_multi_llm_enabled() -> bool:
    return os.environ.get("SDLC_MULTI_LLM", "0") == "1"


def detect_terminal_id() -> str:
    terminal_id = os.environ.get("CLAUDE_TERMINAL_ID", "").strip()
    if terminal_id:
        return terminal_id
    wt_session = os.environ.get("WT_SESSION", "").strip()
    if wt_session:
        return f"console_{wt_session}"
    return "unknown"


def sanitize_plan_name(plan_path: str) -> str:
    name = Path(plan_path).stem
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return sanitized or "plan"


def default_adversarial_root() -> Path:
    """Resolve the default adversarial-artifacts root.

    Override with the CLAUDE_ADVERSARIAL_ROOT env var; otherwise use the project
    artifacts tree so scratch stays out of ~/.claude/plans/ and out of the repo
    root. auto_verify.py searches this same root.
    """
    env_root = os.environ.get("CLAUDE_ADVERSARIAL_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    return Path("P:/.claude/.artifacts/adversarial")


def build_adversarial_review_context(
    plan_path: str,
    *,
    root: str | Path | None = None,
    terminal_id: str | None = None,
) -> AdversarialReviewContext:
    resolved_plan_path = str(Path(plan_path))
    resolved_terminal_id = terminal_id or detect_terminal_id()
    sanitized_plan_name = sanitize_plan_name(resolved_plan_path)
    # Default to the project artifacts tree so adversarial scratch stays out of
    # ~/.claude/plans/ and out of the repo root. Override via the `root` kwarg
    # or the CLAUDE_ADVERSARIAL_ROOT env var.
    if root is None:
        base_root = default_adversarial_root()
    else:
        base_root = Path(root)
    base_dir = base_root / sanitized_plan_name / resolved_terminal_id
    findings_paths = {
        agent: base_dir / filename
        for agent, filename in AGENT_FINDINGS_FILENAMES.items()
    }
    return AdversarialReviewContext(
        plan_path=resolved_plan_path,
        terminal_id=resolved_terminal_id,
        sanitized_plan_name=sanitized_plan_name,
        base_dir=base_dir,
        workflow_stage_path=base_dir / "workflow_stage.json",
        findings_paths=findings_paths,
    )


def write_workflow_stage(
    context: AdversarialReviewContext,
    stage: str,
    **extra: Any,
) -> Path:
    context.base_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "plan_path": context.plan_path,
        "terminal_id": context.terminal_id,
    }
    if extra:
        payload.update(extra)
    context.workflow_stage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return context.workflow_stage_path


def prepare_adversarial_review_context(
    plan_path: str,
    *,
    root: str | Path | None = None,
    terminal_id: str | None = None,
) -> AdversarialReviewContext:
    context = build_adversarial_review_context(
        plan_path,
        root=root,
        terminal_id=terminal_id,
    )
    write_workflow_stage(context, "step_4a")
    return context


def resolve_prompt_template(
    template: str,
    *,
    plan_path: str,
    findings_dir: str,
    findings_path: str,
) -> str:
    rendered = (
        template.replace("<plan_path>", plan_path)
        .replace("<findings_dir>", findings_dir)
        .replace("<findings_path>", findings_path)
    )
    unresolved = [token for token in UNRESOLVED_PROMPT_TOKENS if token in rendered]
    if unresolved:
        raise ValueError(
            "Prompt template contains unresolved dispatch token(s): "
            + ", ".join(sorted(unresolved))
        )
    return rendered


def parse_reference_dispatch_prompts(
    reference_text: str,
) -> dict[str, tuple[str, str, str]]:
    """Parse canonical adversarial-agent prompt templates from the reference doc."""
    prompts: dict[str, tuple[str, str, str]] = {}
    for match in TASK_BLOCK_PATTERN.finditer(reference_text):
        subagent_type = match.group("subagent_type")
        description = match.group("description")
        prompt = match.group("prompt")
        agent = subagent_type.removeprefix("adversarial-")
        prompts[agent] = (subagent_type, description, prompt)

    # External agents are dispatched via Bash/ai-cli, not Agent tool, so they have no
    # Task() block in the reference prompts file. Exclude them from the validation check.
    expected = set(ALL_AGENTS) - set(PHASE1_OPTIONAL_EXTERNAL)
    missing = sorted(expected - set(prompts))
    if missing:
        raise ValueError(
            "Reference prompt file is missing canonical adversarial agent prompt(s): "
            + ", ".join(missing)
        )
    return prompts


def load_reference_dispatch_prompts(
    reference_path: str | Path | None = None,
) -> dict[str, tuple[str, str, str]]:
    path = Path(reference_path) if reference_path is not None else REFERENCE_PROMPTS_PATH
    return parse_reference_dispatch_prompts(path.read_text(encoding="utf-8"))


def build_dispatch_specs(
    context: AdversarialReviewContext,
    *,
    phase: str = "phase1",
    agents: list[str] | tuple[str, ...] | None = None,
    reference_path: str | Path | None = None,
) -> list[DispatchSpec]:
    """Build canonical dispatch specs from the reference prompts with resolved paths."""
    prompts = load_reference_dispatch_prompts(reference_path)
    if agents is not None:
        agent_names = tuple(agents)
    elif phase == "phase1":
        agent_names = PHASE1_AGENTS
    elif phase == "critic":
        agent_names = ("critic",)
    elif phase == "all":
        agent_names = ALL_AGENTS
    else:
        raise ValueError(f"Unsupported adversarial review phase: {phase}")

    unknown = sorted(set(agent_names) - set(ALL_AGENTS))
    if unknown:
        raise ValueError("Unknown adversarial agent(s): " + ", ".join(unknown))

    # External agents (deepseek-adversarial) are dispatched via Bash, not prompts
    prompt_dispatchable = tuple(a for a in agent_names if a not in PHASE1_OPTIONAL_EXTERNAL)

    specs: list[DispatchSpec] = []
    for agent in prompt_dispatchable:
        subagent_type, description, template = prompts[agent]
        findings_path = context.findings_paths[agent]
        prompt = resolve_prompt_template(
            template,
            plan_path=context.plan_path,
            findings_dir=str(context.base_dir),
            findings_path=str(findings_path),
        )
        specs.append(
            DispatchSpec(
                agent=agent,
                subagent_type=subagent_type,
                description=description,
                findings_path=findings_path,
                prompt=prompt,
            )
        )
    return specs


def validate_findings_output_path(
    agent: str,
    returned_path: str | Path,
    context: AdversarialReviewContext,
) -> bool:
    """Return True only when the agent returned its exact terminal-scoped findings path."""
    expected = context.findings_paths[agent].resolve()
    actual = Path(returned_path).resolve()
    return actual == expected


def validate_findings_file(
    findings_path: str | Path,
    *,
    plan_path: str,
    expected_path: str | Path | None = None,
    max_age_seconds: int = 86400,
    now: float | None = None,
) -> dict[str, Any]:
    """Validate that a findings file is the current plan's exact, fresh, canonical output."""
    path = Path(findings_path)
    if expected_path is not None and path.resolve() != Path(expected_path).resolve():
        return {"valid": False, "reason": "unexpected_path", "path": str(path)}
    if not path.exists():
        return {"valid": False, "reason": "missing", "path": str(path)}
    try:
        if path.stat().st_size <= 0:
            return {"valid": False, "reason": "empty", "path": str(path)}
        age_seconds = (now if now is not None else time.time()) - os.path.getmtime(path)
        if max_age_seconds >= 0 and age_seconds > max_age_seconds:
            return {"valid": False, "reason": "stale", "path": str(path), "age_seconds": age_seconds}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"valid": False, "reason": "invalid_json", "path": str(path)}
    except OSError as exc:
        return {"valid": False, "reason": f"oserror:{exc.__class__.__name__}", "path": str(path)}

    if not isinstance(payload, dict):
        return {"valid": False, "reason": "invalid_payload_type", "path": str(path)}
    if payload.get("plan_path") != plan_path:
        return {"valid": False, "reason": "plan_path_mismatch", "path": str(path)}
    return {"valid": True, "reason": "ok", "path": str(path)}


def collect_findings_status(
    context: AdversarialReviewContext,
    *,
    phase: str = "phase1",
    max_age_seconds: int = 86400,
    now: float | None = None,
) -> dict[str, Any]:
    """Report which canonical findings files are valid, missing, or invalid for resume/retry."""
    statuses: dict[str, dict[str, Any]] = {}
    for spec in build_dispatch_specs(context, phase=phase):
        statuses[spec.agent] = validate_findings_file(
            spec.findings_path,
            plan_path=context.plan_path,
            expected_path=spec.findings_path,
            max_age_seconds=max_age_seconds,
            now=now,
        )

    valid = sorted(agent for agent, status in statuses.items() if status["valid"])
    missing = sorted(agent for agent, status in statuses.items() if status["reason"] == "missing")
    invalid = {
        agent: status["reason"]
        for agent, status in statuses.items()
        if not status["valid"] and status["reason"] != "missing"
    }
    return {
        "complete": len(valid) == len(statuses),
        "valid": valid,
        "missing": missing,
        "invalid": invalid,
        "statuses": statuses,
    }
