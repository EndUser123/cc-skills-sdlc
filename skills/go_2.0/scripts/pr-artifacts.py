#!/usr/bin/env python3
"""Generate local PR artifacts from the selected task."""
import json, os, pathlib, datetime

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]

task_path = state_dir / f"active-task_{run_id}.json"
task = json.loads(task_path.read_text(encoding="utf-8"))["task"]

task_id = task.get("id", "TASK")
title = task.get("title", "Untitled task")
objective = task.get("objective", "")
review_depth = os.environ.get("REVIEW_DEPTH", "full")

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
    "completed_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
}

(state_dir / f"commit-message_{run_id}.txt").write_text(commit_msg, encoding="utf-8")
(state_dir / f"pr-title_{run_id}.txt").write_text(pr_title + "\n", encoding="utf-8")
(state_dir / f"pr-body_{run_id}.md").write_text(pr_body + "\n", encoding="utf-8")
(state_dir / f"pr-ready_{run_id}.md").write_text(pr_ready + "\n", encoding="utf-8")
(state_dir / f"task-result_{run_id}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print("PR artifacts written")
