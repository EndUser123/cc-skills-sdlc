#!/usr/bin/env python3
"""Canonical /go SDLC orchestrator with selectable worker dispatch.

Default dispatch is pi. Override with:
    python orchestrate.py --dispatch claude --prompt "..."
    GO_DISPATCH=claude python orchestrate.py --prompt "..."
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

VALID_DISPATCHES = ("pi", "claude", "local")
SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_context import resolve as _resolve_run_context, canonical_terminal_id as _canonical_terminal_id  # noqa: E402
from preflight_propose import run_preflight as _run_preflight  # noqa: E402


@dataclass
class TaskContract:
    """Parsed task contract from active-task_*.json."""

    task_id: str
    title: str
    objective: str
    scope_in: list[str]
    scope_out: list[str]
    acceptance_criteria: list[str]
    verification_commands: list[str]
    forbidden_files: list[str]
    source: str
    raw: dict[str, Any]

    @classmethod
    def from_active_task(cls, data: dict[str, Any]) -> "TaskContract":
        inner = data.get("task", data)
        return cls(
            task_id=inner.get("id", "unknown"),
            title=inner.get("title", ""),
            objective=inner.get("objective", ""),
            scope_in=inner.get("scope_in", []),
            scope_out=inner.get("scope_out", []),
            acceptance_criteria=inner.get("acceptance_criteria", []),
            verification_commands=inner.get("verification_commands", []),
            forbidden_files=inner.get("forbidden_files", []),
            source=data.get("source", "unknown"),
            raw=inner,
        )




def inject_route_decision(
    state_dir: Path, run_id: str, dispatch: str,
    pi_info: "PiModelInfo | None" = None,
) -> None:
    """Write routeDecision metadata into the active-task JSON.

    Metadata-only -- does not change dispatch behavior or routing.
    Records the correct abstraction: harness, model source, role separation
    status, and rejected harnesses with reasons.
    """
    task_file = state_dir / f"active-task_{run_id}.json"
    if not task_file.exists():
        return
    task_data = json.loads(task_file.read_text(encoding="utf-8"))
    task = task_data.get("task", task_data)

    # Determine model source
    override = os.environ.get("GO_MODEL_OVERRIDE", "").strip()
    local_llm = os.environ.get("GO_LOCAL_LLM", "").strip()
    if override:
        model_source = "GO_MODEL_OVERRIDE"
    elif dispatch == "local" and local_llm:
        model_source = "GO_LOCAL_LLM"
    elif dispatch == "pi" and pi_info is not None:
        model_source = "complexity-classifier"
    else:
        model_source = "unknown"

    # Rejected harnesses with reasons
    rejected: list[dict[str, str]] = []
    for harness, reason in [
        ("claude", "unsupported-stub: no non-interactive worker implementation"),
        ("agy", "not-wired: agy is not integrated into /go dispatch"),
    ]:
        rejected.append({"harness": harness, "reason": reason})
    if dispatch != "local":
        if local_llm:
            rejected.append({"harness": "local", "reason": "not-selected"})
        else:
            rejected.append({"harness": "local", "reason": "unavailable: GO_LOCAL_LLM not set"})
    if dispatch != "pi":
        rejected.append({"harness": "pi", "reason": "not-selected"})

    pi_transcript_review = dispatch == "pi"

    chosen_model: str | None = None
    complexity_tier: str | None = None
    if dispatch == "pi" and pi_info is not None:
        chosen_model = pi_info.pi_model
        complexity_tier = pi_info.tier
    elif override:
        chosen_model = override
    elif dispatch == "local" and local_llm:
        chosen_model = local_llm
    else:
        chosen_model = None

    route: dict[str, object] = {
        "roleSeparation": False,
        "dispatchMode": "flat-single-harness",
        "plannerHarness": None,
        "plannerModelRoute": None,
        "implementerHarness": dispatch,
        "implementerModelRoute": chosen_model,
        "verifierHarness": "builtin-scripts",
        "verifierModelRoute": None,
        "selfVerificationAllowed": False,
        "piTranscriptReview": pi_transcript_review,
        "singleDispatchHarness": dispatch,
        "singleDispatchModel": chosen_model,
        "chosenDispatch": dispatch,
        "chosenModel": chosen_model,
        "modelSource": model_source,
        "complexityTier": complexity_tier,
        "fallbackPolicyVisibleToGo": False,
        "actualFallbackObserved": None,
        "rejectedHarnesses": rejected,
    }

    task["routeDecision"] = route
    write_json(task_file, task_data)


@dataclass
class PiModelInfo:
    """Resolved pi model from pi-model_*.json."""

    classifier_model: str
    tier: str
    pi_model: str

    @classmethod
    def load(cls, path: Path) -> "PiModelInfo":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)


@dataclass
class TranscriptVerdict:
    """Verdict from transcript review."""

    verdict: str
    reason: str
    critical_issues: list[str]

    @classmethod
    def from_subagent_json(cls, text: str) -> "TranscriptVerdict":
        data = json.loads(text)
        return cls(
            verdict=data.get("verdict", "FAIL"),
            reason=data.get("reason", ""),
            critical_issues=data.get("critical_issues", []),
        )


def default_dispatch() -> str:
    """Return dispatch mode from GO_DISPATCH, defaulting to pi."""

    value = os.environ.get("GO_DISPATCH", "pi").strip().lower()
    return value if value in VALID_DISPATCHES else "pi"


def script_path(*parts: str) -> Path:
    """Resolve a helper path inside the canonical /go skill."""

    return SKILL_DIR / Path(*parts)


def load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def now_utc_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_script(
    script: Path,
    args: list[str],
    state_dir: Path,
    run_id: str,
    cwd: Path | None = None,
) -> int:
    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["GO_RUN_ID"] = run_id
    env["GO_STATE_DIR"] = str(state_dir.resolve())
    if cwd is not None:
        env["WORKTREE"] = str(cwd.resolve())
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd or state_dir,
        env=env,
        capture_output=False,
    )
    return result.returncode


def phase_marker(state_dir: Path, phase: str, run_id: str) -> Path:
    p = state_dir / f".{phase}_{run_id}"
    touch(p)
    return p


def write_current_run(state_dir: Path, run_id: str, status: str, dispatch: str) -> None:
    terminal_id = _canonical_terminal_id()
    payload = {
        "schema_version": "go.current-run.v1",
        "run_id": run_id,
        "terminal_id": terminal_id,
        "go_state_dir": str(state_dir.resolve()),
        "dispatch": dispatch,
        "status": status,
        "updated_at": now_iso(),
    }
    write_json(state_dir / "current-run.json", payload)
    write_json(state_dir / f"current-run_{terminal_id}.json", payload)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="/go orchestrator")
    parser.add_argument(
        "--dispatch",
        choices=VALID_DISPATCHES,
        default=default_dispatch(),
        help="Worker dispatch mode. Precedence: CLI, GO_DISPATCH, pi.",
    )
    parser.add_argument("--prompt", help="Task description (overrides task queue)")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Generate a proposal artifact only; do NOT dispatch, verify, or mutate active-task.",
    )
    parser.add_argument(
        "--recon-only",
        action="store_true",
        help="Force worker to produce a recon/flow artifact and stop. Used to bootstrap the recon-before-dispatch requirement.",
    )
    parser.add_argument(
        "--recon-bypass",
        action="store_true",
        help="Skip the recon-before-dispatch requirement. Audit-logged.",
    )
    parser.add_argument("--plan", help="Path to plan.md")
    parser.add_argument("--tasks", help="Path to tasks.json")
    parser.add_argument("--scope-in", nargs="*", default=[], help="Scope in patterns")
    parser.add_argument("--forbidden", nargs="*", default=[], help="Forbidden files")
    return parser.parse_args(argv)


def default_verification_commands() -> list[str]:
    raw = os.environ.get("GO_DEFAULT_VERIFICATION_COMMANDS", "python -m pytest -q")
    return [part.strip() for part in raw.split(";") if part.strip()]


def _heading_or_stem(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                return title[:80]
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or "Plan task"


def create_plan_task(args: argparse.Namespace, state_dir: Path, run_id: str) -> TaskContract | None:
    plan_path = Path(args.plan).expanduser().resolve()
    if not plan_path.exists():
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "task-selection",
                "reason_code": "plan_file_not_found",
                "path": str(plan_path),
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return None

    plan_text = plan_path.read_text(encoding="utf-8")
    title = _heading_or_stem(plan_path, plan_text)
    terminal_id = _canonical_terminal_id()
    selected_at = now_utc_z()
    task_data: dict[str, Any] = {
        "run_id": run_id,
        "terminal_id": terminal_id,
        "selected_at": selected_at,
        "source": "plan-md",
        "source_ref": str(plan_path),
        "task": {
            "id": f"plan-{run_id[:8]}",
            "title": title,
            "objective": plan_text.strip() or title,
            "status": "selected",
            "priority": "P1",
            "scope_in": args.scope_in or [],
            "scope_out": [],
            "acceptance_criteria": [line.strip("- ").strip() for line in plan_text.splitlines() if line.strip().startswith("- ")],
            "verification_commands": default_verification_commands(),
            "forbidden_files": args.forbidden or [],
            "task_type": "implementation",
        },
    }
    write_json(state_dir / f"active-task_{run_id}.json", task_data)
    phase_marker(state_dir, "task-selected", run_id)
    return TaskContract.from_active_task(task_data)


def ensure_runtime_env(dispatch: str) -> tuple[Path, str]:
    terminal_id = _canonical_terminal_id()
    os.environ["TERMINAL_ID"] = terminal_id
    os.environ["CLAUDE_TERMINAL_ID"] = terminal_id
    # Recover run_id from disk before minting a fresh one (go.resume.v1 D3).
    recovered = _resolve_run_context()
    run_id = (
        os.environ.get("RUN_ID")
        or os.environ.get("GO_RUN_ID")
        or (recovered.run_id if recovered.resolved else "")
        or str(uuid.uuid4())
    )
    os.environ["RUN_ID"] = run_id
    os.environ["GO_RUN_ID"] = run_id
    os.environ.setdefault("MAX_ATTEMPTS", "3")
    default_state_dir = Path.cwd() / ".claude" / ".artifacts" / terminal_id / "go"
    state_dir = Path(os.environ.get("GO_STATE_DIR", str(default_state_dir))).resolve()
    os.environ["GO_STATE_DIR"] = str(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir, run_id


# NOTE: Not using any existing require_recon() because no equivalent exists in
# this repo. Searched via `grep -rn "require_recon" P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/go/`
# on 2026-07-02 — no matches. The CLI flags `--recon-only` and `--recon-bypass`
# were added in the same patch, so this is a fresh sub-system.

# Fields required in a recon/flow artifact for non-trivial /go tasks. Promoted
# from the agentic-reliability ladder to prevent "jump straight to coding" on
# broad, architectural, hook/plugin/router/orchestrator prompts.
_RECON_REQUIRED_FIELDS: tuple[str, ...] = (
    "objective",
    "task_classification",
    "entrypoint",
    "call_path",
    "files_read",
    "likely_edited_files",
    "existing_pattern_found",
    "ownership_layer",
    "source_vs_test_triage",
    "risk",
    "patch_budget",
    "verification_plan",
    "skip_reason",
)


class ReconMissingError(Exception):
    """Raised by require_recon when the required recon artifact is missing/incomplete."""


def _classify_prompt_for_recon(prompt: str) -> dict[str, Any]:
    """Classify whether a --prompt is high-risk (requires recon) or low-risk (skips)."""
    low = prompt.lower()
    high_risk_keywords = (
        "hook", "plugin", "router", "dispatcher", "orchestrator",
        "/go", "preflight", "stop gate", "pretooluse", "posttooluse",
        "sessionstart", "userpromptsubmit", "subagentstop",
        "architecture", "architectural", "broad", "system",
        "investigate", "audit", "design ", "review ", "diagnos",
        "refactor", "redesign", "migrat",
    )
    low_risk_keywords = (
        "typo", "rename ", "bump ", "wip", "whitespace",
        "add a test for", "add a comment",
    )
    is_low = any(k in low for k in low_risk_keywords)
    is_high = any(k in low for k in high_risk_keywords)
    is_long = len(prompt) >= 240
    if is_low and not (is_high or is_long):
        return {"requires_recon": False, "risk_class": "trivial"}
    if is_high or is_long:
        return {"requires_recon": True, "risk_class": "high"}
    return {"requires_recon": False, "risk_class": "moderate"}


def _emit_recon_telemetry(
    event: str, state_dir: Path, run_id: str, extra: dict[str, Any]
) -> None:
    """Emit a recon telemetry event to the existing sink. Fail-open."""
    try:
        from __lib.agentic_reliability_telemetry import log_event
        log_event(
            category="recon_before_dispatch",
            event=event,
            gate="recon_before_dispatch",
            session_id=run_id,
            terminal_id=_canonical_terminal_id(),
            decision="telemetry",
            extra=extra,
        )
    except Exception:
        pass


def require_recon(
    args: argparse.Namespace, state_dir: Path, run_id: str, prompt: str
) -> None:
    """For high-risk --prompt tasks, require a recon/flow artifact before
    load_or_create_task writes the active-task file. Raises ReconMissingError
    (caller must treat as a block) when the artifact is missing or incomplete.
    Audit-logs every event to the existing agentic_reliability_telemetry sink.
    """
    if getattr(args, "recon_bypass", False):
        _emit_recon_telemetry(
            "recon_bypass", state_dir, run_id,
            {"reason": "explicit_bypass", "prompt_len": len(prompt)},
        )
        return
    classification = _classify_prompt_for_recon(prompt)
    if not classification["requires_recon"]:
        return
    recon_path = state_dir / f"recon_{run_id}.json"
    if not recon_path.exists():
        blocked = {
            "phase": "recon",
            "reason_code": "missing_recon_artifact",
            "risk_class": classification["risk_class"],
            "required_artifact": str(recon_path),
            "required_fields": list(_RECON_REQUIRED_FIELDS),
            "message": (
                "High-risk prompt requires a recon/flow artifact before dispatch. "
                f"Write {recon_path} with the 13 required fields, "
                "or pass --recon-bypass to override (audit-logged), "
                "or pass --recon-only to have the worker produce the artifact."
            ),
        }
        write_json(state_dir / f"blocked_recon_{run_id}.json", blocked)
        touch(state_dir / f".blocked-recon_{run_id}")
        _emit_recon_telemetry("recon_missing", state_dir, run_id, blocked)
        raise ReconMissingError(blocked)
    try:
        with open(recon_path, encoding="utf-8") as fh:
            recon = json.loads(fh.read())
    except (OSError, json.JSONDecodeError) as exc:
        blocked = {
            "phase": "recon",
            "reason_code": "recon_parse_error",
            "error": str(exc),
            "required_artifact": str(recon_path),
        }
        write_json(state_dir / f"blocked_recon_{run_id}.json", blocked)
        touch(state_dir / f".blocked-recon_{run_id}")
        _emit_recon_telemetry("recon_parse_error", state_dir, run_id, blocked)
        raise ReconMissingError(blocked)
    missing = [f for f in _RECON_REQUIRED_FIELDS if f not in recon]
    if missing:
        blocked = {
            "phase": "recon",
            "reason_code": "recon_incomplete",
            "missing_fields": missing,
            "required_artifact": str(recon_path),
        }
        write_json(state_dir / f"blocked_recon_{run_id}.json", blocked)
        touch(state_dir / f".blocked-recon_{run_id}")
        _emit_recon_telemetry("recon_incomplete", state_dir, run_id, blocked)
        raise ReconMissingError(blocked)
    write_json(
        state_dir / f"recon-validated_{run_id}.json",
        {"recon_artifact": str(recon_path), "validated_at": now_utc_z()},
    )
    _emit_recon_telemetry(
        "recon_validated", state_dir, run_id,
        {"artifact": str(recon_path), "risk_class": classification["risk_class"]},
    )


def load_or_create_task(args: argparse.Namespace, state_dir: Path, run_id: str) -> TaskContract | None:
    if args.prompt:
        # Recon-before-dispatch gate (Phase 1 of agentic-reliability ladder).
        # Blocks dispatch for high-risk prompts until a recon artifact exists.
        if not getattr(args, "preflight_only", False) and not getattr(args, "recon_only", False):
            try:
                require_recon(args, state_dir, run_id, args.prompt)
            except ReconMissingError:
                return None
        explicit_verification = os.environ.get("GO_DEFAULT_VERIFICATION_COMMANDS", "").strip()
        verification_commands = default_verification_commands()
        if os.environ.get("GO_REQUIRE_EXPLICIT_VERIFICATION") == "1" and not explicit_verification:
            write_json(
                state_dir / f"blocked_{run_id}.json",
                {
                    "phase": "task-selection",
                    "reason_code": "missing_verification_commands",
                    "message": "Prompt task requires explicit verification commands before dispatch.",
                },
            )
            touch(state_dir / f".blocked_{run_id}")
            return None
        selected_at = now_utc_z()
        terminal_id = _canonical_terminal_id()
        task_data: dict[str, Any] = {
            "run_id": run_id,
            "terminal_id": terminal_id,
            "selected_at": selected_at,
            "source": "cli",
            "source_ref": "cli",
            "task": {
                "id": f"prompt-{run_id[:8]}",
                "title": args.prompt[:60],
                "objective": args.prompt,
                "status": "selected",
                "priority": "P1",
                "scope_in": args.scope_in or [],
                "scope_out": [],
                "acceptance_criteria": [],
                "verification_commands": verification_commands,
                "forbidden_files": args.forbidden or [],
                "task_type": "implementation",
            },
        }
        # Phase 5: include the verification plan from the matrix so the
        # worker sees task-specific verification expectations before
        # implementation. The plan is informational/advisory only —
        # it does not block dispatch.
        try:
            _preflight = importlib.import_module("preflight_propose")
            _classify = getattr(_preflight, "classify_dispatch", None)
            _suggest = getattr(_preflight, "verification_suggestions", None)
            _vp_fmm = getattr(_preflight, "verification_policy_from_fmm", None)
            _rewrite = getattr(_preflight, "rewrite_goal", None)
            if _classify and _suggest and _vp_fmm and _rewrite:
                _rewritten = _rewrite(args.prompt)
                _classify(_rewritten)
                task_data["task"]["verificationSuggestions"] = _suggest(_rewritten)
                _vp, _vp_source = _vp_fmm(args.prompt)
                if _vp is not None:
                    task_data["task"]["verificationPolicy"] = _vp
                    task_data["task"]["verificationPolicySource"] = _vp_source
                _fmm = getattr(_preflight, "failure_mode_guidance_all", None)
                if _fmm:
                    _fmm_result = _fmm(args.prompt)
                    if _fmm_result:
                        task_data["task"]["failureModeGuidance"] = _fmm_result
                _mp = getattr(_preflight, "requires_mutation_plan", None)
                if _mp:
                    _mp_result = _mp(args.prompt)
                    if _mp_result:
                        task_data["task"]["requiresMutationPlan"] = True
                        task_data["task"]["mutationPlanReason"] = _mp_result["reason"]
                        task_data["task"]["mutationPlanKinds"] = _mp_result["kinds"]
                _ps = getattr(_preflight, "parallel_strategy_for_task", None)
                if _ps:
                    _ps_result = _ps(args.prompt)
                    if _ps_result.get("recommended"):
                        task_data["task"]["parallelStrategy"] = _ps_result
                _tp = getattr(_preflight, "thought_partner_assessment", None)
                if _tp:
                    _tp_result = _tp(args.prompt)
                    if _tp_result:
                        task_data["task"]["thoughtPartner"] = _tp_result
                _cg = getattr(_preflight, "compress_goal", None)
                if _cg:
                    _compressed = _cg(args.prompt)
                    task_data["task"]["goalConditionSize"] = len(_compressed)
                _pr = getattr(_preflight, "plan_review", None)
                if _pr:
                    _pr_result = _pr(args.prompt)
                    if _pr_result:
                        task_data["task"]["planReview"] = _pr_result
        except Exception:
            # Verification plan is advisory; never block dispatch on import/parse failure.
            pass
        write_json(state_dir / f"active-task_{run_id}.json", task_data)
        phase_marker(state_dir, "task-selected", run_id)
    elif args.plan:
        task = create_plan_task(args, state_dir, run_id)
        if task is None:
            return None
        write_json(state_dir / f"task-contract-{run_id}.json", task.raw)
        return task
    else:
        select_script = script_path("scripts", "select-task.py")
        if args.tasks:
            os.environ["GO_TASKS_FILE"] = str(Path(args.tasks).expanduser().resolve())
        else:
            os.environ.setdefault("GO_TASKS_FILE", str((Path.cwd() / ".claude" / "tasks" / "tasks.json").resolve()))
        rc = run_script(select_script, [], state_dir, run_id)
        if rc != 0:
            return None
        phase_marker(state_dir, "task-selected", run_id)
        task_file = state_dir / f"active-task_{run_id}.json"
        task_data = json.loads(task_file.read_text(encoding="utf-8"))

    task = TaskContract.from_active_task(task_data)
    write_json(state_dir / f"task-contract-{run_id}.json", task.raw)
    return task


def create_worktree(dispatch: str, state_dir: Path, run_id: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    prefix = "pi" if dispatch == "pi" else "ai"
    run_suffix_source = run_id[4:] if run_id.startswith("run-") else run_id
    suffix = "".join(ch for ch in run_suffix_source if ch.isalnum())[:8] or uuid.uuid4().hex[:8]
    root = Path("P:/worktrees")
    worktree = root / f"{prefix}-task-{ts}-{suffix}"
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "worktree", "add", "-b", f"{prefix}/{prefix}-task-{ts}-{suffix}", str(worktree), "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"git worktree add failed for {worktree}: {detail}")
    write_json(state_dir / f"worktree-{run_id}.json", {"worktree": str(worktree)})
    phase_marker(state_dir, "worktree-ready", run_id)
    return worktree


def classify_and_resolve_pi(state_dir: Path, run_id: str) -> PiModelInfo | None:
    classify_script = script_path("scripts", "classify_complexity.py")
    rc = run_script(classify_script, [], state_dir, run_id)
    if rc != 0:
        return None
    phase_marker(state_dir, "classified", run_id)

    resolve_script = script_path("scripts", "adapters", "pi", "resolve_model.py")
    rc = run_script(resolve_script, [], state_dir, run_id)
    if rc != 0:
        return None
    phase_marker(state_dir, "model-resolved", run_id)
    return PiModelInfo.load(state_dir / f"pi-model_{run_id}.json")


def task_prompt(task_file: Path) -> str:
    task_json = json.loads(task_file.read_text(encoding="utf-8")) if task_file.exists() else {}
    inner = task_json.get("task", task_json)
    parts = [f"Task: {inner.get('title', '')}", f"Objective: {inner.get('objective', '')}"]
    for criterion in inner.get("acceptance_criteria", []):
        parts.append(f"- Accept: {criterion}")
    for command in inner.get("verification_commands", []):
        parts.append(f"- Verify: {command}")
    for item in inner.get("scope_in", []):
        parts.append(f"- Scope: {item}")
    for item in inner.get("forbidden_files", []):
        parts.append(f"- DO NOT modify: {item}")
    # Phase 5.5: include the matrix-derived verification expectations so the worker
    # sees them before implementation. Advisory only — never blocks dispatch.
    vp = inner.get("verificationPolicy")
    vs = inner.get("verificationSuggestions")
    if vs:
        parts.append("")
        parts.append("---")
        parts.append("Verification expectations:")
        if vp:
            parts.append(f"  Policy: {vp}")
        for suggestion in vs:
            parts.append(f"  - {suggestion}")
        parts.append(
            "  Treat these as advisory. Prefer targeted tests over generic pytest. "
            "If not run, explicitly say not run. "
            'Do not claim "verified," "tests pass," "fixed," or "works" '
            "without command evidence."
        )
    # Phase 6: Failure Mode Matrix guidance — proactive failure anticipation.
    fmm = inner.get("failureModeGuidance")
    if fmm:
        parts.append("")
        parts.append("---")
        parts.append("Common failure modes for this task type:")
        for fm in fmm.get("failure_modes", []):
            parts.append(f"  - {fm}")
        if fmm.get("required_recon"):
            parts.append("Required recon before editing:")
            for item in fmm["required_recon"]:
                parts.append(f"  - {item}")
        if fmm.get("search_evidence"):
            parts.append("Search/read evidence required:")
            for item in fmm["search_evidence"]:
                parts.append(f"  - {item}")
        if fmm.get("negative_tests"):
            parts.append("Negative tests / behavior tests:")
            for item in fmm["negative_tests"]:
                parts.append(f"  - {item}")
        if fmm.get("claim_requirements"):
            parts.append("Completion claim requirements:")
            for item in fmm["claim_requirements"]:
                parts.append(f"  - {item}")
        # Secondary safeguard rows (multi-type prompts).
        for sec in fmm.get("secondary", []):
            parts.append("")
            parts.append("Additional safeguards (secondary task type):")
            for fm in sec.get("failure_modes", []):
                parts.append(f"  - {fm}")
            if sec.get("negative_tests"):
                parts.append("  Key tests:")
                for item in sec["negative_tests"]:
                    parts.append(f"    - {item}")
            if sec.get("claim_requirements"):
                parts.append("  Claim requirements:")
                for item in sec["claim_requirements"]:
                    parts.append(f"    - {item}")
    # Phase 6.7: Execution-control safeguards for multi-phase/multi-task prompts.
    _title_obj = f"{inner.get('title', '')} {inner.get('objective', '')}".lower()
    _has_phase_pattern = any(kw in _title_obj for kw in (
        "phase", "multi-phase", "multi-task", "stages", "steps",
        "quarantine", "migration", "delegat",
    ))
    if _has_phase_pattern:
        parts.append("")
        parts.append("---")
        parts.append("Execution-control safeguards (multi-phase task):")
        parts.append("  Delegation: executors may not write to shared tree unless")
        parts.append("    isolated worktree, patch bundle, or disjoint-file lock plan exists.")
        parts.append("  Mutation preconditions: before any file change, produce:")
        parts.append("    permitted files, proposed changes, verification contract, rollback command.")
        parts.append("  Authoritative run: if run-once-defines-result, save full output to file.")
        parts.append("    If truncated/missing, mark phase FAILED or restart once. Do not reclassify.")
        parts.append("  Report contract: if user requested strict format, final output must match.")
        parts.append("  Live hook path: Stop hook JSON validation failure = task not complete.")
    # Phase 6.9: Hook-work contract — only when the task touches hook wiring.
    _has_hook_pattern = any(kw in _title_obj for kw in (
        "hook", "settings.json", "hooks.json", "router", "dispatch",
        "stop hook", "pretooluse", "posttooluse",
    ))
    if _has_hook_pattern:
        parts.append("")
        parts.append("---")
        parts.append("Hook-work contract (this task touches hook wiring):")
        parts.append("  1. Discover the dispatch surface BEFORE wiring: read settings.json,")
        parts.append("     settings.local.json, plugin hooks.json, and __lib/router.py.")
        parts.append("     State which surface is live. Do not create a third pattern.")
        parts.append("  2. Stop output contract: block -> print")
        parts.append('     {"decision":"block","reason":"continue: ..."};')
        parts.append("     allow/done/fail-open -> print NOTHING.")
        parts.append('     Never print {}, {"decision":"approve"}, or other allow payloads.')
        parts.append("  3. Never claim 'registered', 'live', or 'verified' without evidence:")
        parts.append("     cite the registration file:line and show real-command smoke output.")
        parts.append("     Tests-passing is not liveness.")
        parts.append("  4. Tests must cover three layers: unit logic, direct invocation,")
        parts.append("     and real registered-dispatch-path smoke.")
        parts.append("  5. Plugin file changes trigger the mutation checklist where applicable:")
        parts.append("     version bump + cache rebuild + scope check before 'done'.")
    # Phase 6.10: Continuation policy — warn against pairing native /goal with
    # state-expressible /go task-completion work.
    _has_completion_pattern = any(kw in _title_obj for kw in (
        "completion", "task-completion", "run to completion", "until done",
        "block stopping", "goal loop", "continuation", "pr_ready", "all tasks complete",
    ))
    if _has_completion_pattern:
        parts.append("")
        parts.append("---")
        parts.append("Continuation policy (state-expressible /go goal):")
        parts.append("  This goal is state-expressible. The deterministic /go continuation")
        parts.append("  gate (scripts/go_continuation_gate.py, Stop[3]) decides completion from")
        parts.append("  /go state (phase markers, .pr_ready, .blocked) — not an LLM judgment.")
        parts.append("  Do NOT pair native /goal with this work: it re-enables the brittle")
        parts.append("  native goal-loop evaluator for no benefit.")
        parts.append("  Use the deterministic gate for task-completion goals.")
        parts.append("  Reserve tier-2 review/critic subagents for FUZZY quality goals")
        parts.append("  the gate cannot express (subjective correctness, design quality).")
    # Phase 6.8: Mutation-plan requirement (explicit field, not inferred).
    if inner.get("requiresMutationPlan"):
        parts.append("")
        parts.append("---")
        parts.append("MUTATION PLAN REQUIRED:")
        parts.append(f"  Reason: {inner.get('mutationPlanReason', 'quarantine/move/delete task')}")
        parts.append(f"  Kinds: {', '.join(inner.get('mutationPlanKinds', []))}")
        parts.append("  BEFORE any file move/delete/quarantine operation, create")
        parts.append("    mutation-plan_{phase_id}.json in the state directory with:")
        parts.append("      phase_id, operation_type, authoritative_source_output,")
        parts.append("      exempt_filter_result, proposed_move_list (or proposed_delete_list),")
        parts.append("      permitted_fence, rollback_command, verification_commands.")
        parts.append("  Use ONLY the authoritative source output for classification.")
        parts.append("  Do NOT classify from truncated output.")
        parts.append("  Do NOT mutate files outside the permitted fence.")
        parts.append("  Rollback if verification or fence checks fail.")
        parts.append("  If DONE is claimed but no valid mutation-plan exists, the phase is NOT complete.")
    # Phase 7: Thought-partner assessment.
    tp = inner.get("thoughtPartner")
    if tp:
        parts.append("")
        parts.append("---")
        parts.append("Thought partner assessment:")
        parts.append(f"  Real goal: {tp.get('taskIntent', 'unknown')[:200]}")
        if tp.get("impliedRequirements"):
            parts.append("  Implied requirements:")
            for item in tp["impliedRequirements"]:
                parts.append(f"    - {item}")
        if tp.get("missingImprovements"):
            parts.append("  Missing high-ROI improvements:")
            for item in tp["missingImprovements"]:
                parts.append(f"    - {item}")
        if tp.get("unsafeAssumptions"):
            parts.append("  Unsafe assumptions:")
            for item in tp["unsafeAssumptions"]:
                parts.append(f"    - {item}")
        if tp.get("missingVerification"):
            parts.append("  Missing verification:")
            for item in tp["missingVerification"]:
                parts.append(f"    - {item}")
    # Phase 8: Plan review advisory.
    pr = inner.get("planReview")
    if pr and pr.get("planProvided"):
        parts.append("")
        parts.append("---")
        parts.append("Plan improvements:")
        parts.append("  Before executing the supplied plan, account for these findings:")
        for item in pr.get("planImprovements", []):
            parts.append(f"    - {item}")
        if pr.get("sharedFileConflicts"):
            parts.append("  Shared-file conflicts:")
            for item in pr["sharedFileConflicts"]:
                parts.append(f"    - {item}")
        if pr.get("missingTests"):
            parts.append("  Missing tests:")
            for item in pr["missingTests"]:
                parts.append(f"    - {item}")
        if pr.get("missingRollback"):
            parts.append("  Missing rollback:")
            for item in pr["missingRollback"]:
                parts.append(f"    - {item}")
        if pr.get("nonBlockingWork"):
            parts.append("  Non-blocking parallel work:")
            for item in pr["nonBlockingWork"]:
                parts.append(f"    - {item}")
    # Phase 9: Parallel strategy advisory.
    ps = inner.get("parallelStrategy")
    if ps and ps.get("recommended"):
        parts.append("")
        parts.append("---")
        parts.append("Safe parallelism:")
        parts.append("  Use non-mutating parallel agents by default for the lanes below if available.")
        parts.append("  Do not let parallel agents mutate the shared tree.")
        parts.append("  Parent owns final patch and verification.")
        parts.append("")
        parts.append(f"  Mode: {ps.get('mode', 'analysis-parallel-mutation-serialized')}")
        parts.append(f"  Mutation policy: {ps.get('mutationPolicy', 'serialized')}")
        parts.append(f"  Overhead risk: {ps.get('overheadRisk', 'low')}")
        parts.append("")
        parts.append("  Lanes:")
        for lane in ps.get("lanes", []):
            parts.append(f"    {lane['name']}: {lane['purpose']} -> {lane['output']}")
    return "\n".join(parts)


def dispatch_pi(worktree: Path, state_dir: Path, run_id: str, pi_info: PiModelInfo) -> bool:
    task_file = state_dir / f"active-task_{run_id}.json"
    harness = load_script_module(
        "go_pi_harness_runtime",
        script_path("scripts", "adapters", "pi", "harness.py"),
    )
    result = harness.run_pi_harness(
        worktree=worktree,
        state_dir=state_dir,
        run_id=run_id,
        pi_model=pi_info.pi_model,
        prompt=task_prompt(task_file),
    )
    if result.exit_code != 0:
        return False
    phase_marker(state_dir, "dispatched", run_id)

    review_script = script_path("scripts", "adapters", "pi", "review_transcript.py")
    rc = run_script(review_script, [], state_dir, run_id)
    if rc != 0:
        return False
    phase_marker(state_dir, "transcript-reviewed", run_id)

    verdict_file = state_dir / f"pi-review_{run_id}.json"
    critical: list[str] = []
    if verdict_file.exists():
        review_data = json.loads(verdict_file.read_text(encoding="utf-8"))
        warnings = review_data.get("warnings", [])
        critical = [w for w in warnings if w.startswith(("BLIND_WRITE", "FORBIDDEN_FILE", "NO_FILES_WRITTEN"))]
    if critical:
        return False
    phase_marker(state_dir, "transcript-verdict", run_id)
    phase_marker(state_dir, "coded", run_id)
    return True


def dispatch_claude(state_dir: Path, run_id: str) -> bool:
    write_json(
        state_dir / f"dispatch-result_{run_id}.json",
        {
            "dispatch": "claude",
            "status": "unsupported-automated-dispatch",
            "reason": "Claude dispatch has no non-interactive worker implementation in this orchestrator.",
        },
    )
    touch(state_dir / f".blocked_{run_id}")
    return False


def dispatch_local(state_dir: Path, run_id: str) -> bool:
    # Check for local LLM dispatch path
    local_llm = os.environ.get("GO_LOCAL_LLM", "").strip()
    if local_llm:
        # Dispatch to local LLM (LM Studio, Ollama, vLLM)
        dispatch_script = script_path("scripts", "adapters", "local", "dispatch_local.py")
        rc = run_script(dispatch_script, [], state_dir, run_id, cwd=Path.cwd())
        if rc != 0:
            write_json(
                state_dir / f"dispatch-result_{run_id}.json",
                {
                    "dispatch": "local",
                    "status": "failed",
                    "reason": f"Local LLM dispatch failed: {local_llm}",
                },
            )
            return False
        phase_marker(state_dir, "worktree-ready", run_id)
        phase_marker(state_dir, "dispatched", run_id)
        phase_marker(state_dir, "coded", run_id)
        return True

    # Default: skipped worker (verify current checkout)
    write_json(
        state_dir / f"dispatch-result_{run_id}.json",
        {
            "dispatch": "local",
            "status": "skipped-worker",
            "reason": "Local dispatch performs no worker step and runs verification against the current checkout.",
        },
    )
    phase_marker(state_dir, "worktree-ready", run_id)
    phase_marker(state_dir, "dispatched", run_id)
    phase_marker(state_dir, "coded", run_id)
    return True


def run_simplify_gate(worktree: Path, state_dir: Path, run_id: str, diff_stat: str) -> bool:
    status_path = state_dir / f"simplify-status_{run_id}.md"
    simplify_command = os.environ.get("GO_SIMPLIFY_COMMAND", "").strip()
    if not simplify_command:
        status_path.write_text(
            "\n".join(
                [
                    "# Simplify Gate",
                    "",
                    "Status: SKIPPED",
                    "Reason: GO_SIMPLIFY_COMMAND is not set.",
                    "",
                    "Diff stat:",
                    "```",
                    diff_stat.rstrip(),
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return True

    result = subprocess.run(
        simplify_command,
        cwd=worktree,
        shell=True,
        capture_output=True,
        text=True,
    )
    status_path.write_text(
        "\n".join(
            [
                "# Simplify Gate",
                "",
                f"Status: {'PASS' if result.returncode == 0 else 'FAIL'}",
                f"Command: {simplify_command}",
                f"Exit code: {result.returncode}",
                "",
                "Stdout:",
                "```",
                (result.stdout or "").rstrip(),
                "```",
                "",
                "Stderr:",
                "```",
                (result.stderr or "").rstrip(),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if result.returncode != 0:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "simplify",
                "reason_code": "simplify_command_failed",
                "command": simplify_command,
                "exit_code": result.returncode,
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return False
    return True


def run_common_tail(worktree: Path, state_dir: Path, run_id: str) -> bool:
    # Step 1: Run verification (verify-task.py)
    verify_script = script_path("scripts", "verify-task.py")
    rc = run_script(verify_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "verified", run_id)

    # Step 2: Get diff for simplify gate
    diff = subprocess.run(
        ["git", "diff", "--stat", "--stat-width", "200"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    if diff.returncode != 0:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "diff",
                "reason_code": "git_diff_failed",
                "stderr": (diff.stderr or diff.stdout or "").strip(),
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return False

    # Step 3: Run simplify gate (if there are changes)
    if diff.stdout and not any(diff.stdout.startswith(prefix) for prefix in ["0 files", "no changes", "???"]):
        if not run_simplify_gate(worktree, state_dir, run_id, diff.stdout):
            return False
    phase_marker(state_dir, "simplified", run_id)

    # Step 4: Run refactor review (between simplify and regressions)
    refactor_script = script_path("scripts", "refactor-review.py")
    rc = run_script(refactor_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "refactor-reviewed", run_id)

    # Step 5: Run regression tests (before verify-task)
    regression_script = script_path("scripts", "regression-runner.py")
    rc = run_script(regression_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "regression-passed", run_id)

    # Step 6: Run code reviews
    review_script = script_path("scripts", "review-passes.py")
    rc = run_script(review_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "reviews-passed", run_id)

    # Step 7: Run QA verification
    qa_script = script_path("scripts", "run-qa-verification.py")
    qa_args = ["--dry-run"] if os.environ.get("GO_QA_DRY_RUN", "").strip() == "1" else []
    rc = run_script(qa_script, qa_args, state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "qa-passed", run_id)

    # Step 8: Run mutation gate
    mutation_script = script_path("scripts", "mutation-gate.py")
    rc = run_script(mutation_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "mutation-passed", run_id)

    # Step 9: Run coverage gate (before pr-artifacts)
    coverage_script = script_path("scripts", "coverage-gate.py")
    rc = run_script(coverage_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "coverage-passed", run_id)

    # Step 10: Generate PR artifacts
    pr_script = script_path("scripts", "pr-artifacts.py")
    rc = run_script(pr_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    touch(state_dir / f".pr-ready_{run_id}")
    phase_marker(state_dir, "pr-ready", run_id)

    # Step 11: Run loop check (non-blocking)
    loop_script = script_path("scripts", "loop-check.py")
    run_script(loop_script, [], state_dir, run_id, cwd=worktree)
    return True


def orchestrate(args: argparse.Namespace) -> str:
    state_dir, run_id = ensure_runtime_env(args.dispatch)
    write_current_run(state_dir, run_id, "running", args.dispatch)

    def finish(status: str) -> str:
        write_current_run(state_dir, run_id, status, args.dispatch)
        if status == "pr_ready":
            return "<promise>PR_READY</promise>"
        return "<promise>BLOCKED</promise>"

    # Preflight-only: generate a proposal artifact and exit BEFORE load_or_create_task
    # so active-task-<runid>.json is never written. No dispatch / common-tail.
    if getattr(args, "preflight_only", False):
        return _orchestrate_preflight(args, state_dir, run_id)

    task = load_or_create_task(args, state_dir, run_id)
    if task is None:
        return finish("blocked")

    if args.dispatch == "local":
        inject_route_decision(state_dir, run_id, "local")
        if not dispatch_local(state_dir, run_id):
            return finish("blocked")
        if not run_common_tail(Path.cwd(), state_dir, run_id):
            return finish("blocked")
        return finish("pr_ready")

    if args.dispatch == "claude":
        inject_route_decision(state_dir, run_id, "claude")
        if not dispatch_claude(state_dir, run_id):
            return finish("blocked")

    try:
        worktree = create_worktree(args.dispatch, state_dir, run_id)
    except RuntimeError as exc:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {"phase": "worktree", "error": str(exc), "dispatch": args.dispatch},
        )
        touch(state_dir / f".blocked_{run_id}")
        return finish("blocked")
    if args.dispatch == "pi":
        pi_info = classify_and_resolve_pi(state_dir, run_id)
        inject_route_decision(state_dir, run_id, "pi", pi_info)
        if pi_info is None or not dispatch_pi(worktree, state_dir, run_id, pi_info):
            return finish("blocked")

    if not run_common_tail(worktree, state_dir, run_id):
        return finish("blocked")
    return finish("pr_ready")


_PREFLIGHT_FAIL_RC = 2
# Module-level exit-code carrier, set by _orchestrate_preflight, read by main().
# Kept separate from any function name to avoid the int-overwrites-function pitfall.
_preflight_exit_code: int = 0


def _orchestrate_preflight(args: argparse.Namespace, state_dir: Path, run_id: str) -> str:
    """Generate proposal artifact only. Never dispatch / verify / write active-task.

    Returns a one-line summary. If --preflight-only is used without --prompt,
    writes a small blocked sentinel and sets the module-level exit code to 2.
    """
    global _preflight_exit_code
    if not getattr(args, "prompt", None):
        write_json(
            state_dir / f"blocked_preflight_{run_id}.json",
            {
                "phase": "preflight",
                "reason_code": "missing_prompt",
                "message": "--preflight-only requires --prompt.",
            },
        )
        touch(state_dir / f".preflight-failed_{run_id}")
        write_current_run(state_dir, run_id, "preflight-failed", args.dispatch)
        _preflight_exit_code = _PREFLIGHT_FAIL_RC
        return f"preflight-only BLOCKED (run_id={run_id}): missing --prompt"
    artifact = _run_preflight(args, state_dir, run_id, _canonical_terminal_id())
    phase_marker(state_dir, "preflight-proposed", run_id)
    write_current_run(state_dir, run_id, "preflight-proposed", args.dispatch)
    _preflight_exit_code = 0
    return f"preflight OK (run_id={run_id}): wrote {artifact.name}"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    token = orchestrate(args)
    # Preflight returns a one-line summary string (not a promise token); print as-is.
    print(token)
    # Honor preflight failure exit code; default 0 keeps the existing contract.
    if getattr(args, "preflight_only", False):
        return _preflight_exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
