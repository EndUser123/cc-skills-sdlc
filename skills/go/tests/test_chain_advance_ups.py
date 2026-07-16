"""Tests for chain_advance_ups.py — UserPromptSubmit hook."""

import io
import json
from pathlib import Path

import pytest

import sys as _sys
import importlib.util as _util

_PACKAGE = Path(__file__).resolve().parents[1]
_spec = _util.spec_from_file_location(
    "chain_advance_ups", _PACKAGE / "scripts" / "chain_advance_ups.py"
)
_ups = _util.module_from_spec(_spec)
_sys.modules["chain_advance_ups"] = _ups
_spec.loader.exec_module(_ups)

parse_chain = _ups.parse_chain
_cache = {}  # module-level state for tests


class TestParseChain:
    """parse_chain() unit tests."""

    def test_no_chain_on_bare_command(self):
        assert parse_chain("/go") == []

    def test_no_chain_on_primary_only(self):
        assert parse_chain("/go task") == []

    def test_two_step_chain(self):
        result = parse_chain("/go task, /check")
        assert result == [("go", "task"), ("check", "")]

    def test_chain_with_args(self):
        result = parse_chain("/go task --verbose, /check --deep")
        assert result == [("go", "task --verbose"), ("check", "--deep")]

    def test_three_step_chain(self):
        result = parse_chain("/go task, /check, /verify")
        assert len(result) == 3
        assert result[2] == ("verify", "")

    def test_chain_ignores_no_slash(self):
        assert parse_chain("/go task, check") == []

    def test_chain_ignores_natural_comma(self):
        assert parse_chain("/go task 1, task 2") == []

    def test_no_slash_no_chain(self):
        assert parse_chain("hello world") == []

    def test_namespaced_skill(self):
        result = parse_chain("/go task, /cc-skills-sdlc:check")
        assert result == [("go", "task"), ("cc-skills-sdlc:check", "")]

    def test_chain_preserves_spaces(self):
        result = parse_chain("/go    task   , /check   verify")
        assert result == [("go", "task"), ("check", "verify")]


class TestSessionId:
    """_session_id() resolution."""

    def test_uses_payload_session_id(self):
        sid = _ups._session_id({"sessionId": "test-session-1"})
        assert sid == "test-session-1"

    def test_uses_claude_code_session_id_fallback(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
        monkeypatch.setenv("CLAUDE_TERMINAL_ID", "term-1")
        sid = _ups._session_id({})
        assert sid == "term-1"


class TestMainIntegration:
    """Integration tests for main() via stdin simulation."""

    def _mock_stdin(self, data: bytes):
        """Patch sys.stdin to return bytes via .buffer.read()."""
        class _MockBuffer:
            def read(self):
                return data
        class _MockStdin:
            buffer = _MockBuffer()
        _sys.stdin = _MockStdin()

    def test_no_input_returns_empty(self, capsys):
        self._mock_stdin(b"")
        _ups.main()
        out, _ = capsys.readouterr()
        assert out.strip() == "{}"

    def test_non_chain_prompt_returns_empty(self, capsys):
        self._mock_stdin(json.dumps({"prompt": "/go task"}).encode())
        _ups.main()
        out, _ = capsys.readouterr()
        assert out.strip() == "{}"

    def test_chain_prompt_creates_manifest(self, capsys, tmp_path):
        import os as _os
        _os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        # Reset the hook's cached manifest module so it reloads with the new env var
        _ups._manifest_mod = None
        payload = json.dumps({"prompt": "/go task, /check", "sessionId": "sess-1"})
        self._mock_stdin(payload.encode())
        _ups.main()
        out, _ = capsys.readouterr()
        # Chain input: pass through
        assert out.strip() == "{}"
        # Verify manifest was created (reuse the hook's loaded module so CHAIN_STEPS_DIR matches)
        cm = _ups._get_manifest_module()
        chains = cm.list_chains(session_id="sess-1")
        assert len(chains) == 1
        assert len(chains[0].steps) == 2
        assert chains[0].steps[0].skill == "go"
        assert chains[0].steps[1].skill == "check"
        # Cleanup
        for c in chains:
            cm.clear_chain(c.chain_id, force=True)
        del _os.environ["CHAIN_STEPS_DIR"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cm():
    """Get the chain_manifest module (shared lazy import)."""
    if "cm" in _cache:
        return _cache["cm"]
    import importlib.util as _u
    spec = _u.spec_from_file_location(
        "chain_manifest", _PACKAGE / "scripts" / "chain_manifest.py"
    )
    mod = _u.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _cache["cm"] = mod
    return mod
