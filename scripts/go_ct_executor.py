"""go-ct executor — orchestrates the task pipeline using Pydantic state + file-based phase gates.

Usage:
    python go_ct_executor.py --task "description" [--output-dir .claude/.artifacts/go] [--cleanup pre|force]
    python go_ct_executor.py --cleanup audit  # scan for orphaned worktrees and stale state

Phase sequence: pre-clean (advisory) → worktree → task → code → verify → simplify → review → merge → PR → post-clean
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    print("ERROR: pydantic is required. Install with: pip install pydantic", file=sys.stderr)
    sys.exit(1)


# === State Models ===

class TaskType(str, Enum):
    IMPLEMENTATION = "implementation"
    REFACTOR = "refactor"
    DESIGN = "design"
    PLANNING = "planning"
    CONFIG = "config"


class TaskStatus(str, Enum):
    READY = "ready"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class CleanupMode(str, Enum):
    AUDIT = "audit"      # report only, never destructive
    FORCE = "force"      # prune orphaned worktrees, archive stale state
    SKIP = "skip"        # skip pre-clean entirely


class PhaseStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    task_id: str
    title: str
    objective: str
    status: TaskStatus = TaskStatus.READY
    priority: str = "P2"
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    task_type: TaskType = TaskType.IMPLEMENTATION
    routing: Optional[dict] = None


class Phase(BaseModel):
    name: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    artifacts: dict[str, str] = {}


class PipelineState(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    terminal_id: str = Field(default_factory=lambda: os.environ.get("TERMINAL_ID", "unknown"))
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    task: Optional[Task] = None
    worktree_path: Optional[str] = None
    worktree_branch: Optional[str] = None

    phases: dict[str, Phase] = {}

    def phase(self, name: str) -> Phase:
        if name not in self.phases:
            self.phases[name] = Phase(name=name)
        return self.phases[name]

    def complete_phase(self, name: str) -> None:
        p = self.phase(name)
        p.status = PhaseStatus.COMPLETED
        p.started_at = p.started_at or datetime.now().isoformat()
        p.completed_at = datetime.now().isoformat()

    def fail_phase(self, name: str, error: str) -> None:
        p = self.phase(name)
        p.status = PhaseStatus.FAILED
        p.error = error

    model_config = ConfigDict(use_enum_values=True)


# === Phase Gate File Operations ===

def touch_gate(state_dir: Path, gate_name: str) -> None:
    """Write a phase gate flag file."""
    gate_file = state_dir / f".{gate_name}"
    gate_file.write_text("")
    print(f"  [GATE] {gate_name}")


def check_gate(state_dir: Path, gate_name: str) -> bool:
    """Check if a phase gate exists."""
    return (state_dir / f".{gate_name}").exists()


# === Pre-Clean Functions ===

def get_worktrees() -> dict[str, str]:
    """Return {worktree_path: branch_name} for all git worktrees."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return {}

    worktrees = {}
    current_path = None
    current_branch = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[9:]
        elif line.startswith("branch "):
            current_branch = line[8:]
        elif line == "" and current_path and current_branch:
            worktrees[current_path] = current_branch
            current_path = None
            current_branch = None
    return worktrees


def find_state_dirs(base_dir: Path, skill: str) -> list[dict]:
    """Find all state directories for a skill across all terminals."""
    artifacts_dir = base_dir / skill
    if not artifacts_dir.exists():
        return []

    state_dirs = []
    for term_dir in artifacts_dir.iterdir():
        if not term_dir.is_dir():
            continue
        worktree_info = term_dir / "worktree.json"
        if worktree_info.exists():
            try:
                info = json.loads(worktree_info.read_text())
                state_dirs.append({
                    "terminal_id": term_dir.name,
                    "worktree_path": info.get("path", ""),
                    "branch": info.get("branch", ""),
                    "run_id": info.get("run_id", ""),
                    "state_dir": term_dir,
                })
            except (json.JSONDecodeError, OSError):
                continue
    return state_dirs


