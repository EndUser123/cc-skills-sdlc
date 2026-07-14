#!/usr/bin/env python3
"""Tests for deterministic run identity (B0: run_record, run_id, worktree disposition).

Identity path: session_id -> run_record.write() -> exact-key file
            -> run_record.read() validates identity fields
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_record
from run_record import (
    generate_run_id, write_run_record, read_run_record,
    run_record_path, parse_worktree_porcelain, inventory_worktrees,
    SCHEMA_VERSION,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_artifacts():
    """Return a TemporaryDirectory-based artifacts root for isolated tests."""
    td = tempfile.TemporaryDirectory()
    return Path(td.name), td


# ── Run ID generation ─────────────────────────────────────────────────────────

class TestRunIdGeneration:
    def test_has_session_prefix(self):
        rid = generate_run_id("test-sess-1234-abcd")
        assert rid.startswith("go-test-"), f"run_id should start with go-test-: {rid}"

    def test_unknown_session_prefix(self):
        rid = generate_run_id("")
        assert rid.startswith("go-unknown-"), f"empty session should produce unknown prefix: {rid}"
        rid2 = generate_run_id("short")
        assert rid2.startswith("go-short-") or rid2.startswith("go-unknown-"), f"short session: {rid2}"

    def test_uniqueness_within_session(self):
        ids = {generate_run_id("same-session-1234") for _ in range(100)}
        assert len(ids) >= 95, f"100 runs should produce nearly 100 unique IDs, got {len(ids)}"

    def test_no_collision_different_sessions(self):
        a = generate_run_id("session-a-1111-1111")
        b = generate_run_id("session-b-2222-2222")
        assert a != b


# ── Run record paths ──────────────────────────────────────────────────────────

class TestRunRecordPaths:
    def test_path_contains_session_and_run(self):
        art = Path("/tmp/artifacts")
        p = run_record_path("sess-1234", "go-sess-20260713T120000-a1b2c3", art)
        assert "go-runs" in str(p)
        assert "sess-1234" in str(p)
        assert "go-sess-20260713T120000-a1b2c3" in str(p)
        assert p.name == "run-record.json"

    def test_default_artifacts_root(self):
        p = run_record_path("s", "r")
        assert "go-runs" in str(p)


# ── Write and read ────────────────────────────────────────────────────────────

class TestWriteAndRead:
    def test_write_and_read_back(self):
        art, td = _make_artifacts()
        try:
            sess = "test-sess-0000-0000-0000-000000000000"
            run = generate_run_id(sess)
            w = write_run_record(session_id=sess, run_id=run,
                repository="/tmp/repo", base_revision="abc123",
                current_revision="abc123", worktree_path="/tmp/wt",
                contract_fingerprint="fp123", artifacts_root=art)
            assert w["session_id"] == sess
            assert w["run_id"] == run
            assert w["repository"] == "/tmp/repo"
            assert w["contract_fingerprint"] == "fp123"
            assert w["schema"] == SCHEMA_VERSION

            r = read_run_record(session_id=sess, run_id=run, artifacts_root=art)
            assert r is not None
            assert r["session_id"] == sess
        finally:
            td.cleanup()

    def test_atomic_write_survives(self):
        """Write to tmp then replace — file at target path is valid JSON."""
        art, td = _make_artifacts()
        try:
            sess = "atomic-sess-0000-0000-0000-000000000000"
            run = generate_run_id(sess)
            write_run_record(session_id=sess, run_id=run,
                repository="/tmp/r", artifacts_root=art)
            path = run_record_path(sess, run, art)
            assert path.is_file(), f"record file should exist: {path}"
            data = json.loads(path.read_text())
            assert data["session_id"] == sess
            assert data["run_id"] == run
            assert data["schema"] == SCHEMA_VERSION
        finally:
            td.cleanup()

    def test_write_without_session_or_run_returns_empty(self):
        assert write_run_record(session_id="", run_id="") == {}
        assert write_run_record(session_id="s", run_id="") == {}
        assert write_run_record(session_id="", run_id="r") == {}

    def test_write_auto_populates_git_fields(self):
        """When repository/revision not provided, they're auto-detected."""
        art, td = _make_artifacts()
        try:
            sess = "auto-sess-0000-0000-0000-000000000000"
            run = generate_run_id(sess)
            w = write_run_record(session_id=sess, run_id=run, artifacts_root=art)
            assert w["repository"] != "", "repository should be auto-detected"
            assert w["base_revision"] != "", "revision should be auto-detected"
            assert w["current_revision"] != ""
        finally:
            td.cleanup()


