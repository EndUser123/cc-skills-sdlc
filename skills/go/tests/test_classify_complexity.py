"""Tests for classify_complexity.py."""

import os
import json
import pathlib
import tempfile

from skills.go.scripts.classify_complexity import classify, TIER_MODEL_MAP


def _make_task(**overrides) -> dict:
    base = {
        "id": "TASK-001",
        "title": "Test task",
        "objective": "Test objective",
        "status": "ready",
        "priority": "P1",
        "scope_in": [],
        "scope_out": [],
        "forbidden_files": [],
        "acceptance_criteria": ["Pass tests"],
        "verification_commands": ["pytest -q"],
    }
    base.update(overrides)
    return base


class TestPresetComplexity:
    """When estimated_complexity is pre-set, use it directly."""

    def test_high_preset_returns_t4_glm(self):
        result = classify(_make_task(estimated_complexity="high"))
        assert result["tier"] == "T4"
        assert result["model"] == "GLM-5.1"

    def test_low_preset_returns_t1_m27(self):
        result = classify(_make_task(estimated_complexity="low"))
        assert result["tier"] == "T1"
        assert result["model"] == "M27"


class TestConfigTasks:
    """Config tasks only use verification signal — should max at T1."""

    def test_config_with_many_forbidden_files_still_t1(self):
        result = classify(_make_task(
            task_type="config",
            forbidden_files=["a.py", "b.py", "c.py", "d.py"],
            verification_commands=["pytest -q"],
        ))
        assert result["tier"] == "T1"
        assert result["model"] == "M27"

    def test_config_with_no_verification(self):
        result = classify(_make_task(task_type="config", verification_commands=[]))
        assert result["tier"] == "T1"


class TestImplementationTasks:
    """Implementation tasks use full signal set."""

    def test_simple_implementation_t1(self):
        result = classify(_make_task(
            task_type="implementation",
            scope_in=["src/main.py"],
            acceptance_criteria=["Works"],
            verification_commands=["pytest -q"],
        ))
        assert result["tier"] == "T1"
        assert result["model"] == "M27"

    def test_complex_implementation_t3(self):
        result = classify(_make_task(
            task_type="implementation",
            scope_in=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"],
            acceptance_criteria=[
                "Criterion 1", "Criterion 2", "Criterion 3",
                "Criterion 4", "Criterion 5", "Criterion 6",
            ],
            verification_commands=["pytest", "ruff check", "mypy", "bandit"],
            forbidden_files=["secrets.env"],
        ))
        assert result["model"] == "M27"


class TestDesignTasks:
    """Design tasks include task_type weight signal — can reach T4."""

    def test_design_with_large_scope_reaches_t4(self):
        result = classify(_make_task(
            task_type="design",
            scope_in=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"],
            acceptance_criteria=[
                "Arch constraint 1", "Arch constraint 2", "Arch constraint 3",
                "Arch constraint 4", "Arch constraint 5", "Arch constraint 6",
            ],
            verification_commands=["pytest", "ruff check", "mypy", "bandit"],
            forbidden_files=["secrets.env", "config.py"],
        ))
        assert result["tier"] == "T4"
        assert result["model"] == "GLM-5.1"


class TestConfidence:
    """Confidence is high when signals agree, medium when spread."""

    def test_uniform_signals_high_confidence(self):
        result = classify(_make_task(
            scope_in=["a.py"],
            acceptance_criteria=["Criterion 1"],
            verification_commands=["pytest"],
            forbidden_files=[],
        ))
        assert result["confidence"] == "high"

    def test_divergent_signals_medium_confidence(self):
        result = classify(_make_task(
            task_type="implementation",
            scope_in=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"],  # 3pts
            acceptance_criteria=["Criterion 1"],  # 1pt
            verification_commands=["pytest"],  # 1pt
            forbidden_files=[],  # 1pt
        ))
        assert result["confidence"] == "medium"


class TestTierModelMap:
    """Verify tier -> model mapping."""

    def test_t1_t2_t3_all_m27(self):
        for tier in ("T1", "T2", "T3"):
            assert TIER_MODEL_MAP[tier] == "M27"

    def test_t4_is_glm51(self):
        assert TIER_MODEL_MAP["T4"] == "GLM-5.1"


class TestOverride:
    """GO_MODEL_OVERRIDE bypasses classification."""

    def test_override_env_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GO_MODEL_OVERRIDE", "custom-model")
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("RUN_ID", "test-override")

        from skills.go.scripts.classify_complexity import main
        main()

        out = tmp_path / "model-selection_test-override.json"
        result = json.loads(out.read_text())
        assert result["model"] == "custom-model"
        assert result["tier"] == "override"
