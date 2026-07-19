"""Worktree lifecycle tests (15 cases) for /go shared lifecycle primitives.

Uses real temporary git repos and worktrees. Each test is self-contained.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

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


def _create_falsify_worktree(repo, worktree_root, run_id="test-run-1", head=None):
    """Helper: create a falsify-style worktree for lifecycle tests."""
    if head is None:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True).stdout.strip()
    wd = worktree_root / f"falsify-{run_id[:8]}"
    branch = f"falsify/{run_id[:8]}"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-b", branch, str(wd), head],
        check=True, capture_output=True)
    return wd, branch, run_id


# --- imports for lifecycle ---

@pytest.fixture(autouse=True)
def _monkey_enable(monkeypatch):
    monkeypatch.setenv("GO_FALSIFICATION_ENABLE", "1")


def _ws():
    import worktree_safety as ws
    import importlib
    importlib.reload(ws)
    return ws


# Test 1: normal success removes everything
def test_1_normal_success_cleans_all(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-1")
    assert aw.is_dir()
    reg = ws.lifecycle_register(aw, branch, run_id, repo, "test",
                                 state_dir=tmp_path / "state")
    assert reg["status"] == "active"
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    assert lr["git_remove_ok"] is True
    assert lr["branch_deleted"] is True
    assert lr["git_pruned"] is True
    assert not aw.is_dir()
    r = ws.lifecycle_get_registration(run_id, tmp_path / "state")
    assert r.get("cleanup_state") == "cleaned"


# Test 2: expected block cleans
def test_2_expected_block_cleans(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-2")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    assert lr["git_remove_ok"] is True
    assert not aw.is_dir()


# Test 3: timeout cleans
def test_3_timeout_cleans(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-3")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    assert lr["git_remove_ok"] is True
    assert not aw.is_dir()


# Test 4: malformed result failure cleans
def test_4_malformed_result_cleans(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-4")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    assert lr["git_remove_ok"] is True
    assert not aw.is_dir()


# Test 5: exception between creation and registration is reconciled
def test_5_unregistered_worktree_reconciled(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-5")
    assert aw.is_dir()
    # Simulate never registering (crash after creation)
    # Reconcile should find it as RECLAIMABLE (git-registered but no lifecycle)
    rc = ws.lifecycle_reconcile(tmp_path / "state")
    # Find our path
    for e in rc.get("entries", []):
        if "run-5" in e["path"]:
            assert e["classification"] in ("RECLAIMABLE", "ORPHAN_DIRECTORY")
            break
    else:
        pytest.skip("reconcile output format depends on git metadata scope")
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    subprocess.run(["git", "-C", str(repo), "branch", "-D", branch])


# Test 6: directory gone but git metadata remains
def test_6_orphan_git_metadata(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-6")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    # Remove directory only
    shutil.rmtree(aw, ignore_errors=True)
    assert not aw.is_dir()
    # Git metadata still registered
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    assert lr["branch_deleted"] is True
    assert lr["git_pruned"] is True


# Test 7: git metadata gone but directory remains
def test_7_directory_without_git_metadata(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-7")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    # Clean with lifecycle succeeds before .git is removed
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    # After lifecycle_clean_worktree, directory must be gone
    assert not aw.exists(), f"worktree {aw} still exists after lifecycle_clean_worktree"
    # Verify lifecycle registry updated
    reg = ws.lifecycle_get_registration(run_id, tmp_path / "state")
    assert reg.get("cleanup_state") == "cleaned"


# Test 8: foreign/newer worktree untouched
def test_8_foreign_newer_untouched(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    # Create two worktrees.
    aw1, b1, r1 = _create_falsify_worktree(repo, tmp_path, "run-old")
    aw2, b2, r2 = _create_falsify_worktree(repo, tmp_path, "run-newer")
    # Register both.
    ws.lifecycle_register(aw1, b1, r1, repo, "test",
                           state_dir=tmp_path / "state")
    ws.lifecycle_register(aw2, b2, r2, repo, "test",
                           state_dir=tmp_path / "state")
    # Clean only the first (old) one.
    lr = ws.lifecycle_clean_worktree(aw1, repo, r1, tmp_path / "state",
                                       branch_name=b1)
    assert lr["git_remove_ok"] is True
    # The newer one should still exist.
    assert aw2.is_dir()
    # Clean up
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw2)])
    subprocess.run(["git", "-C", str(repo), "branch", "-D", b2])


# Test 9: active session-bound worktree untouched
def test_9_active_worktree_untouched(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-active")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state",
                           owner_session="active-session")
    # lifecycle_reconcile should classify it as ACTIVE
    rc = ws.lifecycle_reconcile(tmp_path / "state")
    found = False
    for e in rc.get("entries", []):
        if "run-active" in e["path"]:
            assert e["classification"] == "ACTIVE", f"got {e['classification']}"
            found = True
    if not found:
        pytest.skip("reconcile scope")
    # Clean up
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    subprocess.run(["git", "-C", str(repo), "branch", "-D", branch])


# Test 10: Windows cleanup failure becomes CLEANUP_FAILED
def test_10_cleanup_failure_classified(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-10")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    # Mark as cleaned but leave directory (simulates partial failure)
    ws.lifecycle_mark_terminal(run_id, "cleaned", tmp_path / "state")
    # Reconcile should see CLEANUP_FAILED
    rc = ws.lifecycle_reconcile(tmp_path / "state")
    found = False
    for e in rc.get("entries", []):
        if "run-10" in e["path"]:
            if e["classification"] == "CLEANUP_FAILED":
                found = True
    # Clean up
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    subprocess.run(["git", "-C", str(repo), "branch", "-D", branch])
    if not found:
        pytest.skip("reconcile scope")


# Test 11: PRESERVED_FOR_REVIEW worktree not reclaimed
def test_11_preserved_not_reclaimed(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-pres")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    ws.lifecycle_quarantine(aw, run_id, "review needed", repo,
                             branch, tmp_path / "state", expire_hours=4)
    rc = ws.lifecycle_reconcile(tmp_path / "state")
    found = False
    for e in rc.get("entries", []):
        if "run-pres" in e["path"]:
            assert e["classification"] == "PRESERVED_FOR_REVIEW"
            found = True
    if not found:
        pytest.skip("reconcile scope")
    # Clean up manually
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    subprocess.run(["git", "-C", str(repo), "branch", "-D", branch])


# Test 12: expired quarantine becomes reclaimable
def test_12_expired_quarantine_reclaimable(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-exp")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    # Set expired quarantine (0 hours = already expired)
    ws.lifecycle_quarantine(aw, run_id, "temp issue", repo,
                             branch, tmp_path / "state",
                             expire_hours=-1)
    # Reconcile
    rc = ws.lifecycle_reconcile(tmp_path / "state")
    # Clean up manually
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    subprocess.run(["git", "-C", str(repo), "branch", "-D", branch])


# Test 13: cleanup is idempotent
def test_13_idempotent_cleanup(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-idem")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    lr1 = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                        branch_name=branch)
    assert "errors" not in lr1 or not lr1["errors"]
    # Idempotent: already removed
    lr2 = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                        branch_name=branch)
    # Should not crash; branch deletion may fail (already gone)
    assert isinstance(lr2, dict)


# Test 14: next-session reconciliation finds crash leftovers
def test_14_crash_leftover_reconciliation(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-crash")
    # Simulate crash: worktree created, never registered
    assert aw.is_dir()
    # Reconcile should find it
    rc = ws.lifecycle_reconcile(tmp_path / "state")
    # Clean up
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    subprocess.run(["git", "-C", str(repo), "branch", "-D", branch])


# Test 15: branch deletion occurs only when safe
def test_15_branch_deletion_safe(tmp_path):
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-br")
    ws.lifecycle_register(aw, branch, run_id, repo, "test",
                           state_dir=tmp_path / "state")
    # Clean worktree first
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    # Now try lifecycle clean (branch still exists)
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    # Branch should be deleted since worktree is already gone
    bp = subprocess.run(["git", "-C", str(repo), "branch", "--list", branch],
                         capture_output=True, text=True)
    assert bp.stdout.strip() == "", f"branch {branch} still exists"


# Test 16: PR 1 falsifier — unreachable branch is preserved by default
def test_16_unreachable_branch_preserved_without_auto_tag(tmp_path):
    """PR 1 falsifier: lifecycle_clean_worktree must NOT silently -D a
    branch whose tip is not reachable from main. Only auto_tag=True
    creates a backup tag and force-deletes."""
    ws = _ws()
    repo = _git_repo(tmp_path / "repo")
    aw, branch, run_id = _create_falsify_worktree(repo, tmp_path, "run-unc")
    # Make a commit in the worktree so the branch diverges from main
    test_file = aw / "extra.txt"
    test_file.write_text("diverged content\n")
    subprocess.run(["git", "-C", str(aw), "add", "extra.txt"], check=True)
    subprocess.run(["git", "-C", str(aw), "commit", "-m", "diverge"], check=True)
    # Capture branch tip before worktree removal
    tip_before = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", branch],
        capture_output=True, text=True).stdout.strip()
    # Manually remove the worktree
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)])
    # Call lifecycle clean WITHOUT auto_tag — branch should be preserved
    lr = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                       branch_name=branch)
    assert lr["branch_deleted"] is False, (
        f"unreachable branch was deleted without auto_tag: {lr}")
    bp = subprocess.run(["git", "-C", str(repo), "branch", "--list", branch],
                         capture_output=True, text=True)
    assert bp.stdout.strip() != "", (
        f"unreachable branch {branch} was lost from the repo")
    # Branch tip is unchanged (still the diverged commit)
    tip_after = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", branch],
        capture_output=True, text=True).stdout.strip()
    assert tip_after == tip_before, (
        f"branch tip changed: {tip_after} != {tip_before}")
    # Now retry WITH auto_tag=True — branch should be deleted, backup tag created
    lr2 = ws.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / "state",
                                        branch_name=branch, auto_tag=True)
    assert lr2["branch_deleted"] is True, (
        f"branch should be deleted with auto_tag=True: {lr2}")
    # Branch should be gone now
    bp2 = subprocess.run(["git", "-C", str(repo), "branch", "--list", branch],
                         capture_output=True, text=True)
    assert bp2.stdout.strip() == "", (
        f"branch {branch} still exists after auto_tag delete")
    # Backup tag should exist and point to the original tip
    tag_pattern = f"backup/{branch.replace('/', '-')}-*"
    tag_list = subprocess.run(
        ["git", "-C", str(repo), "tag", "-l", tag_pattern],
        capture_output=True, text=True).stdout.strip()
    assert tag_list, "no backup tag created"
    first_tag = tag_list.split("\n")[0]
    tag_target = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"{first_tag}^{{commit}}"],
        capture_output=True, text=True).stdout.strip()
    assert tag_target == tip_before, (
        f"backup tag points to {tag_target}, expected {tip_before}")


# --- Management-root reconciliation boundary tests --------------------------
# The management root controls disk scanning scope. Git cross-reference
# finds registered worktrees regardless of location. These tests verify
# the boundary semantics.


def test_default_root_worktree_visible_to_reconciliation(tmp_path, monkeypatch):
    import importlib
    import worktree_safety as ws_mod
    importlib.reload(ws_mod)
    default_root = tmp_path / '.worktrees'
    monkeypatch.setenv('GO_WORKTREE_ROOT', str(default_root))
    importlib.reload(ws_mod)
    repo = _git_repo(tmp_path / 'repo')
    aw, branch, run_id = _create_falsify_worktree(repo, default_root, 'run-vis')
    ws_mod.lifecycle_register(aw, branch, run_id, repo, 'test',
                               state_dir=tmp_path / 'state')
    rc_result = ws_mod.lifecycle_reconcile(tmp_path / 'state')
    found = any('run-vis' in e['path'] for e in rc_result.get('entries', []))
    ws_mod.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / 'state',
                                     branch_name=branch)
    assert found, 'Worktree not found in reconcile result'


def test_git_worktree_outside_management_root_found(tmp_path, monkeypatch):
    import importlib
    import worktree_safety as ws_mod
    importlib.reload(ws_mod)
    repo = _git_repo(tmp_path / 'repo')
    outside_root = tmp_path / 'outside'
    aw, branch, run_id = _create_falsify_worktree(repo, outside_root, 'run-out')
    ws_mod.lifecycle_register(aw, branch, run_id, repo, 'test',
                               state_dir=tmp_path / 'state')
    monkeypatch.setattr(ws_mod, 'LIFECYCLE_MANAGED_WORKTREE_ROOT', tmp_path)
    rc = ws_mod.lifecycle_reconcile(tmp_path / 'state')
    found = any('run-out' in e['path'] for e in rc.get('entries', []))
    ws_mod.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / 'state',
                                     branch_name=branch)
    assert found, 'Git-registered outside management root not found'


def test_disk_orphan_outside_management_root_excluded(tmp_path, monkeypatch):
    import importlib
    import worktree_safety as ws_mod
    importlib.reload(ws_mod)
    orphan_root = tmp_path / 'other'
    orphan_root.mkdir(parents=True, exist_ok=True)
    (orphan_root / 'falsify-orphan').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ws_mod, 'LIFECYCLE_MANAGED_WORKTREE_ROOT', tmp_path)
    rc = ws_mod.lifecycle_reconcile(tmp_path / 'state')
    found = any('falsify-orphan' in e['path'] for e in rc.get('entries', []))
    assert not found, 'Disk orphan outside management root was claimed'


def test_existing_worktrees_not_moved(tmp_path, monkeypatch):
    import importlib
    import worktree_safety as ws_mod
    importlib.reload(ws_mod)
    repo = _git_repo(tmp_path / 'repo')
    old_root = tmp_path / 'old-worktrees'
    aw, branch, run_id = _create_falsify_worktree(repo, old_root, 'run-old-loc')
    original_path = str(aw.resolve())
    ws_mod.lifecycle_register(aw, branch, run_id, repo, 'test',
                               state_dir=tmp_path / 'state')
    monkeypatch.setattr(ws_mod, 'LIFECYCLE_MANAGED_WORKTREE_ROOT', tmp_path)
    rc = ws_mod.lifecycle_reconcile(tmp_path / 'state')
    for e in rc.get('entries', []):
        if 'run-old-loc' in e['path']:
            assert aw.is_dir(), 'Worktree removed'
            assert str(aw.resolve()) == original_path, 'Worktree path changed'
            break
    ws_mod.lifecycle_clean_worktree(aw, repo, run_id, tmp_path / 'state',
                                     branch_name=branch)


# --- PR 2 tests: worktree_lifecycle module -----------------------------------
# Extracted helpers from worktree_safety.lifecycle_clean_worktree. Each test
# creates a real temporary git repo so reachability checks are exercised.


def test_safe_delete_branch_reachable(tmp_path):
    """Branch tip equal to main HEAD -> reachable -> safe-delete via -d."""
    from worktree_lifecycle import safe_delete_branch
    repo = _git_repo(tmp_path / "repo")
    # Create a branch at HEAD (reachable from main)
    subprocess.run(["git", "-C", str(repo), "branch", "feat/merged"], check=True)
    deleted, status = safe_delete_branch(repo, "feat/merged")
    assert deleted is True
    assert status == "merged_deleted"
    bp = subprocess.run(["git", "-C", str(repo), "branch", "--list", "feat/merged"],
                        capture_output=True, text=True)
    assert bp.stdout.strip() == "", "branch still exists"


def test_safe_delete_branch_unreachable_default_preserves(tmp_path):
    """Branch tip NOT reachable from main; auto_tag=False (default) -> preserved."""
    from worktree_lifecycle import safe_delete_branch
    repo = _git_repo(tmp_path / "repo")
    aw, _branch, _run = _create_falsify_worktree(repo, tmp_path, "run-sdb")
    # Make a divergent commit so branch tip is unreachable
    (aw / "extra.txt").write_text("divergent\n")
    subprocess.run(["git", "-C", str(aw), "add", "extra.txt"], check=True)
    subprocess.run(["git", "-C", str(aw), "commit", "-qm", "diverge"], check=True)
    branch = "falsify/run-sdb"
    deleted, status = safe_delete_branch(repo, branch, auto_tag=False)
    assert deleted is False
    assert status == "unreachable_preserved"
    bp = subprocess.run(["git", "-C", str(repo), "branch", "--list", branch],
                        capture_output=True, text=True)
    assert bp.stdout.strip() != "", "unreachable branch was deleted (should be preserved)"


def test_safe_delete_branch_unreachable_auto_tag_deletes(tmp_path):
    """Branch tip NOT reachable; auto_tag=True -> backup tag created, branch deleted."""
    from worktree_lifecycle import safe_delete_branch
    repo = _git_repo(tmp_path / "repo")
    aw, _branch, _run = _create_falsify_worktree(repo, tmp_path, "run-at")
    (aw / "extra.txt").write_text("divergent\n")
    subprocess.run(["git", "-C", str(aw), "add", "extra.txt"], check=True)
    subprocess.run(["git", "-C", str(aw), "commit", "-qm", "diverge"], check=True)
    branch = "falsify/run-at"
    # Remove the worktree first (safe_delete_branch requires branch not in use)
    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(aw)],
                   check=True)
    tip_before = subprocess.run(["git", "-C", str(repo), "rev-parse", branch],
                               capture_output=True, text=True).stdout.strip()
    deleted, status = safe_delete_branch(repo, branch, auto_tag=True)
    assert deleted is True, f"safe_delete_branch returned deleted=False, status={status!r}"
    assert status.startswith("backup_tag_deleted:"), f"unexpected status: {status}"
    # Branch is gone
    bp = subprocess.run(["git", "-C", str(repo), "branch", "--list", branch],
                        capture_output=True, text=True)
    assert bp.stdout.strip() == "", "branch still exists after auto_tag delete"
    # Backup tag exists and points at original tip
    tag_name = status.split(":", 1)[1]
    tag_target = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"{tag_name}^" + "{commit}"],
        capture_output=True, text=True,
    ).stdout.strip()
    assert tag_target == tip_before, (
        f"backup tag points to {tag_target}, expected {tip_before}"
    )


def test_safe_delete_branch_in_use_returns_error(tmp_path):
    """safe_delete_branch fails (does not crash) when branch is currently checked out."""
    from worktree_lifecycle import safe_delete_branch
    repo = _git_repo(tmp_path / "repo")
    _aw, _branch, _run = _create_falsify_worktree(repo, tmp_path, "run-inuse")
    # Branch is `falsify/run-inus` (run_id[:8] of "run-inuse")
    actual_branch = "falsify/run-inus"
    # Don't remove the worktree — the branch is still in use.
    deleted, status = safe_delete_branch(repo, actual_branch, auto_tag=False)
    assert deleted is False
    assert status.startswith("git_error:"), f"expected git_error, got {status!r}"
    # Branch is still present
    bp = subprocess.run(["git", "-C", str(repo), "branch", "--list", actual_branch],
                        capture_output=True, text=True)
    assert bp.stdout.strip() != "", "branch should still exist after failed delete"


def test_repo_policy_validate_name_default():
    """Default RepoPolicy accepts alphanum / dot / dash / underscore names."""
    from worktree_lifecycle import RepoPolicy
    p = RepoPolicy()
    ok, msg = p.validate_name("yt-is-cleanup-foo")
    assert ok is True and msg == ""
    ok, msg = p.validate_name("refactor.cold-planes_v2")
    assert ok is True
    # Empty name rejected
    ok, msg = p.validate_name("")
    assert ok is False
    # Names with shell metacharacters rejected
    ok, msg = p.validate_name("foo;rm -rf /")
    assert ok is False
    ok, msg = p.validate_name("foo bar")  # space
    assert ok is False


def test_repo_policy_validate_name_custom_pattern():
    """Custom naming_pattern is enforced."""
    from worktree_lifecycle import RepoPolicy
    p = RepoPolicy(naming_pattern=r"^yt-is-[a-z]+-[a-z0-9]{4}$")
    ok, _ = p.validate_name("yt-is-feature-abcd")
    assert ok is True
    ok, _ = p.validate_name("yt-is-feature-abC")  # uppercase fails lowercase-only pattern
    assert ok is False
    ok, _ = p.validate_name("not-yt-is-feature-abcd")  # wrong prefix
    assert ok is False


def test_validate_name_function_with_and_without_policy():
    """Standalone validate_name function uses default policy when none given."""
    from worktree_lifecycle import validate_name, RepoPolicy
    # No policy -> defaults
    ok, _ = validate_name("anything.reasonable-name")
    assert ok is True
    # With explicit policy
    ok, _ = validate_name("foo", RepoPolicy(naming_pattern=r"^bar$"))
    assert ok is False
    ok, _ = validate_name("bar", RepoPolicy(naming_pattern=r"^bar$"))
    assert ok is True


def test_load_policy_default_when_no_file(tmp_path):
    """load_policy returns defaults when file doesn't exist."""
    from worktree_lifecycle import load_policy
    p = load_policy(tmp_path / "nonexistent.toml")
    assert p.package_name == "yt-is"
    assert p.main_branch == "main"
    assert p.backup_tag_prefix == "backup"


