#!/usr/bin/env python3
"""go-safe: Cross-platform task initialization guard for /go skill."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def run_git(args: list[str], root_dir: Path) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root_dir,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def die(error: str, artifact_dir: Path, run_id: str) -> None:
    Path(artifact_dir / f".blocked_{run_id}").touch()
    print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)


def require_file(path: Path, artifact_dir: Path, run_id: str) -> None:
    if not path.is_file():
        die(f"missing required file: {path}", artifact_dir, run_id)


def infer_args() -> tuple[str, str, str, str]:
    """Infer or require ROOT_DIR, TERMINAL_ID, GO_RUN_ID, ARTIFACT_ROOT."""
    parser = argparse.ArgumentParser(description="go-safe initialization guard")
    parser.add_argument("--root-dir", help="Root of the repo (default: git toplevel or cwd)")
    parser.add_argument("--terminal-id", help="Terminal ID (default: from env or generated)")
    parser.add_argument("--go-run-id", help="GO_RUN_ID (default: from env or generated)")
    parser.add_argument("--artifact-root", default=".claude/.artifacts", help="Artifact root")
    parser.add_argument("remainder", nargs="*", help="Remaining args passed to init script")
    args = parser.parse_args()

    root_dir = args.root_dir or ""
    if not root_dir:
        rc, out, _ = run_git(["rev-parse", "--show-toplevel"], Path.cwd())
        root_dir = out if rc == 0 else str(Path.cwd().resolve())

    terminal_id = args.terminal_id or os.environ.get("CLAUDE_TERMINAL_ID", "")
    if not terminal_id:
        import uuid
        terminal_id = str(uuid.uuid4()).split("-")[0]

    go_run_id = args.go_run_id or os.environ.get("GO_RUN_ID", "")
    if not go_run_id:
        import uuid
        go_run_id = str(uuid.uuid4())

    artifact_root = args.artifact_root
    return root_dir, terminal_id, go_run_id, artifact_root


def main() -> int:
    root_dir, terminal_id, go_run_id, artifact_root = infer_args()
    root = Path(root_dir).resolve()
    artifact_dir = Path(artifact_root) / terminal_id / "go"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Export for subprocess calls
    os.environ["TERMINAL_ID"] = terminal_id
    os.environ["GO_RUN_ID"] = go_run_id
    os.environ["GO_ARTIFACT_DIR"] = str(artifact_dir)

    # Branch check
    rc, current_branch, _ = run_git(["branch", "--show-current"], root)
    if rc != 0 or not current_branch:
        die("not in a git repository or branch undetectable", artifact_dir, go_run_id)
    if current_branch in ("main", "master"):
        die(f"refusing to run on {current_branch}", artifact_dir, go_run_id)

    # Worktree check
    rc, worktree_out, _ = run_git(["worktree", "list", "--porcelain"], root)
    cwd = str(Path.cwd().resolve())
    in_worktree = False
    if rc == 0:
        for line in worktree_out.splitlines():
            if line.startswith("worktree ") and line.split("worktree ", 1)[1].strip() == cwd:
                in_worktree = True
                break

    if not in_worktree:
        # Allow non-worktree only if explicitly configured; default is to warn
        (artifact_dir / f".worktree-ready_{go_run_id}").touch()
    else:
        (artifact_dir / f".worktree-ready_{go_run_id}").touch()

    # Build paths to called scripts
    skills_go = root / "skills" / "go"
    init_script = skills_go / "scripts" / "init_go_run.py"
    validator = skills_go / "scripts" / "validate_go_contracts.py"

    # Run init_go_run.py
    init_result = subprocess.run(
        [
            sys.executable, str(init_script),
            "--root-dir", str(root),
            "--terminal-id", terminal_id,
            "--go-run-id", go_run_id,
            "--artifact-dir", str(artifact_dir),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if init_result.returncode != 0:
        die(f"init_go_run.py failed: {init_result.stderr.strip()}", artifact_dir, go_run_id)

    # Verify required artifacts exist
    for fname in [
        f"run_{go_run_id}.json",
        f"selected-task_{go_run_id}.json",
        f"dispatch-decision_{go_run_id}.json",
        f"dispatch-result_{go_run_id}.json",
    ]:
        require_file(artifact_dir / fname, artifact_dir, go_run_id)

    # Validate contracts
    schema_dir = skills_go / "schemas"
    val_result = subprocess.run(
        [sys.executable, str(validator), "--schema-dir", str(schema_dir), "--artifact-dir", str(artifact_dir)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if val_result.returncode != 0:
        die(f"contract validation failed: {val_result.stderr.strip()}", artifact_dir, go_run_id)

    print(f"<promise>GO_DISPATCHED</promise>")
    print(f"GO_RUN_ID={go_run_id}")
    print(f"TERMINAL_ID={terminal_id}")
    print(f"ARTIFACT_DIR={artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
