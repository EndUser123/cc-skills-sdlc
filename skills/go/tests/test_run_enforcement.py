#!/usr/bin/env python3
"""Tests for current-run enforcement, workspace lease, pre-write, Stop-gate, lifecycle.

Identity path: session_id -> pointer -> run record -> validate -> lease
"""
from __future__ import annotations
import json, os, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_record
from run_record import (
    generate_run_id, generate_workspace_id, write_run_record, read_run_record,
    update_run_record_status, validate_current_run, pointer_path,
    acquire_workspace_lease, release_workspace_lease, validate_workspace_lease,
    check_pre_write, inventory_worktrees, current_branch,
    SCHEMA_VERSION, LEASE_SCHEMA_VERSION,
)

REPO = "/tmp/test-repo"
WT_PATH = "/tmp/test-wt"
BRANCH = "feature/test"


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

class TempArtifacts:
    def __init__(self):
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name)
    def cleanup(self):
        self._td.cleanup()


# ═════════════════════════════════════════════════════════════════════════════
# Workspace identity
# ═════════════════════════════════════════════════════════════════════════════

class TestWorkspaceIdentity:
    def test_generates_deterministic_id(self):
        w1 = generate_workspace_id("/tmp/repo", "feature/auth")
        w2 = generate_workspace_id("/tmp/repo", "feature/auth")
        assert w1 == w2, "same inputs must produce same ID"
        assert w1.startswith("ws-"), f"must start with ws-: {w1}"

    def test_different_path_produces_different_id(self):
        w1 = generate_workspace_id("/tmp/repo", "feature/a")
        w2 = generate_workspace_id("/tmp/repo", "feature/b")
        assert w1 != w2, "different branches must produce different IDs"

    def test_run_record_contains_workspace_id(self):
        art = TempArtifacts()
        try:
            sess = "ws-sess-0000-0000-0000-000000000000"
            run = generate_run_id(sess)
            w = write_run_record(session_id=sess, run_id=run, repository=REPO,
                base_revision="abc", worktree_path=WT_PATH,
                contract_fingerprint="fp123", workspace_id="ws-test-0001",
                artifacts_root=art.path)
            assert w["workspace_id"] == "ws-test-0001"
        finally:
            art.cleanup()


# ═════════════════════════════════════════════════════════════════════════════
# Run record lifecycle status
# ═════════════════════════════════════════════════════════════════════════════

class TestLifecycleStatus:
    def _make(self):
        art = TempArtifacts()
        sess = "lc-sess-0000-0000-0000-000000000000"
        run = generate_run_id(sess)
        write_run_record(session_id=sess, run_id=run, repository=REPO,
            base_revision="abc", worktree_path=WT_PATH,
            contract_fingerprint="fp123", lifecycle_status="active",
            workspace_id="ws-lc-test", artifacts_root=art.path)
        return art, sess, run

    def test_active_record_readable(self):
        art, sess, run = self._make()
        try:
            r = read_run_record(session_id=sess, run_id=run, artifacts_root=art.path,
                require_lifecycle_status="active")
            assert r is not None
        finally:
            art.cleanup()

    def test_inactive_record_blocked_by_require(self):
        art, sess, run = self._make()
        try:
            update_run_record_status(session_id=sess, run_id=run,
                lifecycle_status="impl_complete", artifacts_root=art.path)
            r = read_run_record(session_id=sess, run_id=run, artifacts_root=art.path,
                require_lifecycle_status="active")
            assert r is None, "should be None when not active"
            r2 = read_run_record(session_id=sess, run_id=run, artifacts_root=art.path,
                require_lifecycle_status="impl_complete")
            assert r2 is not None, "should match new status"
        finally:
            art.cleanup()

    def test_lifecycle_transitions(self):
        art, sess, run = self._make()
        try:
            for status in ("active", "impl_complete", "check_complete", "artifacts_finalized"):
                update_run_record_status(session_id=sess, run_id=run,
                    lifecycle_status=status, artifacts_root=art.path)
                r = read_run_record(session_id=sess, run_id=run, artifacts_root=art.path,
                    require_lifecycle_status=status)
                assert r is not None, f"should read back status={status}"
        finally:
            art.cleanup()

    def test_update_nonexistent_record_returns_none(self):
        r = update_run_record_status(session_id="no-sess", run_id="no-run",
            lifecycle_status="done")
        assert r is None, "nonexistent record should return None"


