"""Tests for submodule-agnostic /go dispatch (#916).

Anti-mock: real temp git repos + a real `git worktree add` to verify the
worktree lands in the target repo (not an empty parent-level dir).
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import orchestrate  # noqa: E402


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for args in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"],
                 ["git", "config", "user.name", "t"]):
        subprocess.run(args, cwd=path, check=True)
    (path / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def test_nearest_git_root_prefers_inner_repo(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner_repo"
    _init_repo(outer)
    _init_repo(inner)
    assert orchestrate._nearest_git_root(inner / "a.py") == inner.resolve()
    assert orchestrate._nearest_git_root(outer / "a.py") == outer.resolve()


def test_resolve_target_repo_single(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    root, status = orchestrate.resolve_target_repo([str(repo / "a.py")])
    assert status == "single"
    assert root == repo.resolve()


def test_resolve_target_repo_cross_repo(tmp_path: Path) -> None:
    r1 = tmp_path / "r1"
    r2 = tmp_path / "r2"
    _init_repo(r1)
    _init_repo(r2)
    _root, status = orchestrate.resolve_target_repo([str(r1 / "a.py"), str(r2 / "a.py")])
    assert status == "cross-repo"


def test_resolve_target_repo_unknown_for_empty_and_missing() -> None:
    assert orchestrate.resolve_target_repo([])[1] == "unknown"
    assert orchestrate.resolve_target_repo([__file__ + ".nope"])[1] == "unknown"


def test_create_worktree_lands_in_target_repo(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "submod"
    _init_repo(repo)
    (repo / "real.py").write_text("Y = 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "two"], check=True)

    wt_root = tmp_path / "wts"
    monkeypatch.setenv("GO_WORKTREE_ROOT", str(wt_root))
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    target_repo, status = orchestrate.resolve_target_repo([str(repo / "real.py")])
    assert status == "single"
    assert target_repo == repo.resolve()

    wt = orchestrate.create_worktree("pi", state_dir, "run-ABCD1234", target_repo)
    assert wt_root in wt.parents
    assert (wt / "real.py").exists()
    rec = json.loads((state_dir / "worktree-run-ABCD1234.json").read_text())
    assert Path(rec["target_repo"]) == repo.resolve()
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)], check=False)
