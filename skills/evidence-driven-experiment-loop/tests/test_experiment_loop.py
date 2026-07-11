import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "experiment_loop.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        text=True,
        capture_output=True,
    )


def base(tmp_path):
    path = tmp_path / "s.json"
    result = run(
        "init",
        "--state",
        path,
        "--objective",
        "compare",
        "--workspace",
        tmp_path,
    )
    assert result.returncode == 0
    return path


def load(path):
    return json.loads(path.read_text())


def save(path, state):
    path.write_text(json.dumps(state))


def valid(tmp_path):
    path = base(tmp_path)
    state = load(path)
    state["authority_paths"] = ["."]
    state["lifecycle_state"] = "offline_attribution"
    state["headline_metric"] = "latency_ms"
    state["claims"] = [{
        "type": "verified_fact",
        "text": "x",
        "action_allowed": "use as offline evidence",
        "evidence": "artifact.txt",
    }]
    save(path, state)
    return path


def test_init_defaults(tmp_path):
    state = load(base(tmp_path))
    assert state["schema_version"] == 1
    assert state["lifecycle_state"] == "authority_check"
    assert state["handoff_status"] == "in_progress"


def test_valid_offline_state(tmp_path):
    assert run("validate", "--state", valid(tmp_path)).returncode == 0


def test_documented_minimal_offline_shape_validates(tmp_path):
    save_path = tmp_path / "documented.json"
    save(
        save_path,
        {
            "schema_version": 1,
            "objective": "Compare two offline parsers",
            "workspace": ".",
            "authority_paths": ["."],
            "headline_metric": "latency_ms",
            "historical_best": None,
            "current_control": "parser-a",
            "candidate": "parser-b",
            "lifecycle_state": "offline_attribution",
            "allowed_actions": ["inspect offline artifacts"],
            "forbidden_actions": ["live benchmark"],
            "claims": [],
            "gates": {},
            "verification": {"status": "pending"},
            "adversarial_review": {"status": "pending"},
            "next_action": "collect offline evidence",
            "handoff_status": "in_progress",
        },
    )
    assert run("validate", "--state", save_path).returncode == 0


def test_invalid_enums(tmp_path):
    path = valid(tmp_path)
    state = load(path)
    state["lifecycle_state"] = "bad"
    save(path, state)
    assert run("validate", "--state", path).returncode != 0


@pytest.mark.parametrize(
    "action",
    [
        "live benchmark",
        "run live benchmark",
        "launch telemetry validation",
        "execute throughput validation",
        "start production deployment",
        "perform live comparison",
        "deploy production change",
        "modify production config",
        "change live telemetry",
        "production changes",
    ],
)
def test_explicit_live_actions_require_authorization(tmp_path, action):
    path = valid(tmp_path)
    state = load(path)
    state["allowed_actions"] = [action]
    save(path, state)
    result = run("validate", "--state", path)
    assert result.returncode != 0
    assert "live_authorization" in result.stdout


@pytest.mark.parametrize(
    "action",
    ["analyze benchmark artifacts", "review throughput evidence", "inspect production logs"],
)
def test_offline_actions_do_not_require_authorization(tmp_path, action):
    path = valid(tmp_path)
    state = load(path)
    state["allowed_actions"] = [action]
    save(path, state)
    assert run("validate", "--state", path).returncode == 0


def test_premature_ready_rejected(tmp_path):
    path = valid(tmp_path)
    state = load(path)
    state["handoff_status"] = "ready_for_parent_review"
    save(path, state)
    result = run("validate", "--state", path)
    assert result.returncode != 0
    assert "verification" in result.stdout


def test_ready_status_only_is_rejected(tmp_path):
    path = valid(tmp_path)
    state = load(path)
    state["handoff_status"] = "ready_for_parent_review"
    state["verification"] = {"status": "complete"}
    state["adversarial_review"] = {"status": "complete"}
    save(path, state)
    result = run("validate", "--state", path)
    assert result.returncode != 0
    assert "evidence" in result.stdout


def test_fully_evidenced_review_is_accepted(tmp_path):
    path = valid(tmp_path)
    state = load(path)
    state["handoff_status"] = "ready_for_parent_review"
    state["verification"] = {"status": "completed", "evidence": ["run.json"]}
    state["adversarial_review"] = {
        "status": "complete",
        "load_bearing_claims": ["claim-1"],
        "falsification_attempts": ["attempt-1"],
        "result": "No blocking contradiction found",
    }
    save(path, state)
    assert run("validate", "--state", path).returncode == 0


@pytest.mark.parametrize("authority_path", [3, None, "", "   "])
def test_invalid_authority_path_entries_are_actionable(tmp_path, authority_path):
    path = valid(tmp_path)
    state = load(path)
    state["authority_paths"] = [authority_path]
    save(path, state)
    result = run("validate", "--state", path)
    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr
    assert "authority_paths[0]" in result.stdout


@pytest.mark.parametrize(
    ("claim", "message"),
    [
        ({"type": "verified_fact", "text": "x", "action_allowed": "use"}, "evidence"),
        ({"type": "inference", "text": "x", "action_allowed": "use"}, "falsifier"),
        ({"type": "unsupported", "text": "x", "action_allowed": "use"}, "not eligible"),
        ({"type": "verified_fact", "action_allowed": "use", "evidence": "x"}, "text"),
        ({"type": "verified_fact", "text": "x", "evidence": "x"}, "action_allowed"),
    ],
)
def test_claim_requirements_are_rejected(tmp_path, claim, message):
    path = valid(tmp_path)
    state = load(path)
    state["claims"] = [claim]
    save(path, state)
    result = run("validate", "--state", path)
    assert result.returncode == 1
    assert message in result.stdout


def test_unsupported_claim_type(tmp_path):
    path = valid(tmp_path)
    state = load(path)
    state["claims"] = [{"type": "made_up"}]
    save(path, state)
    assert "unsupported" in run("validate", "--state", path).stdout


def test_malformed_types_report_errors(tmp_path):
    path = valid(tmp_path)
    state = load(path)
    state.update(
        {
            "schema_version": "1",
            "objective": "",
            "authority_paths": {},
            "gates": [],
            "headline_metric": 3,
        }
    )
    save(path, state)
    result = run("validate", "--state", path)
    assert result.returncode != 0
    assert "schema_version" in result.stdout
    assert "authority_paths" in result.stdout


@pytest.mark.parametrize("schema_version", [True, 1.0, "1", None])
def test_schema_version_requires_exact_integer_one(tmp_path, schema_version):
    path = valid(tmp_path)
    state = load(path)
    state["schema_version"] = schema_version
    save(path, state)
    result = run("validate", "--state", path)
    assert result.returncode == 1
    assert "schema_version must be integer 1" in result.stdout


def test_init_does_not_overwrite(tmp_path):
    path = base(tmp_path)
    original = path.read_text()
    result = run(
        "init",
        "--state",
        path,
        "--objective",
        "overwrite",
        "--workspace",
        tmp_path,
    )
    assert result.returncode != 0
    assert path.read_text() == original


def test_relative_authority_path_resolves_against_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "authority.txt").write_text("authority")
    path = base(tmp_path)
    state = load(path)
    state["workspace"] = str(workspace)
    state["authority_paths"] = ["authority.txt"]
    state["headline_metric"] = "latency_ms"
    save(path, state)
    assert run("validate", "--state", path).returncode == 0


def test_goal_budget(tmp_path):
    result = run("goal", "--state", valid(tmp_path), "--max-chars", 4000)
    assert result.returncode == 0
    assert len(result.stdout.rstrip("\n")) <= 4000


def test_too_small_goal_fails(tmp_path):
    assert run("goal", "--state", valid(tmp_path), "--max-chars", 20).returncode != 0


def test_handoff_output(tmp_path):
    result = run("handoff", "--state", valid(tmp_path))
    assert result.returncode == 0
    assert "lifecycle_state" in result.stdout
    assert "verified_evidence" in result.stdout
    assert "live_work_authorized" in result.stdout


def test_json_round_trip(tmp_path):
    path = base(tmp_path)
    original = load(path)
    save(path, load(path))
    assert load(path) == original