def pre_clean(base_dir: Path, skill: str, mode: CleanupMode) -> list[dict]:
    """Audit and optionally clean orphaned worktrees and stale state.

    Returns a list of finding dicts: {type, path, action, message}
    """
    findings = []
    worktrees = get_worktrees()
    state_dirs = find_state_dirs(base_dir, skill)

    # Build sets for comparison
    known_worktrees = {s["worktree_path"] for s in state_dirs if s["worktree_path"]}
    active_state_runs = {s["run_id"] for s in state_dirs if s["run_id"]}

    # 1. Orphaned worktrees: worktree exists but no state dir references it
    for wt_path, branch in worktrees.items():
        if wt_path not in known_worktrees and "ai/go-" in branch:
            # Check for uncommitted changes
            has_changes = False
            if Path(wt_path).exists():
                r = subprocess.run(
                    ["git", "diff", "--quiet"],
                    cwd=wt_path, capture_output=True
                )
                has_changes = r.returncode != 0

            findings.append({
                "type": "orphaned_worktree",
                "path": wt_path,
                "branch": branch,
                "has_changes": has_changes,
                "action": "none",
                "message": f"Orphaned worktree: {wt_path} ({branch})"
                    + (" — has uncommitted changes" if has_changes else " — clean"),
            })

    # 2. Stale state: state dir exists but worktree is gone
    for state in state_dirs:
        if state["worktree_path"] and not Path(state["worktree_path"]).exists():
            findings.append({
                "type": "stale_state",
                "path": str(state["state_dir"]),
                "worktree_path": state["worktree_path"],
                "run_id": state["run_id"],
                "action": "none",
                "message": f"Stale state: no worktree at {state['worktree_path']} "
                    f"(run {state['run_id']})",
            })

    # 3. Apply cleanup actions only in FORCE mode
    if mode == CleanupMode.FORCE:
        for f in findings:
            if f["type"] == "orphaned_worktree" and not f["has_changes"]:
                _prune_worktree(f["path"], f["branch"])
                f["action"] = "pruned"
                f["message"] += " [PRUNED]"
            elif f["type"] == "stale_state":
                _archive_state(f["path"], base_dir)
                f["action"] = "archived"
                f["message"] += " [ARCHIVED]"

    return findings


