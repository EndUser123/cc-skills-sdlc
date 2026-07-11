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
import time
import uuid
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

VALID_DISPATCHES = ("pi", "claude", "local")
SKILL_DIR = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_DIR.parent.parent
ARTIFACTS_ROOT = Path(os.environ.get("GO_ARTIFACTS_ROOT", "P:/.claude/.artifacts"))

_TRANSCRIPT_PATH_FILE = Path.home() / "claude-log.transcript_path.txt"


def resolve_session_id() -> str:
    """Resolve the current Claude Code session ID from the transcript path.

    The UserPromptSubmit log_hook writes ~/claude-log.transcript_path.txt
    before any skill invocation. The filename is {session_uuid}.jsonl.
    This is more reliable than CLAUDE_SESSION_ID env (empty in many
    subprocess contexts). Falls back to env if the file is missing/empty.
    """
    # Primary: extract UUID from transcript filename.
    try:
        tp = _TRANSCRIPT_PATH_FILE.read_text(encoding="utf-8").strip()
        if tp:
            uuid = Path(tp).stem  # d6b4c348-2978-4347-8335-fefa15365fd8
            if uuid and len(uuid) >= 36 and "-" in uuid:
                return uuid
    except (OSError, ValueError):
        pass
    # Fallback: env (often empty in subprocesses, but harmless to try).
    return os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_AGENT_SESSION_ID") or ""


sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_context import resolve as _resolve_run_context, canonical_terminal_id as _canonical_terminal_id  # noqa: E402
from preflight_propose import run_preflight as _run_preflight  # noqa: E402
from preflight_propose import apply_discovery_evidence_merge as _apply_discovery_merge  # noqa: E402
from preflight_propose import emit_discovery_evidence_telemetry as _emit_discovery_telemetry  # noqa: E402
from preflight_propose import record_pi_outcome as _record_pi_outcome  # noqa: E402
from preflight_propose import record_failover_telemetry as _record_failover_telemetry  # noqa: E402


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

    # Determine model source. NOTE: dispatch=="local" is verification-only
    # (TASK-002 Option B) — no worker, no model. GO_LOCAL_LLM was dead code.
    override = os.environ.get("GO_MODEL_OVERRIDE", "").strip()
    if override:
        model_source = "GO_MODEL_OVERRIDE"
    elif dispatch == "pi" and pi_info is not None:
        model_source = "complexity-classifier"
    else:
        model_source = "unknown"

    # Rejected harnesses with reasons
    rejected: list[dict[str, str]] = []
    for harness, reason in [
        ("agy", "not-wired: agy is not integrated into /go dispatch"),
    ]:
        rejected.append({"harness": harness, "reason": reason})
    if dispatch != "local":
        # local mode is verification-only; if not selected, it simply wasn't chosen.
        rejected.append({"harness": "local", "reason": "not-selected"})
    if dispatch != "pi":
        rejected.append({"harness": "pi", "reason": "not-selected"})
    if dispatch != "claude":
        rejected.append({"harness": "claude", "reason": "not-selected"})

    pi_transcript_review = dispatch == "pi"

    chosen_model: str | None = None
    complexity_tier: str | None = None
    if dispatch == "pi" and pi_info is not None:
        chosen_model = pi_info.pi_model
        complexity_tier = pi_info.tier
    elif override:
        chosen_model = override
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
        # Filter to known dataclass fields — resolve_model.py writes additional
        # keys (candidate_chain, candidate_models) consumed elsewhere by
        # _resolve_chain_from_selection; PiModelInfo only carries the 3 it needs.
        known = {f.name for f in fields(cls)}
        return cls(**{k: data[k] for k in known if k in data})


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


