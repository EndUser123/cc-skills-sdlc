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
    # Sentences that hit >= 2 of the noise patterns (current NOISE_THRESHOLD)
    noise_samples = [
        "✅ HOOK_SYNTAX [15ms] All 4 hooks pass syntax check",          # status emoji + KB unit
        "P:\\.claude\\hooks\\session_registry.jsonl: 12345 lines, 678KB", # raw path + size
        "[2026-07-05T12:25:36.873Z] User: tell me about hooks",          # ISO timestamp + role label
    ]
    durable_claims = [
        "The fix is to set priority 0.1 in SkilL_first_gate_v3_xyz_unique line 45.",
        "GO_RUN_ID, RUN_ID, and CLAUDE_GO_RUN_ID are three names for the same env var; carrier via process env is the root cause.",
    ]
    payload = {
        "in_path": str(Path(__file__).parent / "fixtures" / "tiny_signal.json"),
        # Empty wiki dir means the wiki-overlap dedup never fires — isolates the
        # noise + durable-signature filters under test.
        "wiki_dir": str(Path(__file__).parent / "fixtures" / "empty_wiki"),
        "out_path": str(Path(__file__).parent / "fixtures" / "tiny_filtered.json"),
    }
    Path(payload["wiki_dir"]).mkdir(parents=True, exist_ok=True)
    fixture_in = Path(payload["in_path"])
    fixture_in.parent.mkdir(parents=True, exist_ok=True)
    fixture_in.write_text(json.dumps(
        [{"file": "x.txt", "sentence": s, "novelty": 0.95} for s in noise_samples] +
        [{"file": "y.txt", "sentence": s, "novelty": 0.95} for s in durable_claims]
    ), encoding="utf-8")
    r = _run_cli([f"--in={payload['in_path']}",
                  f"--wiki={payload['wiki_dir']}",
                  f"--out={payload['out_path']}"])
    assert r.returncode == 0, r.stderr
    kept = json.loads(Path(payload["out_path"]).read_text(encoding="utf-8"))
    kept_sents = {k["sentence"] for k in kept}
    for s in noise_samples:
        assert s not in kept_sents, f"noise survived: {s[:60]}"
    for s in durable_claims:
        assert s in kept_sents, f"durable claim dropped: {s[:60]}"


def test_durable_signature_required():
    payload_sentences = [
        # No decision verb
        "The file contains 200 lines of code.",
        # Decision verb but no concrete anchor
        "The fix is to do something different.",
        # Decision verb + file.py:line anchor — should survive
        "Root cause: cli.py:1122 imports non-existent research_flash.sources.github_source.",
        # Decision verb + function anchor
        "Fix 3 — Dead code removal: removed unreachable return in apply_epistemic_policy at line 1945.",
    ]
    fixture_in = Path(__file__).parent / "fixtures" / "sig_test.json"
    fixture_in.parent.mkdir(parents=True, exist_ok=True)
    fixture_in.write_text(json.dumps([{"file": "x.txt", "sentence": s, "novelty": 0.95} for s in payload_sentences]), encoding="utf-8")
    out_path = fixture_in.with_name("sig_filtered.json")
    # Empty wiki dir isolates the signature filter from the wiki-dedup filter.
    empty_wiki = Path(__file__).parent / "fixtures" / "empty_wiki"
    empty_wiki.mkdir(parents=True, exist_ok=True)
    r = _run_cli([f"--in={fixture_in}", f"--wiki={empty_wiki}", f"--out={out_path}"])
    assert r.returncode == 0
    kept = {k["sentence"] for k in json.loads(out_path.read_text(encoding="utf-8"))}
    # Both anchor + verb — survive
    assert any("cli.py:1122 imports non-existent" in k for k in kept)
    assert any("Fix 3 — Dead code removal" in k and "apply_epistemic_policy" in k for k in kept)
    # Without anchor or verb — drop
    assert not any("The file contains 200 lines of code." in k for k in kept)
    assert not any("The fix is to do something different." == k for k in kept)