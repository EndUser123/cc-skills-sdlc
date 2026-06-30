from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "__lib"))

import adversarial_review


def test_prepare_adversarial_review_context_creates_terminal_scoped_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "console_test")
    plan_file = tmp_path / "plan weird name.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")

    context = adversarial_review.prepare_adversarial_review_context(
        str(plan_file),
        root=tmp_path / "adversarial",
    )

    assert context.terminal_id == "console_test"
    assert context.sanitized_plan_name == "plan_weird_name"
    assert context.base_dir == tmp_path / "adversarial" / "plan_weird_name" / "console_test"
    assert context.workflow_stage_path.exists()
    payload = json.loads(context.workflow_stage_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "step_4a"
    assert payload["plan_path"] == str(plan_file)
    assert payload["terminal_id"] == "console_test"
    assert context.findings_paths["testing"] == context.base_dir / "testing-findings.json"


def test_resolve_prompt_template_rejects_unresolved_dispatch_tokens() -> None:
    with pytest.raises(ValueError, match="unresolved dispatch token"):
        adversarial_review.resolve_prompt_template(
            "Write findings to <findings_path> for {sanitized_plan_name}",
            plan_path="P:\\\\\\plans/example.md",
            findings_dir="P:\\\\\\.claude/plans/adversarial/example/console_test",
            findings_path="P:\\\\\\.claude/plans/adversarial/example/console_test/testing-findings.json",
        )


def test_reference_prompt_contract_uses_explicit_findings_paths() -> None:
    reference = Path(
        "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/planning/references/adversarial-agent-prompts.md"
    ).read_text(encoding="utf-8")

    assert "{sanitized_plan_name}" not in reference
    assert "<findings_path>" in reference
    assert "<findings_dir>" in reference


def test_build_dispatch_specs_uses_reference_prompts_and_exact_terminal_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "console_test")
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")

    context = adversarial_review.prepare_adversarial_review_context(
        str(plan_file),
        root=tmp_path / "adversarial",
    )
    specs = adversarial_review.build_dispatch_specs(context, phase="all")

    assert [spec.agent for spec in specs] == [
        "compliance",
        "logic",
        "testing",
        "security",
        "failure-modes",
        "critic",
    ]
    testing_spec = next(spec for spec in specs if spec.agent == "testing")
    assert str(context.findings_paths["testing"]) in testing_spec.prompt
    assert str(plan_file) in testing_spec.prompt
    assert "{sanitized_plan_name}" not in testing_spec.prompt
    assert "<findings_path>" not in testing_spec.prompt


def test_validate_findings_output_path_rejects_stale_root_level_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "console_test")
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")
    context = adversarial_review.prepare_adversarial_review_context(
        str(plan_file),
        root=tmp_path / "adversarial",
    )

    stale_root_path = tmp_path / "adversarial" / "testing-findings.json"
    stale_root_path.write_text("{}", encoding="utf-8")

    assert not adversarial_review.validate_findings_output_path(
        "testing",
        stale_root_path,
        context,
    )
    assert adversarial_review.validate_findings_output_path(
        "testing",
        context.findings_paths["testing"],
        context,
    )


def test_collect_findings_status_rejects_wrong_path_even_if_stale_root_file_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "console_test")
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")
    context = adversarial_review.prepare_adversarial_review_context(
        str(plan_file),
        root=tmp_path / "adversarial",
    )

    rogue_root_file = tmp_path / "adversarial" / "testing-findings.json"
    rogue_root_file.parent.mkdir(parents=True, exist_ok=True)
    rogue_root_file.write_text(
        json.dumps({"plan_path": str(plan_file), "findings": []}),
        encoding="utf-8",
    )
    context.findings_paths["testing"].write_text(
        json.dumps({"plan_path": str(plan_file), "findings": []}),
        encoding="utf-8",
    )

    status = adversarial_review.collect_findings_status(context, phase="phase1")

    assert "testing" in status["valid"]
    assert "testing" not in status["invalid"]
    assert rogue_root_file.exists(), "The rogue file should be ignored, not consumed or deleted"


def test_validate_findings_file_rejects_stale_and_mismatched_payloads(
    tmp_path: Path,
) -> None:
    findings_file = tmp_path / "testing-findings.json"
    findings_file.write_text(
        json.dumps({"plan_path": "P:\\\\\\wrong-plan.md", "findings": []}),
        encoding="utf-8",
    )

    mismatch = adversarial_review.validate_findings_file(
        findings_file,
        plan_path="P:\\\\\\expected-plan.md",
    )
    assert mismatch["valid"] is False
    assert mismatch["reason"] == "plan_path_mismatch"

    findings_file.write_text(
        json.dumps({"plan_path": "P:\\\\\\expected-plan.md", "findings": []}),
        encoding="utf-8",
    )
    os.utime(findings_file, (0, 0))
    stale = adversarial_review.validate_findings_file(
        findings_file,
        plan_path="P:\\\\\\expected-plan.md",
        max_age_seconds=0,
        now=1_000_000.0,
    )
    assert stale["valid"] is False
    assert stale["reason"] == "stale"


def test_adversarial_root_defaults_to_project_artifacts_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When root=None, adversarial location is the project artifacts tree, NOT the
    plan's parent directory. This keeps scratch out of ~/.claude/plans/ and out of
    the repo root. auto_verify.py searches this same tree.
    """
    monkeypatch.setenv("CLAUDE_ADVERSARIAL_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("CLAUDE_TERMINAL_ID", "console_test")
    plan_file = tmp_path / "test-plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")

    context = adversarial_review.build_adversarial_review_context(
        str(plan_file),
        root=None,
    )

    expected_base = tmp_path / "artifacts" / "test-plan" / "console_test"
    assert context.base_dir == expected_base
    assert context.findings_paths["compliance"] == expected_base / "compliance-findings.json"

    # Critical: the base_dir must NOT be co-located with the plan (the retired behavior).
    assert context.base_dir.parent.parent != plan_file.parent


def test_adversarial_root_env_var_override_takes_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLAUDE_ADVERSARIAL_ROOT redirects all adversarial output."""
    monkeypatch.setenv("CLAUDE_ADVERSARIAL_ROOT", "Z:/custom/adversarial")
    assert adversarial_review.default_adversarial_root() == Path("Z:/custom/adversarial")


def test_adversarial_root_falls_back_to_project_tree_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the env var, the default is the project artifacts tree on P:."""
    monkeypatch.delenv("CLAUDE_ADVERSARIAL_ROOT", raising=False)
    assert adversarial_review.default_adversarial_root() == Path("P:/.claude/.artifacts/adversarial")
