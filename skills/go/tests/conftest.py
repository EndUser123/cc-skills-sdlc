"""Per-test isolation for /go artifacts.

ARTIFACTS_ROOT defaults to the live P:/.claude/.artifacts at module import.
Without isolation, tests that call write_session_pointer() pollute the real
go-sessions/ pointer store with pointers bound to pytest tmp_paths, which the
live go_continuation_gate then reads on every Stop and blocks on.

Scope GO_ARTIFACTS_ROOT to a per-test tmp_path for both:
  - the already-imported orchestrate module global (monkeypatch.setattr), and
  - the env var (monkeypatch.setenv) for any subprocess gate invocation.
"""
import os
import pathlib
import sys

import pytest

# Two import conventions coexist in this suite: bare `import orchestrate`
# (needs scripts/ on sys.path) and `from skills.go.scripts.X import Y` (needs
# the plugin root on sys.path so `skills` resolves as a package). Add both.
_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SCRIPTS = _PLUGIN_ROOT / "skills" / "go" / "scripts"
for _p in (str(_SCRIPTS), str(_PLUGIN_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture(autouse=True)
def _isolate_go_artifacts(monkeypatch, tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    monkeypatch.setenv("GO_ARTIFACTS_ROOT", str(artifacts))
    mod = pytest.importorskip("orchestrate")
    monkeypatch.setattr(mod, "ARTIFACTS_ROOT", artifacts)
    yield


@pytest.fixture(autouse=True)
def _isolate_go_runtime_env():
    """Snapshot/restore os.environ around each test.

    ensure_runtime_env (orchestrate.py:437-452) writes CLAUDE_TERMINAL_ID,
    TERMINAL_ID, RUN_ID, GO_RUN_ID, and GO_STATE_DIR via direct ``os.environ[k]=``
    — NOT monkeypatch — so the writes persist across the whole pytest session.
    A later subprocess test that does ``env = os.environ.copy()`` and overrides
    only ``RUN_ID`` inherits a stale ``GO_RUN_ID``; run_context.resolve() checks
    ``GO_RUN_ID`` before ``RUN_ID`` (alias order in _ENV_RUN_ALIASES) and
    resolves the wrong run_id -> "no active task". monkeypatch cannot undo
    these because the writes are inside the SUT. This snapshot/restore is the
    standard pytest pattern for "SUT mutates os.environ directly".
    """
    saved = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture(scope="session", autouse=True)
def _assert_no_real_store_leak():
    # Suite-level invariant: after the whole /go suite, the REAL go-sessions
    # pointer store must hold no test-pollution pointer. Catches any writer
    # that bypasses the per-test GO_ARTIFACTS_ROOT isolation (the run-vp-tel
    # incident class — see memory: test-module-alias-isolation-leak).
    # Precise signature: a pointer whose go_state_dir is under the OS temp dir.
    # Real /go runs write under .claude/.artifacts, never temp, so concurrent
    # real runs in other terminals can't flake this.
    import json
    import tempfile

    yield
    real_store = pathlib.Path("P:/.claude/.artifacts/go-sessions")
    if not real_store.is_dir():
        return
    tmp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    leaks = []
    for p in sorted(real_store.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            leaks.append(f"{p.name} (unparseable)")
            continue
        sd = pathlib.Path(str(data.get("go_state_dir", ""))).resolve()
        if sd == tmp_root or tmp_root in sd.parents:
            leaks.append(f"{p.name} -> {sd}")
    assert not leaks, (
        "go-sessions pointer store polluted by tests (pointers under temp dir): "
        + ", ".join(leaks)
    )
