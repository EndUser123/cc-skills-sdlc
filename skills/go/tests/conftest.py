"""Per-test isolation for /go artifacts.

ARTIFACTS_ROOT defaults to the live P:/.claude/.artifacts at module import.
Without isolation, tests that call write_session_pointer() pollute the real
go-sessions/ pointer store with pointers bound to pytest tmp_paths, which the
live go_continuation_gate then reads on every Stop and blocks on.

Scope GO_ARTIFACTS_ROOT to a per-test tmp_path for both:
  - the already-imported orchestrate module global (monkeypatch.setattr), and
  - the env var (monkeypatch.setenv) for any subprocess gate invocation.
"""
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
