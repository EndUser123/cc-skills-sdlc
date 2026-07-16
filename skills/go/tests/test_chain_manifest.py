"""Tests for chain_manifest.py — persistent chain-state manifest."""

import json
import time
from pathlib import Path

import pytest

# Dynamic import matching existing go test pattern (orchestrate dispatch tests)
import importlib.util
import pathlib as _pathlib
import sys as _sys

_PACKAGE = _pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "chain_manifest", _PACKAGE / "scripts" / "chain_manifest.py"
)
_cm = importlib.util.module_from_spec(_spec)
_sys.modules["chain_manifest"] = _cm
_spec.loader.exec_module(_cm)

ChainState = _cm.ChainState
ChainStep = _cm.ChainStep
create_manifest = _cm.create_manifest
get_chain = _cm.get_chain
advance_step = _cm.advance_step
clear_chain = _cm.clear_chain
list_chains = _cm.list_chains

RUN_ID = "87654321-4321-4432-8432-210987654321"


class TestChainStep:
    """ChainStep dataclass serialization."""

    def test_to_dict_round_trips(self):
        step = ChainStep(index=0, skill="go", args="task", status="running")
        data = step.to_dict()
        restored = ChainStep.from_dict(data)
        assert restored.index == step.index
        assert restored.skill == step.skill
        assert restored.args == step.args
        assert restored.status == step.status

    def test_default_status_is_pending(self):
        step = ChainStep(index=0, skill="check")
        assert step.status == "pending"


class TestChainState:
    """ChainState dataclass serialization and validation."""

    def test_to_dict_round_trips(self):
        chain = ChainState(
            chain_id=RUN_ID,
            session_id="session-1",
            steps=[ChainStep(index=0, skill="go", args="task")],
            current_step=0,
            origin_command="/go task, /check",
        )
        data = chain.to_dict()
        restored = ChainState.from_dict(data)
        assert restored.chain_id == chain.chain_id
        assert len(restored.steps) == 1
        assert restored.steps[0].skill == "go"

    def test_validate_valid_chain(self):
        chain = ChainState(chain_id=RUN_ID, session_id="s1", steps=[ChainStep(index=0, skill="go")])
        assert chain.validate() == []

    def test_validate_missing_chain_id(self):
        chain = ChainState(session_id="s1", steps=[ChainStep(index=0, skill="go")])
        errors = chain.validate()
        assert any("chain_id" in e for e in errors)

    def test_validate_empty_steps(self):
        chain = ChainState(chain_id=RUN_ID, session_id="s1")
        errors = chain.validate()
        assert any("steps" in e for e in errors)

    def test_validate_bad_step_index(self):
        chain = ChainState(chain_id=RUN_ID, session_id="s1",
                           steps=[ChainStep(index=1, skill="go")])
        errors = chain.validate()
        assert any("index" in e for e in errors)

    def test_validate_bad_current_step(self):
        chain = ChainState(chain_id=RUN_ID, session_id="s1",
                           steps=[ChainStep(index=0, skill="go")],
                           current_step=5)
        errors = chain.validate()
        assert any("current_step" in e for e in errors)

    def test_validate_invalid_status(self):
        chain = ChainState(chain_id=RUN_ID, session_id="s1",
                           steps=[ChainStep(index=0, skill="go")],
                           status="unknown_status")
        errors = chain.validate()
        assert any("status" in e for e in errors)


class TestCreateManifest:
    """create_manifest() — atomic exclusive write."""

    def test_creates_valid_manifest(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task"), ("check", "")])
        assert chain.chain_id
        assert len(chain.steps) == 2
        assert chain.steps[0].skill == "go"
        assert chain.steps[1].skill == "check"
        assert chain.status == "in_progress"
        clear_chain(chain.chain_id, force=True)

    def test_exclusive_create_prevents_duplicate(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        create_manifest([("go", "task")], chain_id=RUN_ID)
        with pytest.raises(FileExistsError):
            create_manifest([("go", "task")], chain_id=RUN_ID)
        clear_chain(RUN_ID, force=True)

    def test_empty_steps_raises_valueerror(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        with pytest.raises(ValueError, match="non-empty"):
            create_manifest([])

    def test_single_step_chain(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("check", "--deep")])
        assert len(chain.steps) == 1
        assert chain.steps[0].args == "--deep"
        clear_chain(chain.chain_id, force=True)


class TestGetChain:
    """get_chain() — read and validate."""

    def test_reads_existing_chain(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        created = create_manifest([("go", "task")])
        loaded = get_chain(created.chain_id)
        assert loaded.chain_id == created.chain_id
        assert loaded.steps[0].skill == "go"
        clear_chain(created.chain_id, force=True)

    def test_missing_chain_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            get_chain("00000000-0000-0000-0000-000000000000")

    def test_corrupted_chain_raises_valueerror(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        bad_id = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
        path = _PACKAGE / "tests" / f"{bad_id}.json"
        path.write_text('{"schema_version": "wrong"}', encoding="utf-8")
        with pytest.raises(ValueError, match="Corrupted"):
            get_chain(bad_id)
        path.unlink(missing_ok=True)


class TestAdvanceStep:
    """advance_step() — progress chain forward."""

    def test_advances_to_next_step(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task"), ("check", "")])
        assert chain.current_step == 0
        updated = advance_step(chain.chain_id)
        assert updated.current_step == 1
        assert updated.steps[0].status == "complete"
        assert updated.steps[1].status == "running"
        clear_chain(chain.chain_id, force=True)

    def test_last_step_completes_chain(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task")])
        updated = advance_step(chain.chain_id)
        assert updated.status == "complete"
        assert updated.steps[0].status == "complete"
        clear_chain(chain.chain_id, force=True)

    def test_failed_step_marks_chain_failed(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task")])
        updated = advance_step(chain.chain_id, new_status="failed")
        assert updated.status == "failed"
        clear_chain(chain.chain_id, force=True)

    def test_advance_already_complete_raises(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task")])
        advance_step(chain.chain_id)
        with pytest.raises(ValueError, match="already"):
            advance_step(chain.chain_id)
        clear_chain(chain.chain_id, force=True)

    def test_advance_with_explicit_index(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task"), ("verify", ""), ("check", "")])
        updated = advance_step(chain.chain_id, step_index=1)
        assert updated.steps[1].status == "complete"
        assert updated.steps[2].status == "running"
        assert updated.current_step == 2
        clear_chain(chain.chain_id, force=True)


class TestClearChain:
    """clear_chain() — cleanup with TTL."""

    def test_force_removes_chain(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task")])
        assert clear_chain(chain.chain_id, force=True)

    def test_within_ttl_does_not_remove(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        chain = create_manifest([("go", "task")])
        assert not clear_chain(chain.chain_id, ttl_seconds=86400)
        clear_chain(chain.chain_id, force=True)

    def test_missing_chain_returns_false(self):
        assert not clear_chain("nonexistent")


class TestListChains:
    """list_chains() — query existing manifests."""

    def test_filters_by_session(self, monkeypatch):
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", str(_PACKAGE / "tests"))
        c1 = create_manifest([("go", "a")], session_id="session-A")
        c2 = create_manifest([("check", "")], session_id="session-B")
        chains_a = list_chains(session_id="session-A")
        assert all(c.session_id == "session-A" for c in chains_a)
        clear_chain(c1.chain_id, force=True)
        clear_chain(c2.chain_id, force=True)

    def test_empty_dir_returns_empty(self, monkeypatch):
        empty = str(_PACKAGE / "tests" / "_empty")
        monkeypatch.setattr("chain_manifest.CHAIN_STEPS_DIR", empty)
        assert list_chains() == []
