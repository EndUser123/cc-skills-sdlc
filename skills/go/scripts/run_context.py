#!/usr/bin/env python3
"""Disk-authority run-identity reader for /go (contract: go.resume.v1).

Survives the session-compaction process boundary. Process env is a CACHE;
disk tiers (current-run_{terminal_id}.json → env.json → active-task mtime) are
AUTHORITY. On total resolution failure writes a `.unresolved-run_*.json` marker
and returns ``resolved=False`` so consumers start a fresh run instead of
crashing.

See plan-go-resume-binding.md (D1..D8) for the full contract.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

RunIdSource = Literal["env", "current-run", "env.json", "active-task-mtime", "unresolved"]
TidSource = Literal["canonical-env", "none"]

# ─── Canonical terminal_id loader ─────────────────────────────────────────────
# Frozen cross-plugin canonical source (search-research/core/terminal_id.py).
# We import it dynamically by absolute path; plugins stay independent (no
# cross-plugin package import). On any import failure we degrade to env-only
# detection via a local inline fallback that returns None when no signal is set.

_CANONICAL_PATH = Path(
    "P:/packages/.claude-marketplace/plugins/search-research/core/terminal_id.py"
)


def _load_canonical():
    try:
        spec = importlib.util.spec_from_file_location("_canonical_tid", _CANONICAL_PATH)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def canonical_terminal_id_from_env() -> str | None:
    """Env-signal terminal_id, or None when no signal is set.

    Delegates to the canonical module when importable; otherwise falls back to
    inline detection of the same env vars. None ⇒ caller treats as unresolved.
    """
    mod = _load_canonical()
    if mod is not None and hasattr(mod, "canonical_terminal_id_from_env"):
        return mod.canonical_terminal_id_from_env()
    # Inline fallback (keeps the frozen-source invariant: we did not mutate it).
    for var in ("CLAUDE_TERMINAL_ID", "WT_SESSION", "ITERM_SESSION_ID", "WEZTERM_SESSION_ID", "TMUX"):
        val = os.environ.get(var, "").strip()
        if val:
            return val if val.startswith("console_") else f"console_{val}"
    conemu = os.environ.get("ConEmuServerPID", "").strip()
    if conemu:
        return f"console_conemu_{conemu}"
    return None


def canonical_terminal_id() -> str:
    """Full canonical terminal_id INCLUDING the derived ppid-hash fallback.

    NOTE: delegates to the existing frozen canonical implementation in
    search-research/core/terminal_id.py via _load_canonical() (reuse, not
    re-implementation); the inline branch is graceful-degradation only, for
    when that source file cannot be imported.

    Writers (orchestrate.write_current_run, ensure_runtime_env, etc.) use THIS
    during a live /go invocation: ppid is stable within one session, so the
    fallback is safe for write-time keying. The post-compaction READER
    (resolve()) deliberately uses canonical_terminal_id_from_env() instead,
    because the ppid fallback is unstable across per-Bash-call steps.
    """
    mod = _load_canonical()
    if mod is not None and hasattr(mod, "canonical_terminal_id"):
        return mod.canonical_terminal_id()
    tid = canonical_terminal_id_from_env()
    if tid:
        return tid
    import hashlib
    return f"console_{hashlib.sha1(str(os.getppid()).encode()).hexdigest()[:16]}"


# ─── Plugin-tree guard (#939) ─────────────────────────────────────────────────
# /go's contract writes artifacts to the WORKTREE's .claude/ so state travels
# with the repo. But Path.cwd() resolves to the skill's own scripts/ dir when a
# script is hand-invoked or a test runs from there — polluting plugin SOURCE.
# Detect that degenerate case and fall back to the user-global artifacts dir.

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
_USER_ARTIFACTS = Path.home() / ".claude" / ".artifacts"


def _artifacts_base() -> Path:
    """Artifacts base dir: worktree .claude/.artifacts normally; user-global
    when CWD is inside the plugin's own source tree (prevents skill pollution)."""
    cwd = Path.cwd().resolve()
    try:
        cwd.relative_to(_PLUGIN_ROOT)
    except ValueError:
        return cwd / ".claude" / ".artifacts"  # normal worktree CWD
    return _USER_ARTIFACTS  # CWD inside plugin source — don't pollute it


# ─── RunContext ───────────────────────────────────────────────────────────────


_STALE_STATUSES = frozenset({"completed", "aborted", "failed"})
_ENV_RUN_ALIASES = ("GO_RUN_ID", "RUN_ID", "CLAUDE_GO_RUN_ID")


@dataclass
class RunContext:
    run_id: str
    terminal_id: str
    state_dir: Path
    source: RunIdSource
    resolved: bool
    tid_source: TidSource


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    """Load+validate a JSON object; any failure (missing/invalid/schema-broken) → None."""
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _resolve_terminal_id() -> tuple[str, TidSource]:
    tid = canonical_terminal_id_from_env()
    if tid:
        return tid, "canonical-env"
    return "", "none"


