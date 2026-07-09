"""Tests for /go Worktree Safety v1.

Real git repos in tmp_path, no Mock objects. Exercises the CLI via main(argv)
and the guard via simulated stdin payloads.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import worktree_safety as ws  # noqa: E402


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--quiet", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "test")


def _commit_all(path: Path, msg: str) -> str:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", msg)
    return _git(path, "rev-parse", "HEAD").stdout.strip()


def _start_task(state_dir: Path, repo: Path, task_id: str, wt_root: Path,
                **extra) -> int:
    argv = ["--state-dir", str(state_dir), "start",
            "--task-id", task_id, "--title", f"Task {task_id}",
            "--repo-root", str(repo), "--worktree-root", str(wt_root)]
    for k, v in extra.items():
        argv.extend([f"--{k.replace('_', '-')}", str(v)])
    return ws.main(argv)


def test_metadata_creation_and_validation(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "readme.md").write_text("# p\n", encoding="utf-8")
    base = _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    rc = _start_task(state, repo, "wt-1", wt_root)
    assert rc == 0
    meta = json.loads((state / "worktree-tasks" / "wt-1.json").read_text())
    assert meta["schema"] == "worktree-task.v1"
    assert meta["task_id"] == "wt-1"
    assert meta["status"] == "active"
    assert meta["base_commit"] == base
    assert meta["canonical_branch"] == "main"
    assert meta["branch"] == "wt/wt-1"
    assert Path(meta["worktree_path"]).is_dir()


def test_duplicate_active_task_id_refusal(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "r.md").write_text("x\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    assert _start_task(state, repo, "wt-dup", wt_root) == 0
    assert _start_task(state, repo, "wt-dup", wt_root) == 1
    argv = ["--state-dir", str(state), "start", "--task-id", "wt-dup",
            "--title", "Dup", "--repo-root", str(repo), "--resume"]
    assert ws.main(argv) == 0


def test_dry_run_start_emits_commands(tmp_path, capsys):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "r.md").write_text("x\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    argv = ["--state-dir", str(state), "start", "--task-id", "wt-dry",
            "--title", "Dry", "--repo-root", str(repo),
            "--worktree-root", str(wt_root), "--dry-run",
            "--intended-files", "skills/go/scripts/orchestrate.py"]
    rc = ws.main(argv)
    assert rc == 0
    out = capsys.readouterr()
    assert "[dry-run]" in out.out
    assert "worktree add" in out.out
    assert not (state / "worktree-tasks" / "wt-dry.json").exists()
    assert "WARNING" in out.err


def test_status_detects_dirty(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "r.md").write_text("x\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    _start_task(state, repo, "wt-dirty", wt_root)
    meta = json.loads((state / "worktree-tasks" / "wt-dirty.json").read_text())
    (Path(meta["worktree_path"]) / "r.md").write_text("dirty\n")
    results = []
    for t in ws._list_metadata(state):
        sp = ws._git(Path(t["worktree_path"]), "status", "--short")
        results.append(bool(sp.stdout.strip()))
    assert any(results)


def test_status_detects_stale_base(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "r.md").write_text("v1\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    _start_task(state, repo, "wt-stale", wt_root)
    (repo / "r.md").write_text("v2\n"); _commit_all(repo, "advance main")
    meta = json.loads((state / "worktree-tasks" / "wt-stale.json").read_text())
    mp = ws._git(repo, "rev-parse", "main")
    assert mp.stdout.strip() != meta["base_commit"]


def test_status_detects_sensitive_touch(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "skills" / "go" / "scripts").mkdir(parents=True)
    (repo / "skills" / "go" / "scripts" / "orchestrate.py").write_text("# o\n")
    _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    _start_task(state, repo, "wt-sens", wt_root)
    meta = json.loads((state / "worktree-tasks" / "wt-sens.json").read_text())
    wt = Path(meta["worktree_path"])
    (wt / "skills" / "go" / "scripts" / "orchestrate.py").write_text("# changed\n")
    _commit_all(wt, "change sensitive")
    sensitive = ws._sensitive_touched(wt, meta["base_commit"])
    assert "skills/go/scripts/orchestrate.py" in sensitive


def test_precheck_reports_changed_and_risk(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "lib.py").write_text("x = 1\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    _start_task(state, repo, "wt-pre", wt_root, intended_files="lib.py")
    meta = json.loads((state / "worktree-tasks" / "wt-pre.json").read_text())
    (Path(meta["worktree_path"]) / "lib.py").write_text("x = 2\n")
    _commit_all(Path(meta["worktree_path"]), "change")
    argv = ["--state-dir", str(state), "precheck", "--task-id", "wt-pre", "--json"]
    rc = ws.main(argv)
    assert rc == 0
    packet = json.loads((state / "worktree-tasks" / "wt-pre.precheck.json").read_text())
    assert "lib.py" in packet["changed_files"]
    assert packet["merge_risk"] == "low"


def test_precheck_detects_upstream_change(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "lib.py").write_text("x = 1\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    _start_task(state, repo, "wt-up", wt_root, intended_files="lib.py")
    (repo / "lib.py").write_text("x = 99\n"); _commit_all(repo, "upstream change")
    argv = ["--state-dir", str(state), "precheck", "--task-id", "wt-up", "--json"]
    rc = ws.main(argv)
    assert rc == 0
    packet = json.loads((state / "worktree-tasks" / "wt-up.precheck.json").read_text())
    assert "lib.py" in packet["upstream_changed_intended"]
    assert packet["merge_risk"] in ("medium", "high")


def test_cleanup_dry_run_deletes_nothing(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "r.md").write_text("x\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    _start_task(state, repo, "wt-clean", wt_root)
    wt_path = json.loads((state / "worktree-tasks" / "wt-clean.json").read_text())["worktree_path"]
    argv = ["--state-dir", str(state), "cleanup"]
    rc = ws.main(argv)
    assert rc == 0
    assert Path(wt_path).is_dir()


def test_cleanup_refuses_dirty_active(tmp_path):
    repo = tmp_path / "repo"; _init_repo(repo)
    (repo / "r.md").write_text("x\n"); _commit_all(repo, "init")
    state = tmp_path / "state"; wt_root = tmp_path / "wt"
    _start_task(state, repo, "wt-dirty-clean", wt_root)
    meta = json.loads((state / "worktree-tasks" / "wt-dirty-clean.json").read_text())
    (Path(meta["worktree_path"]) / "r.md").write_text("dirty\n")
    argv = ["--state-dir", str(state), "cleanup", "--remove"]
    rc = ws.main(argv)
    assert rc == 1


def test_guard_allows_non_sensitive_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    payload = json.dumps({"tool_name": "Edit",
                          "tool_input": {"file_path": "skills/go/scripts/other.py"}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    _HOOKS = PLUGIN_ROOT / "hooks"
    if str(_HOOKS) not in sys.path:
        sys.path.insert(0, str(_HOOKS))
    import worktree_safety_PreToolUse as guard  # noqa: E402
    rc = guard.main()
    assert rc == 0
    out = capsys.readouterr()
    assert out.out == ""


def test_guard_warns_sensitive_outside_worktree(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/go/scripts/orchestrate.py"}
    })
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    _HOOKS = PLUGIN_ROOT / "hooks"
    if str(_HOOKS) not in sys.path:
        sys.path.insert(0, str(_HOOKS))
    import worktree_safety_PreToolUse as guard  # noqa: E402
    rc = guard.main()
    assert rc == 0
    out = capsys.readouterr()
    assert "WORKTREE_SAFETY" in out.err


def test_malformed_metadata_fails_gracefully(tmp_path):
    state = tmp_path / "state"
    meta_dir = state / "worktree-tasks"
    meta_dir.mkdir(parents=True)
    (meta_dir / "wt-bad.json").write_text("not valid json {{{")
    result = ws._list_metadata(state)
    assert result == []
    argv = ["--state-dir", str(state), "status", "--json"]
    assert ws.main(argv) == 0
