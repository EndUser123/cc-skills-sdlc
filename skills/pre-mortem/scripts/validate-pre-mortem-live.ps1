$ErrorActionPreference = "Stop"

$PackageRoot = "P:\packages\cc-skills-sdlc"
$SkillRoot = Join-Path $PackageRoot "skills\pre-mortem"
$CodexSkill = Join-Path $env:USERPROFILE ".codex\skills\pre-mortem"
$ExpectedVersion = (Get-Content -LiteralPath (Join-Path $PackageRoot ".claude-plugin\plugin.json") -Raw | ConvertFrom-Json).version

Write-Output "pre-mortem live validation starting"

if (-not (Test-Path -LiteralPath $CodexSkill)) {
    throw "Codex pre-mortem skill is not installed at $CodexSkill"
}

$CodexText = Get-Content -LiteralPath (Join-Path $CodexSkill "SKILL.md") -Raw
if ($CodexText -like "*../references/*") {
    throw "Codex installed adapter contains relative ../references paths"
}

$ReferenceMatches = [regex]::Matches($CodexText, "P:/packages/cc-skills-sdlc/skills/pre-mortem/references/[A-Za-z0-9_.\-/]+\.md")
if ($ReferenceMatches.Count -lt 7) {
    throw "Codex installed adapter exposes too few package-owned references: $($ReferenceMatches.Count)"
}

foreach ($Match in $ReferenceMatches) {
    if (-not (Test-Path -LiteralPath $Match.Value)) {
        throw "Codex adapter reference does not exist: $($Match.Value)"
    }
}
Write-Output "codex adapter validation passed"

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("premortem-live-validation-" + [System.Guid]::NewGuid().ToString("N"))
$Python = @"
from pathlib import Path
import shutil
import sys

root = Path(r"$TempRoot")
lib = Path(r"$SkillRoot") / "__lib"
sys.path.insert(0, str(lib))
from premortem_io import PreMortemSession

try:
    session = PreMortemSession.find_or_create_session(staging_root=root)
    session.setup()
    session.write_work("live validation target")
    specialists = session.get_specialists_dir()
    assert session.get_session_dir().exists()
    assert session.get_work_file().exists()
    assert specialists.exists()
    session.get_session_dir().resolve().relative_to(root.resolve())
finally:
    shutil.rmtree(root, ignore_errors=True)
"@

$TempScript = Join-Path ([System.IO.Path]::GetTempPath()) ("premortem-live-validation-" + [System.Guid]::NewGuid().ToString("N") + ".py")
try {
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($TempScript, $Python, $Utf8NoBom)
    python $TempScript
    if ($LASTEXITCODE -ne 0) {
        throw "premortem_io temporary session validation failed with exit code $LASTEXITCODE"
    }
}
finally {
    if (Test-Path -LiteralPath $TempScript) {
        Remove-Item -LiteralPath $TempScript -Force
    }
}
if (Test-Path -LiteralPath $TempRoot) {
    throw "Temporary pre-mortem live validation root was not cleaned: $TempRoot"
}
Write-Output "premortem_io temporary session validation passed"

claude plugin validate $PackageRoot | Out-String | Write-Output
if ($LASTEXITCODE -ne 0) {
    throw "claude plugin validate failed with exit code $LASTEXITCODE"
}

$Details = claude plugin details cc-skills-sdlc@local | Out-String
if ($LASTEXITCODE -ne 0) {
    throw "claude plugin details failed with exit code $LASTEXITCODE"
}
if ($Details -notmatch "pre-mortem") {
    throw "Claude plugin details does not list pre-mortem"
}
if ($Details -notmatch "adversarial-rca") {
    throw "Claude plugin details does not list adversarial-rca"
}
Write-Output "claude plugin inventory validation passed"

$CacheRoot = Join-Path $env:USERPROFILE ".claude\plugins\cache\local\cc-skills-sdlc\$ExpectedVersion"
if (-not (Test-Path -LiteralPath $CacheRoot)) {
    throw "Claude plugin cache does not contain expected version $ExpectedVersion at $CacheRoot"
}

$CacheRequired = @(
    "skills\pre-mortem\references\investigation-types.md",
    "skills\pre-mortem\references\static-test-contract.md",
    "skills\pre-mortem\references\non-static-validation.md",
    "skills\pre-mortem\references\review-lenses.md",
    "skills\pre-mortem\.codex\SKILL.md",
    "agents\adversarial-rca.md"
)

foreach ($RelativePath in $CacheRequired) {
    $Path = Join-Path $CacheRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Claude plugin cache missing $RelativePath"
    }
}

Write-Output "claude plugin cache validation passed for version $ExpectedVersion"
Write-Output "pre-mortem live validation passed"
