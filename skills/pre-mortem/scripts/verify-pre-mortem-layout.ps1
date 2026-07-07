$ErrorActionPreference = "Stop"

$SkillRoot = Split-Path -Parent $PSScriptRoot

$RequiredPaths = @(
    "SKILL.md",
    "skill.json",
    "references/method.md",
    "references/failure-mode-checklist.md",
    "references/output-contract.md",
    "references/pre-mortem-evidence-tiers.md",
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
    ".pi/pre-mortem-contract.md",
    "scripts/validate-pre-mortem-live.ps1"
)

$RequiredAgents = @(
    "adversarial-compliance.md",
    "adversarial-critic.md",
    "adversarial-io-validation.md",
    "adversarial-logic.md",
    "adversarial-performance.md",
    "adversarial-quality.md",
    "adversarial-rca.md",
    "adversarial-security.md",
    "adversarial-state-machine.md",
    "adversarial-testing.md"
)

$Missing = @()
foreach ($RelativePath in $RequiredPaths) {
    $Path = Join-Path $SkillRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) {
        $Missing += $RelativePath
    }
}

foreach ($AgentName in $RequiredAgents) {
    $Path = Join-Path (Split-Path -Parent (Split-Path -Parent $SkillRoot)) ("agents/" + $AgentName)
    if (-not (Test-Path -LiteralPath $Path)) {
        $Missing += ("agents/" + $AgentName)
    }
}

if ($Missing.Count -gt 0) {
    Write-Error ("Missing pre-mortem layout paths: " + ($Missing -join ", "))
}

$SkillText = Get-Content -LiteralPath (Join-Path $SkillRoot "SKILL.md") -Raw
$CodexText = Get-Content -LiteralPath (Join-Path $SkillRoot ".codex/SKILL.md") -Raw
$ExpectedReferences = @(
    "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p1_initial_review.md",
    "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p2_meta_critique.md",
    "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/phases/p3_synthesis.md",
    "references/method.md",
    "references/failure-mode-checklist.md",
    "references/output-contract.md",
    "references/pre-mortem-evidence-tiers.md",
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
    "references/historical-regression-awareness.md"
)

$Unreferenced = @()
foreach ($Reference in $ExpectedReferences) {
    if ($SkillText -notlike "*$Reference*") {
        $Unreferenced += $Reference
    }
}

if ($Unreferenced.Count -gt 0) {
    Write-Error ("SKILL.md does not reference expected paths: " + ($Unreferenced -join ", "))
}

if ($SkillText -like '*${CLAUDE_SKILL_DIR}*') {
    Write-Error 'SKILL.md still contains unresolved ${CLAUDE_SKILL_DIR} placeholder'
}

if ($CodexText -like '*../references/*') {
    Write-Error 'Codex adapter still contains ../references paths that break when installed as a junction'
}

if ($SkillText -like '*P:\\\\\\.claude/agents/*') {
    Write-Error 'SKILL.md still references root .claude agents instead of package-owned agents'
}

Write-Output "pre-mortem layout verification passed"