def _task_has_capability_audit(state_dir: Path, run_id: str) -> bool:
    """Check if the active task has a capability_audit block."""
    import glob as glob_mod
    candidates = sorted(
        state_dir.glob(f"active-task_{run_id}*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ) or sorted(
        state_dir.glob("active-task_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return False
    try:
        task_data = json.loads(candidates[0].read_text(encoding="utf-8"))
        return bool(task_data.get("task", {}).get("capability_audit"))
    except Exception:
        return False


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



def write_session_pointer(state_dir: Path, run_id: str, session_id: str) -> None:
    """Write the session pointer that go_continuation_gate reads.

    Pointer: {artifacts}/go-sessions/{session_id}.json -> {go_state_dir, run_id, updated_at}
    Atomic write (tmp + replace). Overwritten on new run in the same session.
    The gate resolves session_id -> pointer -> state dir ONLY (no env, no mtime).
    """
    if not session_id:
        return  # cannot write a pointer without a session identity
    # Resolve at call time, not from the module global. Tests reach this fn
    # through 3 module identities (orchestrate / skills.go.scripts.orchestrate
    # / a _load_module alias), each with its own ARTIFACTS_ROOT bound at import;
    # only an env read sees the per-test monkeypatched root across all of them.
    artifacts_root = Path(os.environ.get("GO_ARTIFACTS_ROOT", str(ARTIFACTS_ROOT)))
    ptr_path = artifacts_root / 'go-sessions' / f'{session_id}.json'
    write_json(ptr_path, {
        'go_state_dir': str(state_dir.resolve()),
        'run_id': run_id,
        'updated_at': now_utc_z(),
    })



def phase_marker(state_dir: Path, phase: str, run_id: str) -> Path:
    p = state_dir / f".{phase}_{run_id}"
    touch(p)
    return p


def set_delegation_mode(state_dir: Path, mode: str, run_id: str) -> None:
    """Flip the active delegation mutation-authority mode for this run.

    worker = production phase (worker may mutate in scope); advisory = review
    phase (advisory roles read-only); off = neither. The PreToolUse gate reads
    these to enforce delegation_policy at the tool-call boundary.
    """
    worker_m = state_dir / f".delegation-worker_{run_id}"
    advisory_m = state_dir / f".delegation-advisory_{run_id}"
    if mode == "worker":
        advisory_m.unlink(missing_ok=True)
        touch(worker_m)
    elif mode == "advisory":
        worker_m.unlink(missing_ok=True)
        touch(advisory_m)
    elif mode == "off":
        worker_m.unlink(missing_ok=True)
        advisory_m.unlink(missing_ok=True)


# Claude native-subagent tier map. /go cannot call the in-session Agent tool
# itself (it runs as a Bash-invoked Python script), so dispatch_claude writes a
# request artifact and returns a SPAWN_CLAUDE_SUBAGENT token; SKILL.md spawns the
# Agent(...) call with these params, then resumes via --claude-resume.
# Advisory only — the PreToolUse delegation gate (TASK-001.4) enforces worker
# mutation scope regardless of the model chosen here.
_CLAUDE_TIER_MODELS: dict[str, str] = {
    "direct_answer": "haiku",
    "local_surgical": "sonnet",
    "local_rigorous": "sonnet",
    "full_go": "sonnet",
    "pause_for_authorization": "opus",
}

_CLAUDE_SUBAGENT_TYPE = "general-purpose"
_CLAUDE_SUBAGENT_TOOLS: list[str] = ["Read", "Grep", "Glob", "Edit", "Write", "Bash"]


def claude_tier_model(execution_tier: str, task_type: str = "") -> str:
    """Resolve the native-subagent model slug for a Claude-dispatch task.

    design tasks always pin to opus (advisory weight); otherwise the map
    follows the proposal's execution_tier. Unknown tiers default to sonnet.
    """
    if task_type == "design":
        return "opus"
    return _CLAUDE_TIER_MODELS.get(execution_tier, "sonnet")


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
    parser.add_argument(
        "--claude-resume",
        metavar="RUN_ID",
        default="",
        help="Phase 2 of Claude native-subagent dispatch: re-enter the orchestrator "
        "after SKILL.md has spawned the Agent and written claude-task-result_<run_id>.json. "
        "Runs the common tail (verify/review/artifacts) on the current checkout.",
    )
    parser.add_argument(
        "--completion-verify-resume",
        metavar="RUN_ID",
        default="",
        help="Phase 2 of the high-risk completion-verifier: re-enter after SKILL.md "
        "spawned the read-only verifier Agent and wrote completion-verify-result_<run_id>.json. "
        "Runs pr-artifacts + tail only (steps 1-9.6 already ran).",
    )
    parser.add_argument(
        "--falsification-resume",
        metavar="RUN_ID",
        default="",
        help="Phase 2 of the bounded falsification gate: re-enter after SKILL.md spawned "
        "the attacker Agent and wrote falsification-result_<run_id>.json. "
        "Validates request/result binding, applies verdict policy, cleans the disposable "
        "attack worktree, and resumes pr-artifacts only when permitted.",
    )
    parser.add_argument(
        "--validation",
        action="store_true",
        help="Mark this task as validation/audit type. G5 allows Stop when "
        "validation contract is satisfied (task_type=validation + .pr-ready "
        "or status=completed). Implementation tasks always require full SDLC gates.",
    )
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
        "session_id": resolve_session_id(),
        "selected_at": selected_at,
        "created_at": selected_at,
        "updated_at": selected_at,
        "state_version": 1,
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
    write_session_pointer(state_dir, run_id, task_data.get("session_id", ""))
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

def emit_gate_telemetry(event: str, session_id: str = "", decision: str = "silent",
                        reason: str = "", extra: dict | None = None) -> None:
    """Emit a continuation gate telemetry event. Fail-open (importable by the gate)."""
    try:
        from __lib.agentic_reliability_telemetry import log_event
        log_event(
            category="continuation_gate",
            event=event,
            gate="continuation_gate",
            session_id=session_id,
            decision=decision,
            extra={**(extra or {}), "reason": reason} if reason else (extra or {}),
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
        # SEC-2: scrub secrets from the prompt before any state write or worker
        # dispatch. scrub_prompt is pure + idempotent + fail-closed; an import
        # failure fails open (deployment issue, not a secret-leak path).
        try:
            prompt = importlib.import_module("scrub_prompt").scrub(args.prompt)
        except Exception:
            prompt = args.prompt
        # Recon-before-dispatch gate (Phase 1 of agentic-reliability ladder).
        # Blocks dispatch for high-risk prompts until a recon artifact exists.
        if not getattr(args, "preflight_only", False) and not getattr(args, "recon_only", False):
            try:
                require_recon(args, state_dir, run_id, prompt)
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
            "session_id": resolve_session_id(),
            "selected_at": selected_at,
            "created_at": selected_at,
            "updated_at": selected_at,
            "state_version": 1,
            "source": "cli",
            "source_ref": "cli",
            "task": {
                "id": f"prompt-{run_id[:8]}",
                "title": prompt[:60],
                "objective": prompt,
                "status": "selected",
                "priority": "P1",
                "scope_in": args.scope_in or [],
                "scope_out": [],
                "acceptance_criteria": [],
                "verification_commands": verification_commands,
                "forbidden_files": args.forbidden or [],
                "task_type": "validation" if getattr(args, "validation", False) else "implementation",
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
                _rewritten = _rewrite(prompt)
                _classify(_rewritten)
                task_data["task"]["verificationSuggestions"] = _suggest(_rewritten)
                _vp, _vp_source = _vp_fmm(prompt)
                if _vp is not None:
                    task_data["task"]["verificationPolicy"] = _vp
                    task_data["task"]["verificationPolicySource"] = _vp_source
                _fmm = getattr(_preflight, "failure_mode_guidance_all", None)
                if _fmm:
                    _fmm_result = _fmm(prompt)
                    if _fmm_result:
                        task_data["task"]["failureModeGuidance"] = _fmm_result
                _mp = getattr(_preflight, "requires_mutation_plan", None)
                if _mp:
                    _mp_result = _mp(prompt)
                    if _mp_result:
                        task_data["task"]["requiresMutationPlan"] = True
                        task_data["task"]["mutationPlanReason"] = _mp_result["reason"]
                        task_data["task"]["mutationPlanKinds"] = _mp_result["kinds"]
                _ps = getattr(_preflight, "parallel_strategy_for_task", None)
                if _ps:
                    _ps_result = _ps(prompt)
                    if _ps_result.get("recommended"):
                        task_data["task"]["parallelStrategy"] = _ps_result
                _tp = getattr(_preflight, "thought_partner_assessment", None)
                if _tp:
                    _tp_result = _tp(prompt)
                    if _tp_result:
                        task_data["task"]["thoughtPartner"] = _tp_result
                _cg = getattr(_preflight, "compress_goal", None)
                if _cg:
                    _compressed = _cg(prompt)
                    task_data["task"]["goalConditionSize"] = len(_compressed)
                _pr = getattr(_preflight, "plan_review", None)
                if _pr:
                    _pr_result = _pr(prompt)
                    if _pr_result:
                        task_data["task"]["planReview"] = _pr_result
        except Exception:
            # Verification plan is advisory; never block dispatch on import/parse failure.
            pass
        write_json(state_dir / f"active-task_{run_id}.json", task_data)
        write_session_pointer(state_dir, run_id, task_data.get("session_id", ""))
        phase_marker(state_dir, "task-selected", run_id)
    elif args.plan:
        task = create_plan_task(args, state_dir, run_id)
        if task is None:
            return None
        write_json(state_dir / f"task-contract-{run_id}.json", task.raw)
        return task
    else:
        # Bare-invocation plan-handoff resolver: when no --prompt/--plan/--tasks
        # was given and no GO_PLAN_FILE is set, try to bind to the freshest
        # implementation-ready plan that declares go_next_task. Falls through
        # to the queue on no-candidate (exit 3); pauses on ambiguity (exit 2).
        if not args.tasks and not os.environ.get("GO_PLAN_FILE"):
            resolver = script_path("scripts", "resolve_plan_handoff.py")
            rrc = run_script(resolver, [], state_dir, run_id)
            if rrc == 0:
                phase_marker(state_dir, "task-selected", run_id)
                task_file = state_dir / f"active-task_{run_id}.json"
                task_data = json.loads(task_file.read_text(encoding="utf-8"))
                task = TaskContract.from_active_task(task_data)
                write_json(state_dir / f"task-contract-{run_id}.json", task.raw)
                return task
            if rrc == 2:
                return None  # ambiguous — .paused_{run_id} written by resolver
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


def _nearest_git_root(path: Path) -> Path | None:
    """Nearest ancestor of ``path`` containing a ``.git`` entry (dir or file).

    For a path inside an embedded/submodule repo this returns THAT repo's
    root, not the parent's -- the basis for submodule-agnostic dispatch (#916).
    """
    p = path.resolve()
    if p.is_file():
        p = p.parent
    while True:
        if (p / ".git").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent


def resolve_target_repo(scope_in: list[str]) -> tuple[Path | None, str]:
    """Resolve the single git repo a task's ``scope_in`` paths live in (#916).

    Returns ``(repo_root, status)`` where status is:
      - ``"single"``     -- all resolvable paths share one repo root
      - ``"unknown"``    -- scope_in empty or no paths resolve (caller falls back to parent)
      - ``"cross-repo"`` -- paths span >1 repo; caller must reject

    Globs expand relative to CWD. Non-existent literal paths are skipped
    (a scope_in entry may name a file the worker will create).
    """
    import glob as glob_mod

    roots: set[Path] = set()
    for item in scope_in or []:
        spec = (item or "").strip()
        if not spec:
            continue
        matches = glob_mod.glob(spec) or ([spec] if Path(spec).exists() else [])
        for m in matches:
            root = _nearest_git_root(Path(m))
            if root is not None:
                roots.add(root)
    if not roots:
        return None, "unknown"
    if len(roots) > 1:
        return None, "cross-repo"
    return next(iter(roots)), "single"


def create_worktree(
    dispatch: str, state_dir: Path, run_id: str, target_repo: Path | None = None
) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    prefix = "pi" if dispatch == "pi" else "ai"
    run_suffix_source = run_id[4:] if run_id.startswith("run-") else run_id
    suffix = "".join(ch for ch in run_suffix_source if ch.isalnum())[:8] or uuid.uuid4().hex[:8]
    # Submodule-agnostic (#916): create the worktree in the target's real repo,
    # not always the parent. A parent-level worktree is empty for
    # gitlink-without-.gitmodules plugins, so the worker would land in a bare dir.
    repo = target_repo if target_repo is not None else Path.cwd()
    base = f"{prefix}-task-{ts}-{suffix}"
    if target_repo is not None:
        base = f"{base}-{(repo.name or 'repo').replace(' ', '-')}"
    root = Path(os.environ.get("GO_WORKTREE_ROOT", "P:/worktrees"))
    worktree = root / base
    branch = f"{prefix}/{prefix}-task-{ts}-{suffix}"
    root.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(worktree), "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"git worktree add failed for {worktree} (repo={repo}): {detail}"
        )
    write_json(
        state_dir / f"worktree-{run_id}.json",
        {"worktree": str(worktree), "target_repo": str(repo)},
    )
    phase_marker(state_dir, "worktree-ready", run_id)
    return worktree


def _check_parse_health(state_dir: Path, run_id: str,
                           scripts: list[Path]) -> bool:
    """Parse-health gate: ast.parse every script on the selected dispatch path.

    Catches the class of failure where a concurrent-session mid-write leaves a
    script syntactically broken (e.g. completion_evidence_review.py lost its
    def _assemble_verdict header) and the import cascade blocks the entire
    post-impl gate chain.  Writes parse-health_{run_id}.json; returns False if
    any script fails to parse.
    """
    import ast as _ast
    results: list[dict] = []
    all_ok = True
    for script in scripts:
        entry = {"path": str(script), "ok": True, "error": ""}
        try:
            _ast.parse(Path(script).read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
            all_ok = False
        results.append(entry)
    write_json(state_dir / (f"parse-health_{run_id}.json"),
               {"run_id": run_id, "scripts": results, "all_ok": all_ok})
    return all_ok


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
    # Phase 10: Discovery-evidence contract (always present, non-blocking).
    # Tells the worker exactly how to emit structural findings so the
    # apply_discovery_evidence_merge reader can act on them.
    _run_id_from_file = task_file.stem.split("_", 1)[-1] if task_file.name.startswith("active-task_") else ""
    _sd_env = os.environ.get("GO_STATE_DIR", "")
    parts.append("")
    parts.append("---")
    parts.append("Discovery-evidence contract (structural issue reporting):")
    parts.append("  If, while doing this task, you observe a structural issue in the")
    parts.append("  code (e.g. wrong layer ownership, duplicated responsibility, dead")
    parts.append("  producer/consumer, inert code, repeated patching, broad cross-file")
    parts.append("  change needed), you MUST report it so /go can decide whether to")
    parts.append("  recommend /refactor.")
    parts.append("")
    parts.append("  Report ONLY what you actually observed. Do not fabricate findings.")
    parts.append("  Verified findings MUST include a concrete evidence string")
    parts.append("  (file path, line number, grep output, or test result).")
    parts.append("  Inference/assumption findings need source + summary only.")
    parts.append("")
    parts.append("  To report a finding, either:")
    parts.append(f"    1. Write discovery-evidence_{_run_id_from_file}.json to the state_dir")
    parts.append(f"       ({_sd_env}) with: "
                 f'{{"findings": [{{"source": "...", "provenance": "verified|inference|assumption", '
                 f'"summary": "...", "evidence": "...", "structural_issues": ["..."]}}], '
                 f'"run_id": "{_run_id_from_file}"}}')
    parts.append("       Canonical structural_issues: dead_producer_consumer, inert_code,")
    parts.append("       duplicated_responsibility, wrong_layer_ownership, repeated_patching,")
    parts.append("       state_identity_lifecycle_ambiguity, broad_cross_file_change_needed,")
    parts.append("       excessive_test_setup_due_to_design_complexity.")
    parts.append("")
    parts.append("    2. Include a discovery_evidence field in your claude-task-result JSON:")
    parts.append("       {\"discovery_evidence\": {\"findings\": [...]}}")
    parts.append("")
    parts.append("  Absence is acceptable if no structural issue was observed during the task.")
    parts.append("  The telemetry in the common tail will record whether evidence was emitted.")
    return "\n".join(parts)





def _resolve_aliases_to_provider_model(aliases: list[str]) -> list[str]:
    """Map bare aliases to provider/model strings via the resolver used for normal chains.

    M3 is only included when GO_PI_ALLOW_M3_FALLBACK=1 (policy-gated). Bare aliases
    that the resolver does not know (or that resolve to None) are dropped. This
    prevents the historic "bare OPENCODE_DEEPSEEK" failure where pi fuzzy-matched
    it to the wrong provider.
    """
    import os as _os
    import importlib.util as _ilu
    _rm_path = Path(__file__).resolve().parent / "adapters" / "pi" / "resolve_model.py"
    _rm_spec = _ilu.spec_from_file_location("_fb_resolve_model", _rm_path)
    _rm = _ilu.module_from_spec(_rm_spec)
    _rm_spec.loader.exec_module(_rm)
    _allow_m3 = _rm._allow_m3_fallback()
    out: list[str] = []
    for alias in aliases:
        if alias == "M3" and not _allow_m3:
            continue  # policy: M3 is opt-in only
        resolved = _rm.resolve(alias)
        if resolved is None:
            continue  # unknown alias: do not emit bare name
        out.append(resolved)
    return out


def _resolve_chain_from_selection(state_dir, run_id) -> list:
    """Read candidate chain from pi-model JSON if present, else default.

    Run-local read; no cross-terminal aggregation. The candidate_chain is
    written by resolve_model.py into pi-model_{run_id}.json (not model-selection,
    which only carries tier/model/confidence/signals).
    """
    chain: list[str] = []
    try:
        pi_model_file = state_dir / f"pi-model_{run_id}.json"
        if pi_model_file.exists():
            data = json.loads(pi_model_file.read_text(encoding="utf-8"))
            chain = data.get("candidate_chain", []) or []
    except (OSError, ValueError):
        chain = []
    if not chain:
        # Fallback must use resolved provider/model strings (not bare aliases).
        # M3 is policy-gated via _allow_m3_fallback.
        chain = _resolve_aliases_to_provider_model(["OPENCODE_DEEPSEEK", "M3"])
        if not chain:
            # Last-resort: if even the resolver failed, use the documented
            # OPENCODE_DEEPSEEK provider/model so the worker can still attempt it.
            chain = ["opencode-go/deepseek-v4-flash"]
    return [c for c in chain if c]


def _read_run_scope(state_dir, run_id) -> tuple:
    """Read tier + task_class for telemetry scoping (run-local, best-effort)."""
    tier, task_class = "", ""
    try:
        sel = state_dir / f"model-selection_{run_id}.json"
        if sel.exists():
            sd = json.loads(sel.read_text(encoding="utf-8"))
            tier = sd.get("tier", "") or ""
        prop = state_dir / f"task-proposal_{run_id}.json"
        if prop.exists():
            pd = json.loads(prop.read_text(encoding="utf-8"))
            task_class = pd.get("task_type", "") or pd.get("task_intent", "") or ""
    except (OSError, ValueError):
        pass
    return tier, task_class


def _alias_reverse_map() -> dict:
    """resolved provider/model -> alias (e.g. 'llama-cpp/ornith-1.0-9b' -> 'LOCAL_ORNITH')."""
    try:
        rm_path = Path(__file__).resolve().parent / "adapters" / "pi" / "resolve_model.py"
        spec = importlib.util.spec_from_file_location("go_resolve_model_tel", rm_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {v: k for k, v in mod.MODEL_MAP.items()}
    except Exception:
        return {}


def _record_candidate_attempt(state_dir, run_id, tier, task_class,
                              candidate_chain, attempt_index, model_alias,
                              provider_model, started_at, latency_ms,
                              outcome, reject_reason, final_model_used,
                              fallback_used, validator_reason) -> dict:
    """Append one advisory per-candidate-attempt record (run_id-scoped).

    Advisory-only: not read by routing policy. Complements failover-telemetry
    (one summary per dispatch) with per-attempt granularity + timing, so
    future aggregate analysis can expand/contract local scope from real
    dispatch outcomes rather than model preference.
    Storage: state_dir/pi-candidate-attempts_{run_id}.jsonl (append-only).
    """
    ended_at = datetime.now(timezone.utc).isoformat()
    record = {
        "event": "pi_candidate_attempt",
        "ts": ended_at,
        "run_id": run_id,
        "state_dir": str(state_dir),
        "task_class": task_class,
        "tier": tier,
        "candidate_chain": candidate_chain,
        "attempt_index": attempt_index,
        "model_alias": model_alias,
        "provider_model": provider_model,
        "started_at": started_at,
        "ended_at": ended_at,
        "latency_ms": round(latency_ms, 1),
        "outcome": outcome,  # success|reject|error
        "reject_reason": reject_reason,
        "final_model_used": final_model_used,
        "fallback_used": fallback_used,
        "validator_reason": validator_reason,
    }
    try:
        tel_path = state_dir / f"pi-candidate-attempts_{run_id}.jsonl"
        with tel_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass
    return record


def _candidate_chain_failover(harness, worktree, state_dir, run_id, prompt,
                               candidate_chain, task_file) -> tuple:
    """Try each candidate in order; stop at first accepted attempt.

    Returns (result, final_model, failed_models). result may be None if all
    candidates raised exceptions. Acceptance rejects:
      - nonzero exit
      - thinking-only output (no final assistant text)
      - malformed/empty output

    Emits one advisory pi_candidate_attempt record per candidate tried
    (run_id-scoped, append-only) for future scope expand/contract analysis.
    """
    failed_models = []
    result = None
    tier, task_class = _read_run_scope(state_dir, run_id)
    alias_map = _alias_reverse_map()
    for idx, model in enumerate(candidate_chain):
        alias = alias_map.get(model, model)
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()
        try:
            result = harness.run_pi_harness(
                worktree=worktree, state_dir=state_dir, run_id=run_id,
                pi_model=model, prompt=prompt,
            )
        except Exception as exc:
            reason = f"exception: {exc}"
            failed_models.append({"model": model, "reason": reason})
            _record_candidate_attempt(
                state_dir, run_id, tier, task_class, candidate_chain, idx,
                alias, model, started_at, (time.monotonic() - t0) * 1000.0,
                "error", reason, "", idx > 0, "harness_exception")
            continue

        if result is None or result.exit_code != 0:
            reason = f"exit_code={getattr(result, 'exit_code', 'None')}"
            failed_models.append({"model": model, "reason": reason})
            _record_candidate_attempt(
                state_dir, run_id, tier, task_class, candidate_chain, idx,
                alias, model, started_at, (time.monotonic() - t0) * 1000.0,
                "error", reason, "", idx > 0, "nonzero_exit")
            continue

        # Acceptance: detect thinking-only or no-text output
        transcript_path = getattr(result, "transcript_path", None)
        output_text = ""
        if transcript_path and Path(str(transcript_path)).exists():
            try:
                output_text = Path(str(transcript_path)).read_text(encoding="utf-8")
            except OSError:
                pass

        has_text = False
        if output_text:
            for line in output_text.splitlines():
                try:
                    ev = json.loads(line.strip())
                    if ev.get("type") in ("message_update", "message"):
                        msg = ev.get("message", {})
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for c_item in content:
                                if c_item.get("type") == "text" and c_item.get("text", "").strip():
                                    has_text = True
                                    break
                except json.JSONDecodeError:
                    continue
                if has_text:
                    break

        if not has_text:
            failed_models.append({"model": model, "reason": "thinking_only_or_no_text"})
            _record_candidate_attempt(
                state_dir, run_id, tier, task_class, candidate_chain, idx,
                alias, model, started_at, (time.monotonic() - t0) * 1000.0,
                "reject", "thinking_only_or_no_text", "", idx > 0,
                "no_acceptable_text")
            continue

        # Success
        _record_candidate_attempt(
            state_dir, run_id, tier, task_class, candidate_chain, idx,
            alias, model, started_at, (time.monotonic() - t0) * 1000.0,
            "success", "", model, idx > 0, "accepted")
        return result, model, failed_models

    last_model = candidate_chain[-1] if candidate_chain else "unknown"
    return result, last_model, failed_models


def dispatch_pi(worktree: Path, state_dir: Path, run_id: str, pi_info: PiModelInfo) -> bool:
    task_file = state_dir / f"active-task_{run_id}.json"
    harness = load_script_module(
        "go_pi_harness_runtime",
        script_path("scripts", "adapters", "pi", "harness.py"),
    )
    prompt = task_prompt(task_file)

    # Resolve candidate chain from model-selection; default to OPENCODE_DEEPSEEK first.
    candidate_chain = _resolve_chain_from_selection(state_dir, run_id)
    if not candidate_chain:
        candidate_chain = [pi_info.pi_model]

    result, final_model, failed_models = _candidate_chain_failover(
        harness, worktree, state_dir, run_id, prompt, candidate_chain, task_file,
    )

    # Record failover telemetry (run-local, non-blocking).
    _record_failover_telemetry(
        state_dir, run_id,
        candidate_chain=candidate_chain,
        attempted_model=final_model,
        provider="",
        outcome="failed" if (result is None or getattr(result, "exit_code", -1) != 0) else "success",
        failure_reason="; ".join(f.get("reason", "") for f in failed_models),
        fallback_selected=candidate_chain[1] if len(candidate_chain) > 1 else "",
        final_model=final_model,
        final_status="failed" if (result is None or getattr(result, "exit_code", -1) != 0) else "success",
    )

    if result is None or getattr(result, "exit_code", -1) != 0:
        return False
    phase_marker(state_dir, "dispatched", run_id)
    set_delegation_mode(state_dir, "worker", run_id)

    review_script = script_path("scripts", "adapters", "pi", "review_transcript.py")
    rc = run_script(review_script, [], state_dir, run_id)
    if rc != 0:
        return False
    phase_marker(state_dir, "transcript-reviewed", run_id)
    set_delegation_mode(state_dir, "advisory", run_id)

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
    """Phase 1 of Claude native-subagent dispatch.

    Writes claude-task-request_{run_id}.json (tier-resolved model, scrubbed
    prompt, tools allowlist, scope), emits the dispatched + delegation-worker
    markers, and returns True. The caller then emits SPAWN_CLAUDE_SUBAGENT so
    SKILL.md can invoke the in-session Agent(...) tool — /go cannot call it
    from Python. Phase 2 (--claude-resume) runs the common tail after the
    subagent returns and SKILL.md writes claude-task-result_{run_id}.json.

    FM-2: any failure (opt-out, marker write, missing active-task) writes
    blocked_{run_id}.json BEFORE returning False.
    """
    if os.environ.get("GO_DISABLE_CLAUDE_TASK_SUBAGENT", "").strip():
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "reason_code": "claude_subagent_disabled",
                "run_id": run_id,
                "ts": now_utc_z(),
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return False

    task_file = state_dir / f"active-task_{run_id}.json"
    if not task_file.exists():
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "reason_code": "missing_active_task",
                "run_id": run_id,
                "ts": now_utc_z(),
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return False

    task_data = json.loads(task_file.read_text(encoding="utf-8"))
    task_inner = task_data.get("task", task_data)
    task_type = task_inner.get("task_type", "")

    execution_tier = ""
    proposal_file = state_dir / f"task-proposal_{run_id}.json"
    if proposal_file.exists():
        try:
            execution_tier = (
                json.loads(proposal_file.read_text(encoding="utf-8"))
                .get("execution_tier", "")
            )
        except (OSError, ValueError):
            execution_tier = ""

    model = claude_tier_model(execution_tier or "full_go", task_type)
    scope_in = task_inner.get("scope_in", [])
    forbidden = task_inner.get("forbidden_files", [])

    request = {
        "run_id": run_id,
        "ts": now_utc_z(),
        "model": model,
        "subagent_type": _CLAUDE_SUBAGENT_TYPE,
        "tools": list(_CLAUDE_SUBAGENT_TOOLS),
        "prompt": task_prompt(task_file),
        "scope_in": scope_in,
        "forbidden_files": forbidden,
        "execution_tier": execution_tier,
        "task_type": task_type,
    }
    try:
        write_json(state_dir / f"claude-task-request_{run_id}.json", request)
        write_json(
            state_dir / f"dispatch-result_{run_id}.json",
            {
                "dispatch": "claude",
                "status": "spawn-pending",
                "model": model,
                "reason": "Request artifact written; awaiting native-subagent spawn by main-loop Claude.",
            },
        )
        phase_marker(state_dir, "dispatched", run_id)
        set_delegation_mode(state_dir, "worker", run_id)
    except OSError as exc:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "reason_code": "request_write_failed",
                "run_id": run_id,
                "error": str(exc),
                "ts": now_utc_z(),
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return False
    return True


def run_local_verification(state_dir: Path, run_id: str) -> bool:
    # /go --dispatch local: no worker spawn. The user made the edit by hand;
    # /go runs its verification/review/artifact gates over the current checkout.
    # Renamed from dispatch_local (TASK-002 Option B): the function performs no
    # dispatch, so the old name was an active lie. The dead GO_LOCAL_LLM
    # local-LLM-adapter branch and adapters/local/ were removed with it.
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


def _pr_artifacts_and_tail(worktree: Path, state_dir: Path, run_id: str) -> bool:
    """Steps 10-13: PR artifacts + .pr-ready + loop/telemetry. Extracted so the
    completion-verifier resume path can run ONLY this tail."""
    pr_script = script_path("scripts", "pr-artifacts.py")
    rc = run_script(pr_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    touch(state_dir / f".pr-ready_{run_id}")
    phase_marker(state_dir, "pr-ready", run_id)
    loop_script = script_path("scripts", "loop-check.py")
    run_script(loop_script, [], state_dir, run_id, cwd=worktree)
    try:
        _emit_discovery_telemetry(state_dir, run_id)
    except Exception:
        pass
    try:
        _record_pi_outcome(state_dir, run_id, dispatch_route="",
                           review_verdict="", rescue_escalation_needed=False)
    except Exception:
        pass
    return True


def _completion_verify_request_payload(state_dir: Path, run_id: str) -> dict:
    """Build the read-only verifier request payload from run-scoped artifacts."""
    active = {}
    at_path = state_dir / f"active-task_{run_id}.json"
    if at_path.is_file():
        try:
            active = json.loads(at_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            active = {}
    task = active.get("task", active) if isinstance(active, dict) else {}
    cer_verdict = {}
    cer_path = state_dir / f"completion-evidence-review_{run_id}.json"
    if cer_path.is_file():
        try:
            cer_verdict = json.loads(cer_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cer_verdict = {}
    return {
        "schema": "completion-verify-request.v1",
        "run_id": run_id,
        "title": task.get("title", ""),
        "objective": task.get("objective", ""),
        "acceptance_criteria": task.get("acceptance_criteria", []),
        "scope_in": task.get("scope_in", []),
        "scope_out": task.get("scope_out", []),
        "constraints": {
            "forbidden_files": task.get("forbidden_files", []),
            "done_when": task.get("done_when", ""),
        },
        "worker_summary": task.get("summary", ""),
        "mechanical_review_verdict": cer_verdict.get("verdict"),
        "mechanical_review_evidence": cer_verdict.get("evidence", []),
        "calibration_mode": "advisory",
        "agent_contract": {
            "tools": ["Read", "Grep", "Glob", "Bash"],
            "read_only": True,
            "output_artifact": f"completion-verify-result_{run_id}.json",
            "output_schema": "completion-verifier.v1",
        },
    }


def _append_verify_ledger(state_dir: Path, run_id: str, entry: dict) -> None:
    """Append-only run-scoped verifier ledger (not a persistent pattern DB)."""
    try:
        log_path = state_dir / "completion-verify-ledger.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": now_utc_z(), "run_id": run_id, **entry}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        pass


def _apply_completion_verify_result(state_dir: Path, run_id: str) -> str:
    """Read completion-verify-result_{run_id}.json and apply advisory semantics.
    Returns: 'proceed' | 'advisory_revise' | 'fail'. ADVISORY_REVISE does NOT
    block .pr-ready; only infrastructure failure (missing/malformed) is hard."""
    res_path = state_dir / f"completion-verify-result_{run_id}.json"
    if not res_path.is_file():
        _append_verify_ledger(state_dir, run_id, {"phase": "resume", "outcome": "missing_result"})
        return "fail"
    try:
        data = json.loads(res_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _append_verify_ledger(state_dir, run_id, {"phase": "resume", "outcome": "malformed_result"})
        return "fail"
    verdict = str(data.get("verdict", "")).upper()
    _append_verify_ledger(state_dir, run_id, {
        "phase": "resume", "outcome": verdict,
        "omitted": data.get("omitted", []),
        "uncertain": data.get("uncertain", []),
    })
    if verdict == "PROCEED":
        return "proceed"
    # ADVISORY_REVISE + orphan/old non-PROCEED values are surfaced, not hard.
    if verdict == "ADVISORY_REVISE":
        try:
            (state_dir / f".completion-verify-advisory_{run_id}").write_text(
                json.dumps(data.get("omitted", [])), encoding="utf-8"
            )
        except OSError:
            pass
        return "advisory_revise"
    return "advisory_revise"


def _completion_verify_gate(worktree: Path, state_dir: Path, run_id: str) -> str:
    """Step 9.7 high-risk completion-verifier gate.
    Returns: 'skip' (low-risk or SKIP env), 'pause' (high-risk; writes
    request + pending marker; orchestrate emits SPAWN_COMPLETION_VERIFIER),
    'fail' (infrastructure error)."""
    if os.environ.get("GO_COMPLETION_VERIFY_SKIP", "").strip() == "1":
        return "skip"
    active = {}
    at_path = state_dir / f"active-task_{run_id}.json"
    if at_path.is_file():
        try:
            active = json.loads(at_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            active = {}
    task = active.get("task", active) if isinstance(active, dict) else {}
    try:
        from completion_evidence_review import task_should_trigger
    except ImportError:
        return "skip"
    triggered, _reason = task_should_trigger(task)
    if not triggered:
        phase_marker(state_dir, "completion-verify-skipped", run_id)
        return "skip"
    if (state_dir / f"completion-verify-result_{run_id}.json").is_file():
        _apply_completion_verify_result(state_dir, run_id)
        phase_marker(state_dir, "completion-verify-applied", run_id)
        return "skip"
    try:
        payload = _completion_verify_request_payload(state_dir, run_id)
        req_path = state_dir / f"completion-verify-request_{run_id}.json"
        req_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        touch(state_dir / f".completion-verify-pending_{run_id}")
        phase_marker(state_dir, "completion-verify-requested", run_id)
    except OSError:
        return "fail"
    return "pause"


def _falsification_gate(worktree: Path, state_dir: Path, run_id: str) -> str:
    """Step 9.8 bounded falsification gate (conditional; opt-out
    GO_FALSIFICATION_SKIP=1). For qualifying high-risk tasks, writes a
    run-scoped request, creates a disposable attack worktree, and emits
    SPAWN_FALSIFIER. SKILL.md spawns an attacker Agent in the attack worktree
    and re-invokes with --falsification-resume.

    Returns: 'skip' (low-risk or SKIP env or result already applied),
    'pause' (high-risk; writes request + pending marker), 'fail' (infra error).
    """
    if os.environ.get("GO_FALSIFICATION_SKIP", "").strip() == "1":
        return "skip"

    # Load task + changed files for routing.
    active = {}
    at_path = state_dir / f"active-task_{run_id}.json"
    if at_path.is_file():
        try:
            active = json.loads(at_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            active = {}
    task = active.get("task", active) if isinstance(active, dict) else {}

    # Get changed files from the worktree.
    try:
        diff_proc = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        changed_files = [l.strip() for l in diff_proc.stdout.splitlines() if l.strip()] if diff_proc.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        changed_files = []

    # Load proposal for risk classification.
    proposal = {}
    prop_path = state_dir / f"task-proposal_{run_id}.json"
    if prop_path.is_file():
        try:
            proposal = json.loads(prop_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            proposal = {}

    # Centralized routing decision.
    try:
        _scripts_dir = str(Path(__file__).resolve().parent)
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)
        import falsification_gate as _fg
    except ImportError:
        return "skip"

    required, routing_reasons = _fg.should_falsify(task, proposal, changed_files)

    # Write routing artifact for inspectability.
    write_json(
        state_dir / f"falsification-routing_{run_id}.json",
        {
            "run_id": run_id,
            "required": required,
            "reasons": routing_reasons,
            "ts": now_utc_z(),
        },
    )

    if not required:
        phase_marker(state_dir, "falsification-skipped", run_id)
        return "skip"

    # If a result already exists (resume path), apply it.
    result_path = state_dir / f"falsification-result_{run_id}.json"
    if result_path.is_file():
        phase_marker(state_dir, "falsification-applied", run_id)
        return "skip"

    # Build + write the request.
    try:
        _session_id = (active.get("session_id", "") if isinstance(active, dict) else "") or ""
        payload = _fg.build_falsification_request(
            state_dir, run_id, worktree, task, changed_files, proposal, routing_reasons,
            session_id=_session_id,
        )
    except Exception as exc:
        write_json(state_dir / f"blocked_{run_id}.json",
                   {"reason_code": "falsification_request_error", "error": str(exc)[:500]})
        touch(state_dir / f".blocked_{run_id}")
        return "fail"

    req_path = state_dir / f"falsification-request_{run_id}.json"
    req_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # Budget enforcement: attempt counter.
    attempt_file = state_dir / f".falsification-attempt_{run_id}"
    attempt_count = 0
    if attempt_file.exists():
        try:
            attempt_count = int(attempt_file.read_text(encoding="utf-8").strip() or "0")
        except (ValueError, OSError):
            attempt_count = 0
    max_attempts = payload.get("budget", {}).get("max_attempts", 1)
    if attempt_count >= max_attempts:
        write_json(state_dir / f"blocked_{run_id}.json",
                   {"reason_code": "falsification_max_attempts", "attempts": attempt_count})
        touch(state_dir / f".blocked_{run_id}")
        return "fail"

    # Budget enforcement: pending age (total_elapsed_seconds).
    pending_path = state_dir / f".falsification-pending_{run_id}"
    if pending_path.exists():
        import time as _time
        try:
            age = _time.time() - pending_path.stat().st_mtime
            max_elapsed = payload.get("budget", {}).get("total_elapsed_seconds", 300)
            if age > max_elapsed:
                write_json(state_dir / f"blocked_{run_id}.json",
                           {"reason_code": "falsification_timeout", "age_seconds": int(age)})
                touch(state_dir / f".blocked_{run_id}")
                return "fail"
        except OSError:
            pass

    # Create the disposable attack worktree (includes full state materialization).
    try:
        scope_in = task.get("scope_in", []) if isinstance(task, dict) else []
        attack_path, mat_report = _fg.create_attack_worktree(
            Path(payload["authoritative_worktree"]), run_id, payload["head_revision"], scope_in,
        )
        payload["materialization_report"] = mat_report
        # Record attack worktree path in the request for cleanup on resume.
        payload["attack_worktree"] = str(attack_path)
        # Capture materialization baseline: the hash of every changed file's
        # content at this exact moment, BEFORE the Agent mutates anything.
        # The resume path uses this baseline to measure attacker-writes as a
        # DELTA from materialized state, not from git HEAD.
        try:
            mat_baseline = _fg.capture_materialization_baseline(attack_path)
            payload["materialization_baseline"] = mat_baseline
        except Exception:
            payload["materialization_baseline"] = {}
        req_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        write_json(state_dir / f"blocked_{run_id}.json",
                   {"reason_code": "falsification_worktree_error", "error": str(exc)[:500]})
        touch(state_dir / f".blocked_{run_id}")
        return "fail"

    touch(state_dir / f".falsification-pending_{run_id}")
    phase_marker(state_dir, "falsification-requested", run_id)
    return "pause"


def _apply_falsification_result(state_dir: Path, run_id: str) -> str:
    """Read falsification-result_{run_id}.json, validate binding, apply verdict.

    Returns: 'proceed' | 'block' | 'fail'.
    Missing/malformed/mismatched results fail closed.
    """
    _scripts_dir = str(Path(__file__).resolve().parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    import falsification_gate as _fg

    req_path = state_dir / f"falsification-request_{run_id}.json"
    res_path = state_dir / f"falsification-result_{run_id}.json"

    if not res_path.is_file():
        return "fail"  # missing → fail closed

    # Budget enforcement: output-size cap (enforced before loading).
    output_size_limit = 5 * 1024 * 1024  # 5 MiB default
    if res_path.stat().st_size > output_size_limit:
        write_json(state_dir / f"blocked_{run_id}.json",
                   {"reason_code": "falsification_output_too_large", "size": res_path.stat().st_size})
        touch(state_dir / f".blocked_{run_id}")
        return "fail"

    try:
        request = json.loads(req_path.read_text(encoding="utf-8")) if req_path.is_file() else {}
        result = json.loads(res_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "fail"  # malformed → fail closed

    # Budget enforcement: attempt counter increment.
    attempt_file = state_dir / f".falsification-attempt_{run_id}"
    try:
        count = int(attempt_file.read_text(encoding="utf-8").strip() or "0") if attempt_file.exists() else 0
    except (ValueError, OSError):
        count = 0
    count += 1
    try:
        attempt_file.write_text(str(count), encoding="utf-8")
    except OSError:
        pass

    # Execution provenance (Part 1): load the run-scoped command ledger and
    # the declared attack worktree so FALSIFIED counterexamples must reference
    # real, bound command executions.
    attack_path_str = request.get("attack_worktree", "")
    ledger = _fg.load_ledger(state_dir, run_id)

    ok, reason = _fg.validate_falsification_result(
        result, request, run_id,
        ledger=ledger, attack_worktree=attack_path_str,
    )
    if not ok:
        write_json(state_dir / f"blocked_{run_id}.json",
                   {"reason_code": "falsification_result_rejected", "detail": reason})
        touch(state_dir / f".blocked_{run_id}")
        _terminalize_falsification_pointer(request, state_dir, run_id)
        return "fail"

    verdict = result.get("verdict", "")
    policy = _fg.apply_verdict_policy(verdict)

    # Part 2 budget enforcement: measure ATTACKER writes as a delta from the
    # post-materialization baseline (not from git HEAD). The legitimate
    # implementation diff consumed in materialization uses ZERO attacker budget.
    budget_violation = ""
    if attack_path_str:
        baseline = (request.get("materialization_baseline", {})
                    if isinstance(request, dict) else {})
        writes = _fg.measure_attacker_writes(Path(attack_path_str), baseline)
        budget = request.get("budget", {}) if isinstance(request, dict) else {}
        max_files = int(budget.get("max_files_writable", 50) or 0)
        max_bytes = int(budget.get("max_aggregate_bytes", 10 * 1024 * 1024) or 0)
        if max_files and writes.get("files_changed", 0) > max_files:
            budget_violation = "falsification_file_budget_exceeded"
        elif max_bytes and writes.get("bytes_written", 0) > max_bytes:
            budget_violation = "falsification_byte_budget_exceeded"

    # Clean up the attack worktree regardless of verdict.
    if attack_path_str:
        cleanup_report = _fg.cleanup_attack_worktree(Path(attack_path_str))
        # Verify authoritative worktree unchanged (HEAD + digests).
        auth_report = _fg.verify_authoritative_unchanged(
            Path(request["authoritative_worktree"]),
            request.get("head_revision", ""),
            request.get("staged_diff_digest", ""),
            request.get("unstaged_diff_digest", ""),
        )
        if not auth_report.get("ok", False):
            write_json(state_dir / f"blocked_{run_id}.json", {
                "reason_code": "falsification_authoritative_mutated",
                "authoritative_report": auth_report,
                "cleanup_report": cleanup_report,
            })
            touch(state_dir / f".blocked_{run_id}")
            _terminalize_falsification_pointer(request, state_dir, run_id)
            return "fail"

    if budget_violation:
        write_json(state_dir / f"blocked_{run_id}.json", {
            "reason_code": budget_violation,
            "verdict": verdict,
            "writes": writes,
        })
        touch(state_dir / f".blocked_{run_id}")
        _terminalize_falsification_pointer(request, state_dir, run_id)
        return "fail"

    phase_marker(state_dir, "falsification-resolved", run_id)

    if policy == "proceed":
        return "proceed"
    # block or advisory-block
    write_json(state_dir / f"blocked_{run_id}.json", {
        "reason_code": f"falsification_{verdict.lower()}",
        "verdict": verdict,
    })
    touch(state_dir / f".blocked_{run_id}")
    # Part 4: terminal outcomes (FALSIFIED + fail-closed verdicts) must not
    # leave the session pointer active for G4/G5 to loop on.
    _terminalize_falsification_pointer(request, state_dir, run_id)
    return "block"


def _terminalize_falsification_pointer(request: dict, state_dir: Path, run_id: str) -> None:
    """Remove the exact session pointer for this run iff it binds to this
    run_id + state_dir. Fail-silent; never touch foreign/newer pointers."""
    try:
        session_id = (request.get("session_id", "") if isinstance(request, dict) else "") or ""
        if not session_id:
            return
        import falsification_gate as _fg
        _fg.terminalize_session_pointer(session_id, run_id, str(state_dir))
    except Exception:
        pass


def run_common_tail(worktree: Path, state_dir: Path, run_id: str) -> bool:
    # Step 1: Run verification (verify-task.py)
    verify_script = script_path("scripts", "verify-task.py")
    rc = run_script(verify_script, [], state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "verified", run_id)

    # Step 1.5: Run capability-claim audit (if task has capability_audit)
    if _task_has_capability_audit(state_dir, run_id):
        audit_script = script_path("scripts", "capability_claim_audit.py")
        rc = run_script(audit_script, [str(state_dir), run_id], state_dir, run_id, cwd=worktree)
        if rc != 0:
            return False
        phase_marker(state_dir, "capability-audit-passed", run_id)

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

    # Step 9.5: Completion Evidence Review (post-implementation review gate).
    # The reviewer inspects the worker's completion report, the worktree git
    # diff, and existing evidence artifacts. It is read-only and runs in the
    # orchestrator's process (not the Stop hook), so it adds no logic to
    # Stop_enforce_gate.py. Triggers are documented in the reviewer's SKILL.md
    # section and in completion_evidence_review.py:task_should_trigger().
    review_script = script_path("scripts", "completion_evidence_review.py")
    review_args = ["--worktree", str(worktree), "--state-dir", str(state_dir), "--run-id", run_id]
    if os.environ.get("GO_COMPLETION_REVIEW_SKIP", "").strip() == "1":
        review_args.append("--skip-on-low-risk")
    rc = run_script(review_script, review_args, state_dir, run_id, cwd=worktree)
    if rc != 0:
        return False
    phase_marker(state_dir, "completion-reviewed", run_id)

    # Step 9.6: Final Omission Audit (read-only; reuses CER verdict schema).
    # Derives the completion-authority ladder (L0..L5), classifies the commit
    # boundary, audits the mechanism-change contract, and downgrades verdict
    # wording when a claim exceeds the derived authority. Opt out for low-risk
    # local edits with GO_OMISSION_AUDIT_SKIP=1. Adds no Stop/G4/G5 logic.
    if os.environ.get("GO_OMISSION_AUDIT_SKIP", "").strip() != "1":
        oa_script = script_path("scripts", "omission_audit.py")
        oa_args = ["--worktree", str(worktree), "--state-dir", str(state_dir), "--run-id", run_id]
        rc = run_script(oa_script, oa_args, state_dir, run_id, cwd=worktree)
        if rc != 0:
            return False
        phase_marker(state_dir, "omission-audited", run_id)

    # Step 9.7: High-risk completion-verifier gate (advisory-first; opt-out
    # GO_COMPLETION_VERIFY_SKIP=1). On pause, orchestrate emits
    # SPAWN_COMPLETION_VERIFIER; SKILL.md spawns a read-only verifier Agent and
    # re-invokes with --completion-verify-resume.
    cv = _completion_verify_gate(worktree, state_dir, run_id)
    if cv == "pause":
        return False
    if cv == "fail":
        return False

    # Step 9.8: Bounded falsification gate (conditional; opt-out
    # GO_FALSIFICATION_SKIP=1). For qualifying high-risk tasks, writes a
    # run-scoped request, creates a disposable attack worktree, emits
    # SPAWN_FALSIFIER; SKILL.md spawns an attacker Agent in the attack
    # worktree and re-invokes with --falsification-resume.
    fv = _falsification_gate(worktree, state_dir, run_id)
    if fv == "pause":
        return False
    if fv == "fail":
        return False

    return _pr_artifacts_and_tail(worktree, state_dir, run_id)


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

    # Completion-verifier phase 2: SKILL.md spawned the read-only verifier
    # Agent and wrote completion-verify-result_<run_id>.json. Apply advisory
    # semantics and run only the pr-artifacts tail (steps 1-9.6 already ran).
    if getattr(args, "completion_verify_resume", ""):
        resume_run_id = args.completion_verify_resume
        pending = state_dir / f".completion-verify-pending_{resume_run_id}"
        if pending.is_file():
            try:
                pending.unlink()
            except OSError:
                pass
        outcome = _apply_completion_verify_result(state_dir, resume_run_id)
        if outcome == "fail" and not (state_dir / f"completion-verify-result_{resume_run_id}.json").is_file():
            write_json(
                state_dir / f"blocked_{resume_run_id}.json",
                {"reason_code": "completion_verify_missing", "run_id": resume_run_id, "ts": now_utc_z()},
            )
            touch(state_dir / f".blocked_{resume_run_id}")
            return finish("blocked")
        phase_marker(state_dir, "completion-verify-resumed", resume_run_id)
        if not _pr_artifacts_and_tail(Path.cwd(), state_dir, resume_run_id):
            return finish("blocked")
        return finish("pr_ready")

    # Falsification phase 2: SKILL.md spawned the attacker Agent in the
    # disposable worktree and wrote falsification-result_<run_id>.json.
    # Validate binding, apply verdict policy, clean up, resume tail.
    if getattr(args, "falsification_resume", ""):
        resume_run_id = args.falsification_resume
        pending = state_dir / f".falsification-pending_{resume_run_id}"
        if pending.is_file():
            try:
                pending.unlink()
            except OSError:
                pass
        outcome = _apply_falsification_result(state_dir, resume_run_id)
        if outcome == "fail":
            return finish("blocked")
        if outcome == "block":
            return finish("blocked")
        phase_marker(state_dir, "falsification-resumed", resume_run_id)
        if not _pr_artifacts_and_tail(Path.cwd(), state_dir, resume_run_id):
            return finish("blocked")
        return finish("pr_ready")

    # Claude phase 2: SKILL.md spawned the Agent and wrote the result. Run the
    # common tail on the current checkout (no worktree — the subagent worked
    # in-place under the PreToolUse delegation gate).
    if getattr(args, "claude_resume", ""):
        resume_run_id = args.claude_resume
        result_file = state_dir / f"claude-task-result_{resume_run_id}.json"
        if not result_file.exists():
            write_json(
                state_dir / f"blocked_{resume_run_id}.json",
                {
                    "reason_code": "missing_claude_task_result",
                    "run_id": resume_run_id,
                    "ts": now_utc_z(),
                },
            )
            touch(state_dir / f".blocked_{resume_run_id}")
            return finish("blocked")
        phase_marker(state_dir, "coded", resume_run_id)
        set_delegation_mode(state_dir, "advisory", resume_run_id)
        _apply_discovery_merge(state_dir, resume_run_id)
        if not run_common_tail(Path.cwd(), state_dir, resume_run_id):
            if (state_dir / f".falsification-pending_{resume_run_id}").is_file():
                return "<promise>SPAWN_FALSIFIER</promise>"
            if (state_dir / f".completion-verify-pending_{resume_run_id}").is_file():
                return "<promise>SPAWN_COMPLETION_VERIFIER</promise>"
            return finish("blocked")
        return finish("pr_ready")

    task = load_or_create_task(args, state_dir, run_id)
    if task is None:
        return finish("blocked")

    if args.dispatch == "local":
        # No worker exists in local dispatch (verification/review/artifact gates only),
        # so discovery_evidence is never produced. _apply_discovery_merge is
        # intentionally not called here; it is wired in claude_resume (L1531) and
        # the pi path (below at the call site) where workers run.
        inject_route_decision(state_dir, run_id, "local")
        if not run_local_verification(state_dir, run_id):
            return finish("blocked")
        if not run_common_tail(Path.cwd(), state_dir, run_id):
            if (state_dir / f".falsification-pending_{run_id}").is_file():
                return "<promise>SPAWN_FALSIFIER</promise>"
            if (state_dir / f".completion-verify-pending_{run_id}").is_file():
                return "<promise>SPAWN_COMPLETION_VERIFIER</promise>"
            return finish("blocked")
        return finish("pr_ready")

    if args.dispatch == "claude":
        inject_route_decision(state_dir, run_id, "claude")
        if not dispatch_claude(state_dir, run_id):
            return finish("blocked")
        # Phase 1 complete: request artifact written. Hand off to SKILL.md,
        # which reads claude-task-request_{run_id}.json, spawns the in-session
        # Agent(...) call, writes claude-task-result_{run_id}.json, then
        # re-invokes with --claude-resume <run_id> for phase 2.
        return "<promise>SPAWN_CLAUDE_SUBAGENT</promise>"

    # Submodule-agnostic dispatch (#916): resolve the real repo the task targets.
    target_repo, repo_status = resolve_target_repo(task.scope_in)
    if repo_status == "cross-repo":
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {
                "phase": "scope",
                "error": "cross-repo task",
                "detail": "scope_in spans multiple git repos; /go dispatches one repo at a time. Split the task.",
                "scope_in": task.scope_in,
            },
        )
        touch(state_dir / f".blocked_{run_id}")
        return finish("blocked")

    try:
        worktree = create_worktree(args.dispatch, state_dir, run_id, target_repo)
    except RuntimeError as exc:
        write_json(
            state_dir / f"blocked_{run_id}.json",
            {"phase": "worktree", "error": str(exc), "dispatch": args.dispatch},
        )
        touch(state_dir / f".blocked_{run_id}")
        return finish("blocked")
    if args.dispatch == "pi":
        # Parse-health gate: verify all scripts on the PI dispatch path parse
        # before making any live/runtime claims. Catches concurrent-session
        # mid-write syntax errors that cascade through import dependencies.
        _ph_scripts = [
            script_path("scripts", "orchestrate.py"),
            script_path("scripts", "completion_evidence_review.py"),
            script_path("scripts", "omission_audit.py"),
            script_path("scripts", "adapters", "pi", "resolve_model.py"),
            script_path("scripts", "adapters", "pi", "harness.py"),
        ]
        if not _check_parse_health(state_dir, run_id, _ph_scripts):
            write_json(state_dir / (f"blocked_{run_id}.json"),
                       {"reason_code": "parse_health_failed",
                        "run_id": run_id, "ts": now_utc_z()})
            touch(state_dir / (f".blocked_{run_id}"))
            return finish("blocked")
        pi_info = classify_and_resolve_pi(state_dir, run_id)
        inject_route_decision(state_dir, run_id, "pi", pi_info)
        if pi_info is None or not dispatch_pi(worktree, state_dir, run_id, pi_info):
            return finish("blocked")
        _apply_discovery_merge(state_dir, run_id)

    if not run_common_tail(worktree, state_dir, run_id):
        if (state_dir / f".completion-verify-pending_{run_id}").is_file():
            return "<promise>SPAWN_COMPLETION_VERIFIER</promise>"
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
