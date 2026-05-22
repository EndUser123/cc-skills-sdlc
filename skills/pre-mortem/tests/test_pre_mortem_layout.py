"""Layout contract tests for the package-owned pre-mortem skill."""

import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = SKILL_ROOT.parents[1]


def test_required_layout_paths_exist() -> None:
    required = [
        "SKILL.md",
        "skill.json",
        "references/method.md",
        "references/failure-mode-checklist.md",
        "references/output-contract.md",
        "references/evidence-contract.md",
        "references/modes.md",
        "references/investigation-types.md",
        "references/static-test-contract.md",
        "references/non-static-validation.md",
        "references/review-lenses.md",
        "references/project-profiles.md",
        "references/decision-model.md",
        "references/live-probe-planner.md",
        "references/finding-synthesis.md",
        "references/destructive-live-preflight.md",
        "references/historical-regression-awareness.md",
        "references/predictable-issues.md",
        "references/phases/p1_initial_review.md",
        "references/phases/p2_meta_critique.md",
        "references/phases/p3_synthesis.md",
        "__lib/premortem_io.py",
        ".codex/SKILL.md",
        ".codex/README.md",
        ".pi/pre-mortem-contract.md",
        ".pi/task-template.json",
        "scripts/verify-pre-mortem-layout.ps1",
        "scripts/validate-pre-mortem-live.ps1",
        "scripts/install-codex-adapter.ps1",
    ]

    missing = [path for path in required if not (SKILL_ROOT / path).exists()]
    assert not missing


def test_package_contains_all_dispatched_specialist_agents() -> None:
    required_agents = [
        "adversarial-compliance.md",
        "adversarial-critic.md",
        "adversarial-io-validation.md",
        "adversarial-logic.md",
        "adversarial-performance.md",
        "adversarial-quality.md",
        "adversarial-rca.md",
        "adversarial-security.md",
        "adversarial-state-machine.md",
        "adversarial-testing.md",
    ]

    missing = [name for name in required_agents if not (PACKAGE_ROOT / "agents" / name).exists()]
    assert not missing


def test_skill_manifest_points_to_authoritative_adapters_and_references() -> None:
    manifest = json.loads((SKILL_ROOT / "skill.json").read_text(encoding="utf-8"))

    assert manifest["primary_environment"] == "claude-code"
    assert manifest["adapters"]["claude"] == "SKILL.md"
    assert manifest["adapters"]["codex"] == ".codex/SKILL.md"
    assert manifest["adapters"]["pi"] == ".pi/pre-mortem-contract.md"
    assert manifest["references"]["investigation_types"] == "references/investigation-types.md"
    assert manifest["references"]["static_test_contract"] == "references/static-test-contract.md"
    assert manifest["references"]["non_static_validation"] == "references/non-static-validation.md"
    assert manifest["references"]["review_lenses"] == "references/review-lenses.md"
    assert manifest["references"]["project_profiles"] == "references/project-profiles.md"
    assert manifest["references"]["decision_model"] == "references/decision-model.md"
    assert manifest["references"]["live_probe_planner"] == "references/live-probe-planner.md"
    assert manifest["references"]["finding_synthesis"] == "references/finding-synthesis.md"
    assert manifest["references"]["destructive_live_preflight"] == "references/destructive-live-preflight.md"
    assert (
        manifest["references"]["historical_regression_awareness"]
        == "references/historical-regression-awareness.md"
    )
    assert manifest["references"]["phases"] == "references/phases"


def test_claude_skill_references_moved_phase_prompts_and_shared_contracts() -> None:
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    expected = [
        "references/method.md",
        "references/failure-mode-checklist.md",
        "references/output-contract.md",
        "references/evidence-contract.md",
        "references/modes.md",
        "references/investigation-types.md",
        "references/static-test-contract.md",
        "references/non-static-validation.md",
        "references/review-lenses.md",
        "references/project-profiles.md",
        "references/decision-model.md",
        "references/live-probe-planner.md",
        "references/finding-synthesis.md",
        "references/destructive-live-preflight.md",
        "references/historical-regression-awareness.md",
        "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p1_initial_review.md",
        "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p2_meta_critique.md",
        "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p3_synthesis.md",
    ]

    missing = [path for path in expected if path not in skill_text]
    assert not missing
    assert "skills/pre-mortem/phases" not in skill_text
    assert "${CLAUDE_SKILL_DIR}" not in skill_text
    assert "PreMortemSession.find_or_create_session()" in skill_text


