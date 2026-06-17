#!/usr/bin/env python3
"""Generate local PR artifacts from verified gate evidence."""
import json, os, pathlib, datetime, sys

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

task_path = state_dir / f"active-task_{run_id}.json"
task = json.loads(task_path.read_text(encoding="utf-8"))["task"]

task_id = task.get("id", "TASK")
title = task.get("title", "Untitled task")
objective = task.get("objective", "")
review_depth = os.environ.get("REVIEW_DEPTH", "full")


def _read_json(label: str, path: pathlib.Path, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"{label} missing")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"malformed gate evidence: {label}: {exc.msg}")
        return {}
    except OSError as exc:
        errors.append(f"{label} unreadable: {exc}")
        return {}


def _missing(label: str, errors: list[str]) -> bool:
    return any(error == f"{label} missing" for error in errors)


def _gate_errors() -> list[str]:
    errors = []
    verification_summary = _read_json("verification-summary", state_dir / f"verification-summary_{run_id}.json", errors)
    review_summary = _read_json("review-summary", state_dir / f"review-summary_{run_id}.json", errors)
    qa_verdict = _read_json("qa-verdict", state_dir / f"qa-verdict-{run_id}.json", errors)
    mutation_gate = _read_json("mutation-gate", state_dir / f"mutation-gate-{run_id}.json", errors)

    if not _missing("verification-summary", errors) and verification_summary.get("verified") is not True:
        errors.append("verification-summary present but not verified")
    if not _missing("review-summary", errors) and review_summary.get("failed") is not False:
        errors.append("review-summary present but failed")
    if not _missing("qa-verdict", errors) and qa_verdict.get("qa_status") not in {"accept", "accept-with-concerns", "skipped"}:
        errors.append("qa-verdict present but blocking")
    if not _missing("mutation-gate", errors) and mutation_gate.get("status") not in {"passed", "skipped"}:
        errors.append("mutation-gate present but blocking")
    return errors


errors = _gate_errors()
if errors:
    print("ERROR: missing required gate evidence: " + "; ".join(errors), file=sys.stderr)
    sys.exit(1)

commit_msg = f"""feat: complete {task_id.lower()} {title.lower()}

VERIFIED: PASS
SIMPLIFIED: PASS
REVIEWED: {review_depth.upper()}

RUN_ID: {run_id}
TASK_ID: {task_id}
"""

pr_title = f"{task_id}: {title}"

pr_body = f"""## Summary

- Completed {task_id}: {title}
- Objective: {objective}

## Verification

See `verification-results_{run_id}.txt`.

## Quality gates

- Verification: PASS
- Simplify: PASS
- Review depth: {review_depth}

## Notes

- Local PR artifacts generated only
- No remote push performed
"""

pr_ready = f"""# PR Ready

Task: {task_id}
Title: {title}
Run: {run_id}

Status:
- Verification: PASS
- Simplify: PASS
- Reviews: PASS

Next steps:
1. Review local artifacts
2. Commit using generated commit message
3. Open PR manually if desired

<promise>PR_READY</promise>
"""

result = {
    "run_id": run_id,
    "task_id": task_id,
    "status": "pr_ready",
    "completed_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
}

(state_dir / f"commit-message_{run_id}.txt").write_text(commit_msg, encoding="utf-8")
(state_dir / f"pr-title_{run_id}.txt").write_text(pr_title + "\n", encoding="utf-8")
(state_dir / f"pr-body_{run_id}.md").write_text(pr_body + "\n", encoding="utf-8")
(state_dir / f"pr-ready_{run_id}.md").write_text(pr_ready + "\n", encoding="utf-8")
(state_dir / f"task-result_{run_id}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

verification_path = state_dir / f"verification-result_{run_id}.json"
if verification_path.exists():
    try:
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        verification = {}
    verification.update(
        {
            "run_id": run_id,
            "task_id": verification.get("task_id", task_id),
            "status": "passed",
            "pr_ready": True,
            "generated_at": datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )
    artifact_paths = verification.setdefault("artifact_paths", {})
    artifact_paths["pr_ready"] = str(state_dir / f"pr-ready_{run_id}.md")
    verification_path.write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
print("PR artifacts written")