# ═════════════════════════════════════════════════════════════════════════════
# Validated current-run pointer
# ═════════════════════════════════════════════════════════════════════════════

class TestValidateCurrentRun:
    def _setup(self):
        art = TempArtifacts()
        sess = "vr-sess-0000-0000-0000-000000000000"
        run = generate_run_id(sess)
        write_run_record(session_id=sess, run_id=run, repository=REPO,
            base_revision="abc", worktree_path=WT_PATH,
            contract_fingerprint="fp123", workspace_id="ws-vr-test",
            artifacts_root=art.path)
        # Write session pointer
        ptr_path = pointer_path(session_id=sess, artifacts_root=art.path)
        ptr_path.parent.mkdir(parents=True, exist_ok=True)
        ptr_path.write_text(json.dumps({
            "run_id": run, "go_state_dir": str(art.path / "state"),
            "updated_at": "2026-07-13T12:00:00Z",
        }))
        return art, sess, run

    def test_valid_run_passes(self):
        art, sess, run = self._setup()
        try:
            r = validate_current_run(session_id=sess, run_id=run,
                artifacts_root=art.path,
                expected_repository=REPO)
            assert r["verified"] is True, f"should pass: {r}"
        finally:
            art.cleanup()

    def test_foreign_session_fails(self):
        art, sess, run = self._setup()
        try:
            r = validate_current_run(session_id="foreign-session", run_id=run,
                artifacts_root=art.path)
            assert r["verified"] is False
        finally:
            art.cleanup()

    def test_missing_pointer_fails(self):
        r = validate_current_run(session_id="no-session", run_id="no-run")
        assert r["verified"] is False

    def test_wrong_repository_fails(self):
        art, sess, run = self._setup()
        try:
            r = validate_current_run(session_id=sess, run_id=run,
                artifacts_root=art.path, expected_repository="/tmp/wrong-repo")
            assert r["verified"] is False
            assert r.get("reason_code") in ("REPOSITORY_MISMATCH",)
        finally:
            art.cleanup()

    def test_lifecycle_not_active_fails(self):
        art, sess, run = self._setup()
        try:
            update_run_record_status(session_id=sess, run_id=run,
                lifecycle_status="completed", artifacts_root=art.path)
            r = validate_current_run(session_id=sess, run_id=run,
                artifacts_root=art.path)
            assert r["verified"] is False
            assert r.get("reason_code") == "LIFECYCLE_NOT_ACTIVE"
        finally:
            art.cleanup()


# ═════════════════════════════════════════════════════════════════════════════
# Atomic workspace lease
# ═════════════════════════════════════════════════════════════════════════════

