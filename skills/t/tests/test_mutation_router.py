#!/usr/bin/env python3
"""Tests for /t skill router mutation intent detection."""

import importlib.util
import sys
from pathlib import Path

T_SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(T_SKILL_DIR))

from router import detect_mode_from_prompt  # noqa: E402


def _load_t_main():
    spec = importlib.util.spec_from_file_location("t_skill_main", T_SKILL_DIR / "__main__.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_router_detects_mutation_keyword() -> None:
    """The literal word 'mutation' routes to mutation mode."""
    assert detect_mode_from_prompt("mutation score for skill_guard") == "mutation"


def test_router_detects_mutmut() -> None:
    """The mutmut tool name routes to mutation mode."""
    assert detect_mode_from_prompt("run mutmut on inference.py") == "mutation"


def test_router_detects_survived_keyword() -> None:
    """The 'survived' keyword routes to mutation mode."""
    assert detect_mode_from_prompt("which mutants survived?") == "mutation"


def test_router_detects_fault_detection_phrase() -> None:
    """The phrase 'fault detection' routes to mutation mode."""
    assert detect_mode_from_prompt("test strength / fault detection") == "mutation"


def test_router_detects_equivalent_mutants() -> None:
    """The phrase 'equivalent mutants' routes to mutation mode."""
    assert detect_mode_from_prompt("review the equivalent mutants") == "mutation"


def test_router_mutation_takes_precedence_over_discovery() -> None:
    """Mutation beats discovery when both keywords are present."""
    assert detect_mode_from_prompt("what is the mutation coverage report?") == "mutation"


def test_router_mutation_takes_precedence_over_bisect() -> None:
    """Mutation beats bisect when both keywords are present."""
    assert detect_mode_from_prompt("did mutmut break after the refactor?") == "mutation"


def test_router_still_supports_existing_modes() -> None:
    """Adding mutation keywords did not regress other modes."""
    assert detect_mode_from_prompt("what tests exist?") == "discovery"
    assert detect_mode_from_prompt("when did this break?") == "bisect"
    assert detect_mode_from_prompt("run tests") == "execution"
    assert detect_mode_from_prompt("comprehensive analysis") == "comprehensive"
    assert detect_mode_from_prompt("") == "smart"


def test_main_dispatches_mutation_mode(monkeypatch) -> None:
    """The real /t entrypoint exposes mutation mode."""
    t_main = _load_t_main()
    monkeypatch.setattr(t_main, "_run_execution_mode", lambda *_args: 99)
    monkeypatch.setattr(t_main, "_run_mutation_mode", lambda *_args: 42, raising=False)

    assert t_main.main(mode="mutation") == 42
