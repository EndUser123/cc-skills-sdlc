#!/usr/bin/env python3
"""Bare-invocation plan-handoff resolver for /go.

When /go is invoked with no --prompt, --plan, or --tasks, this scans
~/.claude/plans for the freshest plan that is:
  - status: implementation-ready
  - unresolved_blockers: 0
  - matching <plan>.evidence-gate.json with verdict PASS and current plan hash
  - declares a go_next_task block (explicit next task)

Single candidate -> bind (write active-task_{run_id}.json, exit 0).
Multiple candidates -> pause (write .paused_{run_id}, exit 2).
No candidate -> fall through to queue/transcript (exit 3).

The go_next_task frontmatter block shape (controlled schema):
  go_next_task:
    task_id: TASK-001.1
    title: short title
    objective: one-sentence objective
    verification_commands: pytest -q   # optional, comma-delimited
    priority: P1                       # optional, default P1

Full task contract (acceptance criteria, scope) lives in the plan body;
the worker reads it via source_ref. This block carries only what is needed
to identify and start the next task.
"""
import datetime
import importlib.util
import json
import os
import pathlib
import re
import sys

PLANS_DIR = pathlib.Path(
    os.environ.get("GO_PLANS_DIR", str(pathlib.Path.home() / ".claude" / "plans"))
)
# Import-safe defaults; main() reads these fresh from os.environ at call time.
STATE_DIR = pathlib.Path(os.environ.get("GO_STATE_DIR", "."))
RUN_ID = os.environ.get("RUN_ID", "")
TERMINAL_ID = os.environ.get("TERMINAL_ID", "")
EVIDENCE_GATE_PATH = pathlib.Path(__file__).resolve().parents[2] / "planning" / "scripts" / "evidence_gate.py"


def _strip_quotes(v: str) -> str:
    """Strip one matching pair of surrounding quotes only (preserve embedded quotes)."""
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v


def _parse_frontmatter(text: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Split frontmatter into flat scalar keys and nested indented blocks.

    Ponytail: hand-rolled, no PyYAML dependency (matches planning skill style).
    Handles the controlled go_next_task schema; not a general YAML parser.
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, {}
    flat: dict[str, str] = {}
    nested: dict[str, dict[str, str]] = {}
    current_key: str | None = None
    for raw in m.group(1).splitlines():
        if not raw.strip():
            continue
        if raw[0].isspace() and current_key:
            line = raw.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                nested.setdefault(current_key, {})[k.strip()] = _strip_quotes(v.strip())
            continue
        if ":" in raw:
            k, v = raw.split(":", 1)
            k, v = k.strip(), v.strip()
            if v == "":
                current_key = k
            else:
                flat[k] = _strip_quotes(v)
                current_key = None
    return flat, nested


def _candidate_plans() -> list[tuple[pathlib.Path, dict[str, str], dict[str, str]]]:
    cands: list[tuple[pathlib.Path, dict[str, str], dict[str, str]]] = []
    for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        text = _read_verified_plan(p)
        if text is None:
            continue
        flat, nested = _parse_frontmatter(text)
        if flat.get("status") != "implementation-ready":
            continue
        if str(flat.get("unresolved_blockers", "0")).strip() != "0":
            continue
        gnt = nested.get("go_next_task") or {}
        if not gnt.get("task_id") or not gnt.get("objective"):
            continue
        cands.append((p, flat, gnt))
    return cands


def _read_verified_plan(plan_path: pathlib.Path) -> str | None:
    """Load a plan only when the canonical evidence gate verifies its bytes.

    The sidecar is intentionally bound to the exact plan bytes so a plan edit
    cannot retain a stale readiness verdict.
    """
    try:
        spec = importlib.util.spec_from_file_location("planning_evidence_gate", EVIDENCE_GATE_PATH)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.read_verified_plan(plan_path)
    except (OSError, ImportError, AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _build_task(gnt: dict[str, str]) -> dict:
    vc_raw = gnt.get("verification_commands", "")
    verification = [c.strip() for c in vc_raw.split(",") if c.strip()] or ["python -m pytest -q"]
    return {
        "id": gnt["task_id"],
        "title": gnt.get("title", gnt["task_id"]),
        "objective": gnt["objective"],
        "status": "selected",
        "priority": gnt.get("priority", "P1"),
        "scope_in": [],
        "scope_out": [],
        "acceptance_criteria": [],
        "verification_commands": verification,
        "forbidden_files": [],
        "task_type": "implementation",
    }


def main() -> int:
    # Read env fresh at call time (module-level defaults are import-safety only).
    global PLANS_DIR, STATE_DIR, RUN_ID, TERMINAL_ID
    PLANS_DIR = pathlib.Path(
        os.environ.get("GO_PLANS_DIR", str(PLANS_DIR))
    )
    STATE_DIR = pathlib.Path(os.environ["GO_STATE_DIR"])
    RUN_ID = os.environ["RUN_ID"]
    TERMINAL_ID = os.environ.get("TERMINAL_ID", TERMINAL_ID)
    cands = _candidate_plans()
    if not cands:
        print("plan-handoff: no implementation-ready plan with go_next_task found")
        return 3
    if len(cands) > 1:
        names = [
            {"path": str(p), "task_id": g["task_id"], "title": g.get("title", "")}
            for p, _, g in cands
        ]
        paused = STATE_DIR / f".paused_{RUN_ID}"
        paused.write_text(
            json.dumps(
                {"run_id": RUN_ID, "reason": "multiple_plan_candidates", "candidates": names},
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"plan-handoff: {len(cands)} implementation-ready plans declare go_next_task — disambiguate:")
        for n in names:
            print(f"  - {n['task_id']}: {n['path']}")
        return 2
    plan_path, flat, gnt = cands[0]
    selected_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "run_id": RUN_ID,
        "terminal_id": TERMINAL_ID,
        "session_id": "",
        "selected_at": selected_at,
        "created_at": selected_at,
        "updated_at": selected_at,
        "state_version": 1,
        "source": "plan-handoff",
        "source_ref": str(plan_path),
        "plan_binding": {
            "plan_path": str(plan_path),
            "plan_status": flat.get("status"),
            "unresolved_blockers": flat.get("unresolved_blockers", "0"),
            "selected_task_id": gnt["task_id"],
            "binding_reason": "freshest implementation-ready plan with explicit go_next_task",
        },
        "task": _build_task(gnt),
    }
    out = STATE_DIR / f"active-task_{RUN_ID}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(f"plan-handoff: bound {gnt['task_id']} ({gnt.get('title', '')}) from {plan_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
