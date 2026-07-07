"""Tests for wiki_signal_filter.py — tool-output noise + durable-claim signatures."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "wiki_signal_filter.py"


def _run_cli(args: list[str], stdin_payload: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), *args]
    if stdin_payload is not None:
        return subprocess.run(cmd, input=json.dumps(stdin_payload), capture_output=True, text=True, encoding="utf-8")
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def test_help_prints():
    r = _run_cli(["--help"])
    assert r.returncode == 0
    assert "filter" in r.stdout.lower()


def test_tool_output_noise_detected():
    # Sentences that hit >= 3 of the noise patterns
    noise_samples = [
        "✅ HOOK_SYNTAX [15ms] All 4 hooks pass syntax check",          # status emoji + log level + KB unit
        "P:\\.claude\\hooks\\session_registry.jsonl: 12345 lines, 678KB", # raw path + size
        "[2026-07-05T12:25:36.873Z] User: tell me about hooks",          # ISO timestamp + role label
        "1 | component  | path  | status",                                # table row + table separator
    ]
    # Direct unit check via subprocess by feeding each
    payload = {
        "in_path": str(Path(__file__).parent / "fixtures" / "tiny_signal.json"),
        "wiki_dir": "P:/.data/wiki/concepts",
        "out_path": str(Path(__file__).parent / "fixtures" / "tiny_filtered.json"),
    }
    fixture_in = Path(payload["in_path"])
    fixture_in.parent.mkdir(parents=True, exist_ok=True)
    fixture_in.write_text(json.dumps([{"file": "x.txt", "sentence": s, "novelty": 0.95} for s in noise_samples] + [
        # Genuine durable claims that should survive
        {"file": "y.txt", "sentence": "The fix is to set priority 0.1 in UserPromptSubmit_router.py line 45.", "novelty": 0.95},
        {"file": "z.txt", "sentence": "GO_RUN_ID, RUN_ID, and CLAUDE_GO_RUN_ID are three names for the same env var; carrier via process env is the root cause.", "novelty": 0.95},
    ]), encoding="utf-8")
    r = _run_cli([f"--in={payload['in_path']}",
                  f"--wiki={payload['wiki_dir']}",
                  f"--out={payload['out_path']}"])
    assert r.returncode == 0, r.stderr
    kept = json.loads(Path(payload["out_path"]).read_text(encoding="utf-8"))
    kept_sents = {k["sentence"] for k in kept}
    # Noise should be gone
    for s in noise_samples:
        assert s not in kept_sents, f"noise survived: {s[:60]}"
    # Durable claims should remain
    assert any("priority 0.1 in UserPromptSubmit_router.py line 45" in k for k in kept)
    assert any("GO_RUN_ID, RUN_ID, and CLAUDE_GO_RUN_ID" in k for k in kept)


def test_durable_signature_required():
    payload_sentences = [
        # No decision verb (just an observation)
        "The file contains 200 lines of code.",
        # Decision verb but no concrete anchor
        "The fix is to do something different.",
        # Both present — should survive
        "caused by a stale require() cache after the lmstudio -> llama-cpp rename at line 12",
    ]
    fixture_in = Path(__file__).parent / "fixtures" / "sig_test.json"
    fixture_in.parent.mkdir(parents=True, exist_ok=True)
    fixture_in.write_text(json.dumps([{"file": "x.txt", "sentence": s, "novelty": 0.95} for s in payload_sentences]), encoding="utf-8")
    out_path = fixture_in.with_name("sig_filtered.json")
    r = _run_cli([f"--in={fixture_in}", "--wiki=P:/.data/wiki/concepts", f"--out={out_path}"])
    assert r.returncode == 0
    kept = {k["sentence"] for k in json.loads(out_path.read_text(encoding="utf-8"))}
    assert "caused by a stale require() cache after the lmstudio -> llama-cpp rename at line 12" in kept
    assert "The file contains 200 lines of code." not in kept
    assert "The fix is to do something different." not in kept