def resolve(state_dir_hint: Path | None = None) -> RunContext:
    """Resolve the active run identity. Disk is authority; env is cache.

    Precedence (D1): env (fast-path, cross-checked) → current-run → env.json →
    active-task mtime → unresolved marker.
    """
    terminal_id, tid_source = _resolve_terminal_id()

    # D8: no env-signal terminal_id ⇒ the canonical generator would fall back to
    # sha1(os.getppid()), which is unstable across /go's per-Bash-call steps and
    # would silently re-orphan. Treat as unresolved instead.
    if tid_source == "none":
        return _unresolved(terminal_id="", tid_source="none", hint=state_dir_hint)

    # Locate the state dir: explicit hint, else GO_STATE_DIR env, else the
    # canonical terminal-scoped artifact path.
    state_dir = _resolve_state_dir(state_dir_hint, terminal_id)

    # Delete any stale unresolved marker on a successful tier hit (D2 lifecycle).
    marker = state_dir / f".unresolved-run_{terminal_id}.json"

    # Tier 0 — env fast-path (D1 discriminator): return env ONLY when no
    # current-run pointer exists OR it agrees with the env value.
    env_run = next((os.environ.get(a) for a in _ENV_RUN_ALIASES if os.environ.get(a)), None)
    cr_data = _read_current_run(state_dir, terminal_id)
    if env_run and (cr_data is None or str(cr_data.get("run_id", "")) == env_run):
        _safe_delete(marker)
        return RunContext(env_run, terminal_id, state_dir, "env", True, tid_source)

    # Tier 1 — current-run (D7: stale status falls through).
    if cr_data is not None:
        run_id = str(cr_data.get("run_id", "")).strip()
        status = str(cr_data.get("status", "")).strip()
        if run_id and status not in _STALE_STATUSES:
            _safe_delete(marker)
            return RunContext(run_id, terminal_id, _state_dir_from_data(cr_data, state_dir),
                              "current-run", True, tid_source)

    # Tier 2 — env.json fallback.
    ej_data = _safe_load_json(state_dir / "env.json")
    if ej_data is not None:
        run_id = str(ej_data.get("RUN_ID") or ej_data.get("GO_RUN_ID") or "").strip()
        if run_id:
            sd = _state_dir_from_env_json(ej_data, state_dir)
            _safe_delete(marker)
            return RunContext(run_id, terminal_id, sd, "env.json", True, tid_source)

    # Tier 3 — most-recent active-task mtime.
    run_id = _most_recent_active_task_run_id(state_dir)
    if run_id:
        _safe_delete(marker)
        return RunContext(run_id, terminal_id, state_dir, "active-task-mtime", True, tid_source)

    # Total failure → unresolved marker, never crash.
    return _unresolved(terminal_id=terminal_id, tid_source=tid_source, hint=state_dir)


def _read_current_run(state_dir: Path, terminal_id: str) -> dict[str, Any] | None:
    """Read current-run_{terminal_id}.json then current-run.json; validate."""
    for candidate in (state_dir / f"current-run_{terminal_id}.json", state_dir / "current-run.json"):
        data = _safe_load_json(candidate)
        if data is not None and isinstance(data.get("run_id"), str) and data["run_id"].strip():
            return data
    return None


def _state_dir_from_data(cr_data: dict[str, Any], fallback: Path) -> Path:
    raw = cr_data.get("go_state_dir")
    if isinstance(raw, str) and raw.strip():
        return Path(raw)
    return fallback


def _state_dir_from_env_json(ej_data: dict[str, Any], fallback: Path) -> Path:
    raw = ej_data.get("GO_STATE_DIR")
    if isinstance(raw, str) and raw.strip():
        return Path(raw)
    return fallback


def _resolve_state_dir(hint: Path | None, terminal_id: str) -> Path:
    if hint is not None:
        return Path(hint).resolve()
    env_sd = os.environ.get("GO_STATE_DIR", "").strip()
    if env_sd:
        return Path(env_sd).resolve()
    return (_artifacts_base() / terminal_id / "go").resolve()


def _most_recent_active_task_run_id(state_dir: Path) -> str:
    candidates = sorted(
        state_dir.glob("active-task_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for cand in candidates:
        data = _safe_load_json(cand)
        if data is None:
            continue
        # Filename carries the run_id stem: active-task_{run_id}.json
        stem = cand.stem.removeprefix("active-task_")
        if stem:
            return stem
    return ""


def _safe_delete(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _unresolved(terminal_id: str, tid_source: TidSource, hint: Path | None) -> RunContext:
    state_dir = _resolve_state_dir(hint, terminal_id) if terminal_id else (Path(hint).resolve() if hint else _artifacts_base())
    marker_name = f".unresolved-run_{terminal_id}.json" if terminal_id else ".unresolved-run_unk.json"
    payload = {
        "reason": "all-resolution-tiers-missed",
        "terminal_id": terminal_id,
        "tid_source": tid_source,
    }
    try:
        _atomic_write_json(state_dir / marker_name, payload)
    except OSError:
        pass  # (l) marker-write failure must never crash the consumer
    return RunContext("", terminal_id, state_dir, "unresolved", False, tid_source)


if __name__ == "__main__":
    # ponytail: smoke self-check — `python run_context.py` prints the resolved ctx.
    ctx = resolve()
    print(f"resolved={ctx.resolved} run_id={ctx.run_id!r} tid={ctx.terminal_id!r} "
          f"source={ctx.source} tid_source={ctx.tid_source}")
    sys.exit(0)