class TestWorkspaceLease:
    def test_acquire_and_release(self):
        ws = "ws-test-acquire"
        lr = Path(tempfile.mkdtemp())
        try:
            a = acquire_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", repository=REPO, leases_root=lr)
            assert a["acquired"] is True
            v = validate_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", leases_root=lr)
            assert v["valid"] is True

            rel = release_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", leases_root=lr)
            assert rel["released"] is True

            v2 = validate_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", leases_root=lr)
            assert v2["valid"] is False
        finally:
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_exclusive_acquire(self):
        ws = "ws-test-exclusive"
        lr = Path(tempfile.mkdtemp())
        try:
            a1 = acquire_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", repository=REPO, leases_root=lr)
            assert a1["acquired"] is True

            a2 = acquire_workspace_lease(workspace_id=ws, session_id="s2",
                run_id="r2", repository=REPO, leases_root=lr)
            assert a2["acquired"] is False
            assert a2["reason_code"] == "LEASE_ALREADY_HELD"
        finally:
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_foreign_owner_cannot_validate(self):
        ws = "ws-test-foreign"
        lr = Path(tempfile.mkdtemp())
        try:
            acquire_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", repository=REPO, leases_root=lr)
            v = validate_workspace_lease(workspace_id=ws, session_id="s2",
                run_id="r2", leases_root=lr)
            assert v["valid"] is False
            assert v["reason_code"] == "LEASE_FOREIGN_OWNER"
        finally:
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_foreign_owner_cannot_release(self):
        ws = "ws-test-foreign-rel"
        lr = Path(tempfile.mkdtemp())
        try:
            acquire_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", repository=REPO, leases_root=lr)
            rel = release_workspace_lease(workspace_id=ws, session_id="s2",
                run_id="r2", leases_root=lr)
            assert rel["released"] is False
            assert rel["reason_code"] == "LEASE_FOREIGN_OWNER"
        finally:
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_lease_reacquire_after_release(self):
        ws = "ws-test-reacquire"
        lr = Path(tempfile.mkdtemp())
        try:
            a1 = acquire_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", repository=REPO, leases_root=lr)
            assert a1["acquired"] is True
            release_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", leases_root=lr)

            a2 = acquire_workspace_lease(workspace_id=ws, session_id="s2",
                run_id="r2", repository=REPO, leases_root=lr)
            assert a2["acquired"] is True, "should reacquire after release"
        finally:
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_concurrent_acquire_race(self):
        """Two threads race for the same lease. Only one should succeed."""
        ws = "ws-test-concurrent"
        lr = Path(tempfile.mkdtemp())
        results = []
        def _try_acquire(label):
            r = acquire_workspace_lease(workspace_id=ws, session_id=label,
                run_id=f"r-{label}", repository=REPO, leases_root=lr)
            results.append((label, r["acquired"]))

        t1 = threading.Thread(target=_try_acquire, args=("s1",))
        t2 = threading.Thread(target=_try_acquire, args=("s2",))
        t1.start(); t2.start()
        t1.join(); t2.join()

        acquired = sum(1 for _, ok in results if ok)
        assert acquired == 1, f"exactly 1 should acquire, got {acquired}: {results}"
        import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_lease_record_has_required_fields(self):
        ws = "ws-test-fields"
        lr = Path(tempfile.mkdtemp())
        try:
            a = acquire_workspace_lease(workspace_id=ws, session_id="s1",
                run_id="r1", repository=REPO, worktree_path=WT_PATH,
                leases_root=lr)
            assert a["acquired"] is True
            lease = a["lease"]
            assert lease["schema"] == LEASE_SCHEMA_VERSION
            assert lease["workspace_id"] == ws
            assert lease["session_id"] == "s1"
            assert lease["run_id"] == "r1"
            assert lease["lifecycle_status"] == "active"
        finally:
            import shutil; shutil.rmtree(lr, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
# Pre-write gate check
# ═════════════════════════════════════════════════════════════════════════════

class TestPreWriteCheck:
    def _setup(self):
        art = TempArtifacts()
        lr = Path(tempfile.mkdtemp())
        sess = "pw-sess-0000-0000-0000-000000000000"
        run = generate_run_id(sess)
        ws_id = generate_workspace_id(WT_PATH, "test-branch")
        write_run_record(session_id=sess, run_id=run, repository=REPO,
            base_revision="abc", worktree_path=WT_PATH,
            contract_fingerprint="fp123", workspace_id=ws_id,
            artifacts_root=art.path)
        # Pointer
        ptr_path = pointer_path(session_id=sess, artifacts_root=art.path)
        ptr_path.parent.mkdir(parents=True, exist_ok=True)
        ptr_path.write_text(json.dumps({
            "run_id": run, "go_state_dir": str(art.path / "state"),
            "updated_at": "2026-07-13T12:00:00Z",
        }))
        # Acquire lease
        acquire_workspace_lease(workspace_id=ws_id, session_id=sess,
            run_id=run, repository=REPO, leases_root=lr)
        return art, lr, sess, run, ws_id

    def test_valid_pre_write_passes(self):
        art, lr, sess, run, ws_id = self._setup()
        try:
            r = check_pre_write(session_id=sess, run_id=run,
                workspace_id=ws_id, artifacts_root=art.path,
                leases_root=lr, repository=REPO, worktree_path=WT_PATH,
                contract_fingerprint="fp123")
            assert r["allow"] is True, f"should allow: {r}"
        finally:
            art.cleanup()
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_foreign_session_blocked(self):
        art, lr, sess, run, ws_id = self._setup()
        try:
            r = check_pre_write(session_id="foreign-sess", run_id=run,
                workspace_id=ws_id, artifacts_root=art.path,
                leases_root=lr)
            assert r["allow"] is False
        finally:
            art.cleanup()
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_wrong_contract_fingerprint_blocked(self):
        art, lr, sess, run, ws_id = self._setup()
        try:
            r = check_pre_write(session_id=sess, run_id=run,
                workspace_id=ws_id, artifacts_root=art.path,
                leases_root=lr, contract_fingerprint="wrong-fp")
            assert r["allow"] is False
        finally:
            art.cleanup()
            import shutil; shutil.rmtree(lr, ignore_errors=True)

    def test_no_lease_blocked_when_workspace_expected(self):
        art, lr, sess, run, ws_id = self._setup()
        # Release the lease
        release_workspace_lease(workspace_id=ws_id, session_id=sess,
            run_id=run, leases_root=lr)
        try:
            r = check_pre_write(session_id=sess, run_id=run,
                workspace_id=ws_id, artifacts_root=art.path,
                leases_root=lr)
            assert r["allow"] is False
        finally:
            art.cleanup()
            import shutil; shutil.rmtree(lr, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
# Finalize-run (lifecycle)
# ═════════════════════════════════════════════════════════════════════════════

class TestFinalizeRun:
    def test_finalize_updates_status_and_releases_lease(self):
        art = TempArtifacts()
        lr = Path(tempfile.mkdtemp())
        try:
            sess = "fr-sess-0000-0000-0000-000000000000"
            run = generate_run_id(sess)
            ws_id = generate_workspace_id("/tmp/wt", "b")
            write_run_record(session_id=sess, run_id=run, repository=REPO,
                base_revision="abc", worktree_path="/tmp/wt",
                contract_fingerprint="fp", workspace_id=ws_id,
                artifacts_root=art.path)
            acquire_workspace_lease(workspace_id=ws_id, session_id=sess,
                run_id=run, repository=REPO, leases_root=lr)

            # Import and call finalize_run
            sys.path.insert(0, str(art.path.parent))
            from orchestrate import finalize_run
            state_dir = art.path / "state"
            state_dir.mkdir()
            result = finalize_run(state_dir, run, sess, ws_id, art.path, lr)

            # Verify status updated
            rec = read_run_record(session_id=sess, run_id=run,
                artifacts_root=art.path)
            assert rec is not None
            assert rec["lifecycle_status"] == "artifacts_finalized"

            # Verify lease released
            vl = validate_workspace_lease(workspace_id=ws_id, session_id=sess,
                run_id=run, leases_root=lr)
            assert vl["valid"] is False
        finally:
            art.cleanup()
            import shutil; shutil.rmtree(lr, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
# Worktree inventory (regression: no mutation)
# ═════════════════════════════════════════════════════════════════════════════

class TestWorktreeInventory:
    def test_inventory_read_only(self):
        before = {e.get("path") for e in inventory_worktrees()}
        after = {e.get("path") for e in inventory_worktrees()}
        assert before == after

    def test_running_on_worktree(self):
        """Verify we're in a git repo and can identify it."""
        wt = run_record.current_worktree_path()
        assert wt != "", "should resolve a worktree path"
        rev = run_record.git_revision()
        assert len(rev) >= 7, f"should resolve a revision: {rev}"