def test_phase_one_uses_package_owned_specialist_agents() -> None:
    p1_text = (SKILL_ROOT / "references" / "phases" / "p1_initial_review.md").read_text(
        encoding="utf-8"
    )

    assert "P:/packages/cc-skills-sdlc/agents/{specialist}.md" in p1_text
    assert "P:/packages/cc-skills-sdlc/agents/adversarial-logic.md" in p1_text
    assert "adversarial-rca" in p1_text
    assert "P:\\\\\\.claude/agents" not in p1_text


def test_phase_prompts_require_logic_and_investigation_coverage() -> None:
    p1_text = (SKILL_ROOT / "references" / "phases" / "p1_initial_review.md").read_text(
        encoding="utf-8"
    )
    p2_text = (SKILL_ROOT / "references" / "phases" / "p2_meta_critique.md").read_text(
        encoding="utf-8"
    )
    p3_text = (SKILL_ROOT / "references" / "phases" / "p3_synthesis.md").read_text(
        encoding="utf-8"
    )

    assert "Logic Review Gate" in p1_text
    assert "Project Profile Discovery" in p1_text
    assert "Static Test Coverage" in p1_text
    assert "Non-Static Validation Coverage" in p2_text
    assert "Investigation Coverage" in p3_text
    assert "Review Lens Coverage" in p3_text
    assert "Project Profile Applied" in p3_text
    assert "Stop/Go Decision" in p3_text
    assert "Live Probe Plan" in p3_text
    assert "Historical Regression Check" in p3_text
    assert "Evidence Strength" in p3_text
    assert "Falsifier" in p3_text
    assert "Wrong-Order Risk" in p3_text
    assert "Missing Lens Fail Condition" in p2_text
    assert "stop/go blocker" in p2_text
    assert "NO-GO UNTIL FIXED" in p3_text
    assert "mandatory lens" in p3_text


def test_codex_adapter_preserves_quality_bar_without_claude_only_mechanics() -> None:
    codex_text = (SKILL_ROOT / ".codex" / "SKILL.md").read_text(encoding="utf-8")

    assert "single-agent" in codex_text
    assert "../references/" not in codex_text
    assert "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/method.md" in codex_text
    assert "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/static-test-contract.md" in codex_text
    assert "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/non-static-validation.md" in codex_text
    assert "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/review-lenses.md" in codex_text
    assert "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/project-profiles.md" in codex_text
    assert "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/decision-model.md" in codex_text
    assert "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/live-probe-planner.md" in codex_text
    assert "Stop/Go Decision" in codex_text
    assert "Live Probe Plan" in codex_text
    assert "static investigation as the default" in codex_text
    assert "Non-static probes run or recommended" in codex_text
    assert "Logic review" in codex_text
    assert "Do not spawn subagents unless the user explicitly asks" in codex_text
    assert "Data-Safety Gate" in codex_text
    assert "Outcomes must be at least as strong as the Claude Code workflow" in codex_text
    assert "Recommended Next Steps" in codex_text
    assert ".claude/.evidence" in codex_text


def test_pi_contract_is_harness_readable_and_non_destructive() -> None:
    pi_text = (SKILL_ROOT / ".pi" / "pre-mortem-contract.md").read_text(encoding="utf-8")

    assert "Inputs" in pi_text
    assert "Output" in pi_text
    assert "Exit Behavior" in pi_text
    assert "investigation_coverage" in pi_text
    assert "static_test_coverage" in pi_text
    assert "review_lens_coverage" in pi_text
    assert "project_profile_applied" in pi_text
    assert "missing_profile_sections" in pi_text
    assert "stop_go_decision" in pi_text
    assert "live_probe_plan" in pi_text
    assert "historical_regression_check" in pi_text
    assert "Do not run non-static probes unless" in pi_text
    assert "Do not perform destructive actions" in pi_text