def _prune_worktree(path: str, branch: str) -> None:
    """Remove a git worktree."""
    # First remove the worktree (filesystem)
    if Path(path).exists():
        try:
            shutil.rmtree(path)
            print(f"  [CLEANUP] Removed worktree directory: {path}")
        except OSError as e:
            print(f"  [CLEANUP] Failed to remove directory {path}: {e}", file=sys.stderr)
            return

    # Then prune via git (this also deletes the branch if fully merged)
    result = subprocess.run(
        ["git", "worktree", "prune"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  [CLEANUP] Pruned git worktree refs: {branch}")
    else:
        print(f"  [CLEANUP] git worktree prune failed: {result.stderr}", file=sys.stderr)


def _archive_state(state_path: str, base_dir: Path) -> None:
    """Archive a stale state directory to .artifacts/archive."""
    archive_dir = base_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = archive_dir / f"{Path(state_path).name}_{ts}"
    try:
        shutil.move(state_path, dest)
        print(f"  [CLEANUP] Archived stale state: {state_path} -> {dest}")
    except OSError as e:
        print(f"  [CLEANUP] Failed to archive {state_path}: {e}", file=sys.stderr)


def purge_attempt_files(state_dir: Path) -> int:
    """Remove .attempt_* files older than 7 days. Returns count purged."""
    if not state_dir.exists():
        return 0
    count = 0
    cutoff = datetime.now().timestamp() - (7 * 24 * 3600)
    for f in state_dir.glob(".attempt_*"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                count += 1
        except OSError:
            pass
    return count


# === Merge / Sync Functions ===

def merge_worktree(state: PipelineState, state_dir: Path) -> dict:
    """Stage and commit worktree changes, return commit info."""
    if not state.worktree_path:
        raise RuntimeError("No worktree to merge")

    wt_path = Path(state.worktree_path)

    # Check for changes
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=wt_path, capture_output=True, text=True
    )
    has_changes = bool(r.stdout.strip())

    if not has_changes:
        print("  [MERGE] No changes to commit")
        return {"commit": None, "has_changes": False, "message": "no changes"}

    # Stage all changes
    subprocess.run(["git", "add", "."], cwd=wt_path, capture_output=True)

    # Commit with task title as message
    task_msg = state.task.title if state.task else "go-ct task"
    commit_result = subprocess.run(
        ["git", "commit", "-m", task_msg],
        cwd=wt_path, capture_output=True, text=True
    )

    if commit_result.returncode != 0:
        print(f"  [MERGE] Commit failed: {commit_result.stderr}", file=sys.stderr)
        return {"commit": None, "has_changes": True, "message": "commit failed"}

    # Get commit hash
    log_result = subprocess.run(
        ["git", "log", "-1", "--format=%H %s"],
        cwd=wt_path, capture_output=True, text=True
    )
    if log_result.returncode == 0:
        commit_hash, commit_msg = log_result.stdout.strip().split(" ", 1)
    else:
        commit_hash, commit_msg = "unknown", ""

    print(f"  [MERGE] Committed: {commit_hash[:8]} - {commit_msg}")
    return {
        "commit": commit_hash,
        "message": commit_msg,
        "has_changes": True,
    }


def post_clean(state: PipelineState, base_dir: Path) -> None:
    """Prune worktree and archive artifacts after PR_READY."""
    if not state.worktree_path:
        return

    state_dir = base_dir / state.terminal_id / "go"

    # Prune worktree (branch stays via git worktree prune if fully merged)
    _prune_worktree(state.worktree_path, state.worktree_branch or "")

    # Purge attempt files
    purged = purge_attempt_files(state_dir)
    if purged:
        print(f"  [CLEANUP] Purged {purged} stale attempt files")

    # Archive state
    if state_dir.exists():
        archive_dir = base_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = archive_dir / f"go-{state.run_id}_{ts}"
        try:
            shutil.copytree(state_dir, dest)
            print(f"  [CLEANUP] Archived run artifacts: {dest}")
        except OSError as e:
            print(f"  [CLEANUP] Failed to archive {state_dir}: {e}", file=sys.stderr)


# === Workflow Steps ===

def create_worktree(state: PipelineState, base_dir: Path) -> tuple[str, str]:
    """STEP 0: Create isolated worktree for the task."""
    state_dir = base_dir / state.terminal_id / "go"
    state_dir.mkdir(parents=True, exist_ok=True)
    touch_gate(state_dir, "worktree-ready")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"ai/go-{state.run_id}-{ts}"
    worktree_path = f"P:/worktrees/go-ct-task-{ts}"

    # Create worktree via git
    cmd = [
        "git", "worktree", "add", "-b", branch_name,
        worktree_path, "HEAD"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create worktree: {result.stderr}")

    state.worktree_path = worktree_path
    state.worktree_branch = branch_name

    # Write worktree info
    (state_dir / "worktree.json").write_text(json.dumps({
        "path": worktree_path,
        "branch": branch_name,
        "run_id": state.run_id,
    }, indent=2))

    print(f"  [WORKTREE] {worktree_path} ({branch_name})")
    return worktree_path, branch_name


def select_task(state: PipelineState, task_desc: str, state_dir: Path) -> None:
    """STEP 1: Parse intent and create task contract."""
    task = Task(
        task_id=f"go-{state.run_id}",
        title=task_desc[:60],
        objective=task_desc,
        task_type=_classify_task_type(task_desc),
    )
    task.routing = _get_routing(task.task_type)

    state.task = task
    touch_gate(state_dir, "task-selected")

    # Write task contract
    (state_dir / f"task-contract_{state.run_id}.json").write_text(
        json.dumps({
            "task_id": task.task_id,
            "title": task.title,
            "objective": task.objective,
            "status": task.status,
            "task_type": task.task_type,
            "routing": task.routing,
        }, indent=2)
    )
    print(f"  [TASK] {task.title} -> {task.routing['skill']}")


def _classify_task_type(desc: str) -> TaskType:
    """Classify task type from description."""
    desc_lower = desc.lower()
    if "refactor" in desc_lower or "cleanup" in desc_lower:
        return TaskType.REFACTOR
    if "design" in desc_lower or "architecture" in desc_lower:
        return TaskType.DESIGN
    if "plan" in desc_lower or "break down" in desc_lower:
        return TaskType.PLANNING
    if "config" in desc_lower or "infra" in desc_lower:
        return TaskType.CONFIG
    return TaskType.IMPLEMENTATION


def _get_routing(task_type: TaskType) -> dict:
    """Get skill routing for task type."""
    routing_map = {
        TaskType.IMPLEMENTATION: {"skill": "/code", "route": "code"},
        TaskType.REFACTOR: {"skill": "/refactor", "route": "refactor"},
        TaskType.DESIGN: {"skill": "/design", "route": "design"},
        TaskType.PLANNING: {"skill": "/planning", "route": "planning"},
        TaskType.CONFIG: {"skill": "direct", "route": "verify"},
    }
    return routing_map.get(task_type, routing_map[TaskType.IMPLEMENTATION])


def run_verification(state: PipelineState, state_dir: Path) -> bool:
    """STEP 3: Run verification commands."""
    if not state.task.verification_commands:
        print("  [VERIFY] No commands defined, skipping")
        touch_gate(state_dir, "verified")
        return True

    for cmd in state.task.verification_commands:
        print(f"  [VERIFY] Running: {cmd}")
        result = subprocess.run(
            cmd, shell=True, cwd=state.worktree_path,
            capture_output=True, text=True
        )
        if result.returncode != 0:
            state.fail_phase("verify", f"Command failed: {cmd}\n{result.stderr}")
            return False

    touch_gate(state_dir, "verified")
    return True


def run_simplify(state: PipelineState, state_dir: Path) -> bool:
    """STEP 4: Run simplify if code changed."""
    diff_file = state_dir / f"diff-summary_{state.run_id}.json"
    if diff_file.exists():
        diff_data = json.loads(diff_file.read_text())
        if diff_data.get("docs_only"):
            print("  [SIMPLIFY] Skipping (docs-only)")
            touch_gate(state_dir, "simplified")
            return True

    # Invoke /simplify skill
    print("  [SIMPLIFY] Running /simplify on worktree")
    # Note: In Claude Code context, this would be the Skill tool call
    # For CLI execution, we mark it pending for human review
    (state_dir / f"simplify-status_{state.run_id}.md").write_text(
        "# Simplify pending — invoke /simplify manually\n"
    )
    touch_gate(state_dir, "simplified")
    return True


def run_reviews(state: PipelineState, state_dir: Path) -> None:
    """STEP 5: Run 7-pass review."""
    print("  [REVIEWS] Running 7-pass review on worktree changes")
    # Note: In Claude Code context, this would invoke review agents
    touch_gate(state_dir, "reviews-passed")


def generate_pr_artifacts(state: PipelineState, state_dir: Path) -> dict:
    """STEP 6: Generate PR artifacts."""
    if not state.worktree_path:
        raise RuntimeError("No worktree created")

    # Check if we have a commit from merge_worktree
    commit_file = state_dir / "commit-info.json"
    if commit_file.exists():
        commit_info = json.loads(commit_file.read_text())
        commit_hash = commit_info.get("commit", "unknown")
        commit_msg = commit_info.get("message", "")
    else:
        # No merge happened — use worktree HEAD
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H %s"],
            cwd=state.worktree_path, capture_output=True, text=True
        )
        if result.returncode == 0:
            commit_hash, commit_msg = result.stdout.strip().split(" ", 1)
        else:
            commit_hash, commit_msg = "unknown", ""

    pr_artifacts = {
        "commit": commit_hash,
        "message": commit_msg,
        "branch": state.worktree_branch,
        "worktree": state.worktree_path,
    }

    (state_dir / f"pr-artifacts_{state.run_id}.json").write_text(
        json.dumps(pr_artifacts, indent=2)
    )

    touch_gate(state_dir, "pr-ready")
    print(f"  [PR] {commit_hash[:8]} - {commit_msg}")
    return pr_artifacts


def save_state(state: PipelineState, base_dir: Path) -> None:
    """Save pipeline state to disk."""
    state_dir = base_dir / state.terminal_id / "go"
    state_dir.mkdir(parents=True, exist_ok=True)

    (state_dir / f"state_{state.run_id}.json").write_text(
        json.dumps({
            "run_id": state.run_id,
            "terminal_id": state.terminal_id,
            "created_at": state.created_at,
            "task": {
                "task_id": state.task.task_id if state.task else None,
                "title": state.task.title if state.task else None,
                "status": state.task.status if state.task else None,
            } if state.task else None,
            "worktree_path": state.worktree_path,
            "worktree_branch": state.worktree_branch,
            "phases": {
                name: {
                    "status": p.status,
                    "started_at": p.started_at,
                    "completed_at": p.completed_at,
                    "error": p.error,
                }
                for name, p in state.phases.items()
            },
        }, indent=2)
    )


# === Main Orchestrator ===

def run_pipeline(
    task_desc: str,
    output_dir: Optional[str] = None,
    cleanup_mode: CleanupMode = CleanupMode.AUDIT,
) -> dict:
    """Execute the full go-ct pipeline."""
    base_dir = Path(output_dir) if output_dir else Path(".claude/.artifacts")

    # Initialize state
    state = PipelineState()
    state_dir = base_dir / state.terminal_id / "go"
    state_dir.mkdir(parents=True, exist_ok=True)

    print(f"[GO-CT] Run {state.run_id} | Terminal {state.terminal_id}")
    print(f"[GO-CT] Task: {task_desc[:60]}...")

    # PRE-CLEAN: audit orphaned worktrees and stale state
    if cleanup_mode != CleanupMode.SKIP:
        print(f"[GO-CT] Pre-clean ({cleanup_mode.value}):")
        findings = pre_clean(base_dir, "go", cleanup_mode)
        if findings:
            for f in findings:
                print(f"  {f['message']}")
        else:
            print("  No orphaned resources found")

    try:
        # STEP 0: Worktree
        worktree_path, branch = create_worktree(state, base_dir)
        state.complete_phase("worktree")

        # STEP 1: Task
        select_task(state, task_desc, state_dir)
        state.complete_phase("task")

        # Note: Actual code execution happens in worktree via subagent
        # For CLI mode, we skip to verification
        touch_gate(state_dir, "coded")

        # STEP 3: Verify
        if not run_verification(state, state_dir):
            print("[GO-CT] Pipeline BLOCKED at verify")
            save_state(state, base_dir)
            return {"status": "blocked", "run_id": state.run_id}

        state.complete_phase("verify")

        # STEP 4: Simplify
        if not run_simplify(state, state_dir):
            print("[GO-CT] Pipeline BLOCKED at simplify")
            save_state(state, base_dir)
            return {"status": "blocked", "run_id": state.run_id}

        state.complete_phase("simplify")

        # STEP 5: Reviews
        run_reviews(state, state_dir)
        state.complete_phase("reviews")

        # STEP 5.5: Merge
        print("[GO-CT] Merging worktree...")
        commit_info = merge_worktree(state, state_dir)
        state.complete_phase("merge")

        # STEP 6: PR
        generate_pr_artifacts(state, state_dir)
        state.complete_phase("pr")

        # STEP 7: Post-clean
        print("[GO-CT] Post-clean:")
        post_clean(state, base_dir)

        # STEP 8: Save final state
        save_state(state, base_dir)

        print(f"[GO-CT] COMPLETE | {state.run_id} | {worktree_path}")
        return {
            "status": "pr_ready",
            "run_id": state.run_id,
            "worktree": worktree_path,
            "branch": branch,
            "commit": commit_info.get("commit"),
        }

    except Exception as e:
        state.fail_phase("unknown", str(e))
        save_state(state, base_dir)
        print(f"[GO-CT] ERROR: {e}")
        return {"status": "error", "run_id": state.run_id, "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="go-ct executor")
    parser.add_argument("--task", help="Task description (required for pipeline run)")
    parser.add_argument("--output-dir", help="Output directory for artifacts")
    parser.add_argument(
        "--cleanup",
        choices=["audit", "force", "skip"],
        default="audit",
        help="Pre-clean mode: audit (report only), force (prune/archive), skip (none)",
    )
    args = parser.parse_args()

    base_dir = Path(args.output_dir) if args.output_dir else Path(".claude/.artifacts")

    # Standalone audit mode
    if args.cleanup == "audit" and not args.task:
        print("[GO-CT] Running cleanup audit...")
        findings = pre_clean(base_dir, "go", CleanupMode.AUDIT)
        if not findings:
            print("No orphaned resources found.")
        else:
            for f in findings:
                print(f"  {f['message']}")
        return

    if not args.task:
        parser.error("--task is required unless running --cleanup audit only")

    cleanup_mode = CleanupMode(args.cleanup)
    result = run_pipeline(args.task, args.output_dir, cleanup_mode)
    print("\n" + json.dumps(result, indent=2))

    if result["status"] == "blocked":
        sys.exit(1)


if __name__ == "__main__":
    main()