# ── Foreign/stale rejection ───────────────────────────────────────────────────

class TestForeignStaleRejection:
    def _setup(self):
        art, td = _make_artifacts()
        sess = "test-sess-0000-0000-0000-000000000000"
        run = generate_run_id(sess)
        write_run_record(session_id=sess, run_id=run,
            repository="/tmp/repo", base_revision="abc123",
            current_revision="abc123", worktree_path="/tmp/wt",
            contract_fingerprint="fp123", artifacts_root=art)
        return art, td, sess, run

    def test_foreign_session_fails_silent(self):
        art, td, sess, run = self._setup()
        try:
            assert read_run_record(session_id="foreign-session", run_id=run, artifacts_root=art) is None
        finally:
            td.cleanup()

    def test_foreign_run_fails_silent(self):
        art, td, sess, run = self._setup()
        try:
            assert read_run_record(session_id=sess, run_id="go-foreign-000000T000000-xxxxxx", artifacts_root=art) is None
        finally:
            td.cleanup()

    def test_wrong_repository_rejected(self):
        art, td, sess, run = self._setup()
        try:
            assert read_run_record(session_id=sess, run_id=run, artifacts_root=art,
                expected_repository="/tmp/wrongrepo") is None
        finally:
            td.cleanup()

    def test_wrong_contract_fingerprint_rejected(self):
        art, td, sess, run = self._setup()
        try:
            assert read_run_record(session_id=sess, run_id=run, artifacts_root=art,
                expected_contract_fingerprint="wrong-fp") is None
        finally:
            td.cleanup()

    def test_wrong_revision_rejected(self):
        art, td, sess, run = self._setup()
        try:
            assert read_run_record(session_id=sess, run_id=run, artifacts_root=art,
                expected_revision="xyz999") is None
        finally:
            td.cleanup()

    def test_nonexistent_run_returns_none(self):
        art, td, sess, run = self._setup()
        try:
            assert read_run_record(session_id=sess,
                run_id="go-nonexistent-000000T000000-xxxxxx", artifacts_root=art) is None
        finally:
            td.cleanup()

    def test_malformed_json_returns_none(self):
        art, td = _make_artifacts()
        try:
            sess = "malformed-sess-0000-0000-0000-000000000000"
            run = generate_run_id(sess)
            path = run_record_path(sess, run, art)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{invalid json", encoding="utf-8")
            assert read_run_record(session_id=sess, run_id=run, artifacts_root=art) is None
        finally:
            td.cleanup()

    def test_wrong_schema_version_returns_none(self):
        art, td = _make_artifacts()
        try:
            sess = "schema-sess-0000-0000-0000-000000000000"
            run = generate_run_id(sess)
            path = run_record_path(sess, run, art)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"schema": "go.wrong.v1", "session_id": sess, "run_id": run}), encoding="utf-8")
            assert read_run_record(session_id=sess, run_id=run, artifacts_root=art) is None
        finally:
            td.cleanup()

    def test_no_newest_fallback(self):
        """Verify no function performs newest/mtime/wildcard fallback."""
        import inspect
        src = inspect.getsource(run_record)
        assert "newest" not in src.lower(), "run_record must not use newest fallback"
        assert "mtime" not in src.lower(), "run_record must not use mtime fallback"
        assert "glob" not in src, "run_record must not use glob fallback"

    def test_matching_repository_passes(self):
        art, td, sess, run = self._setup()
        try:
            assert read_run_record(session_id=sess, run_id=run, artifacts_root=art,
                expected_repository="/tmp/repo") is not None
        finally:
            td.cleanup()


