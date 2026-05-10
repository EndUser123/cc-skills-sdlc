"""Tests for resolve_model.py."""

import json
import pathlib

from skills.go_pi.scripts.resolve_model import resolve, MODEL_MAP


class TestModelResolution:
    """Classifier model names map to correct pi CLI flags."""

    def test_m27_resolves_to_minimax(self):
        assert resolve("M27") == "minimax/MiniMax-M2.7"

    def test_glm51_resolves_to_zai(self):
        assert resolve("GLM-5.1") == "zai/glm-5.1"

    def test_unknown_model_returns_none(self):
        assert resolve("Unknown-Model") is None

    def test_empty_string_returns_none(self):
        assert resolve("") is None

    def test_model_map_covers_all_tiers(self):
        """Every tier model in classify_complexity TIER_MODEL_MAP has a pi mapping."""
        from skills.go.scripts.classify_complexity import TIER_MODEL_MAP
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
            "model": "M27",
            "confidence": "high",
            "score": 8,
            "max_possible": 12,
            "signals": {"file_spread": 2, "criteria": 2, "verification": 2, "sensitivity": 2},
            "task_type": "implementation",
        }
        (tmp_path / "model-selection_test-run.json").write_text(
            json.dumps(selection) + "\n", encoding="utf-8"
        )

        from skills.go_pi.scripts.resolve_model import main
        main()

        out = tmp_path / "pi-model_test-run.json"
        result = json.loads(out.read_text())
        assert result["classifier_model"] == "M27"
        assert result["pi_model"] == "minimax/MiniMax-M2.7"
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

        from skills.go_pi.scripts.resolve_model import main
        main()

        out = tmp_path / "pi-model_override-run.json"
        result = json.loads(out.read_text())
        assert result["pi_model"] == "custom-model-name"
        assert result["classifier_model"] == "custom-model-name"

    def test_missing_selection_file_exits(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GO_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("RUN_ID", "missing")

        from skills.go_pi.scripts.resolve_model import main
        try:
            main()
            assert False, "Should have exited"
        except SystemExit as e:
            assert e.code == 1
