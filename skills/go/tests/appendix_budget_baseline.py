"""Budget-baseline tests: materialized content must NOT consume attacker budget."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _git_repo(dst: Path, files: dict[str, str] | None = None) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for c in [("init", "-q"), ("config", "user.email", "t"), ("config", "user.name", "t")]:
        subprocess.run(["git", "-C", str(dst), *c], check=True)
    if files:
        for name, content in files.items():
            (dst / name).parent.mkdir(parents=True, exist_ok=True)
            (dst / name).write_text(content)
    else:
        (dst / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "-C", str(dst), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(dst), "commit", "-qm", "base"], check=True)
    return dst


def test_large_materialized_diff_consumes_zero_attacker_budget(tmp_path):
    """A large materialized task diff must consume zero attacker-write budget
    when measured by measure_attacker_writes against the materialization baseline."""
    import falsification_gate as fg

    repo = _git_repo(tmp_path / "repo")
    head = subprocess.run(["git","-C",str(repo),"rev-parse","HEAD"],
                          capture_output=True, text=True).stdout.strip()

    # Make a large unstaged change (many files)
    for i in range(10):
        (repo / f"big_file_{i}.py").write_text(f"# content {i}\n" * 100)
    (repo / "target.txt").write_text("EDITED_BY_TASK\n")

    auth_digest = fg.compute_authoritative_tree_digest(repo)

    aw = tmp_path / "attack"
    branch = "t-large-mat"
    subprocess.run(["git","-C",str(repo),"worktree","add","-b",branch,str(aw),head],
                   check=True)

    mat = fg.materialize_authoritative_state(repo, aw, head, [])
    assert mat["digest_match"], f"materialization failed: {mat}"

    # Capture baseline — delta from this point
    baseline = fg.capture_materialization_baseline(aw)

    # Measure attacker writes BEFORE the attacker does anything
    writes = fg.measure_attacker_writes(aw, baseline)

    # All 11 changed files (10 big_file + 1 target.txt) should consume 0 budget
    assert writes["files_changed"] == 0, (
        f"materialized files consumed attacker budget: {writes['files']}")
    assert writes["bytes_written"] == 0, (
        f"materialized bytes consumed attacker budget: {writes['bytes_written']}")

    subprocess.run(["git","-C",str(repo),"worktree","remove","--force",str(aw)])
    subprocess.run(["git","-C",str(repo),"branch","-D",branch])


def test_one_agent_file_consumes_one_file_plus_its_bytes(tmp_path):
    """One Agent-created file consumes exactly one file and its byte size."""
    import falsification_gate as fg

    repo = _git_repo(tmp_path / "repo")
    head = subprocess.run(["git","-C",str(repo),"rev-parse","HEAD"],
                          capture_output=True, text=True).stdout.strip()

    aw = tmp_path / "attack"
    branch = "t-one-file"
    subprocess.run(["git","-C",str(repo),"worktree","add","-b",branch,str(aw),head],
                   check=True)

    mat = fg.materialize_authoritative_state(repo, aw, head, [])
    assert mat["digest_match"]
    baseline = fg.capture_materialization_baseline(aw)

    # Agent creates one file
    agent_file = aw / "agent_new.txt"
    agent_content = "I AM THE ATTACKER\n" * 10
    agent_file.write_text(agent_content)

    writes = fg.measure_attacker_writes(aw, baseline)
    assert writes["files_changed"] == 1, (
        f"expected 1 agent file, got {writes['files']}")
    actual_size = (aw / "agent_new.txt").stat().st_size
    assert writes["bytes_written"] == actual_size, (
        f"expected {actual_size} bytes (actual file size), got {writes['bytes_written']}")

    subprocess.run(["git","-C",str(repo),"worktree","remove","--force",str(aw)])
    subprocess.run(["git","-C",str(repo),"branch","-D",branch])


def test_agent_edit_to_materialized_file_charged_from_materialized_baseline(tmp_path):
    """Agent edits to a materialized file are measured as delta from
    the materialized version, not from git HEAD."""
    import falsification_gate as fg

    repo = _git_repo(tmp_path / "repo")
    head = subprocess.run(["git","-C",str(repo),"rev-parse","HEAD"],
                          capture_output=True, text=True).stdout.strip()

    # Materialized change: expand seed.txt from 5 bytes to ~500 bytes
    big_content = "A" * 500
    (repo / "seed.txt").write_text(big_content)

    aw = tmp_path / "attack"
    branch = "t-edit-mat"
    subprocess.run(["git","-C",str(repo),"worktree","add","-b",branch,str(aw),head],
                   check=True)

    mat = fg.materialize_authoritative_state(repo, aw, head, [])
    assert mat["digest_match"]
    baseline = fg.capture_materialization_baseline(aw)

    # Verify: baseline measures the 500-byte materialized version
    assert (aw / "seed.txt").read_text() == big_content

    # Agent changes seed.txt by appending 100 bytes
    (aw / "seed.txt").write_text(big_content + ("X" * 100))

    writes = fg.measure_attacker_writes(aw, baseline)
    # Only the 100-byte delta is charged, not the full 600 bytes
    assert writes["bytes_written"] == 100, (
        f"expected 100 bytes delta, got {writes['bytes_written']}")
    assert writes["files_changed"] == 1

    subprocess.run(["git","-C",str(repo),"worktree","remove","--force",str(aw)])
    subprocess.run(["git","-C",str(repo),"branch","-D",branch])
