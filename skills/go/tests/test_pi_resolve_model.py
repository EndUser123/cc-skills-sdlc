"""Tests for resolve_model.py."""

import json
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
_RESOLVE_MODEL = _load_module(
    "go_pi_resolve_model",
    PACKAGE / "scripts" / "adapters" / "pi" / "resolve_model.py",
)
resolve = _RESOLVE_MODEL.resolve
MODEL_MAP = _RESOLVE_MODEL.MODEL_MAP


class TestModelResolution:
    """Classifier model names map to correct pi CLI flags."""

    def test_m3_resolves_to_minimax(self):
        assert resolve("M3") == "minimax/MiniMax-M3"

    def test_glm51_resolves_to_zai(self):
        assert resolve("GLM-5.1") == "zai/glm-5.1"

    def test_unknown_model_returns_none(self):
        assert resolve("Unknown-Model") is None

    def test_empty_string_returns_none(self):
        assert resolve("") is None

    def test_model_map_covers_all_tiers(self):
        """Every tier model in classify_complexity TIER_MODEL_MAP has a pi mapping."""
        classify = _load_module(
            "go_classify_complexity",
            PACKAGE / "scripts" / "classify_complexity.py",
        )
        TIER_MODEL_MAP = classify.TIER_MODEL_MAP
        for model in TIER_MODEL_MAP.values():
            assert model in MODEL_MAP, f"No pi mapping for classifier model '{model}'"


class TestResolverScript:
    """End-to-end test of the resolve_model script."""

    def test_resolves_from_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("RUN_ID", "test-run")

        # Write model-selection input
        selection = {
            "tier": "T3",
            "model": "M3",
            "confidence": "high",
            "score": 8,
            "max_possible": 12,
            "signals": {"file_spread": 2, "criteria": 2, "verification": 2, "sensitivity": 2},
            "task_type": "implementation",
        }
        (tmp_path / "model-selection_test-run.json").write_text(
            json.dumps(selection) + "\n", encoding="utf-8"
        )

        _RESOLVE_MODEL.main()

        out = tmp_path / "pi-model_test-run.json"
        result = json.loads(out.read_text())
        assert result["classifier_model"] == "M3"
        assert result["pi_model"] == "minimax/MiniMax-M3"
        assert result["tier"] == "T3"

    def test_override_tier_passes_through(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("RUN_ID", "override-run")

        selection = {
            "tier": "override",
            "model": "custom-model-name",
            "confidence": "high",
            "score": 0,
            "max_possible": 0,
            "signals": {"override": True},
            "task_type": "",
        }
        (tmp_path / "model-selection_override-run.json").write_text(
            json.dumps(selection) + "\n", encoding="utf-8"
        )

        _RESOLVE_MODEL.main()

        out = tmp_path / "pi-model_override-run.json"
        result = json.loads(out.read_text())
        assert result["pi_model"] == "custom-model-name"
        assert result["classifier_model"] == "custom-model-name"

    def test_missing_selection_file_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("RUN_ID", "missing")

        try:
            _RESOLVE_MODEL.main()
            assert False, "Should have exited"
        except SystemExit as e:
            assert e.code == 1
