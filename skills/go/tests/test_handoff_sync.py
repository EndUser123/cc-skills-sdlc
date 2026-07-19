"""Tests for handoff_sync.py — sentinel-block HANDOFF.md generator.

PR 4 of P:/docs/worktree-lifecycle-design.md. Verifies:
- generate_block produces well-formed Markdown
- sync() inserts/updates the sentinel block without disturbing other content
- sync() returns False when no change is needed
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _git_repo(dst: Path) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for c in [("init", "-q"), ("config", "user.email", "t"), ("config", "user.name", "t")]:
        subprocess.run(["git", "-C", str(dst), *c], check=True)
    (dst / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "-C", str(dst), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(dst), "commit", "-qm", "base"], check=True)
    return dst


def test_generate_block_with_no_worktrees():
    """generate_block returns valid Markdown for empty state."""
    from handoff_sync import generate_block
    block = generate_block([], main_branch="main")
    assert "<!-- BEGIN worktree-status" in block
    assert "<!-- END worktree-status -->" in block
    assert "no worktrees registered" in block
    assert "main" in block  # main_branch referenced


def test_generate_block_with_worktrees():
    """generate_block produces a table for non-empty state."""
    from handoff_sync import generate_block, WorktreeState
    states = [
        WorktreeState(path="/repo/.worktrees/feat-a", branch="feat-a", behind_main=0, status="active"),
        WorktreeState(path="/repo/.worktrees/feat-b", branch="feat-b", behind_main=3, status="active"),
    ]
    block = generate_block(states, main_branch="main")
    assert "feat-a" in block
    assert "feat-b" in block
    assert "0" in block
    assert "3" in block
    assert "main" in block


def test_collect_worktree_states(tmp_path):
    """collect_worktree_states parses git worktree list --porcelain correctly."""
    from handoff_sync import collect_worktree_states, WorktreeState
    repo = _git_repo(tmp_path / "repo")
    # Create one worktree
    wt = tmp_path / "wts" / "wt-test"
    wt.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", "test-branch", str(wt), "HEAD"],
        check=True, capture_output=True,
    )
    try:
        states = collect_worktree_states(repo, main_branch="main")
        # At least the main worktree + the test worktree
        assert len(states) >= 1
        # Find our worktree
        wt_state = next((s for s in states if s.branch == "test-branch"), None)
        assert wt_state is not None, f"test-branch not in {[(s.branch, s.path) for s in states]}"
        assert wt_state.behind_main == 0
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(wt)],
                       check=False, capture_output=True)


def test_sync_creates_block_in_new_file(tmp_path):
    """sync() on a non-existent file creates the file with the sentinel block."""
    from handoff_sync import sync
    repo = _git_repo(tmp_path / "repo")
    handoff = tmp_path / "HANDOFF.md"
    assert not handoff.exists()
    updated = sync(repo, handoff, main_branch="main")
    assert updated is True
    assert handoff.exists()
    content = handoff.read_text(encoding="utf-8")
    assert "<!-- BEGIN worktree-status" in content
    assert "<!-- END worktree-status -->" in content


def test_sync_replaces_existing_block(tmp_path):
    """sync() replaces the existing sentinel block, preserves content outside it."""
    from handoff_sync import sync
    repo = _git_repo(tmp_path / "repo")
    handoff = tmp_path / "HANDOFF.md"
    initial = (
        "# Project HANDOFF\n"
        "\n"
        "Some manual notes here that should be preserved.\n"
        "\n"
        "<!-- BEGIN worktree-status (auto-generated; do not edit) -->\n"
        "<!-- generated: old -->\n"
        "OLD CONTENT\n"
        "<!-- END worktree-status -->\n"
        "\n"
        "More manual notes after.\n"
    )
    handoff.write_text(initial, encoding="utf-8")

    updated = sync(repo, handoff, main_branch="main")
    assert updated is True

    new_content = handoff.read_text(encoding="utf-8")
    assert "OLD CONTENT" not in new_content
    assert "Some manual notes here that should be preserved." in new_content
    assert "More manual notes after." in new_content
    # Sentinel markers present
    assert "<!-- BEGIN worktree-status" in new_content
    assert "<!-- END worktree-status -->" in new_content


def test_sync_returns_false_when_unchanged(tmp_path):
    """sync() returns False when the block content is the same as the existing block."""
    from handoff_sync import sync, generate_block
    repo = _git_repo(tmp_path / "repo")
    handoff = tmp_path / "HANDOFF.md"

    # First sync to create
    sync(repo, handoff, main_branch="main")
    # Second sync — should be unchanged
    updated = sync(repo, handoff, main_branch="main")
    assert updated is False


def test_sync_preserves_manual_edits_outside_sentinels(tmp_path):
    """Manual edits in the file but outside sentinels are preserved across multiple syncs."""
    from handoff_sync import sync
    repo = _git_repo(tmp_path / "repo")
    handoff = tmp_path / "HANDOFF.md"

    sync(repo, handoff, main_branch="main")

    # Add a manual section BEFORE the sentinel block
    content = handoff.read_text(encoding="utf-8")
    new_content = "# Project Header\n\nMy important notes.\n\n" + content
    handoff.write_text(new_content, encoding="utf-8")

    # Sync again — header should be preserved
    sync(repo, handoff, main_branch="main")
    final = handoff.read_text(encoding="utf-8")
    assert "My important notes." in final
    assert "# Project Header" in final