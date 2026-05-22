$ErrorActionPreference = "Stop"

$SkillRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $SkillRoot ".codex"
$Destination = Join-Path $env:USERPROFILE ".codex\skills\pre-mortem"

if (-not (Test-Path -LiteralPath $Source)) {
    throw "Codex adapter source not found: $Source"
}

$DestinationParent = Split-Path -Parent $Destination
if (-not (Test-Path -LiteralPath $DestinationParent)) {
    New-Item -ItemType Directory -Path $DestinationParent | Out-Null
}

if (Test-Path -LiteralPath $Destination) {
    $Existing = Get-Item -LiteralPath $Destination -Force
    if ($Existing.LinkType -eq "Junction" -or $Existing.LinkType -eq "SymbolicLink") {
        Remove-Item -LiteralPath $Destination -Force
    } else {
        throw "Destination already exists and is not a link: $Destination"
    }
}

New-Item -ItemType Junction -Path $Destination -Target $Source | Out-Null
Write-Output "Installed Codex pre-mortem adapter: $Destination -> $Source"
