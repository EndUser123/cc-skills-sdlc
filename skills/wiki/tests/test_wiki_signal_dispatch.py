"""Tests for wiki_signal_dispatch.py — Stage 4 plan emission."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "wiki_signal_dispatch.py"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def test_help_prints():
    r = _run_cli(["--help"])
    assert r.returncode == 0
    assert "dispatch" in r.stdout.lower()


def _make_chunk(dir_path: Path, name: str, source: str, source_path: str, candidates: list[dict]) -> Path:
    p = dir_path / name
    p.write_text(json.dumps({
        "source_file": source,
        "source_path": source_path,
        "chunk_index": 0,
        "candidates": candidates,
    }), encoding="utf-8")
    return p


def test_plan_lists_one_block_per_chunk(tmp_path: Path):
    chunks = tmp_path / "chunks"; chunks.mkdir()
    c1 = _make_chunk(chunks, "alpha.json", "alpha.txt", "/src/alpha.txt", [
        {"sentence": "Root cause: alpha.py:1 fails.", "novelty": 0.9, "line_no": 1, "context_snippet": ">>>     1: Root cause: alpha.py:1 fails."},
    ])
    c2 = _make_chunk(chunks, "beta.json", "beta.txt", "/src/beta.txt", [
        {"sentence": "The fix is at beta.py:2.", "novelty": 0.8, "line_no": 2, "context_snippet": ">>>     2: The fix is at beta.py:2."},
    ])
    manifest = tmp_path / "_manifest.json"
    manifest.write_text(json.dumps([
        {"chunk": str(c1), "source_file": "alpha.txt", "candidate_count": 1},
        {"chunk": str(c2), "source_file": "beta.txt", "candidate_count": 1},
    ]), encoding="utf-8")
    out = tmp_path / "plan.md"

    r = _run_cli([f"--manifest={manifest}", f"--chunks-dir={chunks}", f"--out={out}", "--mode=plan"])
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "alpha.txt" in text and "beta.txt" in text
    # each candidate sentence appears in the rendered block
    assert "alpha.py:1" in text
    assert "beta.py:2" in text
    # the execution guidance is present
    assert "Task-tool" in text
    assert "qmd_update_wrapper.ps1" in text


def test_ai_cli_mode_emits_shell_commands(tmp_path: Path):
    chunks = tmp_path / "chunks"; chunks.mkdir()
    c1 = _make_chunk(chunks, "alpha.json", "alpha.txt", "/src/alpha.txt", [
        {"sentence": "Root cause: alpha.py:1 fails.", "novelty": 0.9, "line_no": 1, "context_snippet": ""},
    ])
    manifest = tmp_path / "_manifest.json"
    manifest.write_text(json.dumps([
        {"chunk": str(c1), "source_file": "alpha.txt", "candidate_count": 1},
    ]), encoding="utf-8")
    out = tmp_path / "plan.md"

    r = _run_cli([f"--manifest={manifest}", f"--chunks-dir={chunks}", f"--out={out}", "--mode=ai-cli"])
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert "ai-cli shell commands" in text.lower()
    assert "ai-cli " in text
    # the prompt payload file was written next to the chunk
    assert (chunks / "alpha.prompt.txt").exists()


def test_max_chunks_caps_plan(tmp_path: Path):
    chunks = tmp_path / "chunks"; chunks.mkdir()
    entries = []
    for i in range(5):
        cp = _make_chunk(chunks, f"f{i}.json", f"f{i}.txt", f"/src/f{i}.txt", [
            {"sentence": f"Root cause: f{i}.py:1.", "novelty": 0.9, "line_no": 1, "context_snippet": ""},
        ])
        entries.append({"chunk": str(cp), "source_file": f"f{i}.txt", "candidate_count": 1})
    manifest = tmp_path / "_manifest.json"
    manifest.write_text(json.dumps(entries), encoding="utf-8")
    out = tmp_path / "plan.md"

    r = _run_cli([f"--manifest={manifest}", f"--chunks-dir={chunks}", f"--out={out}", "--max-chunks=2"])
    assert r.returncode == 0
    text = out.read_text(encoding="utf-8")
    # only first two chunk headers appear
    assert "f0.txt" in text and "f1.txt" in text
    assert "f2.txt" not in text