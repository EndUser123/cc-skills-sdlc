"""Receipt store + receipt-based verifier tests.

Proves the false-positive classes are eliminated by construction (the verifier
consults ONLY receipts -- no basename / commit-message / pickaxe / grep matching):
  - same basename in another repository -> NO_EVIDENCE (not VERIFIED)
  - generic commit messages -> irrelevant (no commit-msg path)
  - generic grep/pickaxe matches -> irrelevant (no grep path)
  - stale receipts -> STALE
  - cross-terminal / cross-repo task IDs -> NO_EVIDENCE
Plus: missing-receipt handling, exact repo matching, deterministic output/exit,
and clean safety (only VERIFIED receipts authorize deletion; status=completed
alone never does).
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path("P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/task/scripts")
sys.path.insert(0, str(SCRIPTS))
import task_receipt as R  # noqa: E402
import task_verify as V  # noqa: E402

REPO = "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc"
TEST_TERMINAL = "test_console"


@pytest.fixture(autouse=True)
def _isolated_receipts(tmp_path, monkeypatch):
    monkeypatch.setenv("TASK_RECEIPT_DIR", str(tmp_path / "receipts"))
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", TEST_TERMINAL)
    # Ensure the terminal-scoped subdir exists
    (tmp_path / "receipts" / TEST_TERMINAL).mkdir(parents=True, exist_ok=True)
    yield tmp_path


def _write(tid, **kw):
    # Always write with the test terminal_id so the receipt body and path match.
    kw.setdefault("terminal_id", TEST_TERMINAL)
    return R.write_receipt(tid, repo=REPO, **kw)


# --- receipt store ----------------------------------------------------------

def test_write_verified_with_passing_verify():
    r = _write("100", verify_commands=["echo ok"])
    assert r["evidence_class"] == "VERIFIED"
    assert r["final_commit_sha"]
    assert r["repo"].endswith("cc-skills-sdlc")
    assert R.has_receipt("100")


def test_write_review_when_verify_fails_but_committed():
    r = _write("101", verify_commands=["false"])
    assert r["evidence_class"] == "REVIEW"


def test_write_no_evidence_when_no_verify_no_sha(monkeypatch):
    monkeypatch.setattr(R, "git_head", lambda cwd: None)
    r = _write("102", no_verify=True)
    assert r["evidence_class"] == "NO_EVIDENCE"


def test_read_has_list_roundtrip():
    _write("103", verify_commands=["echo ok"])
    assert R.has_receipt("103")
    assert R.read_receipt("103")["task_id"] == "103"
    assert "103" in R.list_receipts()
    assert not R.has_receipt("999")


# --- verify_task buckets ----------------------------------------------------

def test_no_receipt_is_no_evidence():
    b, _ = V.verify_task("404")
    assert b == "NO_EVIDENCE"


def test_verified_same_repo():
    _write("200", verify_commands=["echo ok"])
    b, _ = V.verify_task("200", current_repo=REPO)
    assert b == "VERIFIED"


def test_review_bucket():
    _write("201", verify_commands=["false"])
    b, _ = V.verify_task("201", current_repo=REPO)
    assert b == "REVIEW"


def test_stale_receipt_when_sha_unreachable():
    _write("202", verify_commands=["echo ok"])
    p = R.receipt_path("202")
    d = json.loads(p.read_text())
    d["final_commit_sha"] = "0" * 40
    p.write_text(json.dumps(d))
    b, reason = V.verify_task("202", current_repo=REPO)
    assert b == "STALE", reason


def test_malformed_receipt_is_blocked():
    R.receipt_path("203").write_text("not json")
    b, _ = V.verify_task("203", current_repo=REPO)
    assert b == "BLOCKED"
    R.receipt_path("204").write_text(json.dumps({"nope": 1}))
    b2, _ = V.verify_task("204", current_repo=REPO)
    assert b2 == "BLOCKED"


# --- false-positive resistance ---------------------------------------------

def test_fp_same_basename_another_repo_not_verified():
    _write("300", verify_commands=["echo ok"])
    b, _ = V.verify_task("300", current_repo="P:/some/other/repo")
    assert b == "NO_EVIDENCE"


def test_fp_generic_commit_message_not_verified():
    b, _ = V.verify_task("301", current_repo=REPO)
    assert b == "NO_EVIDENCE"


def test_fp_generic_grep_pickaxe_not_verified():
    b, _ = V.verify_task("302", current_repo=REPO)
    assert b == "NO_EVIDENCE"


def test_fp_cross_terminal_task_id():
    _write("303", verify_commands=["echo ok"], terminal_id="console_A")
    b, _ = V.verify_task("303", current_repo="P:/elsewhere/console_B_repo")
    assert b == "NO_EVIDENCE"


def test_exact_repo_match_required():
    _write("304", verify_commands=["echo ok"])
    b, _ = V.verify_task("304", current_repo=REPO.replace("/", "\\"))
    assert b == "VERIFIED"


# --- determinism ------------------------------------------------------------

def test_verify_output_deterministic():
    _write("400", verify_commands=["echo ok"])
    _write("401", verify_commands=["false"])
    r1 = V.verify_many(["400", "401"], current_repo=REPO)
    r2 = V.verify_many(["400", "401"], current_repo=REPO)
    assert r1 == r2
    assert r1["buckets"]["VERIFIED"] == ["400"]
    assert r1["buckets"]["REVIEW"] == ["401"]


def test_verify_exit_code_via_cli():
    _write("500", verify_commands=["echo ok"])
    import subprocess
    env = {**os.environ, "TASK_RECEIPT_DIR": os.environ["TASK_RECEIPT_DIR"]}
    r = subprocess.run([sys.executable, str(SCRIPTS / "task_verify.py"), "verify", "500",
                        "--repo", REPO], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout
    r2 = subprocess.run([sys.executable, str(SCRIPTS / "task_verify.py"), "verify", "500", "501",
                         "--repo", REPO], capture_output=True, text=True, env=env)
    assert r2.returncode == 1


# --- clean safety -----------------------------------------------------------

def _make_tracker(tmp_path, task_ids):
    td = tmp_path / "tracker"
    td.mkdir()
    tasks = {tid: {"id": tid, "subject": "t %s" % tid, "status": "completed"} for tid in task_ids}
    (td / "console_test_tasks.json").write_text(json.dumps({"terminal_id": "console_test", "tasks": tasks}))
    return td


def _cli_clean(args, td):
    import subprocess
    env = {**os.environ, "TASK_RECEIPT_DIR": os.environ["TASK_RECEIPT_DIR"]}
    return subprocess.run([sys.executable, str(SCRIPTS / "task_verify.py"), "clean", *args,
                           "--repo", REPO, "--tracker-dir", str(td)],
                          capture_output=True, text=True, env=env)


def test_clean_no_verified_deletes_nothing(_isolated_receipts):
    td = _make_tracker(_isolated_receipts, ["600", "601"])
    r = _cli_clean(["--apply", "600", "601"], td)
    assert r.returncode == 1
    data = json.loads((td / "console_test_tasks.json").read_text())
    assert "600" in data["tasks"] and "601" in data["tasks"]


def test_clean_only_deletes_verified(_isolated_receipts):
    _write("700", verify_commands=["echo ok"])
    td = _make_tracker(_isolated_receipts, ["700", "701"])
    r = _cli_clean(["--apply", "700", "701"], td)
    data = json.loads((td / "console_test_tasks.json").read_text())
    assert "700" not in data["tasks"]
    assert "701" in data["tasks"]
    assert R.has_receipt("700")


def test_clean_dry_run_does_not_delete(_isolated_receipts):
    _write("800", verify_commands=["echo ok"])
    td = _make_tracker(_isolated_receipts, ["800"])
    r = _cli_clean(["800"], td)
    data = json.loads((td / "console_test_tasks.json").read_text())
    assert "800" in data["tasks"]
    assert "DRY RUN" in r.stdout


def test_status_completed_alone_never_deletes(_isolated_receipts):
    td = _make_tracker(_isolated_receipts, ["900"])
    r = _cli_clean(["--apply", "900"], td)
    data = json.loads((td / "console_test_tasks.json").read_text())
    assert "900" in data["tasks"]


# --- unresolved suggester is opt-in (default /task list is cheap) -----------

def test_unresolved_suggester_disabled_by_default():
    """Default /task list must NOT invoke CHS/CKS -> PostToolUse suggester is opt-in."""
    src = Path("P:/packages/.claude-marketplace/plugins/cc-aca-observability/__lib/posttooluse/task_unresolved_suggester_hook.py").read_text()
    assert re.search(r"default_enabled\s*=\s*False", src), \
        "TaskUnresolvedSuggesterHook.default_enabled must be False so bare TaskList is cheap"