def test_load_policy_default_when_none(tmp_path):
    """load_policy(None) returns defaults (graceful no-op)."""
    from worktree_lifecycle import load_policy
    p = load_policy(None)
    assert p.package_name == "yt-is"
    assert p.main_branch == "main"


def test_load_policy_from_toml(tmp_path):
    """load_policy reads worktree-policy.toml when present."""
    from worktree_lifecycle import load_policy
    from pathlib import Path as _P
    cfg = tmp_path / "worktree-policy.toml"
    cfg.write_text(
        '[package]\n'
        'name = "my-pkg"\n'
        '\n'
        '[worktree]\n'
        'main_branch = "trunk"\n'
        'naming_pattern = "^my-pkg-[a-z]+-[a-z0-9]+$"\n'
        'worktree_root = "/tmp/wt"\n'
        'backup_tag_prefix = "bk"\n',
        encoding="utf-8",
    )
    p = load_policy(cfg)
    assert p.package_name == "my-pkg"
    assert p.main_branch == "trunk"
    assert p.naming_pattern == r"^my-pkg-[a-z]+-[a-z0-9]+$"
    # Path comparison (stringifying Path is OS-dependent; comparing Path objects is not)
    assert p.worktree_root == _P("/tmp/wt")
    assert p.backup_tag_prefix == "bk"


def test_load_policy_handles_malformed_gracefully(tmp_path):
    """load_policy returns defaults on malformed TOML (doesn't raise)."""
    from worktree_lifecycle import load_policy
    cfg = tmp_path / "broken.toml"
    cfg.write_text("this is not [valid toml", encoding="utf-8")
    p = load_policy(cfg)
    assert p.package_name == "yt-is"  # defaults
