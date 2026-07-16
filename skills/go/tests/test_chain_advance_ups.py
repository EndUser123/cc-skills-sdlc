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

    def test_chain_without_space_after_command(self):
        """parse_chain handles /go, /check (no space after command)."""
        result = parse_chain("/go, /check")
        assert result == [("go", ""), ("check", "")]

    def test_chain_without_space_args_then_comma(self):
        """parse_chain handles /go task, /check (space before comma, not after cmd)."""
        result = parse_chain("/go task, /check")
        assert result == [("go", "task"), ("check", "")]

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
        """When CLAUDE_CODE_SESSION_ID is set, it's used as fallback."""
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-from-env")
        sid = _ups._session_id({})
        assert sid == "session-from-env"

    def test_uses_instance_id_when_no_session_available(self, monkeypatch):
        """When no payload sessionId and no env var, falls back to _INSTANCE_ID."""
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
        # _INSTANCE_ID is set at module load time
        sid = _ups._session_id({})
        assert sid == _ups._INSTANCE_ID


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

    def test_chain_abandons_old_chain(self, capsys, tmp_path):
        """Creating a new chain abandons any existing active chain for the session."""
        import os as _os
        _os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        _ups._manifest_mod = None
        cm = _ups._get_manifest_module()
        # Create an initial chain
        cm.create_manifest([("go", "task"), ("check", "")], session_id="sess-2")
        # Now send new chain input
        payload = json.dumps({"prompt": "/verify test, /check", "sessionId": "sess-2"})
        self._mock_stdin(payload.encode())
        _ups.main()
        out, _ = capsys.readouterr()
        assert out.strip() == "{}"
        # Verify old chain is gone (abandoned via clear_chain force)
        chains = cm.list_chains(session_id="sess-2")
        active = [c for c in chains if c.status == "in_progress"]
        assert len(active) == 1
        assert active[0].steps[0].skill == "verify"
        # Cleanup
        for c in chains:
            cm.clear_chain(c.chain_id, force=True)
        del _os.environ["CHAIN_STEPS_DIR"]

    def test_non_blank_abandons_chain(self, capsys, tmp_path):
        """Non-blank input while a chain is active abandons the chain."""
        import os as _os
        _os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        _ups._manifest_mod = None
        cm = _ups._get_manifest_module()
        # Create a chain
        chain = cm.create_manifest([("go", "task")], session_id="sess-3")
        cm.advance_step(chain.chain_id, new_status="running")
        # Send non-blank input
        payload = json.dumps({"prompt": "/check unrelated", "sessionId": "sess-3"})
        self._mock_stdin(payload.encode())
        _ups.main()
        out, _ = capsys.readouterr()
        assert out.strip() == "{}"
        # Chain should be cleared (abandoned)
        chains = cm.list_chains(session_id="sess-3")
        assert len(chains) == 0
        del _os.environ["CHAIN_STEPS_DIR"]

    def test_blank_input_advances_chain(self, capsys, tmp_path):
        """Blank input while chain is active advances to next step and injects command."""
        import os as _os
        _os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        _ups._manifest_mod = None
        cm = _ups._get_manifest_module()
        # Create chain at step 0 (go), mark as running at index 0 only
        chain = cm.create_manifest([("go", "task"), ("check", "")], session_id="sess-4")
        cm.advance_step(chain.chain_id, new_status="running", step_index=0)
        # step[0]="running", step[1]="pending", current_step=0
        # Send blank input
        payload = json.dumps({"prompt": "", "sessionId": "sess-4"})
        self._mock_stdin(payload.encode())
        _ups.main()
        out, _ = capsys.readouterr()
        result = json.loads(out.strip())
        # Should inject prose instruction with /check
        assert "run /check" in result["hookSpecificOutput"]["additionalContext"]
        # Verify chain advanced: step[0] complete, step[1] running
        chain = cm.get_chain(chain.chain_id)
        assert chain.steps[0].status == "complete"
        assert chain.current_step == 1
        # Cleanup
        cm.clear_chain(chain.chain_id, force=True)
        del _os.environ["CHAIN_STEPS_DIR"]

    def test_blank_input_on_fresh_chain(self, capsys, tmp_path):
        """Blank input on a fresh chain (step[0] pending, dispatched by SlashCommand)
        correctly marks step[0] done and injects the next step."""
        import os as _os
        _os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        _ups._manifest_mod = None
        cm = _ups._get_manifest_module()
        # Create fresh chain — all steps pending, like after user types
        # "/go task, /check" where step[0] was dispatched by SlashCommand
        chain = cm.create_manifest([("go", "task"), ("check", "")], session_id="sess-fresh")
        # step[0]="pending", step[1]="pending", current_step=0
        assert chain.steps[0].status == "pending"
        # Send blank input
        payload = json.dumps({"prompt": "", "sessionId": "sess-fresh"})
        self._mock_stdin(payload.encode())
        _ups.main()
        out, _ = capsys.readouterr()
        result = json.loads(out.strip())
        # Should inject /check, not /go task
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "run /check" in ctx, f"Got: {ctx}"
        assert "run /go task" not in ctx, f"Should not inject first step: {ctx}"
        # Verify chain: step[0] complete, step[1] running, current_step=1
        chain = cm.get_chain(chain.chain_id)
        assert chain.steps[0].status == "complete", f"Step[0] should be complete: {chain.steps[0]}"
        assert chain.current_step == 1
        # Cleanup
        cm.clear_chain(chain.chain_id, force=True)
        del _os.environ["CHAIN_STEPS_DIR"]

    def test_blank_input_on_last_step_emits_complete(self, capsys, tmp_path):
        """Blank input on the last step signals chain complete."""
        import os as _os
        _os.environ["CHAIN_STEPS_DIR"] = str(tmp_path)
        _ups._manifest_mod = None
        cm = _ups._get_manifest_module()
        # Create 1-step chain, mark running
        chain = cm.create_manifest([("check", "")], session_id="sess-5")
        cm.advance_step(chain.chain_id, new_status="running")
        # Send blank input
        payload = json.dumps({"prompt": "", "sessionId": "sess-5"})
        self._mock_stdin(payload.encode())
        _ups.main()
        out, _ = capsys.readouterr()
        result = json.loads(out.strip())
        # Should emit chain complete
        assert "complete" in result["hookSpecificOutput"]["additionalContext"].lower()
        # Chain should be cleared
        chains = cm.list_chains(session_id="sess-5")
        assert len(chains) == 0
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
