"""Tests for wiki_signal_distill.py — candidate chunking + context extraction."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "wiki_signal_distill.py"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def test_help_prints():
    r = _run_cli(["--help"])
    assert r.returncode == 0
    assert "chunk" in r.stdout.lower()


def test_chunk_includes_context_snippet(tmp_path: Path):
    # Source file with a known durable sentence on a recognizable line
    src = tmp_path / "src"; src.mkdir()
    src_file = src / "trace.txt"
    src_file.write_text(
        "line one filler\n"
        "line two filler\n"
        "Root cause: xyz_pipeline.py:77 silently drops the lock on retry.\n"
        "line four filler\n"
        "line five filler\n",
        encoding="utf-8",
    )
    # Input candidates (as if from wiki_signal_filter.py)
    in_json = tmp_path / "durable.json"
    in_json.write_text(json.dumps([
        {"file": "trace.txt", "sentence": "Root cause: xyz_pipeline.py:77 silently drops the lock on retry.", "novelty": 0.9},
    ]), encoding="utf-8")

    out_dir = tmp_path / "chunks"
    r = _run_cli([f"--in={in_json}", f"--source={src}", f"--out-dir={out_dir}", "--context-lines=1"])
    assert r.returncode == 0, r.stderr

    chunks = [p for p in out_dir.glob("*.json") if p.name != "_manifest.json"]
    assert len(chunks) == 1
    data = json.loads(chunks[0].read_text(encoding="utf-8"))
    assert data["source_file"] == "trace.txt"
    assert len(data["candidates"]) == 1
    cand = data["candidates"][0]
    assert cand["line_no"] == 3
    # Snippet must contain the anchor marker + the surrounding lines
    assert ">>>     3:" in cand["context_snippet"]
    assert "xyz_pipeline.py:77" in cand["context_snippet"]
    # With context-lines=1, exactly 3 lines (line 2, anchor 3, line 4)
    assert len(cand["context_snippet"].splitlines()) == 3


def test_manifest_lists_chunks(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.txt").write_text("Root cause: alpha.py:1 fails silently.\n", encoding="utf-8")
    (src / "b.txt").write_text("The fix is to set beta.py:2 priority.\n", encoding="utf-8")
    in_json = tmp_path / "durable.json"
    in_json.write_text(json.dumps([
        {"file": "a.txt", "sentence": "Root cause: alpha.py:1 fails silently.", "novelty": 0.9},
        {"file": "b.txt", "sentence": "The fix is to set beta.py:2 priority.", "novelty": 0.8},
    ]), encoding="utf-8")

    out_dir = tmp_path / "chunks"
    r = _run_cli([f"--in={in_json}", f"--source={src}", f"--out-dir={out_dir}"])
    assert r.returncode == 0, r.stderr

    manifest = json.loads((out_dir / "_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 2
    files_in_manifest = {m["source_file"] for m in manifest}
    assert files_in_manifest == {"a.txt", "b.txt"}


def test_missing_source_file_skipped(tmp_path: Path):
    src = tmp_path / "src"; src.mkdir()
    (src / "present.txt").write_text("Root cause: real.py:1 fails.\n", encoding="utf-8")
    in_json = tmp_path / "durable.json"
    in_json.write_text(json.dumps([
        {"file": "present.txt", "sentence": "Root cause: real.py:1 fails.", "novelty": 0.9},
        {"file": "absent.txt", "sentence": "Root cause: ghost.py:1 fails.", "novelty": 0.9},
    ]), encoding="utf-8")

    out_dir = tmp_path / "chunks"
    r = _run_cli([f"--in={in_json}", f"--source={src}", f"--out-dir={out_dir}"])
    assert r.returncode == 0
    manifest = json.loads((out_dir / "_manifest.json").read_text(encoding="utf-8"))
    assert {m["source_file"] for m in manifest} == {"present.txt"}