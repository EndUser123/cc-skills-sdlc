#!/usr/bin/env python3
"""
Shared Stop gate evaluation — skill-agnostic, config-driven.

Exit semantics:
  2 = blocking (one or more hard phases missing/failed)
  1 = warning only (all hard satisfied, advisory missing)
  0 = clean (all hard satisfied; advisory either satisfied or allowed to skip)

Usage:
  config = load_config_for_skill("code-ef")   # or "go" (backward compat: "code_v4.0", "go-ef", "go_v3.0")
  exit_code, message = evaluate_gates("code-ef", config, os.environ)
  if message:
      print(message, file=sys.stderr)
  sys.exit(exit_code)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Type alias for the config structure (documented below)
EnforceConfig = list[dict[str, Any]]  # see load_config_for_skill() for shape


# ---------------------------------------------------------------------------
# Config schema (documented, not enforced via class to stay dependency-free)
# ---------------------------------------------------------------------------
"""
Each phase in the config is a dict with these fields:

  name        str   — phase identifier, e.g. "verified", "consumer_contract_precheck"
  gate_type   str   — "hard" or "advisory"
  evidence    dict  — how to check this phase:
    type        str  — "ledger_only" | "file_flag" | "json_file" | "command"
    # ledger_only
    #   (no additional fields needed)
    #
    # file_flag
    #   files    list[str]  — list of file paths (glob-style patterns supported,
    #                          and {run_id} / {terminal_id} are substituted from env)
    #   all      bool       — True means ALL files must exist; False means ANY one suffices
    #
    # json_file
    #   path     str        — JSON file path ({run_id} substitution)
    #   key      str        — top-level key to read
    #   expected str|int|bool — expected value (exact match)
    #
    # command
    #   cmd      list[str]  — command + args
    #   expected int|list[int] — expected exit code(s); non-match = failure
    #
  fast_mode_behavior  str  — optional: "skip_allowed" | "skip_forbidden"
                          — only relevant when CLAUDE_CODE_FAST_MODE is set.
                          Default: "skip_forbidden" (hard phases never skipped).
"""

# ---------------------------------------------------------------------------
# Evidence checkers
# ---------------------------------------------------------------------------

def _check_ledger(skill_id: str, phase_name: str, session_id: str | None = None) -> bool:
    from .phase_ledger import read_phase_ledger
    ledger = read_phase_ledger(skill_id, session_id)
    if ledger is None:
        return False
    entry = ledger.get("phases", {}).get(phase_name, {})
    return entry.get("done") is True


def _evidence_type(phase: dict[str, Any]) -> str:
    """Return the evidence type for a phase (for cold-start heuristic)."""
    ev = phase.get("evidence", {})
    if isinstance(ev, list):
        return ev[0].get("type", "ledger_only") if ev else "ledger_only"
    return ev.get("type", "ledger_only")


def _check_file_flags(
    files: list[str],
    require_all: bool,
    run_id: str,
    terminal_id: str,
) -> bool:
    base = Path.home()
    def expand(pattern: str) -> Path:
        # Resolve relative paths from home directory
        p = pattern.replace("{run_id}", run_id).replace("{terminal_id}", terminal_id)
        path = Path(p)
        return path if path.is_absolute() else base / p

    expanded = [expand(f) for f in files]
    if require_all:
        return all(f.exists() for f in expanded)
    else:
        return any(f.exists() for f in expanded)


def _check_json_file(
    path: str,
    key: str,
    expected: str | int | bool,
    run_id: str,
) -> bool:
    try:
        full_path = Path(path.replace("{run_id}", run_id).replace("{terminal_id}", os.environ.get("CLAUDE_TERMINAL_ID", "")))
        if not full_path.exists():
            return False
        data = json.loads(full_path.read_text(encoding="utf-8"))
        actual = data.get(key)
        return actual == expected
    except Exception:
        return False


def _check_command(
    cmd: list[str],
    expected: int | list[int],
    cwd: str | None,
) -> bool:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or None,
        )
        codes = expected if isinstance(expected, list) else [expected]
        return result.returncode in codes
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate_gates(
    skill_id: str,
    config: EnforceConfig,
    env: dict[str, str],
) -> tuple[int, str]:
    """
    Evaluate all phases in config against evidence sources.

    Returns (exit_code, stderr_message):
      exit 2 + message  — hard gate(s) missing/failed
      exit 1 + message  — advisory missing, all hard satisfied
      exit 0 + ""       — clean
    """
    run_id = env.get("RUN_ID", env.get("CLAUDE_GO_RUN_ID", ""))
    session_id = env.get("CLAUDE_SESSION_ID")
    terminal_id = env.get("CLAUDE_TERMINAL_ID", "")
    fast_mode = env.get("CLAUDE_CODE_FAST_MODE", "").lower() in ("1", "true", "yes")

    # Manual override: set GO_SKIP=1 to bypass all go enforcement.
    # GO_EF_SKIP remains accepted for older local sessions.
    if env.get("GO_SKIP") == "1" or env.get("GO_EF_SKIP") == "1":
        return 0, ""

    hard_missing: list[str] = []
    advisory_missing: list[str] = []
    has_any_evidence = False

    # Cold-start heuristic: if any hard gate uses ledger_only evidence and no ledger
    # exists, the skill has never run — return exit 0 conservatively.
    # go_v3.0 hard gates use file_flag/json_file evidence, so they can fail properly.
    from .phase_ledger import read_phase_ledger
    ledger = read_phase_ledger(skill_id, session_id)
    any_hard_gate_uses_ledger = any(
        p["gate_type"] == "hard" and _evidence_type(p) == "ledger_only"
        for p in config
    )
    if ledger is None and any_hard_gate_uses_ledger:
        return 0, ""

    for phase in config:
        name = phase["name"]
        gate_type = phase["gate_type"]
        evidence = phase.get("evidence", {})
        fast_behavior = phase.get("fast_mode_behavior", "skip_forbidden")

        # Fast mode: skip phases where fast_mode_behavior == "skip_allowed"
        if fast_mode and fast_behavior == "skip_allowed":
            continue

        # Advisory phases with ledger_only evidence are placeholders.
        # Treat them as always-satisfied so they don't generate false warnings.
        # (If/when these phases get real evidence, update their config entry.)
        if gate_type == "advisory" and _evidence_type(phase) == "ledger_only":
            has_any_evidence = True
            continue

        passed = _evaluate_phase(skill_id, phase, run_id, terminal_id, env, session_id)

        if not passed:
            if gate_type == "hard":
                hard_missing.append(name)
            else:
                advisory_missing.append(name)
        else:
            has_any_evidence = True

    # Build messages
    lines: list[str] = []

    if hard_missing:
        lines.append(
            f"BLOCKED: {skill_id} — missing {len(hard_missing)} hard gate(s): "
            f"{', '.join(hard_missing)}"
        )
        lines.append("Run the skill to completion, or use --fast if supported.")

    if advisory_missing:
        lines.append(
            f"WARNING (advisory): {skill_id} — missing {len(advisory_missing)} "
            f"advisory phase(s): {', '.join(advisory_missing)}"
        )
        lines.append("These do not block completion but should be reviewed.")

    message = "\n".join(lines)

    if hard_missing:
        return 2, message
    if advisory_missing:
        return 1, message
    if not has_any_evidence:
        return 0, ""
    return 0, ""


def _evaluate_phase(
    skill_id: str,
    phase: dict[str, Any],
    run_id: str,
    terminal_id: str,
    env: dict[str, str],
    session_id: str | None = None,
) -> bool:
    evidence = phase.get("evidence", {})

    # Normalize: evidence can be a dict (single) or a list (any-of-them)
    items: list[dict[str, Any]] = evidence if isinstance(evidence, list) else [evidence]

    # For a phase with multiple evidence sources: ANY one passing = phase passed
    for ev in items:
        ev_type = ev.get("type", "ledger_only")

        if ev_type == "ledger_only":
            if _check_ledger(skill_id, phase["name"], session_id):
                return True

        elif ev_type == "file_flag":
            files = ev.get("files", [])
            require_all = ev.get("all", False)
            if _check_file_flags(files, require_all, run_id, terminal_id):
                return True

        elif ev_type == "json_file":
            if _check_json_file(
                ev.get("path", ""),
                ev.get("key", ""),
                ev.get("expected"),
                run_id,
            ):
                return True

        elif ev_type == "command":
            cwd = ev.get("cwd")
            if _check_command(
                ev.get("cmd", []),
                ev.get("expected", 0),
                cwd,
            ):
                return True

    # None of the evidence sources passed
    return False


# ---------------------------------------------------------------------------
# Config loading helpers
# ---------------------------------------------------------------------------

def load_config_for_skill(skill_id: str) -> EnforceConfig:
    """
    Load enforce config for a skill_id.
    Looks up from the enforce/configs/ package dict, or raises KeyError.

    Configs are defined as Python dicts in enforce/configs/__init__.py
    to keep the schema explicit and type-checkable without extra deps.
    """
    from enforce.configs import ENFORCE_CONFIGS
    if skill_id not in ENFORCE_CONFIGS:
        raise KeyError(f"No enforce config found for skill_id={skill_id!r}. "
                       f"Available: {list(ENFORCE_CONFIGS)}")
    return ENFORCE_CONFIGS[skill_id]
