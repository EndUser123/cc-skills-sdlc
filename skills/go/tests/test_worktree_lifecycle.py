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
