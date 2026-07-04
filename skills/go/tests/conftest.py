"""Per-test isolation for /go artifacts.

ARTIFACTS_ROOT defaults to the live P:/.claude/.artifacts at module import.
Without isolation, tests that call write_session_pointer() pollute the real
go-sessions/ pointer store with pointers bound to pytest tmp_paths, which the
live go_continuation_gate then reads on every Stop and blocks on.

Scope GO_ARTIFACTS_ROOT to a per-test tmp_path for both:
  - the already-imported orchestrate module global (monkeypatch.setattr), and
  - the env var (monkeypatch.setenv) for any subprocess gate invocation.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_go_artifacts(monkeypatch, tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    monkeypatch.setenv("GO_ARTIFACTS_ROOT", str(artifacts))
    mod = pytest.importorskip("go_orchestrate")
    monkeypatch.setattr(mod, "ARTIFACTS_ROOT", artifacts)
    yield
