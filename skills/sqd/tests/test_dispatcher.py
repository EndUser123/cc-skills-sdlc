"""Tests for SQD dispatcher — layers/dispatcher.py"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from layers.dispatcher import (
    _parse_opencode_jsonl,
    _score_from_finding,
    dispatch_parallel,
    dispatch_single,
    synthesize,
)


# ---------------------------------------------------------------------------
# _score_from_finding
# ---------------------------------------------------------------------------

class TestScoreFromFinding:
    @pytest.mark.parametrize(
        "payload,expected",
        [
            ({"score": 0.7}, 0.7),
            ({"quality_score": 0.8}, 0.8),
            ({"confidence": 0.6}, 0.6),
            ({"rating": 0.9}, 0.9),
            ({"score": 1.0}, 1.0),
            ({"score": 0.0}, 0.0),
            # nested
            ({"outer": {"score": 0.45}}, 0.45),
            ({"data": {"confidence": 0.55}, "other": {"rating": 0.65}}, 0.55),
            # no score → default
            ({}, 0.5),
            ({"summary": "no score field"}, 0.5),
            ({"text": "hello"}, 0.5),
            # wrong type
            ({"score": "high"}, 0.5),
            ({"score": None}, 0.5),
            ({"score": []}, 0.5),
            # priority order: score before quality_score
            ({"score": 0.3, "quality_score": 0.9}, 0.3),
            ({"quality_score": 0.3, "confidence": 0.9, "score": 0.1}, 0.1),
        ],
    )
    def test_score_extraction(self, payload, expected):
        assert _score_from_finding(payload) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# _parse_opencode_jsonl
# ---------------------------------------------------------------------------

class TestParseOpencodeJsonl:
    def test_step_finish_type(self):
        raw = '{"type": "step_finish", "result": {"score": 0.8}}\n'
        result = _parse_opencode_jsonl(raw)
        assert result == {"type": "step_finish", "result": {"score": 0.8}}

    def test_text_type_with_json_inner(self):
        # Inner JSON must be properly escaped within outer JSON
        raw = '{"type": "text", "part": {"text": "{\\"score\\": 0.75, \\"summary\\": \\"good\\"}"}}\n'
        result = _parse_opencode_jsonl(raw)
        assert result == {"score": 0.75, "summary": "good"}

    def test_text_type_with_plain_inner(self):
        raw = '{"type": "text", "part": {"text": "just a string"}}\n'
        result = _parse_opencode_jsonl(raw)
        assert result == {"text": "just a string"}

    def test_mixed_lines_picks_first_text(self):
        raw = '\n\n{"type": "text", "part": {"text": "{\\"score\\": 0.6}"}}\n{"type": "other"}\n'
        result = _parse_opencode_jsonl(raw)
        assert result == {"score": 0.6}

    def test_invalid_lines_skipped(self):
        raw = 'not json at all\n{"type": "step_finish", "score": 0.5}\n'
        result = _parse_opencode_jsonl(raw)
        assert result == {"type": "step_finish", "score": 0.5}

    def test_empty_input(self):
        assert _parse_opencode_jsonl("") is None
        assert _parse_opencode_jsonl("\n\n  \n") is None

    def test_only_whitespace_lines(self):
        raw = "   \n\t\n\n   \n"
        assert _parse_opencode_jsonl(raw) is None

    def test_all_invalid_json(self):
        raw = 'hello world\nfoo bar\n'
        assert _parse_opencode_jsonl(raw) is None


# ---------------------------------------------------------------------------
# dispatch_parallel — consensus + failure + divergent logic
# ---------------------------------------------------------------------------

class TestDispatchParallel:
    @pytest.fixture
    def output_dir(self, tmp_path):
        return tmp_path / "findings"

    @pytest.mark.asyncio
    async def test_consensus_all_same_score_bucket(self, output_dir):
        """When all models return scores in the same integer bucket → exit 0."""

        async def mock_deepseek(t, m, o):
            return {"score": 0.7, "model": "deepseek", "finding_text": "a"}

        async def mock_gemini(t, m, o):
            return {"score": 0.75, "model": "gemini", "finding_text": "a"}

        # Patch dispatch_single for deepseek and gemini
        # We test the logic by calling dispatch_parallel with pre-built findings
        # Since dispatch_single is async with subprocess, mock it per-model

        # Actually: use a real dispatch_parallel but with a patched dispatch_single
        import layers.dispatcher as disp

        orig = disp.dispatch_single

        async def patched(target, model, output_dir):
            return {"score": 0.72, "model": model, "finding_text": "ok"}

        disp.dispatch_single = patched
        try:
            exit_code = await dispatch_parallel("target", ["deepseek", "gemini"], output_dir)
        finally:
            disp.dispatch_single = orig

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_divergent_scores_different_buckets(self, output_dir):
        """When scores fall in different integer buckets → exit 1 + synthesis written."""
        import layers.dispatcher as disp

        orig = disp.dispatch_single

        scores = {"deepseek": 0.7, "gemini": 0.3}  # different buckets: 7 vs 3

        async def patched(target, model, output_dir):
            return {"score": scores[model], "model": model, "finding_text": "ok"}

        disp.dispatch_single = patched
        try:
            exit_code = await dispatch_parallel("target", ["deepseek", "gemini"], output_dir)
        finally:
            disp.dispatch_single = orig

        assert exit_code == 1
        assert (output_dir / "synthesis.json").exists()

    @pytest.mark.asyncio
    async def test_model_failure_returns_exit_2(self, output_dir):
        """When dispatch_single raises an Exception → exit 2."""
        import layers.dispatcher as disp

        orig = disp.dispatch_single

        async def patched(target, model, output_dir):
            raise RuntimeError(f"opencode ({model}) failed")

        disp.dispatch_single = patched
        try:
            exit_code = await dispatch_parallel("target", ["deepseek"], output_dir)
        finally:
            disp.dispatch_single = orig

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_empty_models_list_returns_exit_3(self, output_dir):
        exit_code = await dispatch_parallel("target", [], output_dir)
        assert exit_code == 3

    @pytest.mark.asyncio
    async def test_synthesis_writes_findings_array(self, output_dir):
        """synthesize() writes a JSON file with the findings list."""
        findings = [
            {"score": 0.8, "model": "deepseek", "finding_text": "good"},
            {"score": 0.3, "model": "gpt", "finding_text": "bad"},
        ]
        await synthesize(findings, output_dir)

        path = output_dir / "synthesis.json"
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert "findings" in data
        assert len(data["findings"]) == 2


# ---------------------------------------------------------------------------
# dispatch_single — OSError / TimeoutError paths (no real opencode)
# ---------------------------------------------------------------------------

class TestDispatchSingleErrors:
    @pytest.mark.asyncio
    async def test_unknown_model_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown model"):
            await dispatch_single("target", "unknown_model", tmp_path)


# ---------------------------------------------------------------------------
# CLI smoke test — import and argument parsing
# ---------------------------------------------------------------------------

def test_cli_importable():
    """The sqd package is importable and has dispatch_parallel."""
    from layers.dispatcher import dispatch_parallel, MODELS

    assert MODELS == {"deepseek", "gemini", "claude", "gpt"}
    assert callable(dispatch_parallel)


def test_opencode_model_map_coverage():
    """All MODELS names are mapped in OPENCODE_MODEL_MAP."""
    from layers.dispatcher import MODELS, OPENCODE_MODEL_MAP

    assert MODELS == set(OPENCODE_MODEL_MAP.keys())