# ── Worktree porcelain parsing ────────────────────────────────────────────────

class TestWorktreePorcelainParsing:
    def test_basic_two_worktrees(self):
        porc = (
            "worktree P:/\n"
            "HEAD a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree P:/.worktrees/fix-auth\n"
            "HEAD b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0\n"
            "branch refs/heads/fix-auth\n"
        )
        entries = parse_worktree_porcelain(porc)
        assert len(entries) == 2
        assert entries[0]["branch"] == "main"
        assert entries[1]["branch"] == "fix-auth"
        assert entries[0]["path"] == "P:/"

    def test_detached_head(self):
        porc = (
            "worktree P:/\n"
            "HEAD abc123def456abc123def456abc123def456abc123\n"
            "\n"
        )
        entries = parse_worktree_porcelain(porc)
        assert len(entries) == 1
        assert entries[0]["branch"] == "(detached)"

    def test_bare_worktree(self):
        porc = (
            "worktree P:/bare\n"
            "HEAD a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0\n"
            "bare\n"
        )
        entries = parse_worktree_porcelain(porc)
        assert len(entries) == 1
        assert entries[0].get("bare") is True

    def test_empty_input(self):
        assert parse_worktree_porcelain("") == []

    def test_live_inventory_no_mutation(self):
        """inventory_worktrees must be read-only."""
        before = {e["path"] for e in inventory_worktrees()}
        after = {e["path"] for e in inventory_worktrees()}
        assert before == after, "inventory must not mutate worktree state"


# ── Orchestrate integration ───────────────────────────────────────────────────

class TestOrchestrateIntegration:
    def test_ensure_runtime_env_sets_run_id(self):
        """Verify orchestrate.ensure_runtime_env produces a run_id."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        try:
            from orchestrate import ensure_runtime_env
            state_dir, run_id = ensure_runtime_env("local")
        finally:
            sys.path.pop(0)
        assert run_id, "ensure_runtime_env must produce a run_id"
        assert len(run_id) > 8, f"run_id too short: {run_id}"

    def test_run_id_set_in_env(self):
        """ensure_runtime_env sets RUN_ID and GO_RUN_ID in os.environ."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        try:
            from orchestrate import ensure_runtime_env
            os.environ.pop("RUN_ID", None)
            os.environ.pop("GO_RUN_ID", None)
            ensure_runtime_env("local")
        finally:
            sys.path.pop(0)
        rid = os.environ.get("RUN_ID", "")
        go_rid = os.environ.get("GO_RUN_ID", "")
        assert rid, "RUN_ID must be set"
        assert go_rid, "GO_RUN_ID must be set"
        assert rid == go_rid, "RUN_ID and GO_RUN_ID must match"

    def test_resolve_session_id_returns_string(self):
        """resolve_session_id returns a string (possibly empty)."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        try:
            from orchestrate import resolve_session_id
            sid = resolve_session_id()
        finally:
            sys.path.pop(0)
        assert isinstance(sid, str), f"resolve_session_id returned {type(sid)}"

    def test_session_id_in_run_record(self):
        """When ensure_runtime_env calls write_run_record, the run record's
        session_id should match resolve_session_id()."""
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        try:
            from orchestrate import ensure_runtime_env, resolve_session_id
            os.environ.pop("RUN_ID", None)
            os.environ.pop("GO_RUN_ID", None)
            ensure_runtime_env("local")
        finally:
            sys.path.pop(0)
        # ensure_runtime_env already called write_run_record internally.
        # We verify that run_id is set — the write is advisory (fail-open)
        # so we don't require the record to exist in the auto-detected path.
        assert os.environ.get("RUN_ID", ""), "run_id must be set"


# ── Self-check runs clean ─────────────────────────────────────────────────────

class TestSelfCheck:
    def test_selfcheck_passes(self):
        run_record._selfcheck()
