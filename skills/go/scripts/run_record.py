#!/usr/bin/env python3
"""Deterministic run-identity record, workspace lease, and worktree helpers (B0).

Identity path: session_id -> write_run_record() -> exact-key file -> read_run_record()

Workspace lease: acquire_workspace_lease() — atomic mkdir — holds lease while dir exists

New functions not found in existing go/scripts/ (confirmed by grep before creation):
  generate_workspace_id, current_branch, update_run_record_status,
  validate_current_run, pointer_path, lease_path, lease_record_path,
  acquire_workspace_lease, release_workspace_lease, validate_workspace_lease,
  check_pre_write

Existing write_dispatch_result.update_run_file() is for dispatch status — different schema.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "go.run-record.v1"
RUN_RECORD_FILENAME = "run-record.json"
LEASE_FILENAME = "workspace-lease.json"
ARTIFACTS_ROOT_ENV = "GO_ARTIFACTS_ROOT"
ARTIFACTS_ROOT_DEFAULT = Path("P:/.claude/.artifacts")
LEASES_ROOT_DEFAULT = Path("P:/.claude/.worktrees/leases")

def generate_run_id(session_id: str) -> str:
    prefix = session_id[:8] if session_id and len(session_id) >= 8 else "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    raw = f"{time.perf_counter_ns()}{os.getpid()}".encode()
    suffix = hashlib.md5(raw).hexdigest()[:6]
    return f"go-{prefix}-{ts}-{suffix}"

def generate_workspace_id(worktree_path: str, branch: str = "") -> str:
    raw = f"{worktree_path}:::{branch}".encode()
    return f"ws-{hashlib.sha256(raw).hexdigest()[:12]}"

def repository_root() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except: return ""

def git_revision() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except: return ""

def current_worktree_path() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else os.getcwd()
    except: return os.getcwd()

def current_branch() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10)
        v = r.stdout.strip()
        return v if v and v != "HEAD" else ""
    except: return ""

def _artifacts_root(ar=None):
    if ar is not None: return Path(ar) if isinstance(ar, (str, Path)) else ar
    return Path(os.environ.get(ARTIFACTS_ROOT_ENV, str(ARTIFACTS_ROOT_DEFAULT)))

def _leases_root(lr=None):
    if lr is not None: return Path(lr) if isinstance(lr, (str, Path)) else lr
    return LEASES_ROOT_DEFAULT

def run_record_path(session_id="", run_id="", artifacts_root=None):
    return _artifacts_root(artifacts_root) / "go-runs" / session_id / run_id / RUN_RECORD_FILENAME

def write_run_record(session_id="", run_id="", repository="", base_revision="",
                     current_revision="", worktree_path="", contract_fingerprint="",
                     lifecycle_status="active", workspace_id="", artifacts_root=None):
    if not session_id or not run_id: return {}
    if not repository: repository = repository_root()
    if not current_revision: current_revision = git_revision()
    if not base_revision: base_revision = current_revision
    if not worktree_path: worktree_path = current_worktree_path()
    if not workspace_id:
        workspace_id = generate_workspace_id(worktree_path, current_branch())
    record = {"schema": SCHEMA_VERSION, "session_id": session_id, "run_id": run_id,
        "repository": repository, "base_revision": base_revision,
        "current_revision": current_revision, "worktree_path": worktree_path,
        "contract_fingerprint": contract_fingerprint, "workspace_id": workspace_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lifecycle_status": lifecycle_status}
    p = run_record_path(session_id, run_id, artifacts_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix(p.suffix + ".tmp")
    t.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    t.replace(p)
    return record

def read_run_record(session_id="", run_id="", artifacts_root=None,
                    expected_repository="", expected_revision="",
                    expected_contract_fingerprint="", expected_workspace_id="",
                    require_lifecycle_status=""):
    p = run_record_path(session_id, run_id, artifacts_root)
    if not p.is_file(): return None
    try: r = json.loads(p.read_text(encoding="utf-8"))
    except: return None
    if not isinstance(r, dict): return None
    if r.get("schema") != SCHEMA_VERSION: return None
    if r.get("session_id") != session_id: return None
    if r.get("run_id") != run_id: return None
    if expected_repository and r.get("repository") != expected_repository: return None
    if expected_revision and r.get("base_revision") != expected_revision: return None
    if expected_contract_fingerprint and r.get("contract_fingerprint") != expected_contract_fingerprint: return None
    if expected_workspace_id and r.get("workspace_id") != expected_workspace_id: return None
    if require_lifecycle_status and r.get("lifecycle_status") != require_lifecycle_status: return None
    return r

def update_run_record_status(session_id="", run_id="", lifecycle_status="", artifacts_root=None):
    r = read_run_record(session_id=session_id, run_id=run_id, artifacts_root=artifacts_root)
    if r is None: return None
    r["lifecycle_status"] = lifecycle_status
    r["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    p = run_record_path(session_id, run_id, artifacts_root)
    t = p.with_suffix(p.suffix + ".tmp")
    t.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
    t.replace(p)
    return r

def pointer_path(session_id="", artifacts_root=None):
    return _artifacts_root(artifacts_root) / "go-sessions" / f"{session_id}.json"

def validate_current_run(session_id="", run_id="", artifacts_root=None,
                         expected_repository="", expected_worktree="",
                         expected_contract_fingerprint="", expected_workspace_id=""):
    if not session_id: return {"verified": False, "reason_code": "SESSION_ID_MISSING"}
    if not run_id: return {"verified": False, "reason_code": "RUN_ID_MISSING"}
    pp = pointer_path(session_id, artifacts_root)
    if not pp.is_file(): return {"verified": False, "reason_code": "POINTER_MISSING"}
    try: ptr = json.loads(pp.read_text(encoding="utf-8"))
    except: return {"verified": False, "reason_code": "POINTER_MALFORMED"}
    if not isinstance(ptr, dict): return {"verified": False, "reason_code": "POINTER_MALFORMED"}
    if ptr.get("run_id") != run_id:
        return {"verified": False, "reason_code": "POINTER_RUN_ID_MISMATCH"}
    rec = read_run_record(session_id=session_id, run_id=run_id, artifacts_root=artifacts_root,
        expected_repository=expected_repository,
        expected_contract_fingerprint=expected_contract_fingerprint,
        expected_workspace_id=expected_workspace_id,
        require_lifecycle_status="active")
    if rec is None:
        d = read_run_record(session_id=session_id, run_id=run_id, artifacts_root=artifacts_root)
        if d is None: return {"verified": False, "reason_code": "RUN_RECORD_MISSING_OR_MALFORMED"}
        if d.get("session_id") != session_id: return {"verified": False, "reason_code": "RUN_RECORD_SESSION_MISMATCH"}
        if d.get("run_id") != run_id: return {"verified": False, "reason_code": "RUN_RECORD_RUN_MISMATCH"}
        if expected_repository and d.get("repository") != expected_repository: return {"verified": False, "reason_code": "REPOSITORY_MISMATCH"}
        if expected_worktree and d.get("worktree_path") != expected_worktree: return {"verified": False, "reason_code": "WORKTREE_MISMATCH"}
        if expected_contract_fingerprint and d.get("contract_fingerprint") != expected_contract_fingerprint: return {"verified": False, "reason_code": "CONTRACT_MISMATCH"}
        return {"verified": False, "reason_code": "LIFECYCLE_NOT_ACTIVE", "status": d.get("lifecycle_status","")}
    if expected_worktree and rec.get("worktree_path") != expected_worktree:
        return {"verified": False, "reason_code": "WORKTREE_MISMATCH"}
    return {"verified": True, "reason_code": "OK", "record": rec}

LEASE_SCHEMA_VERSION = "go.workspace-lease.v1"

def lease_path(workspace_id="", leases_root=None):
    return _leases_root(leases_root) / workspace_id

def lease_record_path(workspace_id="", leases_root=None):
    return lease_path(workspace_id, leases_root) / LEASE_FILENAME

def acquire_workspace_lease(workspace_id="", session_id="", run_id="",
                            repository="", worktree_path="", leases_root=None):
    if not workspace_id or not session_id or not run_id:
        return {"acquired": False, "reason_code": "LEASE_IDENTITY_MISSING"}
    ld = lease_path(workspace_id, leases_root)
    lf = lease_record_path(workspace_id, leases_root)
    try:
        ld.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        try: ex = json.loads(lf.read_text(encoding="utf-8")) if lf.is_file() else {}
        except: ex = {}
        return {"acquired": False, "reason_code": "LEASE_ALREADY_HELD",
                "current_lease": ex if isinstance(ex, dict) else {}}
    except (OSError, PermissionError) as e:
        return {"acquired": False, "reason_code": "LEASE_CREATE_FAILED", "error": str(e)}
    if not repository: repository = repository_root()
    if not worktree_path: worktree_path = current_worktree_path()
    lr = {"schema": LEASE_SCHEMA_VERSION,
        "lease_id": f"lease-{workspace_id[:12]}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}",
        "workspace_id": workspace_id, "session_id": session_id, "run_id": run_id,
        "repository": repository, "worktree_path": worktree_path,
        "acquired_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lifecycle_status": "active"}
    lf.write_text(json.dumps(lr, indent=2) + "\n", encoding="utf-8")
    return {"acquired": True, "lease": lr}

def release_workspace_lease(workspace_id="", session_id="", run_id="", leases_root=None):
    if not workspace_id: return {"released": False, "reason_code": "WORKSPACE_ID_MISSING"}
    ld = lease_path(workspace_id, leases_root)
    lf = lease_record_path(workspace_id, leases_root)
    if not ld.is_dir(): return {"released": False, "reason_code": "LEASE_NOT_HELD"}
    try: cur = json.loads(lf.read_text(encoding="utf-8")) if lf.is_file() else {}
    except: cur = {}
    if not isinstance(cur, dict): cur = {}
    if session_id and cur.get("session_id") and cur["session_id"] != session_id:
        return {"released": False, "reason_code": "LEASE_FOREIGN_OWNER"}
    if run_id and cur.get("run_id") and cur["run_id"] != run_id:
        return {"released": False, "reason_code": "LEASE_WRONG_RUN"}
    try:
        if lf.exists(): lf.unlink()
    except: pass
    try: os.rmdir(str(ld))
    except: pass
    return {"released": True} if not ld.is_dir() else {"released": False, "reason_code": "LEASE_DIRECTORY_REMAINS"}

def validate_workspace_lease(workspace_id="", session_id="", run_id="", leases_root=None):
    if not workspace_id: return {"valid": False, "reason_code": "WORKSPACE_ID_MISSING"}
    ld = lease_path(workspace_id, leases_root)
    lf = lease_record_path(workspace_id, leases_root)
    if not ld.is_dir(): return {"valid": False, "reason_code": "LEASE_NOT_HELD"}
    try: cur = json.loads(lf.read_text(encoding="utf-8")) if lf.is_file() else {}
    except: return {"valid": False, "reason_code": "LEASE_MALFORMED"}
    if not isinstance(cur, dict): return {"valid": False, "reason_code": "LEASE_MALFORMED"}
    if session_id and cur.get("session_id") and cur["session_id"] != session_id:
        return {"valid": False, "reason_code": "LEASE_FOREIGN_OWNER"}
    if run_id and cur.get("run_id") and cur["run_id"] != run_id:
        return {"valid": False, "reason_code": "LEASE_WRONG_RUN"}
    return {"valid": True, "lease": cur}

def check_pre_write(session_id="", run_id="", workspace_id="",
                    artifacts_root=None, leases_root=None,
                    repository="", worktree_path="", contract_fingerprint=""):
    rc = validate_current_run(session_id=session_id, run_id=run_id,
        artifacts_root=artifacts_root, expected_repository=repository,
        expected_worktree=worktree_path,
        expected_contract_fingerprint=contract_fingerprint,
        expected_workspace_id=workspace_id)
    if not rc.get("verified"):
        return {"allow": False, "reason_code": rc.get("reason_code", "RUN_FAILED")}
    if workspace_id:
        lc = validate_workspace_lease(workspace_id=workspace_id, session_id=session_id,
            run_id=run_id, leases_root=leases_root)
        if not lc.get("valid"):
            return {"allow": False, "reason_code": lc.get("reason_code", "LEASE_FAILED")}
    return {"allow": True}

def parse_worktree_porcelain(output: str) -> list[dict]:
    entries, cur = [], {}
    for line in output.splitlines():
        line = line.strip()
        if not line:
            if cur: entries.append(cur); cur = {}
            continue
        if line.startswith("worktree "): cur["path"] = line[9:]
        elif line.startswith("HEAD "): cur["head"] = line[5:]
        elif line.startswith("branch "): cur["branch"] = line[7:].replace("refs/heads/", "")
        elif line.startswith("bare"): cur["bare"] = True
    if cur: entries.append(cur)
    for e in entries:
        e.setdefault("branch", "(detached)"); e["clean"] = True; e["untracked"] = False
    return entries

def inventory_worktrees() -> list[dict]:
    try:
        r = subprocess.run(["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=15)
        return parse_worktree_porcelain(r.stdout) if r.returncode == 0 else []
    except: return []

def _selfcheck() -> None:
    from tempfile import TemporaryDirectory, mkdtemp
    rid = generate_run_id("test-session-1234-abcd")
    assert rid.startswith("go-test-")
    assert generate_run_id("test-session-1234-abcd") != rid
    wid = generate_workspace_id("/tmp/repo", "fix-auth")
    assert wid.startswith("ws-")
    with TemporaryDirectory() as td:
        a = Path(td); s = "test-selfcheck-0000-0000-0000"; r = generate_run_id(s)
        w = write_run_record(session_id=s, run_id=r, repository="/tmp/r",
            base_revision="a", current_revision="a", worktree_path="/tmp/w",
            contract_fingerprint="f", artifacts_root=a)
        assert w["session_id"] == s and w["run_id"] == r
        assert read_run_record(session_id=s, run_id=r, artifacts_root=a) is not None
        assert read_run_record(session_id="x", run_id=r, artifacts_root=a) is None
        assert read_run_record(session_id=s, run_id="go-x-0-a", artifacts_root=a) is None
        assert read_run_record(session_id=s, run_id=r, artifacts_root=a, expected_repository="/tmp/x") is None
        assert read_run_record(session_id=s, run_id=r, artifacts_root=a, expected_contract_fingerprint="x") is None
        assert read_run_record(session_id=s, run_id=r, artifacts_root=a, require_lifecycle_status="done") is None
        u = update_run_record_status(session_id=s, run_id=r, lifecycle_status="impl_c", artifacts_root=a)
        assert u is not None and u["lifecycle_status"] == "impl_c"
    ws = "ws-sc"; lr = Path(mkdtemp())
    try:
        a1 = acquire_workspace_lease(workspace_id=ws, session_id="s1", run_id="r1", leases_root=lr)
        assert a1["acquired"] is True
        assert acquire_workspace_lease(workspace_id=ws, session_id="s2", run_id="r2", leases_root=lr)["acquired"] is False
        assert validate_workspace_lease(workspace_id=ws, session_id="s1", run_id="r1", leases_root=lr)["valid"] is True
        assert validate_workspace_lease(workspace_id=ws, session_id="s2", run_id="r2", leases_root=lr)["valid"] is False
        assert release_workspace_lease(workspace_id=ws, session_id="s2", run_id="r2", leases_root=lr)["released"] is False
        assert release_workspace_lease(workspace_id=ws, session_id="s1", run_id="r1", leases_root=lr)["released"] is True
        assert validate_workspace_lease(workspace_id=ws, session_id="s1", run_id="r1", leases_root=lr)["valid"] is False
    finally:
        import shutil; shutil.rmtree(lr, ignore_errors=True)
    print("run_record self-check OK")

if __name__ == "__main__":
    _selfcheck()
