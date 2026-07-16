"""Tests for chain_stop_gate.py — Stop hook for chain enforcement."""

import json
from pathlib import Path

import pytest

import sys as _sys
import importlib.util as _util

_PACKAGE = Path(__file__).resolve().parents[1]
_spec = _util.spec_from_file_location(
    "chain_stop_gate", _PACKAGE / "scripts" / "chain_stop_gate.py"
)
_gate = _util.module_from_spec(_spec)
_sys.modules["chain_stop_gate"] = _gate
_spec.loader.exec_module(_gate)


class TestChainStopGate:
    """chain_stop_gate main() tests."""

    def _mock_stdin(self, data: bytes):
        """Patch sys.stdin.buffer for testing."""
        class _MockBuffer:
            def read(self): return data
        class _MockStdin:
            buffer = _MockBuffer()
        _sys.stdin = _MockStdin()

    def _create_chain(self, steps, session_id, cm):
        """Create a fresh chain manifest."""
        chain = cm.create_manifest(steps, session_id=session_id)
        return chain

    def test_no_stdin_silent(self, capsys):
        """No stdin input should produce no output."""
        self._mock_stdin(b"")
        _gate.main()
        out, _ = capsys.readouterr()
        assert out == "", f"Expected empty output, got: {out}"

    def test_no_prompt_silent(self, capsys):
        """No session_id should produce no output."""
        self._mock_stdin(json.dumps({}).encode())
        _gate.main()
        out, _ = capsys.readouterr()
        assert out == "", f"Expected empty output, got: {out}"

    def test_no_active_chain_silent(self, capsys, tmp_path):
        """No chain manifest for this session -> silent."""
        import os
        os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        self._mock_stdin(json.dumps({"sessionId": "no-chain-test"}).encode())
        _gate.main()
        out, _ = capsys.readouterr()
        assert out == "", f"Expected empty output, got: {out}"

    def test_pending_step_silent(self, capsys, tmp_path):
        """Step is 'pending' (dispatched by SlashCommand) -> silent."""
        import os
        os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        cm = _gate._get_manifest_module()
        self._create_chain([("go", "task")], "pending-test", cm)
        # step[0] is "pending" by default
        self._mock_stdin(json.dumps({"sessionId": "pending-test"}).encode())
        _gate.main()
        out, _ = capsys.readouterr()
        assert out == "", f"Expected empty output, got: {out}"
        # Cleanup
        chains = cm.list_chains(session_id="pending-test")
        for c in chains:
            cm.clear_chain(c.chain_id, force=True)
        del os.environ["CHAIN_STEPS_DIR"]

    def test_running_step_blocks(self, capsys, tmp_path):
        """Current step is 'running' (injected by UPS) -> blocks."""
        import os
        os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        cm = _gate._get_manifest_module()
        chain = self._create_chain([("go", "task"), ("check", "")], "block-test", cm)
        # Simulate UPS hook: advance step[0] to complete, step[1] to running
        cm.advance_step(chain.chain_id, step_index=0, new_status="complete")
        cm.advance_step(chain.chain_id, step_index=1, new_status="running")
        self._mock_stdin(json.dumps({"sessionId": "block-test"}).encode())
        _gate.main()
        out, _ = capsys.readouterr()
        result = json.loads(out.strip())
        assert result["decision"] == "block", f"Expected block, got: {result}"
        assert "continue:" in result["reason"], f"Expected 'continue:' in reason, got: {result}"
        chain_cm = cm.get_chain(chain.chain_id)
        cm.clear_chain(chain.chain_id, force=True)
        del os.environ["CHAIN_STEPS_DIR"]

    def test_complete_chain_silent(self, capsys, tmp_path):
        """Chain is 'complete' -> silent."""
        import os
        os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        cm = _gate._get_manifest_module()
        chain = self._create_chain([("go", "task")], "complete-test", cm)
        cm.advance_step(chain.chain_id, new_status="complete")
        self._mock_stdin(json.dumps({"sessionId": "complete-test"}).encode())
        _gate.main()
        out, _ = capsys.readouterr()
        assert out == "", f"Expected empty output, got: {out}"
        # Chain should be complete
        chain = cm.get_chain(chain.chain_id)
        assert chain.status == "complete"
        cm.clear_chain(chain.chain_id, force=True)
        del os.environ["CHAIN_STEPS_DIR"]
