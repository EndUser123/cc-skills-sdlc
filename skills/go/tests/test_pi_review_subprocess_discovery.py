"""Subprocess-level test: review_transcript.main() writes discovery-evidence on blind write.

This catches the path-resolution bug that unit tests on `extract_discovery_findings`
could not: the importlib path (`parents[N]`) inside main() only runs when the script
is invoked as a subprocess (the real pi-dispatch path). A unit test that imports
the module directly never exercises that code.

Reproduces the failure mode: if `_scripts_dir` resolves to the wrong parent,
`importlib.import_module("preflight_propose")` raises ModuleNotFoundError, the
writer is skipped (best-effort try/except), and discovery-evidence is NOT written.
This test asserts the file IS written when a blind-write transcript exists.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_REVIEW_SCRIPT = SCRIPTS / "adapters" / "pi" / "review_transcript.py"


def _make_blind_write_transcript(path: Path) -> None:
    """A pi --mode json transcript where the worker writes a file with no prior read."""
    events = [
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "write", "arguments": {"path": "src/auth.py",
              "content": "x"}, "id": "w1"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolName": "write",
            "isError": False, "content": [{"type": "text", "text": "ok"}], "toolCallId": "w1"}},
    ]
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def test_review_main_writes_discovery_evidence_on_blind_write(tmp_path: Path) -> None:
    """Subprocess invoke review_transcript.main(); assert discovery-evidence file written.

    Regression for the parents[N] path-resolution bug: if the path is wrong, the
    import fails, the writer is skipped, and this file is never created.
    """
    run_id = "subproc-001"
    state_dir = tmp_path
    transcript = state_dir / f"pi-transcript_{run_id}.jsonl"
    _make_blind_write_transcript(transcript)

    env = {**os.environ, "GO_STATE_DIR": str(state_dir), "RUN_ID": run_id}
    # Active task with no forbidden_files, broad scope so BLIND_WRITE is the only warning.
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"title": "T", "scope_in": [], "forbidden_files": []}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(_REVIEW_SCRIPT)],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"review_transcript failed: {result.stderr}"

    # The pi-review summary must exist.
    assert (state_dir / f"pi-review_{run_id}.json").exists()

    # The discovery-evidence file must exist (writer succeeded via correct path).
    de_file = state_dir / f"discovery-evidence_{run_id}.json"
    assert de_file.exists(), (
        "discovery-evidence not written -- path resolution or import failed silently. "
        f"stderr: {result.stderr}"
    )
    de = json.loads(de_file.read_text(encoding="utf-8"))
    assert de["run_id"] == run_id
    assert any(f["structural_issues"] == ["wrong_layer_ownership"] for f in de["findings"])


def test_review_main_no_warnings_no_discovery_file(tmp_path: Path) -> None:
    """Clean transcript (read then write) -> no discovery-evidence file."""
    run_id = "subproc-002"
    state_dir = tmp_path
    transcript = state_dir / f"pi-transcript_{run_id}.jsonl"
    events = [
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "read", "arguments": {"path": "src/auth.py"}, "id": "r1"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolName": "read",
            "isError": False, "content": [{"type": "text", "text": "y"}], "toolCallId": "r1"}},
        {"type": "message", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "write", "arguments": {"path": "src/auth.py",
              "content": "z"}, "id": "w1"}]}},
        {"type": "message", "message": {"role": "toolResult", "toolName": "write",
            "isError": False, "content": [{"type": "text", "text": "ok"}], "toolCallId": "w1"}},
    ]
    with transcript.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    (state_dir / f"active-task_{run_id}.json").write_text(
        json.dumps({"task": {"title": "T", "scope_in": [], "forbidden_files": []}}),
        encoding="utf-8",
    )
    env = {**os.environ, "GO_STATE_DIR": str(state_dir), "RUN_ID": run_id}
    subprocess.run([sys.executable, str(_REVIEW_SCRIPT)], env=env,
                   capture_output=True, text=True, timeout=30)
    assert not (state_dir / f"discovery-evidence_{run_id}.json").exists()


# --- Multi-terminal safe: run_id-scoped paths; no shared state ---
class TestPiDiscoveryWriterFailure:
    """Verify PI review continues even if discovery-evidence writer fails."""

    def test_review_does_not_crash_on_writer_error(self, tmp_path):
        """PI review completes even when discovery-evidence writer fails."""
        rid = "no-crash-001"
        state_dir = tmp_path
        transcript = state_dir / f"pi-transcript_{rid}.jsonl"
        with transcript.open("w", encoding="utf-8") as f:
            f.write(json.dumps({
                "type": "message", "message": {"role": "assistant", "content": [
                    {"type": "toolCall", "name": "write", "arguments": {"path": "x.py"}, "id": "w1"}]}}))
        (state_dir / f"active-task_{rid}.json").write_text(
            json.dumps({"task": {"title": "T", "scope_in": [], "forbidden_files": []}}),
            encoding="utf-8",
        )
        # Force the writer to fail by sabotaging the target module: rename it
        # so importlib.import_module raises ModuleNotFoundError inside main().
        src = SCRIPTS / "preflight_propose.py"
        backup = src.read_text(encoding="utf-8")
        try:
            # Move the real file aside, drop a broken stub in its place.
            real = src.with_suffix(".py.bak")
            src.rename(real)
            try:
                src.write_text("raise RuntimeError('simulated writer failure')\n", encoding="utf-8")
                env = {**os.environ, "GO_STATE_DIR": str(state_dir), "RUN_ID": rid}
                result = subprocess.run(
                    [sys.executable, str(_REVIEW_SCRIPT)],
                    env=env, capture_output=True, text=True, timeout=30,
                )
                # Review must complete (no crash); pi-review must be written.
                assert result.returncode == 0, f"review crashed: {result.stderr}"
                assert (state_dir / f"pi-review_{rid}.json").exists()
                # Error telemetry must be written.
                err_tel = state_dir / f"telemetry-discovery-evidence-error_{rid}.jsonl"
                assert err_tel.exists(), (
                    f"error telemetry not written. stderr: {result.stderr}"
                )
                lines = [json.loads(l) for l in
                         err_tel.read_text(encoding="utf-8").strip().splitlines()]
                assert any(l.get("error_type") in ("import_error", "unexpected_error")
                           for l in lines), f"unexpected error_type: {lines}"
            finally:
                # Restore: drop stub, rename real back.
                if src.exists():
                    src.unlink()
                real.rename(src)
        except Exception:
            # Belt-and-suspenders: if anything blew up mid-test, restore.
            if real.exists() and not src.exists():
                real.rename(src)
            raise


class TestTelemetryErrorDetection:
    """Verify emit_discovery_evidence_telemetry detects writer-error artifacts."""

    def test_telemetry_detects_writer_error_file(self, tmp_path):
        """If telemetry-discovery-evidence-error_{run_id}.jsonl exists,
        telemetry reports writer_error=True and source='writer_error'."""
        import importlib.util
        pp_spec = importlib.util.spec_from_file_location("pp", SCRIPTS / "preflight_propose.py")
        pp = importlib.util.module_from_spec(pp_spec)
        pp_spec.loader.exec_module(pp)
        rid = "tel-err-001"
        # Seed the error artifact (simulating a prior PI writer failure).
        err_path = tmp_path / f"telemetry-discovery-evidence-error_{rid}.jsonl"
        err_path.write_text(json.dumps({
            "event": "discovery_evidence_writer_error",
            "run_id": rid, "error_type": "import_error",
        }) + "\n", encoding="utf-8")
        record = pp.emit_discovery_evidence_telemetry(tmp_path, rid)
        assert record["writer_error"] is True
        assert record["source"] == "writer_error"

    def test_telemetry_distinguishes_dropped_all(self, tmp_path):
        """Discovery file present but no findings -> writer_dropped_all=True."""
        import importlib.util
        pp_spec = importlib.util.spec_from_file_location("pp", SCRIPTS / "preflight_propose.py")
        pp = importlib.util.module_from_spec(pp_spec)
        pp_spec.loader.exec_module(pp)
        rid = "tel-drop-001"
        # Discovery file present but empty findings list.
        (tmp_path / f"discovery-evidence_{rid}.json").write_text(
            json.dumps({"findings": []}), encoding="utf-8",
        )
        record = pp.emit_discovery_evidence_telemetry(tmp_path, rid)
        assert record["writer_dropped_all"] is True
        assert record["exists"] is False
        assert record["source"] == "absent"
