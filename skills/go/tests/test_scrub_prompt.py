#!/usr/bin/env python3
"""Tests for the /go prompt secret scrubber (SEC-2 / TASK-001.2).

Layer map:
  - unit: pure scrub() function (redaction, idempotency, passthrough, fail-closed)
  - integration smoke: load_or_create_task with a planted sk-ant- token; the raw
    secret MUST NOT appear in active-task_{run_id}.json. Proves the scrubber is
    wired at the single ingestion chokepoint so no downstream field leaks it.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys


def _load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PACKAGE = pathlib.Path(__file__).resolve().parents[1]
_SCRUB = _load_module("go_scrub_prompt", PACKAGE / "scripts" / "scrub_prompt.py")
_ORCHESTRATE = _load_module("go_orchestrate", PACKAGE / "scripts" / "orchestrate.py")


# ---------------------------------------------------------------------------
# Unit: pure scrub() function
# ---------------------------------------------------------------------------

def test_scrub_redacts_sk_ant_token():
    assert _SCRUB.scrub("key=sk-ant-DEADBEEF1234567890 then work") == (
        "key=[REDACTED:anthropic-key] then work"
    )


def test_scrub_redacts_sk_cp_and_sk_proj_tokens():
    assert "[REDACTED:anthropic-key]" in _SCRUB.scrub("cp=sk-cp-AAAABBBBCCCCDDDD")
    assert "[REDACTED:anthropic-key]" in _SCRUB.scrub("proj=sk-proj-WXYZ1234abcd5678")


def test_scrub_normal_prompt_unchanged():
    prompt = "Fix the failing tests in the auth module, then run pytest -q."
    assert _SCRUB.scrub(prompt) == prompt


def test_scrub_is_idempotent():
    once = _SCRUB.scrub("token sk-ant-DEADBEEF1234567890 here")
    twice = _SCRUB.scrub(once)
    assert once == twice


def test_scrub_empty_and_short_inputs_passthrough():
    assert _SCRUB.scrub("") == ""
    assert _SCRUB.scrub("hi") == "hi"


# ---------------------------------------------------------------------------
# Integration smoke: wired into load_or_create_task
# ---------------------------------------------------------------------------

def test_scrubbed_prompt_does_not_leak_into_active_task(tmp_path, monkeypatch):
    """SEC-2 smoke: a planted sk-ant- in args.prompt must not reach active-task.json."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    run_id = "scrub-smoke"
    secret = "sk-ant-DEADBEEF1234567890"
    args = argparse.Namespace(
        prompt=f"do work with key {secret} please",
        scope_in=[],
        forbidden=[],
        validation=False,
        recon_only=True,      # skip the recon-before-dispatch gate
        preflight_only=False,
    )
    # Don't pollute the real artifacts root during the test.
    monkeypatch.setattr(_ORCHESTRATE, "write_session_pointer", lambda *a, **k: None)

    _ORCHESTRATE.load_or_create_task(args, state_dir, run_id)

    active = (state_dir / f"active-task_{run_id}.json").read_text(encoding="utf-8")
    assert secret not in active, "raw secret leaked into active-task.json"
    assert "[REDACTED:anthropic-key]" in active, "scrubber did not redact in active-task.json"
