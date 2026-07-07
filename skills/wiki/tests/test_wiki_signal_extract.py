"""Tests for wiki_signal_extract.py — signal-pattern scan + wiki-overlap dedup."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "wiki_signal_extract.py"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def test_help_prints():
    r = _run_cli(["--help"])
    assert r.returncode == 0
    assert "scan" in r.stdout.lower()


def test_extract_and_dedup_against_wiki(tmp_path: Path):
    # Source: one file with a durable signal sentence + one with noise
    src = tmp_path / "src"; src.mkdir()
    (src / "good.txt").write_text(
        "Root cause: the daemon leaks the mutex because zombie cleanup never releases it.",
        encoding="utf-8",
    )
    (src / "noise.txt").write_text(
        "The weather is nice today and I went for a walk.",
        encoding="utf-8",
    )
    # Wiki: contains the exact root-cause sentence -> should drive overlap-based drop
    wiki = tmp_path / "wiki"; wiki.mkdir()
    (wiki / "existing.md").write_text(
        "Root cause: the daemon leaks the mutex because zombie cleanup never releases it.",
        encoding="utf-8",
    )
    out = tmp_path / "candidates.json"

    r = _run_cli([f"--source={src}", f"--wiki={wiki}", f"--out={out}"])
    assert r.returncode == 0, r.stderr
    cands = json.loads(out.read_text(encoding="utf-8"))
    # The good sentence is fully absorbed by the wiki page -> dropped as non-novel
    assert all("daemon leaks the mutex" not in c["sentence"] for c in cands), \
        "wiki-absorbed sentence should be dropped"
    # The noise sentence has no signal pattern -> never even a candidate
    assert all("weather is nice" not in c["sentence"] for c in cands)


def test_signal_sentence_with_novel_anchor_survives(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir()
    # Novel root-cause sentence the (empty) wiki has never seen
    (src / "novel.txt").write_text(
        "Root cause: cli_unicorn_v9.py:42 imports non-existent sparkle_module.zeta.",
        encoding="utf-8",
    )
    wiki = tmp_path / "wiki"; wiki.mkdir()  # empty
    out = tmp_path / "candidates.json"

    r = _run_cli([f"--source={src}", f"--wiki={wiki}", f"--out={out}"])
    assert r.returncode == 0, r.stderr
    cands = json.loads(out.read_text(encoding="utf-8"))
    assert any("cli_unicorn_v9.py:42" in c["sentence"] for c in cands), \
        "novel signal sentence should be extracted"


def test_missing_source_dir_errors_clean(tmp_path: Path):
    out = tmp_path / "candidates.json"
    r = _run_cli([f"--source={tmp_path / 'nonexistent'}", f"--wiki={tmp_path}", f"--out={out}"])
    assert r.returncode == 1
    assert "not found" in r.stderr.lower() or "not found" in r.stdout.lower()


def test_chain_files_skipped(tmp_path: Path):
    """GATE-001: chain_*.md session exports are skipped by default to avoid
    re-scanning already-ingested transcripts."""
    src = tmp_path / "src"; src.mkdir()
    (src / "chain_20260705_192919.md").write_text(
        "Root cause: novel_chain_bug.py:1 fails silently.", encoding="utf-8",
    )
    (src / "real_source.txt").write_text(
        "Root cause: novel_real_bug.py:2 fails silently.", encoding="utf-8",
    )
    wiki = tmp_path / "wiki"; wiki.mkdir()
    out = tmp_path / "candidates.json"

    r = _run_cli([f"--source={src}", f"--wiki={wiki}", f"--out={out}"])
    assert r.returncode == 0
    assert "skipped 1 chain files" in r.stdout, f"expected chain skip message, got: {r.stdout}"
    cands = json.loads(out.read_text(encoding="utf-8"))
    # The chain file's sentence must NOT appear; the real file's must
    assert all("novel_chain_bug" not in c["sentence"] for c in cands), \
        "chain_*.md file should be skipped"
    assert any("novel_real_bug" in c["sentence"] for c in cands), \
        "real source file should be scanned"


def test_log_md_hash_dedup(tmp_path: Path):
    """GATE-002: files whose SHA256 hash appears in the wiki log.md are
    reported as already-processed. This test verifies the hash-loading
    path works by creating a log.md with a known hash."""
    import hashlib
    src = tmp_path / "src"; src.mkdir()
    source_file = src / "ingested.txt"
    source_content = "Root cause: dedup_test.py:1 fails on retry."
    source_file.write_text(source_content, encoding="utf-8")

    wiki = tmp_path / "wiki"; wiki.mkdir()
    file_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
    (wiki / "log.md").write_text(
        f"## [2026-07-07] ingest | test\nSHA256: {file_hash}\n",
        encoding="utf-8",
    )
    out = tmp_path / "candidates.json"

    r = _run_cli([f"--source={src}", f"--wiki={wiki}", f"--out={out}"])
    assert r.returncode == 0
    # The extractor should report that it loaded hashes from log.md
    assert "already-injected hashes: 1" in r.stdout or "already-injected hashes: " in r.stdout, \
        f"expected hash loading from log.md, got: {r.stdout